// Read the Grove EMG on GPIO32 and publish "index,sample" over Wi-Fi using MQTT.

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "secrets.h"

const int emgPin = 32;
const int sampleRateHz = 200;
const unsigned long samplePeriodUs = 1000000UL / sampleRateHz;
const char* emgTopic = "emg/forearm";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long nextSampleTime = 0;
unsigned long sampleIndex = 0;

void connectWifi() {
  Serial.print("Wi-Fi: joining ");
  Serial.println(wifiSsid);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
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
    if (mqttClient.connect("esp32-emg")) {
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
  analogReadResolution(12);
  analogSetPinAttenuation(emgPin, ADC_11db);
  connectWifi();
  connectMqtt();
  nextSampleTime = micros();
}

void loop() {
  if (!mqttClient.connected()) {
    connectMqtt();
  }
  mqttClient.loop();

  if ((long)(micros() - nextSampleTime) >= 0) {
    nextSampleTime += samplePeriodUs;

    int emgValue = analogRead(emgPin);

    char payload[20];
    snprintf(payload, sizeof(payload), "%lu,%d", sampleIndex, emgValue);
    mqttClient.publish(emgTopic, payload);
    sampleIndex++;
  }
}
