packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

# -------------------------------------------------------
# Variables
# -------------------------------------------------------

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "ami_users" {
  description = "List of AWS account IDs to share the AMI with (demo account)"
  type        = list(string)
  default     = []
}

variable "source_ami_filter_name" {
  type    = string
  default = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
}

variable "instance_type" {
  type    = string
  default = "t2.micro"
}

variable "ssh_username" {
  type    = string
  default = "ubuntu"
}

# -------------------------------------------------------
# Timestamp for unique naming
# -------------------------------------------------------

locals {
  timestamp = formatdate("YYYYMMDDHHmmss", timestamp())
}

# -------------------------------------------------------
# AWS Source — Amazon EBS
# -------------------------------------------------------

source "amazon-ebs" "webapp" {
  region        = var.aws_region
  ami_name      = "csye6225-webapp-${local.timestamp}"
  instance_type = var.instance_type
  ssh_username  = var.ssh_username

  ami_users = var.ami_users

  source_ami_filter {
    filters = {
      name                = var.source_ami_filter_name
      root-device-type    = "ebs"
      virtualization-type = "hvm"
      architecture        = "x86_64"
    }
    owners      = ["099720109477"] # Canonical (Ubuntu)
    most_recent = true
  }

  launch_block_device_mappings {
    device_name           = "/dev/sda1"
    volume_size           = 25
    volume_type           = "gp2"
    delete_on_termination = true
  }

  tags = {
    Name        = "csye6225-webapp-${local.timestamp}"
    Environment = "dev"
    Builder     = "packer"
  }
}

# -------------------------------------------------------
# Build
# -------------------------------------------------------

build {
  sources = ["source.amazon-ebs.webapp"]

  # Create temp directory for app files
  provisioner "shell" {
    inline = ["mkdir -p /tmp/webapp"]
  }

  # Copy application artifact into the image
  provisioner "file" {
    source      = "webapp-artifact/"
    destination = "/tmp/webapp/"
  }

  # Copy systemd service file
  provisioner "file" {
    source      = "webapp.service"
    destination = "/tmp/webapp.service"
  }

  # Copy CloudWatch agent config
  provisioner "file" {
    source      = "packer/cloudwatch-config.json"
    destination = "/tmp/cloudwatch-config.json"
  }

  # Run setup script
  provisioner "shell" {
    script = "packer/setup.sh"
  }
}
