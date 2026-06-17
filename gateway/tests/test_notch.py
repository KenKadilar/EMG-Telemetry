import math
from emg_gateway import rbj_notch, Biquad


def peakToPeak(values):
    return max(values) - min(values)


def makeSineWave(freqHz, fs=200.0, count=2000, amplitude=200, baseline=1750):
    # Build `count` samples of a sine wave at freqHz, wobbling +/- amplitude around baseline.
    wave = []
    k = 0
    while k < count:
        angle = 2 * math.pi * freqHz * k / fs    # how far along the wave sample k sits
        wave.append(baseline + amplitude * math.sin(angle))
        k += 1
    return wave


def runThroughNotch(signal, fs=200.0, mains=50.0):
    notch = Biquad(rbj_notch(fs, mains))
    notch.reset(signal[0], signal[0])
    output = []
    i = 0
    while i < len(signal):
        output.append(notch(signal[i]))
        i += 1
    return output[500:]          # skip the first 500 samples: the filter needs time to settle


def test_notch_kills_50hz():
    # a 50 Hz wave (~400 peak-to-peak) goes in; after the notch it should be nearly flat
    out = runThroughNotch(makeSineWave(50))
    assert peakToPeak(out) < 20


def test_notch_keeps_slow_signal():
    # a 5 Hz wave passes through almost untouched (the notch only targets 50 Hz)
    out = runThroughNotch(makeSineWave(5))
    assert peakToPeak(out) > 350


def test_notch_preserves_dc():
    # a flat constant (no wave at all) comes out unchanged
    flatLine = [1750.0] * 600
    out = runThroughNotch(flatLine)
    assert abs(out[-1] - 1750.0) < 1
