from functools import wraps
from typing import Union

import httpx
import jwt
import requests
from google.cloud import firestore
from jwt import algorithms
from quart import Request, Websocket, current_app, jsonify, request

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


async def get_user_id(req: Union[Request, Websocket] = request) -> str:
    auth_header: str = req.headers.get(AUTH_HEADER, "", type=str)
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
        raise ValueError("Invalid user ID")

    db: firestore.AsyncClient = current_app.config["DATABASE"]
    if not (await db.collection("users").document(user_id).get()).exists:
        await add_user_to_db(user)
    USER_IDS.add(user_id)
    return user_id


async def _get_terra_user(auth_header: str):
    async with httpx.AsyncClient() as client:
        headers = {
            "accept": "application/json",
            AUTH_HEADER: auth_header,
        }
        response = await client.get(f"{constants.SAM_API_URL}/api/users/v2/self", headers=headers)

    if response.status_code != 200:
        raise ValueError("Token is invalid")

    return response.json()


async def _get_azure_b2c_user(auth_header: str):
    if not auth_header.startswith(BEARER_PREFIX):
        raise ValueError("Invalid Authorization header")

    token = auth_header[len(BEARER_PREFIX):]
    headers = jwt.get_unverified_header(token)
    kid = headers["kid"]

    if kid not in PUBLIC_KEYS:
        raise ValueError("Invalid KID")

    public_key = PUBLIC_KEYS[kid]
    try:
        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=constants.AZURE_B2C_CLIENT_ID,
        )

    except jwt.ExpiredSignatureError as e:
        raise ValueError("Token has expired") from e
    except jwt.DecodeError as e:
        raise ValueError("Token is invalid") from e
    except jwt.InvalidTokenError as e:
        raise ValueError("Token is not valid") from e

    return decoded_token


async def get_auth_key_user(
    request: Request, authenticate_user: bool = True
) -> dict:
    auth_key = request.headers.get(AUTH_HEADER)
    if not auth_key:
        logger.error("no authorization key provided")
        return {}

    db: firestore.AsyncClient = current_app.config["DATABASE"]
    doc = (
        await db.collection("users").document("auth_keys").get()
    ).to_dict().get(auth_key)

    if not doc:
        logger.error("invalid authorization key")
        return {}

    return doc


def authenticate(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        try:
            await get_user_id()
        except Exception as e:
            return jsonify({"message": str(e)}), 401

        return await f(*args, **kwargs)

    return decorated_function
