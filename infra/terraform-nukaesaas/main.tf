terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }

  # State separado del de "recordshop" (que no vive en este bucket — ver
  # infra/README o la memoria del proyecto). Key propia, sin riesgo de
  # colisión con terraform/state/k3s_ec2 ni terraform/state/network, que sí
  # viven aquí.
  backend "s3" {
    bucket = "nukae-terraform-state-d21rip1v"
    key    = "terraform/state/nukaesaas/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# Dades de la VPC per defecte (ja existeix al compte, compartida amb recordshop)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Ubuntu 24.04 LTS arm64 (Graviton) — última AMI oficial a eu-west-1
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
