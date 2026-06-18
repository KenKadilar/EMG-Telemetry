# Gateway service: subscribe to raw "index,sample", apply a 50 Hz notch, re-publish "index,filtered".
# Tracks gaps in the index and reports the measured drop rate.
# Optional cloud branch: if aws_config.py is present, also forwards a decimated (~5/s) rolling activity level to AWS IoT Core.

import argparse, glob, json, math, os, statistics, time
from collections import deque
import paho.mqtt.client as mqtt


def rbj_notch(fs, f0, q=2.5):
    """Second-order RBJ notch coefficients (b0,b1,b2,a1,a2), a0-normalized."""
    w0 = 2 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    a0 = 1 + alpha
    return 1 / a0, (-2 * c) / a0, 1 / a0, (-2 * c) / a0, (1 - alpha) / a0


class Biquad:
    """Stateful direct-form-I biquad, one sample at a time (from emg_studio.py)."""
    def __init__(self, coeffs):
        self.b0, self.b1, self.b2, self.a1, self.a2 = coeffs
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def __call__(self, x):
        y = (self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2
             - self.a1 * self.y1 - self.a2 * self.y2)
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y

    def reset(self, x=0.0, y=0.0):
        self.x1 = self.x2 = x
        self.y1 = self.y2 = y


def parseBatch(payload):
    """Parse a 'startIndex,s0,s1,...' MQTT payload into (startIndex, [samples]). None if malformed."""
    parts = payload.split(b',')
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), [int(p) for p in parts[1:]]
    except ValueError:
        return None


class GapCounter:
    """Counts dropped samples from gaps in the batch start-index sequence."""
    def __init__(self):
        self.lastIndex = None
        self.totalSampleCount = 0
        self.dropped = 0

    def update(self, startIndex, count):
        if self.lastIndex is not None:
            gap = startIndex - self.lastIndex - 1
            if gap < 0 or gap > 1000:        # stream restarted (ESP32 reboot / out of order): reset
                self.totalSampleCount = 0
                self.dropped = 0
            elif gap > 0:
                self.dropped += gap
        self.lastIndex = startIndex + count - 1
        self.totalSampleCount += count

    def lossPercent(self):
        total = self.totalSampleCount + self.dropped
        return 100.0 * self.dropped / total if total else 0.0


def makeAwsClient():
    """Connect a second MQTT client to AWS IoT Core over mutual TLS. None if not configured or unreachable."""
    try:
        import aws_config
    except ImportError:
        print("cloud uplink off (no aws_config.py)", flush=True)
        return None
    rootCa = os.path.join(aws_config.credsDir, "AmazonRootCA1.pem")
    certificate = glob.glob(os.path.join(aws_config.credsDir, "*-certificate.pem.crt"))[0]
    privateKey = glob.glob(os.path.join(aws_config.credsDir, "*-private.pem.key"))[0]
    cloud = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="emg-edge-gateway")
    cloud.tls_set(ca_certs=rootCa, certfile=certificate, keyfile=privateKey)
    cloud.reconnect_delay_set(min_delay=1, max_delay=30)
    try:
        cloud.connect(aws_config.endpoint, 8883, keepalive=60)
    except OSError as e:
        print("cloud uplink unreachable (%s); running local-only" % e, flush=True)
        return None
    cloud.loop_start()
    print("cloud uplink on ->", aws_config.endpoint, flush=True)
    return cloud


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=1883)
    ap.add_argument('--in-topic', default='emg/forearm')
    ap.add_argument('--out-topic', default='emg/forearm/filtered')
    ap.add_argument('--fs', type=float, default=200.0)
    ap.add_argument('--mains', type=float, default=50.0, help='Canada: 60')
    ap.add_argument('--report-every', type=int, default=1000)
    ap.add_argument('--cloud-topic', default='emg/forearm/cloud')
    args = ap.parse_args()

    notch = Biquad(rbj_notch(args.fs, args.mains))
    tracker = GapCounter()
    primed = {'done': False}
    lastReport = {'count': 0}
    awsClient = makeAwsClient()
    cloudState = {'lastPublish': 0.0}
    cloudWindow = deque(maxlen=200)

    def onConnect(client, userdata, flags, reasonCode, properties):
        print("gateway connected (", reasonCode, "):", args.in_topic, "-> notch ->", args.out_topic)
        client.subscribe(args.in_topic)

    def onMessage(client, userdata, message):
        parsed = parseBatch(message.payload)
        if parsed is None:
            return
        startIndex, samples = parsed

        tracker.update(startIndex, len(samples))

        filteredBatch = []
        for s in samples:
            if not primed['done']:
                notch.reset(s, s)
                primed['done'] = True
            filteredBatch.append(int(round(notch(float(s)))))

        client.publish(args.out_topic, "%d,%s" % (startIndex, ",".join(str(f) for f in filteredBatch)))

        if awsClient is not None:
            cloudWindow.extend(filteredBatch)
            now = time.time()
            if now - cloudState['lastPublish'] >= 0.2:
                cloudState['lastPublish'] = now
                activityLevel = round(statistics.pstdev(cloudWindow), 1)
                awsClient.publish(args.cloud_topic, json.dumps({"time": round(now, 2), "level": activityLevel}))

        if tracker.totalSampleCount < lastReport['count']:
            lastReport['count'] = 0
        if tracker.totalSampleCount - lastReport['count'] >= args.report_every:
            lastReport['count'] = tracker.totalSampleCount
            print("received %d  dropped %d  (%.2f%% loss)" % (
                tracker.totalSampleCount, tracker.dropped, tracker.lossPercent()), flush=True)

    def onDisconnect(client, userdata, disconnectFlags, reasonCode, properties):
        print("disconnected (", reasonCode, "); reconnecting...", flush=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = onConnect
    client.on_message = onMessage
    client.on_disconnect = onDisconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    while True:
        try:
            client.connect(args.host, args.port, keepalive=60)
            break
        except OSError as e:
            print("broker not reachable (%s); retrying in 2s" % e, flush=True)
            time.sleep(2)

    client.loop_forever()


if __name__ == '__main__':
    main()
