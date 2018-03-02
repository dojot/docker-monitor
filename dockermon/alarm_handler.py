""" Docker alarm service.

This module implements an alarm service for monitoring when containers
are running or not.

Todo:
    * integrate with the dojot alarm manager.
    * align the status of the alarms when the service starts.
"""
import docker
import logging
import threading
import requests

from datetime import datetime
from alarmlibrary.connection import RabbitMqClientConnection
from alarmlibrary.alarm import Alarm, AlarmSeverity
from alarmlibrary.exceptions import (AuthenticationError, ConnectionClosed, AlarmManagerException, InvalidAlarm)


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
        # TODO Align the alarms

        while True:
            try:
                for event in self.__docker_client.events(filters={'Type': 'container'}, decode=True):

                    if event['Action'] == 'die' \
                            or event['Action'] == 'stop' \
                            or event['Action'] == 'start' \
                            or event['Action'] == 'pause' \
                            or event['Action'] == 'unpause':

                        self.__logger.debug("Received event: {0}".format(event))

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

                        # send alarm to dojot alarm server
                        alarm = self.__make_dojot_alarm(data)
                        try:
                            self.__alarm_client.send(alarm)
                        except (InvalidAlarm, ValueError):
                            self.__logger.error("Not well-formed alarm {0}. Discarding alarm ...".
                                                format(alarm))
                        except ConnectionClosed:
                            # TODO try to reconnect and resend the alarm.
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

    def __make_dojot_alarm(self, data):
        """Makes an alarm to send to dojot Alarm Manager"""
        self.__logger.info("Making alarm: {0}".format(data))
        alarm = Alarm(data['domain'],
                      data['namespace'],
                      AlarmSeverity[data['severity']],
                      datetime.fromtimestamp(data['eventTimestamp']),
                      data['description'])
        alarm.add_primary_subject('container', data['primarySubject']['container'])
        alarm.add_primary_subject('image', data['primarySubject']['image'])
        alarm.add_additional_data('exitCode', data['additional-field']['exitCode'])
        alarm.add_additional_data('imageId', data['additional-field']['imageId'])

        return alarm
