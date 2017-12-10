from logging import getLogger
logger = getLogger(__name__)


import asyncio
from .exception import AsyncWebsocketError
from .handler import AsyncWebsocketCallbackBase, AsyncWebsocketHandler
from .connection import AsyncWebsocketConnection
from .handshake import make_handshake_request


async def client_connect_async(loop: asyncio.AbstractEventLoop,
                               callbacks: AsyncWebsocketCallbackBase,
                               host: str, port: int, path: str)->None:
    #parsed = urlparse(url)
    logger.debug('connect %s:%s%s', host, port, path)
    reader, writer = await asyncio.open_connection(
        host=host, port=port, loop=loop)

    hostport_bytes = f'{host}:{port}'.encode('utf-8')
    path_bytes = (path or '/').encode('utf-8')

    # Handshake
    header_str = make_handshake_request(hostport_bytes, path_bytes)
    writer.write(header_str)

    # http response
    line = await reader.readline()
    splited = line.decode('utf-8').split(' ', 2)
    if len(splited) != 3:
        raise AsyncWebsocketError('not http ?')

    _http_version, status_code, _status = splited
    if int(status_code) != 101:
        raise AsyncWebsocketError('fail to switch: %s' % line)

    while True:
        line = await reader.readline()
        if line == b'\r\n':
            break
        logger.debug('%s', line)

    logger.debug('switch to websocket')

    # WebSocket
    client = AsyncWebsocketConnection(host, port, writer, True)
    ws = AsyncWebsocketHandler(loop, callbacks, reader, client)
    await ws.handle()
