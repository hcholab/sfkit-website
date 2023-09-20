import os
import secrets

import firebase_admin
from flask import Flask
from flask_cors import CORS
from google.cloud import firestore

from src import cli
from src.utils import custom_logging
from src.web import web, participants, study

logger = custom_logging.setup_logging(__name__)


def create_app() -> Flask:
    initialize_firebase_admin()

    app = Flask(__name__)
    CORS(app)

    app.config.from_mapping(
        SECRET_KEY=secrets.token_hex(16), DATABASE=firestore.Client()
    )

    app.register_blueprint(cli.bp)
    app.register_blueprint(web.bp)
    app.register_blueprint(participants.bp)
    app.register_blueprint(study.bp)

    return app


def initialize_firebase_admin() -> None:
    key: str = ".serviceAccountKey.json"
    if os.path.exists(key):  # local testing
        firebase_admin.initialize_app(firebase_admin.credentials.Certificate(key))
    else:
        logger.info("No service account key found, using default for firebase_admin")
        firebase_admin.initialize_app()
