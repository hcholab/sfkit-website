import asyncio
from typing import Tuple

from google.cloud import firestore
from quart import Blueprint, current_app, request

from src.auth import get_cli_user
from src.utils import constants, custom_logging
from src.utils.api_functions import process_parameter, process_status, process_task
from src.utils.google_cloud.google_cloud_storage import upload_blob_from_file
from src.utils.studies_functions import setup_gcp

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("cli", __name__, url_prefix="/api")

PARTICIPANTS_KEY = "participants"


def _get_user_study_ids(user):
    if constants.TERRA:
        return user["id"], request.args.get("study_id")
    else:
        return user["username"], user["study_id"]


def _get_db() -> firestore.AsyncClient:
    return current_app.config["DATABASE"]


async def _get_study(study_id: str):
    doc = await _get_db().collection("studies").document(study_id).get()
    return doc.to_dict()


@bp.route("/upload_file", methods=["POST"])
async def upload_file() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    user_id, study_id = _get_user_study_ids(user)

    logger.info(
        f"upload_file: {study_id}, request: {request}, request.files: {request.files}"
    )

    file = (await request.files).get("file", None)

    if not file:
        logger.info("no file")
        return {"error": "no file"}, 400

    logger.info(f"filename: {file.filename}")

    study = await _get_study(study_id)
    if not study:
        return {"error": "not found"}, 404
    elif not user_id in study[PARTICIPANTS_KEY]:
        return {"error": "forbidden"}, 403

    role = str(study[PARTICIPANTS_KEY].index(user_id))

    if "manhattan" in str(file.filename):
        file_path = f"{study_id}/p{role}/manhattan.png"
    elif "pca_plot" in str(file.filename):
        file_path = f"{study_id}/p{role}/pca_plot.png"
    elif str(file.filename) == "pos.txt":
        file_path = f"{study_id}/pos.txt"
    else:
        file_path = f"{study_id}/p{role}/result.txt"

    upload_blob_from_file("sfkit", file, file_path)
    logger.info(f"uploaded file {file.filename} to {file_path}")

    return {}, 200


@bp.route("/get_doc_ref_dict", methods=["GET"])
async def get_doc_ref_dict() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    user_id, study_id = _get_user_study_ids(user)

    study = await _get_study(study_id)
    if not study:
        return {"error": "not found"}, 404
    elif not user_id in study[PARTICIPANTS_KEY]:
        return {"error": "forbidden"}, 403

    return study, 200


@bp.route("/get_username", methods=["GET"])
async def get_username() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    username, _ = _get_user_study_ids(user)
    return {"username": username}, 200


@bp.route("/update_firestore", methods=["GET"])
async def update_firestore() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    user_id, study_id = _get_user_study_ids(user)

    msg = str(request.args.get("msg"))
    _, parameter = msg.split("::")

    db = _get_db()
    study_ref = db.collection("studies").document(study_id)
    study = (await study_ref.get()).to_dict()
    if not study:
        return {"error": "not found"}, 404
    elif not user_id in study[PARTICIPANTS_KEY]:
        return {"error": "forbidden"}, 403

    gcp_project = str(study["personal_parameters"][user_id]["GCP_PROJECT"]["value"])
    role = str(study[PARTICIPANTS_KEY].index(user_id))

    if parameter.startswith("status"):
        return await process_status(
            db,
            user_id,
            study_id,
            parameter,
            study_ref,
            study,
            gcp_project,
            role,
        )
    elif parameter.startswith("task"):
        return await process_task(db, user_id, parameter, study_ref)
    else:
        return await process_parameter(db, user_id, parameter, study_ref)


@bp.route("/create_cp0", methods=["GET"])
async def create_cp0() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    user_id, study_id = _get_user_study_ids(user)

    study_ref = _get_db().collection("studies").document(study_id)
    study = (await study_ref.get()).to_dict()
    if not study:
        return {"error": "not found"}, 404
    elif not user_id in study[PARTICIPANTS_KEY]:
        return {"error": "forbidden"}, 403

    # Create a new task for the setup_gcp function
    asyncio.create_task(setup_gcp(study_ref, "0"))

    return {}, 200
