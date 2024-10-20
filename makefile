tf_init:
	cd infrastructure && terraform init -upgrade

tf_plan:
	cd infrastructure && terraform plan

tf_apply:
	cd infrastructure && terraform apply -auto-approve

tf_destroy:
	cd infrastructure && terraform destroy -auto-approve
