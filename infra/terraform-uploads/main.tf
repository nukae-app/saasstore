# Almacenamiento de las subidas del admin (imágenes, vídeos, tipografías, facturas)
# para nukaesaas. Stack propio y pequeño, con su state en el bucket común (key
# distinta): no depende del stack principal ni de db_password.
#
#   public/...   lo sirve CloudFront (OAC) a través de Caddy en /uploads/*
#   private/...  facturas de gastos: SIN acceso público; la API genera URLs firmadas
#
# Ver api/app/services/storage.py y docs/PLAN_UPLOADS_S3.md.
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
    key    = "terraform/state/uploads/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "ec2_role_name" {
  description = "Rol IAM de la EC2 de nukaesaas (lo crea terraform-nukaesaas/iam.tf)"
  type        = string
  default     = "nukaesaas-ec2-role"
}

data "aws_caller_identity" "me" {}

locals {
  bucket_name = "nukaesaas-uploads-${data.aws_caller_identity.me.account_id}"
}

# ---------------------------------------------------------------- bucket (privado)
resource "aws_s3_bucket" "uploads" {
  bucket = local.bucket_name

  lifecycle {
    prevent_destroy = true # contiene datos de la tienda: no se borra con un `terraform destroy`
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Versionado: sustituye a la copia de seguridad (se recupera lo borrado o sobrescrito).
resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  depends_on = [aws_s3_bucket_versioning.uploads]

  rule {
    id     = "versiones-antiguas"
    status = "Enabled"
    filter {}

    # Las versiones sustituidas/borradas se conservan 90 días y luego desaparecen
    # (también limita el tiempo que se guardan datos de facturas ya eliminadas).
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ---------------------------------------------------------------- CloudFront (solo public/)
resource "aws_cloudfront_origin_access_control" "uploads" {
  name                              = "${local.bucket_name}-oac"
  description                       = "Acceso de CloudFront al bucket de subidas (solo prefijo public/)"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "security" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_distribution" "uploads" {
  enabled         = true
  comment         = "nukaesaas - subidas publicas (/uploads)"
  is_ipv6_enabled = true
  http_version    = "http2and3"
  price_class     = "PriceClass_100" # Europa y Norteamérica: la más barata

  origin {
    domain_name              = aws_s3_bucket.uploads.bucket_regional_domain_name
    origin_id                = "uploads-public"
    origin_path              = "/public" # private/ queda fuera del alcance de CloudFront
    origin_access_control_id = aws_cloudfront_origin_access_control.uploads.id
  }

  default_cache_behavior {
    target_origin_id           = "uploads-public"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "CloudFrontLeePublic"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/public/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.uploads.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [aws_s3_bucket_public_access_block.uploads]
}

# ---------------------------------------------------------------- permiso de la EC2
data "aws_iam_policy_document" "ec2" {
  statement {
    sid       = "ObjetosDeSubidas"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
  statement {
    sid       = "ListarSubidas"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.uploads.arn]
  }
}

resource "aws_iam_role_policy" "ec2_uploads" {
  name   = "${var.ec2_role_name}-uploads-s3"
  role   = var.ec2_role_name
  policy = data.aws_iam_policy_document.ec2.json
}

output "bucket" {
  value = aws_s3_bucket.uploads.bucket
}

output "cdn_domain" {
  value = aws_cloudfront_distribution.uploads.domain_name
}

output "distribution_id" {
  value = aws_cloudfront_distribution.uploads.id
}
