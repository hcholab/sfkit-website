from quart import current_app

from src.utils import custom_logging

logger = custom_logging.setup_logging(__name__)


async def remove_notification(notification: str, user_id: str) -> None:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(user_id)
    doc_ref_dict = (await doc_ref.get()).to_dict()
    notifications = doc_ref_dict.get("notifications", [])
    notifications.remove(notification)
    await doc_ref.set({"notifications": notifications}, merge=True)


async def add_notification(
    notification: str, user_id: str, location: str = "notifications"
) -> None:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(user_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict() or {}
    notifications: list[str] = doc_ref_dict.get(location, [])
    notifications.append(notification)
    await doc_ref.set({location: notifications}, merge=True)
