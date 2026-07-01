# Debug tool: capture the raw EMG stream, apply the notch offline, and report drops/range/mains content to a CSV.

import sys, time, math, argparse
import numpy as np
import paho.mqtt.client as mqtt
from emg_gateway import rbj_notch, Biquad   # the exact notch the gateway uses


def amplitudeAt(x, f, fs):
    n = np.arange(len(x))
    s = np.sum(x * np.sin(2 * np.pi * f * n / fs)) * 2 / len(x)
    c = np.sum(x * np.cos(2 * np.pi * f * n / fs)) * 2 / len(x)
    return math.hypot(s, c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=1883)
    ap.add_argument('--topic', default='emg/forearm')
    ap.add_argument('--fs', type=float, default=200.0)
    ap.add_argument('--mains', type=float, default=50.0)
    ap.add_argument('--seconds', type=float, default=8.0)
    ap.add_argument('--csv', default='/tmp/emg_debug.csv')
    args = ap.parse_args()

    indices, samples = [], []

    def onConnect(c, u, fl, rc, pr):
        print("debug connected; capturing %.0fs from %s" % (args.seconds, args.topic), flush=True)
        c.subscribe(args.topic)

    def onMessage(c, u, m):
        parts = m.payload.split(b',')
        if len(parts) < 2:
            return
        try:
            start = int(parts[0])
            vals = [int(x) for x in parts[1:]]
        except ValueError:
            return
        for k, v in enumerate(vals):
            indices.append(start + k)
            samples.append(v)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = onConnect
    client.on_message = onMessage
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()
    time.sleep(args.seconds)
    client.loop_stop()
    client.disconnect()

    if not samples:
        print("no data captured (is the ESP32 publishing on %s?)" % args.topic, flush=True)
        return

    raw = np.array(samples, dtype=float)
    idx = np.array(indices)
    drops = (idx[-1] - idx[0] + 1) - len(idx)

    bq = Biquad(rbj_notch(args.fs, args.mains))
    bq.reset(raw[0], raw[0])
    notched = np.array([bq(v) for v in raw])

    def report(name, x):
        ac = x - x.mean()
        print("%-8s min=%4.0f max=%4.0f mean=%6.1f std=%6.1f | 50Hz=%5.1f 100Hz=%5.1f 150Hz=%5.1f" % (
            name, x.min(), x.max(), x.mean(), x.std(),
            amplitudeAt(ac, 50, args.fs), amplitudeAt(ac, 100, args.fs), amplitudeAt(ac, 150, args.fs)), flush=True)

    print("samples=%d drops=%d rate=%.0f/s" % (len(raw), drops, len(raw) / args.seconds), flush=True)
    report("raw", raw)
    report("notched", notched)

    with open(args.csv, 'w') as f:
        f.write("index,raw,notched\n")
        for i in range(len(raw)):
            f.write("%d,%d,%d\n" % (idx[i], raw[i], round(notched[i])))
    print("wrote", args.csv, flush=True)


if __name__ == '__main__':
    main()
