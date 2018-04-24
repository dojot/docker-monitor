FROM python:3.6-alpine

EXPOSE 5000
CMD ["./docker/entrypoint.sh", "start"]
WORKDIR /usr/src/app

RUN apk --no-cache add git gcc musl-dev && \
    mkdir -p /usr/src/app
ADD . /usr/src/app
RUN python3 setup.py develop && \
    apk del git gcc musl-dev
