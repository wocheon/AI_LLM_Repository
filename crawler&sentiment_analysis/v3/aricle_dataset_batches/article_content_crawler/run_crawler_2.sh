#!/bin/bash
docker rm article_content_collector_desc_2 -f

docker run --rm -d \
	--network=app-network  \
	-v ./log:/app/log \
	--name article_content_collector_desc_2 article_content_collector_desc:latest

docker logs article_content_collector_desc_2 -f
