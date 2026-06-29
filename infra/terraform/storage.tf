# Object storage for the marketplace: product images (served via per-object
# public-read ACL) and PRIVATE digital goods / encrypted HLS (served via
# short-lived presigned URLs or the gated proxy). One bucket, mixed visibility.
#
# The app talks S3 via static access keys (boto3), not the instance IAM token,
# so we mint a dedicated service account with a static access key.

resource "yandex_iam_service_account" "storage" {
  folder_id   = var.folder_id
  name        = "${var.project_name}-storage"
  description = "S3 access for marketplace object storage (images + digital goods)"
}

resource "yandex_resourcemanager_folder_iam_member" "storage_editor" {
  folder_id = var.folder_id
  role      = "storage.editor"
  member    = "serviceAccount:${yandex_iam_service_account.storage.id}"
}

resource "yandex_iam_service_account_static_access_key" "storage_key" {
  service_account_id = yandex_iam_service_account.storage.id
  description        = "Static S3 key used by backend services (S3_ACCESS_KEY/S3_SECRET_KEY)"
}

resource "yandex_storage_bucket" "assets" {
  access_key = yandex_iam_service_account_static_access_key.storage_key.access_key
  secret_key = yandex_iam_service_account_static_access_key.storage_key.secret_key
  bucket     = "${var.project_name}-${var.environment}-assets"

  # Bucket itself is private (no anonymous listing). Product images are uploaded
  # with an object-level public-read ACL; digital assets stay fully private.
  anonymous_access_flags {
    read = false
    list = false
  }

  # Tidy up incomplete multipart uploads.
  lifecycle_rule {
    id      = "abort-incomplete-multipart"
    enabled = true
    abort_incomplete_multipart_upload_days = 7
  }
}

output "s3_bucket" {
  value = yandex_storage_bucket.assets.bucket
}

output "s3_access_key" {
  value     = yandex_iam_service_account_static_access_key.storage_key.access_key
  sensitive = true
}

output "s3_secret_key" {
  value     = yandex_iam_service_account_static_access_key.storage_key.secret_key
  sensitive = true
}
