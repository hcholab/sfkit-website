import asyncio
import io
import os
import zipfile
from datetime import datetime

from firebase_admin import auth as firebase_auth
from quart import Blueprint, Response, current_app, jsonify, request, send_file

from src.api_utils import get_display_names, get_studies, is_valid_uuid
from src.auth import authenticate, get_user_id
from src.utils import constants, custom_logging
from src.utils.generic_functions import add_notification, remove_notification
from src.utils.google_cloud.google_cloud_secret_manager import \
    get_firebase_api_key
from src.utils.google_cloud.google_cloud_storage import (
    download_blob_to_bytes, download_blob_to_filename)
from src.utils.studies_functions import (add_file_to_zip, check_conditions,
                                         update_status_and_start_setup)

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("web", __name__, url_prefix="/api")


@bp.route("/createCustomToken", methods=["POST"])
@authenticate
async def create_custom_token() -> Response:
    user_id = await get_user_id()
    try:
        # Use the thread executor to run the blocking function
        loop = asyncio.get_event_loop()
        custom_token = await loop.run_in_executor(
            None, firebase_auth.create_custom_token, user_id
        )
        return (
            jsonify(
                {
                    "customToken": custom_token.decode("utf-8"),
                    "firebaseApiKey": await get_firebase_api_key(),
                    "firebaseProjectId": constants.FIREBASE_PROJECT_ID,
                    "firestoreDatabaseId": constants.FIRESTORE_DATABASE,
                }
            ),
            200,
        )
    except Exception as e:
        print("Error creating custom token:", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/public_studies", methods=["GET"])
@authenticate
async def public_studies() -> Response:
    try:
        public_studies = await get_studies(private_filter=False)
        display_names = await get_display_names()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    for study in public_studies:
        study["owner_name"] = display_names.get(study["owner"], study["owner"])

    return jsonify({"studies": public_studies})


@bp.route("/my_studies", methods=["GET"])
@authenticate
async def my_studies() -> Response:
    try:
        my_studies = await get_studies()
        display_names = await get_display_names()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    for study in my_studies:
        study["owner_name"] = display_names.get(study["owner"], study["owner"])

    user_id = await get_user_id()
    my_studies = [
        study
        for study in my_studies
        if user_id in study["participants"] or user_id in study["invited_participants"]
    ]
    return jsonify({"studies": my_studies})


@bp.route("/profile/<user_id>", methods=["GET", "POST"])
@authenticate
async def profile(user_id: str = None) -> Response:
    db = current_app.config["DATABASE"]

    if not user_id:
        user_id = await get_user_id()

    if request.method == "GET":
        try:
            display_names = (
                await db.collection("users").document("display_names").get()
            ).to_dict() or {}
            profile = (
                await db.collection("users").document(user_id).get()
            ).to_dict() or {}

            profile["displayName"] = display_names.get(user_id, user_id)
            return jsonify({"profile": profile}), 200

        except Exception as e:
            return (
                jsonify({"error": "Failed to fetch profile data", "details": str(e)}),
                500,
            )

    elif request.method == "POST":
        try:
            data = await request.get_json()
            logged_in_user_id = await get_user_id()

            if logged_in_user_id != user_id:
                return (
                    jsonify({"error": "You are not authorized to update this profile"}),
                    403,
                )

            display_names = (
                await db.collection("users").document("display_names").get()
            ).to_dict() or {}
            display_names[user_id] = data["displayName"]
            await db.collection("users").document("display_names").set(display_names)

            profile = (
                await db.collection("users").document(user_id).get()
            ).to_dict() or {}
            profile["about"] = data["about"]
            await db.collection("users").document(user_id).set(profile)

            return jsonify({"message": "Profile updated successfully"})

        except Exception as e:
            return (
                jsonify({"error": "Failed to update profile", "details": str(e)}),
                500,
            )


@bp.route("/start_protocol", methods=["POST"])
@authenticate
async def start_protocol() -> Response:
    user_id = await get_user_id()
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(request.args.get("study_id"))
    doc_ref_dict = (await doc_ref.get()).to_dict() or {}
    statuses = doc_ref_dict["status"]

    if statuses[user_id] == "":
        if message := check_conditions(doc_ref_dict, user_id):
            return jsonify({"error": message}), 400

        statuses[user_id] = "ready to begin sfkit"
        await doc_ref.set({"status": statuses}, merge=True)

    if "" in statuses.values():
        logger.info("Not all participants are ready.")
    elif statuses[user_id] == "ready to begin sfkit":
        await update_status_and_start_setup(
            doc_ref, doc_ref_dict, request.args.get("study_id")
        )

    return jsonify({"message": "Protocol started successfully"}), 200


@bp.route("/send_message", methods=["POST"])
@authenticate
async def send_message() -> Response:
    db = current_app.config["DATABASE"]

    data = await request.get_json()
    study_id = data.get("study_id")
    message = data.get("message")
    sender = data.get("sender")

    if not message or not sender or not study_id:
        return jsonify({"error": "Message, sender, and study_id are required"}), 400

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()

    new_message = {
        "sender": sender,
        "time": datetime.now().strftime("%m/%d/%Y %H:%M"),
        "body": message,
    }

    doc_ref_dict["messages"] = doc_ref_dict.get("messages", []) + [new_message]
    await doc_ref.set(doc_ref_dict)

    return jsonify({"message": "Message sent successfully", "data": new_message}), 200


@bp.route("/download_results_file", methods=("GET",))
@authenticate
async def download_results_file() -> Response:
    user_id = await get_user_id()

    db = current_app.config["DATABASE"]
    study_id = request.args.get("study_id")

    # verify study_id for added security against path-injection
    if not is_valid_uuid(study_id):
        return jsonify({"error": "Invalid study_id"}), 400

    doc_ref_dict = (await db.collection("studies").document(study_id).get()).to_dict()
    role: str = str(doc_ref_dict["participants"].index(user_id))

    base = "src/static/results"
    shared = f"{study_id}/p{role}"
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
        return await send_file(
            io.BytesIO("Failed to get results".encode()),
            attachment_filename="result.txt",
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
    return await send_file(
        zip_buffer,
        attachment_filename=f"{study_id}_p{role}_results.zip",
        mimetype="application/zip",
        as_attachment=True,
    )


@bp.route("/fetch_plot_file", methods=["POST"])
@authenticate
async def fetch_plot_file() -> Response:  # sourcery skip: use-named-expression
    user_id = await get_user_id()
    study_id = (await request.get_json()).get("study_id")
    db = current_app.config["DATABASE"]
    doc_ref = await db.collection("studies").document(study_id).get()
    doc_ref_dict = doc_ref.to_dict()
    role: str = str(doc_ref_dict["participants"].index(user_id))

    plot_name = "manhattan" if "GWAS" in doc_ref_dict["study_type"] else "pca_plot"

    plot = download_blob_to_bytes("sfkit", f"{study_id}/p{role}/{plot_name}.png")
    if plot:
        return await send_file(
            io.BytesIO(plot),
            mimetype="image/png",
            as_attachment=True,
            attachment_filename=f"{plot_name}.png",
        )
    else:
        return "File not found", 404


@bp.route("/update_notifications", methods=["POST"])
@authenticate
async def update_notifications() -> Response:
    user_id = await get_user_id()
    data = await request.get_json()

    await remove_notification(data.get("notification"), user_id)
    await add_notification(data.get("notification"), user_id, "old_notifications")
    return Response(status=200)
