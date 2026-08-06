# Subnet group per a RDS (usa les 3 AZ de la VPC per defecte)
resource "aws_db_subnet_group" "recordshop" {
  name        = "${var.project}-subnet-group"
  description = "Subnets per a RDS RecordShop"
  subnet_ids  = data.aws_subnets.default.ids

  tags = { Name = "${var.project}-subnet-group" }
}

resource "aws_db_instance" "postgres" {
  identifier        = "${var.project}-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.db_instance_class
  allocated_storage = 20
  storage_type      = "gp2"

  # Restaurada des d'un snapshot xifrat (RDS no permet activar l'encriptació
  # in-place; cal snapshot -> còpia xifrada -> restore). Un cop restaurada,
  # engine/username/password venen del snapshot i Terraform no els torna a aplicar.
  storage_encrypted   = true
  snapshot_identifier = var.rds_encrypted_snapshot_id

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.recordshop.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible     = false # només accessible des de l'EC2
  deletion_protection     = false
  skip_final_snapshot     = true
  backup_retention_period = 7 # 7 dies de backups automàtics
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  tags = { Name = "${var.project}-db" }

  lifecycle {
    # snapshot_identifier només s'usa per crear la instància; ignorem canvis
    # perquè futurs `apply` (amb la var buida) no intentin recrear-la de nou.
    ignore_changes = [snapshot_identifier]
  }
}
