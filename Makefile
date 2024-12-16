SHELL := /bin/bash

include .env

.EXPORT_ALL_VARIABLES:

# -i, -o StrictHostKeyChecking=no и
# -o UserKnownHostsFile=/dev/null
# отключают проверку подлинности хоста, чтобы избежать запроса на подтверждение.

.PHONY: setup-airflow-variables
setup-airflow-variables:
	@echo "Running setup_airflow_variables.sh on $(AIRFLOW_HOST)..."
	ssh -i $(PRIVATE_KEY_PATH) \
		-o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null \
		$(AIRFLOW_VM_USER)@$(AIRFLOW_HOST) \
		'bash /home/ubuntu/setup_airflow_variables.sh'
	@echo "Script execution completed"

.PHONY: upload-dags-to-airflow
upload-dags-to-airflow:
	@echo "Uploading dags to $(AIRFLOW_HOST)..."
	scp -i $(PRIVATE_KEY_PATH) \
		-o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null \
		-r dags/*.py $(AIRFLOW_VM_USER)@$(AIRFLOW_HOST):/home/airflow/dags/
	@echo "Dags uploaded successfully"

.PHONY: upload-src-to-bucket
upload-src-to-bucket:
	@echo "Uploading src to $(S3_BUCKET_NAME)..."
	s3cmd put --recursive src/ s3://$(S3_BUCKET_NAME)/src/
	@echo "Src uploaded successfully"

# .PHONY: upload-data-to-bucket
# upload-data-to-bucket:
# 	@echo "Uploading data to $(S3_BUCKET_NAME)..."
# 	s3cmd put --recursive data/input_data/*.csv s3://$(S3_BUCKET_NAME)/input_data/
# 	@echo "Data uploaded successfully"
#
# .PHONY: download-output-data-from-bucket
# download-output-data-from-bucket:
# 	@echo "Downloading output data from $(S3_BUCKET_NAME)..."
# 	s3cmd get --recursive s3://$(S3_BUCKET_NAME)/output_data/ data/output_data/
# 	@echo "Output data downloaded successfully"

.PHONY: instance-list
instance-list:
	@echo "Listing instances..."
	yc compute instance list

.PHONY: git-push-secrets
git-push-secrets:
	@echo "Pushing secrets to github..."
	python3 utils/push_secrets_to_github_repo.py
