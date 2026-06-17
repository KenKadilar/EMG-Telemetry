# Subscribe to the EMG stream from the broker and report what arrives (Step 2: prove our own code receives it).

import time
import paho.mqtt.client as mqtt

brokerHost = "127.0.0.1"          # the broker runs on this same laptop
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
    receivedSample = int(message.payload)              # payload is text like b"1753"; turn it back into a number
    messageCount += 1
    now = time.time()
    if now - windowStart >= 1.0:                  # once per second, report the rate and the latest reading
        print("rate: %d msg/s   last value: %d" % (messageCount, receivedSample))
        messageCount = 0
        windowStart = now

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = onConnect
client.on_message = onMessage
client.connect(brokerHost, brokerPort, keepalive=60)
client.loop_forever()                              # block here, handling callbacks as messages arrive
