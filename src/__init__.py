import os
import secrets

import firebase_admin
from quart import Quart
from quart_cors import cors
from google.cloud import firestore

from src import cli, signaling, status
from src.api_utils import get_api_origin

from src.utils import custom_logging
from src.web import web, participants, study

logger = custom_logging.setup_logging(__name__)


def create_app() -> Quart:
    initialize_firebase_admin()

    app = Quart(__name__)
    app = cors(app, allow_origin=get_api_origin())

    app.config.from_mapping(
        SECRET_KEY=secrets.token_hex(16), DATABASE=firestore.AsyncClient()
    )

    app.register_blueprint(status.bp)
    app.register_blueprint(cli.bp)
    app.register_blueprint(web.bp)
    app.register_blueprint(participants.bp)
    app.register_blueprint(study.bp)
    app.register_blueprint(signaling.bp)

    return app


def initialize_firebase_admin() -> None:
    key: str = ".serviceAccountKey.json"
    if os.path.exists(key):  # local testing
        firebase_admin.initialize_app(firebase_admin.credentials.Certificate(key))
    else:
        logger.info("No service account key found, using default for firebase_admin")
        firebase_admin.initialize_app()


# def initialize_firestore_async_client():
#     key: str = ".serviceAccountKey.json"

#     # If service account key exists, use it (local testing)
#     if os.path.exists(key):
#         with open(key) as json_file:
#             json_data = json.load(json_file)
#         return firestore.AsyncClient(
#             project=json_data["project_id"],
#             credentials=service_account.Credentials.from_service_account_info(
#                 json_data
#             ),
#         )

#     else:
#         logger.info(
#             "No service account key found, using Google Application Default Credentials"
#         )
#         return firestore.AsyncClient()
