#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Start the server
uvicorn server.main:app --reload --host 0.0.0.0 --port $SERVER_PORT --log-level debug
