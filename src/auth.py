import datetime
import functools
import json
import secrets
import string

import flask
from firebase_admin import auth as firebase_auth
from flask import (
    Blueprint,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from google.auth import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from requests import post
from requests.exceptions import HTTPError
from werkzeug import Response

from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.helper_functions import flash, redirect_with_flash

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_logged_in_user() -> None:
    g.flash = flask.request.cookies.get("flash")
    try:
        # extract jwt for user from session cookie
        session_cookie = flask.request.cookies.get("session")
        user_dict = firebase_auth.verify_session_cookie(
            session_cookie, check_revoked=True
        )
        g.user = {"id": user_dict["email"]}
    except Exception as e:
        if "session cookie provided: None" not in str(e):
            print(f'Error logging in user: "{e}"')
        g.user = None
    else:
        try:
            # for use in accessing firebase from the frontend.  See https://firebase.google.com/docs/auth/admin/create-custom-tokens
            g.custom_token = firebase_auth.create_custom_token(user_dict["uid"]).decode(
                "utf-8"
            )
        except Exception as e:
            print(f"Error creating custom token: {e}")


@bp.after_app_request
def remove_old_flash_messages(response: flask.Response) -> flask.Response:
    if flask.request.cookies.get("flash"):
        response.set_cookie("flash", "")
    return response


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        return view(**kwargs) if g.user else redirect(url_for("auth.login"))

    return wrapped_view


@bp.route("/register", methods=("GET", "POST"))
def register() -> Response:
    if request.method == "GET":
        return make_response(render_template("auth/register.html"))

    email = request.form["email"]
    password = request.form["password"]
    password_check = request.form["password_check"]

    if password_check != password:
        return redirect_with_flash(
            location="auth.register",
            message="Passwords do not match. Please double-check and try again.",
        )
    try:
        firebase_auth.create_user(email=email, password=password)
        gcloudIAM = GoogleCloudIAM()
        gcloudIAM.give_cloud_build_view_permissions(email)

        return update_session_cookie_and_return_to_index(email, password)
    except Exception as e:
        if ("EMAIL_EXISTS") in str(e):
            return redirect_with_flash(
                location="auth.register",
                message="This email is already registered.  Please either Log In or use a different email.",
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

    email = request.form["email"]
    password = request.form["password"]

    try:
        return update_session_cookie_and_return_to_index(email, password)
    except Exception as e:
        if ("INVALID_PASSWORD") in str(e):
            return redirect_with_flash(
                location="auth.login", message="Invalid password. Please try again."
            )
        elif ("USER_NOT_FOUND") in str(e):
            return redirect_with_flash(
                location="auth.login",
                message="No user found with that email. Please try again.",
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


@bp.route("/callback", methods=("POST",))
def login_with_google_callback() -> Response:
    try:
        decoded_token = id_token.verify_oauth2_token(
            request.form["credential"],
            google_requests.Request(),
            "419003787216-rcif34r976a9qm3818qgeqed7c582od6.apps.googleusercontent.com",
        )
    except Exception as e:
        return redirect_with_flash(
            location="gwas.index", message="Invalid Google account.", error=str(e)
        )

    token = jwt.decode(
        request.form["credential"], verify=False
    )  # verify = False because we already verified the token separately

    print(f"Decoded token: {decoded_token}")
    print(f"Token: {token}")

    rand_temp_password = "".join(
        secrets.choice(string.ascii_lowercase) for _ in range(16)
    )

    try:
        firebase_auth.get_user_by_email(token["email"])
        firebase_auth.update_user(
            uid=token["email"], email=token["email"], password=rand_temp_password
        )
    except firebase_auth.UserNotFoundError:
        firebase_auth.create_user(
            uid=token["email"], email=token["email"], password=rand_temp_password
        )
        gcloudIAM = GoogleCloudIAM()
        gcloudIAM.give_cloud_build_view_permissions(token["email"])

    return update_session_cookie_and_return_to_index(token["email"], rand_temp_password)


def update_session_cookie_and_return_to_index(email, password):
    expires_in = datetime.timedelta(days=1)

    user = sign_in_with_email_and_password(email, password)
    session_cookie = firebase_auth.create_session_cookie(
        user["idToken"], expires_in=expires_in
    )
    response = redirect(url_for("gwas.index"))
    response.set_cookie(
        "session",
        session_cookie,
        expires=datetime.datetime.now() + expires_in,
        httponly=True,
        secure=True,
    )

    return response


def sign_in_with_email_and_password(email, password):
    with open("fbconfig.json") as f:
        config = json.load(f)
    api_key = config["apiKey"]
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}".format(
        api_key
    )
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
    request_object = post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()


def raise_detailed_error(request_object):
    try:
        request_object.raise_for_status()
    except HTTPError as e:
        raise HTTPError(e, request_object.text) from e
