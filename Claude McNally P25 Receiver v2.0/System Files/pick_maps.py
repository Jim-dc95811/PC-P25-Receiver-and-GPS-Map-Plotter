#!/usr/bin/env python3
"""
Map picker for The Traveler PC.

Opens a native file dialog so the user picks the MAP FILE to view - a .tpkx
(ArcGIS Earth tile package) or .mbtiles - from anywhere on this PC. Prints the
chosen file's full path on stdout (empty if cancelled). The map server
(units_kml.py, /pick-map) takes that file, serves its folder so every map in
it is listed too, and jumps the view to the picked map.

Pick the map, not a folder - one dialog, one click.
"""
import os
import sys


def pick(initial_dir):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Pick a map to view  (.tpkx or .mbtiles)",
            initialdir=initial_dir or os.path.expanduser("~"),
            filetypes=[("Maps (.tpkx .mbtiles)", "*.tpkx *.mbtiles"),
                       ("ArcGIS Earth tile package", "*.tpkx"),
                       ("MBTiles", "*.mbtiles"),
                       ("All files", "*.*")])
        root.destroy()
        return path or ""
    except Exception:
        return ""


def main():
    # Start the dialog in the folder of the last-picked map, if any.
    initial = ""
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps_folder.txt")
    try:
        d = open(cfg, encoding="utf-8").read().strip()
        if d and os.path.isdir(d):
            initial = d
    except OSError:
        pass
    print(pick(initial))


if __name__ == "__main__":
    main()
