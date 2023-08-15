from flask import current_app, g, redirect, url_for
from werkzeug import Response

from src.utils import custom_logging

logger = custom_logging.setup_logging(__name__)


def redirect_with_flash(url: str = "", location: str = "", message: str = "", error: str = "") -> Response:
    if url and location:
        raise ValueError("Both 'url' and 'location' cannot be provided. Provide only one of them.")
    if not url and not location:
        raise ValueError("At least one of 'url' or 'location' must be provided.")

    if location:
        url = url_for(location)

    dest = redirect(url)
    logger.info(f"{message}: {error}") if error else logger.info(message)
    flash(dest, message)
    return dest


def flash(response: Response, message: str) -> Response:
    response.set_cookie(key="flash", value=message, path="/")
    return response


def get_notifications() -> list[str]:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(g.user["id"])
    doc_ref_dict = doc_ref.get().to_dict()
    return doc_ref_dict.get("notifications", [])


def remove_notification(notification: str) -> None:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(g.user["id"])
    doc_ref_dict = doc_ref.get().to_dict()
    notifications = doc_ref_dict.get("notifications", [])
    notifications.remove(notification)
    doc_ref.set({"notifications": notifications}, merge=True)


def add_notification(notification: str, user_id: str, location: str = "notifications") -> None:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(user_id)
    doc_ref_dict: dict = doc_ref.get().to_dict() or {}
    notifications: list[str] = doc_ref_dict.get(location, [])
    notifications.append(notification)
    doc_ref.set({location: notifications}, merge=True)
