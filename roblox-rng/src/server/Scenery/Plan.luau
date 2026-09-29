--!strict
-- 주변 풍경 배치 계획(순수 계산: Instance 없이 숫자 표만 만듦). Scenery/init.luau 가 이 표대로 파트·지형을 만듭니다.
-- 섬 모양(해안선·땅 높이·물가 바위·먼 작은 섬)은 Scenery/Island 가 정하고, 여기서는 그 위에 무엇을 둘지 정합니다.
--
-- 구역(광장 중심에서의 거리 r):
--   r 62~115    안쪽 잔디: 산책로 고리(r 84), 부지 길 양옆 산울타리, 길 입구 덤불, 틈 앞 둥근 꽃밭·벤치, 작은 꽃나무
--   r 115~205   이웃 부지 사이 쐐기 틈 8곳: 틈마다 주제가 다른 정원(분수 광장/꽃 정원/과수원/연못과 다리/
--               소풍 잔디/바위 정원/토피어리 길/정자) + 가운데 오솔길(정원마다 재질이 다름)
--   r 205~212   바깥 산책로 고리. 부지 뒤마다 벤치 + 정원등 + 양옆 산울타리
--   212~풀밭 끝  숲띠: 부지 뒤 양옆 숲 무리(큰 나무 가운데 + 둘레 작은 나무, 가끔 분홍 꽃나무 무리) + 빈터 바위,
--               숲 가장자리 덤불, 모래 쪽은 야자수
--   모래사장    등대(곶 바위 위), 부두(T자 끝 + 구명 튜브 + 매어 둔 배), 파라솔·선베드 묶음, 간식 가게, 모래성, 구조대 망루,
--               야자수 무리(2~3 그루씩)
--   바다        돛단배, 수영 구역 부표 줄, 먼 작은 섬(지형) 위 야자수
-- 모든 장식은 ParkLayout.blocked(부지·간판·길·광장)와 산책로를 비켜 가고, 서로 겹치지 않게 놓습니다.
-- 난수는 구역마다 고정 시드(Rng)라서 한 구역을 고쳐도 다른 구역 배치는 그대로입니다.

local Island = require(script.Parent.Island)
local ParkLayout = require(script.Parent.Parent.ParkLayout)
local Rng = require(script.Parent.Rng)

type Rng = Rng.Rng

local Plan = {}

local TAU = math.pi * 2
local WATER = Island.WATER_LEVEL

-- 조절 값 ---------------------------------------------------------------------
local T = {
	SEED = 8128,

	-- 산책로. 고리는 짧은 곧은 판 Segments 개(이음매마다 조금만 꺾여서 둥글게 보임).
	-- 이웃 판끼리 윗면 높이를 0.05 씩 번갈아(겹치는 모서리가 같은 높이에서 깜빡이지 않게).
	-- 안쪽 고리는 원이 아니라 느린 물결 셋을 겹친 구불구불한 고리(반지름 Radius ± Wobble: 약 71~95,
	-- 광장 둘레 나무 고리(62)와 부지 입구 간판 자리(104) 사이). 바깥 고리는 부지 뒤 좁은 자리라 원
	-- 재질: 안쪽은 밝은 돌길, 바깥(숲띠 속)은 짙은 모래색 자갈길(흰 원이 눈에 띄지 않게)
	INNER_RING = { Radius = 82, Width = 7, Segments = 80, Wobble = 15, Material = "Cobblestone" },
	OUTER_RING = {
		Radius = 208.5,
		Width = 7,
		Segments = 96,
		Wobble = 0,
		Material = "Pebble",
		Color = { 196, 174, 136 },
	},
	RING_TOP = 0.15, -- 고리 윗면(홀수 번째 판은 0.1). 부지 길(0.2)보다 낮아서 겹치는 곳은 부지 길이 보임
	TRAIL_TOP = 0.18, -- 정원 오솔길 윗면(고리 위로 살짝 올라탐)
	DISC_TOP = 0.12, -- 분수 광장 원판 윗면(오솔길 끝이 그 위로 올라탐)
	ROUTE_HEIGHT = 0.3, -- 산책로 판 두께
	WALKWAY_MATERIAL = "Cobblestone",
	TRAIL_WIDTH = 5,
	ROUTE_MARGIN = 1.5, -- 산책로 양옆 여유(벤치·정원등은 따로 더 가깝게)
	EDGE_MARGIN = 2, -- 풀밭 끝(모래 시작) 안쪽 여유
	SPACING = 0.6, -- 장식끼리 최소 틈
	CORRIDOR_HALF_WIDTH = 10, -- 광장에서 틈 방향으로 바다가 보이게 큰 나무를 두지 않는 반폭(바깥 고리 너머)

	-- 틈 정원 주제(ParkLayout.gapAngles() 순서: 270도 = 지구본 뒤, 315도(등대 쪽), 0도, ... 225도)
	GARDEN_THEMES = { "Fountain", "Flowers", "Orchard", "Pond", "Picnic", "Rockery", "Topiary", "Gazebo" },

	-- 숲띠
	BELT = {
		GroveRadius = 14, -- 숲 무리 반지름
		BlossomGroves = 0.25, -- 큰 무리가 꽃나무(분홍) 무리일 확률
		Trees = 76, -- 넓은잎나무 최대 수(보통 무리 크기로 정해짐)
		Palms = 10, -- 모래 쪽 야자수 최대 수
		TreeScale = { 1.05, 1.45 },
		PalmScale = { 1.05, 1.35 },
		BushChance = 0.3, -- 나무마다 옆에 덤불을 둘 확률
		Rocks = 7,
		-- 풀밭 끝(모래 시작) 덤불 띠: FringeStep 스터드마다 한 자리, 띠 밀도(각도 물결)가 FringeCut 보다 큰 곳에만
		-- (덤불 무리와 트인 곳이 번갈아: 고르게 흩뿌리지 않음)
		FringeStep = 11,
		FringeCut = 0.2,
	},

	BEACH = {
		PalmGroves = 13, -- 모래사장 야자수 무리 수(섬 둘레에 고르지 않은 간격으로, 무리마다 1~3 그루)
		-- 파라솔 묶음 자리(도)
		SetZones = {
			{ From = 163, To = 184, Count = 4 },
			{ From = 21, To = 37, Count = 3 },
			{ From = 212, To = 228, Count = 3 },
		},
		Surfboards = { 199, 44, 188 }, -- 서핑보드 거치대(도, 풀밭 끝 가까운 모래)
		-- 모래 오솔길(지형 칠하기): 바깥 산책로에서 모래사장으로 굽이쳐 내려감(도). 등대 쪽은 등대까지
		Footpaths = { 315, 135, 173.5, 38, 217.3 },
		FootpathHalf = 3,
		Driftwood = 6, -- 떠밀려 온 나무(물가 가까운 모래)
		KioskAngle = 142,
		LifeguardAngle = 191, -- 구조대 망루(수영 구역 부표 옆 모래사장)
		PierLength = 48, -- 물가에서 바다 쪽으로(부두 T자 끝까지)
		PierWidth = 5,
		PierHead = { Width = 13, Depth = 7 }, -- T자 끝 판
		DeckTop = 0.4, -- 부두 윗면
		Buoys = { From = 166, To = 198, Count = 7, Offset = 24 }, -- 수영 구역 부표(물가에서 바다 쪽 거리)
	},

	SEA = {
		Boats = { -- Scale = 크기 배율(멀리 있는 배는 크게 해서 수평선에서도 보이게)
			{ Angle = 172, Offset = 55, Heading = 70, Scale = 1.2 },
			{ Angle = 24, Offset = 70, Heading = 130, Scale = 1.4 },
			{ Angle = 252, Offset = 120, Heading = -20, Scale = 1.8 },
			{ Angle = 300, Offset = 210, Heading = 35, Scale = 2.2 },
			{ Angle = 95, Offset = 170, Heading = 170, Scale = 2 },
		},
	},

	-- 보이지 않는 벽: 물가 + Offset 을 Step 도 간격으로 짚은 뒤, 곧게 펴도 Tolerance 이상 안 벗어나는 점은 뺌
	WALL = { Step = 1, Tolerance = 1.2, Offset = 3, Height = 60, Bottom = -14, PierGap = 0.4 },
}
Plan.Tuning = T

-- 장식 하나. Kind 별 모양은 Scenery/Props.luau
export type Item = {
	Kind: string,
	Zone: string, -- 파트 개수를 셀 때 묶는 구역
	X: number,
	Y: number, -- 서 있는 땅의 윗면 높이(비탈이면 발밑 가장 낮은 곳)
	Z: number,
	Radius: number, -- 바닥 반지름(비켜 가기·간격)
	Scale: number,
	Turn: number, -- 방향(라디안). (cos, sin) = 앞(벤치·배)이나 기우는 쪽(나무)
	Tint: number, -- 0~1 색·모양 변화
	Style: number, -- 종류 안의 모양/색 번호
	Height: number, -- 산울타리·부두·다리: 길이
	Layer: string, -- "Solid"(서로 안 겹침) / "Free"(검사 안 함)
}

-- 산책로 판: 고리(곧은 판 Segments 개), 곧은 길 조각, 둥근 광장 원판
-- 고리: Points = 가운데 선 꼭짓점(닫힌 꺾은선, 각도가 커지는 순서), 판은 꼭짓점 사이마다 하나
export type Ring = {
	Radius: number,
	Width: number,
	Segments: number,
	Top: number,
	Material: string,
	Color: { number }?, -- 없으면 재질 기본색(Scenery/init 의 ROUTE_COLORS)
	Points: { { number } },
}
export type Segment = { X1: number, Z1: number, X2: number, Z2: number, Width: number, Top: number, Material: string }
export type Disc = { X: number, Z: number, R: number, Top: number, Material: string }

export type Result = {
	Items: { Item },
	Rings: { Ring },
	Trails: { Segment },
	Discs: { Disc },
	Wall: { Points: { { number } }, Height: number, Bottom: number }, -- 닫힌 꺾은선(안쪽 면이 선 위)
	Paint: { Island.Shape }, -- 지형 윗면 칠하기
	Ponds: { Island.Pond }, -- 지형 연못(물 윗면 y = 0)
	Skipped: { [string]: number }, -- 자리가 없어 못 놓은 장식 수("구역/종류" 별)
}

type Circle = { X: number, Z: number, R: number }
type Capsule = { X1: number, Z1: number, X2: number, Z2: number, R: number }

type Ctx = {
	Items: { Item },
	Cells: { [number]: { Item } },
	Big: { Item },
	Keep: { Circle }, -- 아무것도 두지 않을 원(부두 발판, 바위, 연못)
	Capsules: { Capsule }, -- 산울타리처럼 긴 장식
	Paint: { Island.Shape },
	Skipped: { [string]: number },
}

-- 놓을 장식 설명. Region: "Island"(풀밭) / "Beach"(마른 모래) / "Free"
type Spec = {
	Kind: string,
	Zone: string,
	Region: string,
	X: number,
	Z: number,
	Y: number?,
	Radius: number,
	Scale: number?,
	Turn: number?,
	Tint: number?,
	Style: number?,
	Height: number?,
	Layer: string?,
	RouteMargin: number?, -- 산책로 여유를 따로(벤치·정원등)
	OnRoute: boolean?, -- 산책로 위에 일부러 두는 것(분수·정자·다리·연못 꾸밈·아치): 산책로 검사를 건너뜀
	Tall: boolean?, -- 큰 나무: 광장에서 바다가 보이는 틈 방향(시야)을 비켜 감
	Flat: number?, -- 납작한 장식: 이 반지름만큼 지형을 풀잎 없는 재질로 칠함
	Foot: number?, -- 발밑 높이를 잴 반지름(기본 min(Radius, 1.5))
}

local GAP_ANGLES = ParkLayout.gapAngles()
local FOOTPRINTS = ParkLayout.footprints()
local RINGS = { T.INNER_RING, T.OUTER_RING }

type RingTuning = {
	Radius: number,
	Width: number,
	Segments: number,
	Wobble: number,
	Material: string,
	Color: { number }?,
}

-- 고리 가운데 선의 반지름(각도 = 라디안). 물결 셋(2·3·5 번 도는)을 겹쳐서 한 바퀴 돌면 제자리, 최대 ±Wobble
local function ringRadius(ring: RingTuning, angle: number): number
	local wobble = ring.Wobble
	if wobble == 0 then
		return ring.Radius
	end
	local n = 0.5 * math.sin(2 * angle + 0.7) + 0.35 * math.sin(3 * angle + 2.1) + 0.15 * math.sin(5 * angle + 4)
	return ring.Radius + wobble * n
end
Plan.ringRadius = ringRadius

-- 고리마다 가운데 선 꼭짓점(모듈을 불러올 때 한 번)
local RING_POINTS: { { { number } } } = {}
for i, ring in RINGS do
	local points = {}
	for k = 0, ring.Segments - 1 do
		local a = k / ring.Segments * TAU
		local r = ringRadius(ring, a)
		table.insert(points, { math.cos(a) * r, math.sin(a) * r })
	end
	RING_POINTS[i] = points
end

local CELL = 24
local BIG = 12 -- 이보다 큰 장식은 격자 대신 따로 모아 둠

-- 도움 함수 -------------------------------------------------------------------

local function polar(angle: number, distance: number): (number, number)
	return math.cos(angle) * distance, math.sin(angle) * distance
end

-- angle 방향 축을 따라 along 만큼 가고, 옆(각도가 커지는 쪽이 +)으로 side 만큼 간 곳
local function onAxis(angle: number, along: number, side: number): (number, number)
	local dx, dz = math.cos(angle), math.sin(angle)
	return dx * along - dz * side, dz * along + dx * side
end

-- (x, z) 에서 (tx, tz) 를 바라보는 방향(라디안)
local function facing(x: number, z: number, tx: number, tz: number): number
	return math.atan2(tz - z, tx - x)
end

-- 선분 (x1, z1)-(x2, z2) 까지 거리
local function segmentDistance(x: number, z: number, x1: number, z1: number, x2: number, z2: number): number
	local vx, vz = x2 - x1, z2 - z1
	local length2 = vx * vx + vz * vz
	local t = if length2 > 0 then math.clamp(((x - x1) * vx + (z - z1) * vz) / length2, 0, 1) else 0
	local px, pz = x1 + vx * t - x, z1 + vz * t - z
	return math.sqrt(px * px + pz * pz)
end

-- 고리 index 가운데 선까지 거리(각도로 가까운 판 셋만 봄)
local function ringDistance(index: number, x: number, z: number): number
	local points = RING_POINTS[index]
	local n = #points
	local k = math.floor((math.atan2(z, x) % TAU) / TAU * n)
	local best = math.huge
	for d = -1, 1 do
		local i = (k + d) % n
		local p, q = points[i + 1], points[(i + 1) % n + 1]
		best = math.min(best, segmentDistance(x, z, p[1], p[2], q[1], q[2]))
	end
	return best
end

-- 정원 오솔길 모양 -------------------------------------------------------------------
-- 오솔길은 틈 가운데 선(안쪽 고리 r 84 → 바깥 고리 r 208.5). Cut = 오솔길을 끊는 구간(rho),
-- Disc = 그 자리의 광장 원판(Build 면 산책로처럼 만듦, 아니면 장식이 바닥을 만듦), Bridge = 연못 위 다리
-- Curve = 오솔길이 넓은 곳(rho 140 너머)에서 옆으로 굽이치는 폭(0 이면 곧게). 한 조각이 길면 S 자, 짧으면 한 번 휨
type ThemeRoute = {
	Material: string,
	Curve: number?,
	Cut: { number }?,
	Disc: { Rho: number, R: number, Top: number?, Material: string?, Build: boolean }?,
	Bridge: { From: number, To: number, Width: number }?,
	Pond: { Rho: number, R: number, Depth: number }?,
}
local THEME_ROUTES: { [string]: ThemeRoute } = {
	Fountain = {
		Material = "Cobblestone",
		Cut = { 158, 182 },
		Disc = { Rho = 170, R = 13, Build = true },
	},
	Flowers = { Material = "Brick", Curve = 6 },
	Orchard = { Material = "Pebble", Curve = 7 },
	Pond = {
		Material = "Cobblestone",
		Cut = { 155, 185 },
		Bridge = { From = 153, To = 187, Width = 4.6 },
		Pond = { Rho = 170, R = 11.5, Depth = 3.5 },
	},
	Picnic = { Material = "Pebble", Curve = 7 },
	Rockery = { Material = "Slate", Curve = 6 },
	Topiary = { Material = "Brick" },
	Gazebo = {
		Material = "Cobblestone",
		Curve = 4,
		Cut = { 170, 182 },
		Disc = { Rho = 176, R = 7.5, Top = 0.4, Material = "WoodPlanks", Build = false },
	},
}

local CURVE_FROM = 140 -- 틈이 넓어지는 곳(여기부터 오솔길이 굽이침)

-- 오솔길 한 조각(rho a → b)을 곧은 판 여러 개로. curve ~= 0 이면 CURVE_FROM 너머에서 옆으로 굽이침(양 끝은 가운데 선).
-- 이음매에서 꺾이는 만큼 판을 늘려 바깥 틈을 덮고, 이웃 판끼리 윗면을 0.04 씩 번갈아(겹친 곳이 깜빡이지 않게)
local function trailPieces(angle: number, a: number, b: number, curve: number, material: string): { Segment }
	local points: { { number } } = {}
	local start = math.max(a, CURVE_FROM)
	if curve == 0 or b - start < 12 then
		points = { { a, 0 }, { b, 0 } }
	else
		if start > a then
			table.insert(points, { a, 0 })
		end
		local waves = if b - start > 45 then 2 else 1 -- 길면 S 자
		local steps = math.max(4, math.ceil((b - start) / 4))
		for k = 0, steps do
			local u = k / steps
			local side = curve * math.sin(math.pi * waves * u) * (if waves == 2 then 1 else 0.8)
			table.insert(points, { start + (b - start) * u, side })
		end
	end
	local world: { { number } } = {}
	for _, p in points do
		local x, z = onAxis(angle, p[1], p[2])
		table.insert(world, { x, z })
	end
	local half = T.TRAIL_WIDTH / 2
	local function unit(p: { number }, q: { number }): (number, number)
		local dx, dz = q[1] - p[1], q[2] - p[2]
		local length = math.sqrt(dx * dx + dz * dz)
		return dx / length, dz / length
	end
	local function bend(k: number): number
		if k <= 1 or k >= #world then
			return 0
		end
		local ux, uz = unit(world[k - 1], world[k])
		local vx, vz = unit(world[k], world[k + 1])
		return half * math.tan(math.acos(math.clamp(ux * vx + uz * vz, -1, 1)) / 2) + 0.05
	end
	local list: { Segment } = {}
	for k = 1, #world - 1 do
		local p, q = world[k], world[k + 1]
		local dx, dz = unit(p, q)
		local e1, e2 = bend(k), bend(k + 1)
		table.insert(list, {
			X1 = p[1] - dx * e1,
			Z1 = p[2] - dz * e1,
			X2 = q[1] + dx * e2,
			Z2 = q[2] + dz * e2,
			Width = T.TRAIL_WIDTH,
			Top = T.TRAIL_TOP + (k % 2) * 0.04,
			Material = material,
		})
	end
	return list
end

-- 산책로 판정용 모양(모듈을 불러올 때 한 번 계산): 오솔길 조각·다리, 광장 원판
local ROUTE_SEGMENTS: { Segment } = {}
local ROUTE_DISCS: { Disc } = {}
local TRAILS: { Segment } = {}
local DISCS: { Disc } = {}
local PONDS: { Island.Pond } = {}
local GAP_PONDS: { [number]: Island.Pond } = {} -- 틈 번호 → 그 틈의 연못
for j, angle in GAP_ANGLES do
	local theme = T.GARDEN_THEMES[(j - 1) % #T.GARDEN_THEMES + 1]
	local route = THEME_ROUTES[theme] or { Material = T.WALKWAY_MATERIAL }
	local from, to = ringRadius(T.INNER_RING, angle), ringRadius(T.OUTER_RING, angle)
	local pieces = { { from, to } }
	local cut = route.Cut
	if cut then
		pieces = { { from, cut[1] }, { cut[2], to } }
	end
	-- 정원 좌우 뒤집기(gardens() 의 첫 난수와 같은 값): 굽이치는 쪽도 정원 장식과 같이 뒤집힘
	local m = Rng.new(T.SEED + 200 + j):Sign()
	for _, piece in pieces do
		for _, trail in trailPieces(angle, piece[1], piece[2], (route.Curve or 0) * m, route.Material) do
			table.insert(TRAILS, trail)
			table.insert(ROUTE_SEGMENTS, trail)
		end
	end
	local disc = route.Disc
	if disc then
		local x, z = polar(angle, disc.Rho)
		local entry: Disc = {
			X = x,
			Z = z,
			R = disc.R,
			Top = disc.Top or T.DISC_TOP,
			Material = disc.Material or route.Material,
		}
		table.insert(ROUTE_DISCS, entry)
		if disc.Build then
			table.insert(DISCS, entry)
		end
	end
	local bridge = route.Bridge
	if bridge then
		local x1, z1 = polar(angle, bridge.From)
		local x2, z2 = polar(angle, bridge.To)
		table.insert(
			ROUTE_SEGMENTS,
			{ X1 = x1, Z1 = z1, X2 = x2, Z2 = z2, Width = bridge.Width, Top = 0.6, Material = "WoodPlanks" }
		)
	end
	local pond = route.Pond
	if pond then
		local x, z = polar(angle, pond.Rho)
		local entry: Island.Pond = { X = x, Z = z, R = pond.R, Depth = pond.Depth, Seed = 40 + j * 1.7 }
		table.insert(PONDS, entry)
		GAP_PONDS[j] = entry
	end
end

-- 산책로(고리 둘, 정원 오솔길·다리, 광장 원판) 위이거나 너무 가까운지. margin 기본은 ROUTE_MARGIN
function Plan.onRoute(x: number, z: number, pad: number?, margin: number?): boolean
	local m = (pad or 0) + (margin or T.ROUTE_MARGIN)
	for i, ring in RINGS do
		if ringDistance(i, x, z) <= ring.Width / 2 + m then
			return true
		end
	end
	for _, segment in ROUTE_SEGMENTS do
		if segmentDistance(x, z, segment.X1, segment.Z1, segment.X2, segment.Z2) <= segment.Width / 2 + m then
			return true
		end
	end
	for _, disc in ROUTE_DISCS do
		local dx, dz = x - disc.X, z - disc.Z
		local reach = disc.R + m
		if reach > 0 and dx * dx + dz * dz <= reach * reach then
			return true
		end
	end
	return false
end

-- 풀밭 자리 검사: 광장·부지·간판·길(ParkLayout) + 산책로 + 풀밭 끝(모래 시작). 막히면 true 와 이유
function Plan.islandBlocked(x: number, z: number, pad: number?, routeMargin: number?): (boolean, string?)
	local p = pad or 0
	local hit, why = ParkLayout.blocked(x, z, p)
	if hit then
		return true, why
	end
	if Plan.onRoute(x, z, p, routeMargin) then
		return true, "route"
	end
	if math.sqrt(x * x + z * z) + p > Island.grassEdge(math.atan2(z, x)) - T.EDGE_MARGIN then
		return true, "edge"
	end
	return false, nil
end

-- 바깥 고리 너머, 틈 방향 시야 안인지(큰 나무 금지)
local function inCorridor(x: number, z: number, pad: number): boolean
	for _, angle in GAP_ANGLES do
		local dx, dz = math.cos(angle), math.sin(angle)
		local along = x * dx + z * dz
		local side = z * dx - x * dz
		if along > T.OUTER_RING.Radius and math.abs(side) <= T.CORRIDOR_HALF_WIDTH + pad then
			return true
		end
	end
	return false
end

-- 배치 ---------------------------------------------------------------------------

local function cellKey(cx: number, cz: number): number
	return (cx + 5000) * 10000 + (cz + 5000)
end

local function overlaps(ctx: Ctx, x: number, z: number, r: number, gap: number): boolean
	for _, other in ctx.Big do
		local limit = r + other.Radius + gap
		if (other.X - x) ^ 2 + (other.Z - z) ^ 2 < limit * limit then
			return true
		end
	end
	local reach = r + BIG + gap
	for cx = math.floor((x - reach) / CELL), math.floor((x + reach) / CELL) do
		for cz = math.floor((z - reach) / CELL), math.floor((z + reach) / CELL) do
			local list = ctx.Cells[cellKey(cx, cz)]
			if list then
				for _, other in list do
					local limit = r + other.Radius + gap
					if (other.X - x) ^ 2 + (other.Z - z) ^ 2 < limit * limit then
						return true
					end
				end
			end
		end
	end
	for _, capsule in ctx.Capsules do
		if segmentDistance(x, z, capsule.X1, capsule.Z1, capsule.X2, capsule.Z2) < r + capsule.R + gap then
			return true
		end
	end
	return false
end

-- 마른 모래 위인지: 가운데와 둘레 네 곳이 모두 물 위 + 풀밭 끝 바깥
local function onBeach(x: number, z: number, r: number): boolean
	local distance = math.sqrt(x * x + z * z)
	local angle = math.atan2(z, x)
	if distance - r < Island.grassEdge(angle) + 0.5 then
		return false
	end
	if distance + r > Island.coastRadius(angle) - 1.5 then
		return false
	end
	for k = 0, 3 do
		local a = k / 4 * TAU
		if not Island.isDry(x + math.cos(a) * r, z + math.sin(a) * r) then
			return false
		end
	end
	return true
end

local function fits(ctx: Ctx, spec: Spec, x: number, z: number): boolean
	local r = spec.Radius
	local region = spec.Region
	if region == "Island" then
		if spec.OnRoute then
			if ParkLayout.blocked(x, z, r) then
				return false
			end
		elseif Plan.islandBlocked(x, z, r, spec.RouteMargin) then
			return false
		end
	elseif region == "Beach" then
		if not onBeach(x, z, r) then
			return false
		end
	end
	if spec.Tall and inCorridor(x, z, r) then
		return false
	end
	for _, circle in ctx.Keep do
		local limit = r + circle.R
		if (circle.X - x) ^ 2 + (circle.Z - z) ^ 2 < limit * limit then
			return false
		end
	end
	if (spec.Layer or "Solid") == "Solid" then
		return not overlaps(ctx, x, z, r, T.SPACING)
	end
	return true
end

local function insert(ctx: Ctx, item: Item)
	table.insert(ctx.Items, item)
	if item.Layer == "Solid" then
		if item.Radius > BIG then
			table.insert(ctx.Big, item)
		else
			local key = cellKey(math.floor(item.X / CELL), math.floor(item.Z / CELL))
			local list = ctx.Cells[key]
			if not list then
				list = {}
				ctx.Cells[key] = list
			end
			table.insert(list, item)
		end
	end
end

-- 발밑 높이: 공원(평지)은 0, 그 밖은 발밑 원 안에서 가장 낮은 땅(비탈에서 뜨지 않게)
local function groundY(x: number, z: number, foot: number): number
	if x * x + z * z <= (Island.FLAT_RADIUS - foot) ^ 2 then
		return 0
	end
	return Island.lowestAround(x, z, foot)
end

-- spec 자리에 놓아 보고, 안 되면 jitter 안에서 tries 번 더 흔들어 봄. 끝내 안 되면 nil(quiet 가 아니면 Skipped 에 셈)
local function place(ctx: Ctx, rng: Rng, spec: Spec, tries: number?, jitter: number?, quiet: boolean?): Item?
	local x, z = spec.X, spec.Z
	local spread = jitter or spec.Radius
	for attempt = 0, tries or 0 do
		if attempt > 0 then
			x = spec.X + rng:NextNumber(-spread, spread)
			z = spec.Z + rng:NextNumber(-spread, spread)
		end
		if fits(ctx, spec, x, z) then
			local item: Item = {
				Kind = spec.Kind,
				Zone = spec.Zone,
				X = x,
				Y = spec.Y or groundY(x, z, spec.Foot or math.min(spec.Radius, 1.5)),
				Z = z,
				Radius = spec.Radius,
				Scale = spec.Scale or 1,
				Turn = spec.Turn or 0,
				Tint = spec.Tint or 0.5,
				Style = spec.Style or 1,
				Height = spec.Height or 0,
				Layer = spec.Layer or "Solid",
			}
			insert(ctx, item)
			if spec.Flat then
				table.insert(
					ctx.Paint,
					{ Kind = "Circle", X = x, Z = z, R = spec.Flat, Material = "LeafyGrass", Margin = 2 }
				)
			end
			return item
		end
	end
	if quiet then
		return nil
	end
	local key = spec.Zone .. "/" .. spec.Kind
	ctx.Skipped[key] = (ctx.Skipped[key] or 0) + 1
	if Plan.debugSkipped then
		table.insert(Plan.debugSkipped, spec)
	end
	return nil
end

-- 긴 장식(산울타리): (x1, z1) → (x2, z2), 굵기 반지름 r. 풀밭 검사는 양 끝과 가운데
local function placeHedge(ctx: Ctx, zone: string, x1: number, z1: number, x2: number, z2: number, style: number): Item?
	local r = 0.9
	local length = math.sqrt((x2 - x1) ^ 2 + (z2 - z1) ^ 2)
	local steps = math.max(2, math.ceil(length / 3))
	for s = 0, steps do
		local t = s / steps
		local x, z = x1 + (x2 - x1) * t, z1 + (z2 - z1) * t
		local blocked, why = Plan.islandBlocked(x, z, r, 0.5)
		if blocked or overlaps(ctx, x, z, r, 0.3) then
			ctx.Skipped[zone .. "/Hedge"] = (ctx.Skipped[zone .. "/Hedge"] or 0) + 1
			if Plan.debugSkipped then
				table.insert(Plan.debugSkipped, { Kind = "Hedge", X = x, Z = z, Why = why or "overlap" })
			end
			return nil
		end
	end
	local cx, cz = (x1 + x2) / 2, (z1 + z2) / 2
	local item: Item = {
		Kind = "Hedge",
		Zone = zone,
		X = cx,
		Y = groundY(cx, cz, length / 2),
		Z = cz,
		Radius = r,
		Scale = 1,
		Turn = math.atan2(z2 - z1, x2 - x1),
		Tint = 0.5,
		Style = style,
		Height = length,
		Layer = "Free",
	}
	insert(ctx, item)
	table.insert(ctx.Capsules, { X1 = x1, Z1 = z1, X2 = x2, Z2 = z2, R = r })
	return item
end

-- 장식 종류별 바닥 반지름(비켜 가기·간격)
local TREE_RADIUS = 2.4 -- 넓은잎나무(잎은 약 4 x Scale 까지 퍼져서 무리 지으면 살짝 겹침)
local PALM_RADIUS = 1.6
local BUSH_RADIUS = 2.2

local function treeSpec(
	zone: string,
	region: string,
	x: number,
	z: number,
	scale: number,
	style: number,
	rng: Rng
): Spec
	return {
		Kind = "Tree",
		Zone = zone,
		Region = region,
		X = x,
		Z = z,
		Radius = TREE_RADIUS * scale,
		Scale = scale,
		Turn = rng:NextNumber(0, TAU),
		Tint = rng:NextNumber(),
		Style = style,
		Tall = true,
		Foot = 1,
	}
end

local function palmSpec(zone: string, region: string, x: number, z: number, scale: number, rng: Rng): Spec
	return {
		Kind = "Palm",
		Zone = zone,
		Region = region,
		X = x,
		Z = z,
		Radius = PALM_RADIUS * scale,
		Scale = scale,
		-- 바다 쪽으로 기움
		Turn = math.atan2(z, x) + rng:NextNumber(-0.7, 0.7),
		Tint = rng:NextNumber(),
		Style = 1,
		Foot = 0.8,
	}
end

local function bushSpec(zone: string, x: number, z: number, scale: number, flowering: boolean, rng: Rng): Spec
	return {
		Kind = "Bush",
		Zone = zone,
		Region = "Island",
		X = x,
		Z = z,
		Radius = BUSH_RADIUS * scale,
		Scale = scale,
		Turn = rng:NextNumber(0, TAU),
		Tint = rng:NextNumber(),
		Style = if flowering then rng:NextInteger(2, 4) else 1, -- 2~4 = 꽃 색(분홍/하양/노랑)
	}
end

-- 안쪽 잔디(광장 ~ 부지 입구) ---------------------------------------------------------------

-- 후보 자리들을 차례로(각각 tries 번 흔들어) 놓아 봄. 모두 안 되면 첫 후보를 Skipped 에 셈
local function placeFirst(ctx: Ctx, rng: Rng, specs: { Spec }, tries: number, jitter: number): Item?
	for _, spec in specs do
		local item = place(ctx, rng, spec, tries, jitter, true)
		if item then
			return item
		end
	end
	local key = specs[1].Zone .. "/" .. specs[1].Kind
	ctx.Skipped[key] = (ctx.Skipped[key] or 0) + 1
	if Plan.debugSkipped then
		for _, spec in specs do
			table.insert(Plan.debugSkipped, spec)
		end
	end
	return nil
end

local LAWN_IN = ParkLayout.PLAZA_CLEAR + 1 -- 안쪽 잔디 시작(광장 둘레 나무 고리 바깥)

local function innerLawn(ctx: Ctx)
	local rng = Rng.new(T.SEED + 100)
	local inner = T.INNER_RING
	local half = inner.Width / 2
	local function spec(
		kind: string,
		rho: number,
		side: number,
		angle: number,
		radius: number,
		extra: { [string]: any }?
	): Spec
		local x, z = onAxis(angle, rho, side)
		local result: Spec = { Kind = kind, Zone = "Inner", Region = "Island", X = x, Z = z, Radius = radius }
		if extra then
			for key, value in extra do
				(result :: any)[key] = value
			end
		end
		return result
	end
	for j, angle in GAP_ANGLES do
		local ring = ringRadius(inner, angle)
		local inEdge, outEdge = ring - half, ring + half
		local room = inEdge - LAWN_IN -- 고리 안쪽(광장 쪽) 잔디 폭
		local s = if j % 2 == 0 then 1 else -1
		-- 벤치 + 정원등: 오솔길이 시작되는 곳. 안쪽이 넉넉하면 고리 안쪽에서 정원 쪽을, 아니면 바깥 오솔길 옆에서 광장 쪽을 봄
		local benchSpecs = {
			spec("Bench", inEdge - 4.4, 0, angle, 2.8, { Turn = angle, RouteMargin = 0.4 }),
			spec("Bench", outEdge + 4.4, s * 7.5, angle, 2.8, { Turn = angle + math.pi, RouteMargin = 0.4 }),
			spec("Bench", outEdge + 4.4, -s * 7.5, angle, 2.8, { Turn = angle + math.pi, RouteMargin = 0.4 }),
		}
		if room < 8 then
			benchSpecs = { benchSpecs[2], benchSpecs[3], benchSpecs[1] }
		end
		local benchItem = placeFirst(ctx, rng, benchSpecs, 3, 0.8)
		if benchItem then
			local rho = benchItem.X * math.cos(angle) + benchItem.Z * math.sin(angle)
			local side = benchItem.Z * math.cos(angle) - benchItem.X * math.sin(angle)
			placeFirst(ctx, rng, {
				spec("Lamp", rho, side + s * 4.2, angle, 0.6, { RouteMargin = 0.3 }),
				spec("Lamp", rho, side - s * 4.2, angle, 0.6, { RouteMargin = 0.3 }),
			}, 2, 0.6)
		end
		-- 꽃섬(꽃밭 + 뒤에 작은 꽃나무 + 덤불 둘): 고리 안쪽이 넓으면 안쪽, 아니면 바깥(오솔길 반대쪽 옆)
		local rho, side
		if room >= 13 then
			rho, side = LAWN_IN + room * 0.5, -s * 11
		else
			rho, side = outEdge + 7.5, -s * 11
		end
		local style = j % 6 + 1
		local bed = placeFirst(ctx, rng, {
			spec("FlowerBed", rho, side, angle, 3.3, { Turn = rng:NextNumber(0, TAU), Style = style, Flat = 3.3 }),
			spec(
				"FlowerBed",
				outEdge + 7.5,
				side,
				angle,
				3.3,
				{ Turn = rng:NextNumber(0, TAU), Style = style, Flat = 3.3 }
			),
		}, 4, 1.5)
		if bed then
			-- 무리: 꽃밭 뒤(광장에서 먼 쪽) 작은 꽃나무, 양옆 덤불
			local bx, bz = bed.X, bed.Z
			local out = math.atan2(bz, bx)
			local tx, tz =
				bx + math.cos(out) * 5.2 - math.sin(out) * s * 2, bz + math.sin(out) * 5.2 + math.cos(out) * s * 2
			place(
				ctx,
				rng,
				treeSpec("Inner", "Island", tx, tz, rng:NextNumber(0.72, 0.85), if j % 3 == 0 then 1 else 4, rng),
				4,
				1.2,
				true
			)
			for _, k in { -1, 1 } do
				local a = out + k * 1.9 + rng:NextNumber(-0.3, 0.3)
				local d = 3.3 + BUSH_RADIUS * 0.85 + 0.8
				place(
					ctx,
					rng,
					bushSpec(
						"Inner",
						bx + math.cos(a) * d,
						bz + math.sin(a) * d,
						rng:NextNumber(0.75, 0.95),
						k > 0,
						rng
					),
					3,
					1,
					true
				)
			end
		end
		-- 부지 입구 쪽 작은 꽃나무(틈마다 한쪽씩 번갈아)
		local ex, ez = onAxis(angle, 103 + rng:NextNumber(-1.5, 1.5), s * (12 + rng:NextNumber(-1, 1)))
		placeFirst(ctx, rng, { treeSpec("Inner", "Island", ex, ez, rng:NextNumber(0.75, 0.85), 4, rng) }, 6, 2.5)
	end
	for _, footprint in FOOTPRINTS do
		local a = footprint.Angle
		for _, s in { -1, 1 } do
			-- 길 양옆 줄: 광장 쪽 끝에 꽃 덤불 + 이어서 산울타리. 고리 안쪽(광장 ~ 고리)과 바깥(고리 ~ 부지 입구)
			-- 중 긴 쪽에. 옆으로 비킨 자리의 고리 반지름으로 잼(고리가 구불구불해서 길 가운데와 다름)
			local side = s * (ParkLayout.PATH_WIDTH / 2 + ParkLayout.PATH_MARGIN + 1)
			local ring = ringRadius(inner, a + math.atan2(side, ringRadius(inner, a)))
			local inEdge, outEdge = ring - half - 3.4, ring + half + 3.4
			local scale = rng:NextNumber(0.9, 1.05)
			local r = BUSH_RADIUS * scale
			local bushSide = s * (7.6 + r)
			local first, last
			if inEdge - LAWN_IN >= 103 - outEdge then
				first, last = LAWN_IN, inEdge
			else
				first, last = outEdge, 103
			end
			local x, z = onAxis(a, first + r + 1, bushSide)
			place(ctx, rng, bushSpec("Inner", x, z, scale, true, rng), 3, 0.5)
			local from = first + 2 * r + 4.5
			if last - from >= 7 then
				local x1, z1 = onAxis(a, from, side)
				local x2, z2 = onAxis(a, last, side)
				placeHedge(ctx, "Inner", x1, z1, x2, z2, 1)
			end
		end
	end
end

-- 틈 정원 --------------------------------------------------------------------

type Garden = {
	ctx: Ctx,
	rng: Rng,
	angle: number,
	m: number, -- 좌우 뒤집기(-1 / 1)
	pond: Island.Pond?, -- 이 틈의 지형 연못(연못 정원만)
}

-- 정원 좌표(rho = 광장 중심에서 틈 방향 거리, side = 옆, m 을 곱해서 뒤집힘)
local function at(g: Garden, rho: number, side: number): (number, number)
	return onAxis(g.angle, rho, side * g.m)
end

-- 정원 좌표에 장식 하나
local function put(g: Garden, kind: string, rho: number, side: number, radius: number, extra: { [string]: any }?): Item?
	local x, z = at(g, rho, side)
	local spec: Spec = {
		Kind = kind,
		Zone = "Gardens",
		Region = "Island",
		X = x,
		Z = z,
		Radius = radius,
		Turn = g.rng:NextNumber(0, TAU),
		Tint = g.rng:NextNumber(),
	}
	if extra then
		for key, value in extra do
			(spec :: any)[key] = value
		end
	end
	return place(g.ctx, g.rng, spec, 3, 1.5)
end

-- 넓은잎나무. style: 1 초록, 2 과일나무, 3 단풍(빨강), 4 꽃나무(분홍)
local function tree(g: Garden, rho: number, side: number, scale: number, style: number?): Item?
	local x, z = at(g, rho, side)
	local spec = treeSpec("Gardens", "Island", x, z, scale, style or 1, g.rng)
	return place(g.ctx, g.rng, spec, 3, 1.5)
end

-- (rho, side) 에 벤치를 두고 (tRho, tSide) 를 바라보게
local function bench(g: Garden, rho: number, side: number, tRho: number, tSide: number): Item?
	local x, z = at(g, rho, side)
	local tx, tz = at(g, tRho, tSide)
	return put(g, "Bench", rho, side, 2.8, { Turn = facing(x, z, tx, tz), RouteMargin = 0.6 })
end

local function lamp(g: Garden, rho: number, side: number): Item?
	return put(g, "Lamp", rho, side, 0.6, { RouteMargin = 0.3 })
end

local function bed(g: Garden, rho: number, side: number, radius: number, style: number): Item?
	return put(g, "FlowerBed", rho, side, radius, { Style = style, Flat = radius })
end

local function bush(g: Garden, rho: number, side: number, scale: number, flowering: boolean?): Item?
	local x, z = at(g, rho, side)
	return place(g.ctx, g.rng, bushSpec("Gardens", x, z, scale, flowering == true, g.rng), 3, 1.5)
end

local function rock(g: Garden, rho: number, side: number, scale: number): Item?
	return put(g, "Rock", rho, side, 1.8 * scale, { Scale = scale, Style = g.rng:NextInteger(1, 3) })
end

local function topiary(g: Garden, rho: number, side: number, style: number, scale: number?): Item?
	local s = scale or 1
	return put(g, "Topiary", rho, side, 1.3 * s, { Scale = s, Style = style, RouteMargin = 0.8 })
end

local function hedge(g: Garden, rho1: number, side1: number, rho2: number, side2: number)
	local x1, z1 = at(g, rho1, side1)
	local x2, z2 = at(g, rho2, side2)
	placeHedge(g.ctx, "Gardens", x1, z1, x2, z2, 2)
end

-- 검사 없이 그 자리에 바로 두는 장식(연못 꾸밈·다리처럼 자리가 정해진 것). 방향은 틈 방향
local function fixed(g: Garden, kind: string, rho: number, side: number, fields: { [string]: any })
	local x, z = at(g, rho, side)
	local item: Item = {
		Kind = kind,
		Zone = "Gardens",
		X = x,
		Y = 0,
		Z = z,
		Radius = 1,
		Scale = 1,
		Turn = g.angle,
		Tint = g.rng:NextNumber(),
		Style = 1,
		Height = 0,
		Layer = "Free",
	}
	for key, value in fields do
		(item :: any)[key] = value
	end
	insert(g.ctx, item)
end

local THEMES: { [string]: (Garden) -> () } = {}

-- 분수 광장: 오솔길이 둥근 돌 광장으로 이어지고 가운데 3단 분수. 대각선 벤치 넷, 옆 정원등 둘, 꽃밭, 토피어리
THEMES.Fountain = function(g)
	put(g, "Fountain", 170, 0, 5.6, { OnRoute = true, Y = T.DISC_TOP })
	for _, a in { 45, 135, 225, 315 } do
		local r = math.rad(a)
		local rho, side = 170 + math.cos(r) * 16.5, math.sin(r) * 16.5
		bench(g, rho, side, 170, 0)
	end
	lamp(g, 170, 14.6)
	lamp(g, 170, -14.6)
	bed(g, 192, 13, 3.2, 1)
	bed(g, 192, -13, 3.2, 3)
	bed(g, 150, 11, 2.8, 5)
	topiary(g, 150, 4.9, 1)
	topiary(g, 150, -4.9, 1)
	tree(g, 196, 30, 1.2, 1)
	tree(g, 186, -26, 1.1, 1)
	bush(g, 147, -12, 1, true)
end

-- 꽃 정원: 오솔길 입구 장미 아치, 크기·색이 다른 꽃밭 무리, 꽃 덤불, 분홍 꽃나무, 새 물통, 벤치
THEMES.Flowers = function(g)
	put(g, "Arch", 136, 0, 0.8, { Turn = g.angle, OnRoute = true, Layer = "Free", Y = T.TRAIL_TOP })
	bed(g, 146, 10.5, 2.8, 1)
	bed(g, 150, -8.6, 3.2, 2)
	bed(g, 162, 15, 3.6, 3)
	bed(g, 166, -12.5, 3.2, 5)
	bed(g, 178, 17, 3.8, 4)
	bed(g, 182, -13.5, 3.2, 6)
	bed(g, 196, 9, 3, 2)
	bed(g, 194, -24, 3.6, 1)
	bush(g, 170, 21, 1.1, true)
	bush(g, 153, 14.5, 0.9, true)
	put(g, "Birdbath", 170, -21, 1.3)
	tree(g, 192, 27, 1.15, 4)
	tree(g, 188, -29, 1.05, 4)
	bench(g, 184, 10.5, 184, 30)
	lamp(g, 158, -5.2)
end

-- 과수원: 과일나무 두 줄(엇갈려서) + 과일 상자 + 나무 그늘 벤치
THEMES.Orchard = function(g)
	tree(g, 146, 10, 0.95, 2)
	tree(g, 160, -14, 1, 2)
	tree(g, 168, 17, 1.05, 2)
	tree(g, 182, -22, 1.1, 2)
	tree(g, 190, 26, 1.1, 2)
	tree(g, 198, -34, 1.05, 2)
	tree(g, 200, 10, 1, 2)
	put(g, "Crate", 174, -8, 1.4, { Turn = g.angle + 0.4 })
	bench(g, 176, 7.5, 176, 20)
	bush(g, 152, -8, 0.9)
	lamp(g, 164, -3.5)
end

-- 연못: 지형 연못(물 윗면 = 땅) 위로 나무 다리, 둘레 돌·수련·부들, 연못을 보는 벤치, 징검돌
THEMES.Pond = function(g)
	local pond = g.pond :: Island.Pond
	fixed(g, "PondDeco", 170, 0, { Scale = pond.R, Height = pond.Seed })
	fixed(g, "Bridge", 170, 0, { Height = 34 })
	bench(g, 172, 20, 170, 0)
	put(g, "Stones", 157, 12, 3, { Turn = g.angle + g.m * 0.7, Flat = 3 })
	lamp(g, 186, 16)
	bush(g, 193, 21, 1.1)
	bush(g, 188, -20, 1)
	bush(g, 150, -9, 0.9, true)
	rock(g, 191, 10.5, 1)
	tree(g, 198, 30, 1.3, 1)
	tree(g, 192, -31, 1.1, 1)
end

-- 소풍 잔디: 격자무늬 돗자리 둘(바구니·접시), 그늘 나무 아래 소풍 탁자, 꽃밭
THEMES.Picnic = function(g)
	put(g, "Blanket", 165, 14, 3.4, { Turn = g.angle + 0.35, Style = 1, Flat = 3.4 })
	put(g, "Blanket", 182, -15, 3.4, { Turn = g.angle - 0.5, Style = 2, Flat = 3.4 })
	put(g, "PicnicTable", 190, 18, 3.4, { Turn = g.angle + math.pi / 2 })
	tree(g, 194, 30, 1.4, 1)
	tree(g, 152, -11, 0.95, 1)
	bed(g, 196, 8, 2.8, 5)
	bush(g, 176, -23, 1.1)
	bush(g, 146, 11.5, 0.9, true)
	lamp(g, 172, -5.2)
end

-- 바위 정원: 흰 자갈밭(지형 칠하기) 위 크고 작은 바위 무리, 석등, 단풍나무, 벤치
THEMES.Rockery = function(g)
	local gx, gz = at(g, 178, 16)
	table.insert(g.ctx.Paint, { Kind = "Blob", X = gx, Z = gz, R = 11, Material = "Salt", Margin = 0 })
	rock(g, 172, 13, 1.6)
	rock(g, 176, 18.5, 0.9)
	rock(g, 184, 12, 1.1)
	rock(g, 186, 22, 1.4)
	rock(g, 160, -9, 1.2)
	rock(g, 194, -18, 1)
	put(g, "Lantern", 164, 12, 0.9)
	put(g, "Lantern", 192, 7, 0.9)
	tree(g, 170, -18, 0.95, 3)
	tree(g, 198, 32, 1.1, 3)
	tree(g, 148, -9, 0.8, 3)
	bench(g, 184, -14, 184, 16)
	bush(g, 196, -30, 1)
end

-- 토피어리 길: 오솔길 양옆 낮은 산울타리 + 막대 사탕·두 공·세 단 토피어리 줄 + 벤치
THEMES.Topiary = function(g)
	for _, s in { -1, 1 } do
		hedge(g, 128, s * 5.4, 150, s * 5.4)
		hedge(g, 158, s * 5.4, 180, s * 5.4)
		hedge(g, 188, s * 5.4, 200, s * 5.4)
	end
	for k, rho in { 154, 184 } do
		for _, s in { -1, 1 } do
			topiary(g, rho, s * 5.6, if k == 1 then 3 else 2, 1.1)
		end
	end
	topiary(g, 168, 14, 1, 1.2)
	topiary(g, 168, -14, 1, 1.2)
	topiary(g, 194, 22, 3, 1.3)
	topiary(g, 194, -22, 3, 1.3)
	bench(g, 176, 14, 176, 30)
	bed(g, 180, -20, 3, 6)
	tree(g, 196, -31, 1.15, 1)
	lamp(g, 142, 8)
end

-- 정자: 오솔길이 지나가는 흰 팔각 정자(나무 마루 + 기둥 + 둥근 지붕), 둘레 꽃 덤불·정원등·나무
THEMES.Gazebo = function(g)
	put(g, "Gazebo", 176, 0, 1, { Layer = "Free", OnRoute = true, Y = 0, Turn = g.angle, Flat = 8 })
	bush(g, 176, 12, 1, true)
	bush(g, 176, -12, 1, true)
	bush(g, 190, 14, 0.9, true)
	bush(g, 162, -12, 0.9, true)
	lamp(g, 160, -5.2)
	lamp(g, 192, -5.2)
	bed(g, 150, 11, 2.8, 4)
	tree(g, 198, 28, 1.25, 4)
	tree(g, 196, -30, 1.2, 1)
	bench(g, 186, -22, 176, 0)
end

-- 정원 가장자리 심은 무더기: 주제 장식을 다 놓은 뒤, 틈 양옆(부지 울타리 쪽) 빈 잔디 네 곳에 작은 나무 하나 +
-- 둘레 덤불 둘 + 들꽃 무더기를 한 무더기로(넓은 잔디가 비어 보이지 않게, 흩뿌리지 않고 모아서).
-- 자리가 없으면 조용히 건너뜀. 나무 색은 정원 주제를 따름
local PLANTING_TREE = { Orchard = 2, Rockery = 3, Flowers = 4, Gazebo = 4 }
local function plantings(g: Garden, theme: string)
	local rng = g.rng
	for _, rho in { 158, 190 } do
		for _, s in { -1, 1 } do
			local half = ParkLayout.gapHalfWidth(rho)
			local side = s * (half - ParkLayout.PLOT_MARGIN - 5.5)
			local x, z = onAxis(g.angle, rho + rng:NextNumber(-4, 4), side)
			local style = PLANTING_TREE[theme] or (if rng:NextNumber() < 0.3 then 4 else 1)
			local spec = treeSpec("Gardens", "Island", x, z, rng:NextNumber(0.8, 0.95), style, rng)
			local center = place(g.ctx, rng, spec, 5, 3, true)
			local cx, cz = x, z
			local reach = 2
			if center then
				cx, cz, reach = center.X, center.Z, center.Radius
			end
			local out = math.atan2(cz, cx) -- 광장에서 먼 쪽
			for k = 1, 2 do
				local scale = rng:NextNumber(0.75, 1)
				local a = out + (k - 1.5) * 2.2 + rng:NextNumber(-0.3, 0.3)
				local d = reach + BUSH_RADIUS * scale + 0.8
				place(
					g.ctx,
					rng,
					bushSpec("Gardens", cx + math.cos(a) * d, cz + math.sin(a) * d, scale, k == 1, rng),
					3,
					1,
					true
				)
			end
			-- 들꽃 무더기: 광장 쪽 앞
			local a = out + math.pi + rng:NextNumber(-0.5, 0.5)
			local d = reach + 2.6
			place(g.ctx, rng, {
				Kind = "FlowerBed",
				Zone = "Gardens",
				Region = "Island",
				X = cx + math.cos(a) * d,
				Z = cz + math.sin(a) * d,
				Radius = 2.2,
				Turn = rng:NextNumber(0, TAU),
				Style = if rng:NextNumber() < 0.5 then 3 else 6,
				Flat = 2.2,
			}, 3, 1, true)
		end
	end
end

local function gardens(ctx: Ctx)
	for j, angle in GAP_ANGLES do
		local rng = Rng.new(T.SEED + 200 + j)
		local theme = T.GARDEN_THEMES[(j - 1) % #T.GARDEN_THEMES + 1]
		local build = THEMES[theme]
		if build then
			local g = { ctx = ctx, rng = rng, angle = angle, m = rng:Sign(), pond = GAP_PONDS[j] }
			build(g)
			plantings(g, theme)
		end
	end
end

-- 숲띠 -------------------------------------------------------------------------

local function belt(ctx: Ctx)
	local rng = Rng.new(T.SEED + 300)
	local outer = T.OUTER_RING
	local ringOut = outer.Radius + outer.Width / 2

	-- 부지 뒤: 부지를 보는 벤치 + 옆 정원등 + 양옆 산울타리(산책로 바깥 가장자리를 따라)
	for _, footprint in FOOTPRINTS do
		local a = footprint.Angle
		local x, z = onAxis(a, ringOut + 3.3, 0)
		place(ctx, rng, {
			Kind = "Bench",
			Zone = "Belt",
			Region = "Island",
			X = x,
			Z = z,
			Radius = 2.8,
			Turn = a + math.pi,
			RouteMargin = 0.4,
		})
		x, z = onAxis(a, ringOut + 1.2, 4.2)
		place(
			ctx,
			rng,
			{ Kind = "Lamp", Zone = "Belt", Region = "Island", X = x, Z = z, Radius = 0.6, RouteMargin = 0.2 }
		)
		-- 벤치 옆 동전 망원경(바다 쪽을 봄)
		x, z = onAxis(a, ringOut + 2.2, -5.2)
		place(ctx, rng, {
			Kind = "Telescope",
			Zone = "Belt",
			Region = "Island",
			X = x,
			Z = z,
			Radius = 0.8,
			Turn = a,
			RouteMargin = 0.3,
		}, 2, 0.5)
		for _, s in { -1, 1 } do
			local r = ringOut + 2
			local a1 = a + s * math.rad(2.4)
			local a2 = a + s * math.rad(8.5)
			local x1, z1 = polar(a1, r)
			local x2, z2 = polar(a2, r)
			placeHedge(ctx, "Belt", x1, z1, x2, z2, 1)
		end
	end

	-- 숲 무리: 부지마다 뒤쪽 양옆(부지 가운데 선과 틈 시야 사이)에 큰 무리 하나 + 작은 무리 하나.
	-- 무리 가운데에 큰 나무, 둘레에 작은 나무(모래 가까우면 야자수). 무리 사이는 빈터(잔디 언덕·바위)
	local B = T.BELT
	local trees, palms = 0, 0
	local placed: { Item } = {}
	local centers: { { number } } = {}
	local function grove(a: number, count: number, style: number)
		local grass = Island.grassEdge(a)
		local inner = ringOut + 7
		local d = rng:NextNumber(inner, math.max(inner, grass - 7))
		local cx, cz = polar(a, d)
		table.insert(centers, { cx, cz })
		local done = 0
		for attempt = 1, count * 8 do
			if done >= count then
				break
			end
			-- 첫 그루는 무리 가운데 가까이(크게), 나머지는 둘레(작게)
			local spread = if done == 0 then 3 else B.GroveRadius
			local ga, gr = rng:NextNumber(0, TAU), math.sqrt(rng:NextNumber()) * spread
			local x, z = cx + math.cos(ga) * gr, cz + math.sin(ga) * gr
			local edge = Island.grassEdge(math.atan2(z, x))
			local item: Item? = nil
			if edge - math.sqrt(x * x + z * z) < 11 and palms < B.Palms and rng:NextNumber() < 0.6 then
				local scale = rng:NextNumber(B.PalmScale[1], B.PalmScale[2])
				item = place(ctx, rng, palmSpec("Belt", "Island", x, z, scale, rng), 0, 0, true)
				if item then
					palms += 1
				end
			elseif trees < B.Trees then
				local scale = if done == 0
					then rng:NextNumber(1.3, B.TreeScale[2])
					else rng:NextNumber(B.TreeScale[1], 1.25)
				item = place(ctx, rng, treeSpec("Belt", "Island", x, z, scale, style, rng), 0, 0, true)
				if item then
					trees += 1
					table.insert(placed, item)
				end
			end
			if item then
				done += 1
			end
		end
	end
	for i, footprint in FOOTPRINTS do
		local side = if i % 2 == 0 then 1 else -1
		local style = if rng:NextNumber() < B.BlossomGroves then 4 else 1
		grove(footprint.Angle + side * math.rad(rng:NextNumber(10, 16)), rng:NextInteger(5, 7), style)
		grove(footprint.Angle - side * math.rad(rng:NextNumber(11, 15)), rng:NextInteger(3, 4), 1)
	end

	-- 숲 가장자리 덤불(나무 옆, 가끔 꽃 덤불)
	for _, item in placed do
		if rng:NextNumber() < B.BushChance then
			local a = rng:NextNumber(0, TAU)
			local d = item.Radius + rng:NextNumber(2.5, 4.5)
			local scale = rng:NextNumber(0.9, 1.25)
			local spec =
				bushSpec("Belt", item.X + math.cos(a) * d, item.Z + math.sin(a) * d, scale, rng:NextNumber() < 0.3, rng)
			place(ctx, rng, spec, 3, 1.5, true)
		end
	end

	-- 빈터(무리 가운데에서 먼 곳)의 바위
	local rocks = 0
	for _ = 1, 300 do
		if rocks >= B.Rocks then
			break
		end
		local a = rng:NextNumber(0, TAU)
		local d = rng:NextNumber(ringOut + 4, Island.grassEdge(a) - 3)
		local x, z = polar(a, d)
		local open = true
		for _, c in centers do
			if (c[1] - x) ^ 2 + (c[2] - z) ^ 2 < 22 * 22 then
				open = false
				break
			end
		end
		if open then
			local scale = rng:NextNumber(0.9, 1.5)
			local item = place(ctx, rng, {
				Kind = "Rock",
				Zone = "Belt",
				Region = "Island",
				X = x,
				Z = z,
				Radius = 1.8 * scale,
				Scale = scale,
				Turn = rng:NextNumber(0, TAU),
				Tint = rng:NextNumber(),
				Style = rng:NextInteger(1, 3),
			}, 0, 0, true)
			if item then
				rocks += 1
			end
		end
	end
end

-- 모래 오솔길: 바깥 산책로 바깥 가장자리에서 모래사장(등대 쪽은 등대 받침)까지 지형을 모래로 칠한 굽이치는 길.
-- 파트가 없어서 언덕을 그대로 따라가고, 둘레 장식(숲 무리·덤불 띠)은 이 길을 비켜 감
local function footpaths(ctx: Ctx)
	local B = T.BEACH
	local ringOut = T.OUTER_RING.Radius + T.OUTER_RING.Width / 2
	local half = B.FootpathHalf
	for k, angle in B.Footpaths do
		local a = math.rad(angle)
		local to = Island.grassEdge(a) + 2.5
		if angle == Island.LIGHTHOUSE_ANGLE then
			to = Island.coastRadius(a) - 6 - 5 -- 등대 받침 가장자리
		end
		local from = ringOut - 1
		local steps = math.max(3, math.ceil((to - from) / 6))
		local wiggle = 3.5 * (if k % 2 == 0 then 1 else -1)
		local previous: { number }? = nil
		for step = 0, steps do
			local u = step / steps
			local x, z = onAxis(a, from + (to - from) * u, wiggle * math.sin(math.pi * 1.5 * u))
			if previous then
				local px, pz = previous[1], previous[2]
				table.insert(ctx.Paint, {
					Kind = "Segment",
					X1 = px,
					Z1 = pz,
					X2 = x,
					Z2 = z,
					Half = half,
					Material = "Sand",
					Margin = 0.5,
				})
				table.insert(ctx.Capsules, { X1 = px, Z1 = pz, X2 = x, Z2 = z, R = half + 0.5 })
			end
			previous = { x, z }
		end
	end
end

-- 풀밭 끝 덤불 띠: 모래사장 바로 안쪽 풀밭 가장자리를 따라 덤불(가끔 꽃 덤불·작은 나무) 무리.
-- 띠 밀도는 각도 물결이라 덤불이 모인 곳과 바다가 트인 곳이 번갈아 나옴
local function fringe(ctx: Ctx)
	local B = T.BELT
	local rng = Rng.new(T.SEED + 350)
	local circumference = TAU * 250
	local steps = math.floor(circumference / B.FringeStep)
	for k = 0, steps - 1 do
		local a = (k + rng:NextNumber(-0.3, 0.3)) / steps * TAU
		local density = 0.55 * math.sin(3 * a + 1.3) + 0.45 * math.sin(7 * a + 0.4)
		if density > B.FringeCut then
			local d = Island.grassEdge(a) - rng:NextNumber(3.5, 6.5)
			local x, z = polar(a, d)
			local roll = rng:NextNumber()
			if roll < 0.12 then
				place(ctx, rng, treeSpec("Belt", "Island", x, z, rng:NextNumber(0.8, 1.05), 1, rng), 2, 1.5, true)
			else
				local scale = rng:NextNumber(0.75, 1.25)
				place(ctx, rng, bushSpec("Belt", x, z, scale, roll > 0.8, rng), 2, 1.5, true)
			end
		end
	end
end

-- 모래사장·바다 --------------------------------------------------------------------

-- 부두 기준: 풀밭 끝에서 시작해 물가 너머 PierLength 까지. 반환: 방향, 시작 거리, 끝 거리
local function pierLine(): (number, number, number)
	local a = math.rad(Island.PIER_ANGLE)
	return a, Island.grassEdge(a) - 1, Island.coastRadius(a) + T.BEACH.PierLength
end
Plan.pierLine = pierLine

local function beach(ctx: Ctx)
	local B = T.BEACH
	local rng = Rng.new(T.SEED + 500)

	-- 물가 바위와 연못 자리는 비워 둠. 등대 받침(1 번) 말고는 지형 바위 위에 모난 바윗돌 덩어리
	for i, rock in Island.ROCKS do
		table.insert(ctx.Keep, { X = rock.X, Z = rock.Z, R = rock.R * 1.1 })
		if i > 1 then
			local top = rock.Base + rock.Height
			insert(ctx, {
				Kind = "ShoreRock",
				Zone = "Sea",
				X = rock.X,
				Y = top,
				Z = rock.Z,
				Radius = rock.R,
				Scale = rock.R,
				Turn = i * 2.3,
				Tint = 0.5,
				Style = 1,
				Height = top,
				Layer = "Free",
			})
		end
	end

	-- 등대: 곶의 큰 바위 위(물가보다 6 안쪽)
	local la = math.rad(Island.LIGHTHOUSE_ANGLE)
	local lx, lz = polar(la, Island.coastRadius(la) - 6)
	insert(ctx, {
		Kind = "Lighthouse",
		Zone = "Beach",
		X = lx,
		Y = Island.lowestAround(lx, lz, 3.5),
		Z = lz,
		Radius = 4.5,
		Scale = 1,
		Turn = la + math.pi,
		Tint = 0.5,
		Style = 1,
		Height = 0,
		Layer = "Solid",
	})

	-- 부두: 풀밭 끝 → 바다(T자 끝). 모래 위 부분은 다른 장식이 비켜 가게 막아 둠
	local pa, pierFrom, pierTo = pierLine()
	local px, pz = polar(pa, pierFrom)
	insert(ctx, {
		Kind = "Pier",
		Zone = "Beach",
		X = px,
		Y = B.DeckTop,
		Z = pz,
		Radius = B.PierWidth / 2,
		Scale = 1,
		Turn = pa,
		Tint = 0.5,
		Style = 1,
		Height = pierTo - pierFrom,
		Layer = "Free",
	})
	for d = pierFrom - 2, Island.coastRadius(pa) + 2, 3 do
		local kx, kz = polar(pa, d)
		table.insert(ctx.Keep, { X = kx, Z = kz, R = B.PierWidth / 2 + 2 })
	end
	local ex, ez = polar(pa, pierFrom + 6)
	table.insert(ctx.Paint, {
		Kind = "Segment",
		X1 = px,
		Z1 = pz,
		X2 = ex,
		Z2 = ez,
		Half = B.PierWidth / 2,
		Material = "LeafyGrass",
		Margin = 2,
	})
	-- 부두 끝에 매어 둔 작은 배(T자 끝 옆)
	local bx, bz = onAxis(pa, pierTo - B.PierHead.Depth / 2, B.PierHead.Width / 2 + 3.2)
	insert(ctx, {
		Kind = "Boat",
		Zone = "Sea",
		X = bx,
		Y = WATER,
		Z = bz,
		Radius = 3,
		Scale = 0.9,
		Turn = pa + math.pi,
		Tint = 0.2,
		Style = 2,
		Height = 0,
		Layer = "Free",
	})

	-- 구조대 망루: 수영 구역 옆 모래사장 가운데, 바다를 봄
	local ga = math.rad(B.LifeguardAngle)
	local gx, gz = polar(ga, (Island.grassEdge(ga) + Island.coastRadius(ga)) / 2)
	place(ctx, rng, {
		Kind = "Lifeguard",
		Zone = "Beach",
		Region = "Beach",
		X = gx,
		Z = gz,
		Radius = 2.4,
		Turn = ga,
		Foot = 1.8,
	}, 10, 3)

	-- 간식 가게(부두 옆, 풀밭 끝 가까이)
	local ka = math.rad(B.KioskAngle)
	local kx, kz = polar(ka, Island.grassEdge(ka) + 5)
	place(ctx, rng, {
		Kind = "Kiosk",
		Zone = "Beach",
		Region = "Beach",
		X = kx,
		Z = kz,
		Radius = 4.2,
		Turn = ka + math.pi, -- 계산대가 풀밭(섬 안쪽)을 봄
		Foot = 3,
	}, 8, 3)

	-- 파라솔 묶음(파라솔 + 선베드 둘 + 수건): 바다를 보고, 물가와 나란히
	for zi, zone in B.SetZones do
		local from, to = math.rad(zone.From), math.rad(zone.To)
		for k = 1, zone.Count do
			local a = from + (to - from) * (k - 0.5) / zone.Count + rng:NextNumber(-0.03, 0.03)
			local grass, coast = Island.grassEdge(a), Island.coastRadius(a)
			local d = grass + (coast - grass) * rng:NextNumber(0.35, 0.5)
			local x, z = polar(a, d)
			place(ctx, rng, {
				Kind = "BeachSet",
				Zone = "Beach",
				Region = "Beach",
				X = x,
				Z = z,
				Radius = 3.6,
				Turn = a + rng:NextNumber(-0.15, 0.15),
				Style = (zi * 3 + k) % 4 + 1,
				Tint = rng:NextNumber(),
				Foot = 2,
			}, 8, 3)
		end
		-- 모래성 하나
		local a = (from + to) / 2 + rng:NextNumber(-0.1, 0.1)
		local grass, coast = Island.grassEdge(a), Island.coastRadius(a)
		local x, z = polar(a, (grass + coast) / 2 + 2)
		place(ctx, rng, {
			Kind = "Sandcastle",
			Zone = "Beach",
			Region = "Beach",
			X = x,
			Z = z,
			Radius = 1.8,
			Turn = rng:NextNumber(0, TAU),
		}, 10, 5)
	end

	-- 서핑보드 거치대(풀밭 끝 가까운 모래, 보드 앞면이 섬 안쪽을 봄)
	for k, angle in B.Surfboards do
		local a = math.rad(angle)
		local x, z = polar(a, Island.grassEdge(a) + 4)
		place(ctx, rng, {
			Kind = "Surfboards",
			Zone = "Beach",
			Region = "Beach",
			X = x,
			Z = z,
			Radius = 3,
			Turn = a + math.pi + rng:NextNumber(-0.2, 0.2),
			Style = k,
			Foot = 2.5,
		}, 10, 4)
	end

	-- 모래사장 야자수: 섬 둘레에 무리(1~3 그루)를 고르지 않은 간격으로, 풀밭 끝 가까운 모래 위, 바다 쪽으로 기움
	local start = rng:NextNumber(0, TAU)
	for grove = 1, B.PalmGroves do
		local a = start + (grove - 0.5) / B.PalmGroves * TAU + rng:NextNumber(-0.3, 0.3)
		for _ = 1, rng:NextInteger(1, 3) do
			local pa2 = a + rng:NextNumber(-0.04, 0.04)
			local grass = Island.grassEdge(pa2)
			local x, z = polar(pa2, grass + rng:NextNumber(1.5, 6))
			local scale = rng:NextNumber(1.05, 1.45)
			place(ctx, rng, palmSpec("Beach", "Beach", x, z, scale, rng), 5, 2.5, true)
		end
	end

	-- 떠밀려 온 나무(물가 가까운 모래, 아무 방향)
	local placed = 0
	for _ = 1, 80 do
		if placed >= B.Driftwood then
			break
		end
		local a = rng:NextNumber(0, TAU)
		local grass, coast = Island.grassEdge(a), Island.coastRadius(a)
		local x, z = polar(a, grass + (coast - grass) * rng:NextNumber(0.55, 0.75))
		local scale = rng:NextNumber(0.8, 1.2)
		local item = place(ctx, rng, {
			Kind = "Driftwood",
			Zone = "Beach",
			Region = "Beach",
			X = x,
			Z = z,
			Radius = 2.8 * scale,
			Scale = scale,
			Turn = a + math.pi / 2 + rng:NextNumber(-0.6, 0.6),
			Foot = 2,
		}, 0, 0, true)
		if item then
			placed += 1
		end
	end

	-- 수영 구역 부표(빨강·하양 번갈아)
	local buoys = B.Buoys
	for k = 0, buoys.Count - 1 do
		local ba = math.rad(buoys.From + (buoys.To - buoys.From) * k / (buoys.Count - 1))
		local x, z = polar(ba, Island.coastRadius(ba) + buoys.Offset)
		insert(ctx, {
			Kind = "Buoy",
			Zone = "Sea",
			X = x,
			Y = WATER,
			Z = z,
			Radius = 0.6,
			Scale = 1,
			Turn = 0,
			Tint = 0.5,
			Style = k % 2 + 1,
			Height = 0,
			Layer = "Free",
		})
	end
end

local function sea(ctx: Ctx)
	local rng = Rng.new(T.SEED + 600)
	for _, boat in T.SEA.Boats do
		local a = math.rad(boat.Angle)
		local x, z = polar(a, Island.coastRadius(a) + boat.Offset)
		insert(ctx, {
			Kind = "Boat",
			Zone = "Sea",
			X = x,
			Y = WATER,
			Z = z,
			Radius = 4 * boat.Scale,
			Scale = boat.Scale,
			Turn = math.rad(boat.Heading),
			Tint = rng:NextNumber(),
			Style = rng:NextInteger(1, 3),
			Height = 0,
			Layer = "Free",
		})
	end
	-- 먼 작은 섬 위: 풀 언덕에 야자수 무리(크게, 바다 쪽으로 기움) + 큰 덤불 몇 개(언덕이 비어 보이지 않게)
	for _, islet in Island.islets() do
		local palms = if islet.R > 40 then 4 else 3
		local bushes = if islet.R > 40 then 5 else 3
		local size = islet.R / 24
		local spots: { { number } } = {}
		local function spot(spacing: number): (number?, number?)
			for _ = 1, 30 do
				local a = rng:NextNumber(0, TAU)
				local d = math.sqrt(rng:NextNumber()) * islet.R * 0.5
				local x, z = islet.HillX + math.cos(a) * d, islet.HillZ + math.sin(a) * d
				local _, material = Island.surface(x, z)
				local free = material == "Grass"
				for _, p in spots do
					if free and (p[1] - x) ^ 2 + (p[2] - z) ^ 2 < spacing * spacing then
						free = false
					end
				end
				if free then
					table.insert(spots, { x, z })
					return x, z
				end
			end
			return nil, nil
		end
		for _ = 1, palms do
			local x, z = spot(4 * size)
			if x and z then
				insert(ctx, {
					Kind = "Palm",
					Zone = "Sea",
					X = x,
					Y = Island.lowestAround(x, z, 1),
					Z = z,
					Radius = 1,
					Scale = size * rng:NextNumber(0.95, 1.25),
					-- 섬 가운데에서 바깥쪽으로 기움
					Turn = math.atan2(z - islet.Z, x - islet.X) + rng:NextNumber(-0.5, 0.5),
					Tint = rng:NextNumber(),
					Style = 2, -- 먼 야자수(파트 적게)
					Height = 0,
					Layer = "Free",
				})
			end
		end
		for _ = 1, bushes do
			local x, z = spot(3.5 * size)
			if x and z then
				insert(ctx, {
					Kind = "Bush",
					Zone = "Sea",
					X = x,
					Y = Island.lowestAround(x, z, 1.5),
					Z = z,
					Radius = 2,
					Scale = size * rng:NextNumber(0.9, 1.4),
					Turn = rng:NextNumber(0, TAU),
					Tint = rng:NextNumber(),
					Style = 1,
					Height = 0,
					Layer = "Free",
				})
			end
		end
	end
end

-- 보이지 않는 벽 -----------------------------------------------------------------------

-- 닫힌 꺾은선 줄이기: 앞 점에서 곧게 이어도 사이 점들이 tolerance 안에 들면 그 사이 점을 뺌(fixed 점은 남김)
local function simplifyLoop(points: { { number } }, fixed: { boolean }, tolerance: number): { { number } }
	local n = #points
	-- 남길 첫 점: fixed 점이 있으면 그 점부터(한 바퀴 돌아 제자리로)
	local first = 1
	for i = 1, n do
		if fixed[i] then
			first = i
			break
		end
	end
	local order: { number } = {}
	for k = 0, n do
		table.insert(order, (first - 1 + k) % n + 1)
	end
	local kept: { { number } } = { points[order[1]] }
	local anchor = 1
	local j = 2
	while j <= n do
		-- anchor → j+1 로 곧게 가도 되는지(사이 점이 모두 tolerance 안이고, j 가 fixed 가 아니면)
		local nextIndex = j + 1
		local ok = not fixed[order[j]] and nextIndex <= n + 1
		if ok then
			local a, b = points[order[anchor]], points[order[nextIndex]]
			for m = anchor + 1, nextIndex - 1 do
				local p = points[order[m]]
				if segmentDistance(p[1], p[2], a[1], a[2], b[1], b[2]) > tolerance then
					ok = false
					break
				end
			end
		end
		if not ok then
			table.insert(kept, points[order[j]])
			anchor = j
		end
		j += 1
	end
	return kept
end

-- 물가 + Offset 을 따라 도는 닫힌 꺾은선. 부두 자리는 부두 양옆·끝을 감싸고 돌아감(부두 끝까지 걸어갈 수 있고
-- 부두에서 뛰어내려도 벽 안). 반환: {{x, z}, ...}(각도가 커지는 순서)
function Plan.wallPath(): { { number } }
	local W, B = T.WALL, T.BEACH
	local pa, _, pierTo = pierLine()
	local ux, uz = math.cos(pa), math.sin(pa) -- 부두 방향
	local sx, sz = -uz, ux -- 옆(각도가 커지는 쪽)
	local half = B.PierWidth / 2 + W.PierGap
	local headHalf = B.PierHead.Width / 2 + W.PierGap
	local headFrom = pierTo - B.PierHead.Depth - W.PierGap
	local headTo = pierTo + W.PierGap
	local function local2(along: number, side: number): { number }
		return { ux * along + sx * side, uz * along + sz * side }
	end

	local points: { { number } } = {}
	local fixed: { boolean } = {} -- 줄이지 않을 점(부두 감싸기)
	local count = math.floor(360 / W.Step)
	local detoured = false
	for k = 0, count - 1 do
		local a = math.rad(k * W.Step)
		local d = Island.coastRadius(a) + W.Offset
		local x, z = polar(a, d)
		local side = x * sx + z * sz
		local along = x * ux + z * uz
		if along > 0 and math.abs(side) < headHalf + 2 then
			-- 부두 자리: 처음 만났을 때 한 번에 감싸는 길을 넣음(오른쪽 옆 → 끝 → 왼쪽 옆)
			if not detoured then
				detoured = true
				local wallAt = Island.coastRadius(pa) + W.Offset
				for _, p in
					{
						local2(wallAt, -headHalf - 2),
						local2(wallAt, -half),
						local2(headFrom, -half),
						local2(headFrom, -headHalf),
						local2(headTo, -headHalf),
						local2(headTo, headHalf),
						local2(headFrom, headHalf),
						local2(headFrom, half),
						local2(wallAt, half),
						local2(wallAt, headHalf + 2),
					}
				do
					table.insert(points, p)
					fixed[#points] = true
				end
			end
		else
			table.insert(points, { x, z })
		end
	end
	return simplifyLoop(points, fixed, W.Tolerance)
end

-- 지형 칠하기: 공원 파트(광장·부지·길) 밑 + 산책로 밑은 풀잎 없는 LeafyGrass
local function parkPaint(ctx: Ctx)
	local paint = ctx.Paint
	table.insert(paint, { Kind = "Circle", X = 0, Z = 0, R = 48, Material = "LeafyGrass" })
	for _, footprint in FOOTPRINTS do
		table.insert(paint, {
			Kind = "Box",
			X = footprint.CenterX,
			Z = footprint.CenterZ,
			DirX = footprint.DirX,
			DirZ = footprint.DirZ,
			HalfX = footprint.HalfWidth,
			HalfZ = footprint.HalfDepth,
			Material = "LeafyGrass",
		})
		local x1, z1 = polar(footprint.Angle, footprint.PathFrom)
		local x2, z2 = polar(footprint.Angle, footprint.PathTo)
		table.insert(paint, {
			Kind = "Segment",
			X1 = x1,
			Z1 = z1,
			X2 = x2,
			Z2 = z2,
			Half = ParkLayout.PATH_WIDTH / 2,
			Material = "LeafyGrass",
		})
	end
	for i, ring in RINGS do
		local points = RING_POINTS[i]
		for k, p in points do
			local q = points[k % #points + 1]
			table.insert(paint, {
				Kind = "Segment",
				X1 = p[1],
				Z1 = p[2],
				X2 = q[1],
				Z2 = q[2],
				Half = ring.Width / 2,
				Material = "LeafyGrass",
			})
		end
	end
	for _, segment in ROUTE_SEGMENTS do
		table.insert(paint, {
			Kind = "Segment",
			X1 = segment.X1,
			Z1 = segment.Z1,
			X2 = segment.X2,
			Z2 = segment.Z2,
			Half = segment.Width / 2,
			Material = "LeafyGrass",
		})
	end
	for _, disc in ROUTE_DISCS do
		table.insert(paint, { Kind = "Circle", X = disc.X, Z = disc.Z, R = disc.R, Material = "LeafyGrass" })
	end
	for _, pond in PONDS do
		table.insert(ctx.Keep, { X = pond.X, Z = pond.Z, R = pond.R * 1.2 })
	end
end

-- 계획 만들기 -------------------------------------------------------------------

-- 디버그: 표를 넣어 두면 못 놓은 장식 설명(Spec)을 모아 둠
Plan.debugSkipped = nil :: { any }?

function Plan.make(): Result
	local result: Result = {
		Items = {},
		Rings = {},
		Trails = {},
		Discs = {},
		Wall = { Points = Plan.wallPath(), Height = T.WALL.Height, Bottom = T.WALL.Bottom },
		Paint = {},
		Ponds = {},
		Skipped = {},
	}
	for i, ring in RINGS do
		local points = {}
		for _, p in RING_POINTS[i] do
			table.insert(points, table.clone(p))
		end
		table.insert(result.Rings, {
			Radius = ring.Radius,
			Width = ring.Width,
			Segments = ring.Segments,
			Top = T.RING_TOP,
			Material = ring.Material,
			Color = ring.Color,
			Points = points,
		})
	end
	for _, trail in TRAILS do
		table.insert(result.Trails, table.clone(trail))
	end
	for _, disc in DISCS do
		table.insert(result.Discs, table.clone(disc))
	end
	for _, pond in PONDS do
		table.insert(result.Ponds, table.clone(pond))
	end

	local ctx: Ctx = {
		Items = result.Items,
		Cells = {},
		Big = {},
		Keep = {},
		Capsules = {},
		Paint = result.Paint,
		Skipped = result.Skipped,
	}
	parkPaint(ctx)
	footpaths(ctx)
	-- 큰 것(물가 명물)부터 놓고, 작은 장식이 사이를 채움
	beach(ctx)
	sea(ctx)
	gardens(ctx)
	innerLawn(ctx)
	belt(ctx)
	fringe(ctx)
	return result
end

-- 종류별 개수(디버그·테스트용)
function Plan.countKinds(result: Result): { [string]: number }
	local counts = {}
	for _, item in result.Items do
		counts[item.Kind] = (counts[item.Kind] or 0) + 1
	end
	return counts
end

return Plan
