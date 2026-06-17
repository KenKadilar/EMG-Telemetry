# Live scrolling graph of the EMG stream from MQTT.

import os, sys, argparse
os.environ.setdefault('PYQTGRAPH_QT_LIB', 'PyQt6')
import numpy as np
import paho.mqtt.client as mqtt
from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg


class Ring:
    def __init__(self, n, fill=0.0):
        self.n = n
        self.buf = np.full(n, fill, dtype=float)
        self.i = 0

    def push(self, x):
        self.buf[self.i] = x
        self.i = (self.i + 1) % self.n

    def snapshot(self):
        i = self.i
        return np.concatenate((self.buf[i:], self.buf[:i]))


def makeMqttClient(host, port, topic, ring):
    def onConnect(client, userdata, flags, reasonCode, properties):
        print("connected to broker (", reasonCode, "), subscribing to", topic)
        client.subscribe(topic)

    def onMessage(client, userdata, message):
        try:
            ring.push(int(message.payload.split(b',')[-1]))
        except ValueError:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = onConnect
    client.on_message = onMessage
    client.connect(host, port, keepalive=60)
    client.loop_start()
    return client


class Monitor(QtWidgets.QMainWindow):
    def __init__(self, ring, fs, seconds, yMin, yMax):
        super().__init__()
        self.ring = ring
        self.timeAxis = np.arange(ring.n) / fs

        self.setWindowTitle('Live EMG  (over MQTT)')
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        plotWidget = pg.PlotWidget()
        self.setCentralWidget(plotWidget)
        plotWidget.setYRange(yMin, yMax)
        plotWidget.setXRange(0, seconds)
        plotWidget.disableAutoRange()
        plotWidget.showGrid(x=False, y=True, alpha=0.25)
        plotWidget.setLabel('bottom', 'seconds')
        plotWidget.setLabel('left', 'ADC value (0..4095)')
        self.curve = plotWidget.plot(pen=pg.mkPen('#2980b9', width=2))

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updateView)
        self.timer.start(30)

    def updateView(self):
        self.curve.setData(self.timeAxis, self.ring.snapshot())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=1883)
    ap.add_argument('--topic', default='emg/forearm')
    ap.add_argument('--fs', type=float, default=200.0)
    ap.add_argument('--seconds', type=float, default=5.0)
    ap.add_argument('--ymin', type=float, default=1000.0)
    ap.add_argument('--ymax', type=float, default=2500.0)
    args = ap.parse_args()

    n = int(args.fs * args.seconds)
    ring = Ring(n, fill=(args.ymin + args.ymax) / 2)

    client = makeMqttClient(args.host, args.port, args.topic, ring)

    app = QtWidgets.QApplication(sys.argv)
    win = Monitor(ring, args.fs, args.seconds, args.ymin, args.ymax)
    win.resize(1000, 500)
    win.show()
    try:
        app.exec()
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == '__main__':
    main()
