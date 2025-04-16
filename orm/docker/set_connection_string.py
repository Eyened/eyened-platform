import configparser
import os
from dotenv import load_dotenv

filename = '/app/alembic_/alembic.ini'

# Load the .env file (one directory up from 'app' folder)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

password=os.getenv('MYSQL_TEST_DB_ROOT_PASSWORD')

config = configparser.ConfigParser()
config.read(filename)
config.set('alembic', 'sqlalchemy.url', f'mysql+pymysql://root:{password}@test-database:3306/eyened_database')
with open(filename, 'w') as configfile:
    config.write(configfile)
