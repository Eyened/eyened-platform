#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# change to the parent directory
cd ..

# activate virtual environment 
source ${PYTHON_VENV_PATH}/bin/activate

# Start the server
python -m uvicorn server.main:app --host 0.0.0.0 --port $DEV_SERVER_PORT --log-level debug
