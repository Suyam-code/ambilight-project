/*
  test_leds.ino — Run this FIRST, before ambilight_arduino.ino

  Purpose: confirm wiring is correct and figure out your exact NUM_LEDS.
  It will light the strip red -> green -> blue -> rainbow chase in a loop.

  If nothing lights up: check GND is common between Arduino, strip, and
  the power adapter, and check DIN is on pin 6.
  If only SOME LEDs light up: that's your real LED count — count them
  and use that number in NUM_LEDS below (and later in the ambilight files).
*/

#include <FastLED.h>

#define NUM_LEDS   60     // guess for now — set to strip's max length, we'll correct it
#define DATA_PIN   6

CRGB leds[NUM_LEDS];

void setup() {
  FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(80);  // keep it low for a bare-wire test setup
}

void solidColor(CRGB color, int delayMs) {
  fill_solid(leds, NUM_LEDS, color);
  FastLED.show();
  delay(delayMs);
}

void loop() {
  solidColor(CRGB::Red,   1000);
  solidColor(CRGB::Green, 1000);
  solidColor(CRGB::Blue,  1000);

  // Rainbow chase — also helps you visually confirm LED order/count
  for (int j = 0; j < 256; j++) {
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CHSV((i * 256 / NUM_LEDS + j) & 255, 255, 255);
    }
    FastLED.show();
    delay(20);
  }
}
