from logging import getLogger
logger = getLogger(__name__)

import os
from base64 import b64encode
from hashlib import sha1
from binascii import b2a_base64


def make_handshake_response(key: bytes)->bytes:
    '''
    Server
    '''
    GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    hash_value = sha1(key + GUID.encode())
    response_key = b64encode(hash_value.digest()).strip()

    return \
        b'HTTP/1.1 101 Switching Protocols\r\n'\
        b'Upgrade: websocket\r\n'              \
        b'Connection: Upgrade\r\n'             \
        b'Sec-WebSocket-Accept: %b\r\n'        \
        b'\r\n' % response_key


def _create_sec_websocket_key()->bytes:
    '''
    Client
    '''
    s = os.urandom(16)

    MAXLINESIZE = 76  # Excluding the CRLF
    MAXBINSIZE = (MAXLINESIZE // 4) * 3

    """Encode a bytestring into a bytes object containing multiple lines
    of base-64 data."""
    pieces = []
    for i in range(0, len(s), MAXBINSIZE):
        chunk = s[i: i + MAXBINSIZE]
        pieces.append(b2a_base64(chunk))
    return b"".join(pieces)


def make_handshake_request(hostport_bytes: bytes, path_bytes: bytes)->bytes:
    '''
    Client
    '''
    key_bytes = _create_sec_websocket_key().strip()
    logger.debug('handshake...%s', key_bytes)

    headers = [
        b"GET %b HTTP/1.1\r\n" % path_bytes,
        b"Upgrade: websocket\r\n",
        b"Connection: Upgrade\r\n"
        b"Host: %s\r\n" % hostport_bytes,
        b"Sec-WebSocket-Key: %b\r\n" % key_bytes,
        b"Sec-WebSocket-Version: 13\r\n"
        b"\r\n",
    ]
    return b"".join(headers)
