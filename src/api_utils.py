import uuid
from typing import Union
from urllib.parse import urlparse, urlunsplit

import httpx
from google.cloud.firestore_v1 import FieldFilter
from quart import current_app
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from src.utils import constants, custom_logging

logger = custom_logging.setup_logging(__name__)

ID_KEY = "sub"
TERRA_ID_KEY = "id"

class APIException(HTTPException):
    def __init__(self, res: Union[httpx.Response, Response]):
        if isinstance(res, httpx.Response):
            res = Response(
                response=res.content,
                status=res.status_code,
                headers=res.headers.items(),
                content_type=res.headers.get("content-type"),
            )

        if res.content_type == "application/json" and callable(res.json) and "message" in res.json():
            desc = res.json()["message"]
        else:
            desc = str(res.get_data(as_text=True))

        super().__init__(description=desc, response=res)
        self.code = res.status_code


def get_websocket_origin():
    url = urlparse(constants.SFKIT_API_URL)
    scheme = "wss" if url.scheme == "https" else "ws"
    return urlunsplit((scheme, str(url.netloc), "", "", ""))


async def get_studies(private_filter=None) -> list:
    db = current_app.config["DATABASE"]
    desired_keys = [
        "study_id",
        "created",
        "title",
        "study_information",
        "description",
        "requested_participants",
        "participants",
        "owner",
        "private",
        "invited_participants",
        "study_type",
        "setup_configuration",
        "demo",
    ]
    try:
        studies_query = db.collection("studies").select(desired_keys)
        if private_filter is not None:
            studies_query = studies_query.where(filter=FieldFilter("private", "==", private_filter))
        studies = [doc.to_dict() async for doc in studies_query.stream()]
    except Exception as e:
        raise RuntimeError({"error": "Failed to fetch studies", "details": str(e)}) from e

    return studies


async def get_display_names() -> dict:
    db = current_app.config["DATABASE"]
    try:
        doc_ref = await db.collection("users").document("display_names").get()
        display_names = doc_ref.to_dict() or {}
    except Exception as e:
        raise RuntimeError({"error": "Failed to fetch display names", "details": str(e)}) from e

    return display_names


async def add_user_to_db(decoded_token: dict) -> None:
    user_id = decoded_token[TERRA_ID_KEY] if constants.TERRA else decoded_token[ID_KEY]
    logger.info(f"Creating user {user_id}")
    db = current_app.config["DATABASE"]
    try:
        display_name = user_id
        email = ""
        if constants.TERRA and "email" in decoded_token:
            display_name = decoded_token["email"]
            email = decoded_token["email"]
        if "given_name" in decoded_token:
            display_name = decoded_token["given_name"]
            if "family_name" in decoded_token:
                display_name += " " + decoded_token["family_name"]
        if "emails" in decoded_token:
            email = decoded_token["emails"][0]
        await db.collection("users").document("display_names").set({user_id: display_name}, merge=True)
        await db.collection("users").document(user_id).set(
            {
                "about": "",
                "notifications": [],
                "email": email,
                "display_name": display_name,
            },
            merge=True,
        )
    except Exception as e:
        raise RuntimeError({"error": "Failed to create user", "details": str(e)}) from e


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False
