# Subnet group per a RDS (usa les 3 AZ de la VPC per defecte)
resource "aws_db_subnet_group" "nukaesaas" {
  name        = "${var.project}-subnet-group"
  description = "Subnets per a RDS ${var.project}"
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

  # BD nova, sense dades reals: es xifra directament a la creació, sense
  # necessitat del pas snapshot -> còpia xifrada -> restore que va fer falta
  # per a la RDS de recordshop (ja tenia dades quan es va activar xifrat).
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.nukaesaas.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible     = false # només accessible des de l'EC2
  deletion_protection     = false
  skip_final_snapshot     = true
  backup_retention_period = 7 # 7 dies de backups automàtics
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  tags = { Name = "${var.project}-db" }
}
