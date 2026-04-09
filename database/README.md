## EyeNED Database Setup

Optionally:

Specify EYENED_DATABASE_PORT and EYENED_ADMINER_PORT in .env

Run: 
```bash
docker compose up -d
```

Optionally import data dump from other database:
```bash
./load_dump.sh /path/to/dump
```
