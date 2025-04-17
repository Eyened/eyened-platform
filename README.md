# eyened-platform

## Overview

## Features

## Installation 

### Prerequisites
- Docker and Docker Compose
- MySQL database
- Nginx (for file serving)

### Database Setup
1. Set up a MySQL database
2. Initialize the database schema:
    - Use eyened_orm
3. Configure the database:
   - Add an entry to the `Creator` table to enable login
   - For segmentation features: add desired features to the `Feature` table
   - For form annotations: add entries to the `FormSchema` table

### File Server Setup
1. Configure an Nginx server as a file server

### Deployment
Run the following commands to build and start the containers:
```bash
docker-compose build
docker-compose up -d
```

## Development

Run the following scripts to start development servers:
```bash
./start_client_dev.sh
./start_server_dev.sh
```
