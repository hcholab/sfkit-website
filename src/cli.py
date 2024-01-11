import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from google.cloud import firestore
from quart import Blueprint, current_app, request
from werkzeug.exceptions import (BadRequest, Conflict, Forbidden, NotFound,
                                 Unauthorized)

from src.auth import get_cli_user
from src.utils import constants, custom_logging
from src.utils.api_functions import (process_parameter, process_status,
                                     process_task)
from src.utils.google_cloud.google_cloud_storage import upload_blob_from_file
from src.utils.studies_functions import setup_gcp

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("cli", __name__, url_prefix="/api")


@dataclass
class Study:
    id: str
    dict: Dict[str, Any]
    ref: firestore.AsyncDocumentReference
    user_id: str
    role: str


async def _get_user_study_ids():
    user = await get_cli_user(request)
    if not user:
        raise Unauthorized()

    if constants.TERRA:
        user_id, study_id = user["id"], request.args.get("study_id")
    else:
        user_id, study_id = user["username"], user["study_id"]

    if type(user_id) != str:
        raise Conflict("Invalid user ID")

    if study_id is None:
        raise BadRequest("Missing study ID")
    elif type(study_id) != str:
        raise Conflict("Invalid study ID")

    return user_id, study_id


def _get_db() -> firestore.AsyncClient:
    return current_app.config["DATABASE"]


async def _get_study():
    user_id, study_id = await _get_user_study_ids()

    study_ref = _get_db().collection("studies").document(study_id)
    doc = await study_ref.get()
    study = doc.to_dict()
    PARTICIPANTS_KEY = "participants"
    if not study:
        raise NotFound()
    elif not user_id in study[PARTICIPANTS_KEY]:
        raise Forbidden()

    role = str(study[PARTICIPANTS_KEY].index(user_id))

    return Study(study_id, study, study_ref, user_id, role)


@bp.route("/upload_file", methods=["POST"])
async def upload_file() -> Tuple[dict, int]:
    study = await _get_study()
    logger.info(
        f"upload_file: {study.id}, request: {request}, request.files: {request.files}"
    )

    file = (await request.files).get("file", None)
    if not file:
        logger.info("no file")
        raise BadRequest("no file")
    logger.info(f"filename: {file.filename}")

    if "manhattan" in str(file.filename):
        file_path = f"{study.id}/p{study.role}/manhattan.png"
    elif "pca_plot" in str(file.filename):
        file_path = f"{study.id}/p{study.role}/pca_plot.png"
    elif str(file.filename) == "pos.txt":
        file_path = f"{study.id}/pos.txt"
    else:
        file_path = f"{study.id}/p{study.role}/result.txt"

    upload_blob_from_file("sfkit", file, file_path)
    logger.info(f"uploaded file {file.filename} to {file_path}")

    return {}, 200


@bp.route("/get_doc_ref_dict", methods=["GET"])
async def get_doc_ref_dict() -> Tuple[dict, int]:
    study = await _get_study()
    return study.dict, 200


@bp.route("/get_username", methods=["GET"])
async def get_username() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        raise Unauthorized()

    username, _ = _get_user_study_ids(user)
    return {"username": username}, 200


@bp.route("/update_firestore", methods=["GET"])
async def update_firestore() -> Tuple[dict, int]:
    msg = request.args.get("msg")
    if msg is None:
        raise BadRequest("msg is required")
    try:
        _, parameter = msg.split("::")
    except:
        raise BadRequest(
            "msg must be in the format 'update_firestore::parameter=value'"
        )

    study = await _get_study()

    try:
        gcp_project = str(
            study["personal_parameters"][study.user_id]["GCP_PROJECT"]["value"]
        )
    except KeyError:
        raise Conflict("GCP_PROJECT not found")

    db = _get_db()
    if parameter.startswith("status="):
        return await process_status(
            db,
            study.user_id,
            study.id,
            parameter,
            study.ref,
            study,
            gcp_project,
            study.role,
        )
    elif parameter.startswith("task="):
        return await process_task(db, study.user_id, parameter, study.ref)
    else:
        return await process_parameter(db, study.user_id, parameter, study.ref)


@bp.route("/create_cp0", methods=["GET"])
async def create_cp0() -> Tuple[dict, int]:
    study = await _get_study()

    # Create a new task for the setup_gcp function
    asyncio.create_task(setup_gcp(study.ref, "0"))

    return {}, 200
