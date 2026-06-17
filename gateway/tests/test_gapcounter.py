from emg_gateway import GapCounter


def test_contiguous_batches_no_drops():
    g = GapCounter()
    g.update(0, 20)     # indices 0..19
    g.update(20, 20)    # 20..39
    g.update(40, 20)    # 40..59
    assert g.dropped == 0
    assert g.totalSampleCount == 60
    assert g.lossPercent() == 0.0


def test_gap_is_counted():
    g = GapCounter()
    g.update(0, 20)     # 0..19
    g.update(40, 20)    # skipped 20..39 -> 20 lost
    assert g.dropped == 20


def test_restart_resets():
    g = GapCounter()
    g.update(1000, 20)
    g.update(0, 20)     # index jumped backwards (ESP32 reboot) -> reset, not a huge drop
    assert g.dropped == 0
    assert g.totalSampleCount == 20
