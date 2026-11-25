# CLAUDE.md — The P25 Project

**Written by Claude, for Claude.** Read this first if you're picking up this repo. It's the fast orientation; the deep decode research and the full development history live in the sibling repo (below).

> **PUBLIC repo — keep this file public-safe** (strip any employer/agency names; Jim's own name and GitHub handle are fine). **Precedence:** live code/files win over this prose; then this file. A compacted/auto-summary of a prior session is NOT a source of truth — re-read **Current state** from the live repo first.

> **STANDALONE PUBLIC FLAGSHIP (Jim, 2026-11-25).** This repo is the **main product** and stands on its own — its **own public site**, and **map-sourcing links to ArcGIS Earth Unlocked** (one-way: the receiver reads the offline maps those free tools make). Keep the public identity (README, site, product name) **distinct from the Traveler and the Lookout** to prevent confusion — those box products are side options for locked-down machines; THIS is the full-capability flagship the mission runs on. Still true: the *ArcGIS Earth Unlocked* family does **not** link back to this repo yet (a separate future go), and the sibling **P25-GPS-Decode** (the research/engine upstream) stays the dev-only repo, unadvertised.

---

## What it is (one breath)

The canonical home of **Claude McNally's PC P25 Receiver and GPS Map Plotter** (repo `PC-P25-Receiver-and-GPS-Map-Plotter`) — the pure-PC P25 product and the **main product of the mission**: decode P25 **Tier-1 GPS location AND voice straight off the air** (an analog radio's detector audio → a USB sound card → software), plot every unit on an **offline map** by its individual ID, show your own position from a USB GPS, and hear the fleet with the current speaker lit on the map. **All proven live.** Standalone, with its own public site; it reads offline maps you make with the free ArcGIS Earth Unlocked tools.

---

## Relationship to P25-GPS-Decode (the sibling repo)

This repo is the **product** home. The decode **engine**, the full research, the router/box appliance (the "Universal Traveler"), the stdlib on-box decoder, the soft-decision work, the answer-key rig, and the entire development trail live in the sibling repo **`P25-GPS-Decode`** (public, unadvertised). That repo's `CLAUDE.md` is the highest-authority record of the decode internals and history — read it for engine/DSP depth.

This product **bundles its own copy** of the decode engine in `Claude McNally P25 Receiver v1.3/System Files/`:
- `traveler_pc.py` + `live_core.py` + `frontend.py` + `fsk4_demod.py` + `framer.py` + `pdu_blocks.py` + `bch_nid.py` + `fsk4_taps.npy` = the OTA decoder (sounddevice live capture, serves NMEA on `:10110`).
- `units_kml.py` + `map.html` + `leaflet.js/css` = the offline map server.
- `garmin_usb.py` = the Windows Garmin D800/ctypes reader → your own "LOOKOUT / MY POSITION" unit.
- `pick_maps.py` + `traveler_launch.pyw` = the map-file picker and the single pythonw control window.

**Engine improvements proven in the sibling fold INTO this bundled copy** — keep them in sync deliberately (this is the "sealed proven kernel bolted in" rule, not patchwork).

---

## Current state  *(update this when it changes)*

**2026-11-25 (later) — REPO RENAMED → `PC-P25-Receiver-and-GPS-Map-Plotter`; becoming the STANDALONE PUBLIC FLAGSHIP (Jim).** Hardened build launched rock-solid on the bench; burn-in testing started. Jim's direction: this is the **main product**, the Traveler/Lookout are "side toys in a pinch" — so make this repo **completely standalone**, with its **own public site**, **map-sourcing links to ArcGIS Earth Unlocked**, and **no Traveler/Lookout affiliation** in the public identity (to prevent confusion). DONE so far: repo re-attached under the new name (remote repointed, in sync); README rewritten standalone (flagship framing + ArcGIS Earth Unlocked map-sourcing links, no Traveler/Lookout); this dev-doc repositioned. **OPEN:** (1) build the public GitHub-Pages site (`site/index.html` + pages workflow); (2) **code-level de-affiliation decision** — the live source still carries internal `Traveler`/`Lookout` names (filenames `traveler_pc.py`/`traveler_launch.pyw`, `SELF_ID="LOOKOUT"`, `LOOKOUT_MAP_ROOTS` env var, `units_kml.py` "The Lookout" banners, docstrings). User-facing UI already says "Claude McNally's" (map.html) and those names only surface in hidden logs / the NMEA SELF id / the source itself. A full de-affiliation = one clean verified pass (rename the 2 files + SELF_ID + env var + banners, synced across the .bat/launcher/units_kml/map.html), which Jim adopts on a restart — best done as the final pre-public pass, NOT patchwork mid-burn-in. Jim to confirm depth/timing.

**2026-11-25 — ★★★ THE COMBO PLATTER IS LIVE-PROVEN AND THE PRODUCT IS NAMED, PACKAGED, AND BEING HARDENED. "Claude McNally's PC P25 Receiver and GPS Map Plotter" (Jim locked the name).** GPS + CURRENT SPEAKER + **voice in the browser**, all off the air, proven live on Jim's PC with 3 units (MY POSITION, a fleet unit, and an aliased talker whose marker lit while its voice played). **Voice is pure-Python IMBE — NO DVstick, NO SDR, no patent-encumbered part** (P25 Phase-1 conventional voice is IMBE 4.4k, patents expired; the sibling repo's `decode/lc_source.py` pulls the link-control source ID = the join key, and `voice/imbe_decode.py` is a from-scratch pure-Python vocoder verified 0.9998 corr vs the C reference). The product folder is now **`Claude McNally P25 Receiver v1.3/`** (renamed from `The Traveler PC v1.2/`); one-click `.bat`, PDF manual beside it, everything else in System Files; zip `Claude_McNally_P25_Receiver_v1.3.zip`. **Industrial-grade hardening pass COMPLETE + sandbox-verified** (commits d7642cb decode-chain, 8810dab servers, + launcher): combo/worker fault isolation (one bad burst can't kill the decoder), bounded capture queue (drop-oldest, no unbounded growth), sound-card disconnect recovery, **Rule #1 made explicit** (imbe_decode.decode_transmission reports each key-up's bad-frame fraction; a key-up >VOICE_MAX_BAD_FRAC=0.55 is muted — PCM proven byte-identical to the sealed reference), server path-traversal self-guard + /pick-map localhost-only + quiet browser-abort handling + bind-failure messages + voice-port isolation, launcher health-watch. map.html audited clean (no change needed). **The happy path Jim called perfect is held byte-for-byte; hardening is armor around it.** Pending: Jim's live run of the hardened package, then any field-surfaced polish.

**2026-11-24 — The Traveler PC moved here as its canonical home (Jim's call).** v1.2 copied from the sibling's `tool-traveler-pc/`. GPS decode + offline map + you-are-here = **LIVE-PROVEN on Jim's PC**. The app runs as a single pythonw control window (no command consoles), launches the decoder + map server as windowless subprocesses, and has a direct `.tpkx`/`.mbtiles` map-file picker. The sibling repo keeps the box/router lineage.

**Active build — VOICE (the combo platter).** Jim's BK VHF fleet is **P25 Phase 1 conventional** (full-rate). The plan: the decoder already locks the Phase-1 frames for GPS, so voice = also pull the voice codewords from the LDU1/LDU2 frames → a **licensed AMBE+2 vocoder** (a DVMEGA **DVstick 30**, run in its full-rate mode; AMBE+2 is backward-compatible, and the DVSI royalty is paid by buying the authorized stick) → PCM → play. The **current speaker** comes from the voice frame's own link-control **source ID**; the talking unit's marker lights up, with a **VU meter**. Fused by unit ID (position layer + voice layer share the radio's ID; the map already plots by ID). **Rule #1 (Jim):** quality-gated audio — gate on decode quality *before* the vocoder (feeding it marginal codewords = the screech), mute bad frames, hold patiently through fades, picky-but-tunable. Full design: `docs/proposals/` + the sibling's memory/CLAUDE.md.

**Soft-decision engine upgrade (fold-in pending).** A soft-decision FEC upgrade (~**3.16 dB** coding gain, sandbox-verified) was built in the sibling (`decode/soft_blocks.py` + `decode_capture_soft.py`). It lifts GPS **and** voice alike at the margin. Fold it into this bundled engine when the voice build lands (after the 2026-11-25 attenuator field measurement). Hardware: a flat line-level USB interface (Behringer UFO202) is a second, stacking front-end improvement.

---

## Landmines

- **Edit the BUNDLED engine here** (`Claude McNally P25 Receiver v1.3/System Files/`) for product changes — not the sibling's `decode/` (that's the research/bench engine). They are separate copies on purpose.
- **Voice is pure-Python IMBE now, NOT a DVstick.** The earlier plan called for a DVMEGA DVstick; the proven path is the from-scratch pure-Python IMBE decoder (`imbe_decode.py` + `imbe_tables.py` here), no dongle. The DVstick is only ever needed if we someday decode AMBE+2 Phase-2 voice. Ignore older DVstick notes below.
- **The pythonw/tkinter launcher** (`traveler_launch.pyw`) is **untestable in this sandbox** (no tkinter) — logic-verify only; Jim's launch on Windows is the test. Two log files (`decoder_log.txt` / `map_server_log.txt` in System Files) name any failure.
- **"IMBE" is not a separate codec here.** Jim's BK spec names its vocoder "Third Generation Enhanced IMBE … AMBE+2 V1.80"; in modern radios the Phase-1 full-rate voice is just the full-rate mode of the same AMBE+2 dual-rate chip. Don't treat IMBE as a separate/incompatible obstacle — it's the AMBE+2 family throughout, which is exactly why the DVstick (same family) decodes it.
- **Receive-only, always.** Never transmit or alter a radio.
- Deliver files to Jim's Downloads via the bridge; **bump the version on every change** (the window-title version is his tell for what's running); give a changed file a new distinct name.

## docs/

- `docs/proposals/` — two family-styled concept architecture overviews (PDF + HTML source): the **location** overview and the **location + voice** ("combo platter") companion. Reusable templates; they use "Universal Traveler" as the system name (Jim may want them retitled for this repo).

## Resume procedure

1. Clone; attach with push access (`add_repo`, `access: push`). Shallow clone — push with `git -c push.negotiate=true push`.
2. Read this → the sibling `P25-GPS-Decode` `CLAUDE.md` for decode/engine depth → the live code.
3. Product changes live in `Claude McNally P25 Receiver v1.3/System Files/`. Test logic + exact bytes in the sandbox; hand hardware/RF and the Windows launcher checks to Jim.

*Keep this file current and lean.*
