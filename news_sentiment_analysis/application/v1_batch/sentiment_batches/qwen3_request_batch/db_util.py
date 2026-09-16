import configparser
import pymysql

def get_db_conn():
    config = configparser.ConfigParser()
    config.read('config.ini')
    dbcfg = config['mysql']
    conn = pymysql.connect(
        host=dbcfg['host'],
        port=int(dbcfg.get('port', 3306)),
        user=dbcfg['user'],
        password=dbcfg['password'],
        db=dbcfg['database'],
        charset=dbcfg.get('charset', 'utf8mb4'),
        autocommit=True
    )
    return conn
