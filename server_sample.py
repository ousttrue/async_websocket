from logging import getLogger
logger = getLogger(__name__)

import asyncio
import pathlib

from async_websocket import (
    AsyncWebsocketCallbackBase, AsyncWebsocketConnection, AsyncWebsocketServer,
    HttpService, FileSystemMount)


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



def main(host: str, port: int)->None:
    from logging import basicConfig, DEBUG
    basicConfig(
        level=DEBUG,
        datefmt='%H:%M:%S',
        format='%(asctime)s[%(levelname)s][%(name)s.%(funcName)s] %(message)s'
    )

    loop = asyncio.get_event_loop()
    document_root = pathlib.Path(__file__).absolute().parent

    http_service = HttpService()
    http_service.mount(b'/', FileSystemMount(document_root))

    # http server
    server = AsyncWebsocketServer(loop, EchoCallbacks(), http_service)
    loop.run_until_complete(asyncio.start_server(
        server.handle, host, port, loop=loop))

    logger.info("listen tcp: %s:%d...", host, port)
    loop.run_forever()
    logger.info('end')


if __name__ == '__main__':
    main('0.0.0.0', 8080)
