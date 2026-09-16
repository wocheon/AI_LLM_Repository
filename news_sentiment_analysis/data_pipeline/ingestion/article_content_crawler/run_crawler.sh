#!/bin/bash
docker rm article_content_collector_desc -f

docker run -d \
	--network=app-network  \
	-v ./log:/app/log \
	--name article_content_collector_desc article_content_collector_desc:latest

docker logs article_content_collector_desc -f
