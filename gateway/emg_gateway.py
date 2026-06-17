# Gateway service: subscribe to raw "index,sample", apply a 50 Hz notch, re-publish "index,filtered".
# Tracks gaps in the index and reports the measured drop rate.

import argparse, math, time
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=1883)
    ap.add_argument('--in-topic', default='emg/forearm')
    ap.add_argument('--out-topic', default='emg/forearm/filtered')
    ap.add_argument('--fs', type=float, default=200.0)
    ap.add_argument('--mains', type=float, default=50.0, help='Canada: 60')
    ap.add_argument('--report-every', type=int, default=1000)
    args = ap.parse_args()

    notch = Biquad(rbj_notch(args.fs, args.mains))
    state = {'primed': False, 'lastIndex': None, 'received': 0, 'dropped': 0}

    def onConnect(client, userdata, flags, reasonCode, properties):
        print("gateway connected (", reasonCode, "):", args.in_topic, "-> notch ->", args.out_topic)
        client.subscribe(args.in_topic)

    def onMessage(client, userdata, message):
        parts = message.payload.split(b',')
        if len(parts) != 2:
            return
        try:
            sampleIndex = int(parts[0])
            sample = float(int(parts[1]))
        except ValueError:
            return

        last = state['lastIndex']
        if last is not None:
            gap = sampleIndex - last - 1
            if gap < 0 or gap > 1000:
                state['received'] = 0          # stream restarted (ESP32 reboot / out of order): reset tracking
                state['dropped'] = 0
            elif gap > 0:
                state['dropped'] += gap
        state['lastIndex'] = sampleIndex
        state['received'] += 1

        if not state['primed']:
            notch.reset(sample, sample)
            state['primed'] = True
        filtered = notch(sample)
        client.publish(args.out_topic, "%d,%d" % (sampleIndex, int(round(filtered))))

        if state['received'] % args.report_every == 0:
            total = state['received'] + state['dropped']
            loss = 100.0 * state['dropped'] / total if total else 0.0
            print("received %d  dropped %d  (%.2f%% loss)" % (state['received'], state['dropped'], loss), flush=True)

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
