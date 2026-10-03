--!native
-- 수계(하계) 땅 모양. 지형(Terrain)과 맵 위의 모든 것이 이 한 곳의 높이를 따른다.
--
-- 순수 계산만 있다 (math.noise 는 Lune 과 Roblox 서버가 같은 Luau 구현이라 값이 같다).
--   tools/bake_place.luau  이 모양대로 지형을 플레이스 파일에 굽는다 (SmoothGrid)
--   server/TerrainGen.luau 구운 지형을 엔진이 못 읽었을 때 서버에서 같은 모양으로 짓는다
--   server/World.luau      집·자리·진을 이 높이에 놓는다 (Lune 에서는 레이캐스트를 못 쓴다)
--
-- 원작 수계의 방위를 따른다: 가운데 답천사막과 그 위에 뜬 등선향, 서쪽에 벽라국·연국·성제국(쇄천봉),
-- 동쪽 끝은 부족 땅, 북쪽은 대초원, 남쪽은 끝없는 바다. 연국 마을이 원점(스폰)이다. 북쪽이 -z.
-- 서천 설원, 화구산, 해룡 사당, 남천도 천문대 자리는 게임에서 정한 것이다.

local Land = {}

Land.MIN_X, Land.MAX_X = -1280, 1280
Land.MIN_Z, Land.MAX_Z = -1280, 1280
Land.BOTTOM = -64 -- 지형 바닥 (4 의 배수)
Land.SEA = -24 -- 바다 수면
Land.EDGE = 1272 -- 세계순력 벽

local noise, sqrt, abs, max, min, atan2, sin, cos =
	math.noise, math.sqrt, math.abs, math.max, math.min, math.atan2, math.sin, math.cos

local function clamp01(t: number): number
	return if t < 0 then 0 elseif t > 1 then 1 else t
end
-- a 에서 0, b 에서 1 로 부드럽게 (a > b 여도 된다)
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
-- 꺾은선까지 거리. 꼭짓점에 높이(셋째 값)가 있으면 그 자리 높이도
local function polyDist(x: number, z: number, points: { { number } }): (number, number)
	local best, y = math.huge, 0
	for i = 1, #points - 1 do
		local a, b = points[i], points[i + 1]
		local d, t = segDist(x, z, a[1], a[2], b[1], b[2])
		if d < best then
			best, y = d, lerp(a[3] or 0, b[3] or 0, t)
		end
	end
	return best, y
end
Land.smooth = smooth
Land.polyDist = polyDist

-- 지형 ---------------------------------------------------------------------------------

Land.HUB = { x = 0, z = 0, radius = 110 } -- 연국 마을 (높이 0 으로 평평)
Land.PEAK = { x = -860, z = -220, height = 440, radius = 440 } -- 쇄천봉 주봉
Land.PEAKS = { -- 쇄천봉 산맥의 다른 봉우리 { x, z, 높이, 반지름, 시드 }
	{ -980, -640, 330, 330, 0.55 },
	{ -1060, 300, 230, 250, 0.57 },
	{ -720, -520, 210, 220, 0.59 },
}
Land.TARN = { x = -640, z = -330 } -- 빙호 (얼어붙은 산 못)
Land.KNOLL = { x = -500, z = -70 } -- 금맥굴 바위 언덕
Land.SEOAK = { x = -505, z = 40, height = 28 } -- 서악 마을
Land.VOLCANO = { x = 470, z = -300 } -- 화구산
Land.TOWN = { x = 420, z = -10, height = 10 } -- 천색성
Land.MESA = { x = 780, z = -360, height = 96 } -- 답천대
Land.RUINS = { x = 860, z = -40, height = 18 } -- 중령성국 폐허
Land.ISLAND = { x = 860, z = -40, radius = 150 } -- 등선향
Land.OASIS = { x = 730, z = 200 }
Land.EAST_ROCK = { x = 1190, z = -40 } -- 동쪽 성대 바위
Land.LAKE_N = { x = 260, z = -900, radius = 55 } -- 초원 호수
Land.TORTOISE = { x = 0, z = -1180 } -- 현무 언덕
Land.SOUTH_ISLE = { x = 40, z = 1150 } -- 남천도
Land.POOL = { x = -95, z = 178 } -- 용소 (폭포 아래 못)

-- 연하: 쇄천봉에서 내려와 마을 서쪽을 지나는 강 (수면 -1), 폭포 아래 협곡 (수면 -20), 바다로
Land.RIVER = { { -430, -390 }, { -260, -405 }, { -140, -350 }, { -95, -230 }, { -95, 130 } }
Land.GORGE = { { -95, 132 }, { -95, 178 }, { -82, 300 }, { -108, 420 }, { -92, 540 }, { -95, 660 } }
Land.CANYON = { { 300, 90 }, { 360, 200 }, { 330, 320 }, { 400, 440 }, { 380, 560 }, { 420, 650 } } -- 적사협
Land.BUTTES = { -- 벽라국 탁상 바위 { x, z, 반지름, 꼭대기 높이 }
	{ 480, 180, 26, 58 },
	{ 540, 330, 18, 72 },
	{ 260, 380, 22, 50 },
	{ 470, 470, 16, 64 },
	{ 560, 120, 14, 46 },
}
Land.CAUSEWAY = { { 30, 650 }, { 40, 1085 } } -- 남천도로 건너는 둑길

-- 땅을 깎아 낸 길 (꼭짓점 높이는 아래에서 땅을 따라 채운다)
local BENCHES = {
	pool = { { -58, 112, 0 }, { -62, 150, -10 }, { -68, 176, -19 } }, -- 용소로 내려가는 벼랑길
	coast = { { 150, 540, 0 }, { 110, 600, -10 }, { 60, 655, -20 } }, -- 바닷가로 내려가는 비탈길
}

-- 돌을 깐 길 (재질만 바꾼다). 마을에서 땅마다 이어진다
Land.ROADS = {
	{ { 0, -33 }, { 0, -400 }, { 60, -640 }, { 140, -820 }, { 30, -1100 }, { 10, -1160 } }, -- 북쪽 대초원
	{ { 33, 0 }, { 330, -10 } }, -- 동쪽 천색성
	{ { 510, -10 }, { 620, -40 }, { 700, -300 } }, -- 천색성 → 답천대 비탈 아래
	{ { -33, 0 }, { -84, 0 } }, -- 서쪽 다리
	{ { -106, 0 }, { -300, -50 }, { -440, -150 } }, -- 다리 → 영초숲 → 쇄천봉 들머리
	{ { -300, -50 }, { -440, 20 }, { -490, 20 } }, -- 영초숲 → 서악 마을
	{ { 0, 33 }, { 0, 110 }, { -40, 112 }, { -58, 112 } }, -- 남쪽 → 용소 벼랑길
	{ { 0, 110 }, { 60, 110 }, { 150, 540 } }, -- 남쪽 → 바닷가 비탈길
}
-- 쇄천봉 천뢰잔도 (들머리 → 금신천뢰문 옛터 → 꼭대기), 백호령 (서악 → 서천 설원)
Land.PEAK_TRAIL = {
	{ -440, -150 },
	{ -560, -110 },
	{ -560, -260 },
	{ -660, -180 },
	{ -660, -300 },
	{ -760, -200 },
	{ -790, -280 },
	{ -848, -228 },
}
Land.WEST_TRAIL = { { -540, 70 }, { -680, 160 }, { -860, 190 }, { -980, 140 }, { -1100, 70 }, { -1170, 40 } }

local CANALS = {} -- 중령성국의 마른 용맥 수로 넷
for _, angle in { 20, 110, 200, 290 } do
	local r = math.rad(angle)
	table.insert(CANALS, {
		Land.RUINS.x + cos(r) * 70,
		Land.RUINS.z + sin(r) * 70,
		Land.RUINS.x + cos(r) * 360,
		Land.RUINS.z + sin(r) * 360,
	})
end

-- 바닷가 선 (이 z 보다 남쪽은 바다 쪽)
function Land.coastZ(x: number): number
	return 610 + 110 * noise(x / 380, 1.11, 0.5) + 35 * noise(x / 110, 1.13, 0.5)
end

-- 땅마다 섞는 정도 (경계는 노이즈로 구불구불하게)
local function masks(x: number, z: number): (number, number, number, number)
	local scrub = smooth(200, 330, x + 80 * n(0, z, 300, 0.15))
	local desert = smooth(560, 700, x + 130 * n(0, z, 360, 0.17) + 35 * n(0, z, 90, 0.19))
	local steppe = smooth(-500, -700, z + 110 * n(x, 0, 380, 0.21) + 30 * n(x, 0, 80, 0.23))
	-- 영초숲: 강 서쪽 언덕, 가장자리는 구불구불
	local wx = x + 40 * n(x, z, 160, 0.25)
	local wz = abs(z) + 50 * n(x, z, 180, 0.27)
	local forest = smooth(-110, -190, wx) * (1 - smooth(-450, -540, wx)) * (1 - smooth(300, 390, wz))
	return scrub, desert, steppe, forest
end

-- 서천 설원의 동쪽 끝 (x)
local function snowEdge(z: number): number
	return -1000 + 70 * n(0, z, 220, 0.62)
end

-- 길을 깎기 전의 땅 높이
local function ground(x: number, z: number): number
	local scrubM, desertM, steppeM, forestM = masks(x, z)
	local plain = 3 + 6 * n(x, z, 260, 0.11) + 2 * n(x, z, 70, 0.13)
	local steppe = 14 + 18 * n(x, z, 340, 0.71) + 5 * n(x, z, 90, 0.73)
	local scrub = 8 + 10 * n(x, z, 200, 0.81) + 2 * n(x, z, 50, 0.83)
	local dir = x * 0.83 + z * 0.55 + 70 * n(x, z, 260, 0.91)
	local dunes = 26 + 12 * n(x, z, 420, 0.93) + 18 * abs(sin(dir / 58)) ^ 1.6
	local base = lerp(plain, scrub, scrubM)
	base = lerp(base, dunes, desertM)
	base = lerp(base, steppe, steppeM * (1 - desertM * 0.7))
	base += forestM * (6 + 30 * max(0, n(x, z, 110, 0.37) + 0.35))
	local h = base

	-- 쇄천봉: 깎아지른 능선이 있는 큰 봉우리
	local peak = Land.PEAK
	local dP = dist(x, z, peak.x, peak.z)
	if dP < peak.radius then
		local u = 1 - dP / peak.radius
		local ridged = clamp01(1 - abs(n(x, z, 90, 0.51)) * 2.4)
		h += peak.height * u ^ 1.7 + 55 * ridged * 4 * u * (1 - u)
	end
	local dK = dist(x, z, Land.KNOLL.x, Land.KNOLL.z)
	if dK < 46 then
		h = max(h, lerp(h + 30, h, smooth(26, 46, dK)))
	end
	if dP < 50 then -- 꼭대기 너럭바위
		h = lerp(peak.height, h, smooth(30, 50, dP))
	end
	local dG = dist(x, z, Land.TARN.x, Land.TARN.z)
	if dG < 60 then
		h = lerp(150, h, smooth(36, 60, dG))
	end
	for _, other in Land.PEAKS do
		local d = dist(x, z, other[1], other[2])
		if d < other[4] then
			local u = 1 - d / other[4]
			local ridged = clamp01(1 - abs(n(x, z, 80, other[5])) * 2.4)
			h = max(h, base + other[3] * u ^ 1.6 + 40 * ridged * 4 * u * (1 - u))
		end
	end
	-- 서천 설원: 서쪽 끝의 높은 눈벌
	local edge = snowEdge(z)
	local westM = smooth(edge + 50, edge - 60, x) * (1 - smooth(330, 450, z)) * (1 - smooth(-620, -760, z))
	h = max(h, westM * (118 + 8 * n(x, z, 90, 0.6) + 4 * n(x, z, 25, 0.64)))

	-- 북방 대초원: 호수와 현무 언덕
	local lake = Land.LAKE_N
	local dL = dist(x, z, lake.x, lake.z)
	if dL < lake.radius + 40 then
		h = min(h, lerp(4, h, smooth(lake.radius - 10, lake.radius + 40, dL)))
	end
	local dT = dist(x, z, Land.TORTOISE.x, Land.TORTOISE.z)
	if dT < 80 then
		h = max(h, lerp(base + 22, h, smooth(22, 80, dT)))
	end

	-- 화구산: 가운데가 꺼진 불의 산
	local dV = dist(x, z, Land.VOLCANO.x, Land.VOLCANO.z)
	if dV < 230 then
		local cone = if dV >= 55 then 160 * ((230 - dV) / 175) ^ 1.25 else 125 + 35 * smooth(35, 55, dV)
		h = max(h, cone + 4 * n(x, z, 30, 1.3))
	end

	-- 답천사막: 폐허 광장, 마른 수로, 오아시스, 동쪽 바위
	local dR = dist(x, z, Land.RUINS.x, Land.RUINS.z)
	if dR < 100 then
		h = lerp(Land.RUINS.height, h, smooth(62, 100, dR))
	end
	if x > 560 then
		for _, canal in CANALS do
			local d = segDist(x, z, canal[1], canal[2], canal[3], canal[4])
			if d < 10 then
				h -= 5 * (1 - smooth(4, 10, d))
			end
		end
	end
	local dO = dist(x, z, Land.OASIS.x, Land.OASIS.z)
	if dO < 70 then
		h = lerp(18, h, smooth(30, 70, dO))
	end
	if dO < 22 then
		h = lerp(12, 18, smooth(14, 22, dO))
	end
	local dE = dist(x, z, Land.EAST_ROCK.x, Land.EAST_ROCK.z)
	if dE < 60 then
		h = lerp(30, h, smooth(30, 60, dE))
	end
	-- 답천대: 꼭대기가 평평한 탁상 바위, 둘레를 감아 오르는 비탈길
	local mesa = Land.MESA
	local dM = dist(x, z, mesa.x, mesa.z)
	if dM < 100 then
		h = max(h, lerp(mesa.height, h, smooth(72, 92, dM)))
		if dM >= 72 and dM < 90 then
			local theta = math.deg(atan2(z - mesa.z, x - mesa.x)) % 360
			if theta >= 150 and theta <= 280 then
				h = lerp(26, mesa.height, (theta - 150) / 130)
			end
		end
	end

	-- 벽라국: 붉은 협곡과 탁상 바위
	if x > 200 and x < 640 and z > 60 and z < 680 then
		local dc = polyDist(x, z, Land.CANYON)
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
	local town = Land.TOWN
	local townM = (1 - smooth(70, 100, abs(x - town.x))) * (1 - smooth(70, 100, abs(z - town.z)))
	h = lerp(h, town.height, townM)
	local dS = dist(x, z, Land.SEOAK.x, Land.SEOAK.z)
	if dS < 110 then
		h = lerp(Land.SEOAK.height, h, smooth(60, 110, dS))
	end
	h = lerp(0, h, smooth(Land.HUB.radius, 200, sqrt(x * x + z * z)))

	-- 연하
	local dr = polyDist(x, z, Land.RIVER)
	if dr < 34 then
		if dr < 9 then
			h = min(h, -5)
		else
			h = lerp(min(h, 0), h, smooth(9, 34, dr))
		end
	end
	if z > 126 then
		local dg = polyDist(x, z, Land.GORGE)
		local dpool = dist(x, z, Land.POOL.x, Land.POOL.z)
		if dg < 36 or dpool < 40 then
			local bank = -19
			local g = if dg < 8 then -24 elseif dg < 20 then bank else lerp(bank, h, smooth(20, 36, dg))
			if dpool < 22 then
				g = -30
			elseif dpool < 32 then
				g = min(g, bank)
			end
			h = min(h, g)
		end
	end

	-- 남해: 벼랑, 모래밭, 바다 밑. 동쪽(사막)은 넓은 모래 해변
	local cz = Land.coastZ(x)
	local s = z - cz
	if s > -20 then
		local desertCoast = smooth(520, 660, x)
		local cliffW = lerp(30, 110, desertCoast)
		local beach = lerp(h, -20, smooth(-10, cliffW, s))
		beach = lerp(beach, -26, smooth(cliffW + 10, cliffW + 50, s))
		local sea = lerp(-26, -52, smooth(cliffW + 60, cliffW + 420, s))
		h = if s < cliffW + 60 then min(h, beach) else sea
		local dHd = segDist(x, z, -330, cz - 10, -330, 745) -- 해룡 사당 곶
		if dHd < 60 then
			h = max(h, lerp(-10, h, smooth(40, 60, dHd)))
		end
		local isle = Land.SOUTH_ISLE
		local dI = dist(x, z, isle.x, isle.z)
		if dI < 85 then
			h = max(h, lerp(-6 + 3 * n(x, z, 25, 1.7), h, smooth(55, 85, dI)))
		end
		local way = Land.CAUSEWAY
		local dC = segDist(x, z, way[1][1], way[1][2], way[2][1], way[2][2])
		if dC < 14 then
			h = max(h, lerp(-21, h, smooth(7, 14, dC)))
		end
	end
	return h
end

-- 깎아 낸 길의 꼭짓점 높이를 땅에서 채운다
for _, points in BENCHES do
	for _, point in points do
		if point[3] == 0 then
			point[3] = ground(point[1], point[2])
		end
	end
end

-- 땅 높이 (지형 겉면)
function Land.height(x: number, z: number): number
	local h = ground(x, z)
	for _, points in BENCHES do
		local d, y = polyDist(x, z, points)
		if d < 14 then
			h = lerp(y, h, smooth(5, 14, d))
		end
	end
	return h
end

-- 등선향: 이 기둥에 뜬 섬이 있으면 밑면과 윗면 높이
function Land.island(x: number, z: number): (number?, number?)
	local isle = Land.ISLAND
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
	local top = 316 + 10 * n(x, z, 70, 2.3) - 24 * smooth(0.75, 1, t)
	local bottom = 296 - 140 * (1 - t) ^ 1.5 + 10 * n(x, z, 40, 2.5)
	if bottom >= top - 2 then
		return nil, nil
	end
	return bottom, top
end

-- 맵 위에 무엇을 놓을 높이: 섬 위면 섬 윗면, 아니면 땅
function Land.surface(x: number, z: number): number
	local _, top = Land.island(x, z)
	return top or Land.height(x, z)
end

-- 이 기둥의 수면 (물이 없으면 nil)
function Land.water(x: number, z: number, h: number): number?
	if z > Land.coastZ(x) - 40 and h < Land.SEA then
		return Land.SEA
	end
	if h < -1 and z <= 128 and polyDist(x, z, Land.RIVER) < 14 then
		return -1
	end
	if z > 126 and h < -20 then
		if polyDist(x, z, Land.GORGE) < 10 or dist(x, z, Land.POOL.x, Land.POOL.z) < 24 then
			return -20
		end
	end
	if h < 16 and dist(x, z, Land.OASIS.x, Land.OASIS.z) < 18 then
		return 16
	end
	if h < 9 and dist(x, z, Land.LAKE_N.x, Land.LAKE_N.z) < Land.LAKE_N.radius + 10 then
		return 9
	end
	return nil
end

-- 재질 ---------------------------------------------------------------------------------

local function nearRoad(x: number, z: number, width: number): boolean
	for _, road in Land.ROADS do
		if polyDist(x, z, road) < width then
			return true
		end
	end
	if polyDist(x, z, Land.PEAK_TRAIL) < width or polyDist(x, z, Land.WEST_TRAIL) < width then
		return true
	end
	return false
end

-- 겉 재질과 속 재질
local function materials(x: number, z: number, h: number, slope: number): (string, string)
	local scrubM, desertM, steppeM, forestM = masks(x, z)
	local wiggle = 30 * n(x, z, 60, 3.1)
	-- 바다와 바닷가
	local s = z - Land.coastZ(x)
	if s > -30 and h < -6 then
		if h < Land.SEA - 6 then
			return (if h < -40 then "Mud" else "Sand"), "Rock"
		end
		return (if slope > 1.1 then "Slate" else "Sand"), "Rock"
	end
	-- 강바닥과 협곡
	if h < -2 and (polyDist(x, z, Land.RIVER) < 30 or (z > 126 and polyDist(x, z, Land.GORGE) < 40)) then
		return (if slope > 0.9 then "Slate" else "Mud"), "Rock"
	end
	-- 화구산
	local dV = dist(x, z, Land.VOLCANO.x, Land.VOLCANO.z)
	if dV < 220 + wiggle * 0.5 and h > 14 then
		if dV < 40 then
			return "CrackedLava", "Basalt"
		end
		local streak = abs(n(x, z, 40, 3.3)) < 0.06 and dV < 180
		return (if streak then "CrackedLava" else "Basalt"), "Basalt"
	end
	-- 쇄천봉과 서천 설원
	local snowLine = 300 + wiggle
	if h > snowLine or (x < snowEdge(z) + 20 and h > 100) then
		return (if slope > 1.3 then "Glacier" else "Snow"), "Rock"
	end
	if dist(x, z, Land.TARN.x, Land.TARN.z) < 38 and h > 140 then
		return "Ice", "Rock"
	end
	if h > 90 + wiggle and x < -400 then
		return (if slope > 0.8 then "Rock" else "Slate"), "Rock"
	end
	if slope > 0.9 and x < -400 then
		return "Rock", "Rock"
	end
	-- 길
	if h > -2 and desertM < 0.5 and nearRoad(x, z, 4) then
		return "Cobblestone", "Rock"
	end
	-- 답천사막
	if desertM > 0.5 then
		if dist(x, z, Land.RUINS.x, Land.RUINS.z) < 64 then
			return "Pavement", "Sandstone"
		end
		if dist(x, z, Land.OASIS.x, Land.OASIS.z) < 40 then
			return "Grass", "Sandstone"
		end
		if dist(x, z, Land.MESA.x, Land.MESA.z) < 94 or slope > 0.7 then
			return "Sandstone", "Sandstone"
		end
		return "Sand", "Sandstone"
	end
	-- 벽라국: 붉은 흙과 사암 벼랑
	if scrubM > 0.5 then
		if slope > 0.8 or (z > 60 and polyDist(x, z, Land.CANYON) < 34) then
			return "Sandstone", "Sandstone"
		end
		return "Ground", "Rock"
	end
	-- 영초숲
	if forestM > 0.4 then
		return (if slope > 0.8 then "Rock" else "LeafyGrass"), "Rock"
	end
	if steppeM > 0.5 and dist(x, z, Land.LAKE_N.x, Land.LAKE_N.z) < Land.LAKE_N.radius + 6 then
		return "Mud", "Rock"
	end
	if dist(x, z, Land.OASIS.x, Land.OASIS.z) < 40 then
		return "Grass", "Sandstone"
	end
	return (if slope > 1 then "Rock" else "Grass"), "Rock"
end

-- 지형 칸 만들기 ------------------------------------------------------------------------

export type Column = {
	ground: number,
	surface: string,
	under: string,
	water: number?,
	islandBottom: number?,
	islandTop: number?,
	top: number, -- 이 기둥에서 가장 높은 지형
}

-- 기둥 하나 (x, z 는 4스터드 칸의 가운데)
function Land.column(x: number, z: number): Column
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
		top = max(h, water or -math.huge, top or -math.huge),
	}
end

-- 기둥의 칸을 아래(bottom)부터 ny 칸 낸다. emit(칸 번호(0부터), 재질 이름, 차오름 0~1).
-- 빈 칸(공기)은 내지 않는다.
--
-- Roblox 지형은 고체 칸의 겉면을 칸 경계보다 반 칸(2스터드) 바깥에 그린다 (엔진에서 재 보면 꽉 찬 칸
-- 4개 높이의 덩어리가 위아래로 2스터드씩 부풀어 있다). 물은 그렇지 않다. 그래서 고체의 위 겉면은 2 낮춰,
-- 아래 겉면(섬 밑)은 2 올려 칸을 채운다. 그러면 그려지는 겉면이 Land.height 와 맞는다.
local SKIN = 2
function Land.cells(column: Column, bottom: number, ny: number, emit: (number, string, number) -> ())
	local g = column.ground - SKIN
	local water = column.water
	local ib = column.islandBottom
	local it = column.islandTop
	for b = 0, ny - 1 do
		local y0 = bottom + b * 4
		local solid = clamp01((g - y0) / 4)
		-- 물 밑에서는 땅 칸이 반만 차면 물과 한 칸에 섞일 수 없어 빈틈이 생긴다. 꽉 채우거나 물로 둔다
		if water and y0 + 4 <= water and solid > 0 and solid < 1 then
			solid = if solid >= 0.5 then 1 else 0
		end
		if solid > 0 then
			emit(b, if g - y0 > 10 then column.under else column.surface, solid)
		elseif ib and it and y0 + 4 > ib + SKIN and y0 < it - SKIN then
			local occupancy = min(clamp01((it - SKIN - y0) / 4), clamp01((y0 + 4 - ib - SKIN) / 4))
			if occupancy > 0 then
				local fromTop = it - y0
				local name = if fromTop < 8
					then (if it < 300 then "Rock" else "LeafyGrass")
					elseif y0 < ib + 30 then "Basalt"
					else "Slate"
				emit(b, name, occupancy)
			end
		elseif water and y0 < water then
			emit(b, "Water", clamp01((water - y0) / 4))
		elseif y0 > column.top then
			break
		end
	end
end

-- 재질 색, 물빛, 구름. 지형 인스턴스에 한 번 (굽는 곳과 서버 둘 다에서 쓴다)
function Land.decorate(terrain: any)
	local colors = {
		Sand = { 214, 174, 112 },
		Sandstone = { 190, 120, 78 },
		Ground = { 156, 118, 80 },
		Basalt = { 52, 48, 48 },
		CrackedLava = { 232, 90, 40 },
		Snow = { 240, 244, 250 },
		Glacier = { 170, 210, 235 },
		Slate = { 96, 104, 112 },
		LeafyGrass = { 70, 112, 60 },
		Grass = { 98, 140, 74 },
		Mud = { 92, 74, 58 },
		Cobblestone = { 132, 126, 116 },
		Pavement = { 168, 150, 120 },
		Rock = { 112, 108, 104 },
		Ice = { 180, 220, 240 },
	}
	for name, rgb in colors do
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
