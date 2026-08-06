# Registres d'imatges Docker: es construeixen en local i es despleguen a EC2
# fent només `docker pull` (sense build a la màquina de producció).
resource "aws_ecr_repository" "api" {
  name                 = "${var.project}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${var.project}-api" }
}

resource "aws_ecr_repository" "web" {
  name                 = "${var.project}-web"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${var.project}-web" }
}

# Mateixa política per als dos repos: conserva només les últimes 10 imatges
# etiquetades i esborra les "untagged" (les que queden orfes en re-pujar `latest`)
# al cap de 3 dies, perquè l'emmagatzematge no creixi sense control.
locals {
  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Esborra imatges sense tag amb mes de 3 dies"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 3
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Conserva nomes les ultimes 10 imatges etiquetades"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["v", "latest"]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_lifecycle_policy" "web" {
  repository = aws_ecr_repository.web.name
  policy     = local.ecr_lifecycle_policy
}
