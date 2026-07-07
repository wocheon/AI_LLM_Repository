#!/bin/bash
sh docker_build.sh
sh run_flask.sh
docker logs -f result_page_flask