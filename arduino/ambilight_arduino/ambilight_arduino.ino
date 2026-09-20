/*
  Ambilight Arduino Sketch — Adalight Protocol
  Board: Arduino Uno / Nano
  Strip: WS2812B (NeoPixel)

  Wiring:
    Strip +5V -> External 5V PSU (+)   [NOT Arduino 5V if >15 LEDs]
    Strip GND -> External 5V PSU (-)  AND  Arduino GND (common ground!)
    Strip DIN -> Arduino Pin 6  (through a 470ohm resistor)
    1000uF capacitor across strip +5V/GND near the first LED

  Library needed: FastLED (Sketch > Include Library > Manage Libraries > search "FastLED")

  Protocol: Waits for header bytes 'A','d','a', then 2 count bytes + checksum,
  then NUM_LEDS * 3 bytes of RGB data. This matches the Python script
  (ambilight_capture.py) sent alongside this file.
*/

#include <FastLED.h>

#define NUM_LEDS   60     // <-- SET THIS to your actual total LED count
#define DATA_PIN   6
#define BRIGHTNESS 255    // max brightness cap (0-255); tune to taste/power budget

CRGB leds[NUM_LEDS];

// Timeout: if no data received for a while, fade to black so a dead PC
// doesn't leave the strip frozen on the last frame.
unsigned long lastDataMillis = 0;
const unsigned long TIMEOUT_MS = 3000;

void setup() {
  Serial.begin(115200);
  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.clear();
  FastLED.show();

  // Handshake byte so the PC script can confirm the board is ready
  Serial.println("Ada\n");
}

void loop() {
  // Look for the 3-byte header "Ada"
  if (Serial.available() >= 3) {
    if (Serial.read() == 'A') {
      if (Serial.read() == 'd') {
        if (Serial.read() == 'a') {
          // Wait for the rest of the header: hi, lo, checksum
          while (Serial.available() < 3) { if (checkTimeout()) return; }
          uint8_t hi  = Serial.read();
          uint8_t lo  = Serial.read();
          uint8_t chk = Serial.read();

          int count = (hi << 8) + lo + 1;

          if ((hi ^ lo ^ 0x55) == chk && count == NUM_LEDS) {
            for (int i = 0; i < NUM_LEDS; i++) {
              while (Serial.available() < 3) { if (checkTimeout()) return; }
              leds[i].r = Serial.read();
              leds[i].g = Serial.read();
              leds[i].b = Serial.read();
            }
            FastLED.show();
            lastDataMillis = millis();
          }
        }
      }
    }
  }

  checkTimeout();
}

bool checkTimeout() {
  if (millis() - lastDataMillis > TIMEOUT_MS && lastDataMillis != 0) {
    FastLED.clear();
    FastLED.show();
    lastDataMillis = 0; // avoid clearing repeatedly
  }
  return false;
}
