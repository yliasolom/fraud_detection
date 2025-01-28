import os
from datetime import datetime, timedelta
import subprocess

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 12, 16),
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'depends_on_past': False,
}


def run_AB():
    script_path = BASE_DIR + '/otus_mlops_cont_train/src/ab_test_model.py'
    command = ['python', script_path]
    subprocess.run(command, capture_output=True, text=True)


with DAG(
    'fraud_AB_pipeline',
    default_args=default_args,
    description='AB for Fraud Detection',
    schedule_interval='@monthly',
    catchup=False,
) as dag:

    run_AB_task = PythonOperator(
        task_id='run_AB_task',
        python_callable=run_AB,
        dag=dag,
    )

    run_AB_task
