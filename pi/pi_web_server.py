"""

    Web server that shows the 
    state of the raspberry pi
    dice classifier and its latest
    result. On new results, there will
    be a confirmation menu to allow 
    overriding the result

    @author James Englander


"""



from flask import Flask
from flask import render_template
from flask import redirect


app = Flask(__name__)


@app.route("/")
def index():
    """The main index page reroute to the status page"""
    return redirect("/status")

@app.route("/status")
@app.route("/status/<state>")
def status(state=None):
    """This is the main page
        it displays the status
        of the pi
    
    """
    return render_template("status.html", state=state)


@app.route("/set_status/<value>")
def set_status(value=None):
    """Set the status of the page

    Args:
        value (string, optional): the state to 
        set the page to. Defaults to None.
    """
    return redirect(f"/status/{value}")

# @app.route("/submit_correction")
# def button_click():
#     """trying out a url the button click
#     sends the form data to 

#     idk what im doing now
    
#     """

#     # need to return something
#     # i guess just redirect back?
#     return redirect("/status/Correcting")

