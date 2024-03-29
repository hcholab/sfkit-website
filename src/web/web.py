import asyncio
import io
import os
import zipfile
from datetime import datetime, timezone

from firebase_admin import auth as firebase_auth
from quart import Blueprint, Response, current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, Conflict, Forbidden

from src.api_utils import get_display_names, get_studies, is_valid_uuid
from src.auth import authenticate, authenticate_on_terra, get_user_email, get_user_id
from src.utils import constants, custom_logging
from src.utils.generic_functions import add_notification, remove_notification
from src.utils.google_cloud.google_cloud_secret_manager import get_firebase_api_key
from src.utils.google_cloud.google_cloud_storage import download_blob_to_bytes
from src.utils.studies_functions import check_conditions, update_status_and_start_setup

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("web", __name__, url_prefix="/api")


@bp.route("/createCustomToken", methods=["POST"])
@authenticate
async def create_custom_token() -> Response:
    user_id = await get_user_id()
    try:
        loop = asyncio.get_event_loop()
        custom_token = await loop.run_in_executor(None, firebase_auth.create_custom_token, user_id)
        return jsonify(
            {
                "customToken": custom_token.decode("utf-8"),
                "firebaseApiKey": await get_firebase_api_key(),
                "firebaseProjectId": constants.FIREBASE_PROJECT_ID,
                "firestoreDatabaseId": constants.FIRESTORE_DATABASE,
            }
        )

    except Exception as e:
        logger.error(f"Failed to create custom token: {e}")
        raise BadRequest("Error creating custom token")


@bp.route("/public_studies", methods=["GET"])
@authenticate_on_terra
async def public_studies() -> Response:
    try:
        public_studies = await get_studies(private_filter=False)
        display_names = await get_display_names()
    except Exception as e:
        logger.error(f"Failed to fetch public studies: {e}")
        raise BadRequest("Failed to fetch public studies")

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
        logger.error(f"Failed to fetch my studies: {e}")
        raise BadRequest("Failed to fetch my studies")

    for study in my_studies:
        study["owner_name"] = display_names.get(study["owner"], study["owner"])

    user_id = await get_user_id()
    email = await get_user_email(user_id)
    my_studies = [
        study for study in my_studies if user_id in study["participants"] or email in study["invited_participants"]
    ]
    return jsonify({"studies": my_studies})


@bp.route("/profile/<user_id>", methods=["GET", "POST"])
@authenticate
async def profile(user_id: str = "") -> Response:
    db = current_app.config["DATABASE"]

    if not user_id:
        user_id = await get_user_id()

    if request.method == "GET":
        try:
            display_names = (await db.collection("users").document("display_names").get()).to_dict() or {}
            profile = (await db.collection("users").document(user_id).get()).to_dict() or {}

            profile["displayName"] = display_names.get(user_id, user_id)
            return jsonify({"profile": profile})

        except Exception as e:
            logger.error(f"Failed to fetch profile: {e}")
            raise BadRequest("Failed to fetch profile")

    else:  # "POST" request
        try:
            data = await request.get_json()
            logged_in_user_id = await get_user_id()

            if logged_in_user_id != user_id:
                raise Forbidden("You are not authorized to update this profile")

            display_names = (await db.collection("users").document("display_names").get()).to_dict() or {}
            display_names[user_id] = data["displayName"]
            await db.collection("users").document("display_names").set(display_names)

            profile = (await db.collection("users").document(user_id).get()).to_dict() or {}
            profile["about"] = data["about"]
            await db.collection("users").document(user_id).set(profile)

            return jsonify({"message": "Profile updated successfully"})

        except Exception as e:
            logger.error(f"Failed to update profile: {e}")
            raise BadRequest("Failed to update profile")


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
            raise Conflict(message)

        statuses[user_id] = "ready to begin sfkit"
        await doc_ref.set({"status": statuses}, merge=True)

    if "" in statuses.values():
        logger.info("Not all participants are ready.")
    elif statuses[user_id] == "ready to begin sfkit":
        await update_status_and_start_setup(doc_ref, doc_ref_dict, request.args.get("study_id"))

    return jsonify({"message": "Protocol started successfully"})


@bp.route("/send_message", methods=["POST"])
@authenticate
async def send_message() -> Response:
    user_id = await get_user_id()

    db = current_app.config["DATABASE"]

    data = await request.get_json()
    study_id = data.get("study_id")
    message = data.get("message")

    if not message or not study_id:
        raise BadRequest("Missing required fields")

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()

    new_message = {
        "sender": user_id,
        "time": datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M"),
        "body": message,
    }

    doc_ref_dict["messages"] = doc_ref_dict.get("messages", []) + [new_message]
    await doc_ref.set(doc_ref_dict)

    return jsonify({"message": "Message sent successfully", "data": new_message})


@bp.route("/download_results_file", methods=("GET",))
@authenticate
async def download_results_file() -> Response:
    user_id = await get_user_id()

    db = current_app.config["DATABASE"]
    study_id = request.args.get("study_id")

    if not is_valid_uuid(study_id):
        raise BadRequest("Invalid study_id")

    doc_ref_dict = (await db.collection("studies").document(study_id).get()).to_dict()
    role: str = str(doc_ref_dict["participants"].index(user_id))

    shared = f"{study_id}/p{role}"

    result_name = "result.txt"
    result_file = download_blob_to_bytes(constants.RESULTS_BUCKET, os.path.join(shared, result_name))

    plot_name = ("manhattan" if "GWAS" in doc_ref_dict["study_type"] else "pca_plot") + ".png"
    plot_file = download_blob_to_bytes(
        constants.RESULTS_BUCKET,
        os.path.join(shared, plot_name),
    )

    if not (result_file and plot_file):
        return await send_file(
            io.BytesIO("Failed to get results".encode()),
            attachment_filename="result.txt",
            mimetype="text/plain",
            as_attachment=True,
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(result_name, result_file)
        zip_file.writestr(plot_name, plot_file)

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

    plot = download_blob_to_bytes(constants.RESULTS_BUCKET, f"{study_id}/p{role}/{plot_name}.png")
    if plot:
        return await send_file(
            io.BytesIO(plot),
            mimetype="image/png",
            as_attachment=True,
            attachment_filename=f"{plot_name}.png",
        )
    else:
        raise BadRequest("Failed to fetch plot")


@bp.route("/update_notifications", methods=["POST"])
@authenticate
async def update_notifications() -> Response:
    user_id = await get_user_id()
    data = await request.get_json()

    await remove_notification(data.get("notification"), user_id)
    await add_notification(data.get("notification"), user_id, "old_notifications")
    return Response(status=200)
