
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path='/app/docker/.env')

password=os.getenv('MYSQL_TEST_DB_ROOT_PASSWORD')

config = {
    'database': {
        'user': 'root',
        'password': password,
        'host': 'test-database',
        'database': 'eyened_database',
        'port': '3306',
        'raise_on_warnings': True
    },
    'annotations_path': 'missing',
    'viewer_url': 'missing'
}

