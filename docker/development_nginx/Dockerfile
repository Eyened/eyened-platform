FROM nginx:latest

# Copy custom nginx.conf
COPY nginx.conf /etc/nginx/templates/nginx.conf.template
# COPY nginx.dev.conf /etc/nginx/nginx.conf.tmp

# Replace environment variables at build time!
# RUN envsubst < /etc/nginx/nginx.conf.tmp > /etc/nginx/nginx.conf

# Expose port 80
EXPOSE ${DEV_NGINX_PORT}

# Start NGINX

CMD ["nginx", "-g", "daemon off;"]
