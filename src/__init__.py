import os

from flask import Flask
from flask_bootstrap import Bootstrap

from . import auth, general, gwas


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(12).hex()
    Bootstrap(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(gwas.bp)
    app.register_blueprint(general.bp)

    return app
