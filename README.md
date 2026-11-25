# The P25 Project

**Full voice decode and Tier-1 GPS map plotting — passively, off the air, on a plain PC.**

Every P25 radio already transmits its own position in a standardized, open format. **The Traveler PC reads it with nothing but a receiver and a sound card** — and plots every unit on your own offline map, by its radio ID, with no SDR, no base station, no internet, and no cooperation from the radio system. Your own position rides on the same map from a USB GPS. Hearing the fleet — full **voice decode**, with the current speaker lit on the map — is the active build.

---

## The Traveler PC

A plug-in, double-click application. Feed an analog receiver's detector/discriminator audio into a USB sound card, plug in a USB GPS for your own position, drop your offline maps in a folder, and run one `.bat`. A live map opens in your browser: every unit by its ID, with live / stale / alert colors, an incident-commander view, and your own position.

- **⬇️ Download:** [`The_Traveler_PC_v1.2.zip`](The_Traveler_PC_v1.2.zip)
- **📖 User guide:** [`The Traveler PC v1.2/The Traveler PC User Guide.pdf`](The%20Traveler%20PC%20v1.2/The%20Traveler%20PC%20User%20Guide.pdf)

### What you plug in
- **USB sound card → the radio's detector / discriminator audio** — the flat *detected* audio (not the speaker/voice audio). This is what the PC decodes positions from.
- **USB GPS → the PC** for your own "you are here" dot. Optional — the fleet still plots without it.
- **Your offline maps** — `.tpkx` or `.mbtiles` for your area, in the `Maps` folder, or picked from anywhere on the PC via the on-screen **Maps** menu.

The radio is only ever **received** — The Traveler PC never transmits or alters a radio.

### What you need
A Windows PC with **Python 3** (tick *Add python.exe to PATH* when you install it). The first run installs three small helpers automatically and then runs fully offline.

---

## How it works (one breath)

An FM receiver already demodulates the RF to a flat four-level baseband at its detector output — the hard radio work is done. The Traveler PC takes that off a sound card and decodes the standardized P25 **Tier-1 location data** in software: symbol recovery, framing, and error correction, down to the position and the transmitting radio's individual ID, then plots it on your offline imagery. No SDR, no re-demodulation, no infrastructure.

## Status

- **Proven live:** Tier-1 GPS decode off the air, plus the offline map plotter and your own position, on a normal PC.
- **Active build:** full **voice decode** — hearing the fleet through a licensed vocoder, with the **current speaker** identified and lit on the map, and quality-gated audio so marginal signals never play as garbage.

## Architecture & vision

The system architecture and the full location-and-voice vision are written up in **[`docs/proposals/`](docs/proposals/)** — two concept architecture overviews (location, and the location-plus-voice "combo platter").

---

*The Traveler PC — built by Claude McNally. Radio → live map, offline, read-only.*
