"""
Script: data_preprocess.py
DAG: data_preprocess
Description: Simple DAG for Data Preprocessing with PySpark on Yandex.Cloud
"""

import uuid
from datetime import datetime, timedelta
from airflow import DAG
from airflow.settings import Session
from airflow.models import Connection, Variable
from airflow.utils.trigger_rule import TriggerRule
from airflow.providers.yandex.operators.yandexcloud_dataproc import (
    DataprocCreateClusterOperator,
    DataprocCreatePysparkJobOperator,
    DataprocDeleteClusterOperator,
)

# Общие переменные для вашего облака
YC_ZONE = Variable.get("YC_ZONE")
YC_FOLDER_ID = Variable.get("YC_FOLDER_ID")
YC_SUBNET_ID = Variable.get("YC_SUBNET_ID")
YC_SSH_PUBLIC_KEY = Variable.get("YC_SSH_PUBLIC_KEY")

# Переменные для подключения к Object Storage
S3_ENDPOINT_URL = Variable.get("S3_ENDPOINT_URL")
S3_ACCESS_KEY = Variable.get("S3_ACCESS_KEY")
S3_SECRET_KEY = Variable.get("S3_SECRET_KEY")
S3_BUCKET_NAME = Variable.get("S3_BUCKET_NAME")
S3_INPUT_DATA_BUCKET = S3_BUCKET_NAME + "/airflow/"  # YC S3 bucket for input data
S3_SOURCE_BUCKET = S3_BUCKET_NAME[:]  # YC S3 bucket for pyspark source files
S3_DP_LOGS_BUCKET = S3_BUCKET_NAME + "/airflow_logs/"  # YC S3 bucket for Data Proc logs

# Переменные необходимые для создания Dataproc кластера
DP_SA_AUTH_KEY_PUBLIC_KEY = Variable.get("DP_SA_AUTH_KEY_PUBLIC_KEY")
DP_SA_PATH = Variable.get("DP_SA_PATH")
DP_SA_ID = Variable.get("DP_SA_ID")
DP_SECURITY_GROUP_ID = Variable.get("DP_SECURITY_GROUP_ID")

# Создание подключения для Object Storage
YC_S3_CONNECTION = Connection(
    conn_id="yc-s3",
    conn_type="s3",
    host=S3_ENDPOINT_URL,
    extra={
        "aws_access_key_id": S3_ACCESS_KEY,
        "aws_secret_access_key": S3_SECRET_KEY,
        "host": S3_ENDPOINT_URL,
    },
)
# Создание подключения для Dataproc
YC_SA_CONNECTION = Connection(
    conn_id="yc-sa",
    conn_type="yandexcloud",
    extra={
        "extra__yandexcloud__public_ssh_key": DP_SA_AUTH_KEY_PUBLIC_KEY,
        "extra__yandexcloud__service_account_json_path": DP_SA_PATH,
    },
)


# Проверка наличия подключений в Airflow
# Если подключения отсутствуют, то они добавляются
# и сохраняются в базе данных Airflow
# Подключения используются для доступа к Object Storage и Dataproc
def setup_airflow_connections(*connections: Connection) -> None:
    """
    Check and add missing connections to Airflow.

    Parameters
    ----------
    *connections : Connection
        Variable number of Airflow Connection objects to verify and add

    Returns
    -------
    None
    """
    session = Session()
    try:
        for conn in connections:
            if not session.query(Connection).filter(Connection.conn_id == conn.conn_id).first():
                session.add(conn)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# Проверка и добавление подключений в Airflow
setup_airflow_connections(YC_S3_CONNECTION, YC_SA_CONNECTION)


# Настройки DAG
with DAG(
    dag_id="data_preprocess",
    start_date=datetime(year=2024, month=1, day=20),
    schedule_interval=timedelta(minutes=10),
    catchup=False,
) as ingest_dag:
    # 1 этап: создание Dataproc клаcтера
    create_spark_cluster = DataprocCreateClusterOperator(
        task_id="dp-cluster-create-task",
        folder_id=YC_FOLDER_ID,
        cluster_name=f"tmp-dp-{uuid.uuid4()}",
        cluster_description="Temporary cluster for Spark processing under Airflow orchestration",
        subnet_id=YC_SUBNET_ID,
        s3_bucket=S3_DP_LOGS_BUCKET,
        service_account_id=DP_SA_ID,
        ssh_public_keys=YC_SSH_PUBLIC_KEY,
        zone=YC_ZONE,
        cluster_image_version="2.0.43",
        # masternode
        masternode_resource_preset="s3-c4-m16",
        masternode_disk_type="network-ssd",
        # datanodes
        datanode_resource_preset="s3-c4-m16",
        datanode_disk_type="network-ssd",
        datanode_count=1,
        # software
        services=["YARN", "SPARK", "HDFS", "MAPREDUCE"],
        computenode_count=1,
        connection_id=YC_SA_CONNECTION.conn_id,
        dag=ingest_dag,
    )
    # 2 этап: запуск задания PySpark
    poke_spark_processing = DataprocCreatePysparkJobOperator(
        task_id="dp-cluster-pyspark-task",
        main_python_file_uri=f"s3a://{S3_SOURCE_BUCKET}/process_transaction_data.py",
        connection_id=YC_SA_CONNECTION.conn_id,
        args=["--bucket", f"{S3_BUCKET_NAME}/processed_data"],
        dag=ingest_dag,
    )
    # 3 этап: удаление Dataproc кластера
    delete_spark_cluster = DataprocDeleteClusterOperator(
        task_id="dp-cluster-delete-task",
        trigger_rule=TriggerRule.ALL_DONE,
        dag=ingest_dag,
    )
    # Формирование DAG из указанных выше этапов
    # pylint: disable=pointless-statement
    create_spark_cluster >> poke_spark_processing >> delete_spark_cluster
