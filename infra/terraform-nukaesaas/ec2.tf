resource "aws_instance" "nukaesaas" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.ec2_instance_type
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  # Instal·la Docker, Docker Compose i AWS CLI (per fer `docker pull` d'ECR
  # amb el rol IAM de la instància, sense credencials guardades) en el primer
  # arrencada. aarch64, no x86_64: aquesta instància és Graviton — el binari
  # x86 del CLI no arrenca aquí.
  user_data = <<-EOF
    #!/bin/bash
    set -e
    apt-get update -qq
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    apt-get install -y git unzip
    curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscliv2.zip
    unzip -q -o /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install
    rm -rf /tmp/awscliv2.zip /tmp/aws
    echo "Setup complet" >> /var/log/nukaesaas-init.log
  EOF

  tags = { Name = "${var.project}-server" }

  lifecycle {
    # data.aws_ami.ubuntu és most_recent = true, així que canvia cada cop que
    # Canonical publica una imatge nova. Sense això, qualsevol apply futur
    # (encara que sigui per un canvi no relacionat) recrearia l'EC2 sense
    # avisar. Per actualitzar l'AMI deliberadament: treure "ami" d'aquesta
    # llista, fer plan/apply, i tornar-lo a afegir.
    ignore_changes = [ami]
  }
}

# IP elàstica (IP pública fixa que no canvia en reinicis)
resource "aws_eip" "nukaesaas" {
  instance = aws_instance.nukaesaas.id
  domain   = "vpc"

  tags = { Name = "${var.project}-eip" }
}
