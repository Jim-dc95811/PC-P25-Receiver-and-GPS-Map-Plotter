"""
voice_ws.py  -  stream DECODED P25 voice PCM to any browser over a WebSocket.

The combo platter's audio transport. Same proven pattern as the Lookout's
browser audio (hand-rolled WebSocket, raw little-endian int16 PCM, played by the
browser's Web Audio API), but the source here is the pure-Python IMBE decoder,
not a sound card: the decoder pushes 8 kHz PCM with push(), this fans it out to
every connected map tab. No codec, no CDN, no install on the viewer.

- stdlib only (socket + hashlib + base64 + threading).
- server->client frames are unmasked binary (opcode 0x2), 7/16/64-bit length.
- lock-free fan-out with a short per-client send timeout: one stuck listener
  can never stall the decoder or the other viewers.
- isolated: its own thread + port; if audio dies, the map and GPS feed are
  untouched (the same wall the Lookout keeps).
"""
import socket, threading, hashlib, base64, struct, time

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
PORT = 8081
SEND_TIMEOUT = 2.0


def _accept_key(key):
    return base64.b64encode(hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()

def _frame(payload):
    n = len(payload)
    h = bytearray([0x82])                 # FIN + binary opcode
    if n < 126:
        h.append(n)
    elif n < 65536:
        h.append(126); h += struct.pack(">H", n)
    else:
        h.append(127); h += struct.pack(">Q", n)
    return bytes(h) + payload


class VoiceWS:
    def __init__(self, port=PORT):
        self.port = port
        self.clients = set()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.srv = None

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("0.0.0.0", self.port)); srv.listen(8)
        except OSError as e:
            # Keep the wall: if the voice port can't open, voice is simply off -- the map
            # and the position feed are untouched. push() stays a harmless no-op (no clients).
            print("   !! voice port %d unavailable (%s); voice disabled, map/GPS unaffected." % (self.port, e))
            return self
        self.srv = srv
        threading.Thread(target=self._accept, daemon=True).start()
        print("serving voice on ws 0.0.0.0:%d  (the map's Listen button plays this)" % self.port)
        return self

    def _accept(self):
        while not self.stop.is_set():
            try:
                conn, addr = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._handshake, args=(conn, addr), daemon=True).start()

    def _handshake(self, conn, addr):
        try:
            conn.settimeout(5)
            req = b""
            while b"\r\n\r\n" not in req:
                b = conn.recv(1024)
                if not b: conn.close(); return
                req += b
            key = None
            for line in req.decode("latin-1").split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
            if not key:
                conn.close(); return
            resp = ("HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                    "Sec-WebSocket-Accept: %s\r\n\r\n" % _accept_key(key))
            conn.sendall(resp.encode())
            conn.settimeout(SEND_TIMEOUT)
            with self.lock:
                self.clients.add(conn)
            print("   .. a listener connected (%d now)" % len(self.clients))
        except Exception:
            try: conn.close()
            except Exception: pass

    def push(self, pcm_bytes):
        """Fan out one chunk of 16-bit little-endian PCM to every listener."""
        if not pcm_bytes:
            return
        data = _frame(pcm_bytes)
        with self.lock:
            cs = list(self.clients)
        for c in cs:
            try:
                c.sendall(data)
            except Exception:
                try: c.close()
                except Exception: pass
                with self.lock:
                    self.clients.discard(c)

    def listeners(self):
        with self.lock:
            return len(self.clients)

    def shutdown(self):
        self.stop.set()
        try: self.srv.close()
        except Exception: pass
