#!/bin/bash

#############################################
# CSYE6225 Web Application Setup Script
# 
# This script automates the deployment of the
# cloud-native web application on Ubuntu 24.04 LTS
#
# Prerequisites: 
# - Ubuntu 24.04 LTS
# - Root/sudo access
# - Application zip file in current directory
#############################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables
APP_USER="csye6225"
APP_GROUP="csye6225"
APP_DIR="/opt/csye6225"
DB_NAME="csye6225_db"
DB_USER="csye6225_user"
DB_PASSWORD="csye6225_secure_pass"
APP_ZIP="webapp.zip"  # Name of your application zip file

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CSYE6225 Application Setup Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}" 
   echo "Please run: sudo bash setup.sh"
   exit 1
fi

echo -e "${YELLOW}[1/8] Updating package lists...${NC}"
apt update -y
echo -e "${GREEN}✓ Package lists updated${NC}"
echo ""

echo -e "${YELLOW}[2/8] Upgrading system packages...${NC}"
apt upgrade -y
echo -e "${GREEN}✓ System packages upgraded${NC}"
echo ""

echo -e "${YELLOW}[3/8] Installing PostgreSQL...${NC}"
apt install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql
echo -e "${GREEN}✓ PostgreSQL installed and started${NC}"
echo ""

echo -e "${YELLOW}[4/8] Creating application database and user...${NC}"
sudo -u postgres psql << EOF
-- Create database
CREATE DATABASE ${DB_NAME};

-- Create user with password
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};

-- Connect to database
\c ${DB_NAME}

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};

-- Make user the owner of the schema
ALTER SCHEMA public OWNER TO ${DB_USER};
EOF
echo -e "${GREEN}✓ Database and user created${NC}"
echo ""

echo -e "${YELLOW}[5/8] Creating application group...${NC}"
if getent group ${APP_GROUP} > /dev/null 2>&1; then
    echo "Group ${APP_GROUP} already exists"
else
    groupadd --system ${APP_GROUP}
    echo -e "${GREEN}✓ Group ${APP_GROUP} created${NC}"
fi
echo ""

echo -e "${YELLOW}[6/8] Creating application user...${NC}"
if id -u ${APP_USER} > /dev/null 2>&1; then
    echo "User ${APP_USER} already exists"
else
    useradd --system --gid ${APP_GROUP} --shell /bin/false --home ${APP_DIR} ${APP_USER}
    echo -e "${GREEN}✓ User ${APP_USER} created${NC}"
fi
echo ""

echo -e "${YELLOW}[7/8] Deploying application files...${NC}"
# Create application directory
mkdir -p ${APP_DIR}

# Check if zip file exists
if [ ! -f "${APP_ZIP}" ]; then
    echo -e "${RED}Error: ${APP_ZIP} not found in current directory${NC}"
    echo "Please place your application zip file here and run again"
    exit 1
fi

# Install unzip if not present
if ! command -v unzip &> /dev/null; then
    apt install -y unzip
fi

# Extract application files
unzip -o ${APP_ZIP} -d ${APP_DIR}

# Install Python and pip if not present
apt install -y python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv ${APP_DIR}/venv

# Activate venv and install dependencies
source ${APP_DIR}/venv/bin/activate
pip install --upgrade pip
pip install -r ${APP_DIR}/requirements.txt
deactivate

# Create .env file
cat > ${APP_DIR}/.env << EOF
DB_HOST=localhost
DB_PORT=5432
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=${DB_NAME}
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
EOF

echo -e "${GREEN}✓ Application files deployed${NC}"
echo ""

echo -e "${YELLOW}[8/8] Setting file permissions...${NC}"
# Set ownership
chown -R ${APP_USER}:${APP_GROUP} ${APP_DIR}

# Set directory permissions (755)
find ${APP_DIR} -type d -exec chmod 755 {} \;

# Set file permissions (644)
find ${APP_DIR} -type f -exec chmod 644 {} \;

# Make Python scripts executable
chmod 750 ${APP_DIR}/venv/bin/*

# Protect .env file (only user can read)
chmod 600 ${APP_DIR}/.env

echo -e "${GREEN}✓ File permissions set${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Application installed to: ${APP_DIR}"
echo "Database: ${DB_NAME}"
echo "Database user: ${DB_USER}"
echo "Application user: ${APP_USER}"
echo ""
echo "To start the application:"
echo "  cd ${APP_DIR}"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo -e "${YELLOW}Note: Update the database password in ${APP_DIR}/.env for production use${NC}"
