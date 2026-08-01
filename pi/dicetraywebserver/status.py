"""

    The status blueprint for the site.

    Serves the dashboard page and the JSON
    endpoints the page polls to show the
    camera / dice tray status and let the
    user confirm or correct a dice roll.

    @author James Englander

"""

from flask import Blueprint, jsonify, render_template, request

from .tray import get_tray_state


bp = Blueprint('status', __name__)


@bp.route("/")
def index():
    """The dashboard page"""
    return render_template("status/index.html")


@bp.route("/api/status")
def api_status():
    """JSON endpoint the dashboard polls for the
       camera / dice tray status and latest result
    """
    return jsonify(get_tray_state().status())


@bp.route("/api/confirm", methods=["POST"])
def api_confirm():
    """Confirm the classifier's result and release
       the pico back to polling
    """
    tray = get_tray_state()
    accepted = tray.confirm()
    return jsonify({"ok": accepted, "status": tray.status()})


@bp.route("/api/correct", methods=["POST"])
def api_correct():
    """Correct the dice roll value and release the pico"""
    value = request.form.get("value", "").strip()
    tray = get_tray_state()
    accepted = tray.correct(value)
    return jsonify({"ok": accepted, "status": tray.status()})
