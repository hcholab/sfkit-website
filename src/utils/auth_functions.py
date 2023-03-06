import datetime
import json
import random
import secrets
import string

from firebase_admin import auth as firebase_auth
from flask import current_app, redirect, url_for
from requests import post
from requests.exceptions import HTTPError
from requests.models import Response as RequestsResponse
from werkzeug import Response

from src.utils.google_cloud.google_cloud_secret_manager import get_firebase_api_key


def create_user(user_id="", name="anonymous_user", redirect_url=""):
    if not user_id:
        user_id = name + str(random.randint(0, 1000000))

    email = f"{user_id}@sfkit.org" if "@" not in user_id else user_id
    rand_password = "".join(secrets.choice(string.ascii_letters) for _ in range(16))

    try:
        firebase_auth.get_user_by_email(email)
        firebase_auth.update_user(
            uid=user_id,
            email=email,
            password=rand_password,
        )
    except firebase_auth.UserNotFoundError:
        firebase_auth.create_user(
            uid=user_id,
            email=email,
            password=rand_password,
        )

    doc_ref = current_app.config["DATABASE"].collection("users").document("display_names")
    doc_ref.set({user_id: name}, merge=True)

    if "anonymous_user" in email:
        doc_ref = current_app.config["DATABASE"].collection("users").document(user_id)
        doc_ref.set({"secret_access_code": rand_password}, merge=True)

    return update_user(email, rand_password, redirect_url)


def update_user(email: str, password: str, redirect_url: str = "") -> Response:
    expires_in = datetime.timedelta(days=1)

    user = sign_in_with_email_and_password(email, password)
    session_cookie = firebase_auth.create_session_cookie(user["idToken"], expires_in=expires_in)
    response = redirect(redirect_url or url_for("studies.index"))
    response.set_cookie(
        "session",
        session_cookie,
        expires=datetime.datetime.now() + expires_in,
        httponly=True,
        secure=True,
    )

    return response


def sign_in_with_email_and_password(email: str, password: str) -> dict:
    api_key = get_firebase_api_key()
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}".format(api_key)
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
    request_object = post(request_ref, headers=headers, data=data)
    raise_detailed_error(request_object)
    return request_object.json()


def raise_detailed_error(request_object: RequestsResponse) -> None:
    try:
        request_object.raise_for_status()
    except HTTPError as e:
        raise HTTPError(e, request_object.text) from e
