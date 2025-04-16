#!/bin/bash

# Load environment variables
set -a
source ./server/.env
set +a

# Start the client
cd client
npm run dev
