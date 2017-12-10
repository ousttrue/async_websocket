from base64 import b64encode
from hashlib import sha1


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
