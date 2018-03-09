# -*- coding: utf-8 -*-
#https://pythonhosted.org/versiontools/usage.html
from setuptools import setup, find_packages


setup(
    name='dockermon',
    description='Dojot docker monitor.',
    version='0.0.1',

    packages=find_packages(exclude=('docker',)),
    include_package_data=True,
    install_requires=[
        'flask==0.12',
        'docker==2.7.0',
        'requests==2.18.4',
        'gunicorn==19.6.0',
        'gevent==1.2.2',
        'dojot-alarmlibrary'
    ],
    dependency_links=[
        'git+git://github.com/dojot/alarm-client-python@master#egg=dojot-alarmlibrary'
    ],
    python_requires='>=3.6.0',
    author='Rafael Augusto Scaraficci',
    author_email='raugusto@cpqd.com.br',
    url='https://github.com/dojot/docker-monitor',
)