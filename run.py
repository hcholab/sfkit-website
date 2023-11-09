import os
import sys

import src

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    os.environ["FLASK_APP"] = "src"
    os.environ["FLASK_DEBUG"] = "development"
    src.create_app().run(port=port)
