def flash(response, message):
    response.set_cookie("flash", message)
    return response
