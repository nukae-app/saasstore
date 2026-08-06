variable "aws_region" {
  description = "Regió AWS"
  type        = string
  default     = "eu-west-1"
}

variable "project" {
  description = "Nom del projecte (prefix de tots els recursos)"
  type        = string
  default     = "recordshop"
}

variable "ec2_instance_type" {
  description = "Tipus d'instància EC2"
  type        = string
  default     = "t2.medium" # 2 vCPU / 4GB, instància real en marxa
}

variable "db_instance_class" {
  description = "Classe de la instància RDS"
  type        = string
  default     = "db.t4g.micro" # free tier, Graviton (ARM) — més barat i millor rendiment que t3
}

variable "db_name" {
  description = "Nom de la base de dades PostgreSQL"
  type        = string
  default     = "ultralocal"
}

variable "db_username" {
  description = "Usuari administrador de PostgreSQL"
  type        = string
  default     = "ultralocal"
}

variable "db_password" {
  description = "Contrasenya de PostgreSQL (defineix-la via TF_VAR_db_password)"
  type        = string
  sensitive   = true
}

variable "rds_encrypted_snapshot_id" {
  description = "Identificador del snapshot xifrat des del qual restaurar la instància RDS (migració a storage_encrypted, veure infra/README o memòria del projecte)"
  type        = string
  default     = null
}
