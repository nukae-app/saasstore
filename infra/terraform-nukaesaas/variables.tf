variable "aws_region" {
  description = "Regió AWS"
  type        = string
  default     = "eu-west-1"
}

variable "project" {
  description = "Nom del projecte (prefix de tots els recursos) — diferent de \"recordshop\" a propòsit"
  type        = string
  default     = "nukaesaas"
}

variable "ec2_instance_type" {
  description = "Tipus d'instància EC2 (Graviton/arm64)"
  type        = string
  default     = "t4g.medium" # 2 vCPU / 4GB, mateixa mida que el t2.medium actual de recordshop
}

variable "db_instance_class" {
  description = "Classe de la instància RDS (Graviton/arm64, igual que la de recordshop avui)"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Nom de la base de dades PostgreSQL"
  type        = string
  default     = "nukaesaas"
}

variable "db_username" {
  description = "Usuari administrador de PostgreSQL"
  type        = string
  default     = "nukaesaas"
}

variable "db_password" {
  description = "Contrasenya de PostgreSQL (defineix-la via TF_VAR_db_password)"
  type        = string
  sensitive   = true
}
