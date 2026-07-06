#!/bin/sh
cd /app/client
[ ! -f "node_modules/.package-lock.json" ] && npm install
exec npm exec vite -- --host 0.0.0.0 --port 5173 dev
