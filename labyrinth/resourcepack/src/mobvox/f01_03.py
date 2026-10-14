"""Voxel mob designs — floors 1–3 (이끼 회랑 · 거미줄 갱도 · 균사 동굴).  See README.md.

Pilot designs (reference for the other designers): moss_crawler, rusted_miner.
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the mob's left.
"""
from __future__ import annotations

import math  # noqa: F401

from ..voxel.mob_kit import MobGrid, mirror_pt  # noqa: F401

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


DESIGNS = {
    'moss_crawler': moss_crawler,
    'rusted_miner': rusted_miner,
}
