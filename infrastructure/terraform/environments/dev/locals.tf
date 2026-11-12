locals {
  tags = merge(
    {
      Project     = "CDM"
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = "terraform"
    },
    var.common_tags,
  )
}
