from logging import getLogger
logger = getLogger(__name__)


import asyncio
from typing import Callable, Awaitable, List
from .connection import AsyncWebsocketConnection
from .handler import AsyncWebsocketCallbackBase, AsyncWebsocketHandler
from .http import HttpRequest, HttpHeader
from .exception import AsyncWebsocketError
from .handshake import make_handshake_response


class NoLineError(AsyncWebsocketError):
    pass


HTTP_SERVICE_TYPE = Callable[[
    str, str, str, List[HttpHeader], asyncio.streams.StreamWriter], Awaitable[None]]

class AsyncWebsocketServer:

    def __init__(self, loop: asyncio.AbstractEventLoop,
                 callbacks: AsyncWebsocketCallbackBase,
                 http_service: HTTP_SERVICE_TYPE)->None:
        self.loop = loop
        self.http_service = http_service
        self.callbacks = callbacks

    async def handle(self, reader, writer):

        try:
            # read http request
            request_line = await reader.readline()
            if not request_line:
                raise NoLineError('no line')
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
                    raise AsyncWebsocketError(b"invalid line: " + line)

            if request.get_header(b'upgrade'):
                #
                # websocket handshake
                #
                key = request.get_header(b'sec-websocket-key')
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
                await self.http_service(request.method, request.path, request.headers, writer)

        except NoLineError as ex:
            pass
        except Exception as ex:
            logger.error(ex)

        writer.close()
