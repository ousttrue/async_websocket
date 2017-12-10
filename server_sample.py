from logging import getLogger
logger = getLogger(__name__)

import asyncio
import pathlib
from typing import List

from async_websocket import (
    AsyncWebsocketCallbackBase, AsyncWebsocketConnection, AsyncWebsocketServer, HttpHeader)


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


class HttpService:
    def __init__(self, path: pathlib.Path)->None:
        self.html_bytes = path.read_bytes()

    async def __call__(self, method: str, path: str, headers: List[HttpHeader],
                       writer: asyncio.streams.StreamWriter)->None:
        writer.write(b'HTTP/1.1 200 OK\r\n')
        writer.write(('Content-Length: %d\r\n' % len(self.html_bytes)).encode('utf-8'))
        writer.write(b'\r\n')
        writer.write(self.html_bytes)
        writer.write_eof()
        await writer.drain()


def main(host: str, port: int)->None:
    from logging import basicConfig, DEBUG
    basicConfig(
        level=DEBUG,
        datefmt='%H:%M:%S',
        format='%(asctime)s[%(levelname)s][%(name)s.%(funcName)s] %(message)s'
    )

    loop = asyncio.get_event_loop()
    document_root = pathlib.Path(__file__).absolute().parent
    http_service = HttpService(document_root / 'client_sample.html')

    # http server
    server = AsyncWebsocketServer(loop, EchoCallbacks(), http_service)
    loop.run_until_complete(asyncio.start_server(
        server.handle, host, port, loop=loop))

    logger.info("listen tcp: %s:%d...", host, port)
    loop.run_forever()
    logger.info('end')


if __name__ == '__main__':
    main('0.0.0.0', 8080)
