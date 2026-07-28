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


app = Flask(__name__)


@app.route("/")
def index():
    """The main index page route"""
    return "Index Page"

@app.route("/hello")
def hello():
    """an example hello page to a different route"""
    return "Hello Page"

@app.route("/jinja")
@app.route("/jinja/<name>")
def jinja_temp_test(name=None):
    """trying out the jinja
       simple template

       the name shows how to pass data to the page
    
    """
    return render_template("hello.html", person=name)

