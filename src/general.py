import base64
from threading import Thread

from flask import Blueprint, current_app, g, make_response, render_template, request
from werkzeug import Response

from src.auth import login_required
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
# @bp.route("/", methods=["POST"])
# def index() -> tuple[str, int]:
#     envelope = request.get_json()

#     if not envelope or not isinstance(envelope, dict) or "message" not in envelope:
#         return fail()

#     pubsub_message = envelope.get("message")
#     if not isinstance(pubsub_message, dict) or "data" not in pubsub_message:
#         return fail()

#     publishTime: str = str(pubsub_message.get("publishTime"))
#     msg = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
#     print(f"Pub/Sub message decoded: {msg}")

#     try:
#         if msg.startswith("update_firestore"):
#             update_firestore(msg)
#         elif msg.startswith("run_protocol_for_cp0"):
#             _, title = msg.split("::")
#             doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
#             thread = Thread(target=run_protocol_for_cp0, args=(title, doc_ref))
#             thread.start()  # separate thread so can return a response right away
#         else:
#             process_pubsub_from_website_workflow(publishTime, msg)
#             # thread = Thread(target=process_pubsub_from_website_workflow, args=(publishTime, msg))
#             # thread.start()
#     except Exception as e:
#         print(f"error processing pubsub message: {e}")
#     finally:
#         return ("", 204)


# def process_pubsub_from_website_workflow(publish_time: str, msg: str) -> None:
#     [study_title, rest] = msg.split("-secure-gwas", maxsplit=1)
#     [role, content] = rest.split("-", maxsplit=1)

#     if role == "0" and ("validate" in content or "GWAS Completed!" in content):
#         google_cloud_compute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
#         google_cloud_compute.stop_instance(constants.SERVER_ZONE, create_instance_name(study_title, role))
#     else:
#         doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title.replace(" ", "").lower())
#         doc_ref_dict = doc_ref.get().to_dict()
#         statuses = doc_ref_dict.get("status")
#         user_id = doc_ref_dict.get("participants")[int(role)]  # type: ignore

#         if "validate" in content:
#             [_, size, files] = content.split("|", maxsplit=2)
#             if data_has_valid_size(int(size), doc_ref_dict, int(role)) and data_has_valid_files(files):
#                 statuses[user_id] = ["not ready"]
#             else:
#                 statuses[user_id] = ["invalid data"]

#         elif content not in str(statuses.get(user_id, [])):  # type: ignore
#             statuses.get(user_id).append(f"{content} - {publish_time}")  # type: ignore
#         doc_ref.set({"status": statuses}, merge=True)

#         if "validate" in content or "GWAS Completed!" in content:
#             google_cloud_compute = GoogleCloudCompute(
#                 doc_ref_dict.get("personal_parameters", {})
#                 .get(user_id, {})
#                 .get("GCP_PROJECT", {})
#                 .get("value", constants.SERVER_GCP_PROJECT)
#             )
#             google_cloud_compute.stop_instance(
#                 zone=constants.SERVER_ZONE,
#                 instance=create_instance_name(study_title, role),
#             )


# def update_firestore(msg: str) -> None:
#     _, parameter, title, email = msg.split("::")
#     doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
#     doc_ref_dict: dict = doc_ref.get().to_dict()

#     if parameter.startswith("status"):
#         status = parameter.split("=")[1]
#         doc_ref_dict["status"][email] = [status]
#     else:
#         name, value = parameter.split("=")
#         doc_ref_dict["personal_parameters"][email][name]["value"] = value
#     doc_ref.set(doc_ref_dict)


# def run_protocol_for_cp0(title: str, doc_ref) -> None:
#     doc_ref_dict = doc_ref.get().to_dict()

#     if doc_ref_dict["study_type"] in ["gwas", "GWAS"]:
#         gcloudCompute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
#         instance_name: str = create_instance_name(title, "0")
#         cp0_ip_address = gcloudCompute.setup_instance(
#             constants.SERVER_ZONE,
#             instance_name,
#             "0",
#             {"key": "data_path", "value": "secure-gwas-data0"},
#             startup_script="cli",
#             delete=False,
#         )
#         doc_ref_dict["personal_parameters"]["Broad"]["IP_ADDRESS"]["value"] = cp0_ip_address
#         doc_ref.set(doc_ref_dict)

#         gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
#         # copy parameters to parameter files
#         gcloudStorage.copy_parameters_to_bucket(title)
#     elif doc_ref_dict["study_type"] in ["sfgwas", "SFGWAS"]:
#         gcloudCompute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
#         instance_name: str = create_instance_name(title, "0")

#         cp0_ip_address = gcloudCompute.setup_sfgwas_instance(
#             instance_name, metadata={"key": "study_title", "value": f"{title}"}
#         )
#         doc_ref_dict["personal_parameters"]["Broad"]["IP_ADDRESS"]["value"] = cp0_ip_address
#         doc_ref.set(doc_ref_dict)

#         # cmd = "sudo apt-get install python3-pip -y && pip install sfkit && PATH=$PATH:~/.local/bin"
#         # run_ssh_command(cp0_ip_address, cmd)
#         # # run_command(instance_name, cmd)

#         # cmd = f"sfkit run_protocol --study_title {title}"
#         # run_ssh_command(cp0_ip_address, cmd)
#         # run_command(instance_name, cmd)


# def fail() -> tuple[str, int]:
#     msg = "Invalid Pub/Sub message received"
#     print(f"error: {msg}")
#     return (f"Bad Request: {msg}", 400)
