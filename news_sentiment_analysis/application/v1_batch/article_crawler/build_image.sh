#!/bin/bash
docker image rm -f selenium_crawler_test:latest
docker build --rm -t selenium_crawler_test:latest .
