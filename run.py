import os
import sys

import src
from src.utils import constants

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    os.environ["FLASK_APP"] = "src"

    # use dev environment
    constants.FIRESTORE_DATABASE = "sfkit-dev"
    constants.FLASK_DEBUG = "development"
    constants.SFKIT_API_URL = "https://sfkit-website-dev-bhj5a4wkqa-uc.a.run.app/api"
    constants.SERVICE_URL = "dev"

    src.create_app().run(port=port)
