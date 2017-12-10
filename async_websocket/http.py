from typing import List, Sequence, NamedTuple
import pathlib


class HttpHeader(NamedTuple):
    key: bytes
    value: bytes


class HttpRequest:
    def __init__(self, line: bytes)->None:
        self.method, self.path, self.version = line.split()
        self.headers: List[HttpHeader] = []

    def push_line(self, line: bytes)->None:
        kv = line.split(b':', 1)
        self.headers.append(HttpHeader(kv[0].strip().lower(), kv[1].strip()))

    def get_header(self, key: bytes)->bytes:
        for x in self.headers:
            if x.key == key:
                return x.value
        return None

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
