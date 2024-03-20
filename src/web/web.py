import asyncio
import io
import os
import zipfile
from datetime import datetime, timezone

from firebase_admin import auth as firebase_auth
from quart import Blueprint, Response, current_app, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, Conflict, Forbidden

from src.api_utils import fetch_study, get_display_names, get_studies, validate_json, validate_uuid
from src.auth import authenticate, authenticate_on_terra, get_user_email
from src.utils import constants, custom_logging
from src.utils.generic_functions import add_notification, remove_notification
from src.utils.google_cloud.google_cloud_secret_manager import get_firebase_api_key
from src.utils.google_cloud.google_cloud_storage import download_blob_to_bytes
from src.utils.schemas.profile import profile_schema
from src.utils.schemas.send_message import send_message_schema
from src.utils.schemas.update_notifications import update_notifications_schema
from src.utils.studies_functions import check_conditions, update_status_and_start_setup

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("web", __name__, url_prefix="/api")


@bp.route("/createCustomToken", methods=["POST"])
@authenticate
async def create_custom_token(user_id) -> Response:
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
async def public_studies(user_id="") -> Response:
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
async def my_studies(user_id) -> Response:
    try:
        my_studies = await get_studies()
        display_names = await get_display_names()
    except Exception as e:
        logger.error(f"Failed to fetch my studies: {e}")
        raise BadRequest("Failed to fetch my studies")

    for study in my_studies:
        study["owner_name"] = display_names.get(study["owner"], study["owner"])

    email = await get_user_email(user_id)
    my_studies = [
        study for study in my_studies if user_id in study["participants"] or email in study["invited_participants"]
    ]
    return jsonify({"studies": my_studies})


@bp.route("/profile/<target_user_id>", methods=["GET", "POST"])
@authenticate
async def profile(user_id: str, target_user_id: str = "") -> Response:
    db = current_app.config["DATABASE"]
    display_names = (await db.collection("users").document("display_names").get()).to_dict() or {}
    profile = (await db.collection("users").document(target_user_id).get()).to_dict() or {}

    if request.method == "GET":
        try:
            profile["displayName"] = display_names.get(target_user_id, target_user_id)
            profile = {key: profile[key] for key in ["about", "displayName", "email"] if key in profile}
            return jsonify({"profile": profile})
        except Exception as e:
            logger.error(f"Failed to fetch profile: {e}")
            raise BadRequest("Failed to fetch profile")
    else:
        if user_id != target_user_id:
            raise Forbidden("You are not authorized to update this profile")

        data = validate_json(await request.get_json(), schema=profile_schema)
        try:
            display_names[target_user_id] = data["displayName"]
            await db.collection("users").document("display_names").set(display_names)

            profile["about"] = data["about"]
            await db.collection("users").document(target_user_id).set(profile)

            return jsonify({"message": "Profile updated successfully"})
        except Exception as e:
            logger.error(f"Failed to update profile: {e}")
            raise BadRequest("Failed to update profile")


@bp.route("/start_protocol", methods=["POST"])
@authenticate
async def start_protocol(user_id) -> Response:
    study_id = validate_uuid(request.args.get("study_id"))
    _, doc_ref, doc_ref_dict = await fetch_study(study_id, user_id)
    statuses = doc_ref_dict["status"]

    if statuses[user_id] == "":
        if message := check_conditions(doc_ref_dict, user_id):
            raise Conflict(message)

        statuses[user_id] = "ready to begin sfkit"
        await doc_ref.set({"status": statuses}, merge=True)

    if "" in statuses.values():
        logger.info("Not all participants are ready.")
    elif statuses[user_id] == "ready to begin sfkit":
        await update_status_and_start_setup(doc_ref, doc_ref_dict, study_id)

    return jsonify({"message": "Protocol started successfully"})


@bp.route("/send_message", methods=["POST"])
@authenticate
async def send_message(user_id) -> Response:
    data = validate_json(await request.get_json(), schema=send_message_schema)
    study_id = validate_uuid(data.get("study_id"))
    message = data.get("message")

    if not message or not study_id:
        raise BadRequest("Missing required fields")

    _, doc_ref, doc_ref_dict = await fetch_study(study_id, user_id)

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
async def download_results_file(user_id) -> Response:
    study_id = validate_uuid(request.args.get("study_id"))
    _, _, doc_ref_dict = await fetch_study(study_id, user_id)

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
async def fetch_plot_file(user_id) -> Response:
    study_id = validate_uuid((await request.get_json()).get("study_id"))
    _, _, doc_ref_dict = await fetch_study(study_id, user_id)
    role: str = str(doc_ref_dict["participants"].index(user_id))

    plot_name = "manhattan" if "GWAS" in doc_ref_dict["study_type"] else "pca_plot"

    if plot := download_blob_to_bytes(constants.RESULTS_BUCKET, f"{study_id}/p{role}/{plot_name}.png"):
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
async def update_notifications(user_id) -> Response:
    data = validate_json(await request.get_json(), schema=update_notifications_schema)

    await remove_notification(data.get("notification", ""), user_id)
    await add_notification(data.get("notification", ""), user_id, "old_notifications")
    return Response(status=200)
