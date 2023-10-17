from functools import wraps

from google.cloud import firestore
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


async def get_user_id(request) -> str:
    return (await verify_token(request.headers.get("Authorization").split(" ")[1]))["sub"]

async def verify_token(token):
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

        db: firestore.AsyncClient = current_app.config["DATABASE"]
        if not (await db.collection("users").document(decoded_token["sub"]).get()).exists:
            await add_user_to_db(decoded_token)

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
        auth_header = request.headers.get("Authorization")
        if not auth_header or "Bearer" not in auth_header:
            return jsonify({"message": "Authentication token required"}), 401

        token = auth_header.split(" ")[1]

        try:
            await verify_token(token)
        except Exception as e:
            return jsonify({"message": str(e)}), 401

        return await f(*args, **kwargs)

    return decorated_function
