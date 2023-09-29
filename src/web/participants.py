from google.cloud import firestore
from quart import Blueprint, Response, current_app, jsonify, request

from src.auth import authenticate, verify_token
from src.utils import constants, custom_logging
from src.utils.generic_functions import add_notification
from src.utils.studies_functions import email

logger = custom_logging.setup_logging(__name__)
bp = Blueprint("participants", __name__, url_prefix="/api")


@bp.route("/invite_participant", methods=["POST"])
@authenticate
async def invite_participant() -> Response:
    try:
        data = await request.json
        study_id = data.get("study_id")
        inviter = data.get("inviter_id")
        invitee = data.get("invitee_email")
        message = data.get("message", "")

        db: firestore.AsyncClient = current_app.config["DATABASE"]
        display_names = (await db.collection("users").document("display_names").get()).to_dict()
        inviter_name = display_names.get(inviter, inviter)

        doc_ref = db.collection("studies").document(study_id)
        study_dict = (await doc_ref.get()).to_dict()
        study_title = study_dict["title"]

        if await email(inviter_name, invitee, message, study_title) >= 400:
            return jsonify({"error": "Email failed to send"}), 400

        study_dict["invited_participants"].append(invitee)
        await doc_ref.set(
            {"invited_participants": study_dict["invited_participants"]},
            merge=True,
        )

        return jsonify({"message": "Invitation sent successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to send invitation: {e}")
        return jsonify({"error": "Failed to send invitation"}), 500


@bp.route("/remove_participant", methods=["POST"])
@authenticate
async def remove_participant() -> Response:
    db = current_app.config["DATABASE"]

    data = await request.get_json()
    study_id = data.get("study_id")
    user_id = data.get("userId")

    if not study_id or not user_id:
        return jsonify({"error": "Invalid input"}), 400

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = await doc_ref.get().to_dict()

    # Check if the user is a participant in the study
    if user_id not in doc_ref_dict.get("participants", []):
        return jsonify({"error": "User is not a participant in this study"}), 400

    doc_ref_dict["participants"].remove(user_id)
    del doc_ref_dict["personal_parameters"][user_id]
    del doc_ref_dict["status"][user_id]

    await doc_ref.set(doc_ref_dict)

    add_notification(f"You have been removed from {doc_ref_dict['title']}", user_id)
    return jsonify({"message": "Participant removed successfully"}), 200


@bp.route("/approve_join_study", methods=["POST"])
@authenticate
async def approve_join_study() -> Response:
    db = current_app.config["DATABASE"]

    study_id = request.args.get("study_id")
    user_id = request.args.get("userId")

    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = await doc_ref.get().to_dict()

    if user_id in doc_ref_dict.get("requested_participants", {}):
        del doc_ref_dict["requested_participants"][user_id]
    else:
        return jsonify({"error": "User not in requested participants"}), 400

    doc_ref_dict["participants"] = doc_ref_dict.get("participants", []) + [user_id]
    doc_ref_dict["personal_parameters"] = doc_ref_dict.get(
        "personal_parameters", {}
    ) | {user_id: constants.default_user_parameters(doc_ref_dict["study_type"])}
    doc_ref_dict["status"] = doc_ref_dict.get("status", {}) | {user_id: ""}

    await doc_ref.set(doc_ref_dict)

    add_notification(f"You have been accepted to {doc_ref_dict['title']}", user_id=user_id)
    return jsonify({"message": "User has been approved to join the study"}), 200


@bp.route("/request_join_study", methods=["POST"])
@authenticate
async def request_join_study() -> Response:
    try:
        study_id = request.args.get("study_id")
        data = await request.get_json()
        message: str = data.get("message", "")

        db = current_app.config["DATABASE"]
        doc_ref = db.collection("studies").document(study_id)
        doc_ref_dict: dict = await doc_ref.get().to_dict()

        if not doc_ref_dict:
            return jsonify({"error": "Study not found"}), 404

        user_id = (
            await verify_token(request.headers.get("Authorization").split(" ")[1])
        )["sub"]

        requested_participants = doc_ref_dict.get("requested_participants", {})
        requested_participants[user_id] = message

        await doc_ref.set(
            {"requested_participants": requested_participants},
            merge=True,
        )

        return jsonify({"message": "Join study request submitted successfully"}), 200

    except Exception as e:
        logger.error(f"Failed to request to join study: {e}")
        return jsonify({"error": "Failed to request to join study"}), 500


# TODO: add endpoint to accept invitation to study
# @bp.route("/accept_invitation/<study_title>", methods=["GET", "POST"])
# @login_required
# async def accept_invitation(study_title: str) -> Response:
#     db = current_app.config["DATABASE"]
#     doc_ref = db.collection("studies").document(study_id)
#     doc_ref_dict: dict = await doc_ref.get().to_dict()

#     if g.user["id"] not in doc_ref_dict["invited_participants"]:
#         return redirect_with_flash(
#             url=url_for("studies.index"),
#             message="The logged in user is not invited to this study.  If you came here from an email invitation, please log in with the email address you were invited with before accepting the invitation.",
#         )

#     doc_ref_dict["invited_participants"].remove(g.user["id"])

#     await doc_ref.set(
#         {
#             "invited_participants": doc_ref_dict["invited_participants"],
#             "participants": doc_ref_dict["participants"] + [g.user["id"]],
#             "personal_parameters": doc_ref_dict["personal_parameters"]
#             | {
#                 g.user["id"]: constants.default_user_parameters(
#                     doc_ref_dict["study_type"]
#                 )
#             },
#             "status": doc_ref_dict["status"] | {g.user["id"]: ""},
#         },
#         merge=True,
#     )

#     return redirect(url_for("studies.study", study_title=study_title))
