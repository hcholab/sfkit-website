import os
from threading import Thread
from typing import Tuple

from flask import Blueprint, current_app, request
from google.cloud import firestore
from werkzeug import Request

from src.studies import setup_gcp
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, create_instance_name
from src.utils.google_cloud.google_cloud_storage import upload_blob

bp = Blueprint("api", __name__)


@bp.route("/upload_file", methods=["POST"])
def upload_file() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    study_title = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["study_title"]
    study_title = study_title.replace(" ", "").lower()

    print(f"upload_file: {study_title}, request: {request}, request.files: {request.files}")

    file = request.files["file"]
    # check if file is valid
    if not file:
        print("no file")
        return {"error": "no file"}, 400

    print(f"filename: {file.filename}")

    if "manhattan" in str(file.filename):
        file_path = f"src/static/images/{study_title}_manhattan.png"
    else:
        dir_path = f"results/{study_title}"
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, str(file.filename))

    file.save(file_path)
    print(f"saved file {file.filename} to {file_path}")

    # upload file to google cloud storage
    if "manhattan" in str(file.filename):
        upload_blob("sfkit", file_path, f"{study_title}/manhattan.png")
    elif str(file.filename) == "pos.txt":
        upload_blob("sfkit", file_path, f"{study_title}/pos.txt")
    else:
        upload_blob("sfkit", file_path, f"{study_title}/result.txt")

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
        status = parameter.split("=")[1]
        update_status(db.transaction(), doc_ref, username, status)
        if "Finished protocol" in status and doc_ref_dict["setup_configuration"] == "website":
            if doc_ref_dict["personal_parameters"][username]["DELETE_VM"]["value"] == "Yes":
                Thread(target=delete_instance, args=(study_title, doc_ref_dict, gcp_project, role)).start()
            else:
                Thread(target=stop_instance, args=(study_title, doc_ref_dict, gcp_project, role)).start()
    else:
        name, value = parameter.split("=")
        doc_ref_dict = doc_ref.get().to_dict()
        if name in doc_ref_dict["personal_parameters"][username]:
            doc_ref_dict["personal_parameters"][username][name]["value"] = value
        elif name in doc_ref_dict["parameters"]:
            doc_ref_dict["parameters"][name]["value"] = value
        else:
            print(f"parameter {name} not found in {study_title}")
            return {"error": f"parameter {name} not found in {study_title}"}, 400
        doc_ref.set(doc_ref_dict)

    return {}, 200


@firestore.transactional
def update_status(transaction, doc_ref, username, status):
    doc_ref_dict: dict = doc_ref.get(transaction=transaction).to_dict()
    doc_ref_dict["status"][username] = status
    transaction.update(doc_ref, doc_ref_dict)


def delete_instance(study_title, doc_ref_dict, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_title, gcp_project)
    gcloudCompute.delete_instance(create_instance_name(doc_ref_dict["title"], role))


def stop_instance(study_title, doc_ref_dict, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_title, gcp_project)
    gcloudCompute.stop_instance(create_instance_name(doc_ref_dict["title"], role))


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


def verify_authorization_header(request: Request, authenticate_user: bool = True) -> str:
    auth_key = request.headers.get("Authorization")
    if not auth_key:
        print("no authorization header")
        return ""

    doc = current_app.config["DATABASE"].collection("users").document("auth_keys").get().to_dict().get(auth_key)
    if not doc:
        print("invalid authorization key")
        return ""

    return auth_key
