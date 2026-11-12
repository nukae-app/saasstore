# Presupuesto general de la cuenta AWS (todos los servicios) con aviso por
# correo. Stack propio y mínimo, con su state en el mismo bucket que el resto
# (key distinta): no depende de ningún otro recurso ni de db_password.
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
    key    = "terraform/state/budget/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = "eu-west-1"
}

variable "monthly_limit_usd" {
  type    = string
  default = "40"
}

variable "alert_email" {
  type    = string
  default = "paumarroyo@gmail.com"
}

resource "aws_budgets_budget" "monthly" {
  name         = "nukae-mensual-${var.monthly_limit_usd}usd"
  budget_type  = "COST"
  limit_amount = var.monthly_limit_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Aviso cuando el gasto REAL del mes supera el 50 % del límite.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}
