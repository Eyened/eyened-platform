#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# activate virtual environment if PYTHON_VENV_PATH is set
if [ -n "$PYTHON_VENV_PATH" ]; then
    if [ ! -d "${PYTHON_VENV_PATH}" ]; then
        echo "PYTHON_VENV_PATH set but directory not found: ${PYTHON_VENV_PATH}"
        exit 1
    fi
    source "${PYTHON_VENV_PATH}/bin/activate"
fi


echo "Starting server with uvicorn (single worker)..."
(cd .. && python -m uvicorn server.main:app --host 0.0.0.0 --port "$DEV_SERVER_PORT" --log-level debug)