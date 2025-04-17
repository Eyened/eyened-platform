FROM python:3.11-slim

SHELL ["/bin/bash", "-c"]

# Install dependencies
# nodejs, mssql-tools18, msodbcsql18
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        nodejs \
    && npm install -g npm@10.8.3 \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 \
        mssql-tools18 \
    && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc \
    && source ~/.bashrc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the ORM
COPY orm /libraries/eyened_orm/
WORKDIR /libraries/eyened_orm
RUN pip install --no-cache-dir -e .

# Build the client
COPY client /client
COPY .env /client/.env
WORKDIR /client
RUN npm install
RUN npm run build   

# Setup the application
COPY server /app/server
WORKDIR /app/server

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug