#!/usr/bin/env python3
"""
The Traveler PC - single-window launcher.

Starts the OTA decoder and the map server as WINDOWLESS background processes
(no black command windows) and shows one small control window. Pick the radio
input, open the map, and Stop when done. Closing this window stops everything.

Run by pythonw.exe (no console) from "Start The Traveler PC.bat".
"""
import os, sys, time, threading, subprocess, webbrowser
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
URL = "http://localhost:8080"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW


def default_maps():
    m = os.path.join(PKG, "Maps")
    try:
        os.makedirs(m, exist_ok=True)
    except OSError:
        pass
    return m


def list_inputs():
    try:
        import sounddevice as sd
        return [(i, d["name"]) for i, d in enumerate(sd.query_devices())
                if d.get("max_input_channels", 0) > 0]
    except Exception:
        return []


def default_device(inputs):
    hints = ("blaster", "sb play", "usb audio", "usb-audio", "usb pnp")
    for i, name in inputs:
        if any(h in name.lower() for h in hints):
            return i
    return inputs[0][0] if inputs else None


class App:
    def __init__(self, root):
        self.root = root
        self.dec = None
        self.srv = None
        os.environ.setdefault("LOOKOUT_MAP_ROOTS", default_maps())

        root.title("The Traveler PC")
        root.configure(bg="#0d141c")
        root.geometry("440x270")
        try:
            root.resizable(False, False)
        except Exception:
            pass

        tk.Label(root, text="THE TRAVELER PC", fg="#7fd1ff", bg="#0d141c",
                 font=("Segoe UI", 15, "bold")).pack(pady=(18, 2))
        tk.Label(root, text="Radio → live map  ·  built by Claude McNally",
                 fg="#c9a24b", bg="#0d141c", font=("Segoe UI", 9, "italic")).pack()

        f = tk.Frame(root, bg="#0d141c")
        f.pack(pady=14)
        tk.Label(f, text="Radio input:", fg="#cfe0ee", bg="#0d141c").grid(row=0, column=0, padx=5, sticky="e")
        self.inputs = list_inputs()
        names = ["%d: %s" % (i, n) for i, n in self.inputs] or ["(no sound inputs found)"]
        self.combo = ttk.Combobox(f, values=names, state="readonly", width=36)
        d = default_device(self.inputs)
        idx = [i for i, _ in self.inputs].index(d) if (d is not None and self.inputs) else 0
        self.combo.current(idx)
        self.combo.grid(row=0, column=1, padx=5)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.restart_decoder())

        self.status = tk.Label(root, text="starting …", fg="#9fb3c8", bg="#0d141c")
        self.status.pack(pady=4)

        bf = tk.Frame(root, bg="#0d141c")
        bf.pack(pady=10)
        tk.Button(bf, text="Open the map", command=lambda: webbrowser.open(URL),
                  bg="#17344a", fg="#eaf4ff", activebackground="#1f4a68",
                  relief="flat", padx=14, pady=7).grid(row=0, column=0, padx=6)
        tk.Button(bf, text="Stop", command=self.stop,
                  bg="#5a1f1f", fg="#ffecec", activebackground="#7a2a2a",
                  relief="flat", padx=18, pady=7).grid(row=0, column=1, padx=6)

        tk.Label(root, text="Closing this window stops The Traveler PC.",
                 fg="#5f7284", bg="#0d141c", font=("Segoe UI", 8)).pack(side="bottom", pady=8)

        root.protocol("WM_DELETE_WINDOW", self.stop)
        self.start()
        threading.Thread(target=self._open_browser, daemon=True).start()

    def _spawn(self, script, logname, *args):
        log = open(os.path.join(HERE, logname), "w", buffering=1, encoding="utf-8", errors="replace")
        return subprocess.Popen([sys.executable, os.path.join(HERE, script), *args],
                                cwd=HERE, creationflags=NO_WINDOW,
                                stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)

    def cur_device(self):
        try:
            return self.inputs[self.combo.current()][0]
        except Exception:
            return None

    def start(self):
        self.srv = self._spawn("units_kml.py", "map_server_log.txt")
        self.restart_decoder()

    def restart_decoder(self):
        if self.dec:
            try:
                self.dec.terminate()
            except Exception:
                pass
        args = ["--serve", "--self-gps"]
        dev = self.cur_device()
        if dev is not None:
            args.append("--device=%d" % dev)
        self.dec = self._spawn("traveler_pc.py", "decoder_log.txt", *args)
        self.status.config(text="running  ·  map at %s" % URL)

    def _open_browser(self):
        time.sleep(3)
        try:
            webbrowser.open(URL)
        except Exception:
            pass

    def stop(self):
        for p in (self.dec, self.srv):
            try:
                if p:
                    p.terminate()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    r = tk.Tk()
    App(r)
    r.mainloop()
