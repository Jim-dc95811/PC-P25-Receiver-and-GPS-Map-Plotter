# CLAUDE.md — The P25 Project

**Written by Claude, for Claude.** Read this first if you're picking up this repo. It's the fast orientation; the deep decode research and the full development history live in the sibling repo (below).

> **PUBLIC repo — keep this file public-safe** (strip any employer/agency names; Jim's own name and GitHub handle are fine). **Precedence:** live code/files win over this prose; then this file. A compacted/auto-summary of a prior session is NOT a source of truth — re-read **Current state** from the live repo first.

> **DELIBERATELY UNADVERTISED, same as the sibling.** Do **not** link either P25 repo from the *ArcGIS Earth Unlocked* family (front page, site, montage, all-tools zip, etc.) until Jim's explicit go. Linking the two P25 repos to each other is fine; advertising them to the family is not.

---

## What it is (one breath)

The canonical home of **The Traveler PC** — the pure-PC P25 product: decode P25 **Tier-1 GPS location straight off the air** (an analog receiver's detector audio → a USB sound card → software), plot every unit on an **offline map** by its individual ID, and show your own position from a USB GPS. The repo's mission is **"full voice decode and Tier-1 GPS map plotting"** — location + map are proven live; **voice decode is the active build.**

---

## Relationship to P25-GPS-Decode (the sibling repo)

This repo is the **product** home. The decode **engine**, the full research, the router/box appliance (the "Universal Traveler"), the stdlib on-box decoder, the soft-decision work, the answer-key rig, and the entire development trail live in the sibling repo **`P25-GPS-Decode`** (public, unadvertised). That repo's `CLAUDE.md` is the highest-authority record of the decode internals and history — read it for engine/DSP depth.

The Traveler PC **bundles its own copy** of the decode engine in `The Traveler PC v1.2/System Files/`:
- `traveler_pc.py` + `live_core.py` + `frontend.py` + `fsk4_demod.py` + `framer.py` + `pdu_blocks.py` + `bch_nid.py` + `fsk4_taps.npy` = the OTA decoder (sounddevice live capture, serves NMEA on `:10110`).
- `units_kml.py` + `map.html` + `leaflet.js/css` = the offline map server.
- `garmin_usb.py` = the Windows Garmin D800/ctypes reader → your own "LOOKOUT / MY POSITION" unit.
- `pick_maps.py` + `traveler_launch.pyw` = the map-file picker and the single pythonw control window.

**Engine improvements proven in the sibling fold INTO this bundled copy** — keep them in sync deliberately (this is the "sealed proven kernel bolted in" rule, not patchwork).

---

## Current state  *(update this when it changes)*

**2026-11-24 — The Traveler PC moved here as its canonical home (Jim's call).** v1.2 copied from the sibling's `tool-traveler-pc/`. GPS decode + offline map + you-are-here = **LIVE-PROVEN on Jim's PC**. The app runs as a single pythonw control window (no command consoles), launches the decoder + map server as windowless subprocesses, and has a direct `.tpkx`/`.mbtiles` map-file picker. The sibling repo keeps the box/router lineage.

**Active build — VOICE (the combo platter).** Jim's BK VHF fleet is **P25 Phase 1 conventional** (full-rate). The plan: the decoder already locks the Phase-1 frames for GPS, so voice = also pull the voice codewords from the LDU1/LDU2 frames → a **licensed AMBE+2 vocoder** (a DVMEGA **DVstick 30**, run in its full-rate mode; AMBE+2 is backward-compatible, and the DVSI royalty is paid by buying the authorized stick) → PCM → play. The **current speaker** comes from the voice frame's own link-control **source ID**; the talking unit's marker lights up, with a **VU meter**. Fused by unit ID (position layer + voice layer share the radio's ID; the map already plots by ID). **Rule #1 (Jim):** quality-gated audio — gate on decode quality *before* the vocoder (feeding it marginal codewords = the screech), mute bad frames, hold patiently through fades, picky-but-tunable. Full design: `docs/proposals/` + the sibling's memory/CLAUDE.md.

**Soft-decision engine upgrade (fold-in pending).** A soft-decision FEC upgrade (~**3.16 dB** coding gain, sandbox-verified) was built in the sibling (`decode/soft_blocks.py` + `decode_capture_soft.py`). It lifts GPS **and** voice alike at the margin. Fold it into this bundled engine when the voice build lands (after the 2026-11-25 attenuator field measurement). Hardware: a flat line-level USB interface (Behringer UFO202) is a second, stacking front-end improvement.

---

## Landmines

- **Edit the BUNDLED engine here** (`The Traveler PC v1.2/System Files/`) for product changes — not the sibling's `decode/` (that's the research/bench engine). They are separate copies on purpose.
- **The pythonw/tkinter launcher** (`traveler_launch.pyw`) is **untestable in this sandbox** (no tkinter) — logic-verify only; Jim's launch on Windows is the test. Two log files (`decoder_log.txt` / `map_server_log.txt` in System Files) name any failure.
- **"IMBE" is not a separate codec here.** Jim's BK spec names its vocoder "Third Generation Enhanced IMBE … AMBE+2 V1.80"; in modern radios the Phase-1 full-rate voice is just the full-rate mode of the same AMBE+2 dual-rate chip. Don't treat IMBE as a separate/incompatible obstacle — it's the AMBE+2 family throughout, which is exactly why the DVstick (same family) decodes it.
- **Receive-only, always.** Never transmit or alter a radio.
- Deliver files to Jim's Downloads via the bridge; **bump the version on every change** (the window-title version is his tell for what's running); give a changed file a new distinct name.

## docs/

- `docs/proposals/` — two family-styled concept architecture overviews (PDF + HTML source): the **location** overview and the **location + voice** ("combo platter") companion. Reusable templates; they use "Universal Traveler" as the system name (Jim may want them retitled for this repo).

## Resume procedure

1. Clone; attach with push access (`add_repo`, `access: push`). Shallow clone — push with `git -c push.negotiate=true push`.
2. Read this → the sibling `P25-GPS-Decode` `CLAUDE.md` for decode/engine depth → the live code.
3. Product changes live in `The Traveler PC v1.2/System Files/`. Test logic + exact bytes in the sandbox; hand hardware/RF and the Windows launcher checks to Jim.

*Keep this file current and lean.*
