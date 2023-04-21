import time
from threading import Thread

from flask import current_app
from google.cloud import firestore
from werkzeug import Request

from src.utils import logging
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, create_instance_name

logger = logging.setup_logging(__name__)


def process_status(db, username, study_title, parameter, doc_ref, doc_ref_dict, gcp_project, role):
    status = parameter.split("=")[1]
    update_status(db.transaction(), doc_ref, username, status)
    if "Finished protocol" in status and doc_ref_dict["setup_configuration"] == "website":
        if doc_ref_dict["personal_parameters"][username]["DELETE_VM"]["value"] == "Yes":
            Thread(target=delete_instance, args=(study_title, doc_ref_dict, gcp_project, role)).start()
        else:
            Thread(target=stop_instance, args=(study_title, doc_ref_dict, gcp_project, role)).start()

    return {}, 200


def process_task(db, username, parameter, doc_ref):
    task = parameter.split("=")[1]
    for _ in range(10):
        try:
            update_tasks(db.transaction(), doc_ref, username, task)
            return {}, 200
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            time.sleep(1)

    return {"error": "Failed to update task"}, 400


def process_parameter(db, username, parameter, doc_ref):
    for _ in range(10):
        try:
            if update_parameter(db.transaction(), username, parameter, doc_ref):
                return {}, 200
        except Exception as e:
            logger.error(f"Failed to update parameter: {e}")
            time.sleep(1)

    return {"error": "Failed to update parameter"}, 400


@firestore.transactional
def update_parameter(transaction, username, parameter, doc_ref) -> bool:
    name, value = parameter.split("=")
    doc_ref_dict = doc_ref.get(transaction=transaction).to_dict()
    if name in doc_ref_dict["personal_parameters"][username]:
        doc_ref_dict["personal_parameters"][username][name]["value"] = value
    elif name in doc_ref_dict["parameters"]:
        doc_ref_dict["parameters"][name]["value"] = value
    else:
        logger.info(f"Parameter {name} not found")
        return False
    transaction.update(doc_ref, doc_ref_dict)
    return True


@firestore.transactional
def update_status(transaction, doc_ref, username, status) -> None:
    doc_ref_dict: dict = doc_ref.get(transaction=transaction).to_dict()
    doc_ref_dict["status"][username] = status
    transaction.update(doc_ref, doc_ref_dict)


@firestore.transactional
def update_tasks(transaction, doc_ref, username, task) -> None:
    doc_ref_dict: dict = doc_ref.get(transaction=transaction).to_dict()

    doc_ref_dict.setdefault("tasks", {}).setdefault(username, [])

    if task not in doc_ref_dict["tasks"][username]:
        doc_ref_dict["tasks"][username].append(task)

    transaction.update(doc_ref, doc_ref_dict)


def delete_instance(study_title, doc_ref_dict, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_title, gcp_project)
    gcloudCompute.delete_instance(create_instance_name(doc_ref_dict["title"], role))


def stop_instance(study_title, doc_ref_dict, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_title, gcp_project)
    gcloudCompute.stop_instance(create_instance_name(doc_ref_dict["title"], role))


def verify_authorization_header(request: Request, authenticate_user: bool = True) -> str:
    auth_key = request.headers.get("Authorization")
    if not auth_key:
        logger.info("no authorization key provided")
        return ""

    doc = current_app.config["DATABASE"].collection("users").document("auth_keys").get().to_dict().get(auth_key)
    if not doc:
        logger.info("invalid authorization key")
        return ""

    return auth_key
