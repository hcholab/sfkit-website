from typing import List
from flask import current_app, g, redirect, url_for
from werkzeug import Response


def redirect_with_flash(
    url="", location: str = "", message: str = "", error: str = ""
) -> Response:
    if location:
        url = url_for(location)
    r = redirect(url)
    print(f"{message}: {error}") if error else print(message)
    flash(r, message)
    return r


def flash(response: Response, message: str) -> Response:
    response.set_cookie("flash", message)
    return response


def get_notifications() -> List[str]:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(g.user["id"])
    doc_ref_dict = doc_ref.get().to_dict()
    return doc_ref_dict.get("notifications") if doc_ref_dict else []


def remove_notification(notification: str) -> None:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(g.user["id"])
    doc_ref_dict = doc_ref.get().to_dict()
    notifications = doc_ref_dict.get("notifications") if doc_ref_dict else []
    notifications.remove(notification)
    doc_ref.update({"notifications": notifications})


def add_notification(notification: str, user_id: str) -> None:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("users").document(user_id)
    doc_ref_dict = doc_ref.get().to_dict()
    notifications = doc_ref_dict.get("notifications") if doc_ref_dict else []
    notifications.append(notification)
    doc_ref.set({"notifications": notifications})
