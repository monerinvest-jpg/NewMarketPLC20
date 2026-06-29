variable "cloud_id" {
  description = "Yandex Cloud ID"
  type        = string
}

variable "folder_id" {
  description = "Yandex Cloud Folder ID"
  type        = string
}

variable "default_zone" {
  description = "Default availability zone"
  type        = string
  default     = "ru-central1-a"
}

variable "public_ssh_key_path" {
  description = "Path to public SSH key"
  type        = string
  default     = "/home/it/.ssh/id_rsa.pub"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "handmade"
}

variable "environment" {
  description = "Environment (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "service_account_id" {
  description = "Service account ID for compute instance groups"
  type        = string
}

# ─── Object storage + email (Postbox) ──────────────────────────────────────────

variable "postbox_sender_role" {
  description = "IAM role granting Postbox SMTP send rights to the mail service account"
  type        = string
  default     = "postbox.sender"
}

variable "smtp_from" {
  description = "Verified Postbox sender address used as the From: header"
  type        = string
  default     = "no-reply@example.com"
}

variable "kong_count" {
  description = "Number of Kong instances"
  type        = number
  default     = 2
}

variable "backend_count" {
  description = "Number of backend instances"
  type        = number
  default     = 2
}

variable "kong_cores" {
  description = "CPU cores for Kong VM"
  type        = number
  default     = 2
}

variable "kong_memory" {
  description = "Memory (GB) for Kong VM"
  type        = number
  default     = 2
}

variable "backend_cores" {
  description = "CPU cores for backend VM"
  type        = number
  default     = 2
}

variable "backend_memory" {
  description = "Memory (GB) for backend VM"
  type        = number
  default     = 2
}

variable "disk_size" {
  description = "Disk size (GB) for all VMs"
  type        = number
  default     = 20
}

# PostgreSQL variables (заменяют MySQL)
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "17"
}

variable "postgres_preset" {
  description = "Resource preset for PostgreSQL cluster"
  type        = string
  default     = "s2.micro"
}

variable "postgres_disk" {
  description = "PostgreSQL disk size (GB)"
  type        = number
  default     = 20
}

# Redis variables (без изменений)
variable "redis_version" {
  description = "Redis/Valkey version"
  type        = string
  default     = "8.0-valkey"
}

variable "redis_preset" {
  description = "Resource preset for Redis cluster"
  type        = string
  default     = "b3-c1-m4"
}

variable "redis_disk" {
  description = "Redis disk size (GB)"
  type        = number
  default     = 16
}

variable "public_cidr" {
  description = "CIDR for public subnet"
  type        = string
  default     = "192.168.1.0/24"
}

variable "private_cidr" {
  description = "CIDR for private subnet A"
  type        = string
  default     = "192.168.10.0/24"
}

variable "labels" {
  description = "Resource labels"
  type        = map(string)
  default     = {}
}
