import os
import secrets

import firebase_admin
from flask import Flask
from flask_bootstrap import Bootstrap
from google.cloud import firestore

from src import auth, general, gwas, studies


def create_app() -> Flask:
    initialize_firebase_admin()

    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY=secrets.token_hex(16), DATABASE=firestore.Client())

    Bootstrap(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(gwas.bp)
    app.register_blueprint(general.bp)
    app.register_blueprint(studies.bp)

    return app


def initialize_firebase_admin() -> None:
    # if serviceAccountKey.json file exists, use it to initialize the app (for local testing)
    if os.path.exists("serviceAccountKey.json"):
        firebase_admin.initialize_app(firebase_admin.credentials.Certificate("serviceAccountKey.json"))
    else:
        print("Using default service account for the firebase_admin")
        firebase_admin.initialize_app()
