terraform {
  # Versión fijada a la instalada en el equipo del propietario (v1.17.1).
  required_version = ">= 1.17.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Estado local durante el MVP. Al crear el bucket de estado se añadirá
  # backend "s3" con locking (ver README); nunca commitear *.tfstate*.
}

provider "aws" {
  region = var.aws_region

  # Todos los recursos del stack quedan etiquetados automáticamente
  # (AGENTS.md §13 y criterio CDM-18).
  default_tags {
    tags = local.tags
  }
}
