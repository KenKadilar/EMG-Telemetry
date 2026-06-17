# Subscribe to the EMG stream and report the receive rate + latest sample.

import time
import paho.mqtt.client as mqtt

brokerHost = "127.0.0.1"
brokerPort = 1883
emgTopic = "emg/forearm"

messageCount = 0
receivedSample = 0
windowStart = time.time()

def onConnect(client, userdata, flags, reasonCode, properties):
    print("connected to broker (", reasonCode, "), subscribing to", emgTopic)
    client.subscribe(emgTopic)

def onMessage(client, userdata, message):
    global messageCount, receivedSample, windowStart
    try:
        receivedSample = int(message.payload.split(b',')[-1])
    except ValueError:
        return
    messageCount += 1
    now = time.time()
    if now - windowStart >= 1.0:
        print("rate: %d msg/s   last value: %d" % (messageCount, receivedSample))
        messageCount = 0
        windowStart = now

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = onConnect
client.on_message = onMessage
client.connect(brokerHost, brokerPort, keepalive=60)
client.loop_forever()
