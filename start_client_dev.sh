#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Start the client
cd client

# Create .env file for Vite
cat > .env << EOL
VITE_PORT=$PORT
VITE_HOSTNAME=$HOSTNAME
EOL

npm run dev
