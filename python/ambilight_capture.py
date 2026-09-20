"""
Ambilight Screen Capture -> Arduino (Adalight protocol)

Grabs the edges of your screen, averages the color in zones matching your
physical LED layout, and streams it to the Arduino over serial in real time.

Install dependencies:
    pip install mss pillow numpy pyserial

Run:
    python ambilight_capture.py

Press Ctrl+C to stop (strip will time out and clear itself after a few
seconds, per the Arduino sketch's TIMEOUT_MS).
"""

import time
import sys
import pathlib
import numpy as np
import serial
from mss import mss
from PIL import Image

# ============================= CONFIG =======================================

SERIAL_PORT = "/dev/cu.usbmodem11101"        # Windows: "COM5" etc. Linux/Mac: "/dev/ttyUSB0" or "/dev/ttyACM0"
BAUD_RATE   = 115200        # must match Arduino Serial.begin()

MONITOR_INDEX = 1           # mss monitor index (1 = primary monitor; check via mss().monitors)

# --- LED layout: how many LEDs on each edge of the screen bezel ---
# Order MUST match the physical order LEDs are wired in.
# Default assumes: start bottom-left corner, go UP the left side, then
# CLOCKWISE across top, down the right side, and across the bottom back
# to the start. Adjust LEDS_* counts and EDGE_ORDER to match your build.
LEDS_LEFT   = 10
LEDS_TOP    = 20
LEDS_RIGHT  = 10
LEDS_BOTTOM = 20
EDGE_ORDER  = ["left_up", "top_right", "right_down", "bottom_left"]

NUM_LEDS = LEDS_LEFT + LEDS_TOP + LEDS_RIGHT + LEDS_BOTTOM

EDGE_DEPTH_FRAC = 0.12       # how far into the screen (fraction of dimension) each edge zone samples
FPS_TARGET      = 30
SMOOTHING       = 0.1        # lower = snappier response to scene changes
SATURATION_BOOST = 1.35      # >1 makes colors punchier (edge pixels are often washed out)
GAMMA           = 1.0        # disabled — was over-brightening near-black pixels
BLACK_THRESHOLD = 12         # any channel average below this gets forced to 0 (true black)

# Per-channel calibration — tune if colors look unbalanced on your specific strip.
# (R, G, B) multipliers applied after saturation boost. Start here, adjust by feel:
CHANNEL_GAIN = (1.15, 1.0, 0.80)   # boosts red, slightly reduces blue

BRIGHTNESS = 1.0             # master brightness, 0.0-1.0
BRIGHTNESS_FILE = pathlib.Path(__file__).parent / "brightness.txt"  # edit this file anytime to change brightness live

# ============================================================================


def open_serial():
    print(f"Opening {SERIAL_PORT} @ {BAUD_RATE}...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # allow Arduino to reset after serial connect
    ser.reset_input_buffer()
    print("Connected.")
    return ser


def build_zone_boxes(w, h):
    """Return list of (x0,y0,x1,y1) pixel boxes, one per LED, in EDGE_ORDER."""
    depth_x = max(1, int(w * EDGE_DEPTH_FRAC))
    depth_y = max(1, int(h * EDGE_DEPTH_FRAC))
    boxes = []

    def split(a, b, n):
        pts = np.linspace(a, b, n + 1).astype(int)
        return list(zip(pts[:-1], pts[1:]))

    for edge in EDGE_ORDER:
        if edge == "left_up":
            for y0, y1 in reversed(split(0, h, LEDS_LEFT)):
                boxes.append((0, y0, depth_x, y1))
        elif edge == "top_right":
            for x0, x1 in split(0, w, LEDS_TOP):
                boxes.append((x0, 0, x1, depth_y))
        elif edge == "right_down":
            for y0, y1 in split(0, h, LEDS_RIGHT):
                boxes.append((w - depth_x, y0, w, y1))
        elif edge == "bottom_left":
            for x0, x1 in reversed(split(0, w, LEDS_BOTTOM)):
                boxes.append((x0, h - depth_y, x1, h))
        else:
            raise ValueError(f"Unknown edge '{edge}' in EDGE_ORDER")
    return boxes


def sample_colors(img_array, boxes):
    colors = np.zeros((len(boxes), 3), dtype=np.float32)
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        region = img_array[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)]
        colors[i] = region.reshape(-1, region.shape[-1])[:, :3].mean(axis=0)
    return colors


def apply_style(colors):
    # Black cutoff — kill near-zero pixels entirely instead of letting
    # gamma/saturation brighten them into a dim glow
    brightness = colors.mean(axis=1, keepdims=True)
    black_mask = (brightness < BLACK_THRESHOLD).flatten()

    # Saturation boost
    mean = colors.mean(axis=1, keepdims=True)
    colors = mean + (colors - mean) * SATURATION_BOOST
    colors = np.clip(colors, 0, 255)

    # Gamma correction (only if GAMMA != 1.0)
    if GAMMA != 1.0:
        colors = 255.0 * (colors / 255.0) ** (1.0 / GAMMA)

    # Per-channel calibration
    colors = colors * np.array(CHANNEL_GAIN)

    colors[black_mask] = 0
    colors = colors * BRIGHTNESS
    return np.clip(colors, 0, 255)


def check_brightness_file():
    """Re-read brightness.txt if it exists and has a valid number. Silently ignores bad/missing file."""
    global BRIGHTNESS
    try:
        value = float(BRIGHTNESS_FILE.read_text().strip())
        BRIGHTNESS = max(0.0, min(1.0, value))
    except Exception:
        pass


def send_frame(ser, colors_uint8):
    n = len(colors_uint8) - 1
    hi, lo = (n >> 8) & 0xFF, n & 0xFF
    checksum = hi ^ lo ^ 0x55
    header = bytes(["Ada".encode()[0], "Ada".encode()[1], "Ada".encode()[2], hi, lo, checksum])
    payload = colors_uint8.astype(np.uint8).tobytes()
    ser.write(header + payload)


def main():
    print(f"Configured for {NUM_LEDS} LEDs "
          f"(L{LEDS_LEFT}/T{LEDS_TOP}/R{LEDS_RIGHT}/B{LEDS_BOTTOM})")

    ser = open_serial()
    sct = mss()
    monitor = sct.monitors[MONITOR_INDEX]
    w, h = monitor["width"], monitor["height"]
    boxes = build_zone_boxes(w, h)

    prev_colors = np.zeros((NUM_LEDS, 3), dtype=np.float32)
    frame_interval = 1.0 / FPS_TARGET
    frame_count = 0

    print("Streaming... Ctrl+C to stop.")
    try:
        while True:
            t0 = time.time()

            raw = np.array(sct.grab(monitor))  # BGRA
            frame = raw[:, :, [2, 1, 0]]       # -> RGB

            colors = sample_colors(frame, boxes)
            colors = apply_style(colors)

            # Exponential smoothing to reduce flicker
            colors = SMOOTHING * prev_colors + (1 - SMOOTHING) * colors
            prev_colors = colors

            send_frame(ser, colors)

            elapsed = time.time() - t0
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
