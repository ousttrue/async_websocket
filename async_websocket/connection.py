import struct
from .constants import OPCODE, CONSTANTS, CLOSESTATUS


class AsyncWebsocketConnection:
    def __init__(self, host: str, port: int, writer)->None:
        self.host = host
        self.port = port
        self.writer = writer

    def __str__(self)->str:
        return f'({self.host}:{self.port})'

    def send_pong(self, message: str)->None:
        self.send_text(message, OPCODE.PONG)

    def send_text(self, message: str, opcode: OPCODE = OPCODE.TEXT)->None:
        self.send(message.encode('utf-8'), opcode)

    def send_close(self, status: CLOSESTATUS = CLOSESTATUS.NORMAL, reason: bytes = b"")->None:
        self.send(struct.pack('!H', status) + reason, OPCODE.CLOSE_CONN)

    def send(self, payload: bytes, opcode: OPCODE = OPCODE.BINARY)->None:
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
        header = bytearray()
        payload_length = len(payload)

        # Normal payload
        if payload_length <= 125:
            header.append(CONSTANTS.FIN | opcode)
            header.append(payload_length)

        # Extended payload
        elif payload_length >= 126 and payload_length <= 65535:
            header.append(CONSTANTS.FIN | opcode)
            header.append(CONSTANTS.PAYLOAD_LEN_EXT16)
            header.extend(struct.pack(">H", payload_length))

        # Huge extended payload
        elif payload_length < 18446744073709551616:
            header.append(CONSTANTS.FIN | opcode)
            header.append(CONSTANTS.PAYLOAD_LEN_EXT64)
            header.extend(struct.pack(">Q", payload_length))

        else:
            raise Exception(
                "Message is too big. Consider breaking it into chunks.")

        self.writer.write(header)
        self.writer.write(payload)
