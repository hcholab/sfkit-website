import asyncio
import time

from google.cloud import firestore

from src.utils import custom_logging
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, format_instance_name

logger = custom_logging.setup_logging(__name__)


async def process_status(username, study_id, parameter, doc_ref, doc_ref_dict, gcp_project, role):
    status = parameter.split("=")[1]
    await update_status({"username": username, "status": status, "doc_ref": doc_ref})

    is_finished_protocol = "Finished protocol" in status
    is_website_setup = doc_ref_dict["setup_configuration"] == "website"
    is_delete_vm_yes = doc_ref_dict["personal_parameters"][username]["DELETE_VM"]["value"] == "Yes"
    is_role_zero = role == "0"

    if is_finished_protocol:
        if is_website_setup and is_delete_vm_yes:
            asyncio.create_task(delete_instance(study_id, gcp_project, role))
        elif is_website_setup or is_role_zero:
            asyncio.create_task(stop_instance(study_id, gcp_project, role))

    return {}, 200


async def process_task(username, parameter, doc_ref):
    task = parameter.split("=")[1]
    for _ in range(10):
        try:
            await update_tasks({"username": username, "task": task, "doc_ref": doc_ref})
            return {}, 200
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            time.sleep(1)

    return {"error": "Failed to update task"}, 400


async def process_parameter(username, parameter, doc_ref):
    for _ in range(10):
        try:
            if await update_parameter({"username": username, "parameter": parameter, "doc_ref": doc_ref}):
                return {}, 200
        except Exception as e:
            logger.error(f"Failed to update parameter: {e}")
            time.sleep(1)

    return {"error": "Failed to update parameter"}, 400


@firestore.async_transactional
async def update_parameter(transaction) -> bool:
    username = transaction["username"]
    parameter = transaction["parameter"]
    doc_ref = transaction["doc_ref"]
    name, value = parameter.split("=")
    doc_ref_dict: dict = (await doc_ref.get(transaction=transaction)).to_dict()
    if name in doc_ref_dict["personal_parameters"][username]:
        doc_ref_dict["personal_parameters"][username][name]["value"] = value
    elif name in doc_ref_dict["parameters"]:
        doc_ref_dict["parameters"][name]["value"] = value
    else:
        logger.info(f"Parameter {name} not found")
        return False
    transaction.update(doc_ref, doc_ref_dict)
    return True


@firestore.async_transactional
async def update_status(transaction) -> bool:
    username = transaction["username"]
    status = transaction["status"]
    doc_ref = transaction["doc_ref"]
    doc_ref_dict: dict = (await doc_ref.get(transaction=transaction)).to_dict()
    if "status" in doc_ref_dict:
        doc_ref_dict["status"][username] = status
    else:
        logger.info(f"Status not found for user {username}")
        return False
    transaction.update(doc_ref, doc_ref_dict)
    return True


@firestore.async_transactional
async def update_tasks(transaction) -> bool:
    username = transaction["username"]
    task = transaction["task"]
    doc_ref = transaction["doc_ref"]
    doc_ref_dict: dict = (await doc_ref.get(transaction=transaction)).to_dict()
    doc_ref_dict.setdefault("tasks", {}).setdefault(username, [])

    if task not in doc_ref_dict["tasks"][username]:
        doc_ref_dict["tasks"][username].append(task)
    else:
        logger.info(f"Task {task} already exists for user {username}")
        return False

    transaction.update(doc_ref, doc_ref_dict)
    return True


async def delete_instance(study_id, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_id, gcp_project)
    gcloudCompute.delete_instance(format_instance_name(study_id, role))


async def stop_instance(study_id, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_id, gcp_project)
    gcloudCompute.stop_instance(format_instance_name(study_id, role))
