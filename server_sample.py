from logging import getLogger
logger = getLogger(__name__)

import asyncio
import struct
import array
import pathlib
from base64 import b64encode
from hashlib import sha1
from enum import IntFlag
from abc import ABCMeta, abstractmethod
from typing import Sequence, List


try:
    # If wsaccel is available we use compiled routines to mask data.
    from wsaccel.xormask import XorMaskerSimple

    def _mask(_m, _d):
        return XorMaskerSimple(_m).process(_d)

except ImportError:
    # wsaccel is not available, we rely on python implementations.
    def _mask(_m, _d):
        for i in range(len(_d)):
            _d[i] ^= _m[i % 4]
        return _d.tobytes()


class AsyncWebsocketError(Exception):
    pass


class constants(IntFlag):
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


def make_handshake_response(key: bytes)->bytes:
    GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    hash_value = sha1(key + GUID.encode())
    response_key = b64encode(hash_value.digest()).strip()

    return \
        b'HTTP/1.1 101 Switching Protocols\r\n'\
        b'Upgrade: websocket\r\n'              \
        b'Connection: Upgrade\r\n'             \
        b'Sec-WebSocket-Accept: %b\r\n'        \
        b'\r\n' % response_key


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

    def send_close(self, status=1000, reason=b""):
        #if status < 0 or status >= ABNF.LENGTH_16:
        #    raise ValueError("code is invalid range")
        #self.connected = False
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
            header.append(constants.FIN | opcode)
            header.append(payload_length)

        # Extended payload
        elif payload_length >= 126 and payload_length <= 65535:
            header.append(constants.FIN | opcode)
            header.append(constants.PAYLOAD_LEN_EXT16)
            header.extend(struct.pack(">H", payload_length))

        # Huge extended payload
        elif payload_length < 18446744073709551616:
            header.append(constants.FIN | opcode)
            header.append(constants.PAYLOAD_LEN_EXT64)
            header.extend(struct.pack(">Q", payload_length))

        else:
            raise Exception(
                "Message is too big. Consider breaking it into chunks.")

        self.writer.write(header)
        self.writer.write(payload)


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


class HttpRequest:
    def __init__(self, line):
        self.method, self.path, self.version = line.split()
        self.headers = {}

    def push_line(self, line):
        kv = line.split(b':', 1)
        self.headers[kv[0].strip().lower()] = kv[1].strip()

    def response(self, document_root: pathlib.Path)->Sequence[bytes]:
        if self.method != b'GET':
            return (b"HTTP/1.1 500 ERROR\r\n",
                    b"\r\n")

        request_path = 'index.html' if self.path == b'/' else self.path[1:].decode(
        )
        path = document_root / request_path
        if path.is_dir():
            #logger.info('is_dir')
            path = path / 'index.html'
        if not path.is_file():
            return (b"HTTP/1.1 404 ERROR\r\n",
                    b"\r\n")

        try:
            data = path.read_bytes()
            return (b"HTTP/1.1 200 OK\r\n",
                    b"Content-Type: text/html; charset=utf-8\r\n",
                    b"Content-Length: %d\r\n" % len(data),
                    b"\r\n",
                    data)
        except Exception:
            return (b"HTTP/1.1 500 ERROR\r\n",
                    b"\r\n")


class AsyncWebsocketHandler:

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 callbacks: AsyncWebsocketCallbackBase, reader, client: AsyncWebsocketConnection)->None:
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
        fin = b1 & constants.FIN
        opcode = OPCODE(b1 & constants.OPCODE)
        masked = b2 & constants.MASKED
        payload_length = b2 & constants.PAYLOAD_LEN

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
            _m = array.array("B", masks)
            _d = array.array("B", payload)
            decoded = _mask(_m, _d)
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


class AsyncWebsocketServer:

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 callbacks: AsyncWebsocketCallbackBase, http_service)->None:
        self.loop = loop
        self.http_service = http_service
        self.callbacks = callbacks

    async def handle(self, reader, writer):

        try:
            # read http request
            request_line = await reader.readline()
            if not request_line:
                raise AsyncWebsocketError('no line')
                #return

            #logger.debug(line)
            request = HttpRequest(request_line)
            while True:
                line = await reader.readline()
                if line[-2] == 0x0d and line[-1] == 0x0a:
                    if len(line) == 2:
                        break
                    request.push_line(line[:-2])
                else:
                    raise Exception(b"invalid line: " + line)

            if b'upgrade' in request.headers:
                #
                # websocket handshake
                #
                key = request.headers[b'sec-websocket-key']
                response = make_handshake_response(key)
                writer.write(response)
                await writer.drain()

                #
                # start websocket
                #
                client = AsyncWebsocketConnection(
                    *writer.transport.get_extra_info('peername'), writer)
                handler = AsyncWebsocketHandler(
                    self.loop, self.callbacks, reader, client)
                await handler.handle()
            else:
                #
                # http service
                #
                await self.http_service(request, writer)

        except Exception as ex:
            if str(ex) != 'no line':
                logger.error(ex)

        writer.close()


def main()->None:
    from logging import basicConfig, DEBUG
    basicConfig(
        level=DEBUG,
        datefmt='%H:%M:%S',
        format='%(asctime)s[%(levelname)s][%(name)s.%(funcName)s] %(message)s'
    )

    loop = asyncio.get_event_loop()

    document_root = pathlib.Path(__file__).absolute().parent
    html_bytes = (document_root / 'client_sample.html').read_bytes()
    async def http_service(request, writer):
        writer.write(b'HTTP/1.1 200 OK\r\n')
        writer.write(('Content-Length: %d\r\n' % len(html_bytes)).encode('utf-8'))
        writer.write(b'\r\n')
        writer.write(html_bytes)
        writer.write_eof()
        await writer.drain()

    class EchoCallbacks(AsyncWebsocketCallbackBase):
        def on_client_connected(self, ws: AsyncWebsocketConnection)->None:
            logger.debug('%s', ws)

        def on_client_left(self, ws: AsyncWebsocketConnection)->None:
            logger.debug('%s', ws)

        def on_bytes_message_received(self, ws: AsyncWebsocketConnection, msg: bytes)->None:
            logger.debug('%s <= %s', msg, ws)

        def on_text_message_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
            logger.debug('%s <= %s', msg, ws)
            response = 'echoback: %s' % msg
            logger.debug('%s => %s', response, ws)
            ws.send_text(response)

        def on_ping_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
            logger.debug('%s <= %s', msg, ws)

        def on_pong_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
            logger.debug('%s <= %s', msg, ws)

    callbacks = EchoCallbacks()

    # http server
    host = '127.0.0.1'
    port = 8080
    logger.info("listen tcp: %s:%d...", host, port)
    server = AsyncWebsocketServer(loop, callbacks, http_service)
    server_task = asyncio.start_server(
        server.handle, '0.0.0.0', port, loop=loop)

    loop.run_until_complete(server_task)

    logger.info('start')
    loop.run_forever()
    logger.info('end')


if __name__ == '__main__':
    main()
