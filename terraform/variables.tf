variable "prefix" {
  description = "Resource prefix"
  type        = string
  default     = "hydro"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28.3"
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {
    environment = "dev"
    project     = "hydrosat"
  }
} 