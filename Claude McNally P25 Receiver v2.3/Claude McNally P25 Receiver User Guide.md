# Claude McNally's PC P25 Receiver and GPS Map Plotter — User Guide

## Installing — read this first

1. **Extract All** from the zip first (don't run it from inside the zip).
2. Open the folder. There is **one** thing to double-click: **`Start Claude McNally P25 Receiver.bat`**. Everything else lives in the **System Files** folder — leave it alone.
3. Windows may show a blue "Windows protected your PC" box the first time. Click **More info → Run anyway**.
4. You need **Python 3** on the PC (from python.org — tick *Add python.exe to PATH* when you install it).
5. The first run installs three small helpers automatically (`numpy`, `scipy`, `sounddevice`) — just wait a moment. The PC needs the internet that one time; after that it runs fully offline.

---

## What it is

**It decodes your fleet's P25 straight off the air — their GPS positions *and* their voice — and plots it all on your own offline maps, on a normal PC, with nothing in the field.** A USB sound card takes the radio's detector audio, the PC decodes the P25 Tier-1 position reports and the voice, and a live map opens in your browser: every unit on the map by its ID, your own position beside them, and — when someone keys up — **who is talking**, with their voice playing right in the browser.

No base-station cooperation. No SDR. No internet, no cell, no cloud. No special dongle. Just the radio's audio, a plain PC, and your maps.

The radio is only ever **received** — this receiver never transmits or changes a radio.

---

## What you plug in

- **USB sound card → the radio's detector / discriminator audio** (the flat *detected* audio — e.g. a Kenwood NX-700 **DEO pin 19** with the radio set **WIDE** — not the speaker/voice audio). This single audio feed carries **both** the GPS and the voice. A Sound Blaster Play! 3 is proven; wire DEO → 4.7 µF → 2.2 kΩ → the sound card's **mic tip**, ground → sleeve, mic boost off, level low.
- **Garmin USB GPS → the PC** for **MY POSITION** (your own you-are-here dot). A Garmin GPS 18 USB is proven. Optional — without it, you still see the whole decoded fleet.
- **Your maps** — your offline **`.tpkx` or `.mbtiles`** files, anywhere on this PC. Use **Maps → Pick a map (.tpkx)…** on the screen to choose the map file to view; every map in the same folder is listed too, so you can switch between them. (The `Maps` folder next to the `.bat` is a handy default spot.) No maps = the fleet still plots on a blank map; add maps to see the ground.

---

## Starting it

Double-click **`Start Claude McNally P25 Receiver.bat`**. A small control window opens — the decoder and map server run quietly in the background, with **no command windows**. Pick your **radio input** from the drop-down, and your browser opens the live map at `http://localhost:8080`. You'll see the startup badge, then it clears to the map. **Close the control window (or click Stop) to shut everything down.**

The first launch does a one-time setup (it installs three small helpers and shows a window briefly); after that it runs fully offline.

---

## The map

- **Each unit is plotted by its ID**, the dot matching the radio. **Green** = live, **amber** = stale.
- **MY POSITION** is the teal dot — your own Garmin fix.
- **Blank** (top of the map, next to Listen) drops the map imagery and shows just the blips on a plain **white background** — handy when you only want the units and how far apart they are, or when you have no map for the area. The blips stay in their true relative positions and the range/bearing readout is unchanged; your view doesn't move. Tap it again (it now reads **Map**) to bring the imagery back. The choice is remembered per device, so a phone that chose Blank stays blank.
- **Maps** (top right) lists your maps and switches between them; **Pick a map (.tpkx)…** opens any map file on this PC.
- **📱 Phone** (top right) shows a QR code. Scan it with any phone's camera on the same Wi-Fi and the map opens on the phone — no app, no typing. (The code carries this PC's network address, so it works from a phone even though typing the PC's name wouldn't.)
- **Alias** (top right) lets you give a raw unit ID a crew name (e.g. `9076802` → *Jax 24*). Edit a name beside any ID, or type **any unit ID** in the bottom row to name a radio **before it ever transmits** (not just the ones on screen). Click **Save names**; it shows on the map within a few seconds. Names stick even when that radio isn't transmitting right now.
- A unit that goes quiet turns amber so you can read the fleet at a glance.
- **NAC** — the system's Network Access Code shows in the top bar in **hex** (e.g. `NAC 0x455`) the moment the receiver hears a voice call, and stays put. It confirms you're locked to the right P25 system.

---

## Hearing the fleet — the voice side

The same detector audio that carries the GPS also carries the voice, so the receiver decodes **both** — and plays the voice right in the browser, nothing extra to install.

- **Press ▶ Listen once** (top of the map). The browser starts playing decoded fleet voice. Leave it on; it reconnects on its own if the link blips.
- **CURRENT SPEAKER** — when a unit keys up, its panel shows **who is talking**, matched to the unit by the radio's own ID. **That unit's marker lights with a white ring on the map**, so you *see* who's on the air while you hear them. The panel also shows the **talkgroup** (`TG`, in decimal) and — when both you and the talker have a GPS fix — the **range and true-north bearing** to them (e.g. `· 1.2 mi · 130°`), so you get distance-and-direction to whoever is on the air. (A radio has to rotate through those readouts on its little screen; here they're all in one glance.)
- **It plays the key-up clean, start to finish.** The receiver captures the whole transmission, then plays it — so you hear every word from the first syllable, no clipped front end. On a long transmission that playback runs a little behind real time; on back-and-forth traffic it stays seamless, and a listener at a distance can't tell. (A quiet side-benefit: no squelch tail, no stepped-on first word.)

Voice and the map are kept apart on purpose: if the audio ever drops, the map and the GPS feed keep running untouched.

---

## Test files — prove a build with no radio

The download folder includes a **`Test Files`** folder: known-good over-the-air captures from the bench — the radio's detector audio, saved as WAVs. They let you (or an AI working on this receiver) **verify a decode with no radio connected** — replay any capture and the receiver produces the same result it would live.

Replay from a command prompt in the receiver folder:

    py -3 "System Files\traveler_pc.py" --replay "Test Files\10_gps_48000.wav"

What's in there (a `README.txt` in the folder describes every file):

- **GPS** — `10_gps_48000.wav` is the clean reference: ten position reports that decode to the exact lat/lon and unit IDs the base reported. Plus a second clean capture and a periodic-update capture.
- **Voice** — `3_each_testing12341234_27seconds.wav`: "Testing 1234 1234" spoken three times, the capture the voice decoder was proven on.
- **Combo** — `voice_with_a_couple_of_gps_updates.wav`: voice and GPS from the same unit, so the current-speaker ID matches the plotted dot.
- **Sensitivity sweep** — the VIAVI `153_*` captures step the signal from strong down past the digital cliff (the 5% error point lands near −119 dBm), plus the `1011` / `CAL` / `silence` pattern baselines.

> **For an AI reverse-engineering this receiver:** these captures are your ground truth. Replay them and diff your decode against the known positions, unit IDs, and the spoken phrase. The full method — and the meaning of every number — is in the **Master Technical Reference (P25 OTA Decode)** in the download folder.

---

## Troubleshooting

- **No units on the map.** Units appear only when a radio transmits a GPS report. Confirm the sound card is on the detector audio and the decoder is seeing traffic.
- **MY POSITION missing.** The Garmin needs a clear view of the sky to get a fix; give it a minute outdoors. (A degraded indoor fix is accepted — only a failed fix is dropped.)
- **No map behind the units.** Put a `.tpkx` or `.mbtiles` for your area in the `Maps` folder (or pick one with **Maps → Pick a map**), then refresh the browser.
- **No voice when I press Listen.** Make sure a unit is actually keyed up — the receiver only plays decoded traffic, and it plays the whole key-up *after* the unit un-keys. Check the sound card is on the detector audio.
- **Sound card not found.** The control window's drop-down lists the inputs — pick the USB sound card the radio is wired to.
- **Nothing decodes but the radio is keying up.** Set the receiving radio to **WIDE**, open the squelch, and check the audio level (clean, not clipping). 48 kHz capture, Windows audio "enhancements" off.

---

*Claude McNally's PC P25 Receiver and GPS Map Plotter — an original, built by Claude McNally. Radio → live map and live voice, offline, read-only.*
