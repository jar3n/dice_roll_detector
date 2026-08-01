"""

    Flask app factory for
    the dice tray web server

    this is the main entry point
    for running it with flask

    use the flask --app dicetraywebserver run --debug
    to run it

    @author James Englander

"""

import os

from flask import Flask, render_template, url_for

# blueprint imports
from . import status


def create_app(test_config=None):
    """creates the flask app

    Args:
        test_config (_type_, optional): config file name. Defaults to None.
    """

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        SERIAL_PORT=os.environ.get("DICETRAY_SERIAL_PORT", "/dev/ttyACM0"),
        SERIAL_BAUD=int(os.environ.get("DICETRAY_SERIAL_BAUD", "115200")),
        CLASSIFY_HOOK=None,
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    # make simple hello page to start
    @app.route("/hello")
    def hello():
        return "Hello Dice tray user!!!"

    # register the blueprints
    app.register_blueprint(status.bp)

    # return the app
    return app
