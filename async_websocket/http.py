from typing import Dict, List, NamedTuple, Generator, Any
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


def bytes_http_response(data: bytes)->Generator[bytes, None, None]:
    yield b'HTTP/1.1 200 OK\r\n'
    yield b'Content-Length: %d\r\n' % len(data)
    yield b'\r\n'
    yield data


def not_found_response()->Generator[bytes, None, None]:
    data=b'file not found'
    yield b'HTTP/1.1 404 NOT FOUND\r\n'
    yield b'Content-Length: %d\r\n' % len(data)
    yield b'\r\n'
    yield data


def internal_error_response()->Generator[bytes, None, None]:
    yield b"HTTP/1.1 500 ERROR\r\n"
    yield b"\r\n"


def path_match_mount(path: bytes, mount: bytes)->bool:
    return path.startswith(mount)


class HttpService:
    def __init__(self)->None:
        self.mount_map: Dict[bytes, Any] = {}

    def mount(self, path: bytes, service)->None:
        if not path or (path.startswith(b'/') and path.endswith(b'/')):
            self.mount_map[path] = service
        else:
            raise Exception('mount path must startswith "/" and endswith "/": %s' % path)

    def __call__(self, method: bytes,
                 path: bytes, headers: List[HttpHeader])->Generator[bytes, None, None]:
        for k, v in self.mount_map.items():
            if path_match_mount(path, k):
                relative_path = path[len(k):]
                yield from v(method, relative_path, headers)
                return

        yield from internal_error_response()


class FileSystemMount:
    def __init__(self, base_path: pathlib.Path)->None:
        self.base_path = base_path

    def __call__(self, method: bytes, relative: bytes, headers)->Generator[bytes, None, None]:
        if method != b'GET':
            yield from internal_error_response()
            return

        if relative == b'':
            relative = b'index.html'
        elif relative.endswith(b'/'):
            relative = relative + b'index.html'

        path = self.base_path / relative.decode()
        if not path.is_file():
            yield from not_found_response()
            return

        try:
            yield from bytes_http_response(path.read_bytes())
            return

        except Exception:
            yield from not_found_response()
            return
