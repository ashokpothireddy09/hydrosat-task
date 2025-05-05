terraform {
  required_version = ">= 1.8.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    azapi = {
      source  = "azure/azapi"
      version = ">=1.4.0, <2.0.0"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azapi" {
  alias = "v1"
}

locals {
  aks_api_version = "2024-10-01"  
} 