from logging import getLogger
logger = getLogger(__name__)

import asyncio

from async_websocket import (
    AsyncWebsocketCallbackBase, AsyncWebsocketConnection, client_connect_async)


class EchoClient(AsyncWebsocketCallbackBase):
    def on_client_connected(self, ws: AsyncWebsocketConnection)->None:
        logger.debug('%s', ws)
        ws.send_text('hello')

    def on_client_left(self, ws: AsyncWebsocketConnection)->None:
        logger.debug('%s', ws)

    def on_bytes_message_received(self, ws: AsyncWebsocketConnection, msg: bytes)->None:
        logger.debug('%s <= %s', msg, ws)

    def on_text_message_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
        logger.debug('%s <= %s', msg, ws)
        ws.send_close()

    def on_ping_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
        logger.debug('%s <= %s', msg, ws)

    def on_pong_received(self, ws: AsyncWebsocketConnection, msg: str)->None:
        logger.debug('%s <= %s', msg, ws)


def main(host: str, port: int, path: str)->None:
    from logging import basicConfig, DEBUG
    basicConfig(
        level=DEBUG,
        datefmt='%H:%M:%S',
        format='%(asctime)s[%(levelname)s][%(name)s.%(funcName)s] %(message)s'
    )

    loop = asyncio.get_event_loop()

    callbacks = EchoClient()

    task = asyncio.ensure_future(
        client_connect_async(loop, callbacks, host, port, path), loop=loop)
    loop.run_until_complete(task)
    logger.debug('end')


if __name__ == '__main__':
    main('127.0.0.1', 8080, '/')
