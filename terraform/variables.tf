variable "prefix"               { description = "Resource prefix";  type = string; default = "hydro" }
variable "location"             { description = "Azure region";     type = string; default = "westeurope" }
variable "kubernetes_version"   { description = "AKS version";      type = string; default = "1.29" }
variable "tags" {
  type        = map(string)
  description = "Common tags"
  default     = { Environment = "Challenge", Owner = "<<<EDIT YOUR NAME>>>" }
} 