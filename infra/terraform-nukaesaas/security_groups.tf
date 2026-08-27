# Security Group per a l'EC2 (web + SSH via SSM)
resource "aws_security_group" "ec2" {
  name_prefix = "${var.project}-ec2-"
  description = "${var.project} EC2: HTTP, HTTPS and SSH"
  vpc_id      = data.aws_vpc.default.id

  # lifecycle evita el deadlock quan cal reemplazar el SG mentre esta en us
  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH no s'obre a internet: l'acces es fa via AWS SSM Session Manager
  # (aws ssm start-session / ProxyCommand a ~/.ssh/config), que no necessita
  # cap port entrant obert perque la instancia inicia la connexio cap a AWS.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-ec2" }
}

# Security Group per a RDS (only accessible from EC2)
resource "aws_security_group" "rds" {
  name_prefix = "${var.project}-rds-"
  description = "${var.project} RDS: PostgreSQL only from EC2"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL from EC2"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-rds" }
}
