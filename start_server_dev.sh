#!/bin/bash

# Load environment variables
set -a
source ./server/.env
set +a

# Start the server
cd server
uvicorn main:app --reload --host 0.0.0.0 --port $SERVER_PORT --log-level debug
