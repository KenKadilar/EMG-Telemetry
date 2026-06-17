// Read the Grove EMG on GPIO32 and publish each reading over Wi-Fi using MQTT.

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "secrets.h"

const int emgPin = 32;                        // GPIO32 = ADC1 channel 4 (works while Wi-Fi is on)
const int sampleRateHz = 200;                 // samples per second
const unsigned long samplePeriodUs = 1000000UL / sampleRateHz;   // microseconds between samples (5000 us at 200 Hz)
const char* emgTopic = "emg/forearm";         // the MQTT channel we publish readings to

WiFiClient wifiClient;                         // the raw network connection
PubSubClient mqttClient(wifiClient);           // MQTT speaks through that connection

unsigned long nextSampleTime = 0;              // micros() timestamp when the next sample is due (the tick grid)

void connectWifi() {
  Serial.print("Wi-Fi: joining ");
  Serial.println(wifiSsid);
  WiFi.mode(WIFI_STA);                         // station mode = join an existing network (not act as a hotspot)
  WiFi.setSleep(false);                        // keep the radio awake so we never miss inbound packets (replies, pings)
  WiFi.begin(wifiSsid, wifiPassword);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.print("\nWi-Fi connected, this device is ");
  Serial.println(WiFi.localIP());
}

void connectMqtt() {
  mqttClient.setServer(mqttBrokerIp, mqttBrokerPort);
  while (!mqttClient.connected()) {
    Serial.print("MQTT: connecting to broker ");
    Serial.println(mqttBrokerIp);
    if (mqttClient.connect("esp32-emg")) {     // "esp32-emg" is this client's name on the broker
      Serial.println("MQTT connected");
    } else {
      Serial.print("failed (state ");
      Serial.print(mqttClient.state());
      Serial.println("), retrying in 1s");
      delay(1000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);                    // ADC returns 0..4095
  analogSetPinAttenuation(emgPin, ADC_11db);   // widen input range to roughly 0..3.3V
  connectWifi();
  connectMqtt();
  nextSampleTime = micros();                   // start the sampling grid from now
}

void loop() {
  if (!mqttClient.connected()) {               // if the broker link dropped, get it back
    connectMqtt();
  }
  mqttClient.loop();                            // let the MQTT library service its housekeeping (and keepalive)

  // Sample on a fixed time grid instead of "do the work, then sleep 5 ms". Advancing nextSampleTime by a
  // constant step keeps the average rate locked to 200 Hz even when a publish runs a little long.
  // The (long) cast makes the comparison survive the micros() wraparound (~every 71 minutes).
  if ((long)(micros() - nextSampleTime) >= 0) {
    nextSampleTime += samplePeriodUs;

    int emgValue = analogRead(emgPin);

    char payload[8];
    snprintf(payload, sizeof(payload), "%d", emgValue);   // MQTT sends text, so format the number
    mqttClient.publish(emgTopic, payload);
  }
}
