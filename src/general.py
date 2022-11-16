from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for
from google.cloud.firestore_v1 import CollectionReference
from werkzeug import Response

from src.auth import login_required
from src.utils.generic_functions import add_notification, remove_notification

bp = Blueprint("general", __name__)


@bp.route("/", methods=["GET"])
@bp.route("/home", methods=["GET"])
def home() -> Response:
    return make_response(render_template("general/home.html"))


@bp.route("/workflows", methods=["GET"])
def workflows() -> Response:
    return make_response(render_template("general/workflows.html"))


@bp.route("/instructions", methods=["GET"])
def instructions() -> Response:
    return make_response(render_template("general/instructions.html"))


@bp.route("/contact", methods=["GET"])
def contact() -> Response:
    return make_response(render_template("general/contact.html"))


@bp.route("/update_notifications", methods=["POST"])
@login_required
def update_notifications() -> Response:
    remove_notification(request.data.decode("utf-8"))
    add_notification(request.data.decode("utf-8"), g.user["id"], "old_notifications")
    return Response(status=200)


@bp.route("/profile/<user_id>", methods=["GET"])
@login_required
def profile(user_id: str) -> Response:
    users_collection: CollectionReference = current_app.config["DATABASE"].collection("users")
    profile: dict = users_collection.document(user_id).get().to_dict() or {}
    display_names: dict = users_collection.document("display_names").get().to_dict() or {}

    return make_response(
        render_template(
            "general/profile.html",
            user_id=user_id,
            profile=profile,
            display_name=display_names.get(user_id, user_id),
        )
    )


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile() -> Response:
    users_collection: CollectionReference = current_app.config["DATABASE"].collection("users")
    profile: dict = users_collection.document(g.user["id"]).get().to_dict() or {}
    display_names: dict = users_collection.document("display_names").get().to_dict() or {}

    if request.method == "GET":
        return make_response(
            render_template(
                "general/edit_profile.html",
                profile=profile,
                display_name=display_names.get(g.user["id"], g.user["id"]),
            )
        )

    display_names[g.user["id"]] = request.form["display_name"]
    users_collection.document("display_names").set(display_names)

    profile["about"] = request.form["about"]
    users_collection.document(g.user["id"]).set(profile)

    return redirect(url_for("general.profile", user_id=g.user["id"]))
