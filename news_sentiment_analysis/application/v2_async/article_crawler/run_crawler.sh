#!/bin/bash
docker rm celery_collector -f

docker run --rm -d \
	--network=app-network  \
	-v ./log:/app/log \
	--name celery_collector celery_collector:latest

docker logs celery_collector -f
