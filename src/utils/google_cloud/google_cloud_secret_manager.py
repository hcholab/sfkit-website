import asyncio

from google.cloud import secretmanager

from src.utils import constants

_FIREBASE_API_KEY = constants.FIREBASE_API_KEY

async def get_firebase_api_key() -> str:
    global _FIREBASE_API_KEY
    if not _FIREBASE_API_KEY:
        _FIREBASE_API_KEY = await get_secret("FIREBASE_API_KEY")
    return _FIREBASE_API_KEY


async def get_secret(name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    version = client.secret_version_path(constants.SERVER_GCP_PROJECT, name, "latest")
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, client.access_secret_version, {"name": version}
    )
    return response.payload.data.decode("UTF-8")
