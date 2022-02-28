from flask import redirect, url_for
from werkzeug import Response


def redirect_with_flash(location: str, message: str, error: str = "") -> Response:
    r = redirect(url_for(location))
    print(f"{message}: {error}") if error else print(message)
    flash(r, message)
    return r


def flash(response: Response, message: str) -> Response:
    response.set_cookie("flash", message)
    return response
