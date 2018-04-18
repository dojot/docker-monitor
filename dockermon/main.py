import os
import logging

from dockermon.app import app
from dockermon import metric_handler as metric
from dockermon import alarm_handler as alarm

# set logger
logger = logging.getLogger('docker-monitor')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
channel = logging.StreamHandler()
channel.setFormatter(formatter)
logger.addHandler(channel)

# start alarm handler
host = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
port = os.environ.get('RABBITMQ_PORT', '5672')
user = os.environ.get('RABBITMQ_USER', 'guest')
password = os.environ.get('RABBITMQ_PASSWORD', 'guest')
alarm.AlarmHandler(host, port, user, password)

# start metric handler
metric.MetricHandler()

if __name__ == '__main__':
    # start rest server
    app.run(host='0.0.0.0', threaded=True)
