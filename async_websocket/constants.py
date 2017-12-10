from enum import IntFlag, IntEnum


class CONSTANTS(IntFlag):
    FIN = 0x80
    OPCODE = 0x0f
    MASKED = 0x80
    PAYLOAD_LEN = 0x7f
    PAYLOAD_LEN_EXT16 = 0x7e
    PAYLOAD_LEN_EXT64 = 0x7f


class OPCODE(IntFlag):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE_CONN = 0x8
    PING = 0x9
    PONG = 0xA


class CLOSESTATUS(IntEnum):
    NORMAL = 1000
