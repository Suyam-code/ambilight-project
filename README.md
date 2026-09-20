# Ambilight — DIY Screen-Sync LED Strip

A WS2812B LED strip mounted behind a laptop screen that mirrors on-screen
colors in real time, Philips Ambilight style. Built with an Arduino Uno
and a Python screen-capture script using the Adalight serial protocol.

## Hardware
- Arduino Uno
- WS2812B strip, 60 LEDs
- 5V 2A power supply
- Breadboard + jumper wires

## Setup
1. Flash `arduino/ambilight_arduino/ambilight_arduino.ino` to the Arduino
   (requires the FastLED library).
2. Set up the Python environment:

cd python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

3. Edit `python/ambilight_capture.py` — set `SERIAL_PORT` to your board's port.
4. Run: `python3 ambilight_capture.py`

## Auto-start on macOS
A `launchd` LaunchAgent config is included in `launchagent/` to auto-start
the script on login.
