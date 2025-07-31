## EyeNED platform setup

Production Docker configuration for the EyeNED platform with multi-stage builds and containerized services.

### Quick Start
```bash
# Run the automated setup script
./setup.sh
```

### Services Overview

**api-server:** FastAPI-based backend server with health checks, database connectivity, and image processing capabilities. Built from Python 3.11-slim with Node.js for client building.

**worker:** Background task processor using Redis for job queuing. Handles image processing, segmentation storage, and thumbnail generation.

**database:** MySQL 8.0.27 database with persistent storage and health monitoring for data integrity.

**redis:** Redis 7-alpine for caching and job queue management with health checks.

**fileserver:** Nginx-based file server for static content delivery and image serving with optimized configuration.

**nginx:** Reverse proxy with SSL termination, load balancing, and static file serving for the web application.

### Configuration

The setup script (`setup.sh`) automatically configures:
- Environment variables in `.env` file
- Directory structure for images, storage, and thumbnails
- Database credentials and admin accounts
- Port mappings and volume mounts
- User permissions and security settings

### Deployment

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Volumes and Storage

- **Images:** DICOM and PNG images
- **Segmentations:** Zarr-based annotation storage
- **Thumbnails:** Generated image previews
- **Database:** Persistent MySQL data storage
