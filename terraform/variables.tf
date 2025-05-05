variable "prefix" {
  description = "Name prefix for every Azure resource"
  type        = string
  default     = "hydro"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "westeurope"
}

variable "kubernetes_version" {
  description = "AKS version"
  type        = string
  default     = "1.29"
}

variable "tags" {
  description = "Common tag map"
  type        = map(string)
  default     = {}
}

locals {
  common_tags = merge(
    {
      Environment = "Challenge"
      Owner       = "ashok"
    },
    var.tags
  )
} 