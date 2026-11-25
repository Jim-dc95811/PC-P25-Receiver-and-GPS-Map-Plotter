# Claude McNally's PC P25 Receiver and GPS Map Plotter

**Full voice decode and Tier-1 GPS map plotting — passively, off the air, on a plain PC.**

Every P25 radio already transmits its own position in a standardized, open format. **This receiver reads it with nothing but a radio and a sound card** — and plots every unit on your own offline map, by its radio ID, with no SDR, no base station, no internet, and no cooperation from the radio system. Your own position rides on the same map from a USB GPS. And when a unit keys up, you **hear the fleet** — full voice decode, in your browser, with the current speaker lit on the map.

---

## The receiver

A plug-in, double-click application. Feed an analog radio's detector/discriminator audio into a USB sound card, plug in a USB GPS for your own position, drop your offline maps in a folder, and run one `.bat`. A live map opens in your browser: every unit by its ID, with live / stale / alert colors, your own position, and — when someone transmits — who is talking and their voice playing right in the page.

- **⬇️ Download:** [`Claude_McNally_P25_Receiver_v1.3.zip`](Claude_McNally_P25_Receiver_v1.3.zip)
- **📖 User guide:** [`Claude McNally P25 Receiver v1.3/Claude McNally P25 Receiver User Guide.pdf`](Claude%20McNally%20P25%20Receiver%20v1.3/Claude%20McNally%20P25%20Receiver%20User%20Guide.pdf)

### What you plug in
- **USB sound card → the radio's detector / discriminator audio** — the flat *detected* audio (not the speaker/voice audio). This single feed carries both the positions and the voice.
- **USB GPS → the PC** for your own "you are here" dot. Optional — the fleet still plots without it.
- **Your offline maps** — `.tpkx` or `.mbtiles` for your area, in the `Maps` folder, or picked from anywhere on the PC via the on-screen **Maps** menu.

The radio is only ever **received** — this receiver never transmits or alters a radio.

### What you need
A Windows PC with **Python 3** (tick *Add python.exe to PATH* when you install it). The first run installs three small helpers automatically and then runs fully offline.

---

## How it works (one breath)

An FM radio already demodulates the RF to a flat four-level baseband at its detector output — the hard radio work is done. This receiver takes that off a sound card and decodes the standardized P25 **Tier-1 location data** in software: symbol recovery, framing, and error correction, down to the position and the transmitting radio's individual ID, then plots it on your offline imagery. The same frames carry **voice**, decoded by a pure-software IMBE vocoder (no dongle, no SDR, no patent-encumbered part), with the transmitting radio's link-control ID naming the current speaker. No SDR, no re-demodulation, no infrastructure.

## Status

- **Proven live:** Tier-1 GPS decode off the air; the offline map plotter; your own position; and **voice decode** with the **current speaker** identified and lit on the map — all on a normal PC, nothing installed on the viewer.
- Voice is quality-gated so marginal signals never play as garbage, and the whole key-up is reconstructed and played clean, start to finish.

## Architecture & vision

The system architecture and the full location-and-voice vision are written up in **[`docs/proposals/`](docs/proposals/)** — two concept architecture overviews (location, and the location-plus-voice "combo platter").

---

*Claude McNally's PC P25 Receiver and GPS Map Plotter — an original, built by Claude McNally. Radio → live map and live voice, offline, read-only.*
