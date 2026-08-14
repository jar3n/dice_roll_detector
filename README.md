Dice Roll Detector Code for the RealDice system

The code is split based on the hardware that runs it.
 - client: holds the code that runs on the raspberry pi or other computing device that runs the machine learning and heavier software 
 - firmware: holds the code that runs on the raspberryp pi pico which is responsible for polling the sensors on the tray and reporting when a dice roll hasw been detected


The working demo code utilizes the following files:
 - client:
    - the code inside the client demo folder
    - run the code using flask since its a webserver
    - command `flask --app dicetraywebserver run --debug`
 - firmware:
    - the firmware is in the main.py file because that is the file that micropython looks for when flashing the code and rebooting. This code is a copy of the code in the pico_tray_fw.py file which is where the development of the firmware occcurs.

There is separate code used for running experiments to quantify characteristics of the system. The experiment code for the client is in the client/experiments folder and the firmware experiments code is in the firmware/experiments folder.

