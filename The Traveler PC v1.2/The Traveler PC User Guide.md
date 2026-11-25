# The Traveler PC — User Guide

## Installing — read this first

1. **Extract All** from the zip first (don't run it from inside the zip).
2. Open the folder. There is **one** thing to double-click: **`Start The Traveler PC.bat`**. Everything else lives in the **System Files** folder — leave it alone.
3. Windows may show a blue "Windows protected your PC" box the first time. Click **More info → Run anyway**.
4. You need **Python 3** on the PC (from python.org — tick *Add python.exe to PATH* when you install it).
5. The first run installs three small helpers automatically (`numpy`, `scipy`, `sounddevice`) — just wait a moment. The PC needs the internet that one time; after that it runs fully offline.

---

## What it is

**The Traveler PC decodes your fleet's GPS straight off the air and plots it on your own offline maps — on a normal PC, with nothing in the field.** A USB sound card takes the radio's detector audio, the PC decodes the P25 Tier-1 position reports, and a live map opens in your browser. No base station cooperation, no SDR, no internet, no cell. Your own Garmin shows your own position next to the fleet.

There is no box to flash, no router, no SSH — that machinery only exists to get this onto a locked-down work PC. On a PC you're allowed to run Python on, this is the whole thing: plug in, double-click, watch the map.

---

## What you plug in

- **USB sound card → the radio's detector / discriminator audio** (the flat *detected* audio — e.g. a Kenwood NX-700 **DEO pin 19** with the radio set **WIDE** — not the speaker/voice audio). This is what the PC decodes GPS from. A Sound Blaster Play! 3 is proven; wire DEO → 4.7 µF → 2.2 kΩ → the sound card's **mic tip**, ground → sleeve, mic boost off, level low.
- **Garmin USB GPS → the PC** for **MY POSITION** (your own you-are-here dot). A Garmin GPS 18 USB is proven. Optional — without it, you still see the whole decoded fleet.
- **Your maps** — your offline **`.tpkx` or `.mbtiles`** files, anywhere on this PC. Use **Maps → Pick a map (.tpkx)…** on the screen to choose the map file to view; every map in the same folder is listed too, so you can switch between them. (The `Maps` folder next to the `.bat` is a handy default spot.) No maps = the fleet still plots on a blank map; add maps to see the ground.

The radio is only ever **received** — The Traveler PC never transmits or changes a radio.

---

## Starting it

Double-click **`Start The Traveler PC.bat`**. A small **The Traveler PC** control window opens — the decoder and map server run quietly in the background, with **no command windows**. Pick your **radio input** from the drop-down, and your browser opens the live map at `http://localhost:8080`. You'll see the startup badge, then it clears to the map. **Close the control window (or click Stop) to shut everything down.**

The first launch does a one-time setup (it installs three small helpers and shows a window briefly); after that it runs fully offline.

---

## The screen

- **Each unit is plotted by its ID**, the dot matching the radio. **Green** = live, **amber** = stale.
- **MY POSITION** is the teal dot — your own Garmin fix.
- **Maps** (top right) lists your maps and switches between them; **Pick a map (.tpkx)…** opens any map file on this PC.
- **Alias** (top right) lets you give a raw unit ID a crew name (e.g. `9076802` → *Jax 24*). Edit a name beside any ID, or type **any unit ID** in the bottom row to name a radio **before it ever transmits** (not just the ones on screen). Click **Save names**; it shows on the map within a few seconds. Names stick even when that radio isn't transmitting right now.
- A unit that goes quiet turns amber so you can read the fleet at a glance.

---

## Troubleshooting

- **No units on the map.** Units appear only when a radio transmits a GPS report. Confirm the sound card is on the detector audio and the decoder window shows reports scrolling in.
- **MY POSITION missing.** The Garmin needs a clear view of the sky to get a fix; give it a minute outdoors. (A degraded indoor fix is accepted — only a failed fix is dropped.)
- **No map behind the units.** Put a `.tpkx` or `.mbtiles` for your area in the `Maps` folder, then refresh the browser.
- **Sound card not found.** The decoder window lists the inputs and asks for a number — pick the USB sound card the radio is wired to.
- **Nothing decodes but the radio is keying up.** Set the receiving radio to **WIDE**, open the squelch, and check the audio level (clean, not clipping). 48 kHz capture, Windows audio "enhancements" off.

---

*The Traveler PC — built by Claude McNally. Radio → live map, offline, read-only.*
