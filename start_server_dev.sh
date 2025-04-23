#!/bin/bash

# Load environment variables
set -a
source dev.env
set +a

# Start the server
python -m uvicorn server.main:app --host 0.0.0.0 --port $DEV_SERVER_PORT --log-level debug
