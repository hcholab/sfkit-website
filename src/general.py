import base64
from typing import Tuple

from flask import Blueprint, current_app, make_response, render_template, request
from werkzeug import Response

from src.utils.gwas_functions import data_has_valid_size, data_has_valid_files

bp = Blueprint("general", __name__)


@bp.route("/", methods=["GET"])
@bp.route("/home", methods=["GET"])
def home() -> Response:
    return make_response(render_template("general/home.html"))


@bp.route("/instructions")
def instructions() -> Response:
    return make_response(render_template("general/instructions.html"))


@bp.route("/permissions")
def permissions() -> Response:
    return make_response(render_template("general/permissions.html"))


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
    msg = message.decode("utf-8").strip()
    print(f"Pub/Sub message decoded: {msg}")

    try:
        [study_title, rest] = msg.split("-secure-gwas", maxsplit=1)
        [role, content] = rest.split("-", maxsplit=1)

        db = current_app.config["DATABASE"]
        doc_ref = db.collection("studies").document(
            study_title.replace(" ", "").lower()
        )
        doc_ref_dict = doc_ref.get().to_dict()
        statuses = doc_ref_dict.get("status")
        id = doc_ref_dict.get("participants")[int(role) - 1]

        if "validate" in content:
            [_, size, files] = content.split("|", maxsplit=2)
            if data_has_valid_size(
                int(size), doc_ref_dict, int(role)
            ) and data_has_valid_files(files):
                statuses[id] = ["not ready"]
            else:
                statuses[id] = ["invalid data"]
        else:
            statuses.get(id).append(f"{content} - {publishTime}")
        doc_ref.set({"status": statuses}, merge=True)
    except Exception as e:
        print(f"error: {e}")
    finally:
        return ("", 204)


def fail() -> Tuple[str, int]:
    msg = "Invalid Pub/Sub message received"
    print(f"error: {msg}")
    return (f"Bad Request: {msg}", 400)
