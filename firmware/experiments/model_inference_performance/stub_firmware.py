"""
    Stub for the dice tray (Pico) model inference
    performance experiment firmware.

    Replace this file with the MicroPython firmware that
    runs on the Pico for this experiment, following the
    pattern in
    experiments/vibration_noise_floor/test_vibe_noise_floor.py.

    @author James Englander
"""

from machine import Pin, ADC

VIBE_PIN = 26

vibe = ADC(Pin(VIBE_PIN))


def main():
    # TODO: implement model inference performance experiment firmware
    pass


main()
