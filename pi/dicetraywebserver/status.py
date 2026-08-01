"""

    The status blueprint for the site


    @author James Englander

"""


from flask import Blueprint, url_for, render_template



bp = Blueprint('status', __name__)

@bp.route("/")
def index():
    """Show something"""

    # do processing here maybe later
    return render_template("status/index.html")



