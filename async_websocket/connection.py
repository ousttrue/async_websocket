import struct
import asyncio
from .constants import OPCODE, CONSTANTS, CLOSESTATUS
from .masking import mask


class AsyncWebsocketConnection:
    def __init__(self, host: str, port: int,
                 writer: asyncio.streams.StreamWriter, use_mask: bool)->None:
        self.host = host
        self.port = port
        self.writer = writer
        self.use_mask = use_mask

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

        mask_flag = CONSTANTS.MASKED if self.use_mask else CONSTANTS.NOT_MASKED

        # Normal payload
        if payload_length <= 125:
            header.append(CONSTANTS.FIN | opcode)
            header.append(mask_flag | payload_length)

        # Extended payload
        elif payload_length >= 126 and payload_length <= 65535:
            header.append(CONSTANTS.FIN | opcode)
            header.append(mask_flag | CONSTANTS.PAYLOAD_LEN_EXT16)
            header.extend(struct.pack(">H", payload_length))

        # Huge extended payload
        elif payload_length < 18446744073709551616:
            header.append(CONSTANTS.FIN | opcode)
            header.append(mask_flag | CONSTANTS.PAYLOAD_LEN_EXT64)
            header.extend(struct.pack(">Q", payload_length))

        else:
            raise Exception(
                "Message is too big. Consider breaking it into chunks.")

        self.writer.write(header)
        if self.use_mask:
            mask_key = b'0123'
            self.writer.write(mask_key)
            self.writer.write(mask(mask_key, payload))
        else:
            self.writer.write(payload)
