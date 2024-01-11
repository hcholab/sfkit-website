import asyncio
from typing import Tuple

from quart import Blueprint, current_app, request

from src.auth import get_cli_user
from src.utils import custom_logging, constants
from src.utils.api_functions import process_parameter, process_status, process_task
from src.utils.google_cloud.google_cloud_storage import upload_blob_from_file
from src.utils.studies_functions import setup_gcp

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("cli", __name__, url_prefix="/api")


def _get_username_study_id(user):
    if constants.TERRA:
        return user["id"], request.args.get("study_id")
    else:
        return user["username"], user["study_id"]


@bp.route("/upload_file", methods=["POST"])
async def upload_file() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    username, study_id = _get_username_study_id(user)

    logger.info(
        f"upload_file: {study_id}, request: {request}, request.files: {request.files}"
    )

    file = (await request.files).get("file", None)

    if not file:
        logger.info("no file")
        return {"error": "no file"}, 400

    logger.info(f"filename: {file.filename}")

    db = current_app.config["DATABASE"]
    doc_ref_dict: dict = (
        await db.collection("studies").document(study_id).get()
    ).to_dict()
    role: str = str(doc_ref_dict["participants"].index(username))

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

    _, study_id = _get_username_study_id(user)

    db = current_app.config["DATABASE"]
    study: dict = (await db.collection("studies").document(study_id).get()).to_dict()
    return study, 200


@bp.route("/get_username", methods=["GET"])
async def get_username() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    username, _ = _get_username_study_id(user)

    return {"username": username}, 200


@bp.route("/update_firestore", methods=["GET"])
async def update_firestore() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    username, study_id = _get_username_study_id(user)

    msg: str = str(request.args.get("msg"))
    _, parameter = msg.split("::")

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()
    gcp_project: str = doc_ref_dict["personal_parameters"][username]["GCP_PROJECT"][
        "value"
    ]
    role: str = str(doc_ref_dict["participants"].index(username))

    if parameter.startswith("status"):
        return await process_status(
            db,
            username,
            study_id,
            parameter,
            doc_ref,
            doc_ref_dict,
            gcp_project,
            role,
        )
    elif parameter.startswith("task"):
        return await process_task(db, username, parameter, doc_ref)
    else:
        return await process_parameter(db, username, parameter, doc_ref)


@bp.route("/create_cp0", methods=["GET"])
async def create_cp0() -> Tuple[dict, int]:
    user = await get_cli_user(request)
    if not user:
        return {"error": "unauthorized"}, 401

    _, study_id = _get_username_study_id(user)

    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()

    if not doc_ref_dict:
        return {"error": f"study {study_id} not found"}, 400

    # Create a new task for the setup_gcp function
    asyncio.create_task(setup_gcp(doc_ref, "0"))

    return {}, 200
