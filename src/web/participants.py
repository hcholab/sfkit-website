from quart import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest

from src.api_utils import fetch_study, validate_json, validate_uuid
from src.auth import authenticate
from src.utils import constants, custom_logging
from src.utils.generic_functions import add_notification
from src.utils.schemas.invite_participant import invite_participant_schema
from src.utils.schemas.remove_participant import remove_participant_schema
from src.utils.schemas.request_join_study import request_join_study_schema
from src.utils.studies_functions import email, make_auth_key

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("participants", __name__, url_prefix="/api")


@bp.route("/invite_participant", methods=["POST"])
@authenticate
async def invite_participant(user_id) -> Response:
    data = validate_json(await request.json, schema=invite_participant_schema)
    study_id = validate_uuid(data.get("study_id")) or ""
    invitee = data.get("invitee_email") or ""
    message = data.get("message", "") or ""
    db, doc_ref, study_dict = await fetch_study(study_id, user_id)

    try:
        display_names = (await db.collection("users").document("display_names").get()).to_dict() or {}
        inviter_name = display_names.get(user_id, user_id)

        study_title = study_dict["title"]

        if await email(inviter_name, invitee, message, study_title) >= 400:
            raise BadRequest("Failed to send email")

        study_dict["invited_participants"].append(invitee)
        await doc_ref.set(
            {"invited_participants": study_dict["invited_participants"]},
            merge=True,
        )

        return jsonify({"message": "Invitation sent successfully"})
    except:
        logger.exception("Failed to send invitation")
        raise BadRequest("Failed to send invitation")


@bp.route("/accept_invitation", methods=["POST"])
@authenticate
async def accept_invitation(user_id) -> Response:
    study_id = validate_uuid(request.args.get("study_id"))
    db, doc_ref, doc_ref_dict = await fetch_study(study_id)

    user_doc = await db.collection("users").document(user_id).get()
    user_email = (user_doc.to_dict() or {}).get("email")

    if user_email not in doc_ref_dict.get("invited_participants", []):
        raise BadRequest("User not invited to this study")

    doc_ref_dict["invited_participants"].remove(user_email)

    await _add_participant(doc_ref, doc_ref_dict, study_id, user_id)
    await add_notification(f"You have accepted the invitation to {doc_ref_dict['title']}", user_id)
    return jsonify({"message": "Invitation accepted successfully"})


@bp.route("/remove_participant", methods=["POST"])
@authenticate
async def remove_participant(user_id) -> Response:
    data = validate_json(await request.get_json(), schema=remove_participant_schema)
    study_id = validate_uuid(data.get("study_id"))
    target_user_id = data.get("userId") or ""

    _, doc_ref, doc_ref_dict = await fetch_study(study_id, user_id)

    if user_id != doc_ref_dict["owner"]:
        raise BadRequest("Only the owner can remove participants")

    if target_user_id not in doc_ref_dict.get("participants", []):
        raise BadRequest("User not a participant in this study")

    doc_ref_dict["participants"].remove(target_user_id)
    del doc_ref_dict["personal_parameters"][target_user_id]
    del doc_ref_dict["status"][target_user_id]

    await doc_ref.set(doc_ref_dict)

    await add_notification(f"You have been removed from {doc_ref_dict['title']}", target_user_id)
    return jsonify({"message": "Participant removed successfully"})


@bp.route("/approve_join_study", methods=["POST"])
@authenticate
async def approve_join_study(user_id) -> Response:
    study_id = validate_uuid(request.args.get("study_id")) or ""
    target_user_id = request.args.get("userId") or ""

    _, doc_ref, doc_ref_dict = await fetch_study(study_id, user_id)

    if target_user_id in doc_ref_dict.get("requested_participants", {}):
        del doc_ref_dict["requested_participants"][target_user_id]
    else:
        raise BadRequest("User not requested to join this study")

    await _add_participant(doc_ref, doc_ref_dict, study_id, target_user_id)
    await add_notification(f"You have been accepted to {doc_ref_dict['title']}", user_id=target_user_id)
    return jsonify({"message": "User has been approved to join the study"})


@bp.route("/request_join_study", methods=["POST"])
@authenticate
async def request_join_study(user_id: str) -> Response:
    try:
        study_id = validate_uuid(request.args.get("study_id"))
        data = validate_json(await request.get_json(), schema=request_join_study_schema)
        message: str = data.get("message", "")

        _, doc_ref, doc_ref_dict = await fetch_study(study_id)

        requested_participants = doc_ref_dict.get("requested_participants", {})
        requested_participants[user_id] = message

        await doc_ref.set(
            {"requested_participants": requested_participants},
            merge=True,
        )

        return jsonify({"message": "Join study request submitted successfully"})

    except:
        logger.exception("Failed to request to join study:")
        raise BadRequest("Failed to request to join study")


async def _add_participant(doc_ref, doc_ref_dict, study_id, user_id):
    doc_ref_dict["participants"] = doc_ref_dict.get("participants", []) + [user_id]
    doc_ref_dict["personal_parameters"] = doc_ref_dict.get("personal_parameters", {}) | {
        user_id: constants.default_user_parameters(doc_ref_dict["study_type"])
    }
    doc_ref_dict["status"] = doc_ref_dict.get("status", {}) | {user_id: ""}
    doc_ref_dict["tasks"] = doc_ref_dict.get("tasks", {}) | {user_id: []}
    await doc_ref.set(doc_ref_dict)

    await make_auth_key(study_id, user_id)
