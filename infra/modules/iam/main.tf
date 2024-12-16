#  для настройки сервисного аккаунта в Yandex Cloud с необходимыми правами и ключами доступа, которые затем сохраняются локально в виде JSON-файлов.
resource "yandex_iam_service_account" "sa" {
  name        = var.name
  description = "Service account for VM management"
}

resource "yandex_resourcemanager_folder_iam_member" "sa_roles" {
  for_each = toset([
    "storage.admin",
    "dataproc.editor",
    "compute.admin",
    "dataproc.agent",
    "mdb.dataproc.agent",
    "vpc.user",
    "iam.serviceAccounts.user",
    "storage.uploader",
    "storage.viewer",
    "storage.editor"
  ])

  folder_id = var.provider_config.folder_id
  role      = each.key
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_iam_service_account_static_access_key" "sa-static-key" {
  service_account_id = yandex_iam_service_account.sa.id
  description        = "Static access key for service account"
}

resource "local_file" "sa-static-key-file" {
  content = jsonencode({
    id                 = yandex_iam_service_account_static_access_key.sa-static-key.id
    service_account_id = yandex_iam_service_account_static_access_key.sa-static-key.service_account_id
    created_at         = yandex_iam_service_account_static_access_key.sa-static-key.created_at
    s3_key_id          = yandex_iam_service_account_static_access_key.sa-static-key.access_key
    s3_secret_key      = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
  })
  filename        = "${path.module}/static_key.json"
  file_permission = "0600"
}

resource "yandex_iam_service_account_key" "sa-auth-key" {
  service_account_id = yandex_iam_service_account.sa.id
}

resource "local_file" "sa-auth-key-file" {
  content = jsonencode({
    id                  = yandex_iam_service_account_key.sa-auth-key.id
    service_account_id  = yandex_iam_service_account_key.sa-auth-key.service_account_id
    created_at          = yandex_iam_service_account_key.sa-auth-key.created_at
    public_key          = yandex_iam_service_account_key.sa-auth-key.public_key
    private_key         = regex("-----BEGIN PRIVATE KEY-----[\\s\\S]*$", yandex_iam_service_account_key.sa-auth-key.private_key)
  })
  filename        = "${path.module}/authorized_key.json"
  file_permission = "0600"
}


