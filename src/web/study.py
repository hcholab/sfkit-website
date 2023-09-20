from datetime import datetime
from multiprocessing import Process

from flask import Blueprint, Response, current_app, jsonify, request
from google.cloud import firestore

from src.auth import authenticate, verify_token
from src.utils import constants, custom_logging
from src.utils.google_cloud.google_cloud_compute import (
    GoogleCloudCompute,
    format_instance_name,
)
from src.utils.studies_functions import (
    make_auth_key,
    valid_study_title,
)


logger = custom_logging.setup_logging(__name__)
bp = Blueprint("study", __name__, url_prefix="/api")


@bp.route("/study", methods=["GET"])
@authenticate
def study() -> Response:
    title = request.args.get("title")
    db = current_app.config["DATABASE"]

    try:
        study = db.collection("studies").document(title).get().to_dict()
    except Exception as e:
        return jsonify({"error": "Failed to fetch study", "details": str(e)})

    try:
        display_names = (
            db.collection("users").document("display_names").get().to_dict() or {}
        )
    except Exception as e:
        return jsonify({"error": "Failed to fetch display names", "details": str(e)})

    study["owner_name"] = display_names.get(study["owner"], study["owner"])
    study["display_names"] = {
        participant: display_names.get(participant, participant)
        for participant in study["participants"]
        + list(study["requested_participants"].keys())
        + study["invited_participants"]
    }

    return jsonify({"study": study})


@bp.route("/restart_study", methods=["GET"])
@authenticate
def restart_study() -> Response:
    study_title = request.args.get("title")
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    processes = []
    for role, v in enumerate(doc_ref_dict["participants"]):
        participant = doc_ref_dict["personal_parameters"][v]
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            google_cloud_compute = GoogleCloudCompute(study_title, gcp_project)
            for instance in google_cloud_compute.list_instances():
                if instance == format_instance_name(
                    google_cloud_compute.study_title, str(role)
                ):
                    p = Process(
                        target=google_cloud_compute.delete_instance, args=(instance,)
                    )
                    p.start()
                    processes.append(p)

            p = Process(target=google_cloud_compute.delete_firewall, args=(None,))
            p.start()
            processes.append(p)
    for p in processes:
        p.join()
    logger.info("Successfully Deleted gcp instances and firewalls")

    for participant in doc_ref_dict["participants"]:
        doc_ref_dict["status"][participant] = (
            "ready to begin protocol" if participant == "Broad" else ""
        )
        doc_ref_dict["personal_parameters"][participant]["PUBLIC_KEY"]["value"] = ""
        doc_ref_dict["personal_parameters"][participant]["IP_ADDRESS"]["value"] = ""
    doc_ref_dict["tasks"] = {}

    doc_ref.set(doc_ref_dict)

    return jsonify({"message": "Successfully restarted study"})


@bp.route("/create_study", methods=["POST"])
@authenticate
def create_study() -> Response:
    data = request.json
    study_type = data.get("study_type")
    setup_configuration = data.get("setup_configuration")
    title = data.get("title")
    demo = data.get("demo_study")
    user_id = data.get("user_id")
    private_study = data.get("private_study")
    description = data.get("description")
    study_information = data.get("study_information")

    logger.info(
        f"Creating study of type {study_type} with setup configuration {setup_configuration}"
    )

    (cleaned_study_title, response, status_code) = valid_study_title(
        title, study_type, setup_configuration
    )
    if not cleaned_study_title:
        return response, status_code

    doc_ref = (
        current_app.config["DATABASE"]
        .collection("studies")
        .document(cleaned_study_title)
    )
    doc_ref.set(
        {
            "title": cleaned_study_title,
            "raw_title": title,
            "study_type": study_type,
            "setup_configuration": setup_configuration,
            "private": private_study or demo,
            "demo": demo,
            "description": description,
            "study_information": study_information,
            "owner": user_id,
            "created": datetime.now(),
            "participants": ["Broad", user_id],
            "status": {"Broad": "ready to begin protocol", user_id: ""},
            "parameters": constants.SHARED_PARAMETERS[study_type],
            "advanced_parameters": constants.ADVANCED_PARAMETERS[study_type],
            "personal_parameters": {
                "Broad": constants.broad_user_parameters(),
                user_id: constants.default_user_parameters(study_type, demo),
            },
            "requested_participants": {},
            "invited_participants": [],
        }
    )
    make_auth_key(cleaned_study_title, "Broad")

    return jsonify(
        {"message": "Study created successfully", "study_title": cleaned_study_title}
    )


@bp.route("/delete_study", methods=["DELETE"])
@authenticate
def delete_study() -> Response:
    study_title = request.args.get("title")
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    processes = []
    for participant in doc_ref_dict["personal_parameters"].values():
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            google_cloud_compute = GoogleCloudCompute(study_title, gcp_project)
            p = Process(target=google_cloud_compute.delete_everything)
            p.start()
            processes.append(p)

    for p in processes:
        p.join()
    logger.info("Successfully deleted GCP instances and other related resources")

    for participant in doc_ref_dict["personal_parameters"].values():
        if (auth_key := participant.get("AUTH_KEY").get("value")) != "":
            doc_ref_auth_keys = db.collection("users").document("auth_keys")
            doc_ref_auth_keys.update({auth_key: firestore.DELETE_FIELD})

    db.collection("deleted_studies").document(
        f"{study_title}-" + str(doc_ref_dict["created"]).replace(" ", "").lower()
    ).set(doc_ref_dict)

    doc_ref.delete()

    return jsonify({"message": "Successfully deleted study"})


@bp.route("/study_information", methods=["POST"])
@authenticate
def study_information() -> Response:
    try:
        study_title = request.args.get("title")
        data = request.json
        description = data.get("description")
        study_information = data.get("information")

        doc_ref = (
            current_app.config["DATABASE"].collection("studies").document(study_title)
        )
        doc_ref.set(
            {
                "description": description,
                "study_information": study_information,
            },
            merge=True,
        )

        return jsonify({"message": "Study information updated successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to update study information: {e}")
        return jsonify({"error": "Failed to update study information"}), 500


@bp.route("/parameters", methods=["POST"])
@authenticate
def parameters() -> Response:
    try:
        user_id = verify_token(request.headers.get("Authorization").split(" ")[1])[
            "sub"
        ]
        study_title = request.args.get("title")
        data = request.json
        db = current_app.config["DATABASE"]
        doc_ref = db.collection("studies").document(study_title)
        doc_ref_dict = doc_ref.get().to_dict()

        for p, value in data.items():
            if p in doc_ref_dict["parameters"]:
                doc_ref_dict["parameters"][p]["value"] = value
            elif p in doc_ref_dict["advanced_parameters"]:
                doc_ref_dict["advanced_parameters"][p]["value"] = value
            elif "NUM_INDS" in p:
                participant = p.split("NUM_INDS")[1]
                doc_ref_dict["personal_parameters"][participant]["NUM_INDS"][
                    "value"
                ] = value
            elif p in doc_ref_dict["personal_parameters"][user_id]:
                doc_ref_dict["personal_parameters"][user_id][p]["value"] = value
                if p == "NUM_CPUS":
                    doc_ref_dict["personal_parameters"][user_id]["NUM_THREADS"][
                        "value"
                    ] = value

        doc_ref.set(doc_ref_dict, merge=True)

        return jsonify({"message": "Parameters updated successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to update parameters: {e}")
        return jsonify({"error": "Failed to update parameters"}), 500
