from google.cloud import firestore
from quart import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import BadRequest

from src.auth import authenticate, get_user_id
from src.utils import constants, custom_logging
from src.utils.generic_functions import add_notification
from src.utils.studies_functions import email, make_auth_key

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("participants", __name__, url_prefix="/api")


@bp.route("/invite_participant", methods=["POST"])
@authenticate
async def invite_participant() -> Response:
    try:
        data: dict = await request.json
        study_id = data.get("study_id") or ""
        inviter = data.get("inviter_id") or ""
        invitee = data.get("invitee_email") or ""
        message = data.get("message", "") or ""

        db: firestore.AsyncClient = current_app.config["DATABASE"]
        display_names = (await db.collection("users").document("display_names").get()).to_dict() or {}
        inviter_name = display_names.get(inviter, inviter)

        doc_ref = db.collection("studies").document(study_id)
        study_dict = (await doc_ref.get()).to_dict() or {}
        study_title = study_dict["title"]

        if await email(inviter_name, invitee, message, study_title) >= 400:
            raise BadRequest("Failed to send email")

        study_dict["invited_participants"].append(invitee)
        await doc_ref.set(
            {"invited_participants": study_dict["invited_participants"]},
            merge=True,
        )

        return jsonify({"message": "Invitation sent successfully"})
    except Exception as e:
        logger.error(f"Failed to send invitation: {e}")
        raise BadRequest("Failed to send invitation")


@bp.route("/accept_invitation", methods=["POST"])
@authenticate
async def accept_invitation() -> Response:
    db: firestore.AsyncClient = current_app.config["DATABASE"]

    study_id = request.args.get("study_id")
    user_id = await get_user_id()

    if not study_id or not user_id:
        raise BadRequest("Invalid input")

    user_doc = await db.collection("users").document(user_id).get()
    user_email = (user_doc.to_dict() or {}).get("email")

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict() or {}

    if user_email not in doc_ref_dict.get("invited_participants", []):
        raise BadRequest("User not invited to this study")

    doc_ref_dict["invited_participants"].remove(user_email)

    await _add_participant(doc_ref, doc_ref_dict, study_id, user_id)
    await add_notification(f"You have accepted the invitation to {doc_ref_dict['title']}", user_id)
    return jsonify({"message": "Invitation accepted successfully"})


@bp.route("/remove_participant", methods=["POST"])
@authenticate
async def remove_participant() -> Response:
    db = current_app.config["DATABASE"]

    data = await request.get_json()
    study_id = data.get("study_id")
    user_id = data.get("userId")

    if not study_id or not user_id:
        raise BadRequest("Invalid input")

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()

    if user_id not in doc_ref_dict.get("participants", []):
        raise BadRequest("User not a participant in this study")

    doc_ref_dict["participants"].remove(user_id)
    del doc_ref_dict["personal_parameters"][user_id]
    del doc_ref_dict["status"][user_id]

    await doc_ref.set(doc_ref_dict)

    await add_notification(f"You have been removed from {doc_ref_dict['title']}", user_id)
    return jsonify({"message": "Participant removed successfully"})


@bp.route("/approve_join_study", methods=["POST"])
@authenticate
async def approve_join_study() -> Response:
    db = current_app.config["DATABASE"]

    study_id = request.args.get("study_id") or ""
    user_id = request.args.get("userId") or ""

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()

    if user_id in doc_ref_dict.get("requested_participants", {}):
        del doc_ref_dict["requested_participants"][user_id]
    else:
        raise BadRequest("User not requested to join this study")

    await _add_participant(doc_ref, doc_ref_dict, study_id, user_id)
    await add_notification(f"You have been accepted to {doc_ref_dict['title']}", user_id=user_id)
    return jsonify({"message": "User has been approved to join the study"})


@bp.route("/request_join_study", methods=["POST"])
@authenticate
async def request_join_study() -> Response:
    try:
        study_id = request.args.get("study_id")
        data = await request.get_json()
        message: str = data.get("message", "")

        db = current_app.config["DATABASE"]
        doc_ref = db.collection("studies").document(study_id)
        doc_ref_dict: dict = (await doc_ref.get()).to_dict()

        if not doc_ref_dict:
            raise BadRequest("Study does not exist")

        user_id = await get_user_id()

        requested_participants = doc_ref_dict.get("requested_participants", {})
        requested_participants[user_id] = message

        await doc_ref.set(
            {"requested_participants": requested_participants},
            merge=True,
        )

        return jsonify({"message": "Join study request submitted successfully"})

    except Exception as e:
        logger.error(f"Failed to request to join study: {e}")
        raise BadRequest("Failed to request to join study")


async def _add_participant(doc_ref, doc_ref_dict, study_id, user_id):
    doc_ref_dict["participants"] = doc_ref_dict.get("participants", []) + [user_id]
    doc_ref_dict["personal_parameters"] = doc_ref_dict.get("personal_parameters", {}) | {
        user_id: constants.default_user_parameters(doc_ref_dict["study_type"])
    }
    doc_ref_dict["status"] = doc_ref_dict.get("status", {}) | {user_id: ""}
    await doc_ref.set(doc_ref_dict)

    await make_auth_key(study_id, user_id)
