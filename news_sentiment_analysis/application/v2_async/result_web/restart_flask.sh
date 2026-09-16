#!/bin/bash
sh docker_build.sh
sh run_flask.sh
docker logs -f celery_result_page_flask