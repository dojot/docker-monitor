""" Docker container metric service.

This module implements a REST service for getting statistic metrics
from docker containers.
"""
import docker
import logging
import requests

from dockermon.app import app
from flask import jsonify, make_response, abort
from multiprocessing.pool import ThreadPool


class MetricHandler:
    """Handler for getting metrics from docker containers.
    """
    MAX_THREAD_POOL_SIZE = 25
    """(int): maximum size of the thread pool for parallel call of docker client. 
    """
    DOCKER_CLIENT_TIMEOUT = 3
    """(int): timeout in seconds for calling docker client.
    """

    def __init__(self):
        """Initializes the logger and the docker client connection.
        """
        self.__logger = logging.getLogger('docker-monitor.metrics')
        self.__docker_client = docker.from_env(timeout=self.DOCKER_CLIENT_TIMEOUT)

    def get_metrics_by_container(self, name):
        """Gets statistic metrics for a given container.

        Metrics:
            It gets the container status, the percentage of CPU usage,
            and the percentage of memory usage.

        :param(str) name: container name.
        :return(dic): container metrics.
        """
        metrics = {}
        try:
            container = self.__docker_client.containers.get(name)

            # name
            metrics[container.name] = {}
            # status
            metrics[container.name]['status'] = container.status

            if container.status == 'running':
                data = container.stats(stream=False)
                self.__logger.debug('container name: {0} statistics:{1}'.
                                    format(container.name, data))
                # cpu usage (percent)
                metrics[container.name]['cpu'] = self.__calculate_cpu_percent(data)

                # memory usage (percent)
                metrics[container.name]['mem'] = self.__calculate_mem_percent(data)

                self.__logger.debug('container name: {0} metrics:{1}'.
                                    format(container.name, metrics))
        except docker.errors.NotFound:
            self.__logger.error('Container {0} not found.'.format(name))
            abort(404)
        except requests.exceptions.ReadTimeout:
            self.__logger.error('Communication with docker timed out.')
            abort(408)
        except docker.errors.APIError:
            self.__logger.error('Communication with docker socket failed.')
            abort(500)

        return metrics

    def get_metrics(self):
        """Gets statistic metrics for all running containers.

        Since the calls to the docker client are slow, this method
        uses a pool of threads to getting the metrics in parallel;
        speeding up the response time.

        :return(dic): metrics for all running containers.
        """
        containers = self.__get_docker_containers()

        with ThreadPool(min(self.MAX_THREAD_POOL_SIZE, len(containers))) as pool:
            all_metrics = pool.map(self.get_metrics_by_container, containers)

        return all_metrics

    @staticmethod
    def __calculate_cpu_percent(data):
        """Calculates the percentage of CPU usage.
        :param data: docker statistics coded as a dictionary.
        :return: percentage of cpu usage.
        """
        cpu_percent = 0.0

        cpu_count = len(data["cpu_stats"]["cpu_usage"]["percpu_usage"])

        cpu_delta = (float(data['cpu_stats']['cpu_usage']['total_usage']) -
                     float(data['precpu_stats']['cpu_usage']['total_usage']))

        system_delta = (float(data["cpu_stats"]["system_cpu_usage"]) -
                        float(data["precpu_stats"]["system_cpu_usage"]))

        if system_delta > 0.0:
            cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count

        return cpu_percent

    @staticmethod
    def __calculate_mem_percent(data):
        """Calculates the percentage of memory usage.

        :param data: docker statistics coded as a dictionary.
        :return: percentage of memory usage.
        """
        mem_percent = 0.0

        mem_usage = float(data['memory_stats']['usage'])

        mem_limit = float(data['memory_stats']['limit'])

        if mem_limit > 0.0:
            mem_percent = mem_usage / mem_limit * 100

        return mem_percent

    def __get_docker_containers(self):
        """Gets a list of container names.
        :return: list of container names.
        """
        containers = []

        try:
            containers = [container.name for container in self.__docker_client.containers.list()]
        except requests.exceptions.ReadTimeout:
            self.__logger.error('Communication with docker timed out.')
            abort(408)
        except docker.errors.APIError:
            self.__logger.error('Communication with docker socket failed.')
            abort(500)

        return containers


# Metric handler
handler = MetricHandler()


# REST API
# Gets metrics for all containers
@app.route('/docker-monitor/api/v1.0/metrics', methods=['GET'])
def get_metrics():
    return jsonify(handler.get_metrics())


# Gets metrics for an individual container
@app.route('/docker-monitor/api/v1.0/metrics/<string:container_name>', methods=['GET'])
def get_metrics_by_container(container_name):
    return jsonify(handler.get_metrics_by_container(container_name))


# Not found
@app.errorhandler(404)
def resource_not_found(error):
    return make_response(jsonify({'error': 'Resource not found'}), 404)


# Request timeout
@app.errorhandler(408)
def resource_not_found(error):
    return make_response(jsonify({'error': 'The server is overloaded. Try later.'}), 408)


# Internal server error
@app.errorhandler(500)
def resource_not_found(error):
    return make_response(jsonify({'error': 'The server encountered an internal '
                                           'error and was unable to complete your request.'}), 500)
