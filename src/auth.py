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

# Prepare public keys from Microsoft's JWKS endpoint for token verification
JWKS_URL = "https://sfkitdevb2c.b2clogin.com/sfkitdevb2c.onmicrosoft.com/discovery/v2.0/keys?p=B2C_1_signupsignin1"
jwks = requests.get(JWKS_URL).json()
user_ids = set()
PUBLIC_KEYS = {}


for key in jwks["keys"]:
    kid = key["kid"]
    PUBLIC_KEYS[kid] = algorithms.RSAAlgorithm.from_jwk(key)


async def get_user_id(req: Union[Request, Websocket] = request) -> str:
    auth_header: str = req.headers.get(AUTH_HEADER, "", type=str)
    if not auth_header.startswith("Bearer "):
        raise ValueError("Invalid Authorization header")

    token = auth_header[7:]
    if constants.TERRA:
        res = await _verify_token_terra(token)
    else:
        res = await _verify_token_azure(token)

    user_id = res["userSubjectId"] if constants.TERRA else res["sub"]
    if user_id in user_ids:
        return user_id

    db: firestore.AsyncClient = current_app.config["DATABASE"]
    if not (await db.collection("users").document(user_id).get()).exists:
        await add_user_to_db(res)
    user_ids.add(user_id)
    return user_id


async def _verify_token_terra(token):
    async with httpx.AsyncClient() as client:
        headers = {
            "accept": "application/json",
            AUTH_HEADER: f"Bearer {token}",
        }
        response = await client.get(f"{constants.SAM_API_URL}/api/users/v2/self", headers=headers)

    if response.status_code != 200:
        raise ValueError("Token is invalid")

    return response.json()


async def _verify_token_azure(token):
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
            audience=constants.MICROSOFT_CLIENT_ID,
        )

    except jwt.ExpiredSignatureError as e:
        raise ValueError("Token has expired") from e
    except jwt.DecodeError as e:
        raise ValueError("Token is invalid") from e
    except jwt.InvalidTokenError as e:
        raise ValueError("Token is not valid") from e

    return decoded_token


async def verify_auth_key(
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
