import os
from datetime import datetime, timedelta
import subprocess

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 12, 16),
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
    'depends_on_past': False,
}


def run_train_script():
    script_path = BASE_DIR + '/otus_mlops_cont_train/src/train.py'
    command = ['python', script_path]
    result = subprocess.run(command, capture_output=True, text=True)


with DAG(
    'fraud_detection_pipeline',
    default_args=default_args,
    description='ML Pipeline for Fraud Detection',
    schedule_interval='@monthly',  # каждый месяц
    catchup=False,
) as dag:

    run_ml_train_task = PythonOperator(
        task_id='run_ml_train_script',
        python_callable=run_train_script,
        dag=dag,
    )

    run_ml_train_task
