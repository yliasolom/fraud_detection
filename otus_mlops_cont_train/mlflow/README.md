## Запуск mlflow

На виртуальной машине в YC, которая находитcя в той же сети и подсети, что и ваш dataproc-cluster:

1. Создайте файлик .env, в который добавьте примерно следующее:

```bash 
MLFLOW_PG_USER=mlflow
MLFLOW_PG_PASSWORD=mlflow
MLFLOW_PG_DATABASE=mlflow
MLFLOW_S3_ENDPOINT_URL=https://storage.yandexcloud.net/
AWS_ACCESS_KEY_ID=<идентификатор секретного ключа>
AWS_SECRET_ACCESS_KEY=<секретный ключ>
```

1. Установите все нужные переменные окружния разом:

```bash
source .env
```

1. Запустите Postgres в docker-compose:

```bash
docker-compose up -d
```

1. Установите mlflow:

```bash
pip install mlflow
```

1. Запустите MLFlow Tracking Server, который будет сохранять метрики в Postgres в докере, а модели и прочие артефакты – в S3-бакете в YC.

```bash
mlflow server --backend-store-uri postgresql://${MLFLOW_PG_USER}:${MLFLOW_PG_PASSWORD}@localhost:5432/${MLFLOW_PG_DATABASE} --default-artifact-root s3://otus-mlflow-bucket/artifacts -h 0.0.0.0 -p 8000
```





