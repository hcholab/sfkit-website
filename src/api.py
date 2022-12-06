from typing import Tuple

from flask import Blueprint, current_app, request
from werkzeug import Request

from src.studies import setup_gcp

bp = Blueprint("api", __name__)


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
    title = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["study_title"]

    msg: str = str(request.args.get("msg"))
    _, parameter = msg.split("::")
    doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    if parameter.startswith("status"):
        status = parameter.split("=")[1]
        doc_ref_dict["status"][username] = status
    else:
        name, value = parameter.split("=")
        if name in doc_ref_dict["personal_parameters"][username]:
            doc_ref_dict["personal_parameters"][username][name]["value"] = value
        elif name in doc_ref_dict["parameters"]:
            doc_ref_dict["parameters"][name]["value"] = value
        else:
            print(f"parameter {name} not found in {title}")
            return {"error": f"parameter {name} not found in {title}"}, 400
    doc_ref.set(doc_ref_dict)

    return {}, 200


@bp.route("/create_cp0", methods=["GET"])
def create_cp0() -> Tuple[dict, int]:
    auth_key = verify_authorization_header(request)
    if not auth_key:
        return {"error": "unauthorized"}, 401

    db = current_app.config["DATABASE"]
    study_title = db.collection("users").document("auth_keys").get().to_dict()[auth_key]["study_title"]

    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    if not doc_ref_dict:
        return {"error": f"study {study_title} not found"}, 400

    setup_gcp(doc_ref, "0")

    return {}, 200


def verify_authorization_header(request: Request, authenticate_user: bool = True) -> str:
    print("verifying authorization token")

    auth_key = request.headers.get("Authorization")
    if not auth_key:
        print("no authorization header")
        return ""

    doc = current_app.config["DATABASE"].collection("users").document("auth_keys").get().to_dict().get(auth_key)
    if not doc:
        print("invalid authorization key")
        return ""

    return auth_key
