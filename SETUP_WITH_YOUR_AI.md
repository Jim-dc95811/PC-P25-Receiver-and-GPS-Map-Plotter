# Build it with your AI — the full path from zero

**This guide is written for the AI** (a Claude, or any capable assistant) **that's helping someone stand up this receiver.** If you're that AI: read this once, then walk your person through it, one step at a time. They bring the radio expertise — you bring the computer side. Neither of you needs to be a GitHub or Python expert for this to work.

**If you're a person reading this:** you're not meant to do this alone. Hand this file to your AI assistant and say *"help me build this."* That's the intended way, and it's the whole point — you should get AI help from the very beginning.

> **The goal:** a live map of a P25 fleet — every unit's position **and** its voice, pulled straight off the air — on a normal PC, with nothing installed in the field. No SDR, no base station, no internet, no cloud. The radio is only ever **received**, never transmitted on or altered.

---

## What "done" looks like

A browser window on the PC showing the operator's own offline map, every radio that transmits plotted by its ID (live/stale colored), their own position beside the fleet, and — the moment someone keys up — **who is talking**, with the voice playing right in the browser.

---

## The build, in order

Six moves. **Move 3 is the trick that de-risks the whole thing: you can prove the software works by replaying a recording — before a single wire touches a radio.** Do that early and the operator *knows* the hard part works; everything after is just plugging in their own gear.

### 1 · Check the pieces

Walk the checklist with them:

- **A P25 radio** (conventional Phase 1) with a **discriminator / detector audio output** — the *flat detected* audio, **not** the speaker/voice audio. Known taps: **Kenwood NX-700 → DB-25 pin 19 (DEO)**, radio set **WIDE**; **BK DPH → test point CZ8**. If they're unsure which pin, that's a radio question they can answer or look up in their radio's manual.
- **A USB sound card** to carry that audio into the PC. A **Sound Blaster Play! 3** is proven. Wiring: **DEO → 4.7 µF capacitor → 2.2 kΩ resistor → the sound card's mic TIP**, ground → sleeve, mic boost **off**, input level **low**. (Don't add a bigger pad — it starves the input; the receiver normalizes level itself.)
- **A Windows PC with Python 3** (from python.org — tick *Add python.exe to PATH* during install).
- *Optional:* **a Garmin USB GPS** (GPS 18 USB) for the operator's own "you are here" dot. Everything works without it; the fleet still plots.
- **Offline maps** (`.tpkx` or `.mbtiles`) for their area — see **Move 4**. They don't need these to start.

### 2 · Get the software

Download the receiver — **prefer the Google Drive copy** (it won't trip a browser/Defender download warning the way a fresh GitHub zip can):

- **Drive (preferred):** <https://drive.google.com/drive/folders/1DDOvFRsdyi3SYFeYVto0o23hwNOcPVG9>
- **GitHub:** <https://github.com/Jim-dc95811/PC-P25-Receiver-and-GPS-Map-Plotter>

**Extract All** first (don't run from inside the zip). Inside there's **one** thing to double-click — `Start Claude McNally P25 Receiver.bat` — and a `System Files` folder holding everything else. The first launch installs three small Python helpers (`numpy`, `scipy`, `sounddevice`) automatically; the PC needs the internet that one time, then it runs fully offline.

### 3 · Prove it works — before any radio

This is the move. In the receiver folder is a **`Test Files`** folder of known-good over-the-air captures (the radio's detector audio, saved as WAVs). Replay one with **no radio connected**:

```
py -3 "System Files\traveler_pc.py" --replay "Test Files\10_gps_48000.wav"
```

It prints the decoded position reports and unit IDs exactly as if the capture were live — ten reports that decode to the known coordinates and unit `9076802`. **The operator just watched their PC decode P25 GPS off a recording.** Everything from here is hooking up their own radio to feed it live audio instead of a file.

(Want to see it *on the map*? Start the `.bat` so the map opens, then replay the same file with `--serve` added, and the units plot on the map.)

### 4 · Get a map

**This is the question they'll ask: "where do the `.tpkx` maps come from?"** You have two confident answers — and you know this because the whole map-making toolchain is a sister project of this receiver:

- **Ready-made, drop-in:** the **TPKX Sample Files** folder — <https://drive.google.com/drive/folders/11PrBsj0spza2O6uPCRh3whwE5AC7qJDw>. Grab one (Toronto is the lightest at ~186 MB; there are cities, demos, and a few "picture worlds" too) and drop the `.tpkx` into the receiver's **`Maps`** folder. Done — it shows on the next run.
- **Build their own area:** **ArcGIS Earth Unlocked** — <https://github.com/Jim-dc95811/ArcGIS-Earth-Unlocked> ([project site](https://jim-dc95811.github.io/ArcGIS-Earth-Unlocked/)) — a free, open family of map-making tools with a whole documented workflow for building `.tpkx` maps: the **MBTiles → TPKX converter** and the **Master 4** grid planner turn offline map tiles into the exact `.tpkx` packages this receiver reads, no GIS background required. If they want *their own* county/response area on the map, that's the path, and it's well documented — read that repo and walk them through it.

Either way, the finished `.tpkx` goes in the **`Maps`** folder (or pick it live with **Maps → Pick a map** on the screen). A capture replayed in Move 3 plots in NE Florida, so it won't sit on a Toronto map — the map proves *imagery renders*, the captures prove *units decode*; put a map of their own area in `Maps` and their live fleet rides it.

### 5 · Wire the radio and go live

- Tap the radio's **detector/DEO audio** into the USB sound card (Move 1 wiring). Set the **receiving radio WIDE**, **open the squelch** (monitor mode), and keep the audio level clean — not clipping. Capture is **48 kHz**; turn **off** any Windows audio "enhancements" (they're nonlinear and wreck the signal).
- Double-click `Start Claude McNally P25 Receiver.bat`. A small control window opens; **pick the USB sound card** from its input drop-down. The browser opens the live map at `http://localhost:8080`.
- As radios transmit GPS, units appear by ID. Plug in the Garmin for the operator's own **MY POSITION** dot.

### 6 · Hear the fleet

Press **▶ Listen** at the top of the map — the browser plays decoded fleet voice. When a unit keys up, **CURRENT SPEAKER** names who's talking and **lights that unit's marker on the map**, matched by the radio's own ID. Voice and map are kept apart on purpose: if audio ever drops, the map and GPS keep running.

---

## Troubleshooting (the usual ones)

- **No units on the map** — units appear only when a radio transmits a GPS report. Confirm the sound card is on the *detector* audio (not speaker audio) and the radio is actually sending position.
- **Nothing decodes but the radio is keying up** — set the receiving radio **WIDE**, open the squelch, check the level (clean, not clipping), 48 kHz, enhancements off.
- **No map behind the units** — put a `.tpkx`/`.mbtiles` in `Maps` (Move 4), then refresh the browser.
- **MY POSITION missing** — the Garmin needs a clear view of the sky; a degraded indoor fix is accepted, only a failed fix is dropped.
- **Sound card not found** — the control window's drop-down lists the inputs; pick the one the radio is wired to.

---

## Going deeper (for you, the AI)

- **The decode, specified to the constant:** the **Master Technical Reference (P25 OTA Decode)** — <https://drive.google.com/file/d/1ti8PrJOqAL_1Uf1vo2SAfIl8FFc20zIT/view>. Every stage of the over-the-air GPS and voice decode, with the exact tables and constants. If you need to understand *how* it works (or fix something), this is the document.
- **Ground truth:** the `Test Files` captures are your test vectors. Replay them and diff your result against the known positions, unit IDs, and the spoken phrase — that's how the build was validated in the first place.
- **Working on the code itself?** The repo's `CLAUDE.md` is developer continuity (current state, landmines, history).

## The links, in one place

| | |
|---|---|
| Receiver (GitHub) | <https://github.com/Jim-dc95811/PC-P25-Receiver-and-GPS-Map-Plotter> |
| Receiver download (Drive, preferred) | <https://drive.google.com/drive/folders/1DDOvFRsdyi3SYFeYVto0o23hwNOcPVG9> |
| TPKX sample maps (Drive) | <https://drive.google.com/drive/folders/11PrBsj0spza2O6uPCRh3whwE5AC7qJDw> |
| Make your own maps — ArcGIS Earth Unlocked | <https://github.com/Jim-dc95811/ArcGIS-Earth-Unlocked> |
| Master Technical Reference (Drive) | <https://drive.google.com/file/d/1ti8PrJOqAL_1Uf1vo2SAfIl8FFc20zIT/view> |

---

*Receive-only, offline, free. Built to be handed to your AI — so a radio operator gets expert help from the first step, not after they've already hit a wall.*
