import base64

from flask import Blueprint, current_app, g, make_response, render_template, request
from werkzeug import Response

from src.auth import login_required
from src.gwas import validate_data_for_cp0
from src.utils import constants
from src.utils.generic_functions import add_notification, remove_notification
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_storage import GoogleCloudStorage
from src.utils.gwas_functions import create_instance_name, data_has_valid_files, data_has_valid_size

bp = Blueprint("general", __name__)


@bp.route("/", methods=["GET"])
@bp.route("/home", methods=["GET"])
def home() -> Response:
    return make_response(render_template("general/home.html"))


@bp.route("/instructions")
def instructions() -> Response:
    return make_response(render_template("general/instructions.html"))


@bp.route("/update_notifications", methods=["POST"])
@login_required
def update_notifications() -> Response:
    remove_notification(request.data.decode("utf-8"))
    add_notification(request.data.decode("utf-8"), g.user["id"], "old_notifications")
    return Response(status=200)


@bp.route("/all_notifications", methods=["GET"])
@login_required
def all_notifications() -> Response:
    doc_ref_dict = current_app.config["DATABASE"].collection("users").document(g.user["id"]).get().to_dict()
    return make_response(
        render_template(
            "general/all_notifications.html",
            new_notifications=doc_ref_dict.get("notifications", []),
            old_notifications=doc_ref_dict.get("old_notifications", []),
        )
    )


# for the pubsub
@bp.route("/", methods=["POST"])
def index() -> tuple[str, int]:
    envelope = request.get_json()
    if not envelope:
        return fail()

    if not isinstance(envelope, dict) or "message" not in envelope:
        return fail()

    pubsub_message = envelope.get("message")
    if not isinstance(pubsub_message, dict) or "data" not in pubsub_message:
        return fail()

    publishTime = pubsub_message.get("publishTime")
    message = base64.b64decode(pubsub_message["data"])
    msg = message.decode("utf-8").strip()
    print(f"Pub/Sub message decoded: {msg}")

    try:
        if msg.startswith("update_firestore"):
            _, parameter, title, email = msg.split("::")
            doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
            doc_ref_dict: dict = doc_ref.get().to_dict()
            if parameter.startswith("public_key"):
                public_key = parameter.split("=")[1]
                doc_ref_dict["personal_parameters"][email]["PUBLIC_KEY"]["value"] = public_key
            elif parameter.startswith("status"):
                status = parameter.split("=")[1]
                doc_ref_dict["status"][email] = [status]
            elif parameter.startswith("data_hash"):
                data_hash = parameter.split("=")[1]
                doc_ref_dict["personal_parameters"][email]["DATA_HASH"]["value"] = data_hash
            doc_ref.set(doc_ref_dict)
        # elif msg.startswith("cp0_validate_data"):
        #     title = msg.split("::")[1]
        #     doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
        #     doc_ref_dict = doc_ref.get().to_dict()
        #     validate_data_for_cp0(study_title=title, doc_ref_dict=doc_ref_dict)
        elif msg.startswith("run_protocol_for_cp0"):
            _, title, user_id = msg.split("::")
            doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
            doc_ref_dict = doc_ref.get().to_dict()
            role: str = str(doc_ref_dict["participants"].index(user_id) + 1)

            gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
            # copy parameters to parameter files
            gcloudStorage.copy_parameters_to_bucket(title, role)
            # give user read access to storage buckets for parameter files
            gcloudStorage.add_bucket_iam_member(constants.PARAMETER_BUCKET, "roles/storage.objectViewer", user_id)

            gcloudCompute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
            instance: str = create_instance_name(title, "0")
            vm_parameters = doc_ref_dict["personal_parameters"][user_id]
            gcloudCompute.setup_instance(
                constants.SERVER_ZONE,
                instance,
                "0",
                {"key": "data_path", "value": "secure-gwas-data0"},
                vm_parameters["NUM_CPUS"]["value"],
                boot_disk_size=vm_parameters["BOOT_DISK_SIZE"]["value"],
            )
        else:
            [study_title, rest] = msg.split("-secure-gwas", maxsplit=1)
            [role, content] = rest.split("-", maxsplit=1)

            if role == "0" and ("validate" in content or "GWAS Completed!" in content):
                google_cloud_compute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
                google_cloud_compute.stop_instance(constants.SERVER_ZONE, create_instance_name(study_title, role))
            else:
                doc_ref = (
                    current_app.config["DATABASE"].collection("studies").document(study_title.replace(" ", "").lower())
                )
                doc_ref_dict = doc_ref.get().to_dict()
                statuses = doc_ref_dict.get("status")
                user_id = doc_ref_dict.get("participants")[int(role) - 1]  # type: ignore

                if "validate" in content:
                    [_, size, files] = content.split("|", maxsplit=2)
                    statuses[user_id] = (  # type: ignore
                        ["not ready"]
                        if data_has_valid_size(int(size), doc_ref_dict, int(role)) and data_has_valid_files(files)
                        else ["invalid data"]
                    )

                elif content not in str(statuses.get(user_id, [])):  # type: ignore
                    statuses.get(user_id).append(f"{content} - {publishTime}")  # type: ignore
                doc_ref.set({"status": statuses}, merge=True)

                if "validate" in content or "GWAS Completed!" in content:
                    google_cloud_compute = GoogleCloudCompute(
                        doc_ref_dict.get("personal_parameters", {})
                        .get(user_id, {})
                        .get("GCP_PROJECT", {})
                        .get("value", constants.SERVER_GCP_PROJECT)
                    )
                    google_cloud_compute.stop_instance(
                        zone=constants.SERVER_ZONE,
                        instance=create_instance_name(study_title, role),
                    )
    except Exception as e:
        print(f"error processing pubsub message: {e}")
    finally:
        return ("", 204)


def fail() -> tuple[str, int]:
    msg = "Invalid Pub/Sub message received"
    print(f"error: {msg}")
    return (f"Bad Request: {msg}", 400)
