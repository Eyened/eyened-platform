Follow these steps to set up a development environment:
 
```
cp sample.env .env
```
Set the correct envirionment variables. Choose ports for server and client


Start nginx routing:
```
docker-compose up -d
```

Start client (via vite)
```
start_client_dev.sh
```

Start server (python fastapi via uvicorn)  
```
start_server_dev.sh
```

Now your application should be accessible on the port `DEV_NGINX_PORT`
