import functools
import typing

import flask
from firebase_admin import auth as firebase_auth
from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, url_for
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from werkzeug import Response

from src.utils import constants, logging
from src.utils.auth_functions import create_user, update_user
from src.utils.generic_functions import redirect_with_flash
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.google_cloud.google_cloud_secret_manager import get_firebase_api_key

logger = logging.setup_logging(__name__)

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_logged_in_user() -> None:
    g.flash = flask.request.cookies.get("flash")
    try:
        # extract jwt for user from session cookie
        session_cookie = flask.request.cookies.get("session")
        user_dict = firebase_auth.verify_session_cookie(session_cookie, check_revoked=True)
        username: str = user_dict["email"].split("@")[0] if "sfkit.org" in user_dict["email"] else user_dict["email"]
        g.user = {"id": username}
        display_names = current_app.config["DATABASE"].collection("users").document("display_names").get().to_dict()
        g.user["display_name"] = display_names.get(g.user["id"], g.user["id"])
    except Exception as e:
        no_user_strings = [
            "session cookie provided: None",
            "session cookie must be a non-empty string",
            "The default Firebase app does not exist. Make sure to initialize the SDK by calling initialize_app().",
        ]
        if all(s not in str(e) for s in no_user_strings):
            logger.error(f'Error logging in user: "{e}"')
        g.user = None
    else:
        try:
            # for use in accessing firebase from the frontend.  See https://firebase.google.com/docs/auth/admin/create-custom-tokens
            # this is done when dynamically updating status of a running study, and for the notification system
            g.custom_token = firebase_auth.create_custom_token(user_dict["uid"]).decode("utf-8")
            g.firebase_api_key = get_firebase_api_key()
        except Exception as e:
            logger.error(f"Error creating custom token: {e}")


@bp.after_app_request
def remove_old_flash_messages(response: flask.Response) -> flask.Response:
    if flask.request.cookies.get("flash"):
        response.set_cookie("flash", "")
    return response


def login_required(view: typing.Callable) -> typing.Callable:
    @functools.wraps(view)
    def wrapped_view(**kwargs) -> typing.Callable:
        return view(**kwargs) if g.user else redirect(url_for("auth.login", next=request.url))

    return wrapped_view


@bp.route("/register", methods=("GET", "POST"))
def register() -> Response:
    if request.method == "GET":
        return make_response(render_template("auth/register.html"))

    username = request.form["username"]
    email = f"{username}@sfkit.org" if (username and "@" not in username) else username
    password = request.form["password"]
    password_check = request.form["password_check"]

    if password_check != password:
        return redirect_with_flash(
            location="auth.register",
            message="Passwords do not match. Please double-check and try again.",
        )
    try:
        firebase_auth.create_user(email=email, password=password)
        # gcloudIAM = GoogleCloudIAM()
        # gcloudIAM.give_minimal_required_gcp_permissions(username)

        return update_user(email=email, password=password)
    except Exception as e:
        if ("EMAIL_EXISTS") in str(e):
            return redirect_with_flash(
                location="auth.register",
                message="This username is already registered.  Please either Log In or use a different username.",
            )
        else:
            return redirect_with_flash(
                location="auth.register",
                message="Error creating user.",
                error=str(e),
            )


@bp.route("/login", methods=("GET", "POST"))
def login() -> Response:
    if request.method == "GET":
        return make_response(render_template("auth/login.html"))

    username = request.form["username"]
    email = f"{username}@sfkit.org" if "@" not in username else username
    password = request.form["password"]

    try:
        return update_user(email, password, redirect_url=request.form.get("next", ""))
    except Exception as e:
        if ("INVALID_PASSWORD") in str(e):
            return redirect_with_flash(location="auth.login", message="Invalid password. Please try again.")
        elif ("USER_NOT_FOUND") in str(e):
            return redirect_with_flash(
                location="auth.login",
                message="No user found with that username. Please try again.",
            )
        else:
            return redirect_with_flash(
                location="auth.login",
                message="Error logging in. Please try again.",
                error=str(e),
            )


@bp.route("/logout")
def logout() -> Response:
    response = redirect(url_for("auth.login"))
    response.set_cookie("session", "")
    return response


@bp.route("/login_with_google_callback", methods=("POST",))
def login_with_google_callback() -> Response:
    try:
        decoded_jwt_token = id_token.verify_oauth2_token(
            request.form["credential"],
            google_requests.Request(),
            constants.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        print("in valueerror")
        return redirect_with_flash(location="studies.index", message="Invalid Google account.", error=str(e))

    user_id = decoded_jwt_token["email"]
    name = decoded_jwt_token["name"]
    redirect_url = request.form.get("next", "")

    gcloudIAM = GoogleCloudIAM()
    gcloudIAM.give_minimal_required_gcp_permissions(user_id)

    return create_user(user_id, name, redirect_url)
