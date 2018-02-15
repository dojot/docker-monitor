import logging

from dockermon.app import app
from dockermon import metric_handler
from dockermon import alarm_handler

# set logger
logger = logging.getLogger('docker-monitor')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
channel = logging.StreamHandler()
channel.setFormatter(formatter)
logger.addHandler(channel)

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
