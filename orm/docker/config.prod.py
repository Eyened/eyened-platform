
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path='/app/docker/.env')

user=os.getenv('MYSQL_EYENED_DB_USER')
password=os.getenv('MYSQL_EYENED_DB_PASSWORD')

config = {
    'database': {
        'user': user,
        'password': password,
        'host': 'eyened-server',
        'database': 'eyened_database',
        'port': '22111',
        'raise_on_warnings': True
    },
    'annotations_path': 'missing',
    'viewer_url': 'missing'
}

