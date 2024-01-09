from functools import wraps

from google.cloud import firestore
import httpx
import jwt
from jwt import algorithms
import requests
from quart import current_app, jsonify, request

from src.api_utils import add_user_to_db
from src.utils import constants

# Prepare public keys from Microsoft's JWKS endpoint for token verification
JWKS_URL = "https://sfkitdevb2c.b2clogin.com/sfkitdevb2c.onmicrosoft.com/discovery/v2.0/keys?p=B2C_1_signupsignin1"
jwks = requests.get(JWKS_URL).json()
PUBLIC_KEYS = {}

for key in jwks["keys"]:
    kid = key["kid"]
    PUBLIC_KEYS[kid] = algorithms.RSAAlgorithm.from_jwk(key)


async def get_user_id() -> str:
    auth_header: str = request.headers.get("Authorization", "", type=str)
    if not auth_header.startswith("Bearer "):
        raise ValueError("Invalid Authorization header")
    res = await _verify_token(auth_header[7:])
    return res["id"] if constants.TERRA else res["sub"]


async def _verify_token(token):
    if constants.TERRA:
        res = await _verify_token_terra(token)
    else:
        res = await _verify_token_azure(token)

    user_id = res["id"] if constants.TERRA else res["sub"]

    db: firestore.AsyncClient = current_app.config["DATABASE"]
    if not (await db.collection("users").document(user_id).get()).exists:
        await add_user_to_db(res)


async def _verify_token_terra(token):
    async with httpx.AsyncClient() as client:
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}",
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


def authenticate(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "", type=str)
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Authentication token required"}), 401
        try:
            await _verify_token(auth_header[7:])
        except Exception as e:
            return jsonify({"message": str(e)}), 401

        return await f(*args, **kwargs)

    return decorated_function
