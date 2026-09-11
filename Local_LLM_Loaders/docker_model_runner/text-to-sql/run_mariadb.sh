docker run -d \
  --name mariadb-main \
  -e MYSQL_ROOT_PASSWORD=CHANGE_ME_ROOT_PASSWORD \
  -e MYSQL_DATABASE=connect_test_db \
  -e MYSQL_USER=appuser \
  -e MYSQL_PASSWORD=CHANGE_ME_APP_PASSWORD \
  -v $(pwd)/init.sql:/docker-entrypoint-initdb.d/init.sql \
  -v $(pwd)/mariadb.cnf:/etc/mysql/mariadb.cnf \
  -p 3306:3306 \
  mariadb:10.5.10
