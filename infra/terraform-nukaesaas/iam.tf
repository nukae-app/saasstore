# Permet a l'EC2 fer `docker pull` d'ECR sense guardar credencials AWS a la
# maquina: l'autenticacio es fa via el rol assignat a la instancia.
resource "aws_iam_role" "ec2" {
  name = "${var.project}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = { Name = "${var.project}-ec2-role" }
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy" "secrets_read" {
  name = "${var.project}-secrets-read"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PlatformAndSuperadminSecrets"
        Effect = "Allow"
        Action = "secretsmanager:GetSecretValue"
        Resource = [
          aws_secretsmanager_secret.app.arn,
          aws_secretsmanager_secret.superadmin.arn,
        ]
      },
      {
        # Secrets per tenant (api/app/tenant_secrets.py::SECRET_PREFIX =
        # "saaswebstore/tenants"), creats/actualitzats en calent per l'app
        # quan es dona d'alta o s'edita un tenant des del superadmin — a
        # diferencia dels dos secrets de dalt, aquests no existeixen com a
        # recurs Terraform (es creen dinàmicament, un per tenant).
        Sid    = "TenantSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:CreateSecret",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:saaswebstore/tenants/*"
      },
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project}-ec2-profile"
  role = aws_iam_role.ec2.name
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
