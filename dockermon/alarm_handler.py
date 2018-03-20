""" Docker alarm service.

This module implements an alarm service for monitoring when containers
are running or not.
"""

import docker
import logging
import threading
import requests
import time

from datetime import datetime
from alarmlibrary.connection import RabbitMqClientConnection
from alarmlibrary.alarm import Alarm, AlarmSeverity
from alarmlibrary.exceptions import (AuthenticationError, ConnectionClosed,
                                     AlarmManagerException, InvalidAlarm)


class AlarmHandler:
    """Handler for monitoring the status of the docker containers.
    """

    def __init__(self, host, port, user, password):
        """Initializes the logger, docker client, and the background thread
        for the monitoring loop.
        """
        self.__logger = logging.getLogger('docker-monitor.alarms')

        # docker client
        self.__docker_client = docker.from_env()

        # alarm client
        self.__alarm_client = RabbitMqClientConnection()
        try:
            self.__logger.info("Connecting to {0}:{1}@{2}:{3}".format(user, password,host, port))
            self.__alarm_client.open(host, port, user, password)
        except AuthenticationError as ex:
            self.__logger.error("Authentication error while connecting to RabbitMQ server. Exiting ...")
            raise SystemExit("Authentication error while connecting to RabbitMQ server.")
        except (ConnectionClosed, AlarmManagerException):
            self.__logger.error("Unexpected error while connecting to RabbitMQ server. Exiting ...")
            raise SystemExit("Unexpected error while connecting to RabbitMQ server.")

        # thread pool
        self.__thread = threading.Thread(target=self.run, args=())
        self.__thread.daemon = True
        self.__thread.start()

    def run(self):
        """Infinite loop for monitoring the status of the docker containers.
        It listen to the following container's events: die, stop, start, pause, and unpause.
        """
        # align alarms
        self.__logger.info("Aligning the current status of the alarms")
        since = 0
        until = time.time()
        self.__align_alarms(since, until)

        # start infinite loop
        self.__logger.info("Starting the infinite loop for handling docker events")
        since = until + 1
        while True:
            try:
                for event in self.__docker_client.events(filters={'Type': 'container'},
                                                         since=since,
                                                         decode=True):
                    since = event['time'] + 1
                    alarm = self.__make_alarm(event)
                    if alarm is not None:
                        self.__logger.info("Sending alarm: {0}".format(alarm.serialize()))
                        try:
                            self.__alarm_client.send(alarm)
                        except (InvalidAlarm, ValueError):
                            self.__logger.error("Not well-formed alarm {0}. Discarding alarm ...".
                                            format(alarm))
                        except ConnectionClosed:
                            self.__logger.error("Connection to RabbitMQ server was closed. Exiting ...")
                            raise SystemExit("Connection to RabbitMQ server was closed.")

            except docker.errors.APIError:
                self.__logger.error('Communication with docker socket failed.')

    def __get_image_sha256(self, name):
        """Gets the image identifier (sha256) for a given docker image."""
        try:
            image = self.__docker_client.images.get(name)
            image_sha256 = image.id

        except docker.errors.ImageNotFound:
            self.__logger.error('Image {0} not found.'.format(name))
            image_sha256 = 'Unknown'
        except requests.exceptions.ReadTimeout:
            self.__logger.error('Communication with docker timed out.')
            image_sha256 = 'Unknown'
        except docker.errors.APIError:
            self.__logger.error('Communication with docker socket failed.')
            image_sha256 = 'Unknown'

        return image_sha256

    def __make_alarm(self, event):
        """Makes an alarm to send to dojot Alarm Manager"""
        self.__logger.debug("Making alarm from event {0}".format(event))

        alarm = None
        if event['Action'] == 'die' \
                or event['Action'] == 'stop' \
                or event['Action'] == 'start' \
                or event['Action'] == 'pause' \
                or event['Action'] == 'unpause':

            self.__logger.debug("Processing event.")

            data = {'namespace': 'dojot.docker',
                    'domain': 'ContainerError',
                    'eventTimestamp': event['time']}

            # Container went down
            if event['Action'] == 'die' or event['Action'] == 'stop':
                data['description'] = 'container went down'
                data['severity'] = 'Major'
                data['primarySubject'] = {'container': event['Actor']['Attributes']['name'],
                                          'image': event['Actor']['Attributes']['image']}

            # Container went up
            elif event['Action'] == 'start':
                data['description'] = 'container went up'
                data['severity'] = 'Clear'
                data['primarySubject'] = {'container': event['Actor']['Attributes']['name'],
                                          'image': event['Actor']['Attributes']['image']}

            # Processes were paused
            elif event['Action'] == 'pause':
                data['description'] = 'container processes were paused'
                data['severity'] = 'Major'
                data['primarySubject'] = {'container': event['Actor']['Attributes']['name'],
                                          'image': event['Actor']['Attributes']['image']}

            # Processes were unpaused
            elif event['Action'] == 'unpause':
                data['description'] = 'container processes were unpaused'
                data['severity'] = 'Clear'
                data['primarySubject'] = {'container': event['Actor']['Attributes']['name'],
                                          'image': event['Actor']['Attributes']['image']}

            # additional data
            data['additional-field'] = {'exitCode': (event['Actor']['Attributes']).get('exitCode', 'NA'),
                                        'imageId': self.__get_image_sha256(
                                            event['Actor']['Attributes']['image'])}

            alarm = Alarm(data['domain'],
                          data['namespace'],
                          AlarmSeverity[data['severity']],
                          datetime.fromtimestamp(data['eventTimestamp']),
                          data['description'])
            alarm.add_primary_subject('container', data['primarySubject']['container'])
            alarm.add_primary_subject('image', data['primarySubject']['image'])
            alarm.add_additional_data('exitCode', data['additional-field']['exitCode'])
            alarm.add_additional_data('imageId', data['additional-field']['imageId'])
        else:
            self.__logger.debug("Discarding event.")

        return alarm

    def __align_alarms(self, since, until):
        """Sends the last alarms that happened in the time window (since, until) """
        self.__logger.info("Aligning alarms since {0} until {1}".format(since, until))

        # keep the last alarm for each container
        alarms = {}
        try:
            for event in self.__docker_client.events(filters={'Type': 'container'},
                                                     since=since, until=until, decode=True):
                alarm = self.__make_alarm(event)
                if alarm is not None:
                    self.__logger.info("OK")
                    self.__logger.info(alarm.serialize())
                    alarms[event['Actor']['Attributes']['name']] = alarm
        except docker.errors.APIError:
            self.__logger.error('Communication with docker socket failed. Alarms cannot be aligned!')

        # send the last alarms
        for container in alarms:
            alarm = alarms[container]
            self.__logger.info("Sending alarm: {0}".format(alarm.serialize()))
            try:
                self.__alarm_client.send(alarm)
            except (InvalidAlarm, ValueError):
                self.__logger.error("Not well-formed alarm {0}. Discarding alarm ...".
                                    format(alarm))
            except ConnectionClosed:
                self.__logger.error("Connection to RabbitMQ server was closed. Exiting ...")
                raise SystemExit("Connection to RabbitMQ server was closed.")
