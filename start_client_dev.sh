#!/bin/bash

# Load environment variables
set -a
source dev.env
set +a

# Start the client
cd client
npm exec vite -- --port $DEV_FRONTEND_SERVER_PORT --host 0.0.0.0 dev

