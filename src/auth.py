from functools import wraps
from http import HTTPMethod, HTTPStatus
from typing import Union

import google.auth
import httpx
import jwt
import requests
from google.auth.transport.requests import Request as GAuthRequest
from google.cloud import firestore
from jwt import algorithms
from quart import Request, Websocket, current_app, request
from werkzeug.exceptions import HTTPException, Unauthorized

from src.api_utils import add_user_to_db
from src.utils import constants, custom_logging

logger = custom_logging.setup_logging(__name__)

AUTH_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "

PUBLIC_KEYS = {}
USER_IDS = set()


if not constants.TERRA:
    # Prepare public keys from Microsoft's JWKS endpoint for token verification
    jwks = requests.get(constants.AZURE_B2C_JWKS_URL).json()
    for key in jwks["keys"]:
        kid = key["kid"]
        PUBLIC_KEYS[kid] = algorithms.RSAAlgorithm.from_jwk(key)


def _get_auth_header(req: Union[Request, Websocket]) -> str:
    return req.headers.get(AUTH_HEADER, "", type=str)


async def get_user_id(req: Union[Request, Websocket] = request) -> str:
    auth_header = _get_auth_header(req)
    if constants.TERRA:
        user = await _get_terra_user(auth_header)
    else:
        user = await _get_azure_b2c_user(auth_header)

    user_id = user["id"] if constants.TERRA else user["sub"]
    if user_id in USER_IDS:
        return user_id

    # guard against possible confusion of user_id with auth_keys
    # TODO: move auth_keys into a separate collection
    if user_id == "auth_keys":
        logger.error("Attempted to use 'auth_keys' as user ID")
        raise Unauthorized("Invalid user ID")

    db: firestore.AsyncClient = current_app.config["DATABASE"]
    if not (await db.collection("users").document(user_id).get()).exists:
        await add_user_to_db(user)
    USER_IDS.add(user_id)
    return user_id


async def _sam_request(
    method: HTTPMethod, path: str, headers: httpx.Headers, json: dict | None = None
):
    async with httpx.AsyncClient() as http:
        return await http.request(
            method.name,
            f"{constants.SAM_API_URL}{path}",
            headers=headers,
            json=json,
        )


async def _get_terra_user(auth_header: str):
    res = await _sam_request(
        HTTPMethod.GET,
        "/api/users/v2/self",
        headers={
            AUTH_HEADER: auth_header,
        },
    )

    if res.status_code != HTTPStatus.OK.value:
        raise Unauthorized("Token is invalid")

    return res.json()


def get_service_account_headers():
    creds, _ = google.auth.default()
    creds = creds.with_scopes(["openid", "email", "profile"])
    creds.refresh(GAuthRequest())
    return {
        AUTH_HEADER: BEARER_PREFIX + creds.token,
    }


async def register_terra_service_account():
    logger.info("Registering Terra service account")
    res = await _sam_request(
        HTTPMethod.POST,
        "/api/users/v2/self/register",
        get_service_account_headers(),
        json={
            "acceptsTermsOfService": True,
        },
    )

    if res.status_code not in (HTTPStatus.CREATED.value, HTTPStatus.CONFLICT.value):
        raise HTTPException(description=str(res.read()), response=res)


async def _get_azure_b2c_user(auth_header: str):
    if not auth_header.startswith(BEARER_PREFIX):
        raise Unauthorized("Invalid Authorization header")

    token = auth_header[len(BEARER_PREFIX) :]
    headers = jwt.get_unverified_header(token)
    kid = headers["kid"]

    if kid not in PUBLIC_KEYS:
        raise Unauthorized("Invalid KID")

    public_key = PUBLIC_KEYS[kid]
    try:
        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=constants.AZURE_B2C_CLIENT_ID,
        )

    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("Token has expired") from e
    except jwt.DecodeError as e:
        raise Unauthorized("Token is invalid") from e
    except jwt.InvalidTokenError as e:
        raise Unauthorized("Token is not valid") from e

    return decoded_token


async def get_cli_user(req: Union[Request, Websocket]) -> dict:
    auth_header = _get_auth_header(req)
    if constants.TERRA:
        user = await _get_terra_user(auth_header)
    else:
        if not auth_header:
            raise Unauthorized("Missing authorization key")

        db: firestore.AsyncClient = current_app.config["DATABASE"]
        user = (
            (await db.collection("users").document("auth_keys").get())
            .to_dict()
            .get(auth_header)
        )

        if not user:
            raise Unauthorized("invalid authorization key")
    return user

async def get_user_email(user_id: str) -> str:
    db: firestore.AsyncClient = current_app.config["DATABASE"]
    user = await db.collection("users").document(user_id).get()
    return user.to_dict().get("email", "")

def authenticate(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        try:
            await get_user_id()
        except Exception as e:
            raise Unauthorized(str(e))

        return await f(*args, **kwargs)

    return decorated_function
