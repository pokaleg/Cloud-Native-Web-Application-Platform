#!/bin/bash
set -euo pipefail

echo "=== Starting application setup ==="

# -------------------------------------------------------
# 1. Update system packages
# -------------------------------------------------------
echo ">>> Updating system packages..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# -------------------------------------------------------
# 2. Install system dependencies
#    - python3.12 + venv  : run the app
#    - netcat-openbsd     : cloud-init RDS TCP check
#    - curl + unzip       : install AWS CLI v2
#    - postgresql-client  : psql for debugging RDS
# -------------------------------------------------------
echo ">>> Installing system dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    netcat-openbsd \
    curl \
    unzip \
    postgresql-client

# -------------------------------------------------------
# 3. Install AWS CLI v2
# -------------------------------------------------------
echo ">>> Installing AWS CLI v2..."
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws
aws --version

# -------------------------------------------------------
# 4. Install CloudWatch Unified Agent
#    - Reads logs from /var/log/csye6225/webapp.log
#    - Receives StatsD metrics on UDP port 8125
#    - Forwards both to CloudWatch
# -------------------------------------------------------
echo ">>> Installing CloudWatch Unified Agent..."
curl -fsSL "https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb" \
    -o /tmp/amazon-cloudwatch-agent.deb
sudo dpkg -i /tmp/amazon-cloudwatch-agent.deb
rm -f /tmp/amazon-cloudwatch-agent.deb

# Copy CloudWatch config into AMI (placed by Packer file provisioner)
sudo mkdir -p /opt/aws/amazon-cloudwatch-agent/etc
sudo cp /tmp/cloudwatch-config.json \
    /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
echo ">>> CloudWatch agent installed"

# -------------------------------------------------------
# 5. Create application group and user (non-login)
#    Home directory required — psycopg2 looks for SSL certs
#    in ~/.postgresql/ and fails without a home dir.
# -------------------------------------------------------
echo ">>> Creating csye6225 group and user..."
if ! getent group csye6225 > /dev/null 2>&1; then
    sudo groupadd csye6225
fi
if ! id csye6225 > /dev/null 2>&1; then
    sudo useradd -r -g csye6225 -s /usr/sbin/nologin -m -d /home/csye6225 csye6225
fi
sudo mkdir -p /home/csye6225
sudo chown csye6225:csye6225 /home/csye6225
sudo chmod 700 /home/csye6225

# -------------------------------------------------------
# 6. Create log directory for the application
#    CloudWatch agent reads from /var/log/csye6225/webapp.log
# -------------------------------------------------------
echo ">>> Creating log directory..."
sudo mkdir -p /var/log/csye6225
sudo chown csye6225:csye6225 /var/log/csye6225
sudo chmod 755 /var/log/csye6225

# -------------------------------------------------------
# 7. Deploy application files
# -------------------------------------------------------
echo ">>> Deploying application..."
sudo mkdir -p /opt/csye6225
sudo cp -r /tmp/webapp/* /opt/csye6225/

# -------------------------------------------------------
# 8. Set up Python virtual environment and install deps
# -------------------------------------------------------
echo ">>> Setting up Python virtual environment..."
sudo python3.12 -m venv /opt/csye6225/venv
sudo /opt/csye6225/venv/bin/pip install --upgrade pip
sudo /opt/csye6225/venv/bin/pip install -r /opt/csye6225/requirements.txt

# -------------------------------------------------------
# 9. Create placeholder .env file
#    Real values injected by Terraform cloud-init at launch
# -------------------------------------------------------
echo ">>> Creating placeholder .env file..."
sudo tee /opt/csye6225/.env > /dev/null <<EOF
DB_HOST=
DB_PORT=5432
DB_USER=
DB_PASSWORD=
DB_NAME=
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
S3_BUCKET_NAME=
AWS_REGION=us-east-1
EOF

# -------------------------------------------------------
# 10. Set ownership and permissions
# -------------------------------------------------------
echo ">>> Setting file permissions..."
sudo chown -R csye6225:csye6225 /opt/csye6225
sudo chmod -R 750 /opt/csye6225
sudo chmod 600 /opt/csye6225/.env

# -------------------------------------------------------
# 11. Install and enable systemd service
# -------------------------------------------------------
echo ">>> Configuring systemd service..."
sudo cp /tmp/webapp.service /etc/systemd/system/webapp.service
sudo chmod 644 /etc/systemd/system/webapp.service
sudo systemctl daemon-reload
sudo systemctl enable webapp

echo "=== Application setup complete ==="
