#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script configuration
readonly SCRIPT_NAME=$(basename "$0")
readonly DEFAULT_PORT=80
readonly DEFAULT_BASE_DIR="$HOME/eyened-platform"
readonly ENV_FILE=".env"

# Function to read value from .env file
read_env_value() {
    local key=$1
    if [ -f "$ENV_FILE" ]; then
        local value=$(grep "^${key}=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
        echo "$value"
    fi
}

# Function to print status messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to validate port number
validate_port() {
    local port=$1
    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        print_error "Invalid port number. Must be between 1 and 65535"
        return 1
    fi
    return 0
}

# Function to validate path
validate_path() {
    local path=$1
    if [[ "$path" =~ ^[[:space:]]*$ ]]; then
        print_error "Path cannot be empty"
        return 1
    fi
    return 0
}

# Function to get user input with a default value and validation
get_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local validate_func="$4"
    
    # Check if the variable exists in .env file
    local env_file_value=$(read_env_value "$var_name")
    if [ -n "$env_file_value" ]; then
        print_status "Found existing $var_name in .env: $env_file_value"
        eval "$var_name='$env_file_value'"
        return 0
    fi
    
    # Only prompt if not found in .env file
    while true; do
        if [ -n "$default" ]; then
            read -p "$prompt [$default]: " input
            input=${input:-$default}
        else
            read -p "$prompt: " input
        fi
        
        if [ -n "$validate_func" ]; then
            if $validate_func "$input"; then
                break
            fi
        else
            break
        fi
    done
    
    # Store in the specified variable
    eval "$var_name='$input'"
}

# Function to create directory if it doesn't exist
create_directory() {
    local dir_path="$1"
    local description="$2"
    
    if [ ! -d "$dir_path" ]; then
        print_status "Creating $description directory: $dir_path"
        if mkdir -p "$dir_path"; then
            print_status "Successfully created directory: $dir_path"
        else
            print_error "Failed to create directory: $dir_path"
            return 1
        fi
    else
        print_status "$description directory already exists: $dir_path"
    fi
}

# Function to determine docker compose command
get_docker_compose_cmd() {
    # Test if 'docker compose' works by trying to run it
    if docker compose version &> /dev/null; then
        echo "docker compose"
    elif command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        print_error "Neither 'docker compose' nor 'docker-compose' is available. Please install Docker Compose first."
        exit 1
    fi
}


DOCKER_COMPOSE_CMD=$(get_docker_compose_cmd)

print_status "Welcome to the Eyened Platform setup!"
echo "This script will help you configure your environment variables."
echo "Press Enter to accept the default values shown in brackets."
echo

# Get port with validation
echo "Setting up port. This is where you will access the platform from your browser (or omit the port if you are using the default port 80)"
EXISTING_PORT=$(read_env_value "PORT")
get_input "Enter the port number for the platform" "${EXISTING_PORT:-$DEFAULT_PORT}" PORT validate_port

# Get paths with validation
echo "Setting up paths. These are the directories on your host system that will store the images, segmentations, thumbnails and the database."
EXISTING_IMAGES_PATH=$(read_env_value "IMAGES_BASEPATH")
EXISTING_SEGMENTATIONS_PATH=$(read_env_value "SEGMENTATIONS_ZARR_STORE")
EXISTING_THUMBNAILS_PATH=$(read_env_value "THUMBNAILS_PATH")
EXISTING_DB_PATH=$(read_env_value "DATABASE_PATH")

get_input "Enter the path to your images directory" "${EXISTING_IMAGES_PATH:-$DEFAULT_BASE_DIR/images}" IMAGES_BASEPATH validate_path
get_input "Enter the path to store segmentations" "${EXISTING_SEGMENTATIONS_PATH:-$DEFAULT_BASE_DIR/storage/segmentations.zarr}" SEGMENTATIONS_ZARR_STORE validate_path
get_input "Enter the path to store thumbnails" "${EXISTING_THUMBNAILS_PATH:-$DEFAULT_BASE_DIR/storage/thumbnails}" THUMBNAILS_PATH validate_path
get_input "Enter the path to store the database" "${EXISTING_DB_PATH:-$DEFAULT_BASE_DIR/database}" DATABASE_PATH validate_path

# Get database configuration
echo 
echo "Setting up database configuration. This is used to connect to the database outside of the platform."
EXISTING_DB_PORT=$(read_env_value "DATABASE_PORT")
get_input "Enter the database port" "${EXISTING_DB_PORT:-3306}" DATABASE_PORT validate_port

# Always prompt for database root password
DEFAULT_ROOT_PASSWORD=$(openssl rand -base64 16)
EXISTING_ROOT_PASSWORD=$(read_env_value "DATABASE_ROOT_PASSWORD")
get_input "Enter the database root password (or press Enter for a random one)" "${EXISTING_ROOT_PASSWORD:-$DEFAULT_ROOT_PASSWORD}" DATABASE_ROOT_PASSWORD validate_path

EXISTING_DB_USER=$(read_env_value "DATABASE_USER")
get_input "Enter the database username" "${EXISTING_DB_USER:-eyened}" DATABASE_USER validate_path

EXISTING_DB_PASSWORD=$(read_env_value "DATABASE_PASSWORD")
DEFAULT_DB_PASSWORD=$(openssl rand -base64 16)
get_input "Enter the password for user $DATABASE_USER (or press Enter for a random one)" "${EXISTING_DB_PASSWORD:-$DEFAULT_DB_PASSWORD}" DATABASE_PASSWORD validate_path

EXISTING_ADMIN_USERNAME=$(read_env_value "ADMIN_USERNAME")
EXISTING_ADMIN_PASSWORD=$(read_env_value "ADMIN_PASSWORD")
DEFAULT_ADMIN_PASSWORD=$(openssl rand -base64 16)
echo 
echo "Setting up admin credentials. You will use these to login to the platform for the first time."
get_input "Enter the admin username (or press Enter for 'admin')" "${EXISTING_ADMIN_USERNAME:-admin}" ADMIN_USERNAME validate_path
get_input "Enter the admin password (or press Enter for a random one)" "${EXISTING_ADMIN_PASSWORD:-$DEFAULT_ADMIN_PASSWORD}" ADMIN_PASSWORD validate_path

# Generate SECRET_KEY
EXISTING_SECRET_KEY=$(read_env_value "SECRET_KEY")
if [ -z "$EXISTING_SECRET_KEY" ]; then
    SECRET_KEY=$(openssl rand -base64 32)
    print_status "Generated random SECRET_KEY"
else
    SECRET_KEY="$EXISTING_SECRET_KEY"
    print_status "Using existing SECRET_KEY from .env"
fi

# Create .env file
print_status "Creating .env file..."
if ! cat > "$ENV_FILE" << EOF
# Port on host system to connect to the platform
PORT=${PORT}

# credentials of the default user (for first-time login)
ADMIN_USERNAME="${ADMIN_USERNAME}"
ADMIN_PASSWORD="${ADMIN_PASSWORD}"

# secret key for the application
SECRET_KEY="${SECRET_KEY}"

# local folder to serve images from (possibly read-only)
IMAGES_BASEPATH="${IMAGES_BASEPATH}"

# local path to store segmentations
SEGMENTATIONS_ZARR_STORE="${SEGMENTATIONS_ZARR_STORE}"

# local path to store thumbnails
THUMBNAILS_PATH="${THUMBNAILS_PATH}"

# path to the database files
DATABASE_PATH="${DATABASE_PATH}"

# port on host system to connect to the database
DATABASE_PORT=${DATABASE_PORT}

# database credentials
DATABASE_USER="${DATABASE_USER}"
DATABASE_PASSWORD="${DATABASE_PASSWORD}"
EOF
then
    print_error "Failed to create .env file"
    exit 1
fi

# Always add root password
if ! echo "DATABASE_ROOT_PASSWORD=\"${DATABASE_ROOT_PASSWORD}\"" >> "$ENV_FILE"; then
    print_error "Failed to append root password to .env file"
    exit 1
fi

print_status ".env file created successfully!"

# Create required directories
print_status "Creating required directories..."
if ! create_directory "$IMAGES_BASEPATH" "Images"; then
    print_error "Failed to create images directory"
    exit 1
fi

if ! create_directory "$SEGMENTATIONS_ZARR_STORE" "Segmentations"; then
    print_error "Failed to create segmentations directory"
    exit 1
fi

if ! create_directory "$THUMBNAILS_PATH" "Thumbnails"; then
    print_error "Failed to create thumbnails directory"
    exit 1
fi

if ! create_directory "$DATABASE_PATH" "Database"; then
    print_error "Failed to create database directory"
    exit 1
fi

# Build and start containers
print_status "Building containers..."
if ! $DOCKER_COMPOSE_CMD build; then
    print_error "Failed to build containers"
    exit 1
fi

print_status "Starting containers..."
if ! USERID=$(id -u) GROUPID=$(id -g) $DOCKER_COMPOSE_CMD up -d; then
    print_error "Failed to start containers"
    exit 1
fi

HOSTNAME=$(hostname)
print_status "Setup completed successfully!"
echo -e "\nYour Eyened platform should now be available at:"
echo -e "  Viewer: ${GREEN}http://${HOSTNAME}:${PORT}${NC}"
echo -e "  Adminer: ${GREEN}http://${HOSTNAME}:8080${NC}"
echo -e "\nTo check container status, run:"
echo -e "  ${YELLOW}$DOCKER_COMPOSE_CMD ps${NC}"
echo -e "\nTo view logs, run:"
echo -e "  ${YELLOW}$DOCKER_COMPOSE_CMD logs -f${NC}"
echo -e "\nTo stop the platform, run:"
echo -e "  ${YELLOW}$DOCKER_COMPOSE_CMD down${NC}"
echo -e "\nNext time you want to start the platform, run:"
echo -e "  ${YELLOW}USERID=$(id -u) GROUPID=$(id -g) $DOCKER_COMPOSE_CMD up -d${NC}"

unset ADMIN_PASSWORD DATABASE_ROOT_PASSWORD DATABASE_PASSWORD DEFAULT_DB_PASSWORD DEFAULT_ADMIN_PASSWORD 