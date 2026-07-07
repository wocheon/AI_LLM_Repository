#!/bin/bash
docker image rm -f celery_collector:latest
docker build --rm -t celery_collector:latest .