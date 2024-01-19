import os
import sys

import src
from src.utils import constants

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    os.environ["FLASK_APP"] = "src"
    constants.FIRESTORE_DATABASE = "sfkit-dev"
    src.create_app().run(port=port)
