# Headless EMG gateway service: subscribe to the raw stream, apply a 50 Hz mains notch filter,
# and re-publish the cleaned signal to a derived topic. This is the "gateway" of the project: it
# ingests, processes, and re-publishes, and is what later runs as a systemd service on the Pi.
# The notch math (rbj_notch + Biquad) is reused from the STM32 emg_studio.py.

import argparse, math
import paho.mqtt.client as mqtt


def rbj_notch(fs, f0, q=2.5):
    """Second-order RBJ notch coefficients (b0,b1,b2,a1,a2), a0-normalized. Notches out f0 (the mains hum)."""
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
    ap.add_argument('--fs', type=float, default=200.0, help='samples/sec, must match the firmware rate')
    ap.add_argument('--mains', type=float, default=50.0, help='mains frequency to notch out (Canada: 60)')
    args = ap.parse_args()

    notch = Biquad(rbj_notch(args.fs, args.mains))    # the 50/60 Hz mains-hum notch
    state = {'primed': False}

    def onConnect(client, userdata, flags, reasonCode, properties):
        print("gateway connected (", reasonCode, "):", args.in_topic, "-> notch -> ", args.out_topic)
        client.subscribe(args.in_topic)

    def onMessage(client, userdata, message):
        try:
            raw = float(int(message.payload))
        except ValueError:
            return                                     # ignore a malformed payload, keep the service alive
        if not state['primed']:
            notch.reset(raw, raw)                      # seed the filter at the first sample so it starts at the
            state['primed'] = True                     # baseline instead of ramping up from 0 (no startup jump)
        filtered = notch(raw)
        client.publish(args.out_topic, "%d" % int(round(filtered)))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = onConnect
    client.on_message = onMessage
    client.connect(args.host, args.port, keepalive=60)
    client.loop_forever()                              # headless service: the network loop IS the program


if __name__ == '__main__':
    main()
