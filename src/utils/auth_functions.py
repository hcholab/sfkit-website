import datetime
import json

from firebase_admin import auth as firebase_auth
from flask import redirect, url_for
from requests import post
from requests.models import Response as RequestsResponse
from werkzeug import Response
from requests.exceptions import HTTPError


def update_user(email: str, password: str) -> Response:
    expires_in = datetime.timedelta(days=1)

    user = sign_in_with_email_and_password(email, password)
    session_cookie = firebase_auth.create_session_cookie(user["idToken"], expires_in=expires_in)
    response = redirect(url_for("studies.index"))
    response.set_cookie(
        "session",
        session_cookie,
        expires=datetime.datetime.now() + expires_in,
        httponly=True,
        secure=True,
    )

    return response


def sign_in_with_email_and_password(email: str, password: str) -> dict:
    with open("fbconfig.json") as f:
        config = json.load(f)
    api_key = config["apiKey"]
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
