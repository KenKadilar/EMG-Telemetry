// EMG read test: sample the Grove EMG output on GPIO32 and print raw ADC values over serial.

#include <Arduino.h>

const int emgPin = 32;                       // GPIO32 = ADC1 channel 4 (the block that keeps working with Wi-Fi on)
const int sampleRateHz = 200;                // samples per second
const int samplePeriodMs = 1000 / sampleRateHz;

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);                  // ADC returns 0..4095
  analogSetPinAttenuation(emgPin, ADC_11db); // widen the input range to roughly 0..3.3V
}

void loop() {
  int emgValue = analogRead(emgPin);
  Serial.println(emgValue);
  delay(samplePeriodMs);
}
