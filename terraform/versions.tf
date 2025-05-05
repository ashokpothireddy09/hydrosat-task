terraform {
  required_version = ">= 1.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    azapi = {
      source  = "azure/azapi"
      version = ">= 1.4.0, < 2.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Provider configuration blocks *must* be multi‑line
provider "azurerm" {
  features {}          # required stub block :contentReference[oaicite:1]{index=1}
}

provider "azapi" {
  # no extra settings needed
}
