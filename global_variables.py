from datetime import datetime

SERVER_PROJECT = "broad-cho-priv1"
CLIENT_PROJECT = ""
ZONE = "us-central1-a"
REGION = "us-central1"
NETWORK_NAME = "secure-gwas"
SUBNET_NAME = "secure-gwas-subnet"
INSTANCE_NAME_ROOT = "secure-gwas"
BUCKET_NAME = "broad-cho-priv1-secure-gwas-data"
STATUS: str = "Setting up the Virtual Machine instance at " + \
    str(datetime.now())
