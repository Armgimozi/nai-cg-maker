--!native
-- 옥반(玉盤): 환해(環海)에 둘러싸인 둥근 평평한 땅. 북쪽이 -z, 동쪽이 +x. 송계 마을이 원점(스폰).
-- (연구용 시안. src/shared/Land.luau 와 같은 API: MIN_X/MAX_X/MIN_Z/MAX_Z, BOTTOM, SEA, height, island,
--  surface, water, column, cells, decorate, coastZ 대신 shoreR/shoreDist)
--
-- 오행 방위: 물(북) 명경호 · 나무(동북동) 태고림 · 불(남동) 홍로성 · 흙(남서) 황구 · 쇠(서북서) 백령 산맥.
-- 가장자리는 바다(환해)이고, 바다는 천애(EDGE)에서 운해로 쏟아져 끝난다. 보이지 않는 벽은 없다.

local Land = {}

Land.MIN_X, Land.MAX_X = -2304, 2304 -- 128 의 배수 (bake 덩어리)
Land.MIN_Z, Land.MAX_Z = -2304, 2304
Land.BOTTOM = -64
Land.SEA = -24
Land.RADIUS = 1720 -- 바닷가 평균 반지름
Land.EDGE = 2240 -- 천애: 이 바깥에는 지형(물 포함)이 없다
Land.SWIM = 2150 -- 이보다 멀리 헤엄치면 해류가 밀어낸다 (서버/클라이언트)

local noise, sqrt, abs, max, min, atan2, sin, cos, floor =
	math.noise, math.sqrt, math.abs, math.max, math.min, math.atan2, math.sin, math.cos, math.floor
local huge = math.huge

local function clamp01(t: number): number
	return if t < 0 then 0 elseif t > 1 then 1 else t
end
local function smooth(a: number, b: number, x: number): number
	local t = clamp01((x - a) / (b - a))
	return t * t * (3 - 2 * t)
end
local function lerp(a: number, b: number, t: number): number
	return a + (b - a) * t
end
local function n(x: number, z: number, scale: number, seed: number): number
	return noise(x / scale, z / scale, seed)
end
local function dist(x: number, z: number, cx: number, cz: number): number
	local dx, dz = x - cx, z - cz
	return sqrt(dx * dx + dz * dz)
end
local function segDist(x: number, z: number, ax: number, az: number, bx: number, bz: number): (number, number)
	local vx, vz = bx - ax, bz - az
	local t = clamp01(((x - ax) * vx + (z - az) * vz) / (vx * vx + vz * vz))
	return dist(x, z, ax + vx * t, az + vz * t), t
end
-- 꺾은선 { {x, z, y?}, ... } 까지 거리와 그 자리 y. 네모 범위(+margin) 밖이면 바로 huge
type Poly = { pts: { { number } }, x0: number, x1: number, z0: number, z1: number }
local function poly(points: { { number } }): Poly
	local p = { pts = points, x0 = huge, x1 = -huge, z0 = huge, z1 = -huge }
	for _, q in points do
		p.x0, p.x1 = min(p.x0, q[1]), max(p.x1, q[1])
		p.z0, p.z1 = min(p.z0, q[2]), max(p.z1, q[2])
	end
	return p
end
local function polyDist(x: number, z: number, p: Poly, margin: number?): (number, number)
	local m = margin or 60
	if x < p.x0 - m or x > p.x1 + m or z < p.z0 - m or z > p.z1 + m then
		return huge, 0
	end
	local best, y = huge, 0
	local pts = p.pts
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local d, t = segDist(x, z, a[1], a[2], b[1], b[2])
		if d < best then
			best, y = d, lerp(a[3] or 0, b[3] or 0, t)
		end
	end
	return best, y
end
Land.smooth = smooth
Land.poly = poly
Land.polyDist = polyDist
-- 잡음 섞인 둥근 덩어리: 안쪽 1, 바깥 0
local function blob(x: number, z: number, b): number
	local d = dist(x, z, b.x, b.z)
	if d > b.r + b.w + b.wob * 1.45 then
		return 0
	end
	d += b.wob * (n(x, z, 230, b.seed) + 0.45 * n(x, z, 90, b.seed + 0.05))
	return smooth(b.r + b.w, b.r - b.w, d)
end
Land.blob = blob

-- 자리 ---------------------------------------------------------------------------------

Land.HUB = { x = 0, z = 0, radius = 110 } -- 송계 마을 (높이 0)
-- 백령(白嶺) 산맥. 관운봉이 가장 높다 ('위' 자리)
Land.PEAK = { x = -900, z = -400, height = 560, radius = 430 } -- 관운봉(貫雲峰)
Land.PEAKS = { -- { x, z, 높이, 반지름, 시드, 지수 }
	{ -780, -930, 400, 330, 0.55, 1.6 }, -- 응봉(鷹峰)
	{ -1020, 440, 300, 250, 0.57, 1.5 }, -- 삼첨봉(三尖峰)
	{ -1390, -430, 300, 280, 0.59, 1.6 }, -- 서령(西嶺)
	{ -680, -60, 130, 170, 0.53, 1.5 }, -- 소봉(小峰), 백금굴 뒷산
}
-- 백령 등줄기 { x, z, 능선 높이(땅 위로) }
Land.SPINE = poly({
	{ -760, -1020, 200 },
	{ -860, -660, 230 },
	{ -930, -420, 260 },
	{ -975, -190, 190 },
	{ -1000, 30, 70 }, -- 송풍령 안장
	{ -1010, 250, 160 },
	{ -1030, 440, 190 },
	{ -930, 640, 60 },
})
Land.VILLAGE_W = { x = -500, z = 40, height = 28 } -- 운곡(雲谷) 마을
Land.MINE = { x = -478, z = -160 } -- 백금굴 (금 오행처): 바위 언덕 KNOLL 동쪽 면
Land.KNOLL = { x = -527, z = -160 }
Land.LAKE = { x = -60, z = -700, radius = 170 } -- 명경호(明鏡湖), 수면 -1
Land.LAKE_W = { x = -215, z = -718, radius = 45 } -- 명경호 서쪽 소(폭포 떨어지는 곳)
Land.ISLET = { x = -40, z = -606 } -- 경심정(鏡心亭) 섬
Land.TABLE = { x = -420, z = -760, r = 230, w = 80, wob = 60, seed = 0.59, cliff = -262, height = 112 } -- 비류대(飛流臺): 동쪽은 벼랑
Land.FALLS = { x = -262, z = -718, top = 110, bottom = -1 } -- 비류폭(飛流瀑)
Land.STREAM = poly({ { -610, -805 }, { -480, -772 }, { -360, -736 }, { -268, -718 } }) -- 비류천 (수면 110)
Land.SNOW = { x = -200, z = -1520, r = 640, w = 70, wob = 80, seed = 0.62 } -- 백랑설원(白浪雪原)
Land.GLACIER = poly({ -- 설하(雪河): 응봉에서 북쪽 바다로 흘러내리는 빙하 { x, z, 겉면 높이 }
	{ -720, -1010, 250 },
	{ -600, -1190, 175 },
	{ -470, -1380, 118 },
	{ -360, -1560, 84 },
	{ -290, -1760, 50 },
})
Land.TARN = { x = -560, z = -1215 } -- 빙경담(氷鏡潭): 빙하 위 얼어붙은 못
Land.STEPPE = { x = 700, z = -1080, r = 640, w = 100, wob = 120, seed = 0.21 } -- 백초원(百草原)
Land.CAMP = { x = 620, z = -800, height = 0 } -- 마령채(馬鈴寨) (높이는 땅을 따른다)
Land.STONES = { x = 420, z = -1040 } -- 팔방석진(八方石陣)
Land.CAPE = { x = 1180, z = -1180, height = 120 } -- 망선대(望仙臺): 운제가 시작되는 바위 곶
Land.SKY = { x = 1370, z = -1370, radius = 170, top = 380 } -- 청허경(淸虛境): 바다 위에 뜬 섬
Land.FOREST = { x = 1110, z = -130, r = 560, w = 90, wob = 110, seed = 0.25 } -- 태고림(太古林)
Land.TREE = { x = 495, z = -160 } -- 만년목(萬年木) (목 오행처)
Land.TEMPLE = { x = 1050, z = -300 } -- 무명사(無名寺) 옛터
Land.BAMBOO = { x = 580, z = 300, r = 210, w = 50, wob = 90, seed = 0.31 } -- 청음죽림(聽音竹林)
Land.HERMIT = { x = 600, z = 330 } -- 청음암(聽音庵)
Land.CITY = { x = 300, z = 540, half = 95, height = 12 } -- 홍로성(紅爐城) (화 오행처)
Land.VOLCANO = { x = 820, z = 960, radius = 300, height = 260, crater = 70 } -- 주염산(朱炎山)
Land.MARSH = { x = 130, z = 1270, r = 260, w = 70, wob = 120, seed = 0.41 } -- 무택(霧澤)
Land.TOWER = { x = 260, z = 1340 } -- 무택 고탑(古塔)
Land.PORT = { x = -440, z = 1575, height = 2 } -- 백사포(白沙浦)
Land.LOESS = { x = -400, z = 540, r = 260, w = 80, wob = 130, seed = 0.15 } -- 황구(黃丘)
Land.EARTH = { x = -305, z = 420 } -- 황구 토단 (토 오행처)
Land.DESERT = { x = -980, z = 980, r = 600, w = 90, wob = 110, seed = 0.17 } -- 한해(旱海)
Land.MESA = { x = -700, z = 700, height = 96 } -- 관성대(觀星臺): 칠성단과 팔괘 기둥
Land.RUINS = { x = -1150, z = 1050, height = 18 } -- 침사국(沈沙國) 옛터
Land.OASIS = { x = -1050, z = 650 } -- 녹주(綠洲)
Land.SALT = { x = -1300, z = 760, r = 140, w = 40, wob = 40, seed = 0.19 } -- 한해 소금벌
-- 사방 성대 (반지름 1200)
Land.STARS = {
	north = { x = 0, z = -1200, height = 92 }, -- 북진대(北辰臺)
	east = { x = 1200, z = 0, height = 0 }, -- 조양대(朝陽臺) (언덕 꼭대기, 높이는 아래에서 채운다)
	south = { x = 0, z = 1200, height = -16 }, -- 남명대(南明臺): 무택 가운데 돌 단
	west = { x = -1200, z = 0, height = 150 }, -- 낙조대(落照臺): 서쪽 고원 벼랑 위
}
Land.EAST_HILL = { x = 1200, z = 0, radius = 150, rise = 58 } -- 조양대 언덕
Land.POOL = { x = -95, z = 178 } -- 벽담(碧潭): 벽계 폭포 아래 못 ('아래' 자리)
-- 벽계(碧溪): 명경호에서 마을 서쪽을 지나 벽계 폭포(z=130)로 (수면 -1)
Land.RIVER = poly({ { -70, -528 }, { -85, -420 }, { -112, -320 }, { -95, -230 }, { -95, 130 } })
-- 벽계협: 폭포 아래 협곡 (수면 -20) → 여울 → 무택 (수면 -24)
Land.GORGE = poly({
	{ -95, 132 },
	{ -95, 178 },
	{ -82, 300 },
	{ -70, 440 },
	{ -20, 580 },
	{ 60, 720 },
	{ 120, 860 },
	{ 150, 1000 },
	{ 160, 1085 },
	{ 185, 1180 }, -- 여울 아래: 무택 물길
})
Land.RAPIDS = { x = 162, z = 1088 } -- 여울: 협곡(-20)이 무택(-24)으로 내려서는 곳
Land.CANYON = poly({ { -200, 600 }, { -300, 700 }, { -290, 860 }, { -380, 1000 }, { -470, 1120 } }) -- 단애곡(丹崖谷)
Land.BUTTES = { -- 황구의 탁상 바위 { x, z, 반지름, 꼭대기 높이 }
	{ -420, 640, 22, 58 },
	{ -540, 830, 18, 72 },
	{ -200, 790, 16, 50 },
	{ -350, 560, 14, 46 },
	{ -150, 690, 12, 40 },
}
-- 바다의 섬
Land.ISLES = {
	-- 월아도(月牙島): 초승달 섬, 옛 천문대 (남남서)
	crescent = { x = -330, z = 1930, r = 115, cut = { x = -280, z = 1885, r = 88 }, height = 24 },
	-- 연파군도(煙波群島): 안개 낀 작은 섬들 (동) { x, z, 반지름, 높이 }
	mist = {
		{ 1930, 260, 58, 34 },
		{ 2015, 385, 38, 22 },
		{ 1880, 430, 30, 16 },
		{ 2045, 190, 22, 52 },
		{ 1975, 530, 24, 12 },
	},
	-- 경도(鯨島): 고래 등 같은 긴 섬 (북서)
	whale = { x = -1420, z = -1270, a = 160, b = 58, angle = -40, height = 40 },
}
-- 바닷가 선을 밀어내거나(+) 들이는(-) 곳 { x, z, 양, 너비(cos) }
local CAPES = {
	{ 1180, -1180, 90, 0.9975 }, -- 망선대 곶
	{ 150, 1300, -80, 0.990 }, -- 무택 하구의 만
	{ -440, 1580, -50, 0.9965 }, -- 백사포 포구
	{ 1200, 0, 40, 0.995 }, -- 조양대 앞 곶
}
for _, cape in CAPES do
	local l = sqrt(cape[1] * cape[1] + cape[2] * cape[2])
	cape[1], cape[2] = cape[1] / l, cape[2] / l
end

-- 길 ---------------------------------------------------------------------------------

-- 땅을 깎아 낸 길 (꼭짓점 셋째 값이 높이. nil 이면 땅을 따라 채운다)
local BENCHES = {
	pool = poly({ { -58, 112 }, { -62, 150, -10 }, { -68, 176, -19 } }), -- 벽담 벼랑길 (지금 그대로)
	snow = poly({ { 150, -860 }, { 110, -930, 30 }, { 70, -1010, 70 }, { 40, -1080, 88 } }), -- 백랑설원 오름길
	pass = poly({ -- 송풍령(松風嶺): 운곡 마을 → 낙조대
		{ -560, 40 },
		{ -700, 60, 54 },
		{ -820, 50, 86 },
		{ -930, 30, 116 },
		{ -1040, 12, 142 },
		{ -1110, 4, 150 },
	}),
	causeway = poly({ { 215, 1030 }, { 160, 1120, -20 }, { 60, 1190, -20 }, { 30, 1200, -16 } }), -- 무택 둑길 → 남명대
	table = poly({ { -250, -560 }, { -330, -600, 40 }, { -420, -640, 80 }, { -500, -660, 110 } }), -- 비류대 오름길
}

-- 돌을 깐 길 (재질만). 송계 마을에서 땅마다
Land.ROADS = {
	{ { 0, -33 }, { 20, -300 }, { 70, -500 }, { 150, -650 }, { 150, -860 } }, -- 1 북: 명경호 동쪽 → 설원 오름길
	{ { 40, -1080 }, { 10, -1170 } }, -- 2 설원 위 → 북진대
	{ { 150, -650 }, { 400, -760 }, { 620, -800 }, { 900, -960 }, { 1097, -1097 } }, -- 3 백초원 → 마령채 → 망선대 길 들머리
	{ { 33, 0 }, { 300, -70 }, { 495, -140 }, { 800, -90 }, { 1055, 0 } }, -- 4 동: 만년목 → 조양대 길 들머리
	{ { 24, 33 }, { 150, 260 }, { 230, 450 } }, -- 5 남동: 홍로성 북문
	{ { 395, 560 }, { 540, 700 }, { 615, 755 } }, -- 6 홍로성 동문 → 주염산 길 들머리
	{ { 360, 450 }, { 470, 360 }, { 600, 330 } }, -- 7 홍로성 → 청음암
	{ { 300, 640 }, { 260, 820 }, { 215, 1030 } }, -- 8 홍로성 남문 → 무택 둑길
	{ { -33, 0 }, { -84, 0 } }, -- 9 서쪽 다리
	{ { -106, 0 }, { -300, -50 }, { -440, -150 }, { -488, -162 } }, -- 10 다리 → 청송림 → 백금굴 앞
	{ { -440, -150 }, { -512, -227 } }, -- 10b → 관운잔도 들머리
	{ { -300, -50 }, { -440, 20 }, { -560, 40 } }, -- 11 청송림 → 운곡 마을 (→ 송풍령)
	{ { 0, 33 }, { 0, 110 }, { -40, 112 }, { -58, 112 } }, -- 12 남 → 벽담 벼랑길
	{ { -106, 0 }, { -180, 200 }, { -305, 400 }, { -500, 560 }, { -640, 640 } }, -- 13 남서: 황구 토단 → 관성대
	{ { -770, 760 }, { -900, 850 }, { -1100, 1010 } }, -- 14 관성대 → 침사국 옛터
	{ { -900, 850 }, { -1050, 680 } }, -- 15 → 녹주
	{ { 30, 1200 }, { -160, 1380 }, { -440, 1560 } }, -- 16 남명대 → 백사포
	{ { 20, -300 }, { -180, -470 }, { -250, -560 } }, -- 17 북서: 비류대 오름길
}

-- 관운봉을 감아 오르는 관운잔도: 노이즈 없는 산 모양을 따라 한 바퀴 남짓 (원뿔 둘레 나선)
type Spiral = { cx: number, cz: number, a0: number, dir: number, n: number, pts: { { number } }, dmax: number }
local function makeSpiral(cx: number, cz: number, d0: number, d1: number, a0: number, dir: number, grade: number, profile: (number) -> number): Spiral
	-- pts[k] = { 중심에서 거리, 높이, 길이 지름 방향과 이루는 사인값 (지름 방향 어긋남 → 길에 수직인 거리) }
	local pts = {}
	local d = d0
	local k = 0
	local function slopeAt(r: number): number
		return profile(r - 0.5) - profile(r + 0.5)
	end
	local function tangential(r: number): number
		local m = slopeAt(r)
		local c = if m > 1e-3 then min(grade / m, 0.95) else 0.95
		return sqrt(1 - c * c), c
	end
	pts[0] = { d, profile(d), (tangential(d)) }
	while d > d1 and k < 2000 do
		local sn, c = tangential(d)
		local ds = d * math.rad(1) / sn
		d = max(d1, d - c * ds)
		k += 1
		pts[k] = { d, profile(d), (tangential(d)) }
	end
	return { cx = cx, cz = cz, a0 = a0, dir = dir, n = k, pts = pts, dmax = d0 + 20 }
end
-- 나선까지 거리(지름 방향)와 그 자리 높이
local function spiralAt(x: number, z: number, sp: Spiral): (number, number)
	local dx, dz = x - sp.cx, z - sp.cz
	local d = sqrt(dx * dx + dz * dz)
	if d > sp.dmax then
		return huge, 0
	end
	local t = ((math.deg(atan2(dz, dx)) - sp.a0) * sp.dir) % 360
	local best, by, bw = huge, 0, 1
	local first = true
	while t <= sp.n do
		local i = floor(t)
		local f = t - i
		local p, q = sp.pts[i], sp.pts[min(i + 1, sp.n)]
		local off = abs(d - lerp(p[1], q[1], f)) * lerp(p[3], q[3], f)
		if off < best then
			-- 들머리에서는 깎는 정도를 0 에서 1 로 (첫 4°)
			best, by, bw = off, lerp(p[2], q[2], f), if first then smooth(0, 4, t) else 1
		end
		t += 360
		first = false
	end
	return best, by, bw
end
-- 나선의 꼭짓점들 (월드 좌표, World 가 난간·등롱을 놓을 때)
function Land.spiralPoints(sp: Spiral, every: number?): { Vector3 | { number } }
	local out = {}
	local step = every or 6
	for k = 0, sp.n, step do
		local p = sp.pts[k]
		local a = math.rad(sp.a0 + sp.dir * k)
		table.insert(out, { sp.cx + cos(a) * p[1], p[2], sp.cz + sin(a) * p[1] })
	end
	return out
end
Land.spiralAt = spiralAt

local peak = Land.PEAK
local PEAK_BASE = 12
local PEAK_TOP = 40 -- 꼭대기 너럭바위 반지름
local function peakProfile(d: number): number
	local u = clamp01(1 - (d - PEAK_TOP) / (peak.radius - PEAK_TOP))
	return PEAK_BASE + (peak.height - PEAK_BASE) * u ^ 1.15
end
-- 들머리 (-512, -227) 에서 남쪽으로 돌아 서쪽, 북쪽을 지나 꼭대기 너럭바위로
Land.PEAK_TRAIL = makeSpiral(peak.x, peak.z, 425, PEAK_TOP + 2, 24, 1, 0.6, peakProfile)

local vol = Land.VOLCANO
local function volcanoProfile(d: number): number
	if d >= vol.crater then
		return 8 + (vol.height - 8) * clamp01((vol.radius - d) / (vol.radius - vol.crater)) ^ 1.25
	end
	return vol.height
end
-- 주염산 화구 둘레로 오르는 길 (홍로성 쪽 북서 기슭에서)
Land.VOLCANO_TRAIL = makeSpiral(vol.x, vol.z, 290, vol.crater + 6, 225, 1, 0.6, volcanoProfile)

local hill = Land.EAST_HILL
local function hillProfile(d: number): number
	local u = clamp01(1 - (d - 28) / (hill.radius - 28))
	return 44 + hill.rise * u ^ 1.3
end
-- 조양대 언덕 (서쪽 기슭에서 남쪽으로 돌아)
Land.HILL_TRAIL = makeSpiral(hill.x, hill.z, 145, 30, 180, -1, 0.3, hillProfile)

local cape = Land.CAPE
local function capeProfile(d: number): number
	local u = clamp01(1 - (d - 24) / (120 - 24))
	return 24 + (cape.height - 24) * u ^ 1.1
end
-- 망선대 (남서 기슭에서)
Land.CAPE_TRAIL = makeSpiral(cape.x, cape.z, 118, 26, 135, 1, 0.42, capeProfile)

-- 길이 거의 곧게 오르는 짧은 나선은 꺾은선 길(BENCHES)로 바꾼다 (극좌표로 재면 가로로 기운다)
local function spiralToPoly(sp: Spiral, every: number): Poly
	local points = {}
	for k = 0, sp.n, every do
		local p = sp.pts[k]
		local a = math.rad(sp.a0 + sp.dir * k)
		table.insert(points, { sp.cx + cos(a) * p[1], sp.cz + sin(a) * p[1], p[2] })
	end
	local last = sp.pts[sp.n]
	local a = math.rad(sp.a0 + sp.dir * sp.n)
	table.insert(points, { sp.cx + cos(a) * last[1], sp.cz + sin(a) * last[1], last[2] })
	return poly(points)
end
local SPIRALS = { Land.PEAK_TRAIL, Land.VOLCANO_TRAIL }
local SHORT_SPIRALS = { hill = Land.HILL_TRAIL, cape = Land.CAPE_TRAIL } -- 조양대 언덕길, 망선대 바위길

-- 바닷가 ---------------------------------------------------------------------------------

-- 방향(x, z)의 바닷가 반지름
function Land.shoreR(x: number, z: number): number
	local r = sqrt(x * x + z * z)
	if r < 1 then
		return Land.RADIUS
	end
	local cx, cz = x / r, z / r
	local R = Land.RADIUS
		+ 95 * noise(cx * 1.7, cz * 1.7, 4.1)
		+ 38 * noise(cx * 5.3, cz * 5.3, 4.3)
		+ 14 * noise(cx * 13, cz * 13, 4.7)
	for _, c in CAPES do
		local dot = cx * c[1] + cz * c[2]
		if dot > c[4] then
			R += c[3] * smooth(c[4], 1 - (1 - c[4]) * 0.3, dot)
		end
	end
	return R
end
-- 바닷가 선까지 (바다 쪽이 +)
function Land.shoreDist(x: number, z: number): number
	return sqrt(x * x + z * z) - Land.shoreR(x, z)
end
-- 예전 coastZ 를 쓰던 곳을 위해: 이 자리가 바다 쪽인가
function Land.isSea(x: number, z: number): boolean
	return Land.shoreDist(x, z) > 0
end

-- 벼랑 바닷가인가 (0 모래밭 ~ 1 벼랑): 서쪽 산맥, 북쪽 빙하, 북동 곶
local function cliffy(x: number, z: number): number
	local w = smooth(-700, -1000, x) -- 서쪽
	local north = smooth(-900, -1200, z) * (1 - smooth(500, 900, x))
	local capeM = 1 - smooth(200, 340, dist(x, z, cape.x, cape.z))
	return max(w, north, capeM)
end

-- 바다 밑 (바닷가에서 s 만큼 바다 쪽)
local function seaFloor(r: number, s: number, cliffW: number): number
	local sea = lerp(-26, -56, smooth(cliffW + 60, cliffW + 420, s))
	-- 천애: 끝으로 갈수록 바닥이 솟아 얕은 턱이 된다 (그 너머로 바다가 쏟아진다)
	return lerp(sea, -32, smooth(Land.EDGE - 140, Land.EDGE - 20, r))
end

local function isles(x: number, z: number, h: number): number
	local c = Land.ISLES.crescent
	local dc = dist(x, z, c.x, c.z)
	if dc < c.r + 30 then
		local cut = dist(x, z, c.cut.x, c.cut.z)
		local m = smooth(c.r + 20, c.r - 20, dc) * smooth(c.cut.r - 16, c.cut.r + 16, cut)
		h = max(h, lerp(-30, c.height + 6 * n(x, z, 40, 1.9), m))
	end
	for _, islet in Land.ISLES.mist do
		local d = dist(x, z, islet[1], islet[2])
		if d < islet[3] + 30 then
			local u = smooth(islet[3] + 26, islet[3] * 0.4, d + 8 * n(x, z, 30, 2.1))
			h = max(h, lerp(-30, islet[4] + 4 * n(x, z, 20, 2.2), u))
		end
	end
	local w = Land.ISLES.whale
	local a = math.rad(w.angle)
	local dx, dz = x - w.x, z - w.z
	local u, v = dx * cos(a) + dz * sin(a), -dx * sin(a) + dz * cos(a)
	local e = sqrt((u / w.a) ^ 2 + (v / w.b) ^ 2)
	if e < 1.4 then
		local m = smooth(1.2, 0.6, e + 0.1 * n(x, z, 40, 2.4))
		h = max(h, lerp(-30, w.height * (1 - e * e * 0.5) + 5 * n(x, z, 30, 2.5), m))
	end
	return h
end

-- 땅마다 섞는 정도
type Masks = {
	desert: number,
	loess: number,
	steppe: number,
	forest: number,
	bamboo: number,
	grove: number,
	snow: number,
	marsh: number,
}
local function masks(x: number, z: number): Masks
	local desert = blob(x, z, Land.DESERT)
	-- 청송림(靑松林): 다리 건너 서쪽 영초 숲 (지금 영초숲 자리 그대로)
	local wx = x + 40 * n(x, z, 160, 0.25)
	local wz = abs(z) + 50 * n(x, z, 180, 0.27)
	local grove = smooth(-110, -190, wx) * (1 - smooth(-430, -520, wx)) * (1 - smooth(300, 390, wz))
	return {
		desert = desert,
		loess = blob(x, z, Land.LOESS) * (1 - desert),
		steppe = blob(x, z, Land.STEPPE),
		forest = blob(x, z, Land.FOREST),
		bamboo = blob(x, z, Land.BAMBOO),
		grove = grove,
		snow = blob(x, z, Land.SNOW),
		marsh = blob(x, z, Land.MARSH),
	}
end
Land.masks = masks

-- 길을 깎기 전의 땅 높이 ---------------------------------------------------------------------
local function ground(x: number, z: number): number
	local r = sqrt(x * x + z * z)
	local sR = Land.shoreR(x, z)
	local s = r - sR
	local cl = cliffy(x, z)
	local cliffW = lerp(110, 22, cl)
	if s > cliffW + 70 then -- 먼바다: 바다 밑과 섬만
		return isles(x, z, seaFloor(r, s, cliffW))
	end

	local M = masks(x, z)
	local plain = 3 + 6 * n(x, z, 260, 0.11) + 2 * n(x, z, 70, 0.13)
		+ smooth(260, 650, r) * 18 * max(0, n(x, z, 330, 0.14) + 0.15) ^ 1.5
	local base = plain
	if M.loess > 0 then
		base = lerp(base, 10 + 12 * n(x, z, 200, 0.81) + 3 * n(x, z, 50, 0.83), M.loess)
	end
	if M.desert > 0 then
		local dir = x * 0.83 + z * 0.55 + 70 * n(x, z, 260, 0.91)
		local dunes = 26 + 12 * n(x, z, 420, 0.93) + 18 * abs(sin(dir / 58)) ^ 1.6
		base = lerp(base, dunes, M.desert)
	end
	if M.steppe > 0 then
		base = lerp(base, 14 + 18 * n(x, z, 340, 0.71) + 5 * n(x, z, 90, 0.73), M.steppe)
	end
	if M.forest > 0 then
		local hills = 16 + 26 * max(0, n(x, z, 240, 0.37) + 0.3) + 6 * n(x, z, 60, 0.39)
		base = lerp(base, hills, M.forest)
	end
	if M.bamboo > 0 then
		base = lerp(base, 9 + 9 * n(x, z, 150, 0.33) + 2 * n(x, z, 40, 0.34), M.bamboo)
	end
	if M.grove > 0 then
		base += M.grove * (6 + 30 * max(0, n(x, z, 110, 0.37) + 0.35))
	end
	if M.snow > 0 then
		local dir = x * 0.4 - z * 0.92 + 60 * n(x, z, 300, 0.66)
		local drifts = 74 + 14 * n(x, z, 300, 0.6) + 10 * abs(sin(dir / 44)) ^ 1.8 + 3 * n(x, z, 30, 0.64)
		base = lerp(base, drifts, M.snow)
	end
	if M.marsh > 0 then
		base = lerp(base, -22 + 2.6 * n(x, z, 60, 0.43) + 1.6 * n(x, z, 18, 0.45), M.marsh)
	end
	local h = base

	-- 송풍령: 운곡 마을에서 서쪽 고원으로 오르는 안장
	if x < -480 and x > -1500 and z > -260 and z < 300 then
		local saddle = lerp(28, 150, smooth(-520, -1080, x)) + 6 * n(x, z, 80, 0.5)
		local band = 1 - smooth(120, 240, abs(z - 20 + 40 * n(x, 0, 300, 0.52)))
		h = max(h, lerp(h, saddle, band))
	end
	-- 낙조대 고원: 서쪽 바닷가 벼랑까지
	if x < -1000 then
		local dW = dist(x, z, -1320, 20)
		if dW < 330 then
			h = max(h, lerp(h, 150 + 5 * n(x, z, 60, 0.54), smooth(320, 220, dW + 30 * n(x, z, 120, 0.56))))
		end
	end

	-- 백령 산맥
	local dP = dist(x, z, peak.x, peak.z)
	if dP < peak.radius then
		local u = 1 - dP / peak.radius
		local ridged = clamp01(1 - abs(n(x, z, 90, 0.51)) * 2.4)
		-- 관운잔도 곁에서는 능선 주름을 눕혀 길이 산허리에 얹히게 한다 (도랑처럼 파이지 않게)
		local dT = spiralAt(x, z, Land.PEAK_TRAIL)
		local rough = smooth(8, 50, dT)
		h = max(h, peakProfile(dP) + (h - PEAK_BASE) * (1 - u) * rough + 50 * ridged * 4 * u * (1 - u) * rough)
	end
	-- 백령 등줄기: 봉우리 사이를 잇는 능선 (송풍령에서 낮아진다)
	if x < -600 and x > -1250 and z > -1150 and z < 760 then
		local ds, sy = polyDist(x, z, Land.SPINE, 170)
		if ds < 170 then
			local u = 1 - ds / 170
			local ridged = clamp01(1 - abs(n(x, z, 70, 0.49)) * 2.2)
			h = max(h, base + sy * u ^ 1.4 + 30 * ridged * 4 * u * (1 - u))
		end
	end
	for _, other in Land.PEAKS do
		local d = dist(x, z, other[1], other[2])
		if d < other[4] then
			local u = 1 - d / other[4]
			local ridged = clamp01(1 - abs(n(x, z, 80, other[5])) * 2.4)
			h = max(h, base + other[3] * u ^ other[6] + 40 * ridged * 4 * u * (1 - u))
		end
	end
	if dP < PEAK_TOP + 70 then -- 꼭대기가 가장 높다
		h = min(h, peak.height - 2 * smooth(PEAK_TOP, PEAK_TOP + 20, dP))
	end
	if dP < PEAK_TOP + 8 then -- 관운봉 꼭대기 너럭바위
		h = lerp(peak.height, h, smooth(PEAK_TOP - 4, PEAK_TOP + 8, dP))
	end
	local dK = dist(x, z, Land.KNOLL.x, Land.KNOLL.z) -- 백금굴 바위 언덕
	if dK < 46 then
		h = max(h, lerp(h + 30, h, smooth(26, 46, dK)))
	end
	-- 비류대: 명경호 서쪽의 높은 대지 (동쪽은 깎아지른 벼랑)
	local T = Land.TABLE
	if x > T.x - T.r - T.w - 90 and x < -240 and abs(z - T.z) < T.r + T.w + 90 then
		local ex = smooth(T.cliff + 6, T.cliff - 6, x + 10 * n(x, z, 45, 0.57)) -- 동쪽 벼랑
		local m = ex * blob(x, z, T)
		local top = T.height + 5 * n(x, z, 70, 0.58)
		h = max(h, lerp(h, top, m))
		-- 비류천 물길 (수면 110)
		local ds = polyDist(x, z, Land.STREAM, 20)
		if ds < 16 then
			h = min(h, lerp(104, h, smooth(5, 16, ds)))
		end
	end
	-- 설하 빙하: 둥근 등성이
	local dg, gy = polyDist(x, z, Land.GLACIER, 140)
	if dg < 130 then
		h = max(h, lerp(gy + 6 * n(x, z, 50, 0.68), h, smooth(55, 130, dg)))
		local dT = dist(x, z, Land.TARN.x, Land.TARN.z)
		if dT < 50 then
			h = lerp(gy - 6, h, smooth(28, 50, dT))
		end
	end
	-- 북진대: 설원 위 둥근 단
	local sn = Land.STARS.north
	local dN = dist(x, z, sn.x, sn.z)
	if dN < 60 then
		h = lerp(sn.height, h, smooth(26, 60, dN))
	end

	-- 명경호 (수면 -1) 와 서쪽 소
	local lake = Land.LAKE
	local dL = dist(x, z, lake.x, lake.z) + 14 * n(x, z, 90, 0.75)
	if dL < lake.radius + 40 then
		h = min(h, lerp(-12, h, smooth(lake.radius - 30, lake.radius + 40, dL)))
	end
	local lw = Land.LAKE_W
	local dLw = dist(x, z, lw.x, lw.z)
	if dLw < lw.radius + 30 then
		h = min(h, lerp(-14, h, smooth(lw.radius - 15, lw.radius + 30, dLw)))
	end
	local dI = dist(x, z, Land.ISLET.x, Land.ISLET.z)
	if dI < 34 then
		h = max(h, lerp(2.5, h, smooth(18, 34, dI)))
	end
	-- 백초원 팔방석진, 마령채 (땅을 고른다)
	local dSt = dist(x, z, Land.STONES.x, Land.STONES.z)
	if dSt < 60 then
		h = lerp(18, h, smooth(36, 60, dSt))
	end
	-- 망선대 곶 바위
	local dC = dist(x, z, cape.x, cape.z)
	if dC < 130 then
		h = max(h, lerp(h, capeProfile(dC) + 4 * n(x, z, 30, 2.7), smooth(128, 80, dC)))
		if dC < 30 then
			h = lerp(cape.height, h, smooth(22, 30, dC))
		end
	end
	-- 조양대 언덕
	local dH = dist(x, z, hill.x, hill.z)
	if dH < hill.radius then
		h = max(h, lerp(h, hillProfile(dH) + 3 * n(x, z, 30, 2.8), smooth(hill.radius, hill.radius - 60, dH)))
		if dH < 34 then
			h = lerp(hillProfile(0), h, smooth(26, 34, dH))
		end
	end

	-- 주염산: 가운데가 꺼진 불의 산
	local dV = dist(x, z, vol.x, vol.z)
	if dV < vol.radius then
		local cone = if dV >= vol.crater then volcanoProfile(dV) else vol.height - 45 + 45 * smooth(vol.crater - 25, vol.crater, dV)
		h = max(h, cone + 4 * n(x, z, 30, 1.3))
	end

	-- 한해: 관성대, 침사국 옛터, 녹주, 소금벌
	if M.desert > 0.05 or M.loess > 0.05 then
		local dR = dist(x, z, Land.RUINS.x, Land.RUINS.z)
		if dR < 100 then
			h = lerp(Land.RUINS.height, h, smooth(62, 100, dR))
		end
		local salt = blob(x, z, Land.SALT)
		if salt > 0 then
			h = lerp(h, 6 + 0.6 * n(x, z, 20, 1.1), salt)
		end
		local dO = dist(x, z, Land.OASIS.x, Land.OASIS.z)
		if dO < 70 then
			h = lerp(18, h, smooth(30, 70, dO))
		end
		if dO < 22 then
			h = lerp(12, 18, smooth(14, 22, dO))
		end
		local mesa = Land.MESA
		local dM = dist(x, z, mesa.x, mesa.z)
		if dM < 100 then
			h = max(h, lerp(mesa.height, h, smooth(72, 92, dM)))
			if dM >= 72 and dM < 90 then
				-- 북동(315°)에서 시작해 시계 반대로 130° 돌아 꼭대기
				local theta = (315 - math.deg(atan2(z - mesa.z, x - mesa.x))) % 360
				if theta <= 130 then
					h = lerp(30, mesa.height, theta / 130)
				end
			end
		end
		-- 단애곡과 탁상 바위
		local dc = polyDist(x, z, Land.CANYON, 50)
		if dc < 40 then
			h = min(h, lerp(-14, h, smooth(10, 40, dc)))
		end
		for _, butte in Land.BUTTES do
			local d = dist(x, z, butte[1], butte[2])
			if d < butte[3] + 14 then
				h = max(h, lerp(butte[4], h, smooth(butte[3], butte[3] + 14, d)))
			end
		end
	end

	-- 사람 사는 곳은 평평하게
	local city = Land.CITY
	if abs(x - city.x) < city.half + 40 and abs(z - city.z) < city.half + 40 then
		local m = (1 - smooth(city.half - 25, city.half + 5, abs(x - city.x)))
			* (1 - smooth(city.half - 25, city.half + 5, abs(z - city.z)))
		h = lerp(h, city.height, m)
	end
	local vw = Land.VILLAGE_W
	local dS = dist(x, z, vw.x, vw.z)
	if dS < 110 then
		h = lerp(vw.height, h, smooth(60, 110, dS))
	end
	local camp = Land.CAMP
	local dCa = dist(x, z, camp.x, camp.z)
	if dCa < 90 then
		h = lerp(20, h, smooth(50, 90, dCa))
	end
	local dTe = dist(x, z, Land.TEMPLE.x, Land.TEMPLE.z)
	if dTe < 70 then
		h = lerp(30, h, smooth(40, 70, dTe))
	end
	local dHe = dist(x, z, Land.HERMIT.x, Land.HERMIT.z)
	if dHe < 50 then
		h = lerp(12, h, smooth(28, 50, dHe))
	end
	local dEa = dist(x, z, Land.EARTH.x, Land.EARTH.z)
	if dEa < 50 then
		h = lerp(16, h, smooth(22, 50, dEa))
	end
	local dTr = dist(x, z, Land.TREE.x, Land.TREE.z)
	if dTr < 40 then
		h = lerp(20, h, smooth(24, 40, dTr))
	end
	local sw = Land.STARS.south
	local dSo = dist(x, z, sw.x, sw.z)
	if dSo < 55 then
		h = lerp(sw.height, h, smooth(30, 55, dSo))
	end
	local dTw = dist(x, z, Land.TOWER.x, Land.TOWER.z)
	if dTw < 34 then
		h = lerp(-18, h, smooth(18, 34, dTw))
	end
	h = lerp(0, h, smooth(Land.HUB.radius, 200, r))

	-- 벽계
	local dr = polyDist(x, z, Land.RIVER, 40)
	if dr < 34 then
		if dr < 9 then
			h = min(h, -5)
		else
			h = lerp(min(h, 0), h, smooth(9, 34, dr))
		end
	end
	if z > 126 then
		local dgo = polyDist(x, z, Land.GORGE, 40)
		local dpool = dist(x, z, Land.POOL.x, Land.POOL.z)
		if dgo < 36 or dpool < 40 then
			local bank = -19
			local g = if dgo < 8 then -24 elseif dgo < 20 then bank else lerp(bank, h, smooth(20, 36, dgo))
			if dpool < 22 then
				g = -30
			elseif dpool < 32 then
				g = min(g, bank)
			end
			if z > Land.RAPIDS.z - 4 and dgo < 14 then
				g -= 4 -- 여울 아래는 바다 높이 물 (무택)
			end
			h = min(h, g)
			-- 여울 턱: 협곡 물(-20)이 이 바위 턱을 넘어 무택(-24)으로
			if abs(z - (Land.RAPIDS.z - 6)) < 4 and dgo < 12 then
				h = max(h, -21)
			end
		end
	end

	-- 바닷가: 벼랑 또는 모래밭, 그리고 바다 밑
	if s > -30 then
		local beach = lerp(h, -20, smooth(-10, cliffW, s))
		beach = lerp(beach, -26, smooth(cliffW + 10, cliffW + 50, s))
		h = if s < cliffW + 60 then min(h, beach) else seaFloor(r, s, cliffW)
		-- 백사포 잔교 앞 모래톱
		h = isles(x, z, h)
	end
	return h
end

-- 깎아 낸 길의 꼭짓점 높이를 땅에서 채운다
for _, bench in BENCHES do
	for _, point in bench.pts do
		if point[3] == nil then
			point[3] = ground(point[1], point[2])
		end
	end
end
Land.BENCHES = BENCHES
-- 나선 길의 들머리는 땅 높이에서 시작해 산 모양으로 이어진다
local allSpirals = table.clone(SPIRALS)
for _, sp in SHORT_SPIRALS do
	table.insert(allSpirals, sp)
end
for _, sp in allSpirals do
	local a = math.rad(sp.a0)
	local offset = ground(sp.cx + cos(a) * sp.pts[0][1], sp.cz + sin(a) * sp.pts[0][1]) - sp.pts[0][2]
	local span = min(90, sp.n * 2 // 3)
	for k = 0, span do
		sp.pts[k][2] += offset * (1 - smooth(0, span, k))
	end
end
for name, sp in SHORT_SPIRALS do
	BENCHES[name] = spiralToPoly(sp, 4)
end

-- 땅 높이 (지형 겉면)
function Land.height(x: number, z: number): number
	local r2 = x * x + z * z
	if r2 > Land.EDGE * Land.EDGE then
		return Land.BOTTOM
	end
	local h = ground(x, z)
	for _, bench in BENCHES do
		local d, y = polyDist(x, z, bench, 16)
		if d < 14 then
			h = lerp(y, h, smooth(5, 14, d))
		end
	end
	for _, sp in SPIRALS do
		local d, y, w = spiralAt(x, z, sp)
		if d < 14 then
			h = lerp(h, lerp(y, h, smooth(5, 14, d)), w)
		end
	end
	return h
end

-- 청허경: 이 기둥에 뜬 섬이 있으면 밑면과 윗면 높이
function Land.island(x: number, z: number): (number?, number?)
	local isle = Land.SKY
	local r = dist(x, z, isle.x, isle.z)
	if r >= isle.radius * 1.15 then
		return nil, nil
	end
	local theta = atan2(z - isle.z, x - isle.x)
	local radius = isle.radius * (1 + 0.12 * noise(cos(theta) * 2, sin(theta) * 2, 2.1))
	if r >= radius then
		return nil, nil
	end
	local t = r / radius
	local top = isle.top + 10 * n(x, z, 70, 2.3) - 24 * smooth(0.75, 1, t)
	local bottom = isle.top - 20 - 150 * (1 - t) ^ 1.5 + 10 * n(x, z, 40, 2.5)
	if bottom >= top - 2 then
		return nil, nil
	end
	return bottom, top
end

function Land.surface(x: number, z: number): number
	local _, top = Land.island(x, z)
	return top or Land.height(x, z)
end

-- 이 기둥의 수면 (물이 없으면 nil)
function Land.water(x: number, z: number, h: number): number?
	local r = sqrt(x * x + z * z)
	if r > Land.EDGE then
		return nil
	end
	if h < Land.SEA and r > Land.shoreR(x, z) - 60 then
		return Land.SEA
	end
	if h < -1 and z <= 128 and polyDist(x, z, Land.RIVER, 20) < 14 then
		return -1
	end
	if h < -1 then
		if dist(x, z, Land.LAKE.x, Land.LAKE.z) < Land.LAKE.radius + 60 or dist(x, z, Land.LAKE_W.x, Land.LAKE_W.z) < Land.LAKE_W.radius + 30 then
			return -1
		end
	end
	if z > 126 and h < -20 then
		if (z < Land.RAPIDS.z - 2 and polyDist(x, z, Land.GORGE, 20) < 10) or dist(x, z, Land.POOL.x, Land.POOL.z) < 24 then
			return -20
		end
	end
	if h < Land.SEA and (blob(x, z, Land.MARSH) > 0.3 or (z >= Land.RAPIDS.z - 4 and polyDist(x, z, Land.GORGE, 20) < 14)) then
		return Land.SEA
	end
	if h < 110 and h > 90 and polyDist(x, z, Land.STREAM, 12) < 8 then
		return 110
	end
	if h < 16 and dist(x, z, Land.OASIS.x, Land.OASIS.z) < 18 then
		return 16
	end
	return nil
end

-- 재질 ---------------------------------------------------------------------------------

local ROAD_POLYS = {}
for _, road in Land.ROADS do
	table.insert(ROAD_POLYS, poly(road))
end
local function nearRoad(x: number, z: number, width: number): boolean
	for _, road in ROAD_POLYS do
		if polyDist(x, z, road, width) < width then
			return true
		end
	end
	for _, bench in BENCHES do
		if polyDist(x, z, bench, width) < width then
			return true
		end
	end
	for _, sp in SPIRALS do
		if spiralAt(x, z, sp) < width then
			return true
		end
	end
	return false
end

local function materials(x: number, z: number, h: number, slope: number): (string, string)
	local M = masks(x, z)
	local wiggle = 30 * n(x, z, 60, 3.1)
	local r = sqrt(x * x + z * z)
	local s = r - Land.shoreR(x, z)
	-- 바다와 바닷가
	if s > -40 and h < -6 then
		if r > Land.EDGE - 140 and h < -28 then
			return "Basalt", "Basalt" -- 천애의 턱
		end
		if h < Land.SEA - 6 then
			return (if h < -40 then "Mud" else "Sand"), "Rock"
		end
		return (if slope > 1.1 then "Slate" else "Sand"), "Rock"
	end
	if s > -14 - 30 * n(x, z, 160, 3.5) and h < 40 and slope < 0.6 and cliffy(x, z) < 0.5 then
		return "Sand", "Sandstone"
	end
	-- 무택
	if M.marsh > 0.5 and h < -10 then
		return (if n(x, z, 24, 3.7) > 0.15 then "LeafyGrass" else "Mud"), "Mud"
	end
	-- 강바닥과 협곡
	if h < -2 and (polyDist(x, z, Land.RIVER, 30) < 30 or (z > 126 and polyDist(x, z, Land.GORGE, 40) < 40)) then
		return (if slope > 0.9 then "Slate" else "Mud"), "Rock"
	end
	if h < -1 and dist(x, z, Land.LAKE.x, Land.LAKE.z) < Land.LAKE.radius + 50 then
		return "Mud", "Rock"
	end
	-- 주염산
	local dV = dist(x, z, vol.x, vol.z)
	if dV < vol.radius - 10 + wiggle and h > 14 then
		if dV < vol.crater - 10 then
			return "CrackedLava", "Basalt"
		end
		local streak = abs(n(x, z, 40, 3.3)) < 0.06 and dV < vol.radius - 60
		if streak then
			return "CrackedLava", "Basalt"
		end
		return (if dV > vol.radius - 90 then "Asphalt" else "Basalt"), "Basalt"
	end
	-- 길 (높은 산길 포함)
	if h > -2 and nearRoad(x, z, 4) then
		return (if M.desert > 0.5 then "Sandstone" else "Cobblestone"), "Rock"
	end
	-- 빙하와 설원, 높은 산
	local dg = polyDist(x, z, Land.GLACIER, 80)
	if dg < 70 + wiggle * 0.5 and h > 40 then
		if dist(x, z, Land.TARN.x, Land.TARN.z) < 32 then
			return "Ice", "Glacier"
		end
		return "Glacier", "Glacier"
	end
	if M.snow > 0.5 and h > 40 then
		return (if slope > 1.2 then "Glacier" elseif dist(x, z, Land.STARS.north.x, Land.STARS.north.z) < 30 then "Slate" else "Snow"), "Rock"
	end
	local snowLine = 330 + wiggle
	if h > snowLine then
		return (if slope > 1.4 then "Glacier" else "Snow"), "Rock"
	end
	-- 백령: 높은 곳은 바위, 고원과 대지 위는 풀밭
	if x < -440 then
		if h > 230 + wiggle * 2 then
			return (if slope > 0.8 then "Rock" else "Slate"), "Rock"
		end
		if slope > 0.9 then
			return (if slope > 1.6 then "Slate" else "Rock"), "Rock"
		end
		if h > 60 then
			return (if n(x, z, 90, 3.6) > 0.25 then "Rock" else "Grass"), "Rock"
		end
	end
	-- 한해
	if M.desert > 0.5 then
		if dist(x, z, Land.RUINS.x, Land.RUINS.z) < 64 then
			return "Pavement", "Sandstone"
		end
		if dist(x, z, Land.OASIS.x, Land.OASIS.z) < 40 then
			return "Grass", "Sandstone"
		end
		if blob(x, z, Land.SALT) > 0.5 then
			return "Salt", "Sandstone"
		end
		if dist(x, z, Land.MESA.x, Land.MESA.z) < 94 or slope > 0.7 then
			return "Sandstone", "Sandstone"
		end
		return "Sand", "Sandstone"
	end
	-- 황구: 누런 흙과 붉은 벼랑
	if M.loess > 0.5 then
		if slope > 0.8 or polyDist(x, z, Land.CANYON, 34) < 34 then
			return "Sandstone", "Sandstone"
		end
		return (if dist(x, z, Land.EARTH.x, Land.EARTH.z) < 24 then "Ground" else "Limestone"), "Sandstone"
	end
	-- 숲
	if M.forest > 0.4 then
		return (if slope > 0.8 then "Rock" elseif n(x, z, 130, 3.9) > 0.38 then "Ground" else "LeafyGrass"), "Rock"
	end
	if M.bamboo > 0.4 then
		return (if slope > 0.8 then "Rock" else "LeafyGrass"), "Rock"
	end
	if M.grove > 0.4 then
		return (if slope > 0.8 then "Rock" else "LeafyGrass"), "Rock"
	end
	if dist(x, z, Land.OASIS.x, Land.OASIS.z) < 40 then
		return "Grass", "Sandstone"
	end
	if dist(x, z, cape.x, cape.z) < 90 and slope > 0.6 then
		return "Slate", "Rock"
	end
	return (if slope > 1 then "Rock" else "Grass"), "Rock"
end

-- 지형 칸 -------------------------------------------------------------------------------

export type Column = {
	ground: number,
	surface: string,
	under: string,
	water: number?,
	islandBottom: number?,
	islandTop: number?,
	top: number,
}

local EMPTY: Column = {
	ground = Land.BOTTOM - 8,
	surface = "Rock",
	under = "Rock",
	water = nil,
	islandBottom = nil,
	islandTop = nil,
	top = Land.BOTTOM - 8,
}
function Land.column(x: number, z: number): Column
	if x * x + z * z > Land.EDGE * Land.EDGE then
		return EMPTY -- 천애 바깥: 아무것도 없다
	end
	local h = Land.height(x, z)
	local hx = Land.height(x + 4, z)
	local hz = Land.height(x, z + 4)
	local slope = max(abs(hx - h), abs(hz - h)) / 4
	local surface, under = materials(x, z, h, slope)
	local water = Land.water(x, z, h)
	local bottom, top = Land.island(x, z)
	return {
		ground = h,
		surface = surface,
		under = under,
		water = water,
		islandBottom = bottom,
		islandTop = top,
		top = max(h, water or -huge, top or -huge),
	}
end

local SKIN = 2
function Land.cells(column: Column, bottom: number, ny: number, emit: (number, string, number) -> ())
	local g = column.ground - SKIN
	local water = column.water
	local ib = column.islandBottom
	local it = column.islandTop
	for b = 0, ny - 1 do
		local y0 = bottom + b * 4
		local solid = clamp01((g - y0) / 4)
		if water and y0 + 4 <= water and solid > 0 and solid < 1 then
			solid = if solid >= 0.5 then 1 else 0
		end
		if solid > 0 then
			emit(b, if g - y0 > 10 then column.under else column.surface, solid)
		elseif ib and it and y0 + 4 > ib + SKIN and y0 < it - SKIN then
			local occupancy = min(clamp01((it - SKIN - y0) / 4), clamp01((y0 + 4 - ib - SKIN) / 4))
			if occupancy > 0 then
				local fromTop = it - y0
				local name = if fromTop < 8 then "LeafyGrass" elseif y0 < ib + 30 then "Basalt" else "Slate"
				emit(b, name, occupancy)
			end
		elseif water and y0 < water then
			emit(b, "Water", clamp01((water - y0) / 4))
		elseif y0 > column.top then
			break
		end
	end
end

-- 재질 색 (굽는 곳과 서버 둘 다)
Land.COLORS = {
	Sand = { 214, 186, 132 },
	Sandstone = { 190, 120, 78 },
	Ground = { 150, 112, 74 },
	Limestone = { 198, 156, 94 }, -- 황구 누런 흙
	Salt = { 236, 232, 222 }, -- 한해 소금벌
	Asphalt = { 74, 68, 66 }, -- 주염산 잿벌
	Basalt = { 52, 48, 48 },
	CrackedLava = { 232, 90, 40 },
	Snow = { 240, 244, 250 },
	Glacier = { 170, 210, 235 },
	Slate = { 96, 104, 112 },
	LeafyGrass = { 66, 108, 58 },
	Grass = { 104, 146, 76 },
	Mud = { 88, 76, 60 },
	Cobblestone = { 140, 134, 122 },
	Pavement = { 168, 150, 120 },
	Rock = { 112, 108, 104 },
	Ice = { 180, 220, 240 },
}
function Land.decorate(terrain: any)
	for name, rgb in Land.COLORS do
		terrain:SetMaterialColor((Enum.Material :: any)[name], Color3.fromRGB(rgb[1], rgb[2], rgb[3]))
	end
	terrain.WaterColor = Color3.fromRGB(30, 96, 120)
	terrain.WaterTransparency = 0.35
	terrain.WaterWaveSize = 0.15
	terrain.WaterWaveSpeed = 8
	terrain.WaterReflectance = 0.6
	if not terrain:FindFirstChildOfClass("Clouds") then
		local clouds = Instance.new("Clouds")
		clouds.Cover = 0.5
		clouds.Density = 0.45
		clouds.Parent = terrain
	end
end

return Land
