# Contenidor del secret a AWS Secrets Manager. El VALOR no es gestiona amb
# Terraform (per no deixar les credencials en pla al tfstate); es puja a
# banda amb `aws secretsmanager put-secret-value`.
#
# El camp DISCOGS_TOKEN_SCRIPT (dins d'aquest mateix secret) és el token de
# producció de Discogs, però NOMÉS el llegeix scripts/run_discogs_sync.sh a
# l'host via `aws secretsmanager get-secret-value` — mai arriba a
# api/worker/beat com a DISCOGS_TOKEN perquè _load_secrets_from_aws()
# (app/config.py) el carrega amb el mateix nom de clau, i com que Settings
# no té cap camp `discogs_token_script`, queda inert per a l'app. Quan es
# vulgui activar Discogs de veritat a producció, cal afegir/canviar la clau
# DISCOGS_TOKEN (sense _SCRIPT) aquí.
resource "aws_secretsmanager_secret" "app" {
  name        = "${var.project}/prod"
  description = "Credencials de l'app (DB, JWT, APIs externes) per a l'EC2 de producció"

  tags = { Name = "${var.project}-secrets" }
}
