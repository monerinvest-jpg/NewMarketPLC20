# Transactional email via Yandex Cloud Postbox (SMTP interface).
#
# Postbox authenticates SMTP with a service-account static access key:
#   SMTP_USER     = static key id
#   SMTP_PASSWORD = static key secret
#   SMTP_HOST     = postbox.cloud.yandex.net   (port 587, STARTTLS)
#
# The SENDER IDENTITY (verified domain or single email address) must be created
# separately — in the console or `yc postbox` — and its address set as smtp_from.
# Identity verification (SPF/DKIM/DMARC) is a DNS step that Terraform can't do
# for an external domain, so it is intentionally out of band here.

resource "yandex_iam_service_account" "mail" {
  folder_id   = var.folder_id
  name        = "${var.project_name}-mail"
  description = "Postbox SMTP sender for marketplace transactional email"
}

resource "yandex_resourcemanager_folder_iam_member" "mail_sender" {
  folder_id = var.folder_id
  role      = var.postbox_sender_role
  member    = "serviceAccount:${yandex_iam_service_account.mail.id}"
}

resource "yandex_iam_service_account_static_access_key" "mail_key" {
  service_account_id = yandex_iam_service_account.mail.id
  description        = "SMTP credentials for Postbox (SMTP_USER / SMTP_PASSWORD)"
}

output "smtp_user" {
  value     = yandex_iam_service_account_static_access_key.mail_key.access_key
  sensitive = true
}

output "smtp_password" {
  value     = yandex_iam_service_account_static_access_key.mail_key.secret_key
  sensitive = true
}
