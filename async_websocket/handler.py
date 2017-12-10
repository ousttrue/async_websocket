from logging import getLogger
logger = getLogger(__name__)

import asyncio
import struct
from abc import ABCMeta, abstractmethod
from typing import List

from .exception import AsyncWebsocketError
from .connection import AsyncWebsocketConnection
from .constants import OPCODE, CONSTANTS
from .masking import mask


class AsyncWebsocketCallbackBase(metaclass=ABCMeta):
    @abstractmethod
    def on_client_connected(self, ws: AsyncWebsocketConnection)->None:
        pass

    @abstractmethod
    def on_client_left(self, ws: AsyncWebsocketConnection)->None:
        pass

    @abstractmethod
    def on_bytes_message_received(self, ws: AsyncWebsocketConnection, msg: bytes)->None:
        pass

    @abstractmethod
    def on_text_message_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
        pass

    @abstractmethod
    def on_ping_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
        pass

    @abstractmethod
    def on_pong_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
        pass


class AsyncWebsocketHandler:

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 callbacks: AsyncWebsocketCallbackBase,
                 reader: asyncio.streams.StreamReader,
                 client: AsyncWebsocketConnection)->None:
        self.loop = loop
        self.callbacks = callbacks
        self.reader = reader
        self.client = client

        self.keep_alive = True
        self.valid_client = True

        self.continuation: List[bytes] = []

    def __str__(self)->str:
        if self.client:
            return str(self.client)
        else:
            return super().__str__()

    async def handle(self)->None:
        try:
            self.callbacks.on_client_connected(self.client)
            while self.keep_alive:
                await self.read_next_message()
        except AsyncWebsocketError as ex:
            logger.error(str(ex))
        except Exception as ex:
            logger.error(str(ex))

        #logger.warning('end')
        self.callbacks.on_client_left(self.client)

    async def read_next_message(self)->None:
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
        b1, b2 = await self.reader.read(2)
        fin = b1 & CONSTANTS.FIN
        opcode = OPCODE(b1 & CONSTANTS.OPCODE)
        masked = b2 & CONSTANTS.MASKED
        payload_length = b2 & CONSTANTS.PAYLOAD_LEN

        if opcode == OPCODE.CLOSE_CONN:
            logger.debug("Client asked to close connection.")
            self.keep_alive = False
            return

        if payload_length == 126:
            data2 = await self.reader.read(2)
            payload_length = struct.unpack(">H", data2)[0]
        elif payload_length == 127:
            data8 = await self.reader.read(8)
            payload_length = struct.unpack(">Q", data8)[0]

        if masked:
            masks = await self.reader.read(4)

        remain_size = payload_length
        buffer_size = 1024 * 1024
        buffer_list = []
        while remain_size > 0:
            read_size = buffer_size
            if read_size > remain_size:
                read_size = remain_size
            buffer = await self.reader.read(read_size)
            buffer_list.append(buffer)
            remain_size -= len(buffer)

        payload = b''.join(buffer_list)
        if len(payload) != payload_length:
            logger.error('invalid size %d <=> %d',
                         len(payload), payload_length)

        if masked:
            decoded = mask(masks, payload)
        else:
            decoded = payload

        self.continuation.append(decoded)
        if not fin:
            if opcode != OPCODE.CONTINUATION:
                raise AsyncWebsocketError('opcode should OPCODE_CONTINUATION')
            return

        msg = self.continuation[0] if len(
            self.continuation) == 1 else b''.join(self.continuation)
        self.continuation.clear()

        if opcode == OPCODE.BINARY:
            self.callbacks.on_bytes_message_received(self.client, msg)
        elif opcode == OPCODE.TEXT:
            self.callbacks.on_text_message_received(
                self.client, msg.decode('utf-8'))
        elif opcode == OPCODE.PING:
            self.callbacks.on_ping_received(self.client, msg.decode('utf-8'))
        elif opcode == OPCODE.PONG:
            self.callbacks.on_pong_received(self.client, msg.decode('utf-8'))
        else:
            raise AsyncWebsocketError(
                "Unknown opcode %#x." % opcode.value)
