import io
import os
import zipfile
from datetime import datetime

from firebase_admin import auth as firebase_auth
from flask import Blueprint, Response, current_app, jsonify, request, send_file

from src.api_utils import get_display_names, get_studies
from src.auth import authenticate, verify_token
from src.utils import custom_logging
from src.utils.generic_functions import add_notification, remove_notification
from src.utils.google_cloud.google_cloud_secret_manager import get_firebase_api_key
from src.utils.google_cloud.google_cloud_storage import (
    download_blob_to_bytes,
    download_blob_to_filename,
)
from src.utils.studies_functions import (
    add_file_to_zip,
    check_conditions,
    update_status_and_start_setup,
)

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("web", __name__, url_prefix="/api")


@bp.route("/createCustomToken", methods=["POST"])
@authenticate
def create_custom_token() -> Response:
    print("Creating custom token")
    user = verify_token(request.headers.get("Authorization").split(" ")[1])
    microsoft_user_id = user["sub"]
    try:
        custom_token = firebase_auth.create_custom_token(microsoft_user_id)
        firebase_api_key = get_firebase_api_key()
        return (
            jsonify(
                {
                    "customToken": custom_token.decode("utf-8"),
                    "firebaseApiKey": firebase_api_key,
                }
            ),
            200,
        )
    except Exception as e:
        print("Error creating custom token:", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/public_studies", methods=["GET"])
@authenticate
def public_studies() -> Response:
    try:
        public_studies = get_studies(private_filter=False)
        display_names = get_display_names()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    for study in public_studies:
        study["owner_name"] = display_names.get(study["owner"], study["owner"])

    return jsonify({"studies": public_studies})


@bp.route("/my_studies", methods=["GET"])
@authenticate
def my_studies() -> Response:
    try:
        my_studies = get_studies()
        display_names = get_display_names()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    for study in my_studies:
        study["owner_name"] = display_names.get(study["owner"], study["owner"])

    user = verify_token(request.headers.get("Authorization").split(" ")[1])
    sub = user["sub"]
    my_studies = [
        study
        for study in my_studies
        if sub in study["participants"] or sub in study["invited_participants"]
    ]
    return jsonify({"studies": my_studies})


@bp.route("/profile/<user_id>", methods=["GET", "POST"])
@authenticate
def profile(user_id: str = None) -> Response:
    db = current_app.config["DATABASE"]

    if not user_id:
        user_id = verify_token(request.headers.get("Authorization").split(" ")[1])[
            "sub"
        ]

    if request.method == "GET":
        try:
            display_names = (
                db.collection("users").document("display_names").get().to_dict() or {}
            )
            profile = db.collection("users").document(user_id).get().to_dict() or {}

            profile["displayName"] = display_names.get(user_id, user_id)
            return jsonify({"profile": profile}), 200

        except Exception as e:
            return (
                jsonify({"error": "Failed to fetch profile data", "details": str(e)}),
                500,
            )

    elif request.method == "POST":
        try:
            data = request.get_json()
            logged_in_user_id = verify_token(
                request.headers.get("Authorization").split(" ")[1]
            )["sub"]

            if logged_in_user_id != user_id:
                return (
                    jsonify({"error": "You are not authorized to update this profile"}),
                    403,
                )

            display_names = (
                db.collection("users").document("display_names").get().to_dict() or {}
            )
            display_names[user_id] = data["displayName"]
            db.collection("users").document("display_names").set(display_names)

            profile = db.collection("users").document(user_id).get().to_dict() or {}
            profile["about"] = data["about"]
            db.collection("users").document(user_id).set(profile)

            return jsonify({"message": "Profile updated successfully"})

        except Exception as e:
            return (
                jsonify({"error": "Failed to update profile", "details": str(e)}),
                500,
            )


@bp.route("/start_protocol", methods=["POST"])
@authenticate
def start_protocol() -> Response:
    user_id = verify_token(request.headers.get("Authorization").split(" ")[1])["sub"]
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(request.args.get("title"))
    doc_ref_dict = doc_ref.get().to_dict() or {}
    statuses = doc_ref_dict["status"]

    if statuses[user_id] == "":
        if message := check_conditions(doc_ref_dict, user_id):
            return jsonify({"error": message}), 400

        statuses[user_id] = "ready to begin sfkit"
        doc_ref.set({"status": statuses}, merge=True)

    if "" in statuses.values():
        logger.info("Not all participants are ready.")
    elif statuses[user_id] == "ready to begin sfkit":
        update_status_and_start_setup(doc_ref, doc_ref_dict, request.args.get("title"))

    return jsonify({"message": "Protocol started successfully"}), 200


@bp.route("/send_message", methods=["POST"])
@authenticate
def send_message() -> Response:
    db = current_app.config["DATABASE"]

    data = request.get_json()
    study_title = data.get("study_title")
    message = data.get("message")
    sender = data.get("sender")

    if not message or not sender or not study_title:
        return jsonify({"error": "Message, sender, and study_title are required"}), 400

    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    new_message = {
        "sender": sender,
        "time": datetime.now().strftime("%m/%d/%Y %H:%M"),
        "body": message,
    }

    doc_ref_dict["messages"] = doc_ref_dict.get("messages", []) + [new_message]
    doc_ref.set(doc_ref_dict)

    return jsonify({"message": "Message sent successfully", "data": new_message}), 200


@bp.route("/download_results_file", methods=("GET",))
@authenticate
def download_results_file() -> Response:
    user_id = verify_token(request.headers.get("Authorization").split(" ")[1])["sub"]

    db = current_app.config["DATABASE"]
    study_title = request.args.get("study_title")

    doc_ref_dict = db.collection("studies").document(study_title).get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(user_id))

    base = "src/static/results"
    shared = f"{study_title}/p{role}"
    os.makedirs(f"{base}/{shared}", exist_ok=True)

    result_success = download_blob_to_filename(
        "sfkit",
        f"{shared}/result.txt",
        f"{base}/{shared}/result.txt",
    )

    plot_name = "manhattan" if "GWAS" in doc_ref_dict["study_type"] else "pca_plot"
    plot_success = download_blob_to_filename(
        "sfkit",
        f"{shared}/{plot_name}.png",
        f"{base}/{shared}/{plot_name}.png",
    )

    if not (result_success or plot_success):
        return send_file(
            io.BytesIO("Failed to get results".encode()),
            download_name="result.txt",
            mimetype="text/plain",
            as_attachment=True,
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if result_success:
            add_file_to_zip(zip_file, f"{base}/{shared}/result.txt", "result.txt")
        if plot_success:
            add_file_to_zip(
                zip_file, f"{base}/{shared}/{plot_name}.png", f"{plot_name}.png"
            )

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        download_name=f"{study_title}_p{role}_results.zip",
        mimetype="application/zip",
        as_attachment=True,
    )


@bp.route("/fetch_plot_file", methods=["POST"])
@authenticate
def fetch_plot_file() -> Response:
    user_id = verify_token(request.headers.get("Authorization").split(" ")[1])["sub"]
    study_title = request.get_json().get("study_title")
    db = current_app.config["DATABASE"]
    doc_ref_dict = db.collection("studies").document(study_title).get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(user_id))

    plot_name = "manhattan" if "GWAS" in doc_ref_dict["study_type"] else "pca_plot"

    if plot := download_blob_to_bytes(
        "sfkit", f"{study_title}/p{role}/{plot_name}.png"
    ):
        return send_file(
            io.BytesIO(plot),
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{plot_name}.png",
        )
    else:
        return "File not found", 404


@bp.route("/update_notifications", methods=["POST"])
@authenticate
def update_notifications() -> Response:
    user_id = verify_token(request.headers.get("Authorization").split(" ")[1])["sub"]
    data = request.get_json()

    remove_notification(data.get("notification"), user_id)
    add_notification(data.get("notification"), user_id, "old_notifications")
    return Response(status=200)
