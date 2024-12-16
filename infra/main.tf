# main.tf

# Создает все необходимые ресурсы (VM, сеть, хранилище, сервисный аккаунт).
# Подготавливает и копирует переменные.
# Импортирует переменные в Airflow для корректной работы DAG-ов.
# Упрощает настройку окружения: все автоматизировано и готово после выполнения terraform apply.

locals {
  home = "/home/${var.yc_instance_user}"
  variables_path  = "${local.home}/variables.json"
  authorized_key_path = "${local.home}/authorized_key.json"
  import_airflow_variables_path = "${local.home}/import_airflow_variables.sh"
}

module "iam" {
  source          = "./modules/iam"
  name            = var.yc_service_account_name
  provider_config = var.yc_config
}

module "network" {
  source          = "./modules/network"
  network_name    = var.yc_network_name
  subnet_name     = var.yc_subnet_name
  provider_config = var.yc_config
}

module "storage" {
  source          = "./modules/storage"
  name            = var.yc_bucket_name
  provider_config = var.yc_config
  access_key      = module.iam.access_key
  secret_key      = module.iam.secret_key
}

module "compute" {
  source             = "./modules/compute"
  instance_user      = var.yc_instance_user
  instance_name      = var.yc_instance_name
  service_account_id = module.iam.service_account_id
  subnet_id          = module.network.subnet_id
  ubuntu_image_id    = var.ubuntu_image_id
  public_key_path    = var.public_key_path
  private_key_path   = var.private_key_path
  provider_config    = var.yc_config
}

resource "local_file" "variables_file" {
  content = jsonencode({
    # общие переменные
    YC_ZONE           = var.yc_config.zone
    YC_FOLDER_ID      = var.yc_config.folder_id
    YC_SUBNET_ID      = module.network.subnet_id
    YC_SSH_PUBLIC_KEY = trimspace(file(var.public_key_path))
    # S3
    S3_ENDPOINT_URL = var.yc_storage_endpoint_url
    S3_ACCESS_KEY   = module.iam.access_key
    S3_SECRET_KEY   = module.iam.secret_key
    S3_BUCKET_NAME  = module.storage.bucket
    # Data Proc
    DP_SA_AUTH_KEY_PUBLIC_KEY = module.iam.public_key
    DP_SA_PATH                = local.authorized_key_path
    DP_SA_ID                  = module.iam.service_account_id
    DP_SECURITY_GROUP_ID      = module.network.security_group_id
  })
  filename        = "./variables.json"
  file_permission = "0600"
}


# Добавляем ресурс для копирования и импорта переменных
resource "null_resource" "import_variables" {
  connection {
    type        = "ssh"
    user        = var.yc_instance_user
    private_key = file(var.private_key_path)
    host        = module.compute.external_ip_address
  }

  # Копируем файлы на VM
  provisioner "file" {
    source      = "${path.root}/modules/iam/authorized_key.json"
    destination = local.authorized_key_path
  }
  
  provisioner "file" {
    source      = "./variables.json"
    destination = local.variables_path
  }

  provisioner "file" {
    content = templatefile("${path.root}/scripts/import_airflow_variables.sh", {
      airflow_db_conn = var.airflow_db_conn_default
      }
    )
    destination = local.import_airflow_variables_path
  }

  # Импортируем переменные через Airflow CLI
  provisioner "remote-exec" {
    inline = [
      "chmod +x ${local.import_airflow_variables_path}",
      "bash ${local.import_airflow_variables_path}"
    ]
  }

  depends_on = [
    local_file.variables_file
  ]
}

# Запись переменных в .env файл
# AIRFLOW_ADMIN_PASSWORD это ID виртуальной машины
# AIRFLOW_HOST это IP виртуальной машины
resource "null_resource" "update_env" {
  provisioner "local-exec" {
    command = <<EOT
      # Определяем переменные
      AIRFLOW_HOST=${module.compute.external_ip_address}
      AIRFLOW_ADMIN_PASSWORD=${module.compute.instance_id}
      STORAGE_ENDPOINT_URL=${var.yc_storage_endpoint_url}
      BUCKET_NAME=${module.storage.bucket}
      ACCESS_KEY=${module.iam.access_key}
      SECRET_KEY=${module.iam.secret_key}

      # Замена пустых переменных в .env
#       sed -i "s|^AIRFLOW_HOST=.*|AIRFLOW_HOST=$AIRFLOW_HOST|" ../.env
#       sed -i "s|^AIRFLOW_ADMIN_PASSWORD=.*|AIRFLOW_ADMIN_PASSWORD=$AIRFLOW_ADMIN_PASSWORD|" ../.env
#       sed -i "s|^S3_ENDPOINT_URL=.*|S3_ENDPOINT_URL=$STORAGE_ENDPOINT_URL|" ../.env
#       sed -i "s|^S3_BUCKET_NAME=.*|S3_BUCKET_NAME=$BUCKET_NAME|" ../.env
#       sed -i "s|^S3_ACCESS_KEY=.*|S3_ACCESS_KEY=$ACCESS_KEY|" ../.env
#       sed -i "s|^S3_SECRET_KEY=.*|S3_SECRET_KEY=$SECRET_KEY|" ../.env
      sed -i '' "s|^AIRFLOW_HOST=.*|AIRFLOW_HOST=$AIRFLOW_HOST|" ../.env
      sed -i '' "s|^AIRFLOW_ADMIN_PASSWORD=.*|AIRFLOW_ADMIN_PASSWORD=$AIRFLOW_ADMIN_PASSWORD|" ../.env
      sed -i '' "s|^S3_ENDPOINT_URL=.*|S3_ENDPOINT_URL=$STORAGE_ENDPOINT_URL|" ../.env
      sed -i '' "s|^S3_BUCKET_NAME=.*|S3_BUCKET_NAME=$BUCKET_NAME|" ../.env
      sed -i '' "s|^S3_ACCESS_KEY=.*|S3_ACCESS_KEY=$ACCESS_KEY|" ../.env
      sed -i '' "s|^S3_SECRET_KEY=.*|S3_SECRET_KEY=$SECRET_KEY|" ../.env
    EOT
  }

  depends_on = [
    module.iam,
    module.storage
  ]
}
