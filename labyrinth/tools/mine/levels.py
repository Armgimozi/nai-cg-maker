#!/usr/bin/env python3
"""광산 6층 청사진 (0.3.6 Q1) — tools/data/036/mine.json 의 층 정보로 61×16×61 입체 청사진을 짓는다.

gen_mine.py 가 부른다 (직접 돌리지 않아도 된다). 결정적: 같은 mine.json 이면 같은 청사진.

좌표: 청사진 칸 (ix, iy, iz) ↔ 광산 월드 (x, y, z) = (ix − 30, 바닥 y − 2 + iy, iz − 30).
  iy 0·1 = 바닥 아래 바위 · iy 2 = 바닥 블록 · iy 3 = 발 높이 (= 바닥 y + 1) · iy 15 = 맨 위.
층 모양 (tools/data/036/model/layout6.py 시안을 입체로):
  가운데 승강기 홀 11×9 (높이 6) · 북쪽 벽감 (1층 = 광산 관리소) · 갱도 3갈래 (폭 3, 조금씩 굽음) · 곁방 3 · 끝 채굴장
  (1~3층 갱도 · 4층 어긋난 단층 · 5층 둥근 정동 · 6층 큰 굴).
광맥 = 벽 블록 무더기 (한 무더기 = 광석 한 종류, 3~5칸). 깊이 들어갈수록 귀한 광석이 많다 (가까운 곳은 흔한 광석).
  층의 광석 종류별 블록 수 = mine.json levels[].vein_blocks (계약). 손 닿는 광맥 수 한도는 없다 (주인 결정 §0-2).
보석 노드 = mine.json gem_nodes (층마다 3), 가장 먼 벽에.
빛: 보이는 등불·개구리불·끝 막대 + 모자란 곳만 보이지 않는 빛 블록 (light) — 광맥 앞 ≥ 8 · 바닥 ≥ 6 · 승강기 홀 ≥ 12.
"""
import math
import random
import sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'village'))
import vlib  # noqa: E402  (블록 이름·속성 검사: tools/village/blockdata.json = 26.3)

W = D = 61
H = 16
C = 30
FL = 2          # 바닥 블록 층
F = 3           # 발 높이 층
SHELL = 2       # 공기 둘레 바위 두께 (그 밖은 비움 = 공허)
EYE = 1.62      # 발 → 눈
REACH = 4.5     # 바닐라 블록 손 닿는 거리 (자가 진단 unreachable)

AIR = '.'
KEEP = ' '

EMIT = {
    'lantern': 15, 'waxed_copper_lantern': 15, 'copper_lantern': 15, 'soul_lantern': 10, 'glow_lichen': 7,
    'ochre_froglight': 15, 'pearlescent_froglight': 15, 'verdant_froglight': 15, 'small_amethyst_bud': 1,
    'end_rod': 14, 'light': None,
}
SIGN_WOOD = {1: 'oak', 2: 'dark_oak', 3: 'spruce', 4: 'acacia', 5: 'warped', 6: 'crimson'}
# 발 높이에서 부딪히지 않는 장식 (걸어 지나갈 수 있음)
PASSABLE = {'rail', 'moss_carpet', 'light', 'oak_wall_sign', 'dark_oak_wall_sign', 'spruce_wall_sign', 'acacia_wall_sign',
            'warped_wall_sign', 'crimson_wall_sign', 'glow_lichen'}
# 빛이 지나가는 (불투명하지 않은) 블록
TRANSPARENT_EXTRA = PASSABLE | {'lantern', 'waxed_copper_lantern', 'soul_lantern', 'iron_chain', 'oak_fence', 'end_rod',
                                'pointed_dripstone', 'amethyst_cluster', 'small_amethyst_bud', 'lectern', 'iron_bars'}


class Level:
    """층 하나의 청사진 만들기."""

    def __init__(self, L, ores, gems, all_forbidden):
        self.L = L
        self.n = L['n']
        self.floor_y = L['floor_y']
        self.rnd = random.Random(1000 + self.n * 7919)
        self.ores = ores
        self.gems = gems
        self.forbidden = all_forbidden            # 광석·보석 블록 12 + 모든 층 빈 광맥 블록 (장식·벽에 쓰면 안 됨)
        self.pal = L['palette']
        self.lights = L['lighting']['sources']
        self.cell = [[[KEEP] * D for _ in range(H)] for _ in range(W)]   # [x][y][z] 블록 문자열 | AIR | KEEP
        self.walk = [[False] * D for _ in range(W)]                      # 바닥 칸 (발 높이 공기)
        self.ceil = [[0] * D for _ in range(W)]                          # 바닥 위 공기 높이 (칸 수)
        self.region = [[''] * D for _ in range(W)]                       # hall | alcove | drift | room | end
        self.reserved = set()                                            # 광맥을 두지 않을 벽 칸
        self.veins = []                                                  # (x, y, z, ore)
        self.gem_cells = []                                              # (x, y, z, gem, face)
        self.markers = []
        self.blocked = set()                                             # 걸을 수 없는 바닥 칸 (통·울타리)

    # ── 1. 평면 ─────────────────────────────────────────────────────────

    def open(self, x, z, h, region):
        if 2 + SHELL - 1 <= x <= W - 1 - SHELL and 2 + SHELL - 1 <= z <= D - 1 - SHELL:
            if not self.walk[x][z] or self.ceil[x][z] < h:
                self.ceil[x][z] = max(self.ceil[x][z], h)
            if not self.walk[x][z]:
                self.region[x][z] = region
            self.walk[x][z] = True

    def rect(self, x0, z0, x1, z1, h, region):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for z in range(min(z0, z1), max(z0, z1) + 1):
                self.open(x, z, h, region)

    def blob(self, cx, cz, rx, rz, h, region, rough=0.18, dome=0):
        """울퉁불퉁한 타원 방. dome > 0 이면 가운데가 높다."""
        for x in range(int(cx - rx - 2), int(cx + rx + 3)):
            for z in range(int(cz - rz - 2), int(cz + rz + 3)):
                a = math.atan2(z - cz, x - cx)
                k = 1 + rough * (math.sin(a * 3 + self.n) * 0.6 + math.sin(a * 5 + 2 * self.n) * 0.4)
                r = math.hypot((x - cx) / (rx * k), (z - cz) / (rz * k))
                if r <= 1.0:
                    hh = h + int(round(dome * max(0.0, 1 - r * r)))
                    self.open(x, z, hh, region)

    def drift(self, x0, z0, x1, z1, h, width=3):
        """갱도: (x0,z0)→(x1,z1) 곧은 축을 따라 가운데 줄이 ±1 굽는다. 폭 width, 가끔 넓어짐."""
        horiz = z0 == z1
        length = abs(x1 - x0) if horiz else abs(z1 - z0)
        step = 1 if (x1 > x0 if horiz else z1 > z0) else -1
        off, nxt = 0, self.rnd.randint(4, 6)
        half = width // 2
        for i in range(length + 1):
            if i == nxt:
                if 3 < i < length - 3:
                    off = max(-1, min(1, off + self.rnd.choice((-1, 1))))
                else:
                    off = 0
                nxt = i + self.rnd.randint(4, 7)
            if i > length - 3:
                off = 0
            wide = 1 if self.rnd.random() < 0.12 else 0
            for w in range(-half, half + 1 + wide):
                if horiz:
                    self.open(x0 + step * i, z0 + off + w, h, 'drift')
                else:
                    self.open(x0 + off + w, z0 + step * i, h, 'drift')

    def plan(self):
        n = self.n
        self.rect(C - 5, C - 4, C + 5, C + 4, 6, 'hall')                 # 승강기 홀 11×9
        self.rect(C - 1, C - 7, C + 1, C - 5, 4, 'alcove')               # 북쪽 벽감 (1층 관리소)
        dh = 5 if n in (2, 5) else 4
        self.drift(C - 6, C, C - 22, C, dh)                              # 서쪽 갱도
        self.drift(C + 6, C, C + 22, C, dh)                              # 동쪽 갱도
        self.drift(C, C + 5, C, C + 20, dh)                              # 남쪽 갱도
        # 곁방 (갱도 옆)
        self.blob(C - 15, C - 4.5, 2.6, 2.4, 4, 'room', 0.15, 1)
        self.blob(C + 15, C + 4.5, 2.6, 2.4, 4, 'room', 0.15, 1)
        self.blob(C + 4.5, C + 13, 2.4, 2.6, 4, 'room', 0.15, 1)
        self.rect(C - 15, C - 2, C - 15, C - 1, 4, 'room')               # 곁방 입구
        self.rect(C + 15, C + 1, C + 15, C + 2, 4, 'room')
        self.rect(C + 1, C + 13, C + 3, C + 13, 4, 'room')
        shape = {1: 'drifts', 2: 'drifts', 3: 'drifts', 4: 'fault', 5: 'geode', 6: 'cavern'}[n]
        if shape == 'drifts':
            self.blob(C - 25, C, 3.4, 4.4, 5, 'end', 0.2, 1)
            self.blob(C + 25, C, 3.4, 4.4, 5, 'end', 0.2, 1)
            self.blob(C, C + 24, 4.4, 3.6, 5, 'end', 0.2, 1)
        elif shape == 'fault':                                           # 비스듬히 어긋난 단층: 끝 채굴장을 엇갈리게
            self.blob(C - 25, C - 2, 3.4, 4.6, 5, 'end', 0.22, 1)
            self.blob(C + 25, C + 2, 3.4, 4.6, 5, 'end', 0.22, 1)
            self.blob(C + 1, C + 24, 4.6, 3.6, 5, 'end', 0.22, 1)
            self.rect(C - 23, C - 3, C - 22, C, 4, 'drift')
            self.rect(C + 22, C, C + 23, C + 3, 4, 'drift')
        elif shape == 'geode':                                           # 둥근 정동: 남쪽 큰 둥근 방 (돔)
            self.blob(C, C + 20, 7.6, 7.4, 5, 'end', 0.08, 5)
            self.blob(C - 25, C, 3.4, 4.2, 5, 'end', 0.15, 2)
            self.blob(C + 25, C, 3.4, 4.2, 5, 'end', 0.15, 2)
        else:                                                            # 큰 굴: 넓은 남쪽 굴 + 양쪽 굴
            self.blob(C, C + 20, 8.2, 7.6, 6, 'end', 0.25, 5)
            self.blob(C - 25, C, 4.2, 5.4, 5, 'end', 0.25, 3)
            self.blob(C + 25, C, 4.2, 5.4, 5, 'end', 0.25, 3)
        self.join_plan()
        # 천장 높낮이: 갱도는 4 를 지키고 넓은 방은 조금씩 오르내림
        for x in range(W):
            for z in range(D):
                if self.walk[x][z] and self.region[x][z] in ('end', 'room') and self.rnd.random() < 0.25:
                    self.ceil[x][z] = max(4, min(11, self.ceil[x][z] + self.rnd.choice((-1, 1))))
                self.ceil[x][z] = min(self.ceil[x][z], H - SHELL - F)

    def join_plan(self):
        """떨어진 바닥 조각이 있으면 가장 가까운 이어진 칸까지 ㄱ자 굴(높이 4)로 잇는다."""
        for _ in range(20):
            start = (C, C + 3)
            seen = {start}
            q = deque([start])
            while q:
                x, z = q.popleft()
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p = (x + dx, z + dz)
                    if p not in seen and 0 <= p[0] < W and 0 <= p[1] < D and self.walk[p[0]][p[1]]:
                        seen.add(p)
                        q.append(p)
            rest = [(x, z) for x in range(W) for z in range(D) if self.walk[x][z] and (x, z) not in seen]
            if not rest:
                return
            a = rest[0]
            b = min(seen, key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                self.open(x, a[1], 4, self.region[a[0]][a[1]] or 'drift')
            for z in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                self.open(b[0], z, 4, self.region[b[0]][b[1]] or 'drift')
        raise SystemExit(f'{self.n}층: 평면을 잇지 못함')

    # ── 2. 블록 채우기 ─────────────────────────────────────────────────

    def pick(self, choices, x, y, z, salt=0):
        h = (x * 73856093 ^ y * 19349663 ^ z * 83492791 ^ (salt + self.n) * 2654435761) & 0xffffffff
        h = (h ^ (h >> 13)) * 1274126177 & 0xffffffff
        return choices[h % len(choices)]

    def wall_block(self, x, y, z):
        wall = self.pal['wall']
        n = self.n
        if n == 4:                                                       # 황토 단층: 비스듬한 흙층 띠
            band = int(math.floor((y + (x - C) * 0.35 + (z - C) * 0.12) / 2.0))
            return 'minecraft:' + wall[band % len(wall)]
        if n == 5:                                                       # 정동: 바깥 심층암 · 안쪽 매끈한 현무암 · 자수정 조각
            return 'minecraft:' + self.pick(['deepslate', 'deepslate', 'smooth_basalt', 'smooth_basalt', 'amethyst_block'], x, y, z)
        if n == 2:
            return 'minecraft:' + self.pick(['stone', 'stone', 'deepslate', 'dripstone_block', 'andesite'], x, y, z)
        if n == 1:
            return 'minecraft:' + self.pick(['stone', 'stone', 'stone', 'andesite', 'tuff'], x, y, z)
        if n == 3:
            return 'minecraft:' + self.pick(['deepslate', 'deepslate', 'tuff'], x, y, z)
        return 'minecraft:' + self.pick(['basalt[axis=y]', 'basalt[axis=y]', 'polished_basalt[axis=y]', 'smooth_basalt'], x, y, z)

    def floor_block(self, x, z):
        fl = self.pal['floor']
        if self.n == 1:
            return 'minecraft:' + self.pick(['coarse_dirt', 'packed_mud', 'stone', 'coarse_dirt'], x, FL, z)
        return 'minecraft:' + self.pick(fl, x, FL, z, 3)

    def fill(self):
        for x in range(W):
            for z in range(D):
                if self.walk[x][z]:
                    for y in range(F, F + self.ceil[x][z]):
                        self.cell[x][y][z] = AIR
        air = [(x, y, z) for x in range(W) for y in range(H) for z in range(D) if self.cell[x][y][z] == AIR]
        near = set()
        for (x, y, z) in air:
            for dx in range(-SHELL, SHELL + 1):
                for dy in range(-SHELL, SHELL + 1):
                    for dz in range(-SHELL, SHELL + 1):
                        nx, ny, nz = x + dx, y + dy, z + dz
                        if 0 <= nx < W and 0 <= ny < H and 0 <= nz < D:
                            near.add((nx, ny, nz))
        for (x, y, z) in near:
            if self.cell[x][y][z] != KEEP:
                continue
            if y == FL and self.walk[x][z]:
                self.cell[x][y][z] = self.floor_block(x, z)
            else:
                self.cell[x][y][z] = self.wall_block(x, y, z)

    def is_air(self, x, y, z):
        return 0 <= x < W and 0 <= y < H and 0 <= z < D and self.cell[x][y][z] == AIR

    def solid_rock(self, x, y, z):
        if not (0 <= x < W and 0 <= y < H and 0 <= z < D):
            return False
        c = self.cell[x][y][z]
        return c not in (AIR, KEEP) and vlib.is_full(vlib.parse_block(c)[0])

    def put(self, x, y, z, block):
        vlib.check_block(block)
        self.cell[x][y][z] = block

    # ── 3. 승강기 · 관리소 · 표지판 ─────────────────────────────────────

    def wpos(self, x, y, z):
        return [x - C, self.floor_y - FL + y, z - C]

    def sign(self, x, y, z, facing, lines):
        wood = SIGN_WOOD[self.n]
        self.put(x, y, z, 'minecraft:%s_wall_sign[facing=%s]' % (wood, facing))
        self.markers.append({'type': 'sign', 'pos': self.wpos(x, y, z), 'lines': lines})

    def lift(self):
        top = F + self.ceil[C][C] - 1
        self.put(C, F, C, 'minecraft:lodestone')                         # 승강기 (우클릭)
        for y in range(F + 1, top + 1):
            self.put(C, y, C, 'minecraft:iron_chain[axis=y]')
        for dx, dz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):                 # 승강기 네 귀퉁이 울타리 + 등불
            post = 'minecraft:oak_fence' if self.n <= 3 else 'minecraft:iron_bars'
            self.put(C + dx, F, C + dz, post)
            self.blocked.add((C + dx, C + dz))
            lamp = 'minecraft:soul_lantern[hanging=false]' if self.n == 3 else 'minecraft:lantern[hanging=false]'
            self.put(C + dx, F + 1, C + dz, lamp)
        # 승강기 둘레 바닥 무늬 (3×3 + 테)
        ring = {1: 'polished_andesite', 2: 'polished_andesite', 3: 'polished_deepslate', 4: 'smooth_sandstone',
                5: 'polished_deepslate', 6: 'polished_blackstone_bricks'}[self.n]
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                if max(abs(dx), abs(dz)) == 2:
                    self.put(C + dx, FL, C + dz, 'minecraft:' + ring)
        self.sign(C, F, C + 1, 'south', [self.L['name'], '승강기', '우클릭'])
        self.markers.append({'type': 'lift', 'pos': self.wpos(C, F, C)})
        lx, ly, lz = self.L['landing'][:3]
        self.markers.append({'type': 'landing', 'pos': [lx, ly, lz], 'yaw': self.L['landing'][3]})
        for x in range(C - 2, C + 3):
            for z in range(C - 2, C + 3):
                self.reserved.add((x, z))
        # 북쪽 벽감
        if self.L['office']:
            self.put(C, F, C - 7, 'minecraft:lectern[facing=south]')
            self.blocked.add((C, C - 7))
            self.put(C - 1, F, C - 7, 'minecraft:barrel[facing=up]')
            self.put(C + 1, F, C - 7, 'minecraft:barrel[facing=up]')
            self.blocked.update({(C - 1, C - 7), (C + 1, C - 7)})
            self.sign(C, F + 1, C - 7, 'south', ['광산 관리소', '곡괭이 · 제련', '팔기 · 우클릭'])
            self.markers.append({'type': 'office', 'pos': self.wpos(C, F, C - 7)})
        else:
            self.sign(C, F + 1, C - 7, 'south', [self.L['name'], '광맥은 시간이', '지나면 다시 찹니다'])
        self.markers.append({'type': 'ambient', 'pos': self.wpos(C, F + 2, C), 'fx': 'dust'})

    # ── 4. 장식 (버팀목·레일·종유석·이끼·자수정 …) ─────────────────────

    def drift_cells(self):
        return [(x, z) for x in range(W) for z in range(D) if self.walk[x][z] and self.region[x][z] == 'drift']

    def timbers(self):
        """갱도 버팀목: 5칸마다 벽 속 기둥 + 천장 들보 (걷는 길은 그대로)."""
        post = self.pal['post']
        beam = self.pal['beam']
        done = []
        for (x, z) in sorted(self.drift_cells()):
            if (x, z) in self.reserved:
                continue
            horiz = self.walk[x - 1][z] and self.walk[x + 1][z] and self.region[x - 1][z] == 'drift'
            vert = self.walk[x][z - 1] and self.walk[x][z + 1] and self.region[x][z - 1] == 'drift'
            if horiz == vert:
                continue
            key = x if horiz else z
            if key % 5 != 0 or any(abs(a - x) + abs(b - z) < 4 for a, b in done):
                continue
            # 이 단면의 걷는 칸
            if horiz:
                line = [(x, zz) for zz in range(z - 3, z + 4) if self.walk[x][zz]]
            else:
                line = [(xx, z) for xx in range(x - 3, x + 4) if self.walk[xx][z]]
            if len(line) < 3:
                continue
            h = min(self.ceil[a][b] for a, b in line)
            top = F + h
            ends = [line[0], line[-1]]
            sides = []
            for (a, b) in ends:
                da, db = (0, -1) if (a, b) == line[0] else (0, 1)
                if not horiz:
                    da, db = (-1, 0) if (a, b) == line[0] else (1, 0)
                sides.append((a + da, b + db))
            if not all(self.solid_rock(sa, F, sb) for sa, sb in sides):
                continue
            for (sa, sb) in sides:
                for y in range(F, top):
                    if self.solid_rock(sa, y, sb):
                        self.put(sa, y, sb, 'minecraft:%s[axis=y]' % post if self.has_axis(post) else 'minecraft:' + post)
                self.reserved.add((sa, sb))
            axis = 'z' if horiz else 'x'
            for (a, b) in line + sides:
                if self.solid_rock(a, top, b):
                    self.put(a, top, b, 'minecraft:%s[axis=%s]' % (beam, axis) if self.has_axis(beam) else 'minecraft:' + beam)
            done.append((x, z))

    @staticmethod
    def has_axis(bid):
        spec = vlib.blockdata()['_props'].get(bid, {})
        return 'axis' in spec

    def rails(self):
        """1층: 남쪽 갱도와 서쪽 갱도 가운데에 레일 (밟고 지나감)."""
        for z in range(C + 5, C + 21):
            xs = [x for x in range(C - 2, C + 3) if self.walk[x][z] and self.region[x][z] == 'drift']
            if xs:
                x = xs[len(xs) // 2]
                self.put(x, F, z, 'minecraft:rail[shape=north_south]')
        for x in range(C - 21, C - 5):
            zs = [z for z in range(C - 2, C + 3) if self.walk[x][z] and self.region[x][z] == 'drift']
            if zs:
                z = zs[len(zs) // 2]
                self.put(x, F, z, 'minecraft:rail[shape=east_west]')

    def corner_floor(self, region):
        """그 구역에서 두 면이 벽인 바닥 칸 (통 같은 것을 놓아도 길이 막히지 않는 곳)."""
        out = []
        for x in range(W):
            for z in range(D):
                if not self.walk[x][z] or self.region[x][z] != region or (x, z) in self.reserved:
                    continue
                walls = [not self.walk[x + dx][z + dz] for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                if sum(walls) >= 2 and not (walls[0] and walls[1]) and not (walls[2] and walls[3]):
                    out.append((x, z))
        return out

    def barrels(self, k):
        spots = self.corner_floor('end') + self.corner_floor('room')
        self.rnd.shuffle(spots)
        placed = []
        for (x, z) in spots:
            if len(placed) >= k:
                break
            if any(abs(x - a) + abs(z - b) < 5 for a, b in placed):
                continue
            if self.cell[x][F][z] != AIR:
                continue
            self.blocked.add((x, z))
            if not self.connected():
                self.blocked.discard((x, z))
                continue
            self.put(x, F, z, 'minecraft:barrel[facing=up]')
            placed.append((x, z))

    def ceiling_cells(self, min_h, regions):
        out = []
        for x in range(W):
            for z in range(D):
                if self.walk[x][z] and self.region[x][z] in regions and self.ceil[x][z] >= min_h and (x, z) not in self.reserved:
                    out.append((x, z))
        return out

    def dripstones(self):
        cells = self.ceiling_cells(5, ('end', 'room', 'drift'))
        self.rnd.shuffle(cells)
        for (x, z) in cells[:len(cells) // 5]:
            top = F + self.ceil[x][z] - 1
            if not self.solid_rock(x, top + 1, z) or self.cell[x][top][z] != AIR:
                continue
            if self.rnd.random() < 0.5 and self.cell[x][top - 1][z] == AIR and top - 1 >= F + 3:
                self.put(x, top, z, 'minecraft:pointed_dripstone[thickness=frustum,vertical_direction=down]')
                self.put(x, top - 1, z, 'minecraft:pointed_dripstone[thickness=tip,vertical_direction=down]')
            elif top >= F + 3:
                self.put(x, top, z, 'minecraft:pointed_dripstone[thickness=tip,vertical_direction=down]')

    def moss(self):
        for x in range(W):
            for z in range(D):
                if self.walk[x][z] and self.cell[x][F][z] == AIR and (x, z) not in self.reserved \
                        and self.region[x][z] in ('end', 'room', 'drift') and self.pick([0, 0, 0, 1], x, F, z, 9):
                    self.put(x, F, z, 'minecraft:moss_carpet')

    def wall_faces(self, y, regions):
        """발 위 y 층에서 공기와 맞닿은 벽 칸 → (벽 x, z, 공기 쪽 방향)."""
        out = []
        for x in range(1, W - 1):
            for z in range(1, D - 1):
                if not self.solid_rock(x, y, z):
                    continue
                for (dx, dz, face) in ((1, 0, 'east'), (-1, 0, 'west'), (0, 1, 'south'), (0, -1, 'north')):
                    ax, az = x + dx, z + dz
                    if self.is_air(ax, y, az) and self.walk[ax][az] and self.region[ax][az] in regions:
                        out.append((x, z, face, ax, az))
                        break
        return out

    def wall_decor(self, block_of_face, frac, y, regions):
        """벽에 붙는 장식 (머리 위 y ≥ F+2 이라 부딪히지 않음)."""
        faces = self.wall_faces(y, regions)
        self.rnd.shuffle(faces)
        for (x, z, face, ax, az) in faces[:int(len(faces) * frac)]:
            if self.cell[ax][y][az] == AIR and (ax, az) not in self.reserved:
                self.put(ax, y, az, block_of_face(face))

    def lichen(self, frac, regions=('end', 'room', 'drift')):
        opp = {'east': 'west', 'west': 'east', 'south': 'north', 'north': 'south'}
        self.wall_decor(lambda f: 'minecraft:glow_lichen[%s=true]' % opp[f], frac, F + 2, regions)

    def amethyst(self):
        opp = {'east': 'east', 'west': 'west', 'south': 'south', 'north': 'north'}
        self.wall_decor(lambda f: 'minecraft:amethyst_cluster[facing=%s]' % opp[f], 0.10, F + 2, ('end', 'room'))
        self.wall_decor(lambda f: 'minecraft:small_amethyst_bud[facing=%s]' % opp[f], 0.10, F + 3, ('end', 'room', 'drift'))
        cells = self.ceiling_cells(5, ('end',))
        self.rnd.shuffle(cells)
        for (x, z) in cells[:len(cells) // 8]:
            top = F + self.ceil[x][z] - 1
            if self.cell[x][top][z] == AIR and self.solid_rock(x, top + 1, z) and top >= F + 3:
                self.put(x, top, z, 'minecraft:amethyst_cluster[facing=down]')

    def bands(self, block, y):
        """벽 띠 (3층 응회암 벽돌 띠)."""
        for x in range(W):
            for z in range(D):
                if self.solid_rock(x, y, z) and (x, z) not in self.reserved and any(
                        self.is_air(x + dx, y, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.put(x, y, z, 'minecraft:' + block)

    def pillars(self, block):
        """6층: 큰 굴 가운데 깎은 흑암 기둥 몇 개 (길을 막지 않는 자리만)."""
        cells = [(x, z) for x in range(W) for z in range(D) if self.walk[x][z] and self.region[x][z] == 'end'
                 and self.ceil[x][z] >= 7 and (x, z) not in self.reserved]
        self.rnd.shuffle(cells)
        placed = []
        for (x, z) in cells:
            if len(placed) >= 3:
                break
            if any(abs(x - a) + abs(z - b) < 6 for a, b in placed):
                continue
            if not all(self.walk[x + dx][z + dz] for dx in (-1, 0, 1) for dz in (-1, 0, 1)):
                continue
            self.blocked.add((x, z))
            if not self.connected():
                self.blocked.discard((x, z))
                continue
            for y in range(F, F + self.ceil[x][z]):
                self.put(x, y, z, 'minecraft:' + block)
            placed.append((x, z))

    def decorate(self):
        n = self.n
        self.timbers() if n <= 4 else None
        if n == 1:
            self.rails()
            self.barrels(4)
        elif n == 2:
            self.dripstones()
        elif n == 3:
            self.bands('tuff_bricks', F + 3)
            self.moss()
        elif n == 4:
            self.barrels(3)
        elif n == 5:
            self.amethyst()
        else:
            self.pillars('chiseled_polished_blackstone')

    # ── 5. 이어짐 · 거리 ────────────────────────────────────────────────

    def standable(self, x, z):
        if not (0 <= x < W and 0 <= z < D) or not self.walk[x][z] or (x, z) in self.blocked:
            return False
        for y in (F, F + 1):
            c = self.cell[x][y][z]
            if c != AIR and vlib.parse_block(c)[0] not in PASSABLE:
                return False
        return True

    def distances(self):
        lx, lz = int(math.floor(self.L['landing'][0])) + C, int(math.floor(self.L['landing'][2])) + C
        dist = {(lx, lz): 0}
        q = deque([(lx, lz)])
        while q:
            x, z = q.popleft()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, z + dz)
                if p not in dist and self.standable(*p):
                    dist[p] = dist[(x, z)] + 1
                    q.append(p)
        return dist

    def connected(self):
        dist = self.distances()
        total = sum(1 for x in range(W) for z in range(D) if self.standable(x, z))
        return len(dist) == total

    # ── 6. 보석 노드 · 광맥 ─────────────────────────────────────────────

    def vein_candidates(self, dist):
        """광맥 칸 후보: 발~머리 위(F..F+2) 벽 칸이 걷는 칸과 맞닿음. → {(x,y,z): 걷는 거리}."""
        out = {}
        for y in (F, F + 1, F + 2):
            for x in range(1, W - 1):
                for z in range(1, D - 1):
                    if (x, z) in self.reserved or not self.solid_rock(x, y, z):
                        continue
                    if vlib.parse_block(self.cell[x][y][z])[0] not in self.pal['wall']:
                        continue
                    best = None
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ax, az = x + dx, z + dz
                        if self.is_air(ax, y, az) and (ax, az) in dist and self.region[ax][az] not in ('hall', 'alcove'):
                            d = dist[(ax, az)]
                            best = d if best is None else min(best, d)
                    if best is not None:
                        out[(x, y, z)] = best
        return out

    def place_gems(self, cand):
        spots = sorted(((d, p) for p, d in cand.items() if p[1] == F + 1), reverse=True)
        types = list(self.L['gem_nodes'])
        types.sort(key=lambda g: self.gems[g]['tier'])                    # 귀한 보석이 더 먼 곳에
        chosen = []
        for (d, (x, y, z)) in spots:
            if len(chosen) >= len(types):
                break
            if any(abs(x - a) + abs(z - c) < 10 for (a, _, c, _f) in chosen):
                continue
            face = None
            for dx, dz, f in ((1, 0, 'east'), (-1, 0, 'west'), (0, 1, 'south'), (0, -1, 'north')):
                if self.is_air(x + dx, y, z + dz) and self.walk[x + dx][z + dz]:
                    face = f
                    break
            if face is None:
                continue
            chosen.append((x, y, z, face))
        if len(chosen) < len(types):
            raise SystemExit(f'{self.n}층: 보석 노드 자리가 모자람')
        chosen.sort(key=lambda p: cand[(p[0], p[1], p[2])])               # 가까운 곳 → 흔한 보석
        for (x, y, z, face), g in zip(chosen, types):
            self.gem_cells.append((x, y, z, g, face))
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    for dz in range(-1, 2):
                        cand.pop((x + dx, y + dy, z + dz), None)

    def place_veins(self, cand):
        need = dict(self.L['vein_blocks'])
        order = sorted(need, key=lambda o: self.ores[o]['tier'])
        k = len(order)
        maxd = max(cand.values()) or 1
        target = {o: (i / (k - 1) if k > 1 else 0.5) for i, o in enumerate(order)}
        clusters = []
        free = dict(cand)
        # 귀한 광석부터 먼 곳을 고른다 (흔한 광석은 남은 곳 어디든)
        for ore in reversed(order):
            while need[ore] > 0:
                size = min(need[ore], self.rnd.choice((3, 4, 4, 5)))
                best, best_s = None, None
                for p, d in free.items():
                    t = d / maxd
                    s = -abs(t - target[ore]) * (2.2 if self.ores[ore]['tier'] >= 4 else 1.0)
                    if clusters:
                        md = min(abs(p[0] - c[0]) + abs(p[2] - c[2]) for c in clusters)
                        s += min(md, 9) * 0.05
                    s += self.rnd.random() * 0.45
                    if best_s is None or s > best_s:
                        best, best_s = p, s
                if best is None:
                    raise SystemExit(f'{self.n}층: 광맥 자리가 모자람 ({ore} {need[ore]})')
                cells = self.grow(best, size, free)
                if len(cells) < min(size, 2) and need[ore] >= 2:
                    free.pop(best, None)
                    continue
                for c in cells:
                    self.veins.append((c[0], c[1], c[2], ore))
                need[ore] -= len(cells)
                clusters.append(best)
                for (x, y, z) in cells:
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            for dz in range(-1, 2):
                                free.pop((x + dx, y + dy, z + dz), None)

    def grow(self, seed, size, free):
        cells = [seed]
        seen = {seed}
        frontier = [seed]
        while frontier and len(cells) < size:
            self.rnd.shuffle(frontier)
            p = frontier.pop()
            nb = [(p[0] + dx, p[1] + dy, p[2] + dz) for dx, dy, dz in
                  ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
            self.rnd.shuffle(nb)
            for q in nb:
                if q in free and q not in seen and len(cells) < size:
                    seen.add(q)
                    cells.append(q)
                    frontier.append(q)
                    frontier.append(p)
        return cells

    # ── 7. 빛 ───────────────────────────────────────────────────────────

    def emission(self, c):
        if c in (AIR, KEEP):
            return 0
        bid, props = vlib.parse_block(c)
        if bid == 'light':
            return int(props.get('level', 15))
        return EMIT.get(bid) or 0

    def transparent(self, c):
        if c == AIR:
            return True
        if c == KEEP:
            return False
        bid = vlib.parse_block(c)[0]
        return bid in TRANSPARENT_EXTRA or not vlib.is_full(bid)

    def light_field(self):
        lvl = {}
        q = deque()
        for x in range(W):
            for y in range(H):
                for z in range(D):
                    c = self.cell[x][y][z]
                    e = self.emission(c)
                    if e <= 0:
                        continue
                    if self.transparent(c):
                        if lvl.get((x, y, z), 0) < e:
                            lvl[(x, y, z)] = e
                            q.append((x, y, z))
                    else:                                                # 개구리불 같은 꽉 찬 빛 블록: 이웃으로 e−1
                        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                            p = (x + dx, y + dy, z + dz)
                            if 0 <= p[0] < W and 0 <= p[1] < H and 0 <= p[2] < D and self.transparent(self.cell[p[0]][p[1]][p[2]]):
                                if lvl.get(p, 0) < e - 1:
                                    lvl[p] = e - 1
                                    q.append(p)
        while q:
            x, y, z = q.popleft()
            v = lvl[(x, y, z)]
            if v <= 1:
                continue
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                p = (x + dx, y + dy, z + dz)
                if not (0 <= p[0] < W and 0 <= p[1] < H and 0 <= p[2] < D):
                    continue
                if not self.transparent(self.cell[p[0]][p[1]][p[2]]):
                    continue
                if lvl.get(p, 0) < v - 1:
                    lvl[p] = v - 1
                    q.append(p)
        return lvl

    def needs(self):
        """빛이 있어야 하는 칸 → 최소 밝기."""
        lt = self.L['lighting']
        need = {}
        for x in range(W):
            for z in range(D):
                if self.standable(x, z):
                    m = lt['lift_hall_min'] if self.region[x][z] == 'hall' else lt['floor_min']
                    need[(x, F, z)] = max(need.get((x, F, z), 0), m)
        for (x, y, z, _ore) in self.veins:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, y, z + dz)
                if self.is_air(*p) and self.walk[p[0]][p[2]]:
                    need[p] = max(need.get(p, 0), lt['vein_face_min'])
        for (x, y, z, _g, _f) in self.gem_cells:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, y, z + dz)
                if self.is_air(*p) and self.walk[p[0]][p[2]]:
                    need[p] = max(need.get(p, 0), lt['vein_face_min'])
        return need

    def visible_lights(self):
        """보이는 빛: 걷는 길을 따라 ~7칸마다 (층마다 다른 등)."""
        dist = self.distances()
        cells = sorted(dist, key=lambda p: (dist[p], p))
        placed = [(C + a, C + b) for a in (-1, 1) for b in (-1, 1)]       # 승강기 등불 4
        n = self.n
        for (x, z) in cells:
            if self.region[x][z] == 'hall' and abs(x - C) <= 2 and abs(z - C) <= 2:
                continue
            gap = 6 if self.region[x][z] in ('hall',) else 7
            if any(abs(x - a) + abs(z - b) < gap for a, b in placed):
                continue
            if self.place_light(x, z, len(placed)):
                placed.append((x, z))

    def place_light(self, x, z, i):
        n = self.n
        top = F + self.ceil[x][z] - 1
        if self.cell[x][top][z] != AIR or not self.solid_rock(x, top + 1, z) or top < F + 2:
            return False
        if (x, top, z) in self.front or (x, top - 1, z) in self.front:
            return False
        src = self.lights
        if n == 1:
            self.put(x, top, z, 'minecraft:%s[hanging=true]' % ('lantern' if i % 2 else 'waxed_copper_lantern'))
            return True
        if n == 2:
            if top - 1 >= F + 2 and self.cell[x][top - 1][z] == AIR and self.ceil[x][z] >= 5:
                self.put(x, top, z, 'minecraft:iron_chain[axis=y]')
                self.put(x, top - 1, z, 'minecraft:lantern[hanging=true]')
            else:
                self.put(x, top, z, 'minecraft:lantern[hanging=true]')
            return True
        if n == 3:
            self.put(x, top, z, 'minecraft:soul_lantern[hanging=true]')
            return True
        # 4·5·6층: 벽에 박힌 개구리불 (가까운 벽, 머리 위) 번갈아 천장 등
        froglight = {4: 'ochre_froglight', 5: 'pearlescent_froglight', 6: 'verdant_froglight'}[n]
        if i % 2 == 0:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                wx, wz = x + dx, z + dz
                y = F + 2
                if self.solid_rock(wx, y, wz) and (wx, wz) not in self.reserved and self.region[x][z] != 'hall' \
                        and (wx, y, wz) not in self.front and vlib.parse_block(self.cell[wx][y][wz])[0] in self.pal['wall']:
                    self.put(wx, y, wz, 'minecraft:%s[axis=y]' % froglight)
                    self.reserved.add((wx, wz))
                    return True
        if n == 6:
            self.put(x, top, z, 'minecraft:end_rod[facing=down]')
        elif n == 5:
            # 작은 자수정 싹은 빛이 약하다 → 그 위 천장 바위를 개구리불로
            self.put(x, top, z, 'minecraft:small_amethyst_bud[facing=down]')
            self.put(x, top + 1, z, 'minecraft:%s[axis=y]' % froglight)
        else:
            self.put(x, top, z, 'minecraft:lantern[hanging=true]')
        return True

    def fill_light(self):
        """모자란 칸만 보이지 않는 빛 블록 (light) 으로 채운다 (한 번 돌 때마다 서로 먼 자리 여러 개)."""
        placed = 0
        for _ in range(60):
            lvl = self.light_field()
            need = self.needs()
            short = [(m - lvl.get(p, 0), p) for p, m in need.items() if lvl.get(p, 0) < m]
            if not short:
                return placed
            short.sort(key=lambda t: (-t[0], t[1]))
            now = []
            for _gap, (x, y, z) in short:
                if any(abs(x - a) + abs(y - b) + abs(z - c) < 5 for a, b, c in now):
                    continue
                spot = self.light_spot(x, y, z)
                if spot is None:
                    raise SystemExit(f'{self.n}층: 빛을 둘 자리가 없음 {(x, y, z)}')
                sx, sy, sz = spot
                want = need[(x, y, z)] + 2
                level = min(15, want + abs(sy - y) + abs(sx - x) + abs(sz - z))
                self.put(sx, sy, sz, 'minecraft:light[level=%d]' % level)
                now.append((x, y, z))
                placed += 1
        raise SystemExit(f'{self.n}층: 빛 채우기가 끝나지 않음')

    def light_spot(self, x, y, z):
        # 빛 블록은 보이지 않고 부딪히지 않으며 광맥 앞을 가리지도 않는다 (손 시선이 지나감) — 그래도 광맥 바로 앞은 피한다
        top = F + self.ceil[x][z] - 1
        for yy in range(top, y - 1, -1):
            if self.cell[x][yy][z] == AIR and yy >= F + 2 and (x, yy, z) not in self.front:
                return (x, yy, z)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            for yy in range(F + self.ceil[x][z] - 1, F + 1, -1):
                p = (x + dx, yy, z + dz)
                if self.is_air(*p) and p not in self.front:
                    return p
        if self.cell[x][y][z] == AIR:
            return (x, y, z)
        return None

    # ── 8. 짓기 ─────────────────────────────────────────────────────────

    def build(self):
        self.plan()
        self.fill()
        self.lift()
        self.decorate()
        if not self.connected():
            raise SystemExit(f'{self.n}층: 바닥이 이어지지 않음')
        dist = self.distances()
        cand = self.vein_candidates(dist)
        self.place_gems(cand)
        self.place_veins(cand)
        for (x, y, z, ore) in self.veins:
            self.cell[x][y][z] = '@vein:' + ore
        for (x, y, z, g, _f) in self.gem_cells:
            self.cell[x][y][z] = '@gem:' + g
        self.front = set()
        for (x, y, z, *_rest) in self.veins + self.gem_cells:
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                self.front.add((x + dx, y + dy, z + dz))
        self.visible_lights()
        added = self.fill_light()
        self.check_forbidden()
        return self

    def check_forbidden(self):
        for x in range(W):
            for y in range(H):
                for z in range(D):
                    c = self.cell[x][y][z]
                    if c in (AIR, KEEP) or c.startswith('@'):
                        continue
                    if 'minecraft:' + vlib.parse_block(c)[0] in self.forbidden:
                        raise SystemExit(f'{self.n}층: 장식·벽에 광산 블록 {c} at {(x, y, z)}')

    # ── 9. 내보내기 ─────────────────────────────────────────────────────

    def to_json(self):
        blocks = sorted({self.cell[x][y][z] for x in range(W) for y in range(H) for z in range(D)} - {AIR, KEEP})
        letters = [ch for ch in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*+-=?@^~!|:;,<>/\\']
        letters += [chr(c) for c in range(0x00C0, 0x0250)]
        # 논리 글자는 알아보기 쉽게 고정: 광석 1~6 · 보석 ①~⑥
        fixed = {}
        for o, v in self.ores.items():
            fixed['@vein:' + o] = str(v['tier'])
        for g, v in self.gems.items():
            fixed['@gem:' + g] = chr(0x2460 + v['tier'] - 1)
        pal, rev = {}, {}
        free = [l for l in letters if l not in fixed.values()]
        for b in blocks:
            ch = fixed.get(b) or free.pop(0)
            if not b.startswith('@'):
                b = vlib.fill_defaults(b)
                vlib.check_block(b)
            pal[ch] = b
            rev[self.cell_key(b)] = ch
        layers = []
        for y in range(H):
            rows = []
            for z in range(D):
                row = []
                for x in range(W):
                    c = self.cell[x][y][z]
                    if c in (AIR, KEEP):
                        row.append(c)
                    else:
                        row.append(rev[self.cell_key(c if c.startswith('@') else vlib.fill_defaults(c))])
                rows.append(''.join(row))
            layers.append(rows)
        counts = {}
        for (_x, _y, _z, o) in self.veins:
            counts[o] = counts.get(o, 0) + 1
        return {
            'format': 1,
            'id': 'mine_L%d' % self.n,
            'level': self.n,
            'level_id': self.L['id'],
            'name': self.L['name'],
            'size': [W, H, D],
            'origin': [-C, self.floor_y - FL, -C],
            'floor_y': self.floor_y,
            'note': 'tools/mine/gen_mine.py 생성물 — 손으로 고치지 말 것. 글자 1~6 = @vein:<광석>, ①~⑥ = @gem:<보석> (짓는 순간 mine.yml 블록으로).',
            'palette': pal,
            'markers': self.markers,
            'stats': {'veins': len(self.veins), 'vein_blocks': {o: counts[o] for o in sorted(counts, key=lambda o: self.ores[o]['tier'])},
                      'gems': [g for (_x, _y, _z, g, _f) in sorted(self.gem_cells, key=lambda c: (c[1], c[2], c[0]))]},
            'layers': layers,
        }

    @staticmethod
    def cell_key(b):
        return b


def build_level(L, ores, gems, forbidden):
    return Level(L, ores, gems, forbidden).build()
