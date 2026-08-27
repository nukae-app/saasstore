# Contenidors dels secrets a AWS Secrets Manager. El VALOR no es gestiona amb
# Terraform (per no deixar les credencials en pla al tfstate); es puja a
# banda amb `aws secretsmanager put-secret-value`.
resource "aws_secretsmanager_secret" "app" {
  name        = "${var.project}/prod"
  description = "Credencials de plataforma (DB, JWT, APIs externes) per a l'EC2 de ${var.project}"

  tags = { Name = "${var.project}-secrets" }
}

# Secret separat del de plataforma a propòsit (AWS_SUPERADMIN_SECRETS_NAME,
# ver api/app/config.py::SuperAdminSettings) — la clau de firma JWT del
# panell de superadmin no ha de viure al mateix secret que les credencials
# de cada tenant.
resource "aws_secretsmanager_secret" "superadmin" {
  name        = "${var.project}/superadmin"
  description = "Credencials del realm de superadmin (SUPERADMIN_SECRET_KEY) per a ${var.project}"

  tags = { Name = "${var.project}-superadmin-secrets" }
}
