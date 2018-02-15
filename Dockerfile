FROM python:3.6

RUN mkdir -p /usr/src/app

ADD . /usr/src/app
WORKDIR /usr/src/app

RUN ["python3", "setup.py", "develop"]

EXPOSE 5000

CMD ["./docker/entrypoint.sh", "start"]
