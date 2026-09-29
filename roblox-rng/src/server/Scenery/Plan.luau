--!strict
-- 주변 풍경 배치 계획(순수 계산: Instance 없이 숫자 표만 만듦). Scenery/init.luau 가 이 표대로 파트를 만듭니다.
--
-- 구역(광장 중심에서의 거리 r):
--   r 62~113  안쪽 잔디: 광장 둘레 꽃밭, 안쪽 산책로 고리(r 84), 부지 길 양옆 덤불·꽃밭, 입구 쪽 작은 나무, 가로등·벤치
--   r 113~205 이웃 부지 사이 쐐기 틈 8곳: 틈마다 주제가 다른 작은 정원(분수/꽃밭/숲/연못/소풍/바위/토피어리/수련)
--             + 가운데 오솔길(안쪽 고리 → 바깥 고리)
--   r 205~212 바깥 산책로 고리(부지 뒤를 한 바퀴)
--   r 212~250 부지 뒤 숲띠: 부지 뒤에 나무 무리, 틈 방향은 시야를 위해 큰 나무 없이 비움(바위·언덕·덤불·벤치)
--   r 250~    가장자리: "Ocean" = 모래사장·등대·부두 + 얕은 물·먼바다·작은 섬·배 / "Mountains" = 숲·초록 언덕·눈 덮인 산·폭포
-- 모든 장식은 ParkLayout.blocked(부지·간판·길·광장) 와 산책로를 비켜 가고, 서로 겹치지 않게 놓습니다.
-- 난수는 구역마다 고정 시드(Rng)라서 한 구역을 고쳐도 다른 구역 배치는 그대로입니다.

local ParkLayout = require(script.Parent.Parent.ParkLayout)
local Rng = require(script.Parent.Rng)

type Rng = Rng.Rng

local Plan = {}

local TAU = math.pi * 2
local ISLAND_RADIUS = ParkLayout.ISLAND_RADIUS

-- 조절 값 ---------------------------------------------------------------------
local T = {
	SEED = 8128,

	-- 땅 윗면 높이
	ISLAND_TOP = 0, -- 섬(Baseplate) 윗면
	ROUTE_TOP = 0.15, -- 산책로 윗면. 부지 길(0.2)보다 살짝 낮아서 겹치는 곳은 부지 길이 보임
	ROUTE_HEIGHT = 0.3,

	-- 산책로(ParkService 길과 같은 색·재질). Segments = 고리를 이루는 직선 조각 수
	INNER_RING = { Radius = 84, Width = 7, Segments = 32 },
	OUTER_RING = { Radius = 208.5, Width = 7, Segments = 48 },
	TRAIL_WIDTH = 5, -- 틈 정원 가운데 오솔길
	ROUTE_MARGIN = 1.5, -- 산책로 양옆 여유(가로등·벤치는 더 가깝게 둠)
	EDGE_MARGIN = 2.5, -- 섬 가장자리 안쪽 여유
	SPACING = 0.6, -- 장식끼리 최소 틈
	CORRIDOR_HALF_WIDTH = 10, -- 광장에서 틈 방향으로 바깥이 보이게 큰 나무를 두지 않는 반폭(바깥 고리 너머)

	-- 틈 정원 주제(ParkLayout.gapAngles() 순서: 270도 = 지구본 뒤, 315도, 0도, ... 225도)
	GARDEN_THEMES = { "Fountain", "Flowers", "Grove", "Pond", "Picnic", "Rockery", "Topiary", "Lily" },

	-- 부지 뒤 숲띠
	BELT = {
		-- 부지 하나 뒤 나무 무리 수와 이웃 무리 사이 각도(도). 산맥은 바로 뒤 숲·언덕이 채우므로 조금 적게
		Groves = { Ocean = { PerPlot = 4, Spread = 8.5 }, Mountains = { PerPlot = 2, Spread = 18 } },
		GroveTrees = { 4, 5 },
		GroveRadius = 14,
		TreeScale = { 1.15, 1.75 }, -- 동그란·뾰족 나무 크기(광장 나무 1 보다 커서 부지 뒤를 든든하게 감쌈)
		PalmScale = { 1.1, 1.4 },
		Rocks = 16,
		CorridorMounds = true, -- 틈 방향 시야(큰 나무 없는 곳)마다 낮은 잔디 언덕 하나
		Mounds = 6, -- 그 밖에 흩어 놓을 잔디 언덕 시도 수
		Bushes = 22,
	},
	PATCHES = { Inner = 10, Gardens = 12, Belt = 16 }, -- 잔디 색 무늬(얇은 원판)

	OCEAN = {
		BeachTop = -0.4, -- 모래 윗면
		BeachRadius = 272, -- 모래사장 바깥 반지름
		BeachInset = 1.5, -- 모래 위 장식은 섬 가장자리에서 이만큼 떨어짐
		FoamRadius = 277, -- 물가 흰 거품 띠
		FoamTop = -0.85,
		ShallowRadius = 330, -- 얕은 물(밝은 청록)
		ShallowTop = -1.05,
		MidRadius = 380, -- 얕은 물과 먼바다 사이 중간 빛 띠(물빛이 수평선 쪽으로 차츰 짙어지게)
		MidTop = -1.3,
		DeepTop = -1.6, -- 먼바다
		OceanTile = 2048, -- 먼바다 판 한 장 크기(파트 최대 크기)
		OceanTiles = 2, -- 가운데에서 양쪽으로 몇 장씩: (2*2+1)^2 = 25장, 가로 10240 스터드
		WallRadius = 268, -- 보이지 않는 벽(모래사장 끝)
		WallHeight = 60,
		WallSegments = 24, -- 꼭짓점(270.3)도 모래사장(272) 안
		LighthouseAngle = 315, -- 도. 틈 방향이라 광장에서 정원 사이로 보임
		PierAngle = 135,
		PierLength = 44,
		PierWidth = 6,
		BeachPalms = 24,
		Umbrellas = 9,
		BeachRocks = 7,
		BeltPalmChance = 0.45, -- 숲띠 바깥쪽(r > 232) 나무 중 야자수 비율
		Boats = { -- Scale = 크기 배율(멀리 있는 배는 크게 해서 수평선에서도 보이게)
			{ Angle = 147, Distance = 312, Heading = 60, Scale = 1.3 },
			{ Angle = 28, Distance = 345, Heading = 130, Scale = 1.5 },
			{ Angle = 252, Distance = 385, Heading = -20, Scale = 1.8 },
			{ Angle = 300, Distance = 470, Heading = 35, Scale = 2.2 },
			{ Angle = 95, Distance = 430, Heading = 170, Scale = 2 },
		},
		IsletSandRise = 1, -- 작은 섬 모래 윗면(먼바다 위)
		IsletGrassRise = 2, -- 작은 섬 풀 윗면(먼바다 위)
		Islets = {
			{ Angle = 205, Distance = 560, Radius = 30 },
			{ Angle = 330, Distance = 720, Radius = 42 },
			{ Angle = 42, Distance = 640, Radius = 26 },
			{ Angle = 112, Distance = 880, Radius = 55 },
			{ Angle = 268, Distance = 980, Radius = 48 },
			{ Angle = 160, Distance = 700, Radius = 34 },
		},
	},

	MOUNTAINS = {
		FieldTop = -0.25, -- 섬 바깥 들판 윗면(섬보다 살짝 낮음)
		FieldTile = 2048, -- 들판 판 한 장 크기(파트 최대 크기). 먼바다처럼 (2*2+1)^2 = 25장, 가로 10240 스터드
		FieldTiles = 2,
		WallRadius = 256,
		WallHeight = 60,
		WallSegments = 24,
		ForestFrom = 259, -- 숲 가장자리 나무 줄
		ForestTo = 285,
		ForestTrees = 76,
		ForestPineChance = 0.5,
		BeltPineChance = 0.25, -- 부지 뒤 숲띠 나무 중 뾰족 나무 비율(뾰족 나무는 파트 9개, 동그란 나무는 3개)
		BlobFrom = 276, -- 그 뒤 나무 덩어리(큰 공)
		BlobTo = 322,
		Blobs = 80,
		-- Stagger = 짝수 번째 언덕을 이만큼 뒤로(두 줄로 엇갈려서 도넛처럼 고르게 보이지 않게)
		Hills = { Count = 22, Distance = 350, Stagger = 22, Diameter = { 120, 180 }, Top = { 34, 64 } },
		Peaks = {
			Count = 14,
			Distance = 480,
			Stagger = 36, -- 홀수 번째 산을 이만큼 뒤로(앞뒤 두 겹 산줄기)
			BaseRadius = { 105, 130 },
			Height = { 120, 190 },
			Faces = 5,
			Snow = { 0.3, 0.4 }, -- 꼭대기에서 눈이 덮는 비율
			SnowLift = 1.4, -- 눈 면을 바위 면보다 바깥으로
			RockThickness = 3,
			SnowThickness = 1.6,
			-- 이 값보다 바깥을 향한 면은 만들지 않음(-0.6 이면 섬에서는 안 보이는 면을 빼서 파트 약 25% 절약.
			-- 대신 위에서 내려다보는 미리보기에서 가까운 산이 속 빈 껍데기로 보임). -1 이하 = 모든 면
			CullDot = -2,
		},
		WaterfallAngle = 315,
		WaterfallDistance = 302, -- 절벽 중심
		WaterfallHeight = 44,
	},
}
Plan.Tuning = T

export type Variant = string -- "Ocean" | "Mountains"
Plan.VARIANTS = { "Ocean", "Mountains" }
Plan.DEFAULT_VARIANT = "Ocean"

-- 장식 하나. Kind 별 모양은 Scenery/Props.luau
export type Item = {
	Kind: string,
	Zone: string, -- 파트 개수를 셀 때 묶는 구역
	X: number,
	Y: number, -- 서 있는 땅의 윗면 높이
	Z: number,
	Radius: number, -- 바닥 반지름(비켜 가기·간격)
	Scale: number,
	Turn: number, -- 방향(라디안). (cos, sin) = 앞(벤치·배)이나 기우는 쪽(야자수)
	Tint: number, -- 0~1 색 변화
	Style: number, -- 종류 안의 모양/색 번호
	Height: number, -- 언덕·덩어리: 땅 위로 솟은 높이 / 폭포: 절벽 높이 / 부두: 길이
	Layer: string, -- "Solid"(서로 안 겹침) / "Patch"(풀 무늬끼리만 안 겹침) / "Free"
}

-- 고리 산책로(직선 조각 Segments 개), 곧은 길 조각
export type Ring = { Radius: number, Width: number, Segments: number, Top: number }
export type Segment = { X1: number, Z1: number, X2: number, Z2: number, Width: number, Top: number }

-- 산 면 하나(세 꼭짓점 {x, y, z}). Snow = 눈 면
export type Triangle = { A: { number }, B: { number }, C: { number }, Snow: boolean, Tint: number, Thickness: number }
export type Peak = { X: number, Z: number, Height: number, Triangles: { Triangle } }

export type Result = {
	Variant: Variant,
	Items: { Item },
	Rings: { Ring },
	Trails: { Segment },
	Stream: { Segment },
	Peaks: { Peak },
	Wall: { Radius: number, Height: number, Segments: number },
	Skipped: { [string]: number }, -- 자리가 없어 못 놓은 장식 수("구역/종류" 별)
}

type Circle = { X: number, Z: number, R: number }

type Ctx = {
	Items: { Item },
	Cells: { [number]: { Item } },
	Big: { Item },
	Patches: { Item },
	Keep: { Circle },
	Skipped: { [string]: number },
}

-- 놓을 장식 설명. Region: "Island"(섬 잔디) / "Beach" / "Field"(섬 바깥 들판) / "Free"
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
	RouteMargin: number?, -- 산책로 여유를 따로(가로등·벤치)
	Tall: boolean?, -- 큰 나무: 광장에서 바깥이 보이는 틈 방향(시야)을 비켜 감
	Backdrop: boolean?, -- 먼 배경(언덕): 부두·개울 같은 비움 자리를 신경 쓰지 않음
	Clearance: number?, -- 섬 검사(부지·길·가장자리)에만 더할 여유(땅속에 묻힌 부분이 더 넓은 언덕)
}

local GAP_ANGLES = ParkLayout.gapAngles()
local FOOTPRINTS = ParkLayout.footprints()
local RINGS = { T.INNER_RING, T.OUTER_RING }

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

-- 산책로(안쪽·바깥 고리, 틈 오솔길) 위이거나 너무 가까운지. margin 기본은 ROUTE_MARGIN
function Plan.onRoute(x: number, z: number, pad: number?, margin: number?): boolean
	local m = (pad or 0) + (margin or T.ROUTE_MARGIN)
	local r = math.sqrt(x * x + z * z)
	for _, ring in RINGS do
		if math.abs(r - ring.Radius) <= ring.Width / 2 + m then
			return true
		end
	end
	for _, angle in GAP_ANGLES do
		local dx, dz = math.cos(angle), math.sin(angle)
		local along = x * dx + z * dz
		local side = z * dx - x * dz
		if
			math.abs(side) <= T.TRAIL_WIDTH / 2 + m
			and along >= T.INNER_RING.Radius - m
			and along <= T.OUTER_RING.Radius + m
		then
			return true
		end
	end
	return false
end

-- 섬 잔디 위 자리 검사: 광장·부지·간판·길(ParkLayout) + 산책로 + 섬 가장자리. 막히면 true 와 이유
function Plan.islandBlocked(x: number, z: number, pad: number?, routeMargin: number?): (boolean, string?)
	local p = pad or 0
	local hit, why = ParkLayout.blocked(x, z, p)
	if hit then
		return true, why
	end
	if Plan.onRoute(x, z, p, routeMargin) then
		return true, "route"
	end
	if math.sqrt(x * x + z * z) + p > ISLAND_RADIUS - T.EDGE_MARGIN then
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
	return false
end

local function fits(ctx: Ctx, spec: Spec, x: number, z: number): boolean
	local r = spec.Radius
	local region = spec.Region
	local distance = math.sqrt(x * x + z * z)
	if region == "Island" then
		if Plan.islandBlocked(x, z, r + (spec.Clearance or 0), spec.RouteMargin) then
			return false
		end
	elseif region == "Beach" then
		if distance - r < ISLAND_RADIUS + T.OCEAN.BeachInset or distance + r > T.OCEAN.WallRadius - 0.5 then
			return false
		end
	elseif region == "Field" then
		if distance - r < T.MOUNTAINS.WallRadius + 1.5 then
			return false
		end
	end
	if spec.Tall and inCorridor(x, z, r) then
		return false
	end
	if not spec.Backdrop then
		for _, circle in ctx.Keep do
			local limit = r + circle.R
			if (circle.X - x) ^ 2 + (circle.Z - z) ^ 2 < limit * limit then
				return false
			end
		end
	end
	local layer = spec.Layer or "Solid"
	if layer == "Solid" then
		return not overlaps(ctx, x, z, r, T.SPACING)
	elseif layer == "Patch" then
		for _, other in ctx.Patches do
			local limit = r + other.Radius + 1
			if (other.X - x) ^ 2 + (other.Z - z) ^ 2 < limit * limit then
				return false
			end
		end
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
	elseif item.Layer == "Patch" then
		table.insert(ctx.Patches, item)
	end
end

local function defaultY(region: string): number
	if region == "Beach" then
		return T.OCEAN.BeachTop
	elseif region == "Field" then
		return T.MOUNTAINS.FieldTop
	end
	return T.ISLAND_TOP
end

-- spec 자리에 놓아 보고, 안 되면 jitter 안에서 tries 번 더 흔들어 봄. 끝내 안 되면 nil(Skipped 에 셈)
local function place(ctx: Ctx, rng: Rng, spec: Spec, tries: number?, jitter: number?): Item?
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
				Y = spec.Y or defaultY(spec.Region),
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
			return item
		end
	end
	local key = spec.Zone .. "/" .. spec.Kind
	ctx.Skipped[key] = (ctx.Skipped[key] or 0) + 1
	if Plan.debugSkipped then
		table.insert(Plan.debugSkipped, spec)
	end
	return nil
end

-- 나무 종류와 크기. 반지름은 잎 반지름보다 조금 작게(무리 지은 나무 잎이 살짝 겹치도록)
local TREE_RADIUS = { RoundTree = 3, PineTree = 3.8, PalmTree = 2.4 }
local BUSH_RADIUS = 2.5 -- 덤불(공 셋) 바깥까지
local MOUND_SLOPE = 0.3 -- 잔디 언덕 높이 = 반지름 x 이 값

-- 잔디 언덕(땅에 묻힌 공의 윗부분)을 만드는 공의 반지름. 바닥 반지름 a, 높이 h
function Plan.moundSphere(a: number, h: number): number
	return (a * a + h * h) / (2 * h)
end

-- 잔디 언덕 설명: 묻힌 공 전체가 부지·길·섬 가장자리를 넘지 않게 Clearance 를 둠
local function moundSpec(zone: string, x: number, z: number, radius: number, tint: number): Spec
	local height = radius * MOUND_SLOPE
	return {
		Kind = "Mound",
		Zone = zone,
		Region = "Island",
		X = x,
		Z = z,
		Radius = radius,
		Height = height,
		Tint = tint,
		Clearance = Plan.moundSphere(radius, height) - radius,
	}
end

local function treeSpec(kind: string, zone: string, region: string, x: number, z: number, scale: number, rng: Rng): Spec
	return {
		Kind = kind,
		Zone = zone,
		Region = region,
		X = x,
		Z = z,
		Radius = TREE_RADIUS[kind] * scale,
		Scale = scale,
		Turn = rng:NextNumber(0, TAU),
		Tint = rng:NextNumber(),
		Style = if kind == "PineTree" then 2 else 1, -- 뾰족 나무: 2 = 두 층
		Tall = true,
	}
end

-- 구역별 배치 -------------------------------------------------------------------

-- 안쪽 잔디(광장 ~ 부지 입구): 꽃밭, 입구 쪽 작은 나무, 오솔길 입구 가로등, 벤치, 부지 길 양옆 덤불·꽃밭
local function innerLawn(ctx: Ctx)
	local rng = Rng.new(T.SEED + 100)
	local inner = T.INNER_RING
	local ringIn, ringOut = inner.Radius - inner.Width / 2, inner.Radius + inner.Width / 2
	for j, angle in GAP_ANGLES do
		for _, s in { -1, 1 } do
			local x, z = onAxis(angle, 70 + rng:NextNumber(-1.5, 1.5), s * (9.5 + rng:NextNumber(-0.8, 0.8)))
			place(ctx, rng, {
				Kind = "FlowerBed",
				Zone = "Inner",
				Region = "Island",
				X = x,
				Z = z,
				Radius = rng:NextNumber(2.6, 3.1),
				Turn = rng:NextNumber(0, TAU),
				Style = (j * 2 + (if s > 0 then 1 else 0)) % 6 + 1,
			}, 4, 1.5)

			local scale = rng:NextNumber(0.8, 0.95)
			x, z = onAxis(angle, 101 + rng:NextNumber(-2, 2), s * (13 + rng:NextNumber(-1.5, 1.5)))
			place(ctx, rng, treeSpec("RoundTree", "Inner", "Island", x, z, scale, rng), 4, 2)

			x, z = onAxis(angle, ringOut + 0.9, s * (T.TRAIL_WIDTH / 2 + 1.1))
			place(ctx, rng, {
				Kind = "Lamp",
				Zone = "Inner",
				Region = "Island",
				X = x,
				Z = z,
				Radius = 0.6,
				RouteMargin = 0.2,
			})
		end
		-- 벤치: 오솔길이 시작되는 곳 안쪽(광장 쪽)에서 부지 쪽(바깥)을 바라봄
		local x, z = onAxis(angle, ringIn - 4, 0)
		place(ctx, rng, {
			Kind = "Bench",
			Zone = "Inner",
			Region = "Island",
			X = x,
			Z = z,
			Radius = 2.8,
			Turn = angle,
			RouteMargin = 0.4,
		}, 3, 1)
	end
	-- 광장 → 부지 길 양옆: 광장 쪽 덤불, 입구 쪽 꽃밭
	for i, footprint in FOOTPRINTS do
		for _, s in { -1, 1 } do
			local scale = rng:NextNumber(0.9, 1.1)
			local x, z = onAxis(footprint.Angle, 72 + rng:NextNumber(-1, 1), s * (7.3 + BUSH_RADIUS * scale))
			place(ctx, rng, {
				Kind = "Bush",
				Zone = "Inner",
				Region = "Island",
				X = x,
				Z = z,
				Radius = BUSH_RADIUS * scale,
				Scale = scale,
				Turn = rng:NextNumber(0, TAU),
				Tint = rng:NextNumber(),
				Style = rng:NextInteger(1, 2),
			}, 3, 0.8)
			x, z = onAxis(footprint.Angle, 96, s * 10)
			place(ctx, rng, {
				Kind = "FlowerBed",
				Zone = "Inner",
				Region = "Island",
				X = x,
				Z = z,
				Radius = 2.6,
				Turn = rng:NextNumber(0, TAU),
				Style = (i + 2) % 6 + 1,
			}, 3, 0.8)
		end
	end
end

-- 틈 정원 --------------------------------------------------------------------

type Garden = {
	ctx: Ctx,
	rng: Rng,
	angle: number,
	m: number, -- 좌우 뒤집기(-1 / 1)
}

-- 정원 좌표(rho = 광장 중심에서 틈 방향 거리, side = 옆, m 을 곱해서 뒤집힘)에 장식 하나
local function put(g: Garden, kind: string, rho: number, side: number, radius: number, extra: { [string]: any }?): Item?
	local x, z = onAxis(g.angle, rho, side * g.m)
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

local function tree(g: Garden, kind: string, rho: number, side: number, scale: number): Item?
	return put(g, kind, rho, side, TREE_RADIUS[kind] * scale, { Scale = scale, Tall = true, Style = 2 })
end

-- (rho, side) 에 벤치를 두고 (tRho, tSide) 를 바라보게
local function bench(g: Garden, rho: number, side: number, tRho: number, tSide: number): Item?
	local x, z = onAxis(g.angle, rho, side * g.m)
	local tx, tz = onAxis(g.angle, tRho, tSide * g.m)
	return put(g, "Bench", rho, side, 2.8, { Turn = facing(x, z, tx, tz), RouteMargin = 0.6 })
end

local function lamp(g: Garden, rho: number, side: number): Item?
	return put(g, "Lamp", rho, side, 0.6, { RouteMargin = 0.3 })
end

local function bed(g: Garden, rho: number, side: number, radius: number, style: number): Item?
	return put(g, "FlowerBed", rho, side, radius, { Style = style })
end

local function bush(g: Garden, rho: number, side: number, scale: number): Item?
	return put(g, "Bush", rho, side, BUSH_RADIUS * scale, { Scale = scale, Style = g.rng:NextInteger(1, 2) })
end

local function rock(g: Garden, rho: number, side: number, scale: number): Item?
	return put(g, "Rock", rho, side, 1.8 * scale, { Scale = scale, Style = g.rng:NextInteger(1, 2) })
end

local THEMES: { [string]: (Garden) -> () } = {}

-- 분수 광장: 오솔길 옆 둥근 분수 + 분수를 보는 벤치 둘 + 꽃밭 + 토피어리
THEMES.Fountain = function(g)
	put(g, "Fountain", 176, 14, 6)
	bench(g, 176, 23.5, 176, 14)
	bench(g, 162, 15, 176, 14)
	lamp(g, 166, 5.2)
	bed(g, 190, -12, 3.2, 1)
	bed(g, 160, -9, 2.8, 4)
	put(g, "Topiary", 138, 6, 1.4, { Scale = 1 })
	put(g, "Topiary", 138, -6, 1.4, { Scale = 1 })
	tree(g, "RoundTree", 194, 26, 1.15)
	tree(g, "RoundTree", 186, -24, 1.05)
end

-- 꽃밭: 크기·색이 다른 꽃밭 여러 개 + 벤치 + 덤불
THEMES.Flowers = function(g)
	bed(g, 140, 7.5, 2.8, 1)
	bed(g, 142, -7.5, 2.6, 2)
	bed(g, 158, 10, 3.4, 3)
	bed(g, 160, -13, 3, 5)
	bed(g, 176, 16, 3.6, 4)
	bed(g, 178, -9, 3.2, 6)
	bed(g, 194, 9, 3, 2)
	bed(g, 192, -25, 3.4, 1)
	lamp(g, 151, -5.2)
	bench(g, 186, -17, 186, 0)
	bush(g, 195, 24, 1.1)
	tree(g, "RoundTree", 186, 26, 1.2)
end

-- 작은 숲: 동그란 나무 무리 + 나무 아래 벤치 + 바위 + 덤불
THEMES.Grove = function(g)
	tree(g, "RoundTree", 146, 8.5, 0.9)
	tree(g, "RoundTree", 160, -12, 1.1)
	tree(g, "RoundTree", 175, 16, 1.2)
	tree(g, "RoundTree", 188, -21, 1.05)
	tree(g, "RoundTree", 196, 7, 1.1)
	tree(g, "RoundTree", 190, 28, 0.95)
	bench(g, 168, 7.2, 168, -10)
	lamp(g, 172, -5.5)
	rock(g, 181, -9, 1.1)
	bush(g, 152, -7, 1)
	bush(g, 170, -19, 1.1)
end

-- 연못: 수련 연못 + 연못을 보는 벤치 + 가로등 + 둘레 덤불, 맞은편에 꽃밭과 나무
THEMES.Pond = function(g)
	put(g, "Pond", 176, 14, 8)
	bench(g, 159, 9.5, 176, 14)
	lamp(g, 157, 14.5)
	bush(g, 192, 6.5, 1)
	bush(g, 190, 25, 1.2)
	bush(g, 168, 21, 0.9)
	rock(g, 184, 23.5, 0.9)
	bed(g, 170, -10, 3, 3)
	bush(g, 150, -8.5, 0.9)
	tree(g, "RoundTree", 191, -20, 1.1)
end

-- 소풍: 피크닉 탁자 둘(돗자리·바구니) + 그늘 나무 + 꽃밭
THEMES.Picnic = function(g)
	put(g, "Picnic", 170, 12, 5.5, { Turn = g.angle + math.pi / 2 })
	put(g, "Picnic", 186, -14, 5.5, { Turn = g.angle - math.pi / 2, Style = 2 })
	tree(g, "RoundTree", 190, 20, 1.3)
	tree(g, "RoundTree", 160, -12, 1)
	lamp(g, 150, 5.2)
	bed(g, 196, 5.5, 2.8, 5)
	bush(g, 146, -6.5, 0.9)
	bush(g, 176, -24, 1.1)
end

-- 바위 정원: 뾰족 나무 + 크고 작은 바위 + 잔디 언덕
THEMES.Rockery = function(g)
	tree(g, "PineTree", 148, 8.5, 0.9)
	tree(g, "PineTree", 168, -14, 1.1)
	tree(g, "PineTree", 186, 21, 1.2)
	tree(g, "PineTree", 194, -27, 1.05)
	tree(g, "PineTree", 178, 7.5, 0.8)
	rock(g, 158, -8, 1.2)
	rock(g, 180, 14, 1.4)
	rock(g, 190, -10, 1)
	rock(g, 166, 19, 0.9)
	local mx, mz = onAxis(g.angle, 194, 12 * g.m)
	place(g.ctx, g.rng, moundSpec("Gardens", mx, mz, 4.5, g.rng:NextNumber()), 3, 1.5)
	lamp(g, 158, 5.2)
end

-- 토피어리 길: 오솔길 양옆에 막대 사탕 모양 나무 줄 + 꽃밭 + 벤치
THEMES.Topiary = function(g)
	for k, rho in { 132, 147, 162, 177, 192 } do
		for _, side in { -1, 1 } do
			put(g, "Topiary", rho, side * 6.2, 1.4, { Scale = if k % 2 == 0 then 1.15 else 1, Style = k % 2 + 1 })
		end
	end
	bed(g, 162, 15, 3, 6)
	bed(g, 170, -17, 3.2, 3)
	bench(g, 186, 16, 186, 0)
	lamp(g, 154, -11)
	tree(g, "RoundTree", 194, -24, 1.15)
end

-- 수련 연못 둘(큰 것 + 작은 것) + 벤치 + 나무
THEMES.Lily = function(g)
	put(g, "Pond", 168, -12, 7, { Style = 2 })
	put(g, "Pond", 190, 16, 5.5, { Style = 2 })
	bench(g, 186, -8, 168, -12)
	lamp(g, 176, 5.2)
	tree(g, "RoundTree", 150, 9, 0.95)
	tree(g, "RoundTree", 194, -28, 1.2)
	bush(g, 176, 22, 1)
	bed(g, 152, -8, 2.6, 2)
end

local function gardens(ctx: Ctx)
	for j, angle in GAP_ANGLES do
		local rng = Rng.new(T.SEED + 200 + j)
		local theme = T.GARDEN_THEMES[(j - 1) % #T.GARDEN_THEMES + 1]
		local build = THEMES[theme]
		if build then
			build({ ctx = ctx, rng = rng, angle = angle, m = rng:Sign() })
		end
	end
end

-- 부지 뒤 숲띠 -------------------------------------------------------------------

local function beltTreeKind(variant: Variant, distance: number, rng: Rng): string
	if variant == "Ocean" then
		if distance > 232 and rng:NextNumber() < T.OCEAN.BeltPalmChance then
			return "PalmTree"
		end
		return if rng:NextNumber() < 0.2 then "PineTree" else "RoundTree"
	end
	return if rng:NextNumber() < T.MOUNTAINS.BeltPineChance then "PineTree" else "RoundTree"
end

local function belt(ctx: Ctx, variant: Variant)
	local rng = Rng.new(T.SEED + 300)
	local outer = T.OUTER_RING
	local ringOut = outer.Radius + outer.Width / 2
	local beltIn, beltOut = ringOut, ISLAND_RADIUS - T.EDGE_MARGIN

	-- 오솔길이 바깥 고리와 만나는 곳: 바깥쪽 양옆 가로등
	for _, angle in GAP_ANGLES do
		for _, s in { -1, 1 } do
			local x, z = onAxis(angle, ringOut + 0.9, s * 6)
			place(ctx, rng, {
				Kind = "Lamp",
				Zone = "Belt",
				Region = "Island",
				X = x,
				Z = z,
				Radius = 0.6,
				RouteMargin = 0.2,
			})
		end
	end

	-- 틈 방향 시야 안의 낮은 잔디 언덕(나무 무리보다 먼저 자리를 잡음)
	if T.BELT.CorridorMounds then
		for _, angle in GAP_ANGLES do
			local x, z = onAxis(angle, rng:NextNumber(226, 232), rng:NextNumber(-7, 7))
			place(ctx, rng, moundSpec("Belt", x, z, rng:NextNumber(5, 6.5), rng:NextNumber()), 4, 3)
		end
	end

	for _, footprint in FOOTPRINTS do
		-- 부지 뒤 벤치(부지를 바라봄) + 양옆 덤불
		local x, z = onAxis(footprint.Angle, ringOut + 3.3, 0)
		place(ctx, rng, {
			Kind = "Bench",
			Zone = "Belt",
			Region = "Island",
			X = x,
			Z = z,
			Radius = 2.8,
			Turn = footprint.Angle + math.pi,
			RouteMargin = 0.4,
		})
		for _, s in { -1, 1 } do
			local scale = rng:NextNumber(0.9, 1.15)
			x, z = onAxis(footprint.Angle, ringOut + 1.9 + BUSH_RADIUS * scale, s * 6.5)
			place(ctx, rng, {
				Kind = "Bush",
				Zone = "Belt",
				Region = "Island",
				X = x,
				Z = z,
				Radius = BUSH_RADIUS * scale,
				Scale = scale,
				Turn = rng:NextNumber(0, TAU),
				Tint = rng:NextNumber(),
				Style = rng:NextInteger(1, 2),
			}, 3, 1)
		end

		-- 나무 무리: 부지 방향 가운데·양옆으로 벌어져서
		local groves = T.BELT.Groves[variant] or T.BELT.Groves.Ocean
		for k = 1, groves.PerPlot do
			local offset = (k - (groves.PerPlot + 1) / 2) * math.rad(groves.Spread)
			local centerAngle = footprint.Angle + offset + math.rad(rng:NextNumber(-2, 2))
			local centerDistance = rng:NextNumber(224, 234)
			local cx, cz = polar(centerAngle, centerDistance)
			for _ = 1, rng:NextInteger(T.BELT.GroveTrees[1], T.BELT.GroveTrees[2]) do
				local a = rng:NextNumber(0, TAU)
				local d = rng:NextNumber(0, T.BELT.GroveRadius)
				local tx, tz = cx + math.cos(a) * d, cz + math.sin(a) * d
				local kind = beltTreeKind(variant, math.sqrt(tx * tx + tz * tz), rng)
				local range = if kind == "PalmTree" then T.BELT.PalmScale else T.BELT.TreeScale
				local scale = rng:NextNumber(range[1], range[2])
				local spec = treeSpec(kind, "Belt", "Island", tx, tz, scale, rng)
				if kind == "PalmTree" then
					spec.Turn = math.atan2(tz, tx) + rng:NextNumber(-0.6, 0.6) -- 바다 쪽으로 기움
				end
				place(ctx, rng, spec, 5, 5)
			end
		end
	end

	local function scatter(count: number, make: (x: number, z: number) -> Spec)
		for _ = 1, count do
			local a = rng:NextNumber(0, TAU)
			local d = rng:NextNumber(beltIn, beltOut)
			local x, z = polar(a, d)
			place(ctx, rng, make(x, z), 6, 6)
		end
	end
	scatter(T.BELT.Rocks, function(x, z)
		local scale = rng:NextNumber(0.8, 1.5)
		return {
			Kind = "Rock",
			Zone = "Belt",
			Region = "Island",
			X = x,
			Z = z,
			Radius = 1.8 * scale,
			Scale = scale,
			Turn = rng:NextNumber(0, TAU),
			Tint = rng:NextNumber(),
			Style = rng:NextInteger(1, 2),
		}
	end)
	scatter(T.BELT.Mounds, function(x, z)
		return moundSpec("Belt", x, z, rng:NextNumber(4.5, 7.5), rng:NextNumber())
	end)
	scatter(T.BELT.Bushes, function(x, z)
		local scale = rng:NextNumber(0.9, 1.3)
		return {
			Kind = "Bush",
			Zone = "Belt",
			Region = "Island",
			X = x,
			Z = z,
			Radius = BUSH_RADIUS * scale,
			Scale = scale,
			Turn = rng:NextNumber(0, TAU),
			Tint = rng:NextNumber(),
			Style = rng:NextInteger(1, 2),
		}
	end)
end

-- 잔디 색 무늬(얇은 원판): 다른 장식 아래에 깔려도 되지만 산책로·부지·서로는 비켜 감
local function patches(ctx: Ctx)
	local rng = Rng.new(T.SEED + 400)
	local zones = {
		{ Zone = "Inner", Count = T.PATCHES.Inner, From = 64, To = 112 },
		{ Zone = "Gardens", Count = T.PATCHES.Gardens, From = 122, To = 204 },
		{ Zone = "Belt", Count = T.PATCHES.Belt, From = 213, To = ISLAND_RADIUS - T.EDGE_MARGIN },
	}
	for _, zone in zones do
		local placed = 0
		local attempts = 0
		while placed < zone.Count and attempts < zone.Count * 30 do
			attempts += 1
			local a = rng:NextNumber(0, TAU)
			local d = rng:NextNumber(zone.From, zone.To)
			local x, z = polar(a, d)
			local spec: Spec = {
				Kind = "Patch",
				Zone = zone.Zone,
				Region = "Island",
				X = x,
				Z = z,
				Radius = rng:NextNumber(4, 10),
				Tint = rng:NextNumber(),
				Style = rng:NextInteger(1, 3),
				Layer = "Patch",
			}
			if fits(ctx, spec, x, z) then
				place(ctx, rng, spec)
				placed += 1
			end
		end
	end
end

-- 바다 가장자리 ------------------------------------------------------------------

local function ocean(ctx: Ctx)
	local O = T.OCEAN
	local rng = Rng.new(T.SEED + 500)
	local beachMid = (ISLAND_RADIUS + O.WallRadius) / 2

	-- 등대(모래사장 끝, 틈 방향이라 광장에서 보임)
	local lighthouseAngle = math.rad(O.LighthouseAngle)
	local x, z = polar(lighthouseAngle, O.WallRadius - 6.5)
	place(ctx, rng, {
		Kind = "Lighthouse",
		Zone = "Beach",
		Region = "Free",
		X = x,
		Z = z,
		Y = O.BeachTop,
		Radius = 5.5,
		Turn = lighthouseAngle + math.pi,
	})

	-- 부두: 모래사장에서 바다로. 모래 위 부분은 다른 장식이 비켜 가게 막아 둠
	local pierAngle = math.rad(O.PierAngle)
	local startDistance = ISLAND_RADIUS + 7
	x, z = polar(pierAngle, startDistance)
	place(ctx, rng, {
		Kind = "Pier",
		Zone = "Beach",
		Region = "Free",
		X = x,
		Z = z,
		Y = O.BeachTop,
		Radius = O.PierWidth / 2,
		Turn = pierAngle,
		Height = O.PierLength,
		Layer = "Free",
	})
	for d = startDistance, startDistance + 14, 3.5 do
		local kx, kz = polar(pierAngle, d)
		table.insert(ctx.Keep, { X = kx, Z = kz, R = O.PierWidth / 2 + 1 })
	end

	-- 모래사장 야자수(바다 쪽으로 기움), 파라솔, 바위
	for k = 1, O.BeachPalms do
		local a = (k - 0.5) / O.BeachPalms * TAU + rng:NextNumber(-0.08, 0.08)
		local d = rng:NextNumber(ISLAND_RADIUS + 4.5, O.WallRadius - 4)
		local px, pz = polar(a, d)
		local scale = rng:NextNumber(1, 1.35)
		local spec = treeSpec("PalmTree", "Beach", "Beach", px, pz, scale, rng)
		spec.Turn = a + rng:NextNumber(-0.5, 0.5)
		place(ctx, rng, spec, 5, 6)
	end
	for _ = 1, O.Umbrellas do
		local a = rng:NextNumber(0, TAU)
		local ux, uz = polar(a, beachMid + rng:NextNumber(-1.5, 1.5))
		place(ctx, rng, {
			Kind = "Umbrella",
			Zone = "Beach",
			Region = "Beach",
			X = ux,
			Z = uz,
			Radius = 3,
			Turn = a + math.pi + rng:NextNumber(-0.4, 0.4),
			Style = rng:NextInteger(1, 4),
		}, 6, 8)
	end
	for _ = 1, O.BeachRocks do
		local a = rng:NextNumber(0, TAU)
		local rx, rz = polar(a, rng:NextNumber(ISLAND_RADIUS + 3, O.WallRadius - 2))
		local scale = rng:NextNumber(0.8, 1.4)
		place(ctx, rng, {
			Kind = "Rock",
			Zone = "Beach",
			Region = "Beach",
			X = rx,
			Z = rz,
			Radius = 1.8 * scale,
			Scale = scale,
			Turn = rng:NextNumber(0, TAU),
			Tint = rng:NextNumber(),
			Style = rng:NextInteger(1, 2),
		}, 4, 4)
	end

	-- 배(얕은 물이면 얕은 물 위, 아니면 먼바다 위)
	for _, boat in O.Boats do
		local bx, bz = polar(math.rad(boat.Angle), boat.Distance)
		place(ctx, rng, {
			Kind = "Boat",
			Zone = "Sea",
			Region = "Free",
			X = bx,
			Z = bz,
			Y = if boat.Distance < O.ShallowRadius then O.ShallowTop else O.DeepTop,
			Radius = 4 * boat.Scale,
			Scale = boat.Scale,
			Turn = math.rad(boat.Heading),
			Tint = rng:NextNumber(),
			Style = rng:NextInteger(1, 3),
			Layer = "Free",
		})
	end

	-- 먼 작은 섬: 모래 + 풀 + 야자수 2~3 + 바위
	local grassTop = O.DeepTop + O.IsletGrassRise
	for _, islet in O.Islets do
		local a = math.rad(islet.Angle)
		local ix, iz = polar(a, islet.Distance)
		place(ctx, rng, {
			Kind = "Islet",
			Zone = "Sea",
			Region = "Free",
			X = ix,
			Z = iz,
			Y = O.DeepTop,
			Radius = islet.Radius,
			Tint = rng:NextNumber(),
			Layer = "Free",
		})
		local palms = rng:NextInteger(2, 3)
		for k = 1, palms do
			local pa = rng:NextNumber(0, TAU)
			local pd = rng:NextNumber(0.05, 0.35) * islet.Radius
			local px, pz = ix + math.cos(pa) * pd, iz + math.sin(pa) * pd
			local scale = islet.Radius / 24 * rng:NextNumber(0.9, 1.2)
			place(ctx, rng, {
				Kind = "PalmTree",
				Zone = "Sea",
				Region = "Free",
				X = px,
				Z = pz,
				Y = grassTop,
				Radius = 1,
				Scale = scale,
				Turn = pa + rng:NextNumber(-0.4, 0.4),
				Tint = rng:NextNumber(),
				Style = k,
				Layer = "Free",
			})
		end
		local ra = rng:NextNumber(0, TAU)
		local rx, rz = ix + math.cos(ra) * islet.Radius * 0.75, iz + math.sin(ra) * islet.Radius * 0.75
		local rockScale = islet.Radius / 12
		place(ctx, rng, {
			Kind = "Rock",
			Zone = "Sea",
			Region = "Free",
			X = rx,
			Z = rz,
			Y = O.DeepTop + O.IsletSandRise,
			Radius = 1,
			Scale = rockScale,
			Turn = rng:NextNumber(0, TAU),
			Tint = rng:NextNumber(),
			Style = 2,
			Layer = "Free",
		})
	end
end

-- 산맥 가장자리 ------------------------------------------------------------------

type Vec = { number }

local function sub(a: Vec, b: Vec): Vec
	return { a[1] - b[1], a[2] - b[2], a[3] - b[3] }
end

local function cross(a: Vec, b: Vec): Vec
	return { a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1] }
end

local function unit(a: Vec): Vec
	local m = math.sqrt(a[1] * a[1] + a[2] * a[2] + a[3] * a[3])
	return { a[1] / m, a[2] / m, a[3] / m }
end

local function along(a: Vec, b: Vec, t: number, lift: Vec, amount: number): Vec
	return {
		a[1] + (b[1] - a[1]) * t + lift[1] * amount,
		a[2] + (b[2] - a[2]) * t + lift[2] * amount,
		a[3] + (b[3] - a[3]) * t + lift[3] * amount,
	}
end

-- 여러 삼각 면으로 된 뾰족한 산(바닥 꼭짓점 Faces 개 + 꼭대기) + 꼭대기 눈
local function peak(rng: Rng, angle: number, distance: number): Peak
	local P = T.MOUNTAINS.Peaks
	local ground = T.MOUNTAINS.FieldTop - 2 -- 바닥 모서리는 들판 아래로 묻음
	local cx, cz = polar(angle, distance)
	local baseRadius = rng:NextNumber(P.BaseRadius[1], P.BaseRadius[2])
	local height = rng:NextNumber(P.Height[1], P.Height[2])
	local apex: Vec = {
		cx + rng:NextNumber(-0.15, 0.15) * baseRadius,
		T.MOUNTAINS.FieldTop + height,
		cz + rng:NextNumber(-0.15, 0.15) * baseRadius,
	}
	local base: { Vec } = {}
	local start = rng:NextNumber(0, TAU)
	for k = 1, P.Faces do
		local a = start + (k - 1 + rng:NextNumber(-0.25, 0.25)) / P.Faces * TAU
		local r = baseRadius * rng:NextNumber(0.85, 1.1)
		table.insert(base, { cx + math.cos(a) * r, ground, cz + math.sin(a) * r })
	end
	local snow = rng:NextNumber(P.Snow[1], P.Snow[2])
	local toCenterX, toCenterZ = -cx / distance, -cz / distance
	local triangles: { Triangle } = {}
	for k = 1, P.Faces do
		local b, c = base[k], base[k % P.Faces + 1]
		local normal = unit(cross(sub(b, apex), sub(c, apex)))
		-- 바깥(산 중심에서 멀어지는 쪽)을 보게
		local mid = { (b[1] + c[1]) / 2 - cx, 0, (b[3] + c[3]) / 2 - cz }
		if normal[1] * mid[1] + normal[3] * mid[3] < 0 then
			normal = { -normal[1], -normal[2], -normal[3] }
		end
		local flat = math.sqrt(normal[1] ^ 2 + normal[3] ^ 2)
		local facingPark = (normal[1] * toCenterX + normal[3] * toCenterZ) / math.max(flat, 1e-6)
		if facingPark >= P.CullDot then
			local tint = rng:NextNumber()
			table.insert(triangles, { A = apex, B = b, C = c, Snow = false, Tint = tint, Thickness = P.RockThickness })
			table.insert(triangles, {
				A = along(apex, apex, 0, normal, P.SnowLift),
				B = along(apex, b, snow, normal, P.SnowLift),
				C = along(apex, c, snow, normal, P.SnowLift),
				Snow = true,
				Tint = tint,
				Thickness = P.SnowThickness,
			})
		end
	end
	return { X = cx, Z = cz, Height = height, Triangles = triangles }
end

local function mountains(ctx: Ctx, result: Result)
	local M = T.MOUNTAINS
	local rng = Rng.new(T.SEED + 600)
	local waterfallAngle = math.rad(M.WaterfallAngle)

	-- 폭포 절벽 + 물웅덩이 + 섬 쪽으로 흐르는 개울(다른 장식이 비켜 감)
	local fx, fz = polar(waterfallAngle, M.WaterfallDistance)
	place(ctx, rng, {
		Kind = "Waterfall",
		Zone = "Mountains",
		Region = "Free",
		X = fx,
		Z = fz,
		Y = M.FieldTop,
		Radius = 20,
		Turn = waterfallAngle + math.pi,
		Height = M.WaterfallHeight,
		Layer = "Free",
	})
	table.insert(ctx.Keep, { X = fx, Z = fz, R = 22 })
	local poolDistance = M.WaterfallDistance - 17
	local px, pz = polar(waterfallAngle, poolDistance)
	table.insert(ctx.Keep, { X = px, Z = pz, R = 12 })
	local points = {
		{ poolDistance - 7, 0 },
		{ poolDistance - 16, 3 },
		{ poolDistance - 25, -2.5 },
		{ ISLAND_RADIUS + 0.5, 1 },
	}
	for k = 1, #points - 1 do
		local x1, z1 = onAxis(waterfallAngle, points[k][1], points[k][2])
		local x2, z2 = onAxis(waterfallAngle, points[k + 1][1], points[k + 1][2])
		table.insert(result.Stream, { X1 = x1, Z1 = z1, X2 = x2, Z2 = z2, Width = 4.5, Top = M.FieldTop + 0.12 })
		table.insert(ctx.Keep, { X = (x1 + x2) / 2, Z = (z1 + z2) / 2, R = 6.5 })
		table.insert(ctx.Keep, { X = x2, Z = z2, R = 4.5 })
	end

	-- 숲 가장자리 나무 줄(벽 바로 바깥)
	for k = 1, M.ForestTrees do
		local a = (k - 0.5) / M.ForestTrees * TAU + rng:NextNumber(-0.04, 0.04)
		local d = rng:NextNumber(M.ForestFrom, M.ForestTo)
		local x, z = polar(a, d)
		local kind = if rng:NextNumber() < M.ForestPineChance then "PineTree" else "RoundTree"
		local scale = rng:NextNumber(1.3, 2.1)
		local spec = treeSpec(kind, "Forest", "Field", x, z, scale, rng)
		spec.Tall = false -- 틈 시야는 섬 안에서만 비움
		spec.Style = 1 -- 먼 숲 뾰족 나무는 긴 뿔 한 층
		place(ctx, rng, spec, 4, 5)
	end

	-- 그 뒤 나무 덩어리(반쯤 묻힌 큰 공): 멀리서 보면 빽빽한 숲
	for _ = 1, M.Blobs do
		local a = rng:NextNumber(0, TAU)
		local d = rng:NextNumber(M.BlobFrom, M.BlobTo)
		local x, z = polar(a, d)
		local diameter = rng:NextNumber(18, 32)
		place(ctx, rng, {
			Kind = "Blob",
			Zone = "Forest",
			Region = "Field",
			X = x,
			Z = z,
			-- 간격용 반지름은 땅 위 둘레(약 0.49 x 지름)보다 작게: 나무 옆에 붙되 나무를 삼키지는 않게
			Radius = diameter * 0.32,
			Scale = diameter,
			Height = diameter * rng:NextNumber(0.55, 0.7),
			Tint = rng:NextNumber(),
		}, 4, 8)
	end

	-- 초록 언덕 고리(폭포가 언덕 사이 골짜기에 오도록 반 칸 비켜서)
	local H = M.Hills
	for k = 1, H.Count do
		local a = waterfallAngle + (k - 0.5) / H.Count * TAU + rng:NextNumber(-0.04, 0.04)
		local d = H.Distance + (if k % 2 == 0 then H.Stagger else 0) + rng:NextNumber(-8, 8)
		if k == 1 or k == H.Count then
			-- 폭포 양옆 언덕은 폭포 앞(물웅덩이·개울)을 덮지 않게 조금 뒤로만
			a = waterfallAngle + (k - 0.5) / H.Count * TAU
			d = H.Distance + 6
		end
		local x, z = polar(a, d)
		local diameter = rng:NextNumber(H.Diameter[1], H.Diameter[2])
		local top = rng:NextNumber(H.Top[1], H.Top[2])
		local radius = diameter / 2
		place(ctx, rng, {
			Kind = "Hill",
			Zone = "Mountains",
			Region = "Free",
			X = x,
			Z = z,
			Y = M.FieldTop,
			Radius = math.sqrt(radius * radius - (radius - top) ^ 2),
			Scale = diameter,
			Height = top,
			Tint = rng:NextNumber(),
			Layer = "Free",
			Backdrop = true,
		})
	end

	-- 눈 덮인 산(폭포 방향에 하나가 오게)
	local P = M.Peaks
	for k = 0, P.Count - 1 do
		local a = waterfallAngle + k / P.Count * TAU + math.rad(rng:NextNumber(-3, 3))
		local d = P.Distance + (if k % 2 == 1 then P.Stagger else 0) + rng:NextNumber(-12, 12)
		table.insert(result.Peaks, peak(rng, a, d))
	end
end

-- 계획 만들기 -------------------------------------------------------------------

-- 디버그: 표를 넣어 두면 못 놓은 장식 설명(Spec)을 모아 둠
Plan.debugSkipped = nil :: { any }?

-- 알 수 없는 이름이면 기본(Ocean)
function Plan.variant(name: string?): Variant
	for _, variant in Plan.VARIANTS do
		if variant == name then
			return variant
		end
	end
	return Plan.DEFAULT_VARIANT
end

function Plan.make(variantName: string?): Result
	local variant = Plan.variant(variantName)
	local edge = if variant == "Ocean" then T.OCEAN else T.MOUNTAINS
	local result: Result = {
		Variant = variant,
		Items = {},
		Rings = {},
		Trails = {},
		Stream = {},
		Peaks = {},
		Wall = { Radius = edge.WallRadius, Height = edge.WallHeight, Segments = edge.WallSegments },
		Skipped = {},
	}
	for _, ring in RINGS do
		table.insert(
			result.Rings,
			{ Radius = ring.Radius, Width = ring.Width, Segments = ring.Segments, Top = T.ROUTE_TOP }
		)
	end
	for _, angle in GAP_ANGLES do
		local x1, z1 = polar(angle, T.INNER_RING.Radius)
		local x2, z2 = polar(angle, T.OUTER_RING.Radius)
		table.insert(result.Trails, { X1 = x1, Z1 = z1, X2 = x2, Z2 = z2, Width = T.TRAIL_WIDTH, Top = T.ROUTE_TOP })
	end

	local ctx: Ctx = { Items = result.Items, Cells = {}, Big = {}, Patches = {}, Keep = {}, Skipped = result.Skipped }
	-- 큰 것(가장자리 명물)부터 놓고, 작은 장식이 사이를 채움
	if variant == "Ocean" then
		ocean(ctx)
	else
		mountains(ctx, result)
	end
	innerLawn(ctx)
	gardens(ctx)
	belt(ctx, variant)
	patches(ctx)
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
