# docker-monitor


[![License badge](https://img.shields.io/badge/license-GPL-blue.svg)](https://opensource.org/licenses/GPL-3.0)

It is a very simple service for monitoring docker containers in dojot deployments.

It provides a REST API to query for container statistics and also publishes alarms when
problems happen.


## Dependencies

It depends on:

- flask
- docker
- requests
- gunicorn
- gevent
- [alarm-client-python](https://github.com/dojot/alarm-client-python)

## Usage

The API for getting statistics is defined in the table bellow. 

| Http Method   | URI                                                                 | Action                                |
| ------------- |---------------------------------------------------------------------| --------------------------------------|
| GET           | `http://<hostname>/docker-monitor/api/v1.0/metrics`                 | Retrieve metrics for all containers   |
| GET           | `http://<hostname>/docker-monitor/api/v1.0/metrics/<container-name>`| Retrieve metrics for a given container|


In case of success, the GET `https://github.com/dojot/alarm-client-python` returns:
```json
[
{
 "<container-name-1>": {"status": "<status>",
                        "cpu":    "<percentage_of_cpu>",
                        "mem":    "<percentage_of_mem>"}
},

...

{
 "<container-name-n>": {"status": "<status>",
                         "cpu":    "<percentage_of_cpu>",
                         "mem":    "<percentage_of_mem>"}

}
]
```
 
and the GET `http://<hostname>/docker-monitor/api/v1.0/metrics/<container-name>` returns:

```json
{
 "<container-name>": {"status": "<status>",
                      "cpu":    "<percentage_of_cpu>",
                      "mem":    "<percentage_of_mem>"}
}
```

The docker-monitor also runs a background thread which listen to docker events, generating the following alarms:

- Container went down (docker events: die, stop)
```json
{
 "namespace":      "dojot.docker.container",
 "domain":         "docker container status change",
 "eventTimestamp": "<timestamp>",
 "description":    "container went down",
 "severity":       "Major",
 "primarySubject": {"container": "<container-name>",
                    "image":     "<image-name>"}
 }
```

- Container went up (docker event: start)
```json
{
 "namespace":      "dojot.docker.container",
 "domain":         "docker container status change",
 "eventTimestamp": "<timestamp>",
 "description":    "container went up",
 "severity":       "Clear",
 "primarySubject": {"container": "<container-name>",
                    "image":     "<image-name>}"}
 }
```

- Container processes were paused (docker event: pause)
```json
{
 "namespace":      "dojot.docker.container",
 "domain":         "docker container status change",
 "eventTimestamp": "<timestamp>",
 "description":    "container processes were paused",
 "severity":       "Major",
 "primarySubject": {"container": "<container-name>",
                    "image":     "<image-name>}"}
 }
```

- Container processes were unpaused (docker event: unpaused)
```json
{
 "namespace":      "dojot.docker.container",
 "domain":         "docker container status change",
 "eventTimestamp": "<timestamp>",
 "description":    "container processes were unpaused",
 "severity":       "Clear",
 "primarySubject": {"container": "<container-name>",
                    "image":     "<image-name>"}
 }
```

## How to run

The service must have access to the docker socket. So, when run the container mount
the the docker socket as a volume.

```bash
sudo docker run -d -v /var/run/docker.sock:/var/run/docker.sock docker-monitor
```


