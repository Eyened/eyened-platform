#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# activate virtual environment 
source ${PYTHON_VENV_PATH}/bin/activate

# Check if WORKERS environment variable is set, otherwise default to 1 for development
WORKERS=${WORKERS:-1}

# Check if USE_GUNICORN is set to use gunicorn instead of uvicorn
if [ "${USE_GUNICORN:-0}" = "1" ]; then
    # Use gunicorn for production-like testing
    echo "Starting server with gunicorn (${WORKERS} workers)..."
    (cd .. && gunicorn server.main:app \
        --workers ${WORKERS} \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:$DEV_SERVER_PORT \
        --log-level debug \
        --reload)
else
    # Use uvicorn for development (simpler debugging)
    if [ "${WORKERS}" -gt 1 ]; then
        echo "Starting server with uvicorn (${WORKERS} workers)..."
        (cd .. && python -m uvicorn server.main:app --host 0.0.0.0 --port $DEV_SERVER_PORT --workers ${WORKERS} --log-level debug)
    else
        echo "Starting server with uvicorn (single worker)..."
        (cd .. && python -m uvicorn server.main:app --host 0.0.0.0 --port $DEV_SERVER_PORT --log-level debug)
    fi
fi