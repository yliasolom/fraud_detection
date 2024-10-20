# IAM ресурсы
resource "yandex_iam_service_account" "sa" {
  name        = var.yc_service_account_name
  description = "Service account for Dataproc cluster and related services"
}

resource "yandex_resourcemanager_folder_iam_member" "sa_roles" {
  for_each = toset([
    "dataproc.editor",
    "dataproc.agent",
    "mdb.dataproc.agent",
    "iam.serviceAccounts.user"
  ])

  folder_id = var.yc_folder_id
  role      = each.key
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_iam_service_account_static_access_key" "sa-static-key" {
  service_account_id = yandex_iam_service_account.sa.id
  description        = "Static access key for Dataproc"
}

# Dataproc ресурсы
resource "yandex_dataproc_cluster" "dataproc_cluster" {
  depends_on  = [yandex_resourcemanager_folder_iam_member.sa_roles]
  description = "Dataproc Cluster created by Terraform"
  name        = "otus-dataproc-cluster"
  labels = {
    created_by = "terraform"
  }
  service_account_id = yandex_iam_service_account.sa.id
  zone_id            = var.yc_zone

  cluster_config {
    version_id = var.yc_dataproc_version

    hadoop {
      services = ["HDFS", "YARN", "SPARK"]
      properties = {
        "yarn:yarn.resourcemanager.am.max-attempts" = 5
      }
    }

    subcluster_spec {
      name = "master"
      role = "MASTERNODE"
      resources {
        resource_preset_id = "s3-c2-m8"  # Класс хоста для мастер-подкластера
        disk_type_id       = "network-ssd"
        disk_size          = 40  # Размер хранилища 40 ГБ
      }
      hosts_count      = 1
      assign_public_ip = true
    }

    subcluster_spec {
      name = "data"
      role = "DATANODE"
      resources {
        resource_preset_id = "s3-c4-m16"  # Класс хоста для дата-подкластера
        disk_type_id       = "network-ssd"
        disk_size          = 128  # Размер хранилища 128 ГБ
      }
      hosts_count = 3  # Количество хостов в дата-подкластер
    }

    subcluster_spec {
      name = "compute"
      role = "COMPUTENODE"
      resources {
        resource_preset_id = var.dataproc_compute_resources.resource_preset_id
        disk_type_id       = "network-ssd"
        disk_size          = var.dataproc_compute_resources.disk_size
      }
      hosts_count = 1
    }
  }
}