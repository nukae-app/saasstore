output "server_ip" {
  description = "IP pública del servidor (apunta el teu domini aquí)"
  value       = aws_eip.recordshop.public_ip
}

output "ssh_command" {
  description = "Comanda per connectar per SSH"
  value       = "ssh -i ${var.project}-key.pem ubuntu@${aws_eip.recordshop.public_ip}"
}

output "rds_endpoint" {
  description = "Endpoint RDS per al DATABASE_URL"
  value       = aws_db_instance.postgres.endpoint
}

output "database_url" {
  description = "DATABASE_URL per al .env de producció"
  value       = "postgresql+psycopg://${var.db_username}:PASSWORD@${aws_db_instance.postgres.endpoint}/${var.db_name}"
  sensitive   = false
}

output "ecr_api_repository_url" {
  description = "URL del repo ECR per a la imatge de l'api/worker/beat"
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_web_repository_url" {
  description = "URL del repo ECR per a la imatge del web"
  value       = aws_ecr_repository.web.repository_url
}
