import os

from flask import Flask
from flask_bootstrap import Bootstrap
from google.cloud import firestore


def create_app(test_config=None):
    app = Flask(__name__)

    if test_config:
        app.config.update(test_config)
    else:
        app.config.from_mapping(
            SECRET_KEY=os.urandom(12).hex(), DATABASE=firestore.Client()
        )

    Bootstrap(app)

    from src import auth, general, gwas

    app.register_blueprint(auth.bp)
    app.register_blueprint(gwas.bp)
    app.register_blueprint(general.bp)

    return app
