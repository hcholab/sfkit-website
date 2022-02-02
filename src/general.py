import base64
from flask import Blueprint, current_app, render_template, request

bp = Blueprint("general", __name__)


@bp.route("/", methods=["GET"])
@bp.route("/home", methods=["GET"])
def home():
    return render_template("home.html")


@bp.route("/workflow")
def workflow():
    return render_template("workflow.html")


@bp.route("/permissions")
def permissions():
    return render_template("permissions.html")


@bp.route("/", methods=["POST"])
def index():
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        return (f"Bad Request: {msg}", 400)

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return (f"Bad Request: {msg}", 400)

    pubsub_message = envelope["message"]

    messsage = []
    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        message = (
            base64.b64decode(pubsub_message["data"]).decode("utf-8").strip().split("-")
        )

    if len(message) > 1:
        (project_title, role, status) = (
            message[0],
            message[-2][-1],
            message[-1],
        )
        if role.isdigit():
            # update status in firestore
            db = current_app.config["DATABASE"]
            doc_ref = db.collection("projects").document(project_title)

            statuses = doc_ref.get().to_dict()["status"]
            statuses[int(role)] = status

            doc_ref.set({"status": statuses}, merge=True)
    else:
        print(f"error: {message}")

    return ("", 204)
