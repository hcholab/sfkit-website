from quart import current_app
from google.cloud.firestore_v1 import FieldFilter

from src.utils import custom_logging


logger = custom_logging.setup_logging(__name__)


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
            studies_query = studies_query.where(
                filter=FieldFilter("private", "==", private_filter)
            )
        studies = [doc.to_dict() async for doc in studies_query.stream()]
    except Exception as e:
        raise RuntimeError(
            {"error": "Failed to fetch studies", "details": str(e)}
        ) from e

    return studies


async def get_display_names() -> dict:
    db = current_app.config["DATABASE"]
    try:
        doc_ref = await db.collection("users").document("display_names").get()
        display_names = doc_ref.to_dict() or {}
    except Exception as e:
        raise RuntimeError(
            {"error": "Failed to fetch display names", "details": str(e)}
        ) from e

    return display_names


async def add_user_to_db(decoded_token: dict) -> None:
    logger.info(f"Creating user {decoded_token['sub']}")
    db = current_app.config["DATABASE"]
    try:
        await db.collection("users").document(decoded_token["sub"]).set({"about": "", "notifications": []})
        display_name = decoded_token["sub"]
        if "given_name" in decoded_token:
            display_name = decoded_token["given_name"]
            if "family_name" in decoded_token:
                display_name += " " + decoded_token["family_name"]
        await db.collection("users").document("display_names").set(
            {decoded_token["sub"]: display_name}, merge=True
        )
    except Exception as e:
        raise RuntimeError({"error": "Failed to create user", "details": str(e)}) from e
