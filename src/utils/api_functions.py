import asyncio
import time

from google.cloud import firestore
from google.cloud.firestore import AsyncClient, AsyncDocumentReference

from src.utils import custom_logging
from src.utils.generic_functions import is_create_vm
from src.utils.google_cloud.google_cloud_compute import (GoogleCloudCompute,
                                                         format_instance_name)

logger = custom_logging.setup_logging(__name__)


async def process_status(
    db: AsyncClient,
    username: str,
    study_id: str,
    parameter: str,
    doc_ref: AsyncDocumentReference,
    doc_ref_dict: dict,
    gcp_project: str,
    role: str,
):
    status = parameter.split("=")[1]
    await update_status(db.transaction(), {"username": username, "status": status, "doc_ref": doc_ref})

    is_finished_protocol = "Finished protocol" in status
    create_vm = is_create_vm(doc_ref_dict, username)
    delete_vm = doc_ref_dict["personal_parameters"][username]["DELETE_VM"]["value"] == "Yes"
    is_role_zero = role == "0"

    if is_finished_protocol:
        if create_vm and delete_vm:
            asyncio.create_task(delete_instance(study_id, gcp_project, role))
        elif create_vm or is_role_zero:
            asyncio.create_task(stop_instance(study_id, gcp_project, role))

    return {}, 200


async def process_task(db: AsyncClient, username: str, parameter: str, doc_ref: AsyncDocumentReference):
    task = parameter.split("=")[1]
    for _ in range(10):
        try:
            await update_tasks(db.transaction(), {"username": username, "task": task, "doc_ref": doc_ref})
            return {}, 200
        except:
            logger.exception("Failed to update task:")
            time.sleep(1)

    return {"error": "Failed to update task"}, 400


async def process_parameter(db: AsyncClient, username: str, parameter: str, doc_ref: AsyncDocumentReference):
    for _ in range(10):
        try:
            if await update_parameter(
                db.transaction(), {"username": username, "parameter": parameter, "doc_ref": doc_ref}
            ):
                return {}, 200
        except:
            logger.exception("Failed to update parameter:")
            time.sleep(1)

    return {"error": "Failed to update parameter"}, 400


async def update_parameter(transaction: firestore.AsyncTransaction, data: dict):
    @firestore.async_transactional
    async def transactional_update_parameter(transaction: firestore.AsyncTransaction) -> bool:
        username = data["username"]
        parameter = data["parameter"]
        doc_ref = data["doc_ref"]
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

    return await transactional_update_parameter(transaction)


async def update_status(transaction: firestore.AsyncTransaction, data: dict):
    @firestore.async_transactional
    async def transactional_update_status(transaction: firestore.AsyncTransaction) -> bool:
        username = data["username"]
        status = data["status"]
        doc_ref = data["doc_ref"]
        doc_ref_dict: dict = (await doc_ref.get(transaction=transaction)).to_dict()
        if "status" in doc_ref_dict:
            doc_ref_dict["status"][username] = status
        else:
            logger.info(f"Status not found for user {username}")
            return False
        transaction.update(doc_ref, doc_ref_dict)
        return True

    return await transactional_update_status(transaction)


async def update_tasks(transaction: firestore.AsyncTransaction, data: dict):
    @firestore.async_transactional
    async def transactional_update_tasks(transaction: firestore.AsyncTransaction) -> bool:
        username = data["username"]
        task = data["task"]
        doc_ref = data["doc_ref"]
        doc_ref_dict: dict = (await doc_ref.get(transaction=transaction)).to_dict()
        doc_ref_dict.setdefault("tasks", {}).setdefault(username, [])

        if task not in doc_ref_dict["tasks"][username]:
            doc_ref_dict["tasks"][username].append(task)
        else:
            logger.info(f"Task {task} already exists for user {username}")
            return False

        transaction.update(doc_ref, doc_ref_dict)
        return True

    return await transactional_update_tasks(transaction)


async def delete_instance(study_id, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_id, gcp_project)
    gcloudCompute.delete_instance(format_instance_name(study_id, role))


async def stop_instance(study_id, gcp_project, role):
    gcloudCompute = GoogleCloudCompute(study_id, gcp_project)
    gcloudCompute.stop_instance(format_instance_name(study_id, role))
