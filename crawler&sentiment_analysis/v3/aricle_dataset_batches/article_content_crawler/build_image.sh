#!/bin/bash
docker image rm -f article_content_collector_desc:latest
docker build --rm -t article_content_collector_desc:latest .
