import base64
from typing import Tuple
from flask import Blueprint, current_app, render_template, request

from src.utils.helper_functions import validate

bp = Blueprint("general", __name__)


@bp.route("/", methods=["GET"])
@bp.route("/home", methods=["GET"])
def home() -> str:
    return render_template("home.html")


@bp.route("/workflow")
def workflow() -> str:
    return render_template("workflow.html")


@bp.route("/permissions")
def permissions() -> str:
    return render_template("permissions.html")


# for the pubsub
@bp.route("/", methods=["POST"])
def index() -> Tuple[str, int]:
    envelope = request.get_json()
    if not envelope:
        return fail()

    if not isinstance(envelope, dict) or "message" not in envelope:
        return fail()

    pubsub_message = envelope.get("message")
    print(f"Pub/Sub message received: {pubsub_message}")

    if not isinstance(pubsub_message, dict) or "data" not in pubsub_message:
        return fail()

    publishTime = pubsub_message.get("publishTime")
    message = base64.b64decode(pubsub_message["data"])
    msg_lst = message.decode("utf-8").strip().split("-")
    print(f"Pub/Sub message received: {msg_lst}")

    try:
        project_title: str = msg_lst[0]
        role: str = msg_lst[-2][-1]
        content: str = msg_lst[-1]

        db = current_app.config["DATABASE"]
        doc_ref = db.collection("projects").document(
            project_title.replace(" ", "").lower()
        )
        doc_ref_dict = doc_ref.get().to_dict()
        statuses = doc_ref_dict.get("status")

        if content.isnumeric():
            if validate(int(content), doc_ref_dict, int(role)):
                statuses[role] = ["not ready"]
            else:
                statuses[role] = ["invalid data"]
        else:
            statuses.get(role).append(f"{content} - {publishTime}")
        doc_ref.set({"status": statuses}, merge=True)
    except Exception as e:
        print(f"error: {e}")
    finally:
        return ("", 204)


def fail() -> Tuple[str, int]:
    msg = "Invalid Pub/Sub message received"
    print(f"error: {msg}")
    return (f"Bad Request: {msg}", 400)
