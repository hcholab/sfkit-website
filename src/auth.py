from functools import wraps
from http import HTTPMethod, HTTPStatus
from typing import Union

import httpx
import jwt
import requests
from google.cloud import firestore
from jwt import algorithms
from quart import Request, Websocket, current_app, request
from werkzeug.exceptions import Unauthorized

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


def _get_auth_header():
    return request.headers.get(AUTH_HEADER, "", type=str)


async def get_user_id(req: Union[Request, Websocket] = request) -> str:
    if constants.TERRA:
        user = await _get_terra_user()
    else:
        user = await _get_azure_b2c_user()

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


async def _sam_request(method: HTTPMethod, path: str):
    async with httpx.AsyncClient() as http:
        return await http.request(
            method.name,
            f"{constants.SAM_API_URL}{path}",
            headers={
                "accept": "application/json",
                AUTH_HEADER: _get_auth_header(),
            },
        )


async def _get_terra_user():
    res = await _sam_request(HTTPMethod.GET, "/api/users/v2/self")

    if HTTPStatus(res.status_code) != HTTPStatus.OK:
        raise Unauthorized("Token is invalid")

    return res.json()


async def _get_azure_b2c_user():
    auth_header = _get_auth_header()
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


async def get_cli_user(req: Request) -> dict:
    if constants.TERRA:
        user = await _get_terra_user()
    else:
        auth_header = _get_auth_header()
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


def authenticate(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        try:
            await get_user_id()
        except Exception as e:
            raise Unauthorized(str(e))

        return await f(*args, **kwargs)

    return decorated_function
