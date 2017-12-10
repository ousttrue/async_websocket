import array

try:
    #
    # https://github.com/methane/wsaccel
    #
    # If wsaccel is available we use compiled routines to mask data.
    from wsaccel.xormask import XorMaskerSimple

    def mask(masks: bytes, payload: bytes)->bytes:
        return XorMaskerSimple(masks).process(payload)

except ImportError:
    # wsaccel is not available, we rely on python implementations.
    def mask(masks: bytes, payload: bytes)->bytes:
        _m = array.array("B", masks)
        _d = array.array("B", payload)
        length = len(_d)
        for i in range(length):
            _d[i] ^= _m[i % 4]
        return _d.tobytes()
