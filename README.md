Dice Roll Detector Code for the RealDice system

The code is split based on the hardware that runs it.
 - client: holds the code that runs on the raspberry pi or other computing device that runs the machine learning and heavier software 
 - firmware: holds the code that runs on the raspberryp pi pico which is responsible for polling the sensors on the tray and reporting when a dice roll hasw been detected

 To run the code, install the required python packages using pip and the requirements.txt file in the demo code folder.
 - to install on the pi you need to change the temp directory pip uses for installing packages
   - command: `export TMPDIR=<place on pi with more than 1 G of storage>`
 - first make a virtual environment with venv: `python -m venv .venv`
 - command to install the packages: `pip install -r requirements.txt`
    - run this command from the client/demo folder

The working demo code utilizes the following files:
 - client:
    - the code inside the client demo folder
    - run the code using flask in the client/demo/webserver folder
    - command `flask --app dicetraywebserver run --debug`
 - firmware:
    - the firmware is in the main.py file because that is the file that micropython looks for when flashing the code and rebooting. This code is a copy of the code in the pico_tray_fw.py file which is where the development of the firmware occcurs.
    - to run the firmware use thonny or another tool to copy the main.py file from the firmware folder into the pico
    - then reboot the pico and the firmware will be running

 
  


There is separate code used for running experiments to quantify characteristics of the system. The experiment code for the client is in the client/experiments folder and the firmware experiments code is in the firmware/experiments folder.

