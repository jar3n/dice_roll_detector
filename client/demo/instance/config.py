# Local config for the dice tray web server.
# Values here override the defaults in dicetraywebserver/__init__.py.
# You can also set the DICETRAY_SERIAL_PORT / DICETRAY_SERIAL_BAUD
# environment variables instead.

SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 115200

# To use the dice classifier hook, import the callable from its own module
# here (see client/demo/classifier.py).  When the pico sends a classify request the
# app calls it with the message dict and shows the returned roll value on
# the dashboard for confirmation:
#

from classifier import classify_roll

CLASSIFY_HOOK = classify_roll

