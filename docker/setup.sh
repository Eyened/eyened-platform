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
readonly CREDS_FILE=".platform_credentials"
readonly ENV_FILE=".env"

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

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_status "Welcome to the Eyened Platform setup!"
echo "This script will help you configure your environment variables."
echo "Press Enter to accept the default values shown in brackets."
echo

# Get port with validation
echo "Setting up port. This is where you will access the platform from your browser (or omit the port if you are using the default port 80)"
get_input "Enter the port number for the platform" "$DEFAULT_PORT" PORT validate_port

# Get paths with validation
echo "Setting up paths. These are the directories on your host system that will store the images, annotations, thumbnails and the database."
get_input "Enter the path to your images directory" "$DEFAULT_BASE_DIR/images" IMAGES_BASEPATH validate_path
get_input "Enter the path to store annotations and thumbnails" "$DEFAULT_BASE_DIR/storage" STORAGE_BASEPATH validate_path
get_input "Enter the path to store the database" "$DEFAULT_BASE_DIR/database" DATABASE_PATH validate_path

# Get database configuration
echo 
echo "Setting up database configuration. This is used to connect to the database outside of the platform."
get_input "Enter the database port" "3306" DATABASE_PORT validate_port

# Check if database exists and handle credentials accordingly
if [ -s "$DATABASE_PATH" ]; then
    echo "Database path exists and is not empty. Please enter the database credentials."
else
    echo "Database path does not exist or is empty. Creating new database."
    DEFAULT_ROOT_PASSWORD=$(openssl rand -base64 16)
    get_input "Enter the database root password (or press Enter for a random one)" "$DEFAULT_ROOT_PASSWORD" DATABASE_ROOT_PASSWORD validate_path    
fi
get_input "Enter the database username" "eyened" DATABASE_USER validate_path
DEFAULT_DB_PASSWORD=$(openssl rand -base64 16)
get_input "Enter the password for user $DATABASE_USER (or press Enter for a random one)" "$DEFAULT_DB_PASSWORD" DATABASE_PASSWORD validate_path
    

DEFAULT_ADMIN_PASSWORD=$(openssl rand -base64 16)
echo 
echo "Setting up admin credentials. You will use these to login to the platform for the first time."
get_input "Enter the admin username (or press Enter for 'admin')" "admin" ADMIN_USERNAME validate_path
get_input "Enter the admin password (or press Enter for a random one)" "$DEFAULT_ADMIN_PASSWORD" ADMIN_PASSWORD validate_path

# Create .env file
print_status "Creating .env file..."
if ! cat > "$ENV_FILE" << EOF
# Port on host system to connect to the platform
PORT=${PORT}

# credentials of the default user (for first-time login)
ADMIN_USERNAME="${ADMIN_USERNAME}"
ADMIN_PASSWORD="${ADMIN_PASSWORD}"

# local folder to serve images from (possibly read-only)
IMAGES_BASEPATH="${IMAGES_BASEPATH}"

# local path to store annotations, thumbnails and other files
STORAGE_BASEPATH="${STORAGE_BASEPATH}"

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

# Add root password only if it was supplied
if [ -n "$DATABASE_ROOT_PASSWORD" ]; then
    if ! echo "DATABASE_ROOT_PASSWORD=\"${DATABASE_ROOT_PASSWORD}\"" >> "$ENV_FILE"; then
        print_error "Failed to append root password to .env file"
        exit 1
    fi
fi

print_status ".env file created successfully!"

# Verify paths exist and create them if needed
print_status "Checking paths..."

# Define all required paths
REQUIRED_PATHS=(
    "$IMAGES_BASEPATH"
    "$STORAGE_BASEPATH"
    "$STORAGE_BASEPATH/thumbnails"
    "$STORAGE_BASEPATH/annotations"
    "$STORAGE_BASEPATH/trash"
    "$DATABASE_PATH"
)

for path in "${REQUIRED_PATHS[@]}"; do
    if [ ! -d "$path" ]; then
        print_warning "Directory $path does not exist. Creating it..."
        if ! mkdir -p "$path"; then
            print_error "Failed to create directory: $path"
            exit 1
        fi
    fi
done

# Build and start containers
print_status "Building containers..."
if ! docker-compose build; then
    print_error "Failed to build containers"
    exit 1
fi

print_status "Starting containers..."
if ! USERID=$(id -u) GROUPID=$(id -g) docker-compose up -d; then
    print_error "Failed to start containers"
    exit 1
fi

HOSTNAME=$(hostname)
print_status "Setup completed successfully!"
echo -e "\nYour Eyened platform should now be available at:"
echo -e "  Viewer: ${GREEN}http://${HOSTNAME}:${PORT}${NC}"
echo -e "  Adminer: ${GREEN}http://${HOSTNAME}:8080${NC}"
echo -e "\nTo check container status, run:"
echo -e "  ${YELLOW}docker-compose ps${NC}"
echo -e "\nTo view logs, run:"
echo -e "  ${YELLOW}docker-compose logs -f${NC}"
echo -e "\nTo stop the platform, run:"
echo -e "  ${YELLOW}docker-compose down${NC}"
echo -e "\nNext time you want to start the platform, run:"
echo -e "  ${YELLOW}USERID=$(id -u) GROUPID=$(id -g) docker-compose up -d${NC}"


# Save credentials to a secure file
print_status "Saving credentials to $CREDS_FILE..."
if ! cat > "$CREDS_FILE" << EOF
Platform URL: http://${HOSTNAME}:${PORT}
Adminer URL: http://${HOSTNAME}:8080
Admin Username: ${ADMIN_USERNAME}
Admin Password: ${ADMIN_PASSWORD}
Database Username: ${DATABASE_USER}
Database Password: ${DATABASE_PASSWORD}
Database Root Password: ${DATABASE_ROOT_PASSWORD}
EOF
then
    print_error "Failed to create credentials file"
    exit 1
fi

# Set secure permissions on credentials file
if ! chmod 600 "$CREDS_FILE"; then
    print_error "Failed to set secure permissions on credentials file"
    exit 1
fi

print_warning "Your credentials have been saved to $CREDS_FILE"
print_warning "Please keep this file secure and delete it after you've noted the credentials"

# Clear sensitive variables
unset ADMIN_PASSWORD DATABASE_ROOT_PASSWORD DATABASE_PASSWORD DEFAULT_DB_PASSWORD DEFAULT_ADMIN_PASSWORD 