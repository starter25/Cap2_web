from __future__ import annotations

import json
import socket
from typing import Any


class UnityBioSender:
    def __init__(self, host: str, port: int) -> None:
        self.host = str(host)
        self.port = int(port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.sock.sendto(data, (self.host, self.port))

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass
