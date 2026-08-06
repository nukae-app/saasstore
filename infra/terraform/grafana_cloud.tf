# Permet a Grafana Cloud llegir CloudWatch (mètriques d'EC2/RDS) via un rol
# de confiança creuada — NO és el rol de l'EC2 (iam.tf), és Grafana Cloud
# (compte extern) qui assumeix aquest rol per consultar mètriques.
# External ID i compte AWS de Grafana: donats per l'assistent "Add new
# connection > Amazon CloudWatch" del propi stack de Grafana Cloud.

variable "grafana_cloud_external_id" {
  description = "External ID que dona Grafana Cloud a l'assistent de connexió CloudWatch (específic d'aquest stack)"
  type        = string
  sensitive   = true
}

locals {
  grafana_cloud_account_id = "008923505280" # compte AWS de Grafana Labs
}

resource "aws_iam_role" "grafana_cloudwatch" {
  name = "${var.project}-grafana-cloudwatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${local.grafana_cloud_account_id}:root" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "sts:ExternalId" = var.grafana_cloud_external_id }
      }
    }]
  })

  tags = { Name = "${var.project}-grafana-cloudwatch" }
}

resource "aws_iam_role_policy" "grafana_cloudwatch_read" {
  name = "${var.project}-grafana-cloudwatch-read"
  role = aws_iam_role.grafana_cloudwatch.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "cloudwatch:GetMetricStatistics",
        "tag:GetResources",
        "ec2:DescribeTags",
        "rds:DescribeDBInstances",
        "rds:ListTagsForResource",
        # CloudWatch Logs (lectura): avui no hi ha cap log group real (els
        # logs van per Alloy -> Loki, no per CloudWatch), però la prova de
        # connexió de Grafana comprova totes dues capacitats — sense
        # aquests permisos surt un avís d'accés denegat, inofensiu però
        # sorollós. Només lectura, res que escrigui/esborri.
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogGroupFields",
        "logs:GetLogEvents",
        "logs:StartQuery",
        "logs:StopQuery",
        "logs:GetQueryResults",
        "logs:FilterLogEvents",
      ]
      Resource = "*"
    }]
  })
}

output "grafana_cloudwatch_role_arn" {
  value = aws_iam_role.grafana_cloudwatch.arn
}
