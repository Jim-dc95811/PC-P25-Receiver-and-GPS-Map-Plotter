#!/usr/bin/env python3
"""
Claude McNally's PC P25 Receiver -- Self-Check.

Walks the whole chain and prints one line per piece: [PASS] / [WARN] / [FAIL],
each with a one-line fix. At the end it says whether you're ready to run.

What it inspects, in order:
  1. Python version
  2. The package files (all of System Files, and the Start .bat)
  3. The libraries the receiver needs (numpy, scipy, sounddevice, pyserial)
  4. Internet -- only matters for the ONE-TIME library install; if something is
     missing it offers to fetch it (online) or warns you can't (offline)
  5. The decode engine imports cleanly
  6. Audio in -- takes a 1-second listen and reports the level (open-squelch
     hiss should sit around 60% peak; silent = cable, clipping = too hot)
  7. GPS -- serial COM ports and/or a Garmin USB puck (optional)
  8. The three network ports the receiver uses (8080 map / 10110 feed / 8081 voice)

Pure-ish: only uses the receiver's own libraries, nothing extra to install.
Runs on the operator's PC; the audio/GPS lines need Windows + the real gear.
"""

import sys, os, socket, subprocess
from pathlib import Path

VERSION = "1.0"

# ---- where things are -------------------------------------------------------
HERE      = Path(__file__).resolve().parent          # Troubleshooting/System Files
PKG_ROOT  = HERE.parents[1]                           # the receiver package root
ENGINE    = PKG_ROOT / "System Files"                 # the receiver's own files
START_BAT = "Start Claude McNally P25 Receiver.bat"

REQUIRED_FILES = [
    "traveler_pc.py", "traveler_launch.pyw", "live_core.py", "combo_core.py",
    "frontend.py", "fsk4_demod.py", "framer.py", "pdu_blocks.py", "bch_nid.py",
    "fsk4_taps.npy", "imbe_decode.py", "imbe_tables.py", "voice_frames.py",
    "voice_ws.py", "garmin_usb.py", "nmea_gps.py", "units_kml.py",
    "pick_maps.py", "qr_svg.py", "map.html", "leaflet.js", "leaflet.css",
]
# import-name -> pip-name  (the four the receiver installs on first run)
LIBS = {"numpy": "numpy", "scipy": "scipy",
        "sounddevice": "sounddevice", "serial": "pyserial"}
PORTS = [(8080, "map page"), (10110, "unit feed"), (8081, "voice")]
DEV_HINTS = ("ufo", "blaster", "sb play", "usb audio", "usb-audio", "usb pnp", "line (")

# ---- reporting --------------------------------------------------------------
_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
def say(level, label, detail=""):
    _counts[level] = _counts.get(level, 0) + 1
    tag = {"PASS": "[ PASS ]", "WARN": "[ WARN ]", "FAIL": "[ FAIL ]", "INFO": "[ INFO ]"}[level]
    line = "%s  %s" % (tag, label)
    print(line)
    if detail:
        for d in detail.split("\n"):
            print("          %s" % d)

def rule():  print("-" * 64)

# ---- 1. Python --------------------------------------------------------------
def check_python():
    v = sys.version_info
    vs = "%d.%d.%d" % (v.major, v.minor, v.micro)
    if v.major == 3 and v.minor >= 8:
        say("PASS", "Python %s" % vs)
    elif v.major == 3:
        say("WARN", "Python %s" % vs, "Older than 3.8 -- usually fine, but 3.8+ is recommended.")
    else:
        say("FAIL", "Python %s" % vs, "Install Python 3 from python.org (tick 'Add python.exe to PATH').")

# ---- 2. Package files -------------------------------------------------------
def check_files():
    if not ENGINE.is_dir():
        say("FAIL", "Package files", "Can't find the 'System Files' folder next to this package.\n"
            "Keep the Troubleshooting folder INSIDE the receiver folder.")
        return
    missing = [f for f in REQUIRED_FILES if not (ENGINE / f).is_file()]
    bat_ok  = (PKG_ROOT / START_BAT).is_file()
    if not missing and bat_ok:
        say("PASS", "Package files (all %d present)" % (len(REQUIRED_FILES) + 1))
    else:
        d = []
        if missing: d.append("Missing from System Files: " + ", ".join(missing))
        if not bat_ok: d.append("Missing: " + START_BAT)
        d.append("Re-extract the whole zip (or re-download the folder); don't move files out.")
        say("FAIL", "Package files", "\n".join(d))

# ---- 3 + 4. Libraries and internet (with offer-to-install) ------------------
def _have(mod):
    try:
        __import__(mod); return True
    except Exception:
        return False

def _online(host="pypi.org", port=443, timeout=4):
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False

def check_libs_and_internet():
    missing = [m for m in LIBS if not _have(m)]
    online = _online()
    if not missing:
        say("PASS", "Libraries (numpy, scipy, sounddevice, pyserial)")
        say("INFO", "Internet: " + ("connected" if online else "offline"),
            "Not needed -- everything's installed; the receiver runs fully offline.")
        return
    # something's missing -> this is the thing that bites people
    pip_names = [LIBS[m] for m in missing]
    say("WARN", "Libraries missing: " + ", ".join(pip_names))
    if not online:
        say("FAIL", "Internet: offline -- can't install the missing libraries",
            "The first run needs the internet ONCE to fetch these; after that it's\n"
            "fully offline. Connect to any network, then run this check again.")
        return
    say("INFO", "Internet: connected")
    try:
        ans = input("          Install the missing libraries now? [Y/n] ").strip().lower()
    except EOFError:
        ans = "n"
    if ans in ("", "y", "yes"):
        print("          installing: %s ..." % " ".join(pip_names))
        rc = subprocess.call([sys.executable, "-m", "pip", "install", *pip_names])
        still = [LIBS[m] for m in missing if not _have(m)]
        if rc == 0 and not still:
            say("PASS", "Libraries installed")
        else:
            say("FAIL", "Install did not complete",
                "Still missing: %s\nTry from a command window: pip install %s"
                % (", ".join(still) or "(unknown)", " ".join(pip_names)))
    else:
        say("WARN", "Skipped the install",
            "Install later with:  pip install %s" % " ".join(pip_names))

# ---- 5. Decode engine imports ----------------------------------------------
def check_engine():
    if not _have("numpy") or not _have("scipy"):
        say("WARN", "Decode engine", "Skipped -- install numpy + scipy first (above), then re-run.")
        return
    sys.path.insert(0, str(ENGINE))
    try:
        import frontend, fsk4_demod, framer, pdu_blocks, bch_nid, live_core, combo_core  # noqa
        say("PASS", "Decode engine imports clean")
    except Exception as e:
        say("FAIL", "Decode engine import error",
            "%s\nA file may be missing or corrupted -- re-extract the package." % e)
    finally:
        try: sys.path.remove(str(ENGINE))
        except ValueError: pass

# ---- 6. Audio: one live listen ---------------------------------------------
def check_audio():
    if not _have("sounddevice") or not _have("numpy"):
        say("WARN", "Audio input", "Skipped -- install the libraries first (above), then re-run.")
        return
    import numpy as np, sounddevice as sd
    try:
        devs = sd.query_devices()
    except Exception as e:
        say("FAIL", "Audio input", "Can't list sound devices (%s)." % e); return
    ins = [(i, d) for i, d in enumerate(devs) if d.get("max_input_channels", 0) > 0]
    if not ins:
        say("FAIL", "Audio input", "No recording device found. Plug in the USB sound card.")
        return
    dev = next((i for i, d in ins if any(h in d["name"].lower() for h in DEV_HINTS)), ins[0][0])
    name = devs[dev]["name"]
    rate = 48000
    try:
        rate = int(devs[dev].get("default_samplerate") or 48000)
    except Exception:
        pass
    # take ~1 s, trying exclusive (the v2.5 path) then shared
    def _grab(exclusive):
        frames = int(rate * 1.0)
        kw = {}
        if exclusive:
            kw["extra_settings"] = sd.WasapiSettings(exclusive=True)
            rec = sd.rec(frames, samplerate=rate, channels=1, dtype="int16", device=dev, **kw)
            sd.wait(); return rec.astype(np.float32) / 32768.0
        rec = sd.rec(frames, samplerate=rate, channels=1, dtype="float32", device=dev)
        sd.wait(); return rec
    mode = "EXCLUSIVE"
    try:
        x = _grab(True)
    except Exception:
        mode = "shared"
        try:
            x = _grab(False)
        except Exception as e:
            say("FAIL", "Audio input", "Could not open '%s' (%s)." % (name, e)); return
    x = np.nan_to_num(x).ravel()
    peak = float(np.max(np.abs(x))) * 100.0
    rms  = float(np.sqrt(np.mean(x * x))) * 100.0
    where = "%s  [%s mode]" % (name, mode)
    lvl = "peak %.0f%% / rms %.0f%%" % (peak, rms)
    if peak < 3:
        say("FAIL", "Audio input -- silent (%s)" % lvl,
            "%s\nNo audio reaching the card. Check the detector-audio cable and that\n"
            "this card is the input; confirm the radio is on and squelch is open." % where)
    elif peak > 97:
        say("WARN", "Audio input -- clipping (%s)" % lvl,
            "%s\nLevel's too hot. Turn the input down (and mic boost off). Decode still\n"
            "works until it actually clips, but give it headroom." % where)
    else:
        extra = ""
        if mode == "shared":
            extra = ("\nTip: tick 'Allow applications to take exclusive control' on the card's\n"
                     "Advanced tab for the cleanest capture (shared still works).")
        say("PASS", "Audio input -- hearing audio (%s)" % lvl,
            "%s\nOpen-squelch hiss normally reads ~55-65%% peak, so this is the radio's\n"
            "noise floor coming through. Good.%s" % (where, extra))

# ---- 7. GPS (optional) ------------------------------------------------------
def check_gps():
    found = []
    # serial COM ports
    if _have("serial"):
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
            if ports:
                found.append("serial COM ports: " + ", ".join(p.device for p in ports))
        except Exception:
            pass
    # Garmin USB puck
    try:
        sys.path.insert(0, str(ENGINE))
        import garmin_usb
        fn = getattr(garmin_usb, "device_present", None)
        if callable(fn) and fn():
            found.append("Garmin USB GPS: present")
    except Exception:
        pass
    finally:
        try: sys.path.remove(str(ENGINE))
        except ValueError: pass
    if found:
        say("PASS", "GPS (MY POSITION)", "\n".join(found))
    else:
        say("INFO", "GPS (MY POSITION): none detected",
            "Optional -- the fleet still plots without it. Plug in a Garmin USB or a\n"
            "serial NMEA puck for your own 'you are here' dot.")

# ---- 8. Ports ---------------------------------------------------------------
def check_ports():
    busy = []
    for port, what in PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            busy.append("%d (%s)" % (port, what))
        finally:
            s.close()
    if not busy:
        say("PASS", "Network ports 8080 / 10110 / 8081 free")
    else:
        say("WARN", "Network ports in use: " + ", ".join(busy),
            "The receiver may already be running, or another app has the port.\n"
            "Close the other copy (or reboot) before starting it.")

# ---- run --------------------------------------------------------------------
def main():
    print("=" * 64)
    print("  Claude McNally's PC P25 Receiver -- Self-Check   v%s" % VERSION)
    print("=" * 64)
    print("  Package: %s" % PKG_ROOT)
    rule()
    for fn in (check_python, check_files, check_libs_and_internet,
               check_engine, check_audio, check_gps, check_ports):
        try:
            fn()
        except Exception as e:
            say("FAIL", fn.__name__ + " crashed", str(e))
        rule()
    p, w, f = _counts["PASS"], _counts["WARN"], _counts["FAIL"]
    print("  Results: %d pass, %d warn, %d fail" % (p, w, f))
    if f == 0 and w == 0:
        print("  >>> All clear -- ready to run. Start the receiver with its .bat.")
    elif f == 0:
        print("  >>> Ready to run; the warnings above are worth a look.")
    else:
        print("  >>> %d issue(s) to fix above before it will run." % f)
    print("=" * 64)

if __name__ == "__main__":
    main()
