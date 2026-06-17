from emg_gateway import parseBatch


def test_parse_good_batch():
    assert parseBatch(b"100,5,6,7") == (100, [5, 6, 7])


def test_parse_single_sample():
    assert parseBatch(b"42,1750") == (42, [1750])


def test_parse_rejects_garbage():
    assert parseBatch(b"100") is None          # index but no samples
    assert parseBatch(b"abc,1,2") is None       # non-numeric index
    assert parseBatch(b"100,x,2") is None       # non-numeric sample
