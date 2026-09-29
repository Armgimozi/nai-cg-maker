--!strict
-- 섬 지형(순수 계산: Instance 없이 숫자만). 해안선·땅 높이·재질과 지형 복셀 표를 만듭니다.
-- Scenery/init.luau 가 이 표를 Workspace.Terrain 에 씁니다(WriteVoxelChannels, 안 되면 WriteVoxels).
--
-- 높이(광장 중심에서의 거리 r):
--   r <= 214          공원(광장·부지·길·산책로): 땅 윗면이 정확히 y = 0(복셀 경계라 평평). 파트가 그대로 올라앉음
--   214 ~ 풀밭 끝       부지 뒤 숲띠: 낮고 둥근 잔디 언덕(최고 4). 풀밭 끝은 234 이상
--   풀밭 끝 ~ 물가      모래사장(물가 = 해안선 245~292, 노이즈로 구불구불 + 등대 곶 + 넓은 모래사장 두 곳)
--   물가 너머           얕은 모래 턱(폭 16~46, 물 깊이 3 = 청록 물빛) → 깊은 바다 바닥(y -24)
-- 물 높이 y = -4(복셀 경계). 먼 바다(한 변 3072)는 FillBlock, 섬 둘레(한 변 784)와 먼 작은 섬은 복셀 표.
-- 물가 바위(지형 Rock)와 먼 작은 섬 모양도 여기서 정합니다(배치 계획 Plan 이 이 모양을 보고 장식을 놓음).
-- 모든 모양은 고정 오프셋 math.noise 라서 서버·미리보기·테스트에서 항상 같습니다.

local Island = {}

local TAU = math.pi * 2

-- 기준 값 ------------------------------------------------------------------------
Island.VOXEL = 4 -- 지형 복셀 한 변(스터드). 아래 높이 값은 모두 이 배수(복셀 경계)
Island.WATER_LEVEL = -4 -- 바다 물 윗면
Island.SEA_FLOOR = -24 -- 먼 바다 바닥 윗면 = 섬 복셀 표 맨 아래
Island.FLOOR_BOTTOM = -28 -- 먼 바다 바닥 판 밑면(FillBlock)
Island.TOP = 4 -- 섬 복셀 표 맨 위(= 숲띠 언덕 최고 높이)
Island.FLAT_RADIUS = 214 -- 이 안은 땅 윗면이 정확히 0(바깥 산책로 바깥 가장자리 212 + 2)
Island.GRASS_MIN = 234 -- 풀밭 끝(모래 시작)의 최소 반지름(바깥 산책로 + 22)
Island.COAST_MIN = 245 -- 해안선(물가) 반지름 범위
Island.COAST_MAX = 292
Island.REGION_HALF = 392 -- 섬 복셀 표: 원점 중심 한 변 784(이 밖은 깊은 바다 바닥)
Island.OCEAN_HALF = 1536 -- 먼 바다: 원점 중심 한 변 3072(반지름 1500 까지 모든 방향)
Island.OCEAN_TILE = 1024 -- 먼 바다 FillBlock 한 번 크기
-- 비상 바닥(default.project.json 의 FallbackGround 원기둥): 지형이 안 만들어져도 스폰·부지 밑이 허공이 아니게.
-- 윗면 y -0.5, 반지름 225(풀밭 끝 234 보다 안쪽)라서 지형이 있으면 땅속에 완전히 묻혀 안 보임
Island.FALLBACK_RADIUS = 225
Island.FALLBACK_TOP = -0.5

local MOUND_HEIGHT = 4 -- 숲띠 잔디 언덕 최고 높이(= TOP)
local SHALLOW_DEPTH = 3 -- 모래 턱 끝의 물 깊이
local DROP_SLOPE = 0.5 -- 모래 턱 너머 깊은 바다로 내려가는 기울기

-- 물가 명물 방향(도): 등대 곶(광장에서 315도 틈 정원 사이로 보임), 넓은 모래사장 두 곳(부두·파라솔)
Island.LIGHTHOUSE_ANGLE = 315
Island.PIER_ANGLE = 135
local HEADLAND = { Angle = math.rad(315), Width = math.rad(9), Bulge = 13 }
local BEACHES = {
	{ Angle = math.rad(150), Width = math.rad(38), Bulge = 8, Extra = 9 },
	{ Angle = math.rad(28), Width = math.rad(30), Bulge = 5, Extra = 7 },
}

-- 먼 작은 섬(모래 + 풀 언덕). Radius = 평균 반지름(물가), Stretch = 길쭉한 정도(긴 축 / 평균, 넓이는 같게),
-- Axis = 긴 축 방향(도), Hill = 풀 언덕 가운데가 섬 가운데에서 치우친 정도(반지름 비율, 치우친 방향은 Axis + 90)
Island.ISLETS = {
	{ Angle = 205, Distance = 560, Radius = 30, Stretch = 1.35, Axis = 40, Hill = 0.18 },
	{ Angle = 330, Distance = 720, Radius = 42, Stretch = 1.25, Axis = 100, Hill = -0.2 },
	{ Angle = 42, Distance = 640, Radius = 26, Stretch = 1.45, Axis = 150, Hill = 0.15 },
	{ Angle = 112, Distance = 880, Radius = 55, Stretch = 1.3, Axis = 10, Hill = 0.22 },
	{ Angle = 268, Distance = 980, Radius = 48, Stretch = 1.4, Axis = 75, Hill = -0.18 },
	{ Angle = 160, Distance = 700, Radius = 34, Stretch = 1.2, Axis = 125, Hill = 0.2 },
}

-- 도움 함수 ------------------------------------------------------------------------

local function smooth(t: number): number
	local c = math.clamp(t, 0, 1)
	return c * c * (3 - 2 * c)
end

-- 두 값 중 큰 값을 부드럽게(k 만큼 둥글게): 경계가 원호로 딱 잘리지 않게
local function smoothMax(a: number, b: number, k: number): number
	return (a + b + math.sqrt((a - b) * (a - b) + k * k)) / 2
end

-- 원 둘레를 따라 매끄럽게 변하는 노이즈(한 바퀴 돌면 제자리). 대략 -0.45 ~ 0.65
local function around(angle: number, freq: number, seed: number): number
	return math.noise(math.cos(angle) * freq + seed, math.sin(angle) * freq - seed * 0.7, seed * 0.31 + 0.5)
end

-- center 방향에서 1, width(라디안) 밖에서 0 인 부드러운 혹
local function bump(angle: number, center: number, width: number): number
	local d = math.abs(math.atan2(math.sin(angle - center), math.cos(angle - center)))
	if d >= width then
		return 0
	end
	local t = d / width
	return (1 - t * t) ^ 2
end

-- 해안선·모래사장 ------------------------------------------------------------------

-- 물가(해안선) 반지름(정확한 식): 두 겹 노이즈 + 등대 곶 + 넓은 모래사장 쪽 불룩
local function coastExact(angle: number): number
	local n = around(angle, 1.6, 3.7) * 0.7 + around(angle, 4.2, 8.9) * 0.3
	local r = 263 + 29 * n + HEADLAND.Bulge * bump(angle, HEADLAND.Angle, HEADLAND.Width)
	for _, beach in BEACHES do
		r += beach.Bulge * bump(angle, beach.Angle, beach.Width)
	end
	return math.clamp(r, Island.COAST_MIN, Island.COAST_MAX)
end

-- 모래사장 폭(풀밭 끝 ~ 물가): 대략 9~24(넓은 모래사장은 더 넓게)
local function beachWidth(angle: number): number
	local w = 15 + 9 * around(angle, 2.3, 5.1)
	for _, beach in BEACHES do
		w += beach.Extra * bump(angle, beach.Angle, beach.Width)
	end
	-- 등대 곶은 바위가 차지하므로 모래를 좁게
	w -= 5 * bump(angle, HEADLAND.Angle, HEADLAND.Width)
	return math.max(w, 9)
end

-- 물가 너머 얕은 모래 턱 폭
local function shelfExact(angle: number): number
	return math.clamp(30 + 22 * around(angle, 2.0, 12.4), 16, 46)
end

-- 각도별 표(0.25도 간격, 사이는 직선 보간): 복셀 칸마다 노이즈를 다시 계산하지 않게. 모든 곳이 이 표를 씀
local STEPS = 1440
local COAST: { number } = {}
local GRASS: { number } = {}
local SHELF: { number } = {}
for i = 0, STEPS do
	local angle = i / STEPS * TAU
	local coast = coastExact(angle)
	COAST[i + 1] = coast
	GRASS[i + 1] = smoothMax(coast - beachWidth(angle), Island.GRASS_MIN, 6)
	SHELF[i + 1] = shelfExact(angle)
end

local function lookup(list: { number }, angle: number): number
	local f = (angle % TAU) / TAU * STEPS
	local i = math.floor(f)
	local t = f - i
	if i >= STEPS then -- 아주 작은 음수 각도는 % 뒤에 TAU 로 반올림될 수 있음
		i, t = STEPS - 1, 1
	end
	return list[i + 1] + (list[i + 2] - list[i + 1]) * t
end

-- 물가(해안선) 반지름. angle = 라디안(atan2(z, x))
function Island.coastRadius(angle: number): number
	return lookup(COAST, angle)
end

-- 풀밭 끝(모래 시작) 반지름
function Island.grassEdge(angle: number): number
	return lookup(GRASS, angle)
end

-- 물가 바위 ----------------------------------------------------------------------

-- 물가 바위(지형 Rock): 반쯤 물에 잠긴 둥근 바위. Base = 바위 밑면 높이, Height = 밑면에서 꼭대기까지
export type Rock = { X: number, Z: number, R: number, Height: number, Base: number, Seed: number }
Island.ROCKS = {} :: { Rock }
local function addRock(angleDegrees: number, offset: number, radius: number, height: number)
	local angle = math.rad(angleDegrees)
	local d = Island.coastRadius(angle) + offset
	table.insert(Island.ROCKS, {
		X = math.cos(angle) * d,
		Z = math.sin(angle) * d,
		R = radius,
		Height = height,
		Base = Island.WATER_LEVEL - 2,
		Seed = #Island.ROCKS * 7.31 + 1.7,
	})
end
-- 등대 곶: 큰 바위(꼭대기 약 y 3, 등대 받침) + 물속 바위 둘. 1 번(등대 받침) 말고는 Plan 이 위에 둥근 바윗돌을 얹음
addRock(315, -3, 13, 9)
addRock(311, 8, 7, 6.5)
addRock(319, 9, 5.5, 6)
-- 물가 여기저기(물 위로 3~4 드러난 울퉁불퉁한 바위 — 위에 Plan 의 바윗돌이 올라앉음)
addRock(72, 3, 9, 8.5)
addRock(76.5, 10, 5, 6)
addRock(207, 3, 8.5, 8)
addRock(252, 4, 7, 7)
addRock(356, 3, 8, 7.5)
addRock(101, 6, 5.5, 6)
addRock(118, 20, 4.5, 5.5) -- 부두 옆 물속 바위

-- 바위마다 옆에 붙은 작은 혹 둘(한 덩어리 둥근 돔이 아니라 울퉁불퉁한 바위 무더기로 보이게). 바위 반지름 R 의
-- 1.3 배 안에만 생김(Plan 은 바위 자리를 R * 1.35 까지 비워 둠)
local LOBES: { Rock } = {}
for _, rock in Island.ROCKS do
	for k = 1, 2 do
		local a = rock.Seed * 2.7 + k * 2.4
		local d = rock.R * (0.45 + 0.1 * k)
		table.insert(LOBES, {
			X = rock.X + math.cos(a) * d,
			Z = rock.Z + math.sin(a) * d,
			R = rock.R * (0.62 - 0.1 * k),
			Height = rock.Height * (0.8 - 0.12 * k),
			Base = rock.Base,
			Seed = rock.Seed + k * 5.1,
		})
	end
end
local ROCK_SHAPES: { Rock } = table.clone(Island.ROCKS)
for _, lobe in LOBES do
	table.insert(ROCK_SHAPES, lobe)
end

-- 바위 높이(바위 밖이면 -무한)
local function rockHeight(x: number, z: number): number
	local best = -math.huge
	for _, rock in ROCK_SHAPES do
		local dx, dz = x - rock.X, z - rock.Z
		local reach = rock.R * 1.3
		if dx * dx + dz * dz < reach * reach then
			local a = math.atan2(dz, dx)
			local radius = rock.R * (1 + 0.22 * around(a, 1.8, rock.Seed))
			local t = math.sqrt(dx * dx + dz * dz) / radius
			if t < 1 then
				-- 둥근 돔에 울퉁불퉁한 노이즈(복셀 4 보다 큰 굴곡만 남음)
				local crag = 1 + 0.2 * math.noise(x / 6 + rock.Seed, z / 6 - rock.Seed, 0.37)
				best = math.max(best, rock.Base + rock.Height * (1 - t * t) ^ 0.7 * crag)
			end
		end
	end
	return best
end

-- 먼 작은 섬 ------------------------------------------------------------------------

export type Islet = {
	X: number,
	Z: number,
	R: number,
	Seed: number,
	Reach: number, -- 이 거리 밖은 깊은 바다 바닥
	Stretch: number,
	Axis: number, -- 라디안
	HillX: number, -- 풀 언덕 가운데(월드)
	HillZ: number,
}
local ISLETS: { Islet } = {}
for i, islet in Island.ISLETS do
	local a = math.rad(islet.Angle)
	local x, z = math.cos(a) * islet.Distance, math.sin(a) * islet.Distance
	local axis = math.rad(islet.Axis)
	local hill = islet.Hill * islet.Radius
	table.insert(ISLETS, {
		X = x,
		Z = z,
		R = islet.Radius,
		Seed = 20 + i * 3.3,
		Reach = islet.Radius * 1.35 * islet.Stretch + (Island.WATER_LEVEL - Island.SEA_FLOOR) / DROP_SLOPE + 16,
		Stretch = islet.Stretch,
		Axis = axis,
		HillX = x - math.sin(axis) * hill,
		HillZ = z + math.cos(axis) * hill,
	})
end

function Island.islets(): { Islet }
	local list = {}
	for _, islet in ISLETS do
		table.insert(list, table.clone(islet))
	end
	return list
end

-- 길쭉한 타원(넓이 = 반지름 1 원) 위 angle 방향 반지름 비율
local function ellipse(islet: Islet, angle: number): number
	local c, s = math.cos(angle - islet.Axis), math.sin(angle - islet.Axis)
	return 1 / math.sqrt((c / islet.Stretch) ^ 2 + (s * islet.Stretch) ^ 2)
end

-- 작은 섬 물가 반지름(가운데에서 angle 방향): 길쭉한 타원 + 두 겹 노이즈(한쪽이 곶처럼 튀어나오고 한쪽은 움푹)
function Island.isletRadius(islet: Islet, angle: number): number
	local n = 1 + 0.24 * around(angle, 1.5, islet.Seed) + 0.14 * around(angle, 3.6, islet.Seed + 4.1)
	return islet.R * n * ellipse(islet, angle)
end

-- 작은 섬 위 높이: 한쪽으로 치우친 구불구불한 풀 언덕(물 위 최고 약 5) → 넓은 모래 → 물속
local function isletHeight(islet: Islet, x: number, z: number): (number, string)
	local dx, dz = x - islet.X, z - islet.Z
	local radius = Island.isletRadius(islet, math.atan2(dz, dx))
	local d = math.sqrt(dx * dx + dz * dz)
	local u = d / radius
	local wl = Island.WATER_LEVEL
	if u <= 1 then
		-- 모래: 가운데 쪽은 물 위 2.5, 물가로 갈수록 낮아짐
		local h = wl + 2.5 * (1 - smooth((u - 0.35) / 0.65))
		-- 풀 언덕: 치우친 가운데에서 구불구불한 가장자리까지(물가 가까이는 스며들어 모래)
		local hx, hz = x - islet.HillX, z - islet.HillZ
		local ha = math.atan2(hz, hx)
		local hillR = islet.R * 0.52 * (1 + 0.28 * around(ha, 2.2, islet.Seed + 9)) * ellipse(islet, ha)
		local hu = math.sqrt(hx * hx + hz * hz) / hillR
		local fade = 1 - smooth((u - 0.55) / 0.3)
		if hu < 1 and fade > 0 then
			h += 2.6 * smooth((1 - hu) / 0.7) * fade
			if hu < 0.92 and u < 0.8 then
				return h, "Grass"
			end
		end
		return h, "Sand"
	end
	local under = d - radius
	-- 물가 너머 얕은 턱(8)은 짧게: 먼 섬 둘레의 밝은 청록 테가 너무 넓게 번지지 않게
	local h = math.max(Island.SEA_FLOOR, wl - under * 0.25 - math.max(0, under - 8) * DROP_SLOPE)
	return h, if h < wl - 5 then "Mud" else "Sand"
end

-- 땅 높이·재질 ------------------------------------------------------------------------

-- 공원·숲띠 잔디 재질: 풀(장식 풀잎) 사이사이 잎 풀(LeafyGrass) 무늬
local function lawnMaterial(x: number, z: number): string
	local v = math.noise(x / 26 + 4.7, z / 26 - 1.9, 0.71) + 0.4 * math.noise(x / 9 + 0.3, z / 9 + 5.1, 0.13)
	return if v > 0.3 then "LeafyGrass" else "Grass"
end

-- 본섬(바위 제외) 높이와 재질. r = 원점 거리
local function mainHeight(x: number, z: number, r: number): (number, string)
	if r <= Island.FLAT_RADIUS then
		return 0, lawnMaterial(x, z)
	end
	local angle = math.atan2(z, x)
	local coast = lookup(COAST, angle)
	local grass = lookup(GRASS, angle)
	local wl = Island.WATER_LEVEL
	if r < grass then
		-- 숲띠: 공원 쪽과 모래 쪽 끝에서는 0 으로 스며드는 둥근 언덕
		local n = math.noise(x / 44 + 17.1, z / 44 + 3.3, 0.5) + 0.45 * math.noise(x / 17 + 2.2, z / 17 + 9.4, 0.27)
		local fade = smooth((r - Island.FLAT_RADIUS) / 14) * smooth((grass - r) / 9)
		return MOUND_HEIGHT * smooth((n + 0.05) / 0.6) * fade, lawnMaterial(x, z)
	elseif r <= coast then
		-- 모래사장: 풀밭 쪽은 완만하게, 물가 쪽은 조금 가파르게
		local u = (r - grass) / math.max(coast - grass, 1)
		return wl * u ^ 1.4, "Sand"
	end
	local d = r - coast
	local shelf = lookup(SHELF, angle)
	local h
	if d < shelf then
		h = wl - SHALLOW_DEPTH * (d / shelf)
	else
		h = math.max(Island.SEA_FLOOR, wl - SHALLOW_DEPTH - (d - shelf) * DROP_SLOPE)
	end
	return h, if h < wl - SHALLOW_DEPTH - 1.5 then "Mud" else "Sand"
end

-- (x, z) 의 땅 윗면 높이와 재질 이름(바위·작은 섬 포함, 연못·칠하기 제외)
function Island.surface(x: number, z: number): (number, string)
	local r = math.sqrt(x * x + z * z)
	local h, material
	if r < Island.REGION_HALF then
		h, material = mainHeight(x, z, r)
	else
		h, material = Island.SEA_FLOOR, "Mud"
		for _, islet in ISLETS do
			local dx, dz = x - islet.X, z - islet.Z
			if dx * dx + dz * dz < islet.Reach * islet.Reach then
				local ih, im = isletHeight(islet, x, z)
				if ih > h then
					h, material = ih, im
				end
			end
		end
	end
	local rock = rockHeight(x, z)
	if rock > h + 0.25 then
		return rock, "Rock"
	end
	return h, material
end

function Island.height(x: number, z: number): number
	return (Island.surface(x, z))
end

-- 반지름 radius 원 안(가운데 + 둘레 8곳)에서 가장 낮은 땅 높이: 비탈에 선 나무·기둥 밑이 뜨지 않게
function Island.lowestAround(x: number, z: number, radius: number): number
	local low = Island.height(x, z)
	for k = 0, 7 do
		local a = k / 8 * TAU
		low = math.min(low, Island.height(x + math.cos(a) * radius, z + math.sin(a) * radius))
	end
	return low
end

-- 물 위 마른 땅인지(모래사장 장식 검사용)
function Island.isDry(x: number, z: number): boolean
	return Island.height(x, z) > Island.WATER_LEVEL + 0.2
end

-- 칠하기·연못 ------------------------------------------------------------------------

-- 지형 윗면 칠하기(Plan 이 만듦): 부지·길·산책로·광장·납작한 장식 밑은 풀잎(Grass 장식)이 얇은 파트를
-- 뚫고 나오지 않게 다른 재질로. Margin = 모양 밖으로 더 칠할 거리(기본 3: 복셀 반 대각선 + 풀잎 여유)
export type Shape = {
	Kind: string, -- "Circle" | "Blob"(가장자리가 구불구불한 원) | "Ring" | "Segment" | "Box"
	Material: string,
	Margin: number?,
	X: number?, -- Circle/Box 중심
	Z: number?,
	R: number?, -- Circle 반지름
	R1: number?, -- Ring(원점 중심) 안·바깥 반지름
	R2: number?,
	X1: number?, -- Segment 양 끝 + 반폭
	Z1: number?,
	X2: number?,
	Z2: number?,
	Half: number?,
	DirX: number?, -- Box: 로컬 Z 축(단위 벡터), 반폭(X)·반깊이(Z)
	DirZ: number?,
	HalfX: number?,
	HalfZ: number?,
}

-- 연못: 물 윗면 y = 0(공원 땅과 같은 높이), 가운데 깊이 Depth, 가장자리 구불구불
export type Pond = { X: number, Z: number, R: number, Depth: number, Seed: number }

-- (x, z) 가 모양 안(+ margin + extra)인지
function Island.inShape(shape: Shape, x: number, z: number, extra: number?): boolean
	local m = (shape.Margin or 3) + (extra or 0)
	local kind = shape.Kind
	if kind == "Circle" then
		local dx, dz = x - (shape.X :: number), z - (shape.Z :: number)
		local reach = (shape.R :: number) + m
		return dx * dx + dz * dz <= reach * reach
	elseif kind == "Blob" then
		local dx, dz = x - (shape.X :: number), z - (shape.Z :: number)
		local r = shape.R :: number
		local reach = r * (1 + 0.3 * around(math.atan2(dz, dx), 1.4, (shape.X :: number) * 0.01 + 3)) + m
		return dx * dx + dz * dz <= reach * reach
	elseif kind == "Ring" then
		local r = math.sqrt(x * x + z * z)
		return r >= (shape.R1 :: number) - m and r <= (shape.R2 :: number) + m
	elseif kind == "Segment" then
		local x1, z1, x2, z2 = shape.X1 :: number, shape.Z1 :: number, shape.X2 :: number, shape.Z2 :: number
		local vx, vz = x2 - x1, z2 - z1
		local length2 = vx * vx + vz * vz
		local t = if length2 > 0 then math.clamp(((x - x1) * vx + (z - z1) * vz) / length2, 0, 1) else 0
		local px, pz = x1 + vx * t - x, z1 + vz * t - z
		local reach = (shape.Half :: number) + m
		return px * px + pz * pz <= reach * reach
	elseif kind == "Box" then
		local dirX, dirZ = shape.DirX :: number, shape.DirZ :: number
		local dx, dz = x - (shape.X :: number), z - (shape.Z :: number)
		local lz = dx * dirX + dz * dirZ
		local lx = dx * dirZ - dz * dirX
		return math.abs(lx) <= (shape.HalfX :: number) + m and math.abs(lz) <= (shape.HalfZ :: number) + m
	end
	return false
end

-- 모양이 차지하는 사각 범위(minX, minZ, maxX, maxZ, 여유 포함)
local function shapeBounds(shape: Shape): (number, number, number, number)
	local m = (shape.Margin or 3) + 3
	local kind = shape.Kind
	if kind == "Circle" or kind == "Blob" then
		local x, z, r = shape.X :: number, shape.Z :: number, (shape.R :: number) * (if kind == "Blob" then 1.3 else 1)
		return x - r - m, z - r - m, x + r + m, z + r + m
	elseif kind == "Ring" then
		local r = (shape.R2 :: number) + m
		return -r, -r, r, r
	elseif kind == "Segment" then
		local h = (shape.Half :: number) + m
		local x1, z1, x2, z2 = shape.X1 :: number, shape.Z1 :: number, shape.X2 :: number, shape.Z2 :: number
		return math.min(x1, x2) - h, math.min(z1, z2) - h, math.max(x1, x2) + h, math.max(z1, z2) + h
	end
	local reach = math.sqrt((shape.HalfX :: number) ^ 2 + (shape.HalfZ :: number) ^ 2) + m
	local x, z = shape.X :: number, shape.Z :: number
	return x - reach, z - reach, x + reach, z + reach
end

-- 연못 가장자리 반지름(구불구불). angle = 연못 가운데에서 본 방향(라디안)
function Island.pondRadius(pond: Pond, angle: number): number
	return pond.R * (1 + 0.16 * around(angle, 1.4, pond.Seed))
end

-- 연못 깊이(연못 밖이면 0)
function Island.pondDepth(ponds: { Pond }, x: number, z: number): number
	local depth = 0
	for _, pond in ponds do
		local dx, dz = x - pond.X, z - pond.Z
		local reach = pond.R * 1.25
		if dx * dx + dz * dz < reach * reach then
			local radius = Island.pondRadius(pond, math.atan2(dz, dx))
			local t = math.sqrt(dx * dx + dz * dz) / radius
			if t < 1 then
				depth = math.max(depth, pond.Depth * smooth((1 - t) / 0.45))
			end
		end
	end
	return depth
end

-- 복셀 표 ------------------------------------------------------------------------------

-- WriteVoxelChannels 모양: [x][y][z] 3차원 표. Material = 재질(materials 표로 바꾼 값), Solid/Liquid = 0~1
export type Grid = {
	MinX: number,
	MinY: number,
	MinZ: number,
	SizeX: number, -- 복셀 수
	SizeY: number,
	SizeZ: number,
	Material: { { { any } } },
	Solid: { { { number } } },
	Liquid: { { { number } } },
	SolidCount: number, -- 땅이 조금이라도 있는 복셀 수
	WaterCount: number, -- 물이 조금이라도 있는 복셀 수
}

export type GridOptions = {
	Paint: { Shape }?,
	Ponds: { Pond }?,
	-- 재질 이름 → 실제 값(Enum.Material.X). 없으면 이름 문자열 그대로(테스트)
	Materials: { [string]: any }?,
}

-- 원점 기준 (minX, minZ) 에서 sizeX x sizeZ 복셀(한 변 VOXEL) 칸의 지형 표. y 는 SEA_FLOOR ~ TOP
function Island.voxels(minX: number, minZ: number, sizeX: number, sizeZ: number, options: GridOptions?): Grid
	local V = Island.VOXEL
	local opts: GridOptions = options or {}
	local names = opts.Materials
	local function mat(name: string): any
		return if names then names[name] else name
	end
	local minY = Island.SEA_FLOOR
	local sizeY = (Island.TOP - minY) // V
	local wl = Island.WATER_LEVEL

	-- 칠하기: 모양마다 걸치는 칸만 돌며 칸 가운데를 검사(나중 모양이 앞 모양을 덮음)
	local paint: { [number]: string } = {}
	for _, shape in opts.Paint or {} do
		local x0, z0, x1, z1 = shapeBounds(shape)
		local i0 = math.max(0, math.floor((x0 - minX) / V))
		local i1 = math.min(sizeX - 1, math.floor((x1 - minX) / V))
		local k0 = math.max(0, math.floor((z0 - minZ) / V))
		local k1 = math.min(sizeZ - 1, math.floor((z1 - minZ) / V))
		for i = i0, i1 do
			local cx = minX + (i + 0.5) * V
			for k = k0, k1 do
				if Island.inShape(shape, cx, minZ + (k + 0.5) * V) then
					paint[i * 100000 + k] = shape.Material
				end
			end
		end
	end
	local ponds = opts.Ponds or {}

	local materials: { { { any } } } = {}
	local solids: { { { number } } } = {}
	local liquids: { { { number } } } = {}
	local solidCount, waterCount = 0, 0
	local air = mat("Air")
	for i = 1, sizeX do
		local mx, sx, lx = {}, {}, {}
		materials[i], solids[i], liquids[i] = mx, sx, lx
		for j = 1, sizeY do
			mx[j], sx[j], lx[j] = {}, {}, {}
		end
		local cx = minX + (i - 0.5) * V
		for k = 1, sizeZ do
			local cz = minZ + (k - 0.5) * V
			local h, name = Island.surface(cx, cz)
			local waterTop = wl
			local depth = if #ponds > 0 then Island.pondDepth(ponds, cx, cz) else 0
			if depth > 0 then
				h = math.min(h, -depth)
				waterTop = 0
				name = if depth > 2.5 then "Mud" elseif depth > 0.6 then "Sand" else name
			end
			local painted = paint[(i - 1) * 100000 + (k - 1)]
			if painted and depth <= 0.6 and name ~= "Sand" and name ~= "Rock" then
				name = painted
			end
			local solidMaterial = mat(name)
			-- 칸 한 줄(아래 → 위): 땅 윗면 h 아래는 땅, 그 위 물 높이까지는 물
			for j = 1, sizeY do
				local bottom = minY + (j - 1) * V
				local solid = (h - bottom) / V
				if solid >= 1 then
					solid = 1
				elseif solid <= 0 then
					solid = 0
				end
				local liquid = (waterTop - bottom) / V
				if liquid >= 1 then
					liquid = 1
				end
				liquid -= solid
				if liquid < 0 then
					liquid = 0
				end
				if solid > 0 then
					mx[j][k] = solidMaterial
					solidCount += 1
				else
					mx[j][k] = air
				end
				sx[j][k] = solid
				lx[j][k] = liquid
				if liquid > 0 then
					waterCount += 1
				end
			end
		end
	end
	return {
		MinX = minX,
		MinY = minY,
		MinZ = minZ,
		SizeX = sizeX,
		SizeY = sizeY,
		SizeZ = sizeZ,
		Material = materials,
		Solid = solids,
		Liquid = liquids,
		SolidCount = solidCount,
		WaterCount = waterCount,
	}
end

-- WriteVoxels(예전 API: 복셀마다 재질 하나)용 표로 바꿈: 땅이 반 이상이면 땅, 아니고 물이 있으면 물(가득)
function Island.legacy(grid: Grid, water: any, air: any): ({ { { any } } }, { { { number } } })
	local materials: { { { any } } } = {}
	local occupancies: { { { number } } } = {}
	for i = 1, grid.SizeX do
		local mi, oi = {}, {}
		materials[i], occupancies[i] = mi, oi
		for j = 1, grid.SizeY do
			local mj, oj = {}, {}
			mi[j], oi[j] = mj, oj
			local gm, gs, gl = grid.Material[i][j], grid.Solid[i][j], grid.Liquid[i][j]
			for k = 1, grid.SizeZ do
				local solid, liquid = gs[k], gl[k]
				if solid >= 0.5 or (solid > 0 and liquid <= 0) then
					mj[k], oj[k] = gm[k], solid
				elseif liquid > 0 then
					mj[k], oj[k] = water, 1
				else
					mj[k], oj[k] = air, 0
				end
			end
		end
	end
	return materials, occupancies
end

-- 쓸 복셀 표 범위: 본섬 한 장 + 작은 섬마다 한 장. Min = 월드 좌표(복셀 경계), Size = 복셀 수
export type Area = { Name: string, MinX: number, MinZ: number, SizeX: number, SizeZ: number }
function Island.areas(): { Area }
	local V = Island.VOXEL
	local half = Island.REGION_HALF
	local count = half * 2 // V
	local list: { Area } = {
		{ Name = "Island", MinX = -half, MinZ = -half, SizeX = count, SizeZ = count },
	}
	for i, islet in ISLETS do
		local x0 = math.floor((islet.X - islet.Reach) / V) * V
		local z0 = math.floor((islet.Z - islet.Reach) / V) * V
		local x1 = math.ceil((islet.X + islet.Reach) / V) * V
		local z1 = math.ceil((islet.Z + islet.Reach) / V) * V
		local sizeX, sizeZ = (x1 - x0) // V, (z1 - z0) // V
		table.insert(list, { Name = "Islet" .. i, MinX = x0, MinZ = z0, SizeX = sizeX, SizeZ = sizeZ })
	end
	return list
end

-- 먼 바다 FillBlock 조각(가운데 x, z, 한 변). 바닥 판(FLOOR_BOTTOM ~ SEA_FLOOR)과 물(SEA_FLOOR ~ WATER_LEVEL)
export type Tile = { X: number, Z: number, Size: number }
function Island.oceanTiles(): { Tile }
	local list: { Tile } = {}
	local tile = Island.OCEAN_TILE
	local count = Island.OCEAN_HALF * 2 // tile
	for i = 0, count - 1 do
		for k = 0, count - 1 do
			table.insert(list, {
				X = -Island.OCEAN_HALF + (i + 0.5) * tile,
				Z = -Island.OCEAN_HALF + (k + 0.5) * tile,
				Size = tile,
			})
		end
	end
	return list
end

-- 지형 재질 색(SetMaterialColor, RGB): 게임 전체의 밝은 만화풍에 맞춤
Island.COLORS = {
	Grass = { 106, 190, 78 }, -- 싱싱한 잔디
	LeafyGrass = { 126, 198, 84 }, -- 잔디 무늬(조금 밝은 연두). 부지·길 밑 칠하기에도 씀(풀잎 장식 없음)
	Sand = { 240, 220, 168 }, -- 밝고 따뜻한 모래
	Rock = { 150, 146, 140 }, -- 따뜻한 회색 바위
	Mud = { 58, 116, 128 }, -- 깊은 바다·연못 바닥(물 너머로 짙은 청록)
	Salt = { 222, 214, 196 }, -- 바위 정원 자갈(따뜻한 흰색)
}

-- 물 속성(Terrain.WaterColor 등)
Island.WATER = {
	Color = { 38, 178, 196 }, -- 청록
	Transparency = 0.5,
	Reflectance = 0.45,
	WaveSize = 0.08,
	WaveSpeed = 8,
}

return Island
