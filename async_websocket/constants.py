from enum import IntFlag, IntEnum


class CONSTANTS(IntFlag):
    '''
    +-+-+-+-+-------+-+-------------+-------------------------------+
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-------+-+-------------+-------------------------------+
    |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
    |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
    |N|V|V|V|       |S|             |   (if payload len==126/127)   |
    | |1|2|3|       |K|             |                               |
    +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
    |     Extended payload length continued, if payload len == 127  |
    + - - - - - - - - - - - - - - - +-------------------------------+
    |                     Payload Data continued ...                |
    +---------------------------------------------------------------+
    '''
    FIN = 0x80 # 0
    OPCODE = 0x0f # 0
    MASKED = 0x80 # 1
    PAYLOAD_LEN = 0x7f # 1
    PAYLOAD_LEN_EXT16 = 0x7e # 126
    PAYLOAD_LEN_EXT64 = 0x7f # 127


class OPCODE(IntFlag):
    '''
    https://tools.ietf.org/html/rfc6455#section-11.8
    '''
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE_CONN = 0x8
    PING = 0x9
    PONG = 0xA


class CLOSESTATUS(IntEnum):
    '''
    https://tools.ietf.org/html/rfc6455#section-11.7
    '''
    NORMAL = 1000
