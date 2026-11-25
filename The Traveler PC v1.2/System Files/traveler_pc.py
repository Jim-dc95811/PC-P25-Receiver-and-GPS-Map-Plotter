#!/usr/bin/env python3
"""
THE TRAVELER PC  -  decode P25 Tier-1 GPS location LIVE off the air, on a PC.

The invention set free of the router: on any PC that can run Python, plug a USB
sound card into the radio's detector audio and a Garmin USB into the PC, and the
fleet plots itself on your own offline maps in a browser tab. No box to flash,
no SSH, no network appliance -- that machinery only exists to get the decode onto
a locked-down PC. This is the pure form.

Listens to a radio's DISCRIMINATOR / detector audio on a USB sound card (e.g. a
Sound Blaster taking the Kenwood NX-700 DEO pin 19, radio set WIDE) and decodes
each GPS report as it keys up -- the exact $G?GGA + $PP25,<unit-id> sentence the
fleet transmits -- with no BK base, no SDR, no cooperating gateway. This is the
live counterpart of the recording decoder: same proven decode core, fed by the
sound card instead of a WAV file. (The Traveler reads the air live; it does not
use wave files -- this is that front end.)

Run it, pick the sound-card input, and leave it listening. Every GPS report
prints with a wall-clock time and is appended to a timestamped log in the same
$GNGGA/$PP25 form as the RNDIS reference feed. Ctrl+C to stop.

  --serve [PORT]   also re-serve every decoded report as a plain NMEA-over-TCP
                   feed on PORT (default 10110) -- the SAME wire format the BK
                   bridge puts out, so the Traveler's units_kml reads it
                   unchanged. This makes the decoder a drop-in replacement for
                   the BK RNDIS input: the Universal Traveler.
  --self-gps       fold the PC's own Garmin USB fix into the same feed as the
                   SELF unit "LOOKOUT" (MY POSITION) -- the you-are-here dot.
                   Needs --serve; no-op if no Garmin is present.
  --replay <wav>   run the identical streaming path on a recording (no sound
                   card) -- a self-check; combine with --serve to feed a map.

Needs: numpy, scipy, sounddevice (the .bat installs them). 48 kHz mono capture,
Windows audio 'enhancements' OFF. Read-only throughout -- a radio is never
transmitted to or altered.
"""
import sys, os, time, queue, threading, socket
from datetime import datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from live_core import LiveDecoder

VERSION = "1.2"                   # The Traveler PC
RATE = 48000                      # ask the card for 48 kHz mono (integer 10 sps)
BLOCK = 2048                      # callback block size
DEV_HINTS = ("blaster", "sb play", "usb audio", "usb-audio", "usb pnp", "line (")
SERVE_PORT = 10110                # standard NMEA-0183-over-TCP port (same as bk_bridge)
LINK_EVERY_S = 5.0                # $PLKT,LINK,UP heartbeat cadence (matches bk_bridge)
SELF_ID = "LOOKOUT"               # map.html centers/colors this id as "MY POSITION"
SELF_EVERY_S = 1.5                # throttle self-position broadcasts


# ---------------------------------------------------------------------------
# NMEA-over-TCP server: a byte-for-byte drop-in for bk_bridge's :10110 feed.
# Broadcasts each sentence as "<sentence>\r\n" (ASCII) to every connected client
# and emits a $PLKT,LINK,UP heartbeat so units_kml stays out of its link alarm.
# ---------------------------------------------------------------------------
def _nmea_mk(body):
    g = 0
    for c in body: g ^= ord(c)
    return "$%s*%02X" % (body, g)

class NmeaServer:
    def __init__(self, port=SERVE_PORT):
        self.port = port
        self.clients = set()
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port)); srv.listen(8)
        self.srv = srv
        threading.Thread(target=self._accept, daemon=True).start()
        threading.Thread(target=self._heartbeat, daemon=True).start()
        print("serving NMEA on tcp 0.0.0.0:%d  (the Traveler's units_kml reads this)" % self.port)

    def _accept(self):
        while not self.stop.is_set():
            try:
                conn, addr = self.srv.accept()
            except OSError:
                return
            conn.settimeout(5)
            with self.lock:
                self.clients.add(conn)
            print("   .. map/viewer connected from %s  (%d now)" % (addr[0], len(self.clients)))

    def broadcast(self, sentence):
        data = (sentence + "\r\n").encode("ascii", "replace")
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

    def _heartbeat(self):
        while not self.stop.is_set():
            self.broadcast(_nmea_mk("PLKT,LINK,UP"))
            self.stop.wait(LINK_EVERY_S)


# ---------------------------------------------------------------------------
# MY POSITION: fold the PC's own Garmin USB fix into the SAME :10110 feed as the
# SELF unit, exactly as the box's bridge does. The Garmin reader (garmin_usb.py)
# is a sealed, proven module (Jim's P25 GPS Tracker) -- used untouched. If no
# Garmin / not Windows, this thread just reports unavailable and the map still
# shows the decoded fleet. Read-only: only the standard start/stop-PVT commands.
# ---------------------------------------------------------------------------
def _coords_ok(lat, lon):
    try:
        if lat != lat or lon != lon:            # NaN
            return False
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:  # (0,0)
            return False
        return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
    except Exception:
        return False

def _self_gga(lat, lon):
    la, lo = abs(lat), abs(lon)
    lad, lod = int(la), int(lo)
    lam, lom = (la - lad) * 60.0, (lo - lod) * 60.0
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    t = datetime.utcnow().strftime("%H%M%S.00")
    body = "GPGGA,%s,%02d%08.5f,%s,%03d%08.5f,%s,1,10,0.9,30.0,M,-31.0,M,," % (
        t, lad, lam, ns, lod, lom, ew)
    return _nmea_mk(body)

def _self_gps_loop(server):
    try:
        import garmin_usb
    except Exception as e:
        print("   .. MY POSITION unavailable (no Garmin reader: %s)" % e)
        return
    pp = _nmea_mk("PP25,%s," % SELF_ID)         # self unit id, map shows it as MY POSITION
    last = 0.0
    while True:
        try:
            if not garmin_usb.device_present():
                time.sleep(3.0); continue
            g = garmin_usb.GarminUSB()
            g.open(); g.start_pvt()
            print("   .. MY POSITION: Garmin GPS connected")
            try:
                while True:
                    fx = g.read_fix()
                    # Jim's correction: trust a fix of 1+ (reject only 0, failed-integrity);
                    # a degraded indoor/canopy fix is exactly what a firefighter gets.
                    if fx and fx.get("fix", 0) >= 1 and _coords_ok(fx["lat"], fx["lon"]):
                        now = time.time()
                        if now - last >= SELF_EVERY_S:
                            server.broadcast(_self_gga(fx["lat"], fx["lon"]))
                            server.broadcast(pp)
                            last = now
            finally:
                try: g.stop_pvt(); g.close()
                except Exception: pass
        except Exception as e:
            print("   .. MY POSITION: lost the Garmin (%s); retrying" % e)
            time.sleep(3.0)


def _make_logger():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logpath = os.path.join(HERE, "..", "live_nmea_%s.log" % ts)
    lf = open(logpath, "w", buffering=1)
    return lf, logpath


def run_live(server):
    try:
        import sounddevice as sd
    except Exception as e:
        print("Could not load sounddevice (%s)." % e)
        print("The .bat installs it; if you ran the .py directly: pip install sounddevice")
        sys.exit(1)

    forced = None
    for a in sys.argv[1:]:
        if a.startswith("--device="): forced = int(a.split("=", 1)[1])
    dev, name = pick_device(sd, forced)

    rate = RATE
    try:
        sd.check_input_settings(device=dev, channels=1, samplerate=RATE, dtype="float32")
    except Exception:
        rate = int(sd.query_devices(dev)["default_samplerate"])
        print("Note: device won't do 48 kHz; using its %d Hz." % rate)

    lf, logpath = _make_logger()
    lf.write("# P25 OTA GPS live decode  started %s  device='%s' %d Hz\n"
             % (datetime.now().isoformat(timespec="milliseconds"), name, rate))
    state = {"n": 0}

    def on_report(gga, pp, t_wall):
        state["n"] += 1
        stamp = datetime.fromtimestamp(t_wall).strftime("%H:%M:%S")
        iso = datetime.fromtimestamp(t_wall).isoformat(timespec="milliseconds")
        print("  [%s]  %s   %s" % (stamp, gga, pp or ""))
        lf.write("%s  %s\n" % (iso, gga))
        if pp: lf.write("%s  %s\n" % (iso, pp))
        if server:
            server.broadcast(gga)
            if pp: server.broadcast(pp)

    dec = LiveDecoder(rate, on_report, lambda m: print("   .. %s" % m))
    q = queue.Queue()
    def cb(indata, frames, tinfo, status):
        q.put(indata[:, 0].copy())

    print("The Traveler PC (OTA decode) v%s" % VERSION)
    print("listening on: %s  (%d Hz mono)" % (name, rate))
    print("log: %s" % os.path.abspath(logpath))
    print("waiting for GPS bursts ... (Ctrl+C to stop)\n")

    stop = threading.Event()
    def worker():
        last = time.time()
        while not stop.is_set():
            try: blk = q.get(timeout=0.5)
            except queue.Empty: blk = None
            if blk is not None: dec.feed(blk)
            if time.time() - last > 30:
                last = time.time()
                print("   .. listening (%d report%s so far)" % (state["n"], "" if state["n"] == 1 else "s"))
    th = threading.Thread(target=worker, daemon=True); th.start()
    try:
        with sd.InputStream(device=dev, channels=1, samplerate=rate,
                            dtype="float32", blocksize=BLOCK, callback=cb):
            while True: time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nstopping ...")
    finally:
        stop.set(); th.join(timeout=2); lf.close()
        print("stopped. %d report%s decoded. log: %s"
              % (state["n"], "" if state["n"] == 1 else "s", os.path.abspath(logpath)))


def run_replay(wavpath, server):
    import wave
    w = wave.open(wavpath, "rb"); rate = w.getframerate(); nch = w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768.0
    w.close()
    if nch > 1: x = x[::nch]
    lf, logpath = _make_logger()
    lf.write("# P25 OTA GPS live decode (REPLAY of %s)  %s\n"
             % (os.path.basename(wavpath), datetime.now().isoformat(timespec="milliseconds")))
    state = {"n": 0}
    def on_report(gga, pp, t_wall):
        state["n"] += 1
        print("  report %2d:  %s   %s" % (state["n"], gga, pp or ""))
        lf.write("%s\n" % gga)
        if pp: lf.write("%s\n" % pp)
        if server:
            server.broadcast(gga)
            if pp: server.broadcast(pp)
    dec = LiveDecoder(rate, on_report, lambda m: None)
    print("The Traveler PC (OTA decode) v%s  --  REPLAY mode" % VERSION)
    print("file: %s  (%d Hz, %.1fs)\n" % (os.path.basename(wavpath), rate, len(x) / rate))
    if server: time.sleep(2.0)          # let a viewer connect before we broadcast
    for s in range(0, len(x), BLOCK):
        dec.feed(x[s:s + BLOCK])
    dec.flush()
    lf.close()
    print("\n%d report%s decoded. log: %s" % (state["n"], "" if state["n"] == 1 else "s", os.path.abspath(logpath)))
    if server:
        print("feed staying up (heartbeat) for viewers; Ctrl+C to stop.")
        try:
            while True: time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nstopping ...")


def pick_device(sd, forced=None):
    devs = sd.query_devices()
    ins = [(i, d) for i, d in enumerate(devs) if d["max_input_channels"] > 0]
    if forced is not None:
        return forced, devs[forced]["name"]
    for i, d in ins:
        if any(h in d["name"].lower() for h in DEV_HINTS):
            return i, d["name"]
    print("\nAvailable sound-card inputs:")
    for i, d in ins:
        print("  [%d] %s  (%d ch, %d Hz)" % (i, d["name"], d["max_input_channels"], int(d["default_samplerate"])))
    while True:
        s = input("Enter the number of the input the radio is wired to: ").strip()
        if s.isdigit() and int(s) in [i for i, _ in ins]:
            return int(s), devs[int(s)]["name"]
        print("  not a listed input number; try again.")


def _badge():
    print("=" * 60)
    print("  THE TRAVELER PC   -   Radio  ->  Live Map        v%s" % VERSION)
    print("  P25 GPS off the air . your own offline maps . no cloud")
    print("  built by Claude McNally")
    print("=" * 60)


def main():
    _badge()
    args = sys.argv[1:]
    serve = "--serve" in args
    port = SERVE_PORT
    if serve:
        i = args.index("--serve")
        if i + 1 < len(args) and args[i + 1].isdigit():
            port = int(args[i + 1])
    server = None
    if serve:
        server = NmeaServer(port); server.start()
        if "--self-gps" in args:
            threading.Thread(target=_self_gps_loop, args=(server,), daemon=True).start()
    # replay if a wav was given (--replay <wav> or a bare .wav arg)
    wav = None
    for i, a in enumerate(args):
        if a == "--replay" and i + 1 < len(args): wav = args[i + 1]
        elif a.lower().endswith(".wav"): wav = a
    if wav:
        if not os.path.isfile(wav):
            print("File not found: %s" % wav); sys.exit(1)
        return run_replay(wav, server)
    return run_live(server)


if __name__ == "__main__":
    main()
