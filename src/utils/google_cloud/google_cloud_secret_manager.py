import asyncio
import os

from google.cloud import secretmanager

from src.utils import constants


async def get_firebase_api_key() -> str:
    firebase_api_key = os.environ.get("FIREBASE_API_KEY")
    if not firebase_api_key:
        firebase_api_key = await get_secret("FIREBASE_API_KEY")
        os.environ.setdefault("FIREBASE_API_KEY", firebase_api_key)
    return firebase_api_key


async def get_secret(name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    version = client.secret_version_path(constants.SERVER_GCP_PROJECT, name, "latest")
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, client.access_secret_version, {"name": version}
    )
    return response.payload.data.decode("UTF-8")
