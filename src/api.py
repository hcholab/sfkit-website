import os
from threading import Thread
from typing import Tuple

from flask import Blueprint, current_app, request

from src.studies import setup_gcp
from src.utils.api_functions import process_parameter, process_status, process_task, verify_authorization_header
from src.utils.google_cloud.google_cloud_storage import upload_blob

bp = Blueprint("api", __name__)


@bp.route("/upload_file", methods=["POST"])
def upload_file() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    user_dict = db.collection("users").document("auth_keys").get().to_dict()[auth_key]
    study_title = user_dict["study_title"].replace(" ", "").lower()
    username = user_dict["username"]

    print(f"upload_file: {study_title}, request: {request}, request.files: {request.files}")

    file = request.files["file"]

    if not file:
        print("no file")
        return {"error": "no file"}, 400

    print(f"filename: {file.filename}")

    doc_ref_dict: dict = db.collection("studies").document(study_title).get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(username))

    if "manhattan" in str(file.filename):
        file_path = f"{study_title}/p{role}/manhattan.png"
    elif "pca_plot" in str(file.filename):
        file_path = f"{study_title}/p{role}/pca_plot.png"
    elif str(file.filename) == "pos.txt":
        file_path = f"{study_title}/pos.txt"
    else:
        file_path = f"{study_title}/p{role}/result.txt"

    # upload file to google cloud storage
    upload_blob("sfkit", file, file_path)
    print(f"uploaded file {file.filename} to {file_path}")

    return {}, 200


@bp.route("/get_doc_ref_dict", methods=["GET"])
def get_doc_ref_dict() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    study_title = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["study_title"]

    doc_ref_dict: dict = db.collection("studies").document(study_title.replace(" ", "").lower()).get().to_dict()

    return doc_ref_dict, 200


@bp.route("/get_username", methods=["GET"])
def get_username() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    username = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["username"]

    return {"username": username}, 200


@bp.route("/update_firestore", methods=["GET"])
def update_firestore() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    username = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["username"]
    study_title = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["study_title"]
    study_title = study_title.replace(" ", "").lower()

    msg: str = str(request.args.get("msg"))
    _, parameter = msg.split("::")
    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()
    gcp_project: str = doc_ref_dict["personal_parameters"][username]["GCP_PROJECT"]["value"]
    role: str = str(doc_ref_dict["participants"].index(username))

    if parameter.startswith("status"):
        return process_status(db, username, study_title, parameter, doc_ref, doc_ref_dict, gcp_project, role)
    elif parameter.startswith("task"):
        return process_task(db, username, parameter, doc_ref)
    else:
        return process_parameter(db, username, parameter, doc_ref)


@bp.route("/create_cp0", methods=["GET"])
def create_cp0() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    study_title = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["study_title"]
    study_title = study_title.replace(" ", "").lower()

    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    if not doc_ref_dict:
        return {"error": f"study {study_title} not found"}, 400

    Thread(target=setup_gcp, args=(doc_ref, "0")).start()

    return {}, 200
