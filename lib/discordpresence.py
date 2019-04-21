import json
import struct
import uuid
from abc import ABCMeta, abstractmethod
import os
import socket
import sys

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4

class DiscordIpcError(Exception):
    pass

class DiscordIpcClient():

    """Work with an open Discord instance via its JSON IPC for its rich presence API.

    In a blocking way.
    Classmethod `for_platform`
    will resolve to one of WinDiscordIpcClient or UnixDiscordIpcClient,
    depending on the current platform.
    Supports context handler protocol.
    """

    def __init__(self, client_id):
        self.client_id = client_id
        self._connect()
        self._do_handshake()

    @classmethod
    def for_platform(cls, client_id, platform=sys.platform):
        if platform == 'win32':
            return WinDiscordIpcClient(client_id)
        else:
            return UnixDiscordIpcClient(client_id)

    @abstractmethod
    def _connect(self):
        pass

    def _do_handshake(self):
        ret_op, ret_data = self.send_recv({'v': 1, 'client_id': self.client_id}, op=OP_HANDSHAKE)
        # {'cmd': 'DISPATCH', 'data': {'v': 1, 'config': {...}}, 'evt': 'READY', 'nonce': None}
        if ret_op == OP_FRAME and ret_data['cmd'] == 'DISPATCH' and ret_data['evt'] == 'READY':
            return
        else:
            if ret_op == OP_CLOSE:
                self.close()
            raise RuntimeError(ret_data)

    @abstractmethod
    def _write(self, date):
        pass

    @abstractmethod
    def _recv(self, size):
        pass

    def _recv_header(self):
        header = self._recv_exactly(8)
        return struct.unpack("<II", header)

    def _recv_exactly(self, size):
        buf = b""
        size_remaining = size
        while size_remaining:
            chunk = self._recv(size_remaining)
            buf += chunk
            size_remaining -= len(chunk)
        return buf

    def close(self):
        
        try:
            self.send({}, op=OP_CLOSE)
        finally:
            self._close()

    @abstractmethod
    def _close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self):
        self.close()

    def send_recv(self, data, op=OP_FRAME):
        nonce = data.get('nonce')
        self.send(data, op=op)
        while True:
            # TODO timeout
            reply = self.recv()
            if reply[1].get('nonce') == nonce:
                return reply
            else:
                pass
        return

    def send(self, data, op=OP_FRAME):
        
        data_str = json.dumps(data, separators=(',', ':'))
        data_bytes = data_str.encode('utf-8')
        header = struct.pack("<II", op, len(data_bytes))
        self._write(header)
        self._write(data_bytes)

    def recv(self):
        """Receives a packet from discord.

        Returns op code and payload.
        """
        op, length = self._recv_header()
        payload = self._recv_exactly(length)
        data = json.loads(payload.decode('utf-8'))
        
        return op, data

    def set_activity(self, act):
        data = {
            'cmd': 'SET_ACTIVITY',
            'args': {'pid': os.getpid(),
                     'activity': act},
            'nonce': str(uuid.uuid4())
        }
        return self.send(data)

    def clear_activity(self):
        data = {
            'cmd': 'SET_ACTIVITY',
            'args': {'pid': os.getpid()},
            'nonce': str(uuid.uuid4())
        }
        return self.send(data)


class WinDiscordIpcClient(DiscordIpcClient):

    _pipe_pattern = R'\\?\pipe\discord-ipc-{}'

    def _connect(self):
        for i in range(10):
            path = self._pipe_pattern.format(i)
            try:
                self._f = open(path, "w+b")
            except OSError as e:
                pass
            else:
                break
        else:
            raise DiscordIpcError("Failed to connect to Discord pipe")

        self.path = path

    def _write(self, data):
        self._f.seek(0, 2)
        self._f.write(data)
        self._f.flush()

    def _recv(self, size):
        return self._f.read(size)

    def _close(self):
        self._f.close()


class UnixDiscordIpcClient(DiscordIpcClient):

    def _connect(self):
        self._sock = socket.socket(socket.AF_UNIX)

        for path in self._iter_path_candidates():
            if not os.path.exists(path):
                continue
            try:
                self._sock.connect(path)
            except OSError as e:
                pass
            except Exception as e:
                pass
            else:
                break
        else:
            raise DiscordIpcError("Failed to connect to a Discord pipe")

    @staticmethod
    def _iter_path_candidates():
        env_keys = ('XDG_RUNTIME_DIR', 'TMPDIR', 'TMP', 'TEMP')
        for env_key in env_keys:
            dir_path = os.environ.get(env_key)
            if dir_path:
                break
        else:
            dir_path = "/tmp"
        snap_path = os.path.join(dir_path, "snap.discord")
        if os.path.exists(snap_path):
            for i in range(10):
                yield os.path.join(snap_path, "discord-ipc-{}".format(i))
        for i in range(10):
            yield os.path.join(dir_path, "discord-ipc-{}".format(i))

    def _write(self, data):
        self._sock.sendall(data)

    def _recv(self, size):
        return self._sock.recv(size)

    def _close(self):
        self._sock.close()