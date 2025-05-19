FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-mysql-client \
    curl \
    git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the entire orm directory
COPY . /app/orm/

# Move environment files to their correct locations
RUN mv /app/orm/migrations/test.env /app/orm/eyened_orm/environments/test.env && \
    mv /app/orm/migrations/source.env /app/orm/eyened_orm/environments/source.env

# installs eyened_orm
WORKDIR /app/orm
RUN pip install .

# Set working directory for running the script
WORKDIR /app/orm/migrations
RUN mv alembic_docker.ini alembic.ini
RUN chmod +x run_alembic.sh

ENTRYPOINT ["./run_alembic.sh"]