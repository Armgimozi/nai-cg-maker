"""Voxel mob designs — floors 1–3 (이끼 회랑 · 거미줄 갱도 · 균사 동굴).  See README.md.

Pilot designs (reference for the other designers): moss_crawler, rusted_miner.
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the mob's left.
"""
from __future__ import annotations

import math  # noqa: F401

from ..util import h2
from ..voxel.mob_kit import MobGrid, fbm3, mirror_pt, vadd, vmul, vnorm  # noqa: F401
from ..voxel.palette import _r

# ───────────────────────────── moss_crawler (이끼 기어다니는 자) ─────────────────────────────
# Six-legged moss hunter: dark bronze-olive chitin carapace in overlapping plates, a living moss
# cushion with ferns / pale flowers on its back, amber hunter eyes, curved mandibles, and thick
# grasshopper-like hind legs folded high for its leap.

CRAWLER_CHITIN = [(11, 9, 8), (24, 20, 15), (40, 34, 24), (62, 53, 35), (92, 79, 49), (130, 113, 68),
                  (176, 158, 100), (224, 210, 156)]
GLOWCAP = [(10, 60, 66), (18, 120, 120), (40, 190, 176), (120, 236, 210), (200, 255, 236), (255, 255, 255)]
AMBER_EYE = [(110, 50, 8), (196, 112, 18), (248, 176, 44), (255, 222, 120), (255, 246, 210), (255, 255, 255)]


def _crawler_ramps(ctx):
    ctx.set_ramp('chitin', CRAWLER_CHITIN)
    ctx.set_ramp('eye', AMBER_EYE)
    ctx.set_ramp('glow', GLOWCAP)
    ctx.set_ramp('cap', GLOWCAP)


def _crawler_body(g: MobGrid, ctx, elite=False):
    # thorax (front, low) + big abdomen (back, domed): an insect silhouette with a neck dip for the head
    g.blob((0, -1.4, 0.6), (5.0, 2.0, 6.4), 'skin', 0.22, top=0.0)                       # belly
    g.plates((0, 0.0, -4.0), (4.6, 3.0, 3.4), n=2, axis=2, mat='chitin', val=0.52, lift=0.08, groove=-0.26,
             ridge=0.7, cut=lambda x, y, z: y < -1.8)
    g.plates((0, 1.0, 2.8), (6.6, 4.2, 6.0), n=4, axis=2, mat='chitin', val=0.48, lift=0.1, groove=-0.28,
             ridge=0.9, cut=lambda x, y, z: y < -1.8)
    # lateral flanges over the leg roots (lighter rim catches light)
    for s in (-1, 1):
        g.capsule((s * 4.4, -1.0, -5.6), (s * 6.0, -0.6, 4.6), 0.9, 0.8, 'chitin', 0.7)
    # abdomen tip
    g.cone((0, 0.4, 8.2), (0, -0.3, 1), 2.2, 1.3, 'chitin', 0.46, 0.75)
    # living moss on the back: the shell surface itself turns to moss (two tones), lumpy cushions on top,
    # hanging strands over the rim, a few ferns / pale flowers / glowing spore buds, two glowcaps
    g.moss_paint(coverage=0.72, mats=['chitin'], scale=4.0, up_min=0.25, depth=2)
    g.clumps(6, 1.5, 'moss', 0.56, mats=['moss'], region=lambda x, y, z: z > -2.5)
    g.sprinkle(['moss'], sprouts=6, flowers=5, glow_buds=4 if not elite else 10, hang=8, hang_len=(1.0, 2.6))
    for c, r in (((2.6, 5.5, 4.2), 0.95), ((-3.0, 5.0, 1.0), 0.8)):
        g.mushroom(c, (0.25 if c[0] > 0 else -0.25, 1, 0.1), 1.3, r, mat='cap', val=0.4, spots=0.0, glow=True)
    # bioluminescent dots along the flanks (cheap single voxels, a firefly-like hunter pattern)
    for s in (-1, 1):
        for z in (-3.6, -0.6, 2.4):
            g.dot((s * 6.6, -0.4, z), 'glow', 0.6, glow=True, prio=5)
    # dorsal thorns poking through the moss (silhouette)
    g.spikes([(0, 3.4, -4.2), (0, 5.4, 0.0), (0, 5.0, 3.6)], (0, 1, 0.5), 2.8, 0.62, 'claw', 0.3, 0.9,
             curl=(0, 0, 0.9), vary=0.15)


def _crawler_head(g: MobGrid, ctx):
    # wedge head: rounded capsule, two plates (crown + face), brow ridges over the eyes
    g.plates((0, 0.3, 0.4), (3.8, 2.5, 3.3), n=2, axis=2, mat='chitin', val=0.5, lift=0.08, reverse=True,
             cut=lambda x, y, z: y < -2.2)
    g.blob((0, -1.0, -1.0), (2.6, 1.3, 2.4), 'skin', 0.28)            # jaw / mouth plate
    for s in (-1, 1):
        g.capsule((s * 0.5, 2.1, -2.5), (s * 3.0, 1.5, -2.0), 0.6, 0.5, 'chitin', 0.74)     # brow ridge
    # four amber eyes: two big hunter eyes, two small ones above
    for s in (-1, 1):
        g.eye((s * 1.85, 0.7, -2.7), 0.9, val=0.42, socket=0.4, facing=(s * 0.5, 0.05, -1))
        g.eye((s * 0.8, 1.6, -3.0), 0.5, val=0.45, facing=(0, 0.2, -1))
    # curved mandibles (pincers) closing inward, pale tips
    for s in (-1, 1):
        g.horn((s * 1.3, -1.4, -2.7), (s * 0.35, -0.3, -1), 3.8, 0.8, curl=(-s * 1.7, 0.3, 0), mat='claw',
               val=0.35, tip_mat='tooth')
    # antennae sweeping up and back
    for s in (-1, 1):
        g.sweep([(s * 0.9, 2.3, -2.1), (s * 1.8, 4.4, -2.4), (s * 3.4, 5.8, -0.4), (s * 4.8, 5.9, 2.4)],
                0.42, 0.36, 'chitin', 0.62)


def _crawler_legs(g: MobGrid, ctx, scale=1.0):
    # legs part pivot sits 3.2 px below the body centre; ground = y −3.2
    gy = -3.2
    S = scale
    legs = [
        # (root, knee, ankle, foot) on the +X side (mirrored for −X): femur up-out, tibia near vertical
        ((4.2, 1.6, -4.8), (8.0, 6.0, -7.2), (9.6, -0.6, -9.4), (10.0, gy, -10.6)),   # fore
        ((5.0, 1.6, -0.6), (9.8, 6.2, -1.0), (11.6, -0.8, -0.6), (12.0, gy, -0.2)),   # mid
    ]
    for s in (-1, 1):
        for root, knee, ankle, foot in legs:
            R, K, A, F = [(s * q[0], q[1], q[2]) for q in (root, knee, ankle, foot)]
            g.limb([R, K, A, F], [0.85 * S, 0.6 * S, 0.45 * S, 0.32 * S], 'chitin', 0.46, joint_mat='chitin',
                   joint_val=0.64, knob=1.15)
            g.cone(F, (s * 0.2, -0.3, -1), 1.1, 0.38, 'claw', 0.25, 0.75)
            g.spikes([tuple(K[a] + (A[a] - K[a]) * 0.45 for a in range(3))], (s * 0.5, 0.2, 1), 1.2, 0.3, 'horn',
                     0.4, 0.85)
        # hind jumping leg: ribbed femur folded high and back, spurred tibia, foot forward
        R = (s * 4.4, 2.0, 4.0)
        K = (s * 7.2, 9.0, 9.2)
        F = (s * 8.2, gy + 0.5, 7.4)
        T = (s * 8.6, gy, 5.0)
        g.sweep([R, (s * 6.2, 6.4, 6.9), K], 1.45 * S, 0.6 * S, 'chitin', 0.46,
                vfn=lambda t, d, p: 0.44 + 0.14 * (1 - d) + (0.14 if int(t * 4) % 2 else 0))   # femur ribs
        g.blob(K, 0.8 * S, 'chitin', 0.8)
        g.capsule(K, F, 0.5 * S, 0.38 * S, 'chitin', 0.5)
        g.capsule(F, T, 0.38 * S, 0.3 * S, 'chitin', 0.42)
        g.cone(T, (0, -0.1, -1), 1.3, 0.36, 'claw', 0.25, 0.75)
        g.spikes([tuple(K[a] + (F[a] - K[a]) * t for a in range(3)) for t in (0.3, 0.6)], (0, 0.3, 1), 1.5, 0.32,
                 'horn', 0.45, 0.88)


def moss_crawler(look, name, part, ctx):
    _crawler_ramps(ctx)
    if name == 'body':
        g = ctx.grid(0.7)
        _crawler_body(g, ctx)
        return g
    if name == 'head':
        g = ctx.grid(0.5)
        _crawler_head(g, ctx)
        return g
    if name == 'legs':
        g = ctx.grid(0.6)
        g.light_mul = 0.5          # thin limbs: calmer baked light, no speckled rim highlights
        _crawler_legs(g, ctx)
        return g
    return None


# ───────────────────────────── rusted_miner (녹슨 광부) ─────────────────────────────
# A miner sealed in the flooded shafts until the rust water grew into him: a dented riveted hard hat with
# a brass head-lamp, a gaunt grey face with ember eyes in deep sockets, a rusted iron plate bolted into
# his chest, leather suspenders, torn sleeves and trousers stained by rust drips, a shackle and chain on
# one wrist, iron-capped boots and a rust-eaten pickaxe whose steel tips still shine.

MINER_FLESH = [(24, 28, 28), (44, 52, 50), (70, 80, 76), (100, 110, 100), (134, 142, 126), (170, 176, 156),
               (206, 208, 188)]
EMBER_EYE = [(120, 36, 6), (200, 84, 14), (250, 146, 38), (255, 206, 104), (255, 242, 196), (255, 255, 255)]
LAMP_GLOW = [(140, 96, 30), (220, 166, 58), (255, 216, 116), (255, 242, 186), (255, 252, 236), (255, 255, 255)]
WORK_SHIRT = [(16, 20, 26), (28, 36, 46), (44, 56, 68), (64, 80, 92), (90, 106, 116), (122, 134, 138),
              (162, 168, 164)]
TROUSERS = [(22, 15, 11), (40, 27, 19), (62, 41, 28), (88, 58, 37), (116, 78, 48), (150, 104, 66)]


def _miner_ramps(ctx):
    ctx.set_ramp('flesh', MINER_FLESH)
    ctx.set_ramp('eye', EMBER_EYE)
    ctx.set_ramp('glow', LAMP_GLOW)
    ctx.set_ramp('cloth', WORK_SHIRT)
    ctx.set_ramp('trousers', TROUSERS)


def _rust_patches(g, mats, amount=0.45, scale=2.2, seed=0):
    """Rust blooming through iron / skin: noise patches switch the material to rust."""
    from ..voxel.mob_kit import fbm3
    sd = g.seed + 401 + seed

    def f(x, y, z, n, m, v):
        q = fbm3(x / scale, y / scale, z / scale, sd)
        if q > 1 - amount:
            return ('rust', 0.3 + 0.6 * (q - (1 - amount)) / amount)
        return None
    g.paint(f, mats)


def _miner_head(g: MobGrid, ctx):
    # gaunt face (skull-ish block with hollow cheeks) and a protruding jaw
    g.rbox((-3.0, -3.4, -3.0), (3.0, 1.8, 3.0), 'flesh', 0.5, bevel=1.2, top=0.12)
    g.rbox((-2.5, -4.0, -3.3), (2.5, -2.2, -0.6), 'flesh', 0.42, bevel=0.6)
    for s in (-1, 1):
        g.carve_blob((s * 2.6, -1.8, -2.6), (0.9, 1.0, 0.9))                         # sunken cheeks
    g.rbox((-0.5, -1.4, -3.5), (0.5, 0.4, -2.8), 'flesh', 0.62, bevel=0.3)            # nose ridge
    g.rbox((-2.9, 0.3, -3.4), (2.9, 1.1, -2.7), 'flesh', 0.36, bevel=0.3)             # heavy brow
    for s in (-1, 1):
        g.eye((s * 1.35, -0.4, -2.85), 0.55, val=0.45, socket=0.45, facing=(s * 0.15, 0, -1))
    g.mouth((0, -2.9, -3.3), 3.0, 0.8, depth=0.8, tooth_len=0.5)
    # wiry rust-crusted beard strands
    for k, x in enumerate((-1.4, 0.0, 1.4)):
        g.sweep([(x, -3.8, -3.0), (x * 1.1, -4.8, -3.2), (x * 1.15, -5.7 + 0.4 * (k % 2), -2.9)],
                0.36, 0.3, 'rust', 0.22, smooth=True)
    # riveted hard hat: rusted iron dome, ridge, wide brim, lamp mount plate
    g.blob((0, 1.9, 0.2), (3.8, 2.7, 3.9), 'iron', 0.5, cut=lambda x, y, z: y < 1.2, top=0.2)
    g.capsule((0, 4.4, -3.0), (0, 4.5, 3.6), 0.55, 0.55, 'iron', 0.66)
    g.blob((0, 1.3, -0.4), (4.9, 0.45, 5.2), 'iron', 0.42, top=0.0)
    g.rbox((-0.9, 1.8, -4.3), (0.9, 3.6, -3.4), 'brass', 0.5, bevel=0.3)
    g.rivets([(x, 1.75, z) for x, z in ((3.6, 0.6), (-3.6, 0.6), (2.6, -2.7), (-2.6, -2.7), (2.6, 3.1), (-2.6, 3.1))],
             'brass')
    _rust_patches(g, ['iron'], 0.3, 3.0)
    g.streaks('rust', ['flesh'], density=0.14, length=(1.0, 3.0), val=0.42)
    # a torn cobweb hanging from the brim (floor 2: web-choked shafts)
    g.strands((4.6, 1.2, -1.4), (4.2, -1.8, 1.8), sag=0.6, mat='web', val=0.85)


def _miner_lamp(g: MobGrid, ctx):
    # dark brass housing along Z, a bright reflector rim and a big hot lens bulging forward (−Z),
    # a bracket down to the hat
    g.cylinder((0, 0, 1.4), (0, 0, -1.0), 1.0, 1.35, 'brass', 0.3)
    g.ring((0, 0, -1.0), 1.35, 0.42, axis='z', mat='brass', val=0.8)
    g.blob((0, 0, -1.1), (1.0, 1.0, 0.75), 'glow', 0.55, glow=True, prio=5,
           vfn=lambda x, y, z, d: 0.85 - 0.35 * d)
    g.capsule((0, -0.9, 0.6), (0, -2.6, 1.4), 0.5, 0.5, 'iron', 0.4)


def _miner_torso(g: MobGrid, ctx):
    # hunched torso: ragged shirt over a forward-sloping chest and a rounded back hump
    g.rbox((-4.2, -5.6, -2.3), (4.2, 4.6, 2.4), 'cloth', 0.48, bevel=1.5, top=0.1)
    g.blob((0, 2.6, 1.0), (4.3, 3.4, 2.6), 'cloth', 0.5)
    for s in (-1, 1):
        g.blob((s * 4.0, 4.2, 0.2), (1.9, 1.8, 2.0), 'cloth', 0.55)
    g.capsule((0, 4.6, -0.2), (0, 6.6, -1.0), 1.5, 1.3, 'flesh', 0.45)              # neck
    g.mottle(['cloth'], 0.14, 2.6)
    # rusted iron plate bolted into the chest (left side of the mob = model −X)
    g.plate((-3.9, -0.4, -3.0), (0.2, 4.0, -2.3), 'iron', 0.5, rivet_mat='iron', rivet_step=1.8, dent=0.25)
    _rust_patches(g, ['iron'], 0.5, 1.6, seed=2)
    # leather suspenders with brass buckles, belt, pouch, rope coil
    for s in (-1, 1):
        g.sweep([(s * 2.4, 4.4, -2.0), (s * 2.3, 1.0, -2.75), (s * 2.0, -3.6, -2.6)], 0.5, 0.5, 'leather', 0.45)
        g.sweep([(s * 2.4, 4.4, -1.4), (s * 2.0, 3.0, 2.8), (s * 1.8, -3.6, 2.6)], 0.5, 0.5, 'leather', 0.4)
        g.rbox((s * 2.0 - 0.5, 0.6, -3.2), (s * 2.0 + 0.5, 1.4, -2.7), 'brass', 0.6)
    g.rbox((-4.5, -5.0, -2.8), (4.5, -3.6, 2.8), 'leather', 0.36, bevel=0.5)
    g.rbox((-0.9, -5.1, -3.3), (0.9, -3.5, -2.8), 'brass', 0.55, bevel=0.2)
    g.rbox((2.6, -6.6, -2.4), (4.4, -4.4, -0.4), 'leather', 0.5, bevel=0.5)          # pouch
    g.ring((-4.4, -3.0, 0.4), 1.6, 0.5, axis='x', mat='bark', val=0.55)                # rope coil
    # torn shirt hem below the belt
    g.cloth([(-4.2, -5.2, -2.5), (4.2, -5.2, -2.5)], 1.6, 'cloth', 0.42, tatter=0.6, normal=(0, 0, -1))
    g.cloth([(4.2, -5.2, 2.5), (-4.2, -5.2, 2.5)], 1.8, 'cloth', 0.4, tatter=0.6, normal=(0, 0, 1), seed=1)
    g.streaks('rust', ['cloth'], density=0.12, length=(1.5, 5.0), val=0.4)
    # rust crust erupting from the left shoulder and the upper back (silhouette: one with the rust water)
    for base, up, n, size in (((-4.2, 5.4, 0.4), (-0.5, 1, 0.2), 4, 2.4), ((-1.6, 5.0, 2.6), (-0.2, 0.8, 1), 3, 1.9),
                              ((1.8, 4.2, 3.0), (0.3, 0.6, 1), 2, 1.5)):
        g.crystals(base, up, n=n, size=size, r=0.7, mat='rust', spread=0.8, seed=int(size * 10))
    g.blob((-3.4, 4.6, 0.8), (2.0, 1.2, 2.0), 'rust', 0.4, lump=0.3, lump_scale=1.2, prio=2)


def _miner_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # sleeve rolled up to the elbow, bony grey forearm, big knuckled hand
    g.capsule((0, -0.4, 0.1), (0, -4.6, 0.0), 1.65, 1.45, 'cloth', 0.5)
    g.ring((0, -4.7, 0.0), 1.45, 0.55, axis='y', mat='cloth', val=0.62)
    g.capsule((0, -5.4, 0.0), (0, -9.6, -0.4), 1.1, 0.95, 'flesh', 0.5)
    g.blob((0, -6.0, 0.0), 1.25, 'flesh', 0.56)                                       # elbow
    g.blob((0, -10.7, -0.5), (1.35, 1.25, 1.3), 'flesh', 0.5)
    for k, x in enumerate((-0.8, -0.27, 0.27, 0.8)):
        g.capsule((x, -11.3, -1.3), (x, -12.3, -1.0 + 0.1 * k), 0.36, 0.32, 'flesh', 0.46)
    g.capsule((o * 1.1, -10.4, -1.2), (o * 0.6, -11.4, -1.8), 0.36, 0.3, 'flesh', 0.5)  # thumb
    if right:
        # riveted iron bracer, rust eating through
        g.plate((-1.4, -9.0, -1.6), (1.4, -6.8, 1.3), 'iron', 0.5, rivet_mat='iron', rivet_step=1.2,
                face=(0, 0, -1), bevel=0.4)
        _rust_patches(g, ['iron'], 0.45, 1.2, seed=4)
    else:
        # shackle with a dangling chain
        g.ring((0, -9.2, -0.4), 1.3, 0.45, axis='y', mat='iron', val=0.5)
        g.chain([(o * 0.9, -9.5, -1.2), (o * 1.3, -11.0, -1.6), (o * 1.0, -12.6, -1.2)], 0.9, 'iron', 0.45)
    _rust_patches(g, ['flesh'], 0.2, 2.0, seed=5)
    g.streaks('rust', ['cloth'], density=0.14, length=(1.0, 3.0), val=0.38)


def _miner_pickaxe(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    # wooden handle forward from the fist (−Z), leather wraps at the grip
    g.capsule((hx, hy, hz + 2.0), (hx, hy, hz - 11.6), 0.62, 0.55, 'wood', 0.5)
    g.bands(['wood'], axis=2, period=0.9, width=0.45, amount=-0.18)
    g.capsule((hx, hy, hz + 1.6), (hx, hy, hz - 2.6), 0.75, 0.75, 'leather', 0.42)
    zh = hz - 10.8
    # iron collar
    g.rbox((hx - 1.0, hy - 1.2, zh - 0.8), (hx + 1.0, hy + 1.2, zh + 0.8), 'iron', 0.45, bevel=0.3)
    g.rivets([(hx + 1.05, hy + 0.6, zh), (hx - 1.05, hy + 0.6, zh), (hx + 1.05, hy - 0.6, zh),
              (hx - 1.05, hy - 0.6, zh)], 'iron', 0.75)
    # curved pick head: a long spike up-back and a chisel down-back, rusted, bright steel tips
    up = [(hx, hy + 0.6, zh), (hx, hy + 3.4, zh + 0.1), (hx, hy + 5.6, zh + 0.6), (hx, hy + 6.6, zh + 1.2)]
    dn = [(hx, hy - 0.6, zh), (hx, hy - 3.0, zh + 0.1), (hx, hy - 4.6, zh + 0.5), (hx, hy - 5.4, zh + 1.0)]
    for pts in (up, dn):
        g.sweep(pts, 1.05, 0.35, 'iron', 0.5, sq=(0.75, 1.0, 1.0),
                vfn=lambda t, d, p: ('blade', 0.75) if t > 0.8 else 0.42 + 0.2 * (1 - d))
    _rust_patches(g, ['iron'], 0.4, 2.0, seed=6)


def _miner_legs(g: MobGrid, ctx):
    # torn trousers on bony legs, leather knee patches, iron-capped boots; hangs from the hip pivot
    g.rbox((-3.8, -2.2, -2.0), (3.8, 0.6, 2.0), 'trousers', 0.42, bevel=0.9)
    for s in (-1, 1):
        x = s * 2.0
        g.capsule((x, -1.4, 0.0), (x + s * 0.1, -6.2, -0.3), 1.65, 1.45, 'trousers', 0.44)
        g.capsule((x + s * 0.1, -6.2, -0.3), (x, -9.4, 0.1), 1.4, 1.3, 'trousers', 0.42)
        g.rbox((x - 1.1, -7.2, -1.9), (x + 1.1, -5.4, -1.3), 'leather', 0.5, bevel=0.4)   # knee patch
        g.cloth([(x - 1.5, -8.8, -1.5), (x + 1.5, -8.8, -1.5)], 1.0, 'trousers', 0.38, tatter=0.7, seed=11 + s)
        # boot: leather shaft, iron toe cap, dark sole
        g.rbox((x - 1.6, -10.4, -1.7), (x + 1.6, -8.6, 1.7), 'leather', 0.42, bevel=0.5)
        g.rbox((x - 1.7, -11.6, -3.0), (x + 1.7, -10.0, 1.8), 'leather', 0.4, bevel=0.6)
        g.blob((x, -10.6, -2.4), (1.6, 1.0, 1.0), 'iron', 0.55, cut=lambda x_, y, z: y < -11.3)
        g.rbox((x - 1.8, -12.0, -3.1), (x + 1.8, -11.5, 1.9), 'dark', 0.2)
    _rust_patches(g, ['iron'], 0.4, 1.2, seed=8)
    g.streaks('rust', ['trousers'], density=0.2, length=(1.5, 4.0), val=0.38)


def rusted_miner(look, name, part, ctx):
    _miner_ramps(ctx)
    fn = {'head': _miner_head, 'lamp': _miner_lamp, 'torso': _miner_torso, 'arm_left': _miner_arm,
          'arm_right': _miner_arm, 'pickaxe': _miner_pickaxe, 'legs': _miner_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'head': 0.55, 'torso': 0.65, 'legs': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── shared helpers (floors 1–3) ─────────────────────────────

GLOW_MATS = ('glow', 'eye', 'core', 'rune', 'lava')


def _ramps(ctx, table):
    """Mob-wide ramps.  Glow ramps are resampled to 11 steps so the atlas pulse (±0.16 along the ramp) still
    changes colour after the budget fitter halves the ramps (coarse levels)."""
    for mat, cols in table.items():
        ctx.set_ramp(mat, _r(cols, 11) if mat in GLOW_MATS else cols)


def _twist(g, n, y0, y1, rx, rz, twist, r, mat='bark', vals=(0.42, 0.62), lean=0.0, steps=5, r_top=None,
           phase=0.0, cx=0.0, cz=0.0):
    """n root / fibre strands twisting from y0 to y1 around an elliptical section (rx(t), rz(t) px), leaning
    forward (−Z) by `lean` px at the y1 end.  Neighbouring strands alternate value so they read apart."""
    for s in range(n):
        a0 = phase + 2 * math.pi * s / n
        pts = []
        for q in range(steps):
            t = q / (steps - 1)
            a = a0 + twist * t
            X = rx(t) if callable(rx) else rx
            Z = rz(t) if callable(rz) else rz
            pts.append((cx + X * math.cos(a), y0 + (y1 - y0) * t, cz + Z * math.sin(a) - lean * t))
        g.sweep(pts, r, r_top if r_top is not None else r * 0.85, mat, vals[s % len(vals)])


def _leaf(g, pts, w, mat='leaf', val=0.5, flat=(1.0, 0.35, 1.0), vein=0.1, prio=3):
    """Leaf blade along a midrib (px points): width w swelling to the middle, flattened by `flat` (per world
    axis), lighter midrib."""
    g.sweep(pts, w, w, mat, val, prio=prio, sq=flat, rfn=lambda t: max(0.3, w * math.sin(math.pi * (0.12 + 0.86 * t)) ** 0.8),
            vfn=lambda t, d, p: val + 0.12 * t + (vein if d < 0.35 else 0.0))


def _surface_y(c, r, x, z):
    """Top of the ellipsoid (c, r) above (x, z) — to plant details on a dome."""
    q = 1 - ((x - c[0]) / r[0]) ** 2 - ((z - c[2]) / r[2]) ** 2
    return c[1] + r[1] * math.sqrt(max(0.0, q))


# ───────────────────────────── root_shambler (뿌리 비틀이) ─────────────────────────────
# A bundle of corridor roots that tore itself out of the floor and twisted into a man's shape: ropes of
# root twisting from narrow hips to hunched shoulders, a split chest where a heartwood ember smoulders,
# a knotted head with deep hollow eyes and a root-hair beard, a crown of root prongs with leaves, long arms
# ending in hooked root fingers, legs that splay into toes gripping the floor — moss and ferns on top.

ROOT_BARK = [(16, 10, 6), (36, 23, 12), (62, 40, 20), (94, 64, 34), (128, 92, 52), (164, 124, 74), (202, 164, 108)]
ROOT_MOSS = [(18, 30, 10), (34, 52, 18), (56, 80, 30), (84, 114, 44), (120, 150, 64), (160, 190, 100),
             (200, 222, 140)]
HOLLOW_EYE = [(60, 50, 8), (140, 120, 20), (214, 196, 70), (246, 236, 150), (255, 250, 214), (255, 255, 255)]
HEARTWOOD = [(90, 40, 6), (170, 90, 16), (236, 150, 40), (255, 204, 100), (255, 238, 180), (255, 255, 240)]
TAN_CAP = [(60, 34, 14), (104, 62, 26), (150, 98, 44), (196, 142, 76), (228, 188, 120), (246, 222, 170)]


def _shambler_torso(g: MobGrid, ctx):
    g.rbox((-3.4, -5.6, -1.8), (3.4, 5.4, 2.4), 'bark', 0.24, bevel=1.4)                # dark inner mass
    # six thick roots twisting from narrow hips to the hunched shoulders (leaning forward)
    _twist(g, 5, -6.6, 5.4, lambda t: 2.9 + 1.9 * math.sin(math.pi * min(1.0, t * 1.2)),
           lambda t: 1.8 + 0.8 * t, 0.6, 1.6, 'bark', (0.5, 0.72), lean=1.4, phase=0.35, steps=4)
    for s in (-1, 1):
        g.blob((s * 4.7, 4.3, 0.1), (2.3, 2.0, 2.2), 'bark', 0.56, lump=0.15, lump_scale=1.6, seed=s)
        g.cone((s * 5.4, 5.2, 1.0), (s * 0.5, 1, 0.5), 2.4, 0.6, 'bark', 0.55, 0.72)        # shoulder thorn
    g.capsule((0, 4.6, -0.8), (0, 6.6, -1.4), 1.7, 1.4, 'bark', 0.5)                    # neck stump
    g.blob((0, -5.6, 0.2), (4.0, 1.4, 2.6), 'bark', 0.42, seed=3)                        # hip knot
    # the split chest: roots torn apart over a smouldering heartwood ember
    g.carve(lambda x, y, z: abs(x) < 1.2 - 0.12 * abs(y - 1.4) and -0.8 < y < 3.8 and z < -0.6)
    g.rbox((-1.4, -1.0, -0.6), (1.4, 4.0, 0.2), 'void', 0.1, prio=2)
    g.blob((0, 1.5, -1.0), (1.1, 1.9, 0.9), 'core', 0.55, glow=True, prio=3)
    # broken root stubs on the back, root hairs from the hem
    for k, (x, d) in enumerate(((-2.4, (-0.5, 1, 0.7)), (2.0, (0.4, 1, 0.9)))):
        g.branch((x, 4.2, 1.6), d, 3.6, 0.75, depth=1, fork=2, spread=0.7, mat='bark', val=0.56, seed=k,
                 tip='leaf', tip_mat='leaf', tip_size=0.65)
    for k, x in enumerate((-2.4, 2.0)):
        g.sweep([(x, -6.4, -1.2 + 0.8 * (k % 2)), (x * 1.1, -8.0, -1.7), (x * 1.15 + 0.3, -9.4 + 0.5 * (k % 2), -1.4)],
                0.42, 0.28, 'bark', 0.46)
    g.moss_paint(coverage=0.55, mats=['bark'], scale=3.2, up_min=0.7, depth=1, patch=0.0)
    g.clumps(2, 1.3, 'moss', 0.55, mats=['moss'], region=lambda x, y, z: y > 3.0)
    g.sprinkle(['moss'], sprouts=3, flowers=2, glow_buds=1, hang=3, hang_len=(1.0, 2.4))
    g.mushroom((-5.2, 5.6, 0.8), (-0.4, 1, 0.1), 0.9, 1.1, mat='cap', val=0.45, spots=0.0)


def _shambler_head(g: MobGrid, ctx):
    g.rbox((-3.3, -2.4, -3.5), (3.3, 3.8, 2.4), 'bark', 0.48, bevel=1.5, top=0.1)
    for s in (-1, 1):                     # brows: two roots crossing over the eyes into a knotted nose
        g.sweep([(s * 3.6, 1.1, -1.4), (s * 1.8, 2.2, -3.7), (-s * 0.5, 1.3, -4.1)], 0.78, 0.55, 'bark', 0.66)
    g.blob((0, 0.1, -3.9), (0.8, 1.1, 0.8), 'bark', 0.6)
    for s in (-1, 1):                     # deep hollow eyes, a faint gold light far inside
        g.eye((s * 1.5, 0.6, -2.8), 0.45, val=0.42, socket=1.05, facing=(s * 0.2, 0, -1))
    g.carve(lambda x, y, z: abs(x) < 2.0 - 0.35 * abs(y + 1.7) and -2.6 < y < -0.9 and z < -2.1)
    g.rbox((-2.0, -2.6, -2.5), (2.0, -0.9, -1.9), 'void', 0.12)
    for x in (-0.9, 1.0):
        g.sweep([(x, -0.8, -3.1), (x + 0.3, -1.8, -3.3), (x - 0.1, -2.8, -3.0)], 0.32, 0.3, 'bark', 0.55)
    for k, x in enumerate((-1.9, 0.0, 1.8)):                # beard of root hairs
        L = 2.6 + 1.4 * (k % 2 == 0)
        g.sweep([(x, -2.7, -2.5), (x * 1.1, -2.7 - L * 0.5, -2.9), (x * 1.2 + 0.3, -2.7 - L, -2.5)], 0.45, 0.28,
                'bark', 0.5)
    for k, (x, d) in enumerate(((-2.1, (-0.6, 1, 0.5)), (0.3, (0.1, 1, 0.9)), (2.3, (0.7, 1, 0.3)))):
        g.branch((x, 3.2, 0.0), d, 3.8 + 0.8 * (k % 2), 0.7, depth=1, fork=2, spread=0.7, mat='bark', val=0.56,
                 tip='leaf', tip_mat='leaf', tip_size=0.7, seed=10 + k)
    g.moss_paint(coverage=0.6, mats=['bark'], scale=2.6, up_min=0.7, depth=1, patch=0.0)
    g.clumps(1, 1.2, 'moss', 0.55, mats=['moss'])
    g.sprinkle(['moss'], sprouts=1, flowers=2, glow_buds=1)


def _shambler_arm(g: MobGrid, ctx):
    o = ctx.out
    X = lambda y: o * 0.09 * -y                     # the long arm angles away from the body toward the hand
    g.blob((o * 0.3, -0.8, 0.0), (2.2, 2.1, 2.2), 'bark', 0.6)
    g.capsule((X(-1.0), -1.0, 0.0), (X(-6.4), -6.4, 0.1), 1.25, 1.05, 'bark', 0.52)
    g.sweep([(X(-1.2) + 1.0 * math.cos(o + 3.2 * t), -1.2 - 5.0 * t, 1.0 * math.sin(o + 3.2 * t)) for t in
             (0, 0.25, 0.5, 0.75, 1.0)], 0.5, 0.45, 'bark', 0.72)                       # a root coiling round
    g.blob((X(-6.6), -6.6, 0.1), (1.5, 1.4, 1.5), 'bark', 0.64)                        # elbow knot
    g.cone((X(-6.4) + o * 0.2, -6.4, 1.2), (o * 0.2, 0.3, 1), 2.0, 0.5, 'bark', 0.58, 0.78)
    g.capsule((X(-6.8), -6.8, 0.1), (X(-11.0), -11.0, -0.3), 1.0, 0.85, 'bark', 0.48)
    hx = X(-11.3)
    g.blob((hx, -11.3, -0.3), (1.4, 1.15, 1.4), 'bark', 0.58)
    for k, (dx, dz) in enumerate(((-1.0, -0.8), (0.2, -1.2), (1.1, -0.3), (-o * 0.4, 0.9))):   # hooked root fingers
        tip = (hx + dx * 2.1, -14.6 + 0.5 * (k % 2), dz * 1.9 - 0.4)
        g.sweep([(hx + dx * 0.6, -11.7, dz * 0.6 - 0.3), (hx + dx * 1.6, -13.1, dz * 1.5 - 0.4), tip], 0.55, 0.36,
                'bark', 0.56)
        g.cone(tip, (dx * 0.3, -0.5, -0.8 + dz * 0.3), 1.1, 0.34, 'claw', 0.3, 0.7)
    g.sweep([(X(-8) + o * 0.9, -8.0, 0.9), (X(-9.6) + o * 1.2, -9.6, 1.2), (X(-11) + o * 1.1, -11.0, 1.0)], 0.3, 0.24,
            'bark', 0.42)
    if ctx.name == 'arm_left':
        for k, d in enumerate(((o * 0.6, 1, -0.4), (o * 1, 0.5, 0.4), (0.0, 1, 0.8))):
            g.branch((o * 1.2, 0.6, 0.0), d, 1.8, 0.35, depth=0, mat='vine', val=0.5, tip='leaf', tip_mat='leaf',
                     tip_size=0.75, seed=50 + k)
    g.moss_paint(coverage=0.8, mats=['bark'], scale=2.0, up_min=0.6, depth=1, patch=0.0)
    g.sprinkle(['moss'], sprouts=1, flowers=1, hang=2, hang_len=(1.0, 2.0))


def _shambler_legs(g: MobGrid, ctx):
    gy = -12.0
    g.blob((0, -1.0, 0.2), (4.2, 1.8, 2.4), 'bark', 0.46, lump=0.15, lump_scale=1.8)
    for s in (-1, 1):
        x = s * 2.1
        g.capsule((x, -0.8, 0.0), (x + s * 0.2, -6.2, -0.3), 1.45, 1.2, 'bark', 0.48)
        _twist(g, 1, -1.0, -10.4, 1.25, 1.2, 4.0, 0.5, 'bark', (0.66,), cx=x + s * 0.1, phase=s)
        g.blob((x + s * 0.2, -6.4, -0.4), (1.5, 1.5, 1.5), 'bark', 0.6)
        g.capsule((x + s * 0.2, -6.6, -0.4), (x, gy + 1.4, 0.0), 1.15, 1.0, 'bark', 0.46)
        for k, (dx, dz) in enumerate(((s * 0.5, -1.0), (s * 1.0, -0.2), (-s * 0.2, 1.0))):
            g.branch((x, gy + 1.3, 0.0), (dx, -0.4, dz), 3.0 + 0.6 * (k % 2), 0.75, depth=0, mat='bark', val=0.5,
                     floor_y=gy, seed=20 + k * 2 + s, bend=(0, -0.6, 0))
    g.moss_paint(coverage=0.5, mats=['bark'], scale=2.4, up_min=0.7, depth=1, patch=0.0)
    g.sprinkle(['moss'], sprouts=2, flowers=1)


def root_shambler(look, name, part, ctx):
    _ramps(ctx, {'bark': ROOT_BARK, 'moss': ROOT_MOSS, 'eye': HOLLOW_EYE, 'core': HEARTWOOD, 'cap': TAN_CAP})
    fn = {'torso': _shambler_torso, 'head': _shambler_head, 'arm_left': _shambler_arm, 'arm_right': _shambler_arm,
          'legs': _shambler_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.7, 'head': 0.55, 'legs': 0.65}.get(name, 0.55))
    g.light_mul = {'torso': 0.6, 'head': 0.75}.get(name, 0.6)
    fn(g, ctx)
    return g


# ───────────────────────────── lantern_wisp (회랑 등불 정령) ─────────────────────────────
# A firefly spirit living in an old corridor lantern: a glowing orb with two dark bead eyes, a curling
# flame tuft and leaf-thin wings; the lantern's brass gimbal cage (two crossed hoops with a finial, a drip
# point, glowing rune notches, verdigris and a vine) spins around it; a fading wisp-tail trails firefly
# specks behind.

WISP_GLOW = [(70, 90, 14), (150, 180, 34), (212, 238, 96), (240, 252, 170), (255, 255, 222), (255, 255, 255)]
WISP_BRASS = [(22, 18, 8), (46, 38, 16), (80, 66, 28), (120, 100, 44), (164, 140, 70), (206, 186, 112),
              (240, 228, 170)]
WISP_PATINA = [(18, 40, 30), (34, 74, 56), (60, 116, 88), (100, 160, 124), (150, 200, 166)]
WISP_WING = [(70, 96, 20), (128, 160, 44), (186, 214, 90), (226, 242, 150), (248, 254, 210)]


def _wisp_core(g: MobGrid, ctx):
    g.blob((0, 0, 0), 2.9, 'glow', glow=True,
           vfn=lambda x, y, z, d: 0.22 + 0.62 * max(0.0, (-z * 0.8 + y * 0.3) / 2.9) ** 0.8)
    # two dark bead eyes on the front of the orb
    for s in (-1, 1):
        for dy in (0.0, 0.5):
            p = g.hit((s * 0.95, 0.1 + dy, -6.0), (0, 0, 1))
            if p:
                g.dot(p, 'void', 0.15, prio=6)
    # curling flame tuft on top
    g.cone((0, 2.3, 0.2), (0, 1, 0.4), 2.6, 1.15, 'glow', 0.72, 0.95, curl=(0, 0.2, 1.8), glow=True)
    # leaf-thin firefly wings angled up and back
    for s in (-1, 1):
        _leaf(g, [(s * 2.2, 1.0, 0.6), (s * 3.6, 2.4, 1.6), (s * 4.4, 3.6, 2.8)], 1.0, 'wing', 0.55,
              flat=(0.45, 1.0, 1.0), vein=0.12)


def _wisp_cage(g: MobGrid, ctx):
    R = 4.6
    g.ring((0, 0, 0), R, 0.55, axis='z', mat='brass', val=0.5)              # main hoop
    g.ring((0, 0, 0), R - 0.25, 0.42, axis='x', mat='brass', val=0.42)      # crossed hoop
    g.cylinder((0, R - 0.3, 0), (0, R + 0.9, 0), 1.3, 0.85, 'brass', 0.58)   # finial cap
    g.ring((0, R + 1.9, 0), 0.85, 0.32, axis='z', mat='brass', val=0.62)     # hanging loop
    g.cone((0, -R + 0.3, 0), (0, -1, 0), 2.4, 1.0, 'brass', 0.45, 0.72)       # drip point
    g.rivets([(R * math.cos(a), R * math.sin(a), -0.6) for a in (0.0, math.pi, 0.785, 2.356, 3.927, 5.498)],
             'brass', 0.8)
    # glowing rune notches on the hoop's front, verdigris patina
    for k in range(6):
        a = math.pi * (0.18 + 0.64 * k / 5) + math.pi
        g.dot((math.cos(a) * R, math.sin(a) * R, -0.7), 'rune', 0.6, glow=True, prio=6)

    def pat(x, y, z, n, m, v):
        q = fbm3(x / 1.6, y / 1.6, z / 1.6, g.seed + 7)
        return ('patina', 0.3 + (q - 0.6) * 1.6) if q > 0.6 else None
    g.paint(pat, ['brass'])
    # a vine with leaves wound round the lower hoop, a moss tuft at the drip
    pts = [(math.cos(a) * (R + 0.5), math.sin(a) * (R + 0.5), 0.6 * math.sin(a * 5))
           for a in [math.pi * (1.05 + 0.9 * k / 10) for k in range(11)]]
    g.vine(pts[3:], r=0.28, mat='vine', leaves=0.45, leaf_size=0.65, buds=0.25, bud_mat='glow')
    g.blob((0, -R - 0.2, 0), (0.9, 0.55, 0.8), 'moss', 0.5)


def _wisp_tail(g: MobGrid, ctx):
    g.sweep([(0, 0.6, -0.9), (0, 0.0, 2.0), (0.4, 0.5, 4.6), (-0.2, 1.7, 6.8), (0.3, 3.0, 8.2)], 1.5, 0.35, 'glow',
            glow=True, vfn=lambda t, d, p: 0.78 - 0.5 * t)
    for s in (-1, 1):
        g.sweep([(0, 0.2, 0.4), (s * 1.3, -0.4, 2.8), (s * 1.9, 0.4, 4.8)], 0.6, 0.3, 'glow', glow=True,
                vfn=lambda t, d, p: 0.6 - 0.4 * t)
    for p in ((1.7, 1.9, 3.0), (-2.0, 0.7, 4.2), (1.0, -1.3, 5.6), (-1.1, 2.9, 6.0), (1.9, 2.7, 7.2), (-0.5, -0.9, 7.9),
              (0.0, 4.4, 8.8)):
        g.dot(p, 'glow', 0.92, glow=True, prio=4)


def lantern_wisp(look, name, part, ctx):
    _ramps(ctx, {'glow': WISP_GLOW, 'rune': WISP_GLOW, 'brass': WISP_BRASS, 'patina': WISP_PATINA,
                 'wing': WISP_WING})
    fn = {'core': _wisp_core, 'cage': _wisp_cage, 'tail': _wisp_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.5)
    fn(g, ctx)
    return g


# ───────────────────────────── stone_beetle (돌갑충) ─────────────────────────────
# A pill-bug that took the corridor's fallen masonry as its shell: seven arched segments, each a row of
# reused blocks (staggered joints, every block its own stone, chipped rims, a faded carved glyph), moss
# and lichen in the seams; a dark chitin head with pale lichen-glow eyes and beaded antennae under the
# front plate, a horn grown from a pillar shard, stubby legs hidden under the flared rim.

BEETLE_STONE = [(26, 26, 28), (44, 45, 48), (66, 67, 70), (92, 93, 95), (120, 121, 120), (150, 150, 146),
                (182, 182, 174), (212, 212, 202)]
BEETLE_CHITIN = [(14, 13, 14), (30, 28, 30), (50, 47, 48), (74, 70, 68), (102, 96, 90), (136, 128, 118),
                 (176, 168, 154)]
BEETLE_MOSS = [(22, 34, 12), (40, 58, 20), (64, 88, 34), (96, 124, 54), (136, 160, 84), (178, 196, 128),
               (214, 226, 172)]
BEETLE_EYE = [(40, 70, 30), (90, 140, 60), (160, 204, 110), (210, 240, 170), (240, 255, 220), (255, 255, 255)]
LICHEN_GLOW = [(30, 70, 40), (60, 140, 80), (120, 210, 130), (190, 246, 190), (236, 255, 236), (255, 255, 255)]


def _beetle_shell(g: MobGrid, ctx):
    c, r, n = (0, -0.8, 0.0), (7.2, 5.4, 8.6), 7
    g.blob((0, -2.8, 0.0), (5.8, 2.0, 7.6), 'chitin', 0.3, top=0.0)                   # underside
    g.plates(c, r, n=n, axis=2, mat='stone', val=0.52, lift=0.12, groove=-0.5, lip=0.22,
             cut=lambda x, y, z: y < -3.6)
    g.plates((0, -2.8, 0.0), (7.9, 1.5, 9.0), n=n, axis=2, mat='stone', val=0.42, lift=0.1, groove=-0.45, lip=0.2,
             cut=lambda x, y, z: y < -3.9 or abs(x) < 4.5)                            # flared rim over the legs
    lo = c[2] - r[2]
    sd = g.seed + 5

    def seg(z):
        return min(n - 1, max(0, int((z - lo) / (2 * r[2]) * n)))

    def blocks(x, y, z, nrm, m, v):
        s = seg(z)
        t = (z - lo) / (2 * r[2]) * n - s
        if t < 0.16:
            if y > 0.6:
                return ('moss', 0.42 + 0.1 * (t < 0.08))            # moss grows in the upper seams
            if s in (2, 4, 6) and t < 0.1:
                return ('glow', 0.3, True)                          # glowing lichen lines down the flanks
            return None
        u = math.atan2(x, max(0.3, y - c[1] + 3.0)) / 0.9 + 0.5 * (s % 2) + h2(s, 1, sd)
        if (u % 1.0) < 0.09:
            return v - 0.22                                         # block joints
        return v + (0.12 if s % 2 else -0.05) + 0.08 * (h2(s, math.floor(u), sd) - 0.5)
    g.paint(blocks, ['stone'])
    for p in ((6.6, -2.2, -3.0), (-6.0, 0.9, 3.8), (2.8, 4.0, 6.0), (-4.4, 3.6, -5.2)):
        g.carve_blob(p, 1.0)                                                           # chipped rims
    g.runes((0, 5.0, -0.6), (0, 1, 0), w=6.0, h=4.6, mat='stone', val=0.12, glow=False, density=1.0, seed=3)
    g.cracks(['stone'], width=0.014, scale=6.0, dv=-0.26, seed=1)
    g.moss_paint(coverage=0.35, mats=['stone'], scale=3.4, up_min=0.65, depth=1, patch=0.0)
    g.clumps(3, 1.3, 'moss', 0.55, mats=['moss'])
    g.sprinkle(['moss'], sprouts=3, flowers=4, hang=4, hang_len=(1.0, 2.2))
    for p, v in (((3.4, 4.6, -1.6), 0.7), ((-2.2, 4.9, 2.4), 0.35)):                     # loose pebbles
        g.blob(p, (0.8, 0.55, 0.7), 'stone', v, prio=3)


def _beetle_head(g: MobGrid, ctx):
    g.blob((0, -0.2, -0.9), (3.3, 2.2, 2.6), 'chitin', 0.5, top=0.2)
    g.blob((0, -1.0, -2.7), (2.0, 1.0, 1.0), 'chitin', 0.4)
    for s in (-1, 1):
        g.eye((s * 2.0, 0.2, -2.4), 0.7, val=0.38, socket=0.15, facing=(s * 0.6, 0.1, -1))
        g.limb([(s * 1.4, 0.9, -2.8), (s * 3.0, 1.8, -4.2), (s * 4.0, 1.2, -5.6), (s * 4.6, 0.0, -6.6)],
               [0.46, 0.4, 0.34, 0.28], 'chitin', 0.55, knob=1.35, joint_val=0.72)
        g.horn((s * 0.9, -1.4, -2.7), (s * 0.2, -0.2, -1), 1.6, 0.45, curl=(-s * 0.7, 0, 0), mat='claw', val=0.3)
    g.moss_paint(coverage=0.5, mats=['chitin'], scale=1.6, up_min=0.6)


def _beetle_horn(g: MobGrid, ctx):
    g.horn((0, -1.2, 1.0), (0, 0.35, -1), 6.6, 1.25, curl=(0, 2.2, -0.4), mat='stone', val=0.42, rings=1.1)
    for s in (-1, 1):
        g.horn((s * 1.0, -1.0, 0.6), (s * 0.6, 0.6, -1), 2.4, 0.55, curl=(s * 0.2, 0.6, 0), mat='stone', val=0.5)
    g.moss_paint(coverage=0.6, mats=['stone'], scale=1.8, up_min=0.5)


def _beetle_legs(g: MobGrid, ctx):
    gy = -2.88
    g.light_mul = 0.6
    for s in (-1, 1):
        for k, z in enumerate((-4.6, -0.6, 3.6)):
            R = (s * 4.4, 1.0, z)
            K = (s * 6.8, 1.8, z - 0.6 + 0.6 * k)
            F = (s * 7.8, gy + 0.3, z - 1.0 + 1.0 * k)
            g.limb([R, K, F], [1.15, 0.85, 0.55], 'chitin', 0.5, joint_val=0.66, knob=1.2)
            g.cone(F, (s * 0.3, -0.5, -0.6), 0.9, 0.4, 'claw', 0.3, 0.65)
            g.spikes([tuple(K[a] + (F[a] - K[a]) * 0.4 for a in range(3))], (s * 0.4, 0.5, 0.6), 0.8, 0.28, 'chitin',
                     0.5, 0.75)


def stone_beetle(look, name, part, ctx):
    _ramps(ctx, {'stone': BEETLE_STONE, 'chitin': BEETLE_CHITIN, 'moss': BEETLE_MOSS, 'eye': BEETLE_EYE,
                 'glow': LICHEN_GLOW})
    fn = {'shell': _beetle_shell, 'head': _beetle_head, 'horn': _beetle_horn, 'legs': _beetle_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'shell': 0.7, 'legs': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── moss_crawler_alpha (우두머리 이끼 기어다니는 자) ─────────────────────────────
# The pack leader: a heavier, scarred carapace with amber-rimmed plates, pronotum horns over the head and
# twin rows of bone thorns; a tall moss crest of fern fronds and glowing spore pods that sheds spores;
# six hot amber eyes (one blinded by a scar), one antenna snapped short, great serrated mandibles.

ALPHA_CHITIN = [(7, 8, 6), (16, 18, 11), (28, 31, 17), (44, 48, 25), (66, 70, 36), (96, 100, 52), (140, 142, 82),
                (196, 196, 136)]
ALPHA_HORN = [(40, 26, 8), (86, 58, 18), (140, 100, 34), (196, 152, 60), (232, 200, 110), (250, 236, 180)]
SPORE_GLOW = [(40, 70, 10), (100, 160, 26), (170, 220, 70), (220, 248, 140), (246, 255, 210), (255, 255, 255)]
ALPHA_EYE = [(120, 30, 6), (210, 80, 14), (250, 140, 40), (255, 200, 110), (255, 240, 200), (255, 255, 255)]


def _alpha_ramps(ctx):
    _ramps(ctx, {'chitin': ALPHA_CHITIN, 'horn': ALPHA_HORN, 'glow': SPORE_GLOW, 'eye': ALPHA_EYE,
                 'cap': GLOWCAP})


ALPHA_ABD = ((0, 1.2, 3.2), (7.8, 4.6, 7.0))


def _alpha_body(g: MobGrid, ctx):
    g.blob((0, -1.8, 0.6), (6.0, 2.3, 7.4), 'skin', 0.22, top=0.0)
    g.plates((0, 0.2, -4.6), (5.6, 3.4, 3.8), n=2, axis=2, mat='chitin', val=0.5, lift=0.1, groove=-0.28, ridge=0.8,
             ridge_mat='horn', cut=lambda x, y, z: y < -2.2)
    g.plates(ALPHA_ABD[0], ALPHA_ABD[1], n=5, axis=2, mat='chitin', val=0.46, lift=0.12, groove=-0.3, ridge=1.0,
             ridge_mat='horn', cut=lambda x, y, z: y < -2.2)
    for s in (-1, 1):
        g.capsule((s * 5.2, -1.2, -6.4), (s * 7.2, -0.8, 5.6), 1.0, 0.9, 'chitin', 0.7)
        g.horn((s * 2.6, 2.6, -6.4), (s * 0.35, 0.55, -1), 4.2, 0.95, curl=(s * 0.3, 1.3, 0), mat='horn', val=0.38,
               rings=0.9)
    g.cone((0, 0.4, 10.0), (0, -0.35, 1), 2.6, 1.5, 'chitin', 0.46, 0.75)
    # twin rows of bone thorns along the shell, amber tips
    for s in (-1, 1):
        for k, z in enumerate((-0.6, 3.0, 6.6)):
            x = s * (3.9 + 0.5 * (k % 2))
            y = _surface_y(*ALPHA_ABD, x, z)
            g.cone((x, y - 0.3, z), (s * 0.55, 1, 0.45), 3.0 - 0.4 * (k == 2), 0.66, 'horn', 0.3, 0.9,
                   curl=(0, 0, 0.8))
    # claw scars across the right flank
    def scar(x, y, z, nrm, m, v):
        if x > 2.0 and any(abs(y * 0.8 + z * 0.6 - c0) < 0.32 for c0 in (0.6, 2.0, 3.4)):
            return ('horn', 0.62)
        return None
    g.paint(scar, ['chitin'])
    g.moss_paint(coverage=0.38, mats=['chitin'], scale=3.4, up_min=0.5, depth=1)
    g.clumps(3, 1.4, 'moss', 0.56, mats=['moss'], region=lambda x, y, z: z > 6 or abs(x) > 4)
    g.sprinkle(['moss'], sprouts=3, flowers=3, glow_buds=4, hang=6, hang_len=(1.0, 3.0))
    for s in (-1, 1):                         # spore sacs glowing along the flanks
        for z in (-3.4, 0.6, 4.6):
            g.blob((s * 7.5, -0.4, z), 0.75, 'glow', 0.45, glow=True, prio=5)


def _alpha_crest(g: MobGrid, ctx):
    def base_y(z):
        return _surface_y(*ALPHA_ABD, 0.0, z + 0.8) + 6.72 - 12.0

    zs = [-3.6 + 1.4 * k for k in range(8)]
    for k, z in enumerate(zs):
        y = base_y(z)
        g.blob((0, y, z), (2.6, 1.3, 1.2), 'moss', 0.48, lump=0.3, lump_scale=1.2, seed=k)
    # fern fronds fanning from the ridge (a mohawk sail), tallest in the middle
    for k, z in enumerate(zs[1:-1]):
        y = base_y(z)
        h = 4.6 + 2.0 * math.sin(math.pi * (k + 0.5) / 6)
        for s in (-1, 1):
            tip = (s * (1.8 + 0.6 * (k % 2)), y + h, z + 1.6)
            _leaf(g, [(s * 0.6, y + 0.6, z), (s * 1.2, y + h * 0.55, z + 0.4), tip], 1.0, 'leaf', 0.45,
                  flat=(1.0, 1.0, 0.4), vein=0.12)
    # glowing spore pods on short stalks, spores drifting above
    for k, (x, z, r) in enumerate(((1.6, -1.6, 1.0), (-1.8, 1.4, 1.2), (1.5, 4.2, 1.1), (-1.2, 6.0, 0.9),
                                   (0.2, 2.6, 1.3))):
        y = base_y(z)
        top = (x * 1.2, y + 2.4 + 0.6 * (k % 2), z)
        g.capsule((x * 0.5, y, z), top, 0.4, 0.35, 'vine', 0.5)
        g.blob(top, r * 1.25, 'glow', glow=True, prio=4, vfn=lambda x_, y_, z_, d: 0.62 - 0.3 * d)
    for p in ((0.6, 8.6, 0.4), (-1.4, 9.4, 3.0), (2.0, 9.0, 5.2), (-0.4, 10.4, 1.8), (1.2, 10.8, -1.2)):
        g.dot(p, 'glow', 0.7, glow=True, prio=4)
    for c, r in (((-2.6, base_y(-1.0) + 0.4, -1.0), 0.9), ((2.6, base_y(5.0) + 0.3, 5.0), 0.8)):
        g.mushroom(c, (0.3 if c[0] > 0 else -0.3, 1, 0.1), 1.0, r, mat='cap', val=0.4, spots=0.0, glow=True)
    g.sprinkle(['moss'], flowers=5, glow_buds=4)


def _alpha_head(g: MobGrid, ctx):
    g.plates((0, 0.4, 0.4), (4.3, 2.9, 3.7), n=2, axis=2, mat='chitin', val=0.5, lift=0.08, reverse=True,
             ridge=0.6, ridge_mat='horn', cut=lambda x, y, z: y < -2.4)
    g.blob((0, -1.1, -1.1), (3.0, 1.4, 2.6), 'skin', 0.28)
    for s in (-1, 1):
        g.capsule((s * 0.5, 2.5, -2.8), (s * 3.4, 1.8, -2.2), 0.7, 0.55, 'chitin', 0.74)          # brow ridge
        g.spikes([(s * 1.6, 3.0, -1.2), (s * 3.0, 2.6, 0.2)], (s * 0.4, 1, 0.5), 1.8, 0.45, 'horn', 0.35, 0.85)
    # six amber eyes; the scarred left one is blind (pale, no glow)
    for s in (-1, 1):
        if s < 0:
            g.blob((s * 2.1, 0.8, -3.0), 0.95, 'tooth', 0.35, prio=5)
            g.sweep([(s * 3.2, 2.6, -2.6), (s * 2.1, 0.8, -3.6), (s * 1.2, -0.8, -3.4)], 0.32, 0.3, 'horn', 0.62, prio=6)
        else:
            g.eye((s * 2.1, 0.8, -3.0), 1.0, val=0.42, socket=0.4, facing=(s * 0.5, 0.05, -1))
        g.eye((s * 0.9, 1.8, -3.4), 0.55, val=0.45, facing=(0, 0.2, -1))
        g.eye((s * 3.0, 1.6, -2.0), 0.45, val=0.45, facing=(s, 0.2, -0.5))
    # antennae: the right sweeps up and back, the left snapped short
    g.sweep([(0.9, 2.6, -2.4), (2.0, 4.8, -2.6), (3.8, 6.4, -0.4), (5.6, 6.6, 2.8)], 0.48, 0.38, 'chitin', 0.62)
    g.sweep([(-0.9, 2.6, -2.4), (-1.9, 4.4, -2.6), (-2.6, 5.4, -1.8)], 0.48, 0.44, 'chitin', 0.62)
    g.dot((-2.6, 5.6, -1.8), 'horn', 0.7, prio=4)


def _alpha_jaw(g: MobGrid, ctx):
    g.rbox((-1.8, -1.1, -1.6), (1.8, 0.0, 0.4), 'chitin', 0.4, bevel=0.4)                 # labium
    g.teeth((-1.4, -1.0, -1.5), (1.4, -1.0, -1.5), 4, 0.7, r=0.3, direction=(0, -1, -0.3))
    for s in (-1, 1):
        g.horn((s * 1.9, -0.2, 0.0), (s * 0.4, -0.15, -1), 5.4, 1.05, curl=(-s * 2.4, 0.4, 0), mat='claw', val=0.34,
               tip_mat='tooth')
        g.spikes([(s * 2.0, -0.2, -1.8), (s * 1.8, -0.2, -3.2)], (-s, 0, -0.3), 0.9, 0.3, 'tooth', 0.5, 0.8)


def _alpha_legs(g: MobGrid, ctx):
    gy = -3.2
    S = 1.15
    legs = [((4.8, 1.8, -5.6), (9.2, 7.0, -8.2), (11.0, -0.6, -10.8), (11.5, gy, -12.2)),
            ((5.8, 1.8, -0.6), (11.2, 7.2, -1.0), (13.2, -0.8, -0.6), (13.8, gy, -0.2))]
    for s in (-1, 1):
        for root, knee, ankle, foot in legs:
            R, K, A, F = [(s * q[0], q[1], q[2]) for q in (root, knee, ankle, foot)]
            g.limb([R, K, A, F], [0.95 * S, 0.7 * S, 0.52 * S, 0.36 * S], 'chitin', 0.46, joint_mat='chitin',
                   joint_val=0.64, knob=1.15)
            g.cone(F, (s * 0.2, -0.3, -1), 1.3, 0.42, 'claw', 0.25, 0.75)
            g.spikes([tuple(K[a] + (A[a] - K[a]) * t for a in range(3)) for t in (0.3, 0.6)], (s * 0.5, 0.2, 1), 1.4,
                     0.34, 'horn', 0.4, 0.88)
        R, K, F, T = (s * 5.0, 2.2, 4.6), (s * 8.2, 10.4, 10.6), (s * 9.4, gy + 0.6, 8.6), (s * 9.9, gy, 5.8)
        g.sweep([R, (s * 7.0, 7.4, 8.0), K], 1.7 * S, 0.7 * S, 'chitin', 0.46,
                vfn=lambda t, d, p: 0.44 + 0.14 * (1 - d) + (0.14 if int(t * 5) % 2 else 0))
        g.blob(K, 0.95 * S, 'chitin', 0.7)
        g.capsule(K, F, 0.58 * S, 0.44 * S, 'chitin', 0.5)
        g.capsule(F, T, 0.44 * S, 0.34 * S, 'chitin', 0.42)
        g.cone(T, (0, -0.1, -1), 1.5, 0.42, 'claw', 0.25, 0.75)
        g.spikes([tuple(K[a] + (F[a] - K[a]) * t for a in range(3)) for t in (0.25, 0.5, 0.75)], (0, 0.3, 1), 1.7,
                 0.36, 'horn', 0.45, 0.88)


def moss_crawler_alpha(look, name, part, ctx):
    _alpha_ramps(ctx)
    fn = {'body': _alpha_body, 'crest': _alpha_crest, 'head': _alpha_head, 'jaw': _alpha_jaw,
          'legs': _alpha_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.72, 'crest': 0.55, 'head': 0.55, 'jaw': 0.5, 'legs': 0.65}.get(name, 0.6))
    if name == 'legs':
        g.light_mul = 0.5
    fn(g, ctx)
    return g


# ───────────────────────────── moss_sproutling (이끼 새싹) ─────────────────────────────
# A seed-bud the warden sprouts from its pillars: a plump green bud cupped in pointed sepals, big glowing
# eyes and a tiny mouth, two cotyledon leaves and a glowing spore bud on top (it bursts into spores),
# stubby root feet.

SPROUT_SKIN = [(14, 30, 8), (26, 52, 14), (44, 82, 24), (68, 116, 36), (100, 152, 52), (140, 190, 80),
               (190, 226, 130), (226, 246, 180)]
SPROUT_EYE = [(80, 110, 10), (170, 200, 40), (226, 246, 110), (248, 255, 190), (255, 255, 236), (255, 255, 255)]
SPROUT_ROOT = [(30, 22, 12), (56, 42, 24), (88, 68, 40), (122, 98, 62), (160, 134, 92), (196, 172, 128)]


def _sprout_bulb(g: MobGrid, ctx):
    g.blob((0, 0.4, 0), (3.6, 3.5, 3.4), 'skin', 0.6, top=0.0,
           vfn=lambda x, y, z, d: 0.58 + 0.1 * math.cos(math.atan2(z, x) * 8) + 0.06 * y / 3.5)
    # a cup of five pointed sepals hugging the lower half (pale rims, dark between the lobes)
    def lobe(x, y, z):
        a = (math.atan2(z, x) / (2 * math.pi) * 5 + 0.15) % 1.0
        return y > -0.9 + 2.9 * (1 - abs(a - 0.5) * 2) ** 1.4
    g.blob((0, -0.5, 0), (4.4, 3.5, 4.2), 'sepal', 0.4, cut=lobe, top=0.25, prio=2)
    g.paint(lambda x, y, z, n, m, v: v + 0.3 if lobe(x, y + 0.5, z) else None, ['sepal'])     # pale lobe rims
    for s in (-1, 1):
        g.eye((s * 1.35, 1.0, -3.0), 0.8, val=0.45, socket=0.2, facing=(s * 0.2, 0, -1))
    g.carve(lambda x, y, z: abs(x) < 0.7 and -0.5 < y < 0.0 and z < -3.0)
    g.rbox((-0.7, -0.5, -3.2), (0.7, 0.0, -2.9), 'mouth', 0.2)
    g.moss_paint(coverage=0.45, mats=['skin'], scale=1.6, up_min=0.6, patch=0.0)
    g.sprinkle(['moss'], sprouts=1, flowers=2)


def _sprout_leaves(g: MobGrid, ctx):
    g.capsule((0, -3.2, 0), (0, 0.4, 0.3), 0.7, 0.55, 'vine', 0.5)
    for s in (-1, 1):
        _leaf(g, [(s * 0.4, 0.2, 0.2), (s * 2.4, 0.9, 0.0), (s * 4.6, 2.2, -0.4)], 1.7, 'leaf', 0.5,
              flat=(1.0, 0.35, 1.0), vein=0.14)
    _leaf(g, [(0, 0.2, 0.4), (0.2, 1.6, 2.0), (0, 3.2, 2.6)], 1.0, 'leaf', 0.42, flat=(1.0, 1.0, 0.4))
    g.blob((0, 1.5, 0.2), 1.25, 'glow', glow=True, vfn=lambda x, y, z, d: 0.78 - 0.3 * d)
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.4
        g.cone((math.cos(a) * 0.9, 1.0, 0.2 + math.sin(a) * 0.9), (math.cos(a), 0.9, math.sin(a)), 1.0, 0.4, 'leaf',
               0.4, 0.6)


def _sprout_legs(g: MobGrid, ctx):
    for s in (-1, 1):
        g.capsule((s * 1.4, -0.2, 0), (s * 1.6, -2.3, -0.2), 0.95, 0.8, 'bark', 0.45)
        for k, (dx, dz) in enumerate(((s * 0.4, -1.0), (s * 1.0, -0.2), (s * 0.3, 0.9))):
            g.capsule((s * 1.6, -2.4, -0.2), (s * 1.6 + dx * 1.3, -3.4, -0.2 + dz * 1.3), 0.5, 0.3, 'bark', 0.5)


def moss_sproutling(look, name, part, ctx):
    _ramps(ctx, {'skin': SPROUT_SKIN, 'eye': SPROUT_EYE, 'glow': SPORE_GLOW, 'bark': SPROUT_ROOT,
                 'sepal': [(8, 24, 14), (16, 44, 26), (28, 70, 40), (46, 100, 56), (76, 136, 76), (120, 176, 104),
                           (176, 214, 150)]})
    fn = {'bulb': _sprout_bulb, 'leaves': _sprout_leaves, 'legs': _sprout_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.5)
    fn(g, ctx)
    return g


# ───────────────────────────── tunnel_skitter (갱도 거미) ─────────────────────────────
# A quick silver spider of the web-choked shafts: a polished abdomen with dark chevrons and pale bristle
# rims, a cephalothorax crowned by eight ice-blue eyes, heavy fangs, long banded legs with knees raised
# high, and a dragline of sticky silk trailing from the spinnerets (silk draped between the legs too).

SKITTER_SILVER = [(10, 12, 18), (24, 28, 38), (46, 52, 66), (76, 84, 102), (114, 122, 142), (158, 166, 184),
                  (204, 210, 224), (240, 244, 250)]
ICE_EYE = [(30, 60, 110), (60, 120, 200), (120, 190, 250), (190, 230, 255), (236, 248, 255), (255, 255, 255)]
SILK = [(110, 116, 128), (160, 166, 178), (206, 210, 220), (234, 238, 244), (252, 252, 255)]

SKITTER_ABD = ((0, 1.4, 3.6), (3.7, 3.2, 4.3))


def _skitter_body(g: MobGrid, ctx):
    c, r = SKITTER_ABD
    g.blob((0, 0.0, -1.0), (2.6, 1.7, 2.4), 'chitin', 0.42, top=0.2)                     # thorax
    g.capsule((0, 0.2, 0.8), (0, 0.6, 1.6), 0.9, 1.0, 'chitin', 0.3)                       # pedicel
    g.blob(c, r, 'chitin', 0.5, top=0.25)
    sd = g.seed + 3

    def pattern(x, y, z, n, m, v):
        if y < c[1] + 0.6:
            return v - 0.08
        u = (z - c[2]) + 1.1 * abs(x)
        if abs(x) < 0.5 and z < c[2] + 2.5:
            return v + 0.22                                                              # pale midline
        if (u + 8.0) % 2.4 < 0.8:
            return v - 0.32                                                              # dark chevrons
        return v + 0.06 * (fbm3(x / 1.5, y / 1.5, z / 1.5, sd) - 0.5)
    g.paint(pattern, ['chitin'])
    # pale bristle rim around the abdomen's waist line, spinnerets, the dragline of silk
    for k in range(10):
        a = 2 * math.pi * k / 10
        p = (c[0] + math.cos(a) * r[0] * 0.98, c[1] + 0.3, c[2] + math.sin(a) * r[2] * 0.98)
        g.cone(p, (math.cos(a), 0.4, math.sin(a)), 0.9, 0.28, 'web', 0.6, 0.9)
    for s in (-1, 1):
        g.cone((s * 0.6, 0.2, c[2] + r[2] - 0.2), (s * 0.3, -0.4, 1), 1.4, 0.45, 'chitin', 0.5, 0.75)
    g.sweep([(0, 0.0, c[2] + r[2] + 0.8), (0, -0.8, c[2] + r[2] + 3.2), (0.6, -2.6, c[2] + r[2] + 5.4),
             (0.4, -4.0, c[2] + r[2] + 6.4)], 0.32, 0.25, 'web', 0.8)
    g.strands((0, 0.4, c[2] + r[2]), (2.6, -3.6, c[2] + r[2] + 2.6), sag=0.4, mat='web', val=0.7)


def _skitter_head(g: MobGrid, ctx):
    g.blob((0, 0.3, -0.2), (2.3, 1.6, 2.0), 'chitin', 0.48, top=0.25)
    # eight eyes: two big forward hunters, two side, four small on the crown
    for s in (-1, 1):
        g.eye((s * 0.75, 0.6, -2.0), 0.55, val=0.45, facing=(s * 0.2, 0.1, -1))
        g.eye((s * 1.7, 0.7, -1.4), 0.4, val=0.45, facing=(s, 0.1, -0.6))
        g.eye((s * 0.6, 1.5, -1.4), 0.32, val=0.5, facing=(0, 1, -0.5))
        g.eye((s * 1.3, 1.6, -0.6), 0.3, val=0.5, facing=(s * 0.4, 1, 0))
    # heavy chelicerae with black fangs, small palps
    for s in (-1, 1):
        g.blob((s * 0.8, -0.6, -1.9), (0.75, 1.0, 0.7), 'chitin', 0.38)
        g.horn((s * 0.8, -1.4, -2.2), (s * 0.1, -1, -0.4), 1.6, 0.45, curl=(-s * 0.5, 0, -0.3), mat='claw', val=0.05)
        g.limb([(s * 1.5, -0.4, -1.6), (s * 2.2, -0.2, -2.8), (s * 1.9, -1.0, -3.6)], [0.32, 0.28, 0.24], 'chitin',
               0.55, knob=1.3)


def _skitter_legs(g: MobGrid, ctx):
    gy = -1.92
    g.light_mul = 0.4
    roots_z = (-2.4, -1.4, -0.4, 0.6)
    plan = [  # knee (x, y, z), ankle (x, y, z), foot (x, z) — +X side, front → back
        ((5.0, 6.4, -5.2), (8.4, 2.2, -8.6), (9.4, -6.8 * 1.0 - 3.6)),
        ((6.4, 6.8, -2.6), (10.0, 2.0, -3.8), (11.2, -4.4)),
        ((6.4, 6.6, 1.4), (10.0, 1.8, 2.6), (11.0, 3.2)),
        ((5.0, 6.2, 4.4), (8.2, 2.0, 7.8), (9.0, 9.4)),
    ]
    for s in (-1, 1):
        for k, ((kx, ky, kz), (ax, ay, az), (fx, fz)) in enumerate(plan):
            R = (s * 1.8, 1.9, roots_z[k])
            K = (s * kx, ky, kz)
            A = (s * ax, ay, az)
            F = (s * fx, gy, fz)

            def band(t, d, p):
                return 0.3 if (t * 3) % 1.0 > 0.82 else 0.5 + 0.08 * (1 - t)
            g.limb([R, K, A, F], [0.8, 0.62, 0.46, 0.32], 'chitin', 0.5, vfn=band, joint_val=0.66, knob=1.15)
    # silk draped between two legs on each side
    g.strands((5.6, 6.2, -2.4), (5.4, 6.0, 1.6), sag=2.2, mat='web', val=0.75)
    g.strands((-8.6, 2.2, -6.0), (-9.4, 2.0, -1.8), sag=1.6, mat='web', val=0.75)


def tunnel_skitter(look, name, part, ctx):
    _ramps(ctx, {'chitin': SKITTER_SILVER, 'eye': ICE_EYE, 'web': SILK})
    fn = {'body': _skitter_body, 'head': _skitter_head, 'legs': _skitter_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.5, 'head': 0.4, 'legs': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── ore_mimic (광맥 흉내쟁이) ─────────────────────────────
# A boulder of silver ore that learned to eat miners: the lower jaw is a lumpy stone basin lined with
# dark red flesh and a ring of silver-crystal fangs; the lid (hinged at the back) is crusted with a lure of
# bright ore crystals, a swallowed miner's pickaxe still stuck in it, two ember eyes peeking from under
# its brow; a fat tongue lolls over the front teeth; four stubby stone-crab legs; cobwebs everywhere.

MIMIC_STONE = [(14, 13, 18), (26, 25, 32), (40, 39, 48), (58, 56, 66), (80, 77, 86), (104, 100, 108),
               (132, 128, 134), (164, 160, 164)]
MIMIC_ORE = [(46, 56, 78), (92, 108, 140), (148, 166, 198), (198, 214, 236), (234, 242, 252), (255, 255, 255)]
MIMIC_FLESH = [(30, 6, 12), (64, 14, 24), (104, 28, 40), (146, 48, 58), (186, 82, 86), (220, 130, 128)]
MIMIC_EYE = [(120, 40, 8), (210, 96, 20), (250, 160, 48), (255, 214, 120), (255, 244, 210), (255, 255, 255)]


def _ore_nodules(g, pts, seed=0):
    """Chunky silver ore nodules half-buried in the stone (bright cores, dark rims)."""
    for k, (p, r) in enumerate(pts):
        g.blob(p, (r, r * 0.8, r), 'ore', prio=3, lump=0.2, lump_scale=0.7, seed=seed + k,
               vfn=lambda x, y, z, d: 0.75 - 0.35 * d)


def _mimic_rock(g: MobGrid, ctx):
    g.blob((0, -0.6, 0), (7.0, 4.8, 7.0), 'stone', 0.5, lump=0.07, lump_scale=4.0, top=0.05,
           cut=lambda x, y, z: y > 4.2)
    g.blob((0, 1.4, -5.6), (5.4, 2.4, 2.0), 'stone', 0.5, cut=lambda x, y, z: y > 4.0)                 # jutting chin
    for p, rr in (((-5.6, -2.6, 3.4), (3.0, 2.6, 3.2)), ((5.2, -3.4, -2.6), (2.6, 2.2, 2.8))):
        g.blob(p, rr, 'stone', 0.46, lump=0.15, lump_scale=2.0, cut=lambda x, y, z: y > 4.0)   # side boulders
    g.carve_blob((0, 4.4, -0.6), (5.4, 2.8, 5.2))                                      # the mouth basin
    g.blob((0, 4.4, -0.6), (5.6, 3.0, 5.4), 'mouth', 0.3, prio=0, top=0.0,
           cut=lambda x, y, z: y > 4.2)
    g.paint(lambda x, y, z, n, m, v: ('mouth', 0.35 + 0.15 * (y - 1.6) / 2.6), ['mouth'])
    g.blob((0, 2.0, 0.6), (2.6, 1.2, 2.6), 'lava', 0.25, glow=True, prio=1,
           cut=lambda x, y, z: y > 2.4)                                                # the glowing gullet
    _ore_nodules(g, [((-5.4, -0.4, -4.2), 1.3), ((4.6, -2.8, -4.8), 1.0), ((6.4, 1.2, -1.0), 1.1),
                     ((-2.0, -4.0, -5.8), 0.9), ((-6.2, -2.2, 3.6), 1.2), ((3.2, 1.6, 6.2), 1.0)])
    # ring of silver-crystal fangs round the rim (front and sides), bigger at the corners
    for k in range(11):
        a = math.pi * (0.06 + 0.88 * k / 10) + math.pi
        R = (5.9, 5.6)
        p = (math.cos(a) * R[0], 4.0, -0.6 + math.sin(a) * R[1])
        L = 2.6 + 1.1 * (k in (1, 3, 7, 9)) - 0.6 * (k == 5)
        g.cone(p, (-math.cos(a) * 0.25, 1, -math.sin(a) * 0.25), L, 0.65, 'ore', 0.45, 0.95)
    # ore crystal clusters bursting from the flanks, cobwebs strung between them
    for base, up, n, size in (((-6.6, 0.8, -2.2), (-1, 0.5, -0.3), 3, 2.8), ((6.4, -1.4, 3.0), (1, 0.4, 0.4), 3, 2.4),
                              ((2.0, -2.6, -6.6), (0.3, 0.2, -1), 2, 2.0)):
        g.crystals(base, up, n=n, size=size, r=0.75, mat='ore', spread=0.7, seed=int(size * 10))
    g.strands((-6.8, 3.4, -2.4), (-3.4, 4.2, -6.2), sag=1.2, mat='web', val=0.75)
    g.strands((6.8, 1.0, 3.2), (5.2, 4.0, -3.0), sag=1.6, mat='web', val=0.75)


def _mimic_lid(g: MobGrid, ctx):
    zc = -6.4                                                                           # lid centre (hinge at 0)
    g.blob((0, 0.6, zc - 0.5), (7.7, 3.4, 8.1), 'stone', 0.54, lump=0.07, lump_scale=4.0, top=0.08,
           cut=lambda x, y, z: y < -1.6 or z > 1.0)
    g.carve_blob((0, -1.8, zc - 0.4), (5.2, 1.8, 4.9))                                  # the palate
    g.blob((0, -1.8, zc - 0.4), (5.4, 2.0, 5.1), 'mouth', 0.3, prio=0, top=0.0, cut=lambda x, y, z: y < -1.6)
    _ore_nodules(g, [((4.6, 1.8, zc - 4.4), 1.2), ((-5.6, 0.6, zc + 1.4), 1.0), ((5.8, 0.2, zc + 3.0), 0.9)],
                 seed=4)
    for k in range(10):                                                                 # upper fangs
        a = math.pi * (0.08 + 0.84 * k / 9) + math.pi
        p = (math.cos(a) * 5.8, -1.3, zc - 0.4 + math.sin(a) * 5.5)
        g.cone(p, (-math.cos(a) * 0.2, -1, -math.sin(a) * 0.2), 2.3 + 0.9 * (k % 3 == 1), 0.6, 'ore', 0.45, 0.95)
    # brow ridge with two ember eyes peeking out over the mouth
    g.rbox((-5.8, -0.8, zc - 8.8), (5.8, 1.4, zc - 6.0), 'stone', 0.6, bevel=0.8)
    for s in (-1, 1):
        g.eye((s * 2.6, -1.0, zc - 8.1), 0.65, val=0.4, socket=0.3, facing=(0, -0.2, -1))
    # the lure: a crown of bright silver ore crystals; a miner's pickaxe stuck in the crust
    g.crystals((1.2, 3.4, zc + 0.4), (0.2, 1, -0.1), n=5, size=4.4, r=1.15, mat='ore', spread=0.6, seed=5)
    g.crystals((-3.6, 2.6, zc + 2.6), (-0.6, 1, 0.3), n=3, size=2.6, r=0.8, mat='ore', spread=0.7, seed=6)
    g.blob((5.2, 2.0, zc + 2.4), (2.8, 2.4, 3.0), 'stone', 0.56, lump=0.15, lump_scale=2.0)   # lopsided crust
    g.rbox((-7.6, 0.0, zc - 3.0), (-5.2, 1.4, zc + 2.6), 'stone', 0.5, bevel=0.6)       # slab ledge
    g.capsule((-3.2, 2.0, zc - 2.4), (-6.8, 8.2, zc - 4.8), 0.5, 0.45, 'wood', 0.5)
    g.sweep([(-7.4, 7.0, zc - 5.2), (-6.8, 8.4, zc - 4.8), (-5.4, 9.2, zc - 4.0)], 0.6, 0.3, 'iron', 0.5)
    g.sweep([(-6.8, 8.4, zc - 4.8), (-8.0, 9.4, zc - 5.6), (-9.0, 9.6, zc - 6.4)], 0.6, 0.3, 'iron', 0.45)
    g.strands((-6.2, 7.4, zc - 4.4), (-1.0, 4.0, zc - 2.0), sag=1.0, mat='web', val=0.8)
    g.strands((4.6, 2.6, zc - 3.6), (6.6, 0.4, zc + 3.6), sag=1.4, mat='web', val=0.75)


def _mimic_tongue(g: MobGrid, ctx):
    pts = [(0, 0.4, 0.8), (0, 1.8, -0.6), (0, 3.4, -2.4), (0, 3.4, -3.8), (0.3, 1.8, -4.8), (0.2, 0.2, -4.6)]
    g.sweep(pts, 1.7, 0.9, 'flesh', 0.5, sq=(1.0, 0.55, 1.0),
            vfn=lambda t, d, p: 0.45 + 0.2 * t - (0.18 if abs(p[0]) < 0.3 and d > 0.6 else 0.0))


def _mimic_legs(g: MobGrid, ctx):
    gy = -1.92
    for sx in (-1, 1):
        for sz in (-1, 1):
            R = (sx * 4.6, 1.4, sz * 4.6)
            K = (sx * 7.4, 2.6, sz * 6.8)
            F = (sx * 7.7, gy + 0.4, sz * 7.0)
            g.limb([R, K, F], [1.4, 1.1, 0.9], 'stone', 0.45, joint_val=0.58, knob=1.1)
            for k in range(3):
                a = -0.6 + 0.6 * k
                d = (sx * math.cos(a) * 0.7 + 0.2 * sx, -0.6, sz * 0.7 + math.sin(a) * 0.5)
                g.cone(F, d, 1.3, 0.42, 'ore', 0.4, 0.8)


def ore_mimic(look, name, part, ctx):
    _ramps(ctx, {'stone': MIMIC_STONE, 'ore': MIMIC_ORE, 'mouth': MIMIC_FLESH, 'flesh': MIMIC_FLESH,
                 'eye': MIMIC_EYE, 'lava': MIMIC_EYE, 'web': SILK})
    fn = {'rock': _mimic_rock, 'lid': _mimic_lid, 'tongue': _mimic_tongue, 'legs': _mimic_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'rock': 0.65, 'lid': 0.65, 'tongue': 0.5, 'legs': 0.65}.get(name, 0.6))
    fn(g, ctx)
    return g


# ───────────────────────────── echo_bat (메아리 박쥐) ─────────────────────────────
# A bat grown on the shafts' echoes: a shaggy maroon body with a pale chest ruff, a pug face with a spear-
# shaped nose-leaf, an open fanged mouth glowing with the next shriek, and huge ribbed ears whose insides
# carry glowing resonance rings; wide tattered wings with finger bones and wrist thumb-claws.

BAT_FUR = [(14, 9, 10), (30, 19, 22), (50, 32, 36), (74, 48, 52), (102, 68, 70), (134, 94, 92), (168, 126, 120)]
BAT_SKIN = [(46, 22, 26), (92, 48, 54), (140, 84, 88), (186, 128, 128), (222, 174, 168), (244, 214, 206)]
BAT_MEMBRANE = [(22, 12, 16), (44, 24, 30), (72, 40, 48), (104, 60, 68), (138, 86, 92), (170, 116, 120)]
SONIC = [(110, 30, 60), (200, 70, 110), (250, 130, 160), (255, 196, 210), (255, 236, 242), (255, 255, 255)]


def _bat_body(g: MobGrid, ctx):
    g.blob((0, -0.8, 0.4), (2.4, 2.8, 2.2), 'fur', 0.45, top=0.2)                     # body
    g.blob((0, 1.9, -0.3), (2.2, 1.9, 2.0), 'fur', 0.5, top=0.2)                       # head
    g.blob((0, 0.1, -1.4), (2.0, 1.2, 1.0), 'fur', 0.72, lump=0.2, lump_scale=0.8)       # pale chest ruff
    g.blob((0, 1.4, -2.0), (1.3, 0.9, 0.7), 'skin', 0.45)                              # muzzle
    for s in (-1, 1):
        g.eye((s * 1.05, 2.4, -1.8), 0.5, val=0.45, socket=0.2, facing=(s * 0.4, 0.1, -1))
    # spear-shaped nose leaf
    g.slab2d(lambda u, v: abs(u) < 0.75 * (1 - (v - 1.6) / 1.8) and 1.6 <= v <= 3.4, (-1, 1.4), (1, 3.6), 'xy',
             depth=-2.5, half=0.25, mat='skin', vfn=lambda u, v, w, e: 0.5 + 0.2 * min(1.0, e))
    # open shrieking mouth: dark throat with a glowing larynx, fangs top and bottom
    g.carve(lambda x, y, z: abs(x) < 0.85 and 0.2 < y < 1.0 and z < -1.6)
    g.rbox((-0.85, 0.2, -1.9), (0.85, 1.0, -1.5), 'mouth', 0.2)
    g.dot((0, 0.6, -1.7), 'glow', 0.6, glow=True, prio=6)
    for s in (-1, 1):
        g.cone((s * 0.6, 1.0, -2.2), (0, -1, -0.1), 0.8, 0.28, 'tooth', 0.6, 0.9)
        g.cone((s * 0.5, 0.2, -2.0), (0, 1, -0.1), 0.6, 0.25, 'tooth', 0.6, 0.9)
    g.fur(['fur'], direction=(0, -1, 0.4), length=0.9, density=0.12, streak=0.1)
    # hind feet with hooked claws
    for s in (-1, 1):
        g.capsule((s * 1.2, -3.0, 0.6), (s * 1.4, -4.2, 0.4), 0.45, 0.35, 'skin', 0.35)
        for k in (-1, 0, 1):
            g.cone((s * 1.4 + k * 0.35, -4.3, 0.4), (k * 0.2, -0.6, -1), 0.8, 0.22, 'claw', 0.3, 0.6)


def _bat_ears(g: MobGrid, ctx):
    for s in (-1, 1):
        pts = [(s * 1.2, -0.6, 0.1), (s * 2.3, 2.0, 0.0), (s * 3.3, 4.4, 0.3), (s * 3.9, 6.0, 0.6)]
        g.sweep(pts, 1.8, 0.4, 'fur', 0.5, sq=(1.0, 1.0, 0.4),
                rfn=lambda t: 0.4 + 1.6 * math.sin(math.pi * min(1.0, 0.25 + 0.75 * t)) ** 0.7)
        # inner ear: pink membrane with ribs and two glowing resonance arcs on the front face
        base = pts[0]

        def inner(x, y, z, n, m, v, s=s, base=base):
            if n[2] >= 0:
                return None
            d = math.hypot(x - base[0], y - base[1])
            if abs(d - 2.6) < 0.32 or abs(d - 4.5) < 0.32:
                return ('rune', 0.5, True)
            return ('skin', 0.55 - (0.15 if int(d / 0.9) % 2 else 0.0))
        g.paint(inner, ['fur'])
        g.cone((s * 1.4, -0.2, -0.4), (s * 0.3, 1, -0.6), 1.6, 0.45, 'skin', 0.6, 0.8)    # tragus


def _bat_wing(g: MobGrid, side, root, wrist, tips, hip, z=0.6, val=0.5, sag=0.2, bone_r=0.42):
    """Bat wing in the XY plane at depth z: arm root → elbow → wrist, finger bones to each tip, a membrane
    spanning them whose trailing edges are bitten into shallow arcs (sagitta = sag · chord)."""
    elbow = ((root[0] + wrist[0]) / 2 + side * 0.4, max(root[1], wrist[1]) + 0.8)
    g.limb([(root[0], root[1], z), (elbow[0], elbow[1], z), (wrist[0], wrist[1], z)],
           [bone_r * 1.5, bone_r * 1.25, bone_r], 'skin', val + 0.05, knob=1.25)
    for t in tips:
        g.sweep([(wrist[0], wrist[1], z), ((wrist[0] + t[0]) / 2, (wrist[1] + t[1]) / 2 + 0.5, z), (t[0], t[1], z)],
                bone_r * 0.85, bone_r * 0.5, 'skin', val + 0.08)
    poly = [root, wrist] + list(tips) + [hip]
    cx = sum(q[0] for q in poly) / len(poly)
    cy = sum(q[1] for q in poly) / len(poly)
    bites = []
    for a_, b_ in zip(list(tips), list(tips[1:]) + [hip]):
        mx, my = (a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2
        c = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
        sg = sag * c
        R = (c * c / 4 + sg * sg) / (2 * sg)
        nx, ny = -(b_[1] - a_[1]) / c, (b_[0] - a_[0]) / c
        if nx * (mx - cx) + ny * (my - cy) < 0:
            nx, ny = -nx, -ny
        bites.append((mx + nx * (R - sg), my + ny * (R - sg), R))
    edges = list(zip(poly, poly[1:] + poly[:1]))

    def inside(x, y):
        c = False
        for (x1, y1), (x2, y2) in edges:
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        return c and all(math.hypot(x - bx, y - by) > br for bx, by, br in bites)
    xs, ys = [q[0] for q in poly], [q[1] for q in poly]
    g.slab2d(inside, (min(xs), min(ys)), (max(xs), max(ys)), 'xy', depth=z, half=0.0, mat='membrane',
             vfn=lambda u, v, w, e: val + 0.18 * (v - root[1]) / 6.0 - (0.1 if e < 0.6 else 0.0), prio=1)


def _bat_wings(g: MobGrid, ctx):
    for s in (-1, 1):
        root, wrist = (s * 1.6, 0.6), (s * 6.0, 3.2)
        tips = [(s * 12.0, 4.4), (s * 11.6, 0.2), (s * 9.6, -3.0), (s * 6.4, -4.4)]
        _bat_wing(g, s, root, wrist, tips, (s * 1.8, -2.2))
        g.cone((wrist[0], wrist[1], 0.6), (s * 0.2, 1, -0.5), 1.4, 0.38, 'claw', 0.3, 0.7)        # thumb claw


def echo_bat(look, name, part, ctx):
    _ramps(ctx, {'fur': BAT_FUR, 'skin': BAT_SKIN, 'membrane': BAT_MEMBRANE, 'eye': SONIC, 'glow': SONIC,
                 'rune': SONIC})
    fn = {'body': _bat_body, 'ears': _bat_ears, 'wings': _bat_wings}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.4, 'ears': 0.4, 'wings': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── foreman_gorrak (갱도 감독관 고르락) ─────────────────────────────
# The ghost of the overseer who whipped the miners: a hulking barrel-chested brute in a stitched leather
# apron, crossed straps with brass studs, a brass whistle on a chain and a ring of keys, riveted iron
# pauldrons with brass trim (elite), a peaked leather cap with the guild badge, a walrus moustache and a
# chewed cigar with a live ember, pale ghost-flesh with green spirit-fire eyes; a coiled whip trails from
# his left fist and his right swings a rust-eaten pick-hammer with brass bands.

GHOST_FLESH = [(20, 30, 30), (38, 54, 54), (62, 82, 80), (92, 114, 108), (126, 148, 138), (164, 184, 170),
               (204, 220, 204)]
SPIRIT_FIRE = [(20, 90, 60), (40, 170, 110), (100, 230, 160), (180, 255, 210), (230, 255, 240), (255, 255, 255)]
GORRAK_LEATHER = [(18, 11, 7), (36, 22, 13), (60, 37, 21), (88, 56, 32), (118, 78, 46), (152, 106, 64),
                  (190, 140, 92)]
GORRAK_SHIRT = [(16, 14, 14), (30, 26, 26), (48, 42, 40), (70, 62, 58), (96, 86, 78), (126, 116, 104)]
GORRAK_BRASS = [(40, 26, 8), (82, 56, 18), (134, 96, 34), (186, 142, 60), (226, 188, 100), (248, 226, 160),
                (255, 248, 220)]
MOUSTACHE = [(40, 22, 12), (80, 44, 22), (124, 74, 38), (164, 108, 60), (200, 148, 96)]


def _gorrak_ramps(ctx):
    _ramps(ctx, {'flesh': GHOST_FLESH, 'eye': SPIRIT_FIRE, 'glow': SPIRIT_FIRE, 'leather': GORRAK_LEATHER,
                 'cloth': GORRAK_SHIRT, 'brass': GORRAK_BRASS, 'hair': MOUSTACHE})


def _gorrak_torso(g: MobGrid, ctx):
    g.blob((0, 1.4, -0.2), (6.0, 5.4, 3.7), 'cloth', 0.48, top=0.12)                  # barrel chest
    g.blob((0, -3.8, -0.5), (5.3, 3.4, 3.5), 'cloth', 0.44)                            # gut
    g.capsule((0, 5.0, -0.4), (0, 7.6, -0.8), 2.2, 2.0, 'flesh', 0.45)                  # bull neck
    g.mottle(['cloth'], 0.1, 2.4)
    # stitched leather apron over the front, a heavy belt with the overseer's buckle
    g.rbox((-4.6, -7.6, -4.2), (4.6, 3.6, -3.4), 'leather', 0.46, bevel=0.6)
    g.paint(lambda x, y, z, n, m, v: v - 0.22 if (abs(abs(x) - 4.0) < 0.3 or abs(y + 7.0) < 0.3) and n[2] < 0
            else None, ['leather'])
    g.rbox((-5.6, -5.0, -4.0), (5.6, -3.6, 3.6), 'leather', 0.36, bevel=0.5)
    g.plate((-1.3, -5.3, -4.8), (1.3, -3.3, -4.0), 'brass', 0.55, rivet_mat='brass', rivet_step=1.2, bevel=0.3)
    # crossed straps with brass studs
    for s in (-1, 1):
        g.sweep([(s * 4.6, 5.0, -2.6), (s * 1.6, 1.4, -4.3), (-s * 2.6, -3.4, -4.2)], 0.55, 0.55, 'leather', 0.38)
        g.rivets([(s * 3.4, 3.6, -3.8), (s * 0.4, 0.2, -4.6), (-s * 1.8, -2.2, -4.6)], 'brass', 0.8)
    # brass whistle on a chain, a ring of keys at the belt, a coiled whip-handle on the hip
    g.chain([(-1.4, 5.6, -3.2), (-0.6, 3.6, -4.4), (0.6, 2.4, -4.6)], 0.8, 'brass', 0.5)
    g.cylinder((0.4, 2.2, -4.8), (1.8, 1.6, -4.8), 0.5, 0.42, 'brass', 0.65)
    g.ring((3.4, -6.2, -3.8), 0.9, 0.25, axis='z', mat='iron', val=0.6)
    for k in range(3):
        g.capsule((2.8 + 0.6 * k, -6.8, -4.0), (2.6 + 0.7 * k, -8.4, -4.0), 0.25, 0.25, 'iron', 0.55)
    g.ring((-5.6, -4.6, 0.6), 1.7, 0.45, axis='x', mat='leather', val=0.5)
    g.ring((-5.8, -4.6, 0.6), 1.1, 0.35, axis='x', mat='leather', val=0.42)
    # riveted iron pauldrons, two tiers, brass trim (elite)
    for s in (-1, 1):
        g.blob((s * 6.4, 5.2, 0.0), (3.5, 2.4, 3.8), 'iron', 0.5, top=0.2, cut=lambda x, y, z: y < 3.8)
        g.blob((s * 6.9, 3.6, 0.0), (3.4, 1.8, 3.9), 'iron', 0.44, top=0.2, cut=lambda x, y, z: y < 2.6)
        g.ring((s * 6.4, 3.85, 0.0), 3.5, 0.4, axis='y', mat='brass', val=0.55)
        g.rivets([(s * 6.4 + math.cos(a) * 2.6, 6.3, math.sin(a) * 2.8) for a in (0.0, 1.57, 3.14, 4.71)],
                 'brass', 0.8)
        g.spikes([(s * 7.4, 6.4, -0.8), (s * 7.4, 6.4, 1.2)], (s * 0.6, 1, 0), 1.6, 0.5, 'iron', 0.5, 0.85)
    _rust_patches(g, ['iron'], 0.35, 1.6, seed=1)
    g.streaks('rust', ['cloth', 'leather'], density=0.08, length=(1.5, 4.0), val=0.38)
    # spirit fire leaking at the collar and from a wound in the back
    for k, (x, z) in enumerate(((-2.4, 2.4), (2.6, 2.0), (0.0, 3.2))):
        g.cone((x, 4.6, z), (x * 0.1, 1, 0.5), 2.4 + 0.6 * (k == 2), 0.8, 'glow', 0.35, 0.8, glow=True,
               curl=(0, 0.4, 0.8))


def _gorrak_head(g: MobGrid, ctx):
    g.rbox((-3.6, -4.2, -3.4), (3.6, 2.4, 3.2), 'flesh', 0.48, bevel=1.3, top=0.12)
    g.rbox((-3.8, -4.8, -3.9), (3.8, -2.0, 0.6), 'flesh', 0.42, bevel=0.9)            # square jaw
    g.rbox((-3.7, 0.2, -3.9), (3.7, 1.3, -3.0), 'flesh', 0.36, bevel=0.4)             # heavy brow
    g.rbox((-0.7, -1.6, -4.4), (0.7, 0.4, -3.4), 'flesh', 0.56, bevel=0.35)           # broken nose
    for s in (-1, 1):
        g.eye((s * 1.5, -0.4, -3.4), 0.6, val=0.42, socket=0.5, facing=(0, 0, -1))
        g.carve_blob((s * 3.4, -1.6, -2.4), (0.7, 0.9, 0.9))
    # walrus moustache and mutton chops; a chewed cigar with a live ember
    for s in (-1, 1):
        g.sweep([(s * 0.3, -1.9, -4.2), (s * 1.7, -2.3, -4.3), (s * 2.7, -3.4, -4.0), (s * 3.0, -4.6, -3.6)], 0.75,
                0.4, 'hair', 0.55)
        g.rbox((s * 3.3 - 0.6, -3.8, -2.6), (s * 3.3 + 0.6, -0.6, 0.6), 'hair', 0.42, bevel=0.4)
    g.rbox((-1.6, -3.4, -4.1), (1.6, -2.9, -3.8), 'mouth', 0.2)
    g.capsule((1.2, -3.1, -4.2), (2.6, -3.5, -6.6), 0.42, 0.4, 'leather', 0.55)
    g.dot((2.6, -3.5, -6.9), 'lava', 0.6, glow=True, prio=6)
    # peaked leather cap: crown, brass band and guild badge, stiff visor
    g.blob((0, 3.0, 0.3), (4.1, 2.2, 4.0), 'leather', 0.46, cut=lambda x, y, z: y < 2.0, top=0.2)
    g.rbox((-4.0, 1.9, -3.8), (4.0, 2.7, 3.9), 'brass', 0.45, bevel=0.4)
    g.blob((0, 2.0, -4.2), (3.7, 0.4, 2.0), 'leather', 0.34, cut=lambda x, y, z: z > -3.4, top=0.0)
    g.slab2d(lambda u, v: abs(u) + abs(v - 3.8) * 1.2 < 1.2, (-1.4, 2.4), (1.4, 5.2), 'xy', depth=-4.1, half=0.3,
             mat='brass', vfn=lambda u, v, w, e: 0.5 + 0.3 * min(1.0, e))
    g.dot((0, 3.8, -4.5), 'glow', 0.5, glow=True, prio=6)


def _gorrak_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    g.capsule((0, -0.4, 0.1), (0, -5.6, 0.0), 2.3, 2.1, 'cloth', 0.5)                   # sleeve
    g.ring((0, -5.6, 0.0), 2.1, 0.6, axis='y', mat='cloth', val=0.62)                    # rolled cuff
    g.capsule((0, -6.2, 0.0), (0, -10.8, -0.4), 1.9, 1.7, 'flesh', 0.5)                  # thick forearm
    g.plate((-2.0, -10.6, -2.0), (2.0, -7.4, 1.6), 'leather', 0.45, rivet_mat='brass', rivet_step=1.3,
            face=(0, 0, -1), bevel=0.5)                                                    # studded bracer
    g.blob((0, -12.0, -0.5), (1.9, 1.6, 1.8), 'flesh', 0.5)                              # fist
    for k, x in enumerate((-1.1, -0.37, 0.37, 1.1)):
        g.blob((x, -12.6, -1.8), (0.45, 0.6, 0.5), 'flesh', 0.58)
    if not right:
        # the whip: a braided leather cord hanging from the fist, curling at the tip
        g.sweep([(0, -12.6, -1.0), (o * 0.6, -15.0, -1.6), (o * 1.4, -18.0, -1.0), (o * 1.0, -20.4, 0.4),
                 (o * -0.6, -21.2, 0.6), (o * -1.4, -20.4, -0.6)], 0.42, 0.22, 'leather', 0.45,
                vfn=lambda t, d, p: 0.38 + (0.14 if int(t * 22) % 2 else 0.0))
    _rust_patches(g, ['flesh'], 0.12, 2.0, seed=5)


def _gorrak_maul(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    # iron-banded hardwood haft, leather grip, a chain loop at the pommel
    g.capsule((hx, hy, hz + 2.4), (hx, hy, hz - 15.0), 0.8, 0.72, 'wood', 0.5)
    for zb in (-6.0, -10.0, -13.4):
        g.cylinder((hx, hy, hz + zb + 0.4), (hx, hy, hz + zb - 0.4), 0.95, 0.95, 'iron', 0.5)
    g.capsule((hx, hy, hz + 2.0), (hx, hy, hz - 2.6), 0.95, 0.95, 'leather', 0.42)
    g.ring((hx, hy, hz + 3.4), 0.8, 0.28, axis='x', mat='iron', val=0.55)
    zh = hz - 15.4
    # massive hammer block (striking face down), brass bands and rivets; a curved pick spike up-back
    g.rbox((hx - 2.7, hy - 6.6, zh - 2.7), (hx + 2.7, hy + 1.0, zh + 2.7), 'iron', 0.48, bevel=1.1)
    g.rbox((hx - 3.3, hy - 8.4, zh - 3.3), (hx + 3.3, hy - 6.4, zh + 3.3), 'iron', 0.6, bevel=0.8)
    g.rbox((hx - 2.9, hy - 8.9, zh - 2.9), (hx + 2.9, hy - 8.2, zh + 2.9), 'blade', 0.7, bevel=0.3)
    for yb in (-1.0, -5.2):
        g.rbox((hx - 2.8, hy + yb - 0.5, zh - 2.6), (hx + 2.8, hy + yb + 0.5, zh + 2.6), 'brass', 0.5, bevel=0.2)
        g.rivets([(hx + sx * 2.9, hy + yb, zh + sz * 1.6) for sx in (-1, 1) for sz in (-1, 1)], 'brass', 0.85)
    g.horn((hx, hy + 0.6, zh), (0, 1, 0.15), 7.8, 1.2, curl=(0, 0.4, 2.4), mat='iron', val=0.45)
    g.sweep([(hx, hy + 7.2, zh + 2.0), (hx, hy + 8.2, zh + 2.6)], 0.4, 0.25, 'blade', 0.8)
    _rust_patches(g, ['iron'], 0.4, 1.8, seed=6)
    g.streaks('rust', ['iron'], density=0.18, length=(1.0, 3.0), val=0.35)


def _gorrak_legs(g: MobGrid, ctx):
    g.rbox((-5.0, -2.6, -2.6), (5.0, 0.8, 2.6), 'cloth', 0.42, bevel=1.0)
    for s in (-1, 1):
        x = s * 2.6
        g.capsule((x, -1.6, 0.0), (x + s * 0.2, -6.4, -0.3), 2.2, 2.0, 'cloth', 0.44)
        g.capsule((x + s * 0.2, -6.4, -0.3), (x, -9.4, 0.1), 1.9, 1.8, 'cloth', 0.42)
        g.plate((x - 1.6, -7.6, -2.6), (x + 1.6, -5.2, -1.6), 'iron', 0.5, rivet_mat='brass', rivet_step=1.4,
                bevel=0.4)                                                                 # knee guard
        g.rbox((x - 2.0, -10.6, -2.0), (x + 2.0, -8.6, 2.0), 'leather', 0.44, bevel=0.5)    # boot shaft
        g.rbox((x - 0.4, -10.0, -2.3), (x + 0.4, -9.2, -1.9), 'brass', 0.6)                 # buckle
        g.rbox((x - 2.1, -11.6, -3.6), (x + 2.1, -10.2, 2.2), 'leather', 0.4, bevel=0.6)
        g.blob((x, -10.7, -3.0), (2.0, 1.1, 1.2), 'iron', 0.55, cut=lambda x_, y, z: y < -11.3)
        g.rbox((x - 2.2, -12.0, -3.7), (x + 2.2, -11.5, 2.3), 'dark', 0.2)
    _rust_patches(g, ['iron'], 0.4, 1.2, seed=8)
    g.streaks('rust', ['cloth'], density=0.12, length=(1.5, 3.5), val=0.38)


def foreman_gorrak(look, name, part, ctx):
    _gorrak_ramps(ctx)
    fn = {'torso': _gorrak_torso, 'head': _gorrak_head, 'arm_left': _gorrak_arm, 'arm_right': _gorrak_arm,
          'maul': _gorrak_maul, 'legs': _gorrak_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.65, 'head': 0.55, 'legs': 0.65, 'maul': 0.6}.get(name, 0.55))
    fn(g, ctx)
    return g


# ───────────────────────────── silk_hatchling (은실 새끼거미) ─────────────────────────────
# A fresh spiderling from the silk queen's egg sac: a plump pearly abdomen still wrapped in tufts of
# egg silk, a soft blue glow under its translucent skin, two big glassy eyes (and two small), stubby
# fangs and eight short bristly legs.

HATCH_SKIN = [(60, 64, 80), (100, 106, 124), (146, 152, 170), (188, 194, 210), (220, 226, 238), (244, 248, 255)]
HATCH_GLOW = [(40, 90, 160), (80, 150, 230), (140, 200, 255), (200, 236, 255), (240, 250, 255), (255, 255, 255)]


def _hatch_body(g: MobGrid, ctx):
    g.blob((0, 0.6, 1.4), (2.7, 2.3, 2.9), 'skin', 0.55, top=0.25)                   # abdomen
    g.blob((0, 0.1, -1.6), (1.8, 1.4, 1.6), 'skin', 0.5, top=0.2)                     # cephalothorax
    g.paint(lambda x, y, z, n, m, v: ('core', 0.3, True) if (y > 1.6 and abs(x) < 0.5 and 0.0 < z < 3.0) or
            (y > 1.2 and abs(abs(x) - 1.2) < 0.4 and abs(z - 1.6) < 0.5) else None, ['skin'])   # glowing heart line
    for s in (-1, 1):
        g.eye((s * 0.7, 0.5, -2.9), 0.6, val=0.45, facing=(s * 0.2, 0.1, -1))
        g.eye((s * 1.3, 1.1, -2.3), 0.35, val=0.5, facing=(s * 0.5, 0.3, -1))
        g.cone((s * 0.5, -0.6, -2.9), (0, -1, -0.3), 0.9, 0.3, 'claw', 0.3, 0.6)
    # tufts of egg silk still stuck to the back, a short silk thread
    for p, r in (((-1.2, 2.6, 2.0), 0.9), ((1.0, 2.4, 3.0), 0.75), ((0.2, 2.2, 0.4), 0.6)):
        g.blob(p, (r, r * 0.7, r), 'web', 0.75, lump=0.3, lump_scale=0.6, prio=3)
    g.sweep([(0, 0.4, 4.2), (0.3, -0.4, 5.6), (0.0, -1.6, 6.4)], 0.25, 0.25, 'web', 0.85)


def _hatch_legs(g: MobGrid, ctx):
    gy = -1.6
    g.light_mul = 0.5
    plan = [((3.2, 3.2, -3.6), (5.4, gy, -5.4)), ((3.9, 3.4, -1.6), (6.4, gy, -2.6)),
            ((3.9, 3.4, 0.4), (6.4, gy, 1.2)), ((3.2, 3.0, 2.4), (5.2, gy, 4.2))]
    for s in (-1, 1):
        for k, ((kx, ky, kz), (fx, fy, fz)) in enumerate(plan):
            R = (s * 1.3, 1.4, -2.2 + 0.7 * k)
            g.limb([R, (s * kx, ky, kz), (s * fx, fy, fz)], [0.62, 0.5, 0.4], 'skin', 0.5, joint_val=0.68, knob=1.2)


def silk_hatchling(look, name, part, ctx):
    _ramps(ctx, {'skin': HATCH_SKIN, 'eye': ICE_EYE, 'core': HATCH_GLOW, 'web': SILK})
    fn = {'body': _hatch_body, 'legs': _hatch_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.45 if name == 'body' else 0.5)
    fn(g, ctx)
    return g


# ───────────────────────────── capcap (갓꼬마) ─────────────────────────────
# A toddling poison toadstool: a glossy scarlet cap with raised cream warts and a curled rim, pink-cream
# gills underneath, a frilly ring-skirt on a plump cream stem that carries a grumpy face with toxic glowing
# eyes, tiny arm-nubs, and two stubby feet trailing mycelium threads.

CAP_RED = [(40, 8, 6), (78, 16, 10), (122, 30, 18), (166, 46, 28), (206, 74, 44), (232, 116, 76), (248, 164, 124)]
CAP_CREAM = [(96, 74, 52), (150, 124, 92), (200, 176, 140), (232, 214, 182), (248, 236, 214), (255, 250, 238)]
CAP_GILL = [(90, 52, 46), (146, 98, 86), (196, 150, 132), (230, 196, 176), (246, 226, 210)]
TOXIC_EYE = [(90, 110, 10), (170, 200, 30), (220, 244, 80), (244, 255, 160), (255, 255, 220), (255, 255, 255)]


def _capcap_cap(g: MobGrid, ctx):
    g.blob((0, -0.6, 0), (6.0, 3.8, 6.0), 'cap', 0.52, top=0.0, cut=lambda x, y, z: y < -1.7)
    g.ring((0, -1.6, 0), 5.5, 0.75, axis='y', mat='cap', val=0.36)                     # curled rim
    g.cylinder((0, -1.9, 0), (0, -1.4, 0), 5.2, 5.2, 'gill', 0.5,
               vfn=lambda t, rad, p: 0.35 + (0.25 if int((math.atan2(p[2], p[0]) + 4) * 7) % 2 else 0.0) * rad)
    # raised cream warts, bigger on the crown
    for k, (a, rr, sz) in enumerate(((0.3, 0.0, 1.1), (0.7, 2.6, 0.9), (2.4, 2.8, 0.85), (4.0, 2.5, 0.95),
                                     (5.4, 2.9, 0.8), (1.5, 4.3, 0.65), (3.2, 4.5, 0.7), (4.8, 4.4, 0.6),
                                     (6.0, 4.6, 0.6))):
        x, z = math.cos(a) * rr, math.sin(a) * rr
        y = _surface_y((0, -0.6, 0), (6.0, 3.8, 6.0), x, z)
        g.blob((x, y, z), (sz, sz * 0.6, sz), 'spot', 0.7, prio=3)


def _capcap_stem(g: MobGrid, ctx):
    g.blob((0, -2.4, 0), (3.0, 2.6, 2.8), 'spot', 0.5, top=0.15)                      # plump base
    g.cylinder((0, -1.6, 0), (0, 4.0, 0), 2.6, 2.1, 'spot', 0.55)
    # frilly ring-skirt under the cap
    g.ring((0, 3.0, 0), 2.2, 0.45, axis='y', mat='gill', val=0.6)
    pts = [(math.cos(a) * 2.5, 3.0, math.sin(a) * 2.5) for a in [2 * math.pi * k / 14 for k in range(15)]]
    g.cloth(pts, 1.1, 'gill', 0.6, tatter=0.5, normal=(0, 0, -1), holes=0.0)
    # grumpy face: toxic glowing eyes under slanted brows, a pouting mouth
    for s in (-1, 1):
        g.eye((s * 1.05, 0.2, -2.3), 0.75, val=0.45, socket=0.25, facing=(s * 0.2, 0, -1))
        g.sweep([(s * 0.4, 1.1, -2.6), (s * 1.8, 1.6, -2.2)], 0.3, 0.3, 'cap', 0.3)
    g.carve(lambda x, y, z: abs(x) < 0.6 - 0.3 * abs(y + 1.3) and -1.7 < y < -1.0 and z < -2.4)
    g.rbox((-0.6, -1.7, -2.7), (0.6, -1.0, -2.3), 'mouth', 0.2)
    for s in (-1, 1):                                                                  # arm nubs
        g.capsule((s * 2.5, -0.6, 0.0), (s * 3.6, -1.8, -0.4), 0.75, 0.65, 'spot', 0.5)


def _capcap_legs(g: MobGrid, ctx):
    for s in (-1, 1):
        g.capsule((s * 1.3, -0.2, 0.0), (s * 1.4, -2.6, -0.1), 1.0, 0.9, 'spot', 0.5)
        g.blob((s * 1.4, -3.2, -0.6), (1.1, 0.75, 1.4), 'spot', 0.52)
        for k in (-1, 1):
            g.sweep([(s * 1.4 + k * 0.5, -3.6, 0.2), (s * 1.6 + k * 1.0, -4.0, 1.2), (s * 1.8 + k * 1.6, -4.0, 2.2)],
                    0.22, 0.2, 'web', 0.8)


def capcap(look, name, part, ctx):
    _ramps(ctx, {'cap': CAP_RED, 'spot': CAP_CREAM, 'gill': CAP_GILL, 'eye': TOXIC_EYE, 'web': SILK})
    fn = {'cap': _capcap_cap, 'stem': _capcap_stem, 'legs': _capcap_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'cap': 0.6, 'stem': 0.5, 'legs': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── mycelid_shambler (균사 걸음꾼) ─────────────────────────────
# A corpse the mycelium stitched into a puppet: a dried body with the ribcage burst open over glowing
# fungal nodules, white hyphae threads lashed round it, a torn tunic, bracket fungi shelving out of the
# shoulders; its head is a broad tan cap over a bowed skull with hollow eyes, a lacy hyphae veil hanging
# from the cap rim; the arms split at the elbow into hooked, glow-tipped tendrils; one leg is bare bone,
# mycelium mats spread from the feet.

MYC_FLESH = [(26, 20, 18), (48, 38, 32), (74, 60, 48), (104, 86, 68), (134, 114, 90), (168, 148, 118)]
MYC_BONE = [(70, 62, 50), (120, 108, 88), (172, 160, 134), (212, 202, 176), (236, 230, 210), (250, 248, 236)]
MYC_CAP = [(34, 24, 16), (62, 46, 30), (96, 74, 50), (134, 108, 76), (176, 150, 112), (214, 196, 156),
           (240, 230, 200)]
MYC_CLOTH = [(20, 22, 20), (36, 40, 36), (54, 60, 52), (76, 82, 70), (100, 106, 90), (128, 132, 112)]
HYPHAE = [(150, 146, 136), (196, 192, 182), (226, 224, 214), (242, 240, 234), (252, 252, 248)]
FUNGAL_GLOW = [(30, 80, 90), (60, 150, 160), (120, 210, 210), (190, 244, 236), (234, 255, 250), (255, 255, 255)]


def _myc_torso(g: MobGrid, ctx):
    g.rbox((-4.4, -6.0, -2.6), (4.4, 5.4, 2.8), 'flesh', 0.45, bevel=1.6, top=0.1)
    g.blob((0, 4.2, 0.6), (5.0, 2.2, 2.8), 'flesh', 0.5)                               # hunched shoulders
    g.capsule((0, 4.8, -0.4), (0, 6.6, -1.4), 1.4, 1.2, 'flesh', 0.4)                   # neck
    # the burst ribcage: hollow chest, glowing nodules inside, bone ribs arching over it
    g.carve(lambda x, y, z: abs(x) < 3.1 and -1.6 < y < 4.2 and z < -0.8)
    g.rbox((-3.2, -1.8, -1.0), (3.2, 4.3, -0.4), 'void', 0.1, prio=2)
    for p, r in (((-1.2, 0.4, -1.4), 0.9), ((1.4, 1.8, -1.3), 0.75), ((0.2, 3.2, -1.2), 0.6), ((-0.4, -1.0, -1.3), 0.5)):
        g.blob(p, r, 'glow', 0.45, glow=True, prio=3)
    g.capsule((0, 4.2, -2.8), (0, -1.2, -2.6), 0.5, 0.45, 'bone', 0.55)                 # sternum
    for k, y in enumerate((3.4, 2.0, 0.6, -0.8)):
        for s in (-1, 1):
            g.sweep([(0, y, -2.8), (s * 1.8, y - 0.2, -3.0), (s * 3.2, y - 0.6, -1.8), (s * 3.6, y - 0.9, -0.2)],
                    0.38, 0.32, 'bone', 0.6 - 0.04 * k)
    # torn tunic over the left side and the back
    g.cloth([(-4.6, 4.8, 2.9), (0.4, 5.2, 3.0), (3.6, 4.6, 2.9)], lambda u: 6.0 + 4.0 * u, 'cloth', 0.45, tatter=0.6,
            normal=(0, 0, 1), holes=0.08, seed=2)
    g.cloth([(-4.7, 4.6, -2.0), (-4.7, 4.6, 2.4)], 7.4, 'cloth', 0.42, tatter=0.6, normal=(-1, 0, 0), seed=3)
    # hyphae threads lashed round the body
    for a, b in (((-4.6, 4.4, -1.8), (4.4, -3.6, -2.6)), ((4.6, 4.0, -1.0), (-4.4, -5.0, -2.2)),
                 ((-4.5, -2.0, 2.8), (4.5, 2.6, 2.9)), ((-4.2, 0.4, -2.8), (-4.6, -5.6, 1.0))):
        g.strands(a, b, sag=0.6, mat='web', val=0.85)
    # bracket fungi shelving out of the shoulders and the back
    for c, r, s in (((-4.8, 4.6, 0.6), 2.2, -1), ((5.0, 3.4, 1.2), 1.8, 1), ((1.4, 1.0, 3.2), 1.6, 0)):
        g.blob(c, (r, r * 0.38, r), 'cap', 0.55, prio=3,
               cut=lambda x, y, z, c=c, s=s: (s and (x - c[0]) * s < -0.3) or (not s and z - c[2] < -0.3),
               vfn=lambda x, y, z, d: 0.42 + 0.3 * d)
    g.mottle(['flesh'], 0.12, 2.0)


def _myc_head(g: MobGrid, ctx):
    # a bowed skull under the cap: hollow sockets, a jaw of loose teeth
    g.rbox((-2.4, -4.4, -2.8), (2.4, -0.4, 1.6), 'bone', 0.62, bevel=1.1, top=0.1)
    for s in (-1, 1):
        g.eye((s * 1.0, -1.9, -2.6), 0.42, val=0.55, socket=0.7, facing=(0, -0.1, -1))
    g.rbox((-0.4, -3.0, -3.0), (0.4, -2.4, -2.6), 'void', 0.1)
    g.rbox((-1.8, -4.8, -3.0), (1.8, -3.8, -0.4), 'bone', 0.42, bevel=0.3)
    g.teeth((-1.4, -3.8, -2.9), (1.4, -3.8, -2.9), 5, 0.6, r=0.25, direction=(0, -1, 0))
    # the broad tan cap with pale scales, gills underneath, a glowing ring at the rim
    g.blob((0, 0.6, 0.2), (5.2, 2.8, 5.2), 'cap', 0.5, top=0.0, cut=lambda x, y, z: y < -0.3,
           vfn=lambda x, y, z, d: 0.4 + 0.25 * max(0.0, y / 3.4))
    g.cylinder((0, -0.6, 0.2), (0, -0.2, 0.2), 4.9, 4.9, 'gill', 0.5,
               vfn=lambda t, rad, p: ('glow', 0.3, True) if rad > 0.86 else
               0.32 + (0.22 if int((math.atan2(p[2], p[0]) + 4) * 6) % 2 else 0.0))
    for k, (a, rr) in enumerate(((0.4, 1.4), (1.9, 2.6), (3.0, 1.8), (4.2, 3.0), (5.3, 2.2), (2.5, 3.9), (0.9, 3.8))):
        x, z = math.cos(a) * rr, 0.2 + math.sin(a) * rr
        g.dot((x, _surface_y((0, 0.6, 0.2), (5.2, 2.8, 5.2), x, z) + 0.2, z), 'spot', 0.75, prio=4)
    # a lacy hyphae veil hanging from the rim round the sides and back
    pts = [(math.cos(a) * 4.7, -0.6, 0.2 + math.sin(a) * 4.7) for a in [math.pi * (-0.1 + 1.2 * k / 18) for k in range(19)]]
    g.cloth(pts, lambda u: 3.0 + 2.2 * math.sin(math.pi * u), 'web', 0.75, tatter=0.5, normal=(0, 0, 1), holes=0.3,
            seed=4)
    g.strands((-2.4, -1.2, -2.4), (2.6, -1.0, -2.2), sag=1.6, mat='web', val=0.85)


def _myc_arm(g: MobGrid, ctx):
    o = ctx.out
    g.blob((0, -0.6, 0), (1.9, 1.8, 1.9), 'flesh', 0.5)
    g.capsule((0, -0.8, 0), (0, -5.2, 0.2), 1.3, 1.1, 'flesh', 0.45)
    g.cloth([(-1.4, -0.6, -1.2), (1.4, -0.6, -1.2)], 3.2, 'cloth', 0.4, tatter=0.6, seed=5)
    g.blob((0, -5.6, 0.2), 1.25, 'bone', 0.55)                                          # bare elbow knob
    g.strands((0.9, -1.2, -1.0), (-0.8, -5.4, -0.9), sag=0.3, mat='web', val=0.85)
    # the forearm splits into hooked fungal tendrils with glowing drain-tips
    for k, (dx, dz, L) in enumerate(((-0.9, -0.8, 1.0), (0.8, -0.5, 0.92), (0.1, 0.9, 0.86), (o * 1.2, 0.2, 0.78))):
        p0 = (dx * 0.4, -5.8, dz * 0.4)
        p1 = (dx * 1.2, -8.4 * L, dz * 1.0 - 0.2)
        p2 = (dx * 1.8, -12.0 * L, dz * 1.4 - 0.6)
        p3 = (dx * 1.0, -14.6 * L, dz * 1.0 - 1.8)
        g.tentacle(p0, p1, p2, p3, 0.75, 0.32, 'tendril', 0.5, suckers=False, tip_mat='glow', glow_tip=True)
    g.bands(['tendril'], axis=1, period=1.6, width=0.5, amount=0.12)


def _myc_legs(g: MobGrid, ctx):
    gy = -12.0
    g.rbox((-3.8, -2.2, -2.0), (3.8, 0.6, 2.0), 'cloth', 0.42, bevel=0.9)
    # left leg: torn trouser over withered flesh; right: bare bone shin wrapped in hyphae
    g.capsule((-2.0, -1.4, 0.0), (-2.1, -6.4, -0.3), 1.6, 1.4, 'cloth', 0.44)
    g.capsule((-2.1, -6.4, -0.3), (-2.0, -10.6, 0.1), 1.3, 1.1, 'flesh', 0.42)
    g.cloth([(-3.6, -6.0, -1.5), (-0.5, -6.0, -1.5)], 1.6, 'cloth', 0.38, tatter=0.7, seed=11)
    g.capsule((2.0, -1.4, 0.0), (2.1, -6.0, -0.3), 1.5, 1.2, 'flesh', 0.42)
    g.blob((2.1, -6.4, -0.3), 1.0, 'bone', 0.6)
    g.capsule((2.1, -6.8, -0.3), (2.0, -10.6, 0.1), 0.6, 0.5, 'bone', 0.58)
    g.vine_wrap((2.05, -10.4, 0), (2.05, -6.6, 0), 0.75, turns=2.0, mat='web', r=0.22, leaves=0.0)
    for s in (-1, 1):
        x = s * 2.0
        g.rbox((x - 1.3, gy, -2.6), (x + 1.3, gy + 1.6, 1.2), 'flesh' if s < 0 else 'bone', 0.45, bevel=0.5)
        for k, (dx, dz) in enumerate(((s * 0.8, -1.0), (s * 1.0, 0.4), (-s * 0.4, 1.0))):    # mycelium mat
            g.branch((x, gy + 0.3, 0.0), (dx, -0.2, dz), 2.8, 0.35, depth=1, fork=2, spread=0.8, mat='web', val=0.8,
                     floor_y=gy, seed=30 + k * 2 + s)


def mycelid_shambler(look, name, part, ctx):
    _ramps(ctx, {'flesh': MYC_FLESH, 'bone': MYC_BONE, 'cap': MYC_CAP, 'cloth': MYC_CLOTH, 'web': HYPHAE,
                 'spot': HYPHAE, 'glow': FUNGAL_GLOW, 'eye': FUNGAL_GLOW, 'tendril': MYC_CAP,
                 'gill': [(70, 56, 44), (124, 104, 84), (176, 156, 128), (214, 200, 172), (236, 228, 206)]})
    fn = {'torso': _myc_torso, 'head': _myc_head, 'arm_left': _myc_arm, 'arm_right': _myc_arm,
          'legs': _myc_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.6, 'head': 0.55, 'legs': 0.6}.get(name, 0.5))
    g.light_mul = 0.7
    fn(g, ctx)
    return g


# ───────────────────────────── spore_turret (포자 포탑 버섯) ─────────────────────────────
# A giant rooted mushroom-cannon: a swollen violet volva with pale ribs and glowing spore pores, roots
# gripping the floor, a ringed neck; a broad cap with pale spots, a curled rim and softly glowing gills; on
# top a puffball chimney whose throat glows with the next spore charge, puffs drifting up from it.

TUR_SKIN = [(18, 10, 22), (36, 20, 42), (62, 36, 70), (92, 56, 100), (124, 80, 132), (160, 112, 166),
            (200, 156, 204), (232, 200, 236)]
TUR_CAP = [(26, 12, 30), (52, 24, 58), (86, 42, 94), (122, 64, 130), (160, 94, 166), (198, 134, 202),
           (230, 184, 232)]
TUR_SPOT = [(150, 120, 156), (198, 170, 204), (230, 210, 234), (246, 236, 248), (255, 250, 255)]
SPORE_PINK = [(110, 30, 110), (190, 70, 180), (240, 130, 230), (255, 196, 246), (255, 236, 252), (255, 255, 255)]


def _turret_bulb(g: MobGrid, ctx):
    gy = -5.6
    g.blob((0, -0.8, 0), (5.8, 4.4, 5.8), 'skin', 0.5, top=0.15,
           vfn=lambda x, y, z, d: 0.46 + (0.16 if math.cos(math.atan2(z, x) * 7) > 0.55 else 0.0))   # pale ribs
    g.cylinder((0, 2.6, 0), (0, 9.0, 0), 2.6, 2.0, 'skin', 0.56)                         # neck
    g.ring((0, 6.6, 0), 2.4, 0.5, axis='y', mat='spot', val=0.5)                         # ring
    pts = [(math.cos(a) * 2.7, 6.6, math.sin(a) * 2.7) for a in [2 * math.pi * k / 16 for k in range(17)]]
    g.cloth(pts, 1.2, 'spot', 0.45, tatter=0.45, normal=(0, 0, -1), holes=0.0)
    # glowing spore pores in rows between the ribs
    for k in range(7):
        a = 2 * math.pi * (k + 0.5) / 7
        for y in (-2.2, 0.2, 2.0):
            rr = 5.8 * math.sqrt(max(0.0, 1 - ((y + 0.8) / 4.4) ** 2))
            g.dot((math.cos(a) * rr, y, math.sin(a) * rr), 'glow', 0.4, glow=True, prio=5)
    # roots gripping the floor
    for k in range(7):
        a = 2 * math.pi * k / 7 + 0.3
        g.branch((math.cos(a) * 4.4, gy + 1.6, math.sin(a) * 4.4), (math.cos(a), -0.35, math.sin(a)), 3.6, 0.9,
                 depth=1, fork=2, spread=0.6, mat='bark', val=0.4, floor_y=gy, seed=k)


def _turret_cap(g: MobGrid, ctx):
    g.blob((0, -0.6, 0), (9.0, 4.4, 9.0), 'cap', 0.52, top=0.0, cut=lambda x, y, z: y < -1.4)
    g.ring((0, -1.2, 0), 8.6, 0.85, axis='y', mat='cap', val=0.32)                     # curled rim
    # glowing gills underneath (bioluminescent stripes), a hole for the chimney on top
    g.cylinder((0, -1.6, 0), (0, -1.1, 0), 8.2, 8.2, 'gill', 0.4,
               vfn=lambda t, rad, p: ('glow', 0.25 + 0.2 * rad, True) if int((math.atan2(p[2], p[0]) + 4) * 9) % 2
               and rad > 0.35 else 0.3)
    g.carve(lambda x, y, z: x * x + z * z < 2.2 ** 2 and y > 2.0)
    for k, (a, rr, sz) in enumerate(((0.2, 4.2, 1.4), (1.3, 6.4, 1.1), (2.3, 4.6, 1.3), (3.3, 6.6, 1.0),
                                     (4.2, 4.4, 1.2), (5.2, 6.3, 1.1), (0.75, 7.6, 0.8), (2.8, 7.7, 0.8),
                                     (4.7, 7.6, 0.8), (5.9, 3.4, 0.9))):
        x, z = math.cos(a) * rr, math.sin(a) * rr
        y = _surface_y((0, -0.6, 0), (9.0, 4.4, 9.0), x, z)
        if k % 3 == 2:
            g.blob((x, y, z), (sz * 0.6, sz * 0.35, sz * 0.6), 'glow', 0.4, glow=True, prio=4)   # spore pore
        else:
            g.blob((x, y, z), (sz, sz * 0.45, sz), 'spot', 0.72, prio=3)


def _turret_nozzle(g: MobGrid, ctx):
    g.cylinder((0, -1.6, 0), (0, 2.2, 0), 2.2, 1.7, 'cap', 0.55, hollow=1.0)
    g.blob((0, -0.6, 0), (2.2, 1.2, 2.2), 'cap', 0.48)
    g.ring((0, 2.3, 0), 1.7, 0.5, axis='y', mat='spot', val=0.6)
    for k in range(8):                                                                   # frilled lip
        a = 2 * math.pi * k / 8
        g.cone((math.cos(a) * 1.9, 2.2, math.sin(a) * 1.9), (math.cos(a), 0.9, math.sin(a)), 1.2, 0.4, 'spot', 0.5,
               0.8)
    g.cylinder((0, 0.4, 0), (0, 2.0, 0), 1.05, 1.05, 'glow', 0.55, glow=True)             # the glowing charge
    for p, r in (((0.4, 4.2, -0.2), 0.8), ((-0.8, 5.6, 0.6), 0.6), ((0.6, 6.8, 0.3), 0.45)):
        g.blob(p, r, 'glow', 0.7, glow=True, prio=4)


def spore_turret(look, name, part, ctx):
    _ramps(ctx, {'skin': TUR_SKIN, 'cap': TUR_CAP, 'spot': TUR_SPOT, 'glow': SPORE_PINK, 'gill': TUR_SKIN})
    fn = {'bulb': _turret_bulb, 'cap': _turret_cap, 'nozzle': _turret_nozzle}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'bulb': 0.6, 'cap': 0.7, 'nozzle': 0.45}.get(name, 0.6))
    fn(g, ctx)
    return g


# ───────────────────────────── glowcap_moth (빛갓 나방) ─────────────────────────────
# A moth that drank the mushrooms' light: a plush golden thorax collar, a banded tapering abdomen, big dark
# compound eyes, a curled proboscis and feathery antennae; dusty gold wings with dark borders, pale veins
# and glowing mushroom-light eyespots (big on the forewings, small on the hindwings).

MOTH_FUR = [(30, 24, 12), (62, 50, 24), (104, 86, 40), (150, 126, 60), (196, 170, 90), (232, 212, 140),
            (250, 240, 196)]
MOTH_WING = [(24, 20, 10), (52, 42, 20), (92, 76, 34), (138, 116, 52), (184, 158, 76), (222, 200, 120),
             (246, 232, 176)]
MOTH_GLOW = [(110, 90, 10), (200, 170, 30), (248, 220, 80), (255, 244, 160), (255, 252, 220), (255, 255, 255)]


def _moth_body(g: MobGrid, ctx):
    g.blob((0, 0.6, -3.5), (1.5, 1.4, 1.3), 'fur', 0.45)                              # head
    for s in (-1, 1):
        g.eye((s * 1.1, 0.7, -3.9), 0.75, val=0.2, facing=(s, 0, -0.5))                 # compound eyes
    g.sweep([(0, 0.0, -4.6), (0, -0.8, -5.4), (0, -1.6, -5.0), (0, -1.4, -4.4)], 0.22, 0.2, 'claw', 0.3)   # proboscis
    g.blob((0, 0.8, -1.4), (2.2, 2.1, 2.1), 'fur', 0.6, top=0.2)                       # thorax
    g.fur(['fur'], direction=(0, -0.4, 1), length=1.0, density=0.22, streak=0.12)
    g.blob((0, 1.0, -2.4), (2.5, 1.4, 1.2), 'fur', 0.85, lump=0.25, lump_scale=0.7)      # pale collar ruff
    pts = [(0, 0.4, 0.4), (0, 0.1, 2.4), (0, -0.4, 4.4), (0, -0.9, 6.0)]
    g.sweep(pts, 1.9, 0.6, 'fur', 0.5, vfn=lambda t, d, p: 0.4 + (0.28 if int(t * 7) % 2 else 0.0))   # banded abdomen
    for s in (-1, 1):                                                                   # tucked legs
        for k, z in enumerate((-2.2, -1.2, -0.2)):
            g.limb([(s * 1.2, -0.6, z), (s * 2.0, -1.6, z - 0.4), (s * 1.8, -3.0, z - 0.2)], [0.28, 0.24, 0.2], 'claw',
                   0.4, knob=0)


def _moth_antennae(g: MobGrid, ctx):
    from ..voxel.core import catmull, resample
    for s in (-1, 1):
        shaft = [(s * 0.4, -0.4, 0.4), (s * 1.4, 1.8, -0.4), (s * 2.8, 3.8, -0.6), (s * 3.8, 5.0, 0.0)]
        g.sweep(shaft, 0.3, 0.22, 'fur', 0.6)
        for k, (p, t) in enumerate(resample(catmull(shaft, 8), 0.8)[2:-1]):       # feathery barbs, fore and aft
            L = 1.9 * (1 - 0.55 * t)
            side = 1 if k % 2 else -1
            g.cone(p, (s * 0.7, 0.15, -0.9 * side), L, 0.2, 'fur', 0.5, 0.85, r_tip=0.2)


def _moth_wing_pattern(fx, fz, eye, eye_r, border):
    """vfn for a wing in the XZ plane: dark border, pale veins from the root, glowing eyespot."""
    def f(u, v, w, e):
        d = math.hypot(u - eye[0], v - eye[1])
        if d < eye_r * 0.45:
            return ('glow', 0.7, True)
        if d < eye_r * 0.7:
            return ('glow', 0.35, True)
        if d < eye_r:
            return 0.1
        if e < border:
            return 0.18
        a = math.atan2(v - fz, u - fx)
        if abs(((a * 5.0) % 1.0) - 0.5) < 0.07:
            return 0.72
        return 0.5 + 0.12 * (1 - min(1.0, math.hypot(u - fx, v - fz) / 12.0))
    return f


def _poly(pts):
    edges = list(zip(pts, pts[1:] + pts[:1]))

    def inside(x, y):
        c = False
        for (x1, y1), (x2, y2) in edges:
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        return c
    return inside


def _moth_wings(g: MobGrid, ctx):
    for s in (-1, 1):
        fore = [(s * 1.4, -2.6), (s * 6.0, -5.2), (s * 12.4, -5.4), (s * 14.4, -3.6), (s * 13.2, -0.4), (s * 9.0, 1.8),
                (s * 1.8, 0.8)]
        hind = [(s * 1.6, 0.2), (s * 8.4, 2.0), (s * 10.0, 4.8), (s * 8.0, 7.8), (s * 4.2, 8.2), (s * 1.8, 4.2)]
        for poly, eye, er, y0 in ((fore, (s * 8.8, -2.0), 2.6, 0.0), (hind, (s * 6.4, 4.8), 1.7, -0.5)):
            xs = [q[0] for q in poly]
            zs = [q[1] for q in poly]
            # inner wing at y0, outer half one voxel higher (a shallow dihedral catching the light)
            inner = _poly(poly)
            g.slab2d(lambda u, v, inner=inner: inner(u, v) and abs(u) < 7.0, (min(xs), min(zs)), (max(xs), max(zs)),
                     'xz', depth=y0, half=0.0, mat='wing', vfn=_moth_wing_pattern(s * 1.6, -0.8, eye, er, 0.9))
            g.slab2d(lambda u, v, inner=inner: inner(u, v) and abs(u) >= 7.0, (min(xs), min(zs)), (max(xs), max(zs)),
                     'xz', depth=y0 + 0.5, half=0.0, mat='wing', vfn=_moth_wing_pattern(s * 1.6, -0.8, eye, er, 0.9))
        g.capsule((s * 1.2, 0.0, -2.2), (s * 12.4, 0.5, -5.0), 0.4, 0.25, 'wing', 0.62)     # leading-edge vein
        for k in range(4):                                                                 # glowing border dots
            g.dot((s * (10.6 + 0.9 * k), 0.6, -4.8 + 1.3 * k), 'glow', 0.5, glow=True, prio=4)


def glowcap_moth(look, name, part, ctx):
    _ramps(ctx, {'fur': MOTH_FUR, 'wing': MOTH_WING, 'glow': MOTH_GLOW, 'eye': MOTH_GLOW})
    fn = {'body': _moth_body, 'antennae': _moth_antennae, 'wings': _moth_wings}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.4, 'antennae': 0.4, 'wings': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── spore_mother (포자 어미 군락체) ─────────────────────────────
# A living fungal colony rooted deep in the cave: a heaving mound of violet-pink flesh crusted with
# glowing spore sacs and veined, draped in white hyphae, sprouting a brood of red capcaps; a crown of huge
# spotted caps with luminous gold-trimmed gills (elite); a gaping maw with a glowing throat under a
# fanged upper lip; thick hyphae roots spreading over the floor, their tips glowing.

MOTHER_FLESH = [(20, 10, 22), (42, 20, 44), (70, 34, 70), (104, 54, 98), (140, 78, 126), (178, 110, 156),
                (212, 150, 188), (238, 196, 220)]
MOTHER_CAP = [(30, 10, 28), (60, 22, 56), (98, 40, 90), (140, 64, 124), (184, 98, 160), (220, 142, 196),
              (244, 192, 226)]
MOTHER_SPOT = [(170, 130, 160), (214, 180, 204), (240, 218, 234), (252, 240, 248), (255, 252, 255)]
MOTHER_GLOW = [(120, 30, 90), (200, 70, 150), (250, 130, 200), (255, 196, 232), (255, 236, 248), (255, 255, 255)]
GOLD_GILL = [(80, 54, 14), (150, 108, 30), (214, 168, 60), (244, 214, 120), (255, 240, 190), (255, 255, 240)]


def _mother_mass(g: MobGrid, ctx):
    c, r = (0, -0.8, 0.4), (11.0, 9.4, 10.6)
    g.blob(c, r, 'skin', 0.5, lump=0.12, lump_scale=5.0, top=0.15)
    for p, rr in (((-6.4, 3.4, 3.0), (4.6, 4.2, 4.6)), ((6.0, 2.0, 4.4), (4.4, 4.0, 4.2)), ((0.6, 4.4, 5.6), (5.0, 4.0, 4.0)),
                  ((-8.0, -4.6, -4.4), (3.6, 3.4, 3.6)), ((8.2, -3.8, -4.8), (3.4, 3.6, 3.4))):
        g.blob(p, rr, 'skin', 0.52, lump=0.12, lump_scale=3.0, top=0.15)               # heaving lobes
    # the mouth: a cavity with a glowing throat and a fleshy lower lip
    g.carve_blob((0, -1.2, -10.8), (4.4, 3.2, 3.6))
    g.blob((0, -1.2, -9.0), (4.0, 2.8, 2.0), 'mouth', 0.25, prio=0)
    g.blob((0, -1.4, -8.0), (2.0, 1.6, 1.0), 'core', 0.5, glow=True, prio=1)
    g.capsule((-4.2, -3.8, -9.8), (4.2, -3.8, -9.8), 1.2, 1.2, 'skin', 0.62)
    g.teeth((-3.0, -3.0, -10.6), (3.0, -3.0, -10.6), 5, 1.2, r=0.4, direction=(0, 1, 0))
    # glowing spore sacs crusting the mound
    for k, (p, rr) in enumerate((((-8.6, 1.4, -4.0), 1.5), ((8.8, -0.4, -3.4), 1.3), ((-5.0, 6.2, -4.6), 1.2),
                                 ((5.2, 5.8, -5.0), 1.1), ((-9.6, -3.6, 2.4), 1.2), ((9.4, -3.0, 3.6), 1.4),
                                 ((-2.8, 2.6, -8.6), 0.9), ((3.4, 2.4, -8.4), 0.9), ((0.0, 7.4, 6.8), 1.3))):
        g.blob(p, rr, 'glow', glow=True, prio=4, vfn=lambda x, y, z, d: 0.7 - 0.35 * d)
    # white hyphae draped over it
    for a, b in (((-10.0, 2.0, -3.0), (-3.0, 8.0, -4.0)), ((10.0, 1.0, -2.0), (4.0, 7.6, -4.6)),
                 ((-9.0, -5.0, -4.0), (-4.4, 1.0, -9.4)), ((9.4, -4.4, -3.4), (4.6, 1.4, -9.2))):
        g.strands(a, b, sag=1.4, mat='web', val=0.85)
    # the brood: little red capcaps sprouting from the flanks
    for k, (p, up) in enumerate((((-10.4, -1.6, -1.0), (-1, 0.5, -0.2)), ((10.6, 1.6, 1.0), (1, 0.6, 0)),
                                 ((-7.4, 5.0, 4.6), (-0.6, 1, 0.3)), ((7.0, -5.6, -5.4), (0.5, 0.4, -1)),
                                 ((-6.6, -5.8, -6.2), (-0.5, 0.4, -1)))):
        g.mushroom(p, up, 1.6, 1.9, mat='brood', val=0.5, spots=0.0, stem_mat='spot', gill_mat='spot')
        tip = vadd(p, vmul(vnorm(up), 1.6 + 1.0))
        g.dot(tip, 'spot', 0.85, prio=5)


def _mother_caps(g: MobGrid, ctx):
    for k, (base, up, stem, cr) in enumerate((((0, -3.6, 0.6), (0, 1, 0.05), 5.0, 7.2),
                                              ((-6.4, -4.4, -2.0), (-0.6, 1, -0.3), 3.4, 4.4),
                                              ((6.6, -4.2, -1.6), (0.6, 1, -0.2), 3.0, 4.0),
                                              ((-4.8, -4.0, 5.4), (-0.4, 1, 0.5), 3.6, 4.8),
                                              ((5.0, -4.2, 5.4), (0.5, 1, 0.5), 2.6, 3.6),
                                              ((0.2, -4.6, -6.6), (0.1, 1, -0.6), 2.0, 2.8))):
        g.mushroom(base, up, stem, cr, mat='cap', val=0.5, spots=0.0, stem_mat='skin', gill_mat='gill',
                   stem_r=max(0.9, cr * 0.22))
        top = vadd(base, vmul(vnorm(up), stem))
        for j in range(3 + int(cr > 5) * 3):                                          # raised pale spots
            a = 2.4 * j + k
            rr = cr * (0.25 + 0.5 * ((j * 7 + k) % 5) / 4)
            q = vadd(top, (math.cos(a) * rr, 0, math.sin(a) * rr))
            hit = g.hit(vadd(q, (0, cr, 0)), (0, -1, 0), cr * 2)
            if hit:
                g.blob(hit, (cr * 0.16, cr * 0.09, cr * 0.16), 'spot', 0.75, prio=5)
        g.ring(top, cr * 0.95, 0.35, axis='y', mat='rune', val=0.4, glow=True, prio=5)       # luminous gold gill rim


def _mother_maw(g: MobGrid, ctx):
    g.sweep([(-4.4, 0.4, 1.0), (-2.6, 1.0, -0.6), (0, 1.2, -1.4), (2.6, 1.0, -0.6), (4.4, 0.4, 1.0)], 1.3, 1.1,
            'skin', 0.55)
    g.teeth((-3.4, 0.2, -0.6), (3.4, 0.2, -0.6), 7, 2.4, r=0.5, direction=(0, -1, -0.2))
    for s in (-1, 1):
        g.horn((s * 4.2, 0.4, 0.4), (s * 0.2, -1, -0.6), 4.0, 0.9, curl=(-s * 1.8, 0, -0.6), mat='tooth', val=0.4)


def _mother_tendrils(g: MobGrid, ctx):
    gy = -4.8
    g.light_mul = 0.6
    for k in range(9):
        a = 2 * math.pi * (k + 0.5) / 9
        ca, sa = math.cos(a), math.sin(a)
        L = 1.0 + 0.12 * (k % 3)
        p0 = (ca * 7.0, -0.6, sa * 7.0)
        p1 = (ca * 10.0 * L, gy + 0.6, sa * 10.0 * L)
        p2 = (ca * 13.0 * L, gy + 0.8, sa * 13.0 * L)
        p3 = (ca * 14.2 * L + sa * 1.4, gy + 2.6, sa * 14.2 * L - ca * 1.4)
        g.tentacle(p0, p1, p2, p3, 1.45, 0.45, 'skin', 0.45, suckers=False, tip_mat='glow', glow_tip=True)
    for k in range(9):                                                                # mycelium threads
        a0 = 2 * math.pi * (k + 0.5) / 9
        a1 = 2 * math.pi * (k + 1.5) / 9
        g.strands((math.cos(a0) * 10.4, gy + 0.6, math.sin(a0) * 10.4), (math.cos(a1) * 10.4, gy + 0.6,
                  math.sin(a1) * 10.4), sag=0.0, mat='web', val=0.85)


def spore_mother(look, name, part, ctx):
    _ramps(ctx, {'skin': MOTHER_FLESH, 'cap': MOTHER_CAP, 'spot': MOTHER_SPOT, 'glow': MOTHER_GLOW,
                 'core': MOTHER_GLOW, 'rune': GOLD_GILL, 'web': HYPHAE, 'brood': CAP_RED,
                 'gill': [(70, 40, 60), (124, 80, 108), (176, 128, 156), (214, 176, 198), (236, 214, 228)]})
    fn = {'mass': _mother_mass, 'caps': _mother_caps, 'maw': _mother_maw, 'tendrils': _mother_tendrils}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'mass': 0.8, 'caps': 0.75, 'maw': 0.5, 'tendrils': 0.7}.get(name, 0.7))
    fn(g, ctx)
    return g




DESIGNS = {
    'moss_crawler': moss_crawler,
    'rusted_miner': rusted_miner,
    'root_shambler': root_shambler,
    'lantern_wisp': lantern_wisp,
    'stone_beetle': stone_beetle,
    'moss_crawler_alpha': moss_crawler_alpha,
    'moss_sproutling': moss_sproutling,
    'tunnel_skitter': tunnel_skitter,
    'ore_mimic': ore_mimic,
    'echo_bat': echo_bat,
    'foreman_gorrak': foreman_gorrak,
    'silk_hatchling': silk_hatchling,
    'capcap': capcap,
    'mycelid_shambler': mycelid_shambler,
    'spore_turret': spore_turret,
    'glowcap_moth': glowcap_moth,
    'spore_mother': spore_mother,
}
