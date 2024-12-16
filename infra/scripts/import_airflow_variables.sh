#!/bin/bash

function log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')]: $1"
}

export AIRFLOW__CORE__SQL_ALCHEMY_CONN=${airflow_db_conn}
#export AIRFLOW__CORE__SQL_ALCHEMY_CONN=$(airflow config get-value core sql_alchemy_conn)
#export AIRFLOW__CORE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost/airflow"

# Запуск скрипта импорта переменных
log 'Starting Airflow initialization...'
airflow db init

log 'Importing variables...'
airflow variables import /home/ubuntu/variables.json

log 'Verifying variables...'
airflow variables list

# Перезапускаем сервисы
log 'Restarting Airflow services...'
sudo systemctl restart airflow-webserver
sudo systemctl restart airflow-scheduler

# Ждем запуска сервисов
log 'Waiting for Airflow services to start...'
sleep 10
