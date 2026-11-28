# qr_svg.py - serve a "scan to open on your phone" QR for the receiver's own map.
#
# Pure-Python QR encoder (byte mode, versions 1-4, EC level M stepping to L,
# single data block) - lifted verbatim from the proven Lookout QR Maker encoder,
# no external library, no internet - plus a tiny SVG renderer and LAN-IP finder.
# units_kml.py serves /qr.svg (the code) and /phone (the URL) from this.
#
# Why a QR at all: phones force https when you TYPE an address, so a crew that
# types 192.168.x.x:8080 lands on nothing. A QR encodes http:// explicitly, so a
# camera scan opens the map directly. The server fills in its own LAN IP, so the
# code is correct no matter how the operator reached the page (localhost, name, IP).

import socket

# ---------- QR parameters (single data block only) ----------
CONFIGS = [
    (1, 21, 10, 16, None, 0),   # v1-M  ~14 chars
    (2, 25, 16, 28, 18,   0),   # v2-M  ~26
    (3, 29, 26, 44, 22,   0),   # v3-M  ~42
    (3, 29, 15, 55, 22,   1),   # v3-L  ~53
    (4, 33, 20, 80, 26,   1),   # v4-L  ~78
]
MAX_BYTES = 78

# ---------- GF(256) for Reed-Solomon ----------
_exp = [0]*512; _log = [0]*256
_x = 1
for _i in range(255):
    _exp[_i] = _x; _log[_x] = _i
    _x <<= 1
    if _x & 0x100: _x ^= 0x11d
for _i in range(255, 512): _exp[_i] = _exp[_i-255]
def _gmul(a, b):
    if a == 0 or b == 0: return 0
    return _exp[_log[a] + _log[b]]
def _gen_poly(n):
    g = [1]
    for i in range(n):
        g2 = [0]*(len(g)+1)
        for j in range(len(g)):
            g2[j]   ^= _gmul(g[j], _exp[i])
            g2[j+1] ^= g[j]
        g = g2
    return list(reversed(g))
def _rs_encode(data, n):
    gen = _gen_poly(n); msg = list(data) + [0]*n
    for i in range(len(data)):
        c = msg[i]
        if c:
            for j in range(len(gen)): msg[i+j] ^= _gmul(gen[j], c)
    return msg[len(data):]

def _getbit(v, i): return (v >> i) & 1

def pick_config(nbytes):
    bits = 4 + 8 + nbytes*8
    for cfg in CONFIGS:
        if bits <= cfg[3]*8:
            return cfg
    raise ValueError("Address too long for this encoder (max %d characters)." % MAX_BYTES)

def encode_matrix(text):
    """Return (mod, version): mod is a SIZExSIZE list-of-lists of booleans (True = dark)."""
    raw = text.encode("ascii")
    if len(raw) > MAX_BYTES:
        raise ValueError("Address too long for this encoder (max %d characters)." % MAX_BYTES)
    v, SIZE, ECC, DATACW, ALIGN, ECFMT = pick_config(len(raw))

    bits = [0,1,0,0] + [int(b) for b in format(len(raw), "08b")]
    for ch in raw:
        bits += [int(b) for b in format(ch, "08b")]
    bits += [0]*min(4, DATACW*8 - len(bits))
    while len(bits) % 8: bits.append(0)
    data = [int("".join(map(str, bits[i:i+8])), 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]; k = 0
    while len(data) < DATACW: data.append(pad[k % 2]); k += 1
    allcw = data + _rs_encode(data, ECC)

    mod = [[False]*SIZE for _ in range(SIZE)]
    fn  = [[False]*SIZE for _ in range(SIZE)]
    def setf(x, y, val):
        if 0 <= x < SIZE and 0 <= y < SIZE: mod[y][x] = bool(val); fn[y][x] = True
    def finder(cx, cy):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                setf(cx+dx, cy+dy, max(abs(dx), abs(dy)) not in (2, 4))
    def align(cx, cy):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                setf(cx+dx, cy+dy, max(abs(dx), abs(dy)) != 1)
    for i in range(SIZE):
        setf(6, i, i % 2 == 0); setf(i, 6, i % 2 == 0)
    finder(3, 3); finder(SIZE-4, 3); finder(3, SIZE-4)
    if ALIGN is not None: align(ALIGN, ALIGN)
    setf(8, SIZE-8, True)

    def draw_format(mask):
        d = (ECFMT << 3) | mask
        rem = d
        for _ in range(10): rem = (rem << 1) ^ (((rem >> 9) & 1) * 0x537)
        b = ((d << 10) | rem) ^ 0x5412
        for i in range(6):  setf(8, i, _getbit(b, i))
        setf(8, 7, _getbit(b, 6)); setf(8, 8, _getbit(b, 7)); setf(7, 8, _getbit(b, 8))
        for i in range(9, 15): setf(14-i, 8, _getbit(b, i))
        for i in range(8):  setf(SIZE-1-i, 8, _getbit(b, i))
        for i in range(8, 15): setf(8, SIZE-15+i, _getbit(b, i))
        setf(8, SIZE-8, True)
    draw_format(0)

    i = 0; col = SIZE-1
    while col > 0:
        if col == 6: col -= 1
        for vrt in range(SIZE):
            for j in range(2):
                x = col - j
                up = ((col+1) & 2) == 0
                y = (SIZE-1-vrt) if up else vrt
                if not fn[y][x]:
                    bit = _getbit(allcw[i >> 3], 7-(i & 7)) if i < len(allcw)*8 else 0
                    mod[y][x] = bool(bit); i += 1
        col -= 2

    def cond(m, x, y):
        return [ (x+y) % 2 == 0, y % 2 == 0, x % 3 == 0, (x+y) % 3 == 0,
                 (x//3 + y//2) % 2 == 0, (x*y) % 2 + (x*y) % 3 == 0,
                 ((x*y) % 2 + (x*y) % 3) % 2 == 0, ((x+y) % 2 + (x*y) % 3) % 2 == 0 ][m]
    def apply_mask(m):
        for y in range(SIZE):
            for x in range(SIZE):
                if not fn[y][x] and cond(m, x, y): mod[y][x] = not mod[y][x]
    def penalty():
        r = 0
        for y in range(SIZE):
            rc = None; run = 0
            for x in range(SIZE):
                if mod[y][x] == rc: run += 1; r += 3 if run == 5 else (1 if run > 5 else 0)
                else: rc = mod[y][x]; run = 1
        for x in range(SIZE):
            rc = None; run = 0
            for y in range(SIZE):
                if mod[y][x] == rc: run += 1; r += 3 if run == 5 else (1 if run > 5 else 0)
                else: rc = mod[y][x]; run = 1
        for y in range(SIZE-1):
            for x in range(SIZE-1):
                if mod[y][x] == mod[y][x+1] == mod[y+1][x] == mod[y+1][x+1]: r += 3
        for y in range(SIZE):
            b = 0
            for x in range(SIZE):
                b = ((b << 1) & 0x7FF) | (1 if mod[y][x] else 0)
                if x >= 10 and b in (0x05D, 0x5D0): r += 40
        for x in range(SIZE):
            b = 0
            for y in range(SIZE):
                b = ((b << 1) & 0x7FF) | (1 if mod[y][x] else 0)
                if y >= 10 and b in (0x05D, 0x5D0): r += 40
        dark = sum(c for row in mod for c in row); total = SIZE*SIZE
        r += ((abs(dark*20 - total*10) + total - 1)//total - 1) * 10
        return r
    best = None; bestm = 0
    for m in range(8):
        apply_mask(m); draw_format(m); p = penalty(); apply_mask(m)
        if best is None or p < best: best = p; bestm = m
    apply_mask(bestm); draw_format(bestm)
    return mod, v

# ---------- SVG render + LAN IP ----------
def qr_svg(text, quiet=4, px=8):
    """Return an SVG string (black modules on white, quiet zone) encoding `text`."""
    mod, ver = encode_matrix(text)
    n = len(mod); dim = (n + 2*quiet) * px
    rects = []
    for y in range(n):
        for x in range(n):
            if mod[y][x]:
                rects.append('<rect x="%d" y="%d" width="%d" height="%d"/>'
                             % ((x+quiet)*px, (y+quiet)*px, px, px))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
            'width="%d" height="%d" shape-rendering="crispEdges">'
            '<rect width="100%%" height="100%%" fill="#ffffff"/>'
            '<g fill="#000000">%s</g></svg>') % (dim, dim, dim, dim, "".join(rects))

def lan_ip():
    """Primary LAN IPv4 of this machine (picks the main route; sends no packets)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        try: return socket.gethostbyname(socket.gethostname())
        except Exception: return "127.0.0.1"
    finally:
        try: s.close()
        except Exception: pass

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://%s:8080/" % lan_ip()
    print(qr_svg(url))
