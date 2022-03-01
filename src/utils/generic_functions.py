from flask import redirect, url_for
from werkzeug import Response


def redirect_with_flash(
    url="", location: str = "", message: str = "", error: str = ""
) -> Response:
    if location:
        url = url_for(location)
    r = redirect(url)
    print(f"{message}: {error}") if error else print(message)
    flash(r, message)
    return r


def flash(response: Response, message: str) -> Response:
    response.set_cookie("flash", message)
    return response
