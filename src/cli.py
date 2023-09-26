import asyncio
from threading import Thread
from typing import Tuple

from quart import Blueprint, current_app, request

from src.auth import authenticate
from src.utils import custom_logging
from src.utils.api_functions import (
    process_parameter,
    process_status,
    process_task,
    verify_authorization_header,
)
from src.utils.google_cloud.google_cloud_storage import upload_blob_from_file
from src.utils.studies_functions import setup_gcp

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("cli", __name__, url_prefix="/api")


@bp.route("/upload_file", methods=["POST"])
@authenticate
async def upload_file() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    user_dict = (
        await db.collection("users").document("auth_keys").get().to_dict()[auth_key]
    )
    study_title = user_dict["study_title"]
    username = user_dict["username"]

    logger.info(
        f"upload_file: {study_title}, request: {request}, request.files: {request.files}"
    )

    file = request.files.get("file", None)

    if not file:
        logger.info("no file")
        return {"error": "no file"}, 400

    logger.info(f"filename: {file.filename}")

    doc_ref_dict: dict = (
        await db.collection("studies").document(study_title).get().to_dict()
    )
    role: str = str(doc_ref_dict["participants"].index(username))

    if "manhattan" in str(file.filename):
        file_path = f"{study_title}/p{role}/manhattan.png"
    elif "pca_plot" in str(file.filename):
        file_path = f"{study_title}/p{role}/pca_plot.png"
    elif str(file.filename) == "pos.txt":
        file_path = f"{study_title}/pos.txt"
    else:
        file_path = f"{study_title}/p{role}/result.txt"

    upload_blob_from_file("sfkit", file, file_path)
    logger.info(f"uploaded file {file.filename} to {file_path}")

    return {}, 200


@bp.route("/get_doc_ref_dict", methods=["GET"])
@authenticate
async def get_doc_ref_dict() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    study_title = (
        await db.collection("users")
        .document("auth_keys")
        .get()
        .to_dict()[auth_key]["study_title"]
    )

    doc_ref_dict: dict = (
        await db.collection("studies").document(study_title).get().to_dict()
    )

    return doc_ref_dict, 200


@bp.route("/get_username", methods=["GET"])
@authenticate
async def get_username() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    username = (
        await db.collection("users")
        .document("auth_keys")
        .get()
        .to_dict()[auth_key]["username"]
    )

    return {"username": username}, 200


@bp.route("/update_firestore", methods=["GET"])
@authenticate
async def update_firestore() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    username = (
        await db.collection("users")
        .document("auth_keys")
        .get()
        .to_dict()[auth_key]["username"]
    )
    study_title = (
        await db.collection("users")
        .document("auth_keys")
        .get()
        .to_dict()[auth_key]["study_title"]
    )

    msg: str = str(request.args.get("msg"))
    _, parameter = msg.split("::")
    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = await doc_ref.get().to_dict()
    gcp_project: str = doc_ref_dict["personal_parameters"][username]["GCP_PROJECT"][
        "value"
    ]
    role: str = str(doc_ref_dict["participants"].index(username))

    if parameter.startswith("status"):
        return process_status(
            db,
            username,
            study_title,
            parameter,
            doc_ref,
            doc_ref_dict,
            gcp_project,
            role,
        )
    elif parameter.startswith("task"):
        return process_task(db, username, parameter, doc_ref)
    else:
        return process_parameter(db, username, parameter, doc_ref)


@bp.route("/create_cp0", methods=["GET"])
@authenticate
async def create_cp0() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    study_title = (
        await db.collection("users")
        .document("auth_keys")
        .get()
        .to_dict()[auth_key]["study_title"]
    )

    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title)
    doc_ref_dict: dict = await doc_ref.get().to_dict()

    if not doc_ref_dict:
        return {"error": f"study {study_title} not found"}, 400

    # Create a new task for the setup_gcp function
    asyncio.create_task(setup_gcp(doc_ref, "0"))

    return {}, 200