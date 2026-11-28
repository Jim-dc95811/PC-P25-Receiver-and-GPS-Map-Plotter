# nmea_gps.py -- sealed NMEA serial-GPS reader for MY POSITION.
#
# Reads a plain GPS that streams standard NMEA ($GPGGA/$GNGGA, or RMC) over a USB
# serial COM port -- e.g. a Garmin GPS 18x PC/LVC, or a $15 u-blox USB puck -- and
# hands back lat/lon/fix. This is the COM-port cousin of garmin_usb.py (which speaks
# Garmin's private BINARY protocol); between them the receiver reads either kind.
#
# Read-only by design: it OPENS the port and listens; it never writes to the GPS.
# The NMEA parse is the same proven one used on the Traveler's serial GPS path.
import time

try:
    import serial
    from serial.tools import list_ports
    HAVE = True
except Exception:
    HAVE = False

DEFAULT_BAUDS = [9600, 4800, 38400, 19200, 57600, 115200]


def _parse_gga(f):
    # $xxGGA,time,lat,N,lon,W,fixqual,sats,hdop,alt,M,...
    if len(f) < 7 or f[0][-3:] != "GGA" or not f[2] or not f[4]:
        return None
    try:
        lat = int(f[2][:2]) + float(f[2][2:]) / 60.0
        if f[3] == "S":
            lat = -lat
        lon = int(f[4][:3]) + float(f[4][3:]) / 60.0
        if f[5] == "W":
            lon = -lon
        fix = int(f[6] or "0")                 # 0 = invalid, 1 = GPS, 2 = DGPS ...
    except Exception:
        return None
    return dict(lat=lat, lon=lon, fix=fix)


def _parse_rmc(f):
    # $xxRMC,time,status,lat,N,lon,W,...   status A = valid, V = void
    if len(f) < 7 or f[0][-3:] != "RMC" or f[2] != "A" or not f[3] or not f[5]:
        return None
    try:
        lat = int(f[3][:2]) + float(f[3][2:]) / 60.0
        if f[4] == "S":
            lat = -lat
        lon = int(f[5][:3]) + float(f[5][3:]) / 60.0
        if f[6] == "W":
            lon = -lon
    except Exception:
        return None
    return dict(lat=lat, lon=lon, fix=1)


def parse_nmea(line):
    line = line.strip()
    if not line.startswith("$"):
        return None
    f = line.split(",")
    return _parse_gga(f) or _parse_rmc(f)


def _emits_nmea(port, baud, seconds=2.5):
    """True if this port/baud streams GGA or RMC within a couple of seconds."""
    try:
        s = serial.Serial(port, baud, timeout=0.4)
    except Exception:
        return False
    data = b""
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            data += s.read(256)
            if b"GGA," in data or b"RMC," in data:
                return True
    finally:
        try:
            s.close()
        except Exception:
            pass
    return (b"GGA," in data) or (b"RMC," in data)


def find_port(hint=None, bauds=None):
    """Return (port, baud) of the first COM port streaming NMEA, or None.
    hint may be 'COM6' or 'COM6:9600' to force a port (and optional baud)."""
    if not HAVE:
        return None
    bauds = bauds or DEFAULT_BAUDS
    if hint:
        p, b = hint, None
        if ":" in hint:
            p, bs = hint.split(":", 1)
            try:
                b = int(bs)
            except Exception:
                b = None
        for baud in ([b] if b else bauds):
            if _emits_nmea(p, baud):
                return (p, baud)
        return None
    try:
        ports = [pp.device for pp in list_ports.comports()]
    except Exception:
        ports = []
    for p in ports:
        for baud in bauds:
            if _emits_nmea(p, baud):
                return (p, baud)
    return None


class NmeaGPS:
    """Open a known NMEA COM port and read fixes. read_fix() returns the most
    recent dict(lat, lon, fix) seen since the last call, or None."""

    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.s = None
        self._buf = b""

    def open(self):
        self.s = serial.Serial(self.port, self.baud, timeout=0.5)

    def read_fix(self):
        chunk = self.s.read(512)
        if chunk:
            self._buf += chunk
        best = None
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            try:
                fx = parse_nmea(line.decode("latin-1", "replace"))
            except Exception:
                fx = None
            if fx:
                best = fx
        if len(self._buf) > 4096:            # never let a stuck line grow unbounded
            self._buf = self._buf[-1024:]
        return best

    def close(self):
        try:
            if self.s:
                self.s.close()
        except Exception:
            pass
