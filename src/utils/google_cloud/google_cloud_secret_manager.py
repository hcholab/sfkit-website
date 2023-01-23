import os

from google.cloud import secretmanager

from src.utils import constants


def get_firebase_api_key() -> str:
    firebase_api_key = os.environ.get("FIREBASE_API_KEY")
    if not firebase_api_key:
        firebase_api_key = get_secret("FIREBASE_API_KEY")
        os.environ.setdefault("FIREBASE_API_KEY", firebase_api_key)
    return firebase_api_key


def get_secret(name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    version = client.secret_version_path(constants.SERVER_GCP_PROJECT, name, "latest")
    response = client.access_secret_version(request={"name": version})
    return response.payload.data.decode("UTF-8")
