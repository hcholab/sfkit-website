import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from google.cloud.firestore import AsyncClient, AsyncDocumentReference
from quart import Blueprint, current_app, request
from werkzeug.exceptions import BadRequest, Conflict, Forbidden

from src.api_utils import TERRA_ID_KEY
from src.auth import get_cli_user
from src.utils import constants, custom_logging
from src.utils.api_functions import process_parameter, process_status, process_task
from src.utils.google_cloud.google_cloud_storage import upload_blob_from_file
from src.utils.studies_functions import setup_gcp, submit_terra_workflow

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("cli", __name__, url_prefix="/api")


@dataclass
class Study:
    id: str
    dict: Dict[str, Any]
    ref: AsyncDocumentReference
    user_id: str
    role: str


async def _get_user():
    user = await get_cli_user(request)
    user_id = user[TERRA_ID_KEY] if constants.TERRA else user["username"]
    if type(user_id) != str:
        raise Conflict("Invalid user ID")

    return user, user_id


async def _get_user_study_ids():
    user, user_id = await _get_user()

    if constants.TERRA:
        study_id = request.args.get("study_id")
    else:
        study_id = user["study_id"]

    if study_id is None:
        raise BadRequest("Missing study ID")
    elif type(study_id) != str:
        raise Conflict("Invalid study ID")

    return user_id, study_id


def _get_db() -> AsyncClient:
    return current_app.config["DATABASE"]


async def _get_study():
    user_id, study_id = await _get_user_study_ids()

    study_ref = _get_db().collection("studies").document(study_id)
    doc = await study_ref.get()
    study = doc.to_dict()
    PARTICIPANTS_KEY = "participants"
    if not study or PARTICIPANTS_KEY in study and user_id not in study[PARTICIPANTS_KEY]:
        raise Forbidden()
    elif PARTICIPANTS_KEY not in study:
        raise Conflict("study has no participants")
    role = str(study[PARTICIPANTS_KEY].index(user_id))

    return Study(study_id, study, study_ref, user_id, role)


@bp.route("/upload_file", methods=["POST"])
async def upload_file() -> Tuple[dict, int]:
    study: Study = await _get_study()
    files = await request.files
    logger.info(f"upload_file: {study.id}, request: {request}, request.files: {files}")

    file = files.get("file", None)
    if not file:
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


@bp.route("/get_study_options", methods=["GET"])
async def get_study_options() -> Tuple[dict, int]:
    _, username = await _get_user()

    auth_keys_doc = await _get_db().collection("users").document("auth_keys").get()
    auth_keys = auth_keys_doc.to_dict() or {}

    options = [value | {"auth_key": key} for key, value in auth_keys.items() if username == value["username"]]

    return {"options": options}, 200


@bp.route("/get_username", methods=["GET"])
async def get_username() -> Tuple[dict, int]:
    _, username = await _get_user()
    return {"username": username}, 200


@bp.route("/update_firestore", methods=["GET"])
async def update_firestore() -> Tuple[dict, int]:
    try:
        _, parameter = request.args.get("msg", "").split("::")
    except:
        raise BadRequest("msg must be in the format 'update_firestore::parameter=value'")

    study = await _get_study()

    try:
        gcp_project = str(study.dict["personal_parameters"][study.user_id]["GCP_PROJECT"]["value"])
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
            study.dict,
            gcp_project,
            study.role,
        )
    elif parameter.startswith("task="):
        return await process_task(db, study.user_id, parameter, study.ref)
    else:
        return await process_parameter(db, study.user_id, parameter, study.ref)


@bp.route("/create_cp0", methods=["POST", "GET"])  # TODO: Use only POST
async def create_cp0() -> Tuple[dict, int]:
    study = await _get_study()

    if constants.TERRA:
        await submit_terra_workflow(study.id, "0")
    else:
        asyncio.create_task(setup_gcp(study.ref, "0"))

    return {}, 200
