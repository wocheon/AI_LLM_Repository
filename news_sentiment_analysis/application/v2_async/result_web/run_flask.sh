docker rm celery_result_page_flask -f

#	--network=host  \
docker run -d  \
	--network=app-network \
	-p 80:5000  \
	-v .:/app  \
	--name celery_result_page_flask celery_result_page_flask:latest
