# Snapshots diarios del volumen EBS de nukaesaas-server (Data Lifecycle Manager),
# retención 30 días. Stack propio con su state en el mismo bucket (key distinta).
# El volumen se identifica por una etiqueta (aws_ec2_tag), sin tocar el stack principal.
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "nukae-terraform-state-d21rip1v"
    key    = "terraform/state/snapshots/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = "eu-west-1"
}

variable "volume_id" {
  type    = string
  default = "vol-07c15fb40d39686cd"
}

variable "retain_days" {
  type    = number
  default = 30
}

resource "aws_ec2_tag" "backup" {
  resource_id = var.volume_id
  key         = "Backup"
  value       = "diario-30d"
}

data "aws_iam_policy_document" "dlm_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dlm" {
  name               = "nukaesaas-dlm-snapshots"
  assume_role_policy = data.aws_iam_policy_document.dlm_assume.json
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "diaria" {
  description        = "Snapshot diario nukaesaas server retencion ${var.retain_days} dias"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { Backup = aws_ec2_tag.backup.value }

    schedule {
      name = "diario"
      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:00"]
      }
      retain_rule {
        count = var.retain_days
      }
      copy_tags = true
      tags_to_add = {
        SnapshotCreator = "dlm"
      }
    }
  }
}
