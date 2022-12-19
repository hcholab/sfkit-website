import sys
from waitress import serve
import src
from flask import Flask, app
import os

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    # serve(src.create_app(), port=p, debug=True)
    os.environ["FLASK_APP"] = "src"
    os.environ["FLASK_DEBUG"] = "development"
    src.create_app().run(debug=True, port=port)
