-- 옥반(玉盤) 맵. 땅은 지형(Terrain)이고, 그 위의 마을·자리·진·나무는 블록으로 짓는다.
--
-- 땅 모양은 Shared.Land 한 곳에 있다. 지형은 tools/bake_place.luau 가 그 모양대로 플레이스 파일에
-- 구워 넣고, 여기서는 그 높이(Land.surface)를 따라 나머지를 놓는다 (맵을 굽는 Lune 에서는 레이캐스트가 없다).
-- 게임 서버는 Workspace 에 "옥반" 이 없을 때만 이걸 다시 부른다 (지형은 server/TerrainGen.luau).
--
-- 여기서 짓는 것: 송계 마을(스폰), 벽계와 다리·징검돌·벽담, 청송림과 영천굴, 그리고 땅마다 쓰는 자리 전부
-- (과업 자리, 오행처 받침, 사방 성대, 관성대 칠성단과 팔괘 기둥, 전송진, 영맥, 영초 범위, 비급 자리).
-- 자리 좌표는 WorldSites.luau 한 곳에 있다. 그 둘레의 땅은 땅마다의 World*.luau 가 꾸민다 (끝에서 차례로 부른다).
-- 다른 시스템은 이름이 아니라 태그로 맵을 찾는다:
--   Ground        - 영초·요수·별씨가 놓이는 바닥 판 (지형 말고)
--   Vein          - 영맥 (속성 VeinId = 등급, Radius)
--   HerbZone      - 영초가 돋는 범위 (속성 RareMult: 귀한 영초 배율, Weight: 고르는 비중)
--   ManualSpot    - 비급이 나타나는 자리
--   Site          - 과업 자리 (속성 Site = 자리 id, Radius). 오행처 el_wood 등
--   Waypoint      - 전송진 (속성 WaypointId, Name, Order)
--   Plaque        - 글자를 새길 판 (속성 Text 등, client/Plaques.luau)
--   MarketSpot    - 상점 자리 (속성 Shop = "market" 만물상 | "smith" 대장간). F 버튼이 붙어 있다 (server/Market.luau)

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")

local Land = require(Shared.Land)
local Npcs = require(Shared.Npcs)
local Kit = require(script.Parent.WorldKit)
local Build = require(script.Parent.WorldBuild)
local Sites = require(script.Parent.WorldSites)

local World = {}

World.MODEL_NAME = "옥반"

local at = Kit.at
World.at = at

local makeRng = Kit.makeRng
local C = Kit.C
local P = Build.P
local face = Kit.face
local block = Build.block -- 작은 부품은 그림자를 안 드리운다
local disc = Kit.disc
local ball = Kit.ball
local folder = Kit.folder
local model = Kit.model
local light = Kit.light
local motes = Kit.motes
local engrave = Kit.engrave
local signboard = Kit.signboard
local stele = Kit.stele
local siteMarker = Kit.siteMarker
local marketSpot = Kit.marketSpot
local beam = Build.beam
local cyl = Build.cyl
local deco = Build.deco
local V3 = Vector3.new
local CF = CFrame.new
local Mat = Enum.Material
local SITE = Sites.byId

-- 비급이 나타날 수 있는 자리 (WorldSites.MANUALS). 하늘섬 자리는 섬 위에 놓인다
local MANUAL_SPOTS = {}
for _, xz in Sites.MANUALS do
	table.insert(MANUAL_SPOTS, at(xz[1], xz[2], 0.2))
end
World.MANUAL_SPOTS = MANUAL_SPOTS

-- 오행처: 영근 속성마다 운기하는 자리 (Tasks.luau 의 el_* 와 맞춘다)
World.ELEMENT_SITES = {}
for _, s in Sites.TASK do
	if string.sub(s.id, 1, 3) == "el_" then
		table.insert(World.ELEMENT_SITES, s)
	end
end
World.WAYPOINTS = Sites.WAYPOINTS

-- 십이지율: 광장 네 귀퉁이에 셋씩 모인 율점 등롱 (양률과 음려가 번갈아)
World.LU_NAMES = {
	"황종",
	"대려",
	"태주",
	"협종",
	"고선",
	"중려",
	"유빈",
	"임종",
	"이칙",
	"남려",
	"무역",
	"응종",
}
local PLAZA_TOP = 0.5 -- 광장 윗면
local LU_CLUSTERS = {
	Vector3.new(24, PLAZA_TOP, 24),
	Vector3.new(-24, PLAZA_TOP, 24),
	Vector3.new(-24, PLAZA_TOP, -24),
	Vector3.new(24, PLAZA_TOP, -24),
}

-- 팔괘: 관성대 칠성단 둘레 기둥에 선천팔괘 자리대로 단다 (건은 남, 곤은 북, 리는 동, 감은 서).
-- 각도는 칠성단 가운데에서 (cos, sin) = (x, z). 순서는 건 태 리 진 손 감 간 곤 (WorldSites 의 tri_1~8 과 같다)
World.TRIGRAMS = {
	{ name = "건", angle = 90 },
	{ name = "태", angle = 45 },
	{ name = "리", angle = 0 },
	{ name = "진", angle = 315 },
	{ name = "손", angle = 135 },
	{ name = "감", angle = 180 },
	{ name = "간", angle = 225 },
	{ name = "곤", angle = 270 },
}
-- 괘의 효 (아래에서 위로, 1 양효 · 0 음효)
local GUA = {
	["건"] = { 1, 1, 1 },
	["태"] = { 1, 1, 0 },
	["리"] = { 1, 0, 1 },
	["진"] = { 1, 0, 0 },
	["손"] = { 0, 1, 1 },
	["감"] = { 0, 1, 0 },
	["간"] = { 0, 0, 1 },
	["곤"] = { 0, 0, 0 },
}

-- 천인기 천순: 마지막 부탁을 하는 마을 노인 셋 (자리는 WorldSites, 바라보는 곳은 여기)
local ELDERS = {
	{ id = "elder_1", y = PLAZA_TOP, faces = Vector3.new(0, 0, 0) }, -- 광장 가운데 영맥
	{ id = "elder_2", y = 0, faces = Vector3.new(60, 0, 18) }, -- 대장간 모루
	{ id = "elder_3", y = 0, faces = Vector3.new(-95, 0, 20) }, -- 벽계 물
}

-- 만물상: 광장 동북쪽, 대장간과 송계 전송진 사이. 판대 앞이 광장을 본다.
-- 주인(Npcs.luau 의 merchant)은 판대 뒤 걸상에 앉는다 (Npcs 의 position 은 그 걸상 자리)
local STALL = { id = "merchant", position = Vector3.new(48, 0, -26), faces = Vector3.zero }
World.STALL = STALL

-- 자리 비워 두기 ----------------------------------------------------------------------------
-- 나무·살림을 흩뿌릴 때 피하는 곳: 자리(과업·전송진·영맥), 비급 자리, 길, 마을 사람 동선, 먼저 지은 건물

local ROAD_POLYS = {}
for _, road in Land.ROADS do
	table.insert(ROAD_POLYS, Land.poly(road))
end
for _, bench in Land.BENCHES do
	table.insert(ROAD_POLYS, bench)
end

local function segDist(px: number, pz: number, ax: number, az: number, bx: number, bz: number): number
	local vx, vz = bx - ax, bz - az
	local t = math.clamp(((px - ax) * vx + (pz - az) * vz) / math.max(vx * vx + vz * vz, 1e-6), 0, 1)
	local dx, dz = px - (ax + vx * t), pz - (az + vz * t)
	return math.sqrt(dx * dx + dz * dz)
end

local ROUTES = {}
for _, npc in Npcs.list do
	local route = npc.route
	if route then
		for i = 1, #route do
			local a, b = route[i], route[i % #route + 1]
			table.insert(ROUTES, { a.X, a.Z, b.X, b.Z })
		end
	end
end

local taken: { { number } } = {}
local function take(x: number, z: number, r: number)
	table.insert(taken, { x, z, r })
end

local function roadDist(x: number, z: number): number
	local best = math.huge
	for _, p in ROAD_POLYS do
		local d = Land.polyDist(x, z, p, 40)
		if d < best then
			best = d
		end
	end
	return best
end

-- 반지름 r 짜리를 (x, z) 에 놓아도 되는가. roadGap: 길 가운데에서 더 띄울 거리
local function clearOf(x: number, z: number, r: number, roadGap: number?): boolean
	for _, s in Sites.LIST do
		if s.kind ~= "poi" then
			local keep = if s.kind == "wp"
				then 10
				elseif s.kind == "vein" then s.radius + 3
				else math.max(7, s.radius or 0) + 1
			local dx, dz = x - s.x, z - s.z
			if dx * dx + dz * dz < (keep + r) ^ 2 then
				return false
			end
		end
	end
	for _, m in Sites.MANUALS do
		if (x - m[1]) ^ 2 + (z - m[2]) ^ 2 < (r + 3) ^ 2 then
			return false
		end
	end
	for _, t in taken do
		local dx, dz = x - t[1], z - t[2]
		if dx * dx + dz * dz < (r + t[3]) ^ 2 then
			return false
		end
	end
	for _, s in ROUTES do
		if segDist(x, z, s[1], s[2], s[3], s[4]) < r + 2.5 then
			return false
		end
	end
	if roadDist(x, z) < r + (roadGap or 4.5) then
		return false
	end
	return true
end

-- 땅 -----------------------------------------------------------------------------------

local function yawTo(x: number, z: number, tx: number, tz: number): number
	return math.atan2(-(tx - x), -(tz - z))
end

-- 네모 자리 (가운데 x z, 너비 w 깊이 d, 돌림 yaw) 밑 땅의 가장 낮은 곳과 높은 곳
local function rectSpan(x: number, z: number, w: number, d: number, yaw: number): (number, number)
	local lo, hi = math.huge, -math.huge
	local c, s = math.cos(yaw), math.sin(yaw)
	for _, u in { -0.5, 0, 0.5 } do
		for _, v in { -0.5, 0, 0.5 } do
			local lx, lz = u * w, v * d
			local y = Land.surface(x + lx * c + lz * s, z - lx * s + lz * c)
			lo, hi = math.min(lo, y), math.max(hi, y)
		end
	end
	return lo, hi
end

-- 비탈이면 밑을 돌로 메운다 (윗면 = 가장 높은 땅). 윗면 높이를 돌려준다
local function bed(
	parent: Instance,
	x: number,
	z: number,
	w: number,
	d: number,
	yaw: number,
	color: Color3?,
	material: Enum.Material?
): number
	local lo, hi = rectSpan(x, z, w, d, yaw)
	if hi - lo > 0.35 then
		local depth = hi - lo + 1.4
		block(
			parent,
			"Badak",
			V3(w, depth, d),
			CF(x, hi - depth / 2 + 0.05, z) * CFrame.Angles(0, yaw, 0),
			color or P.graniteDark,
			material or Mat.Cobblestone
		)
	end
	return hi
end

-- 등성이·비탈에 걸친 긴 판 (길): a→b 사이 땅이 꺼지면 나눈다
local function trail(parent: Instance, a: Vector3, b: Vector3, width: number, color: Color3, depth: number?)
	local mid = (a + b) / 2
	local g = Land.surface(mid.X, mid.Z)
	if (b - a).Magnitude > 4 and math.abs(g - mid.Y) > 0.35 then
		local m = V3(mid.X, g + 0.05, mid.Z)
		trail(parent, a, m, width, color, depth)
		trail(parent, m, b, width, color, depth)
		return
	end
	local p = beam(parent, "Gil", a, b + (b - a).Unit * 0.6, width, 0.3, color, Mat.Ground)
	p.CanCollide = false
	p.CastShadow = false
end

-- 작은 건물과 살림 ---------------------------------------------------------------------------

local STRAW = Color3.fromRGB(178, 150, 98)
local STRAW_DARK = Color3.fromRGB(138, 112, 72)
local MUD = Color3.fromRGB(200, 178, 140)
local BRONZE = Color3.fromRGB(150, 112, 62)
local SOIL = Color3.fromRGB(112, 86, 62)
local WATTLE = Color3.fromRGB(150, 122, 86)

-- 초가 지붕: 앞뒤 사다리꼴 + 양 끝 세모 (우진각). frame 은 처마 높이 가운데. a ≥ b 는 처마 반너비·반깊이
local function thatch(parent: Instance, frame: CFrame, a: number, b: number, rise: number)
	local m = model(parent, "초가지붕")
	local t = 1.3
	local up = frame.UpVector
	local function W(x: number, y: number, z: number): Vector3
		return frame:PointToWorldSpace(V3(x, y, z))
	end
	local r = math.max(a - b, 0)
	for _, s in { -1, 1 } do
		if r > 0.05 then
			Build.slab(
				m,
				"Jip",
				W(-r, 0, s * b),
				W(r, 0, s * b) - W(-r, 0, s * b),
				W(-r, rise, 0) - W(-r, 0, s * b),
				t,
				up,
				STRAW,
				Mat.Grass
			)
		end
		for _, e in { -1, 1 } do
			Build.rightTri(m, "Jip", W(e * r, 0, s * b), W(e * a, 0, s * b), W(e * r, rise, 0), t, up, STRAW, Mat.Grass)
		end
		Build.tri(
			m,
			"Jip",
			W(s * a, 0, -b),
			W(s * a, 0, b),
			W(s * r, rise, 0),
			t,
			up,
			STRAW:Lerp(STRAW_DARK, 0.15),
			Mat.Grass
		)
	end
	if r > 0.05 then
		cyl(m, "Yongmareum", W(-r - 0.9, rise + 0.1, 0), W(r + 0.9, rise + 0.1, 0), 1.5, STRAW_DARK, Mat.Grass)
	else
		Build.ball(m, "Yongmareum", W(0, rise, 0), 1.8, STRAW_DARK, Mat.Grass)
	end
	return m
end

-- 초가집: 막돌 기단, 흙벽 몸채, 툇마루, 굴뚝, 볏짚 지붕. (tx, tz) 쪽이 앞(마당)
local function choga(parent: Instance, x: number, z: number, tx: number, tz: number, w: number, d: number)
	local m = model(parent, "초가")
	local yaw = yawTo(x, z, tx, tz)
	local y = bed(m, x, z, w + 3, d + 6, yaw, P.graniteDark, Mat.Cobblestone)
	local cf = CF(x, y, z) * CFrame.Angles(0, yaw, 0)
	local base, wallH = 0.9, 6.2
	block(m, "Gidan", V3(w + 2.4, base + 0.6, d + 2.4), cf * CF(0, base / 2 - 0.3, 0), P.graniteDark, Mat.Cobblestone)
	block(m, "Byeok", V3(w, wallH, d), cf * CF(0, base + wallH / 2, 0), MUD, Mat.Plaster)
	for _, px in { -w / 2, w / 2 } do
		for _, pz in { -d / 2, d / 2 } do
			block(m, "Gidung", V3(0.75, wallH, 0.75), cf * CF(px, base + wallH / 2, pz), P.wood, Mat.Wood)
		end
	end
	block(m, "Dori", V3(w + 0.9, 0.6, d + 0.9), cf * CF(0, base + wallH + 0.3, 0), P.woodDark, Mat.Wood)
	local doorX = -w * 0.2
	block(m, "Mun", V3(2.8, 4.6, 0.3), cf * CF(doorX, base + 2.5, -d / 2 - 0.12), P.woodDark, Mat.Wood)
	block(m, "Hanji", V3(2.2, 3.9, 0.34), cf * CF(doorX, base + 2.6, -d / 2 - 0.13), P.hanji, Mat.SmoothPlastic)
	block(m, "Chang", V3(2.2, 1.8, 0.3), cf * CF(w * 0.24, base + 3.9, -d / 2 - 0.12), P.woodDark, Mat.Wood)
	block(m, "Hanji", V3(1.7, 1.35, 0.34), cf * CF(w * 0.24, base + 3.9, -d / 2 - 0.13), P.hanji, Mat.SmoothPlastic)
	block(m, "Toenmaru", V3(w - 0.6, 0.35, 2.4), cf * CF(0, base + 1.0, -d / 2 - 1.2), P.wood, Mat.WoodPlanks)
	block(m, "Daetdol", V3(2.6, 0.5, 1.4), cf * CF(doorX, 0.2, -d / 2 - 3.1), P.granite, Mat.Granite)
	block(
		m,
		"Gulttuk",
		V3(1.3, 4.6, 1.3),
		cf * CF(w / 2 + 1.6, 2.0, d * 0.25),
		MUD:Lerp(P.graniteDark, 0.35),
		Mat.Cobblestone
	)
	thatch(m, cf * CF(0, base + wallH + 0.55, 0), w / 2 + 2.3, d / 2 + 2.3, math.min(w, d) * 0.42 + 1.2)
	take(x, z, math.max(w, d) / 2 + 3.5)
	return m, cf
end

-- 기와집 (Build.house): (tx, tz) 쪽이 앞(마당). 비탈이면 밑을 메운다
local function houseAt(parent: Instance, x: number, z: number, tx: number, tz: number, opts)
	local bay = opts.bay or 5
	local W = opts.bays[1] * bay + 4.4
	local D = opts.bays[2] * bay + 4.4 + 2.4
	local yaw = yawTo(x, z, tx, tz)
	local y = bed(parent, x, z, W, D, yaw)
	local cf = CF(x, y, z) * CFrame.Angles(0, yaw, 0)
	local m, info = Build.house(parent, cf, opts)
	take(x, z, math.max(W, D) / 2 + 2)
	return m, cf, info
end

-- 싸리 울타리 (엮은 판 + 윗대): a→b
local function wattle(parent: Instance, a: Vector3, b: Vector3)
	local len = (b - a).Magnitude
	local cf = face((a + b) / 2, b)
	block(parent, "Ssari", V3(0.3, 2.6, len), cf * CF(0, 1.1, 0), WATTLE, Mat.Wood)
	block(parent, "Ssaridae", V3(0.45, 0.3, len + 0.3), cf * CF(0, 2.45, 0), WATTLE:Lerp(P.woodDark, 0.4), Mat.Wood)
end

-- 볏가리 (짚단 무더기)
local function haystack(parent: Instance, ground: Vector3, size: number)
	local m = model(parent, "볏가리")
	cyl(m, "Jip", ground - V3(0, 0.3, 0), ground + V3(0, size * 0.75, 0), size, STRAW, Mat.Grass)
	Build.ball(m, "Jipkkokji", ground + V3(0, size * 0.78, 0), size * 1.06, STRAW:Lerp(STRAW_DARK, 0.25), Mat.Grass)
	return m
end

-- 장작더미: 둥근 통나무를 눕혀 쌓는다
local function woodpile(parent: Instance, cf: CFrame)
	local m = model(parent, "장작")
	for row = 0, 1 do
		for i = 0, 2 - row do
			local x = -1.0 + i * 1.0 + row * 0.5
			local y = 0.45 + row * 0.85
			cyl(
				m,
				"Jangjak",
				(cf * CF(x, y, -1.4)).Position,
				(cf * CF(x, y, 1.4)).Position,
				0.9,
				Color3.fromRGB(124, 92, 62),
				Mat.Wood
			)
		end
	end
	return m
end

-- 허수아비
local function scarecrow(parent: Instance, ground: Vector3, yaw: number)
	local m = model(parent, "허수아비")
	local cf = CF(ground) * CFrame.Angles(0, yaw, 0)
	beam(m, "Gidung", ground - V3(0, 0.5, 0), ground + V3(0, 5.6, 0), 0.3, 0.3, P.woodDark, Mat.Wood)
	beam(m, "Pal", (cf * CF(-2.2, 4.3, 0)).Position, (cf * CF(2.2, 4.3, 0)).Position, 0.25, 0.25, P.woodDark, Mat.Wood)
	block(m, "Ot", V3(1.6, 2.2, 0.9), cf * CF(0, 3.6, 0), Color3.fromRGB(150, 160, 170), Mat.Fabric)
	Build.ball(m, "Meori", ground + V3(0, 5.4, 0), 1.2, STRAW, Mat.Fabric)
	cyl(m, "Satgat", ground + V3(0, 5.9, 0), ground + V3(0, 6.2, 0), 2.6, STRAW_DARK, Mat.Grass)
	return m
end

-- 감나무: 둥근 나무에 주홍 감 몇 알
local function persimmon(parent: Instance, base: Vector3, rng)
	local height = rng(10, 12.5)
	local m = Build.broadleaf(
		parent,
		base,
		rng,
		{ name = "감나무", height = height, blobs = 6, branches = 2, leaves = { P.leafDeep, P.leaf, P.leafYellow } }
	)
	local center = base + V3(0, height * 0.71, 0)
	local rx = height * 0.36
	for _ = 1, 5 do
		local a = rng(0, math.pi * 2)
		local yy = rng(-0.6, 0.25)
		local dir = V3(math.cos(a) * math.sqrt(1 - yy * yy), yy, math.sin(a) * math.sqrt(1 - yy * yy))
		deco(Build.ball(m, "Gam", center + dir * rx * 1.02, 0.75, Color3.fromRGB(232, 120, 40), Mat.SmoothPlastic))
	end
	return m
end

-- 장승: 마을 어귀를 지키는 나무 장승 (몸에 이름을 새긴다)
local function jangseung(parent: Instance, ground: Vector3, toward: Vector3, text: string, female: boolean)
	local m = model(parent, "장승")
	local look = face(ground, V3(toward.X, ground.Y, toward.Z))
	local H = if female then 8.6 else 9.4
	local wood = Color3.fromRGB(128, 104, 80)
	cyl(m, "Mom", ground - V3(0, 0.8, 0), ground + V3(0, H - 2.4, 0), 1.5, wood, Mat.Wood)
	block(m, "Meori", V3(1.9, 2.6, 1.8), look * CF(0, H - 1.5, 0), wood:Lerp(P.bark, 0.2), Mat.Wood)
	if female then
		block(m, "Gwan", V3(1.7, 0.6, 1.6), look * CF(0, H + 0.05, 0), P.meok, Mat.Wood)
	else
		block(m, "Gwanmo", V3(1.5, 1.7, 1.4), look * CF(0, H + 0.5, 0), P.meok, Mat.Wood)
		block(m, "Gwanmo", V3(2.6, 0.25, 2.2), look * CF(0, H - 0.2, 0), P.meok, Mat.Wood)
	end
	for _, sx in { -1, 1 } do
		block(
			m,
			"Nun",
			V3(0.55, 0.4, 0.2),
			look * CF(sx * 0.45, H - 1.0, -0.92),
			Color3.fromRGB(240, 236, 226),
			Mat.SmoothPlastic
		)
		block(m, "Nunsseop", V3(0.7, 0.18, 0.2), look * CF(sx * 0.45, H - 0.62, -0.93), P.meok, Mat.SmoothPlastic)
	end
	block(m, "Ko", V3(0.45, 0.8, 0.35), look * CF(0, H - 1.6, -1.0), wood:Lerp(P.juhong, 0.25), Mat.Wood)
	block(m, "Ip", V3(1.0, 0.25, 0.2), look * CF(0, H - 2.35, -0.92), P.juhong, Mat.SmoothPlastic)
	local plate = block(
		m,
		"Pan",
		V3(1.0, H - 4.4, 0.2),
		look * CF(0, (H - 4.4) / 2 + 0.6, -0.72),
		wood:Lerp(P.plaster, 0.15),
		Mat.Wood
	)
	engrave(plate, text, "Front", true, "ink")
	take(ground.X, ground.Z, 1.5)
	return m
end

-- 논 한 배미: 흙 둑 안에 물을 대고 모를 줄지어 심는다. 비탈이면 낮은 쪽에 흙 둑이 드러난다 (다랑이)
local function paddy(parent: Instance, x: number, z: number, sx: number, sz: number, yaw: number)
	local m = model(parent, "논")
	local lo, hi = rectSpan(x, z, sx + 1.6, sz + 1.6, yaw)
	local top = hi + 0.2
	local cf = CF(x, top, z) * CFrame.Angles(0, yaw, 0)
	local depth = top - lo + 1.2
	block(m, "Heuk", V3(sx + 1.6, depth, sz + 1.6), cf * CF(0, -depth / 2, 0), SOIL, Mat.Ground)
	local water = block(m, "Mul", V3(sx, 0.2, sz), cf * CF(0, 0.12, 0), Color3.fromRGB(118, 150, 138), Mat.Glass)
	water.Transparency = 0.25
	for _, s in { -1, 1 } do
		block(
			m,
			"Dureong",
			V3(sx + 1.6, 0.6, 0.8),
			cf * CF(0, 0.2, s * (sz / 2 + 0.4)),
			P.leaf:Lerp(SOIL, 0.35),
			Mat.Grass
		)
		block(m, "Dureong", V3(0.8, 0.6, sz), cf * CF(s * (sx / 2 + 0.4), 0.2, 0), P.leaf:Lerp(SOIL, 0.35), Mat.Grass)
	end
	local rows = math.max(2, math.floor(sz / 3.2))
	for i = 1, rows do
		local rz = -sz / 2 + (i - 0.5) * sz / rows
		deco(
			block(
				m,
				"Mo",
				V3(sx - 1.2, 0.7, 0.7),
				cf * CF(0, 0.45, rz),
				P.yangrok:Lerp(P.leafYellow, 0.2),
				Mat.LeafyGrass
			)
		)
	end
	take(x, z, math.max(sx, sz) / 2 + 0.5)
	return m
end

-- 밭 한 뙈기: 고랑 셋과 푸성귀
local function field(parent: Instance, x: number, z: number, sx: number, sz: number, yaw: number)
	local m = model(parent, "밭")
	local lo, hi = rectSpan(x, z, sx, sz, yaw)
	local top = hi + 0.1
	local cf = CF(x, top, z) * CFrame.Angles(0, yaw, 0)
	local depth = top - lo + 1
	block(m, "Heuk", V3(sx, depth, sz), cf * CF(0, -depth / 2, 0), SOIL:Lerp(P.wood, 0.2), Mat.Ground)
	for i = 1, 3 do
		local rz = -sz / 2 + (i - 0.5) * sz / 3
		block(m, "Ijang", V3(sx - 1, 0.6, sz / 3 - 1.4), cf * CF(0, 0.2, rz), SOIL, Mat.Ground)
		deco(block(m, "Namul", V3(sx - 2, 0.7, sz / 3 - 2.4), cf * CF(0, 0.75, rz), P.leafLight, Mat.LeafyGrass))
	end
	take(x, z, math.max(sx, sz) / 2)
	return m
end

-- 우물 곁 빨래줄, 장독대 같은 살림을 흩지 않고 집마다 정해 둔다

-- 송계 마을 -------------------------------------------------------------------------------
--
-- 광장(하품 영맥, 율점 등롱 열둘, 연단로) 둘레에 기와집 여섯, 바깥 들길 가에 초가 여덟.
-- 어귀마다 일주문(북, 동, 남동)과 서쪽 다리머리 장승, 북쪽 어귀에 당산나무. 동쪽에 다랑이 논.

-- 율점 등롱: 기둥 + 등 + 갓. 양률(홀수)은 붉은 등, 음려(짝수)는 푸른 등
local function luLantern(parent: Instance, index: number, position: Vector3, center: Vector3)
	local m = model(parent, World.LU_NAMES[index])
	local yang = index % 2 == 1
	block(m, "Chojeok", V3(1.5, 0.6, 1.5), CF(position + V3(0, 0.15, 0)), P.granite, Mat.Granite)
	block(m, "Post", V3(0.7, 7.4, 0.7), CF(position + V3(0, 3.6, 0)), P.woodDark, Mat.Wood)
	block(m, "Pan", V3(2.0, 0.25, 2.0), CF(position + V3(0, 6.4, 0)), P.meok, Mat.Wood)
	local color = if yang then Color3.fromRGB(214, 84, 60) else Color3.fromRGB(80, 136, 176)
	local lamp = block(m, "Lamp", V3(1.6, 2.0, 1.6), CF(position + V3(0, 7.55, 0)), color, Mat.Neon)
	block(m, "Gat", V3(2.3, 0.35, 2.3), CF(position + V3(0, 8.7, 0)), P.giwaDark, Mat.Slate)
	ball(m, "Boju", position + V3(0, 9.15, 0), 0.6, P.hwang, Mat.Metal)
	light(lamp, if yang then Color3.fromRGB(255, 170, 120) else Color3.fromRGB(160, 205, 255), 16, 1.4)
	siteMarker(m, "lu_" .. index, position, 6)
	-- 기둥에 건 나무 패. 가운데(운기하는 자리)를 본다
	local inward = (center - position).Unit
	local tag = block(
		m,
		"Tag",
		V3(0.9, 2.4, 0.15),
		face(position + inward * 0.5 + V3(0, 4, 0), center + V3(0, 4, 0)),
		C.lacquer,
		Mat.Wood
	)
	tag.CanCollide = false
	engrave(tag, World.LU_NAMES[index], "Front,Back", true)
end

local function buildPlaza(village: Instance)
	local plaza =
		block(village, "광장", V3(60, 3, 60), CF(0, PLAZA_TOP - 1.5, 0), Color3.fromRGB(176, 168, 152), Mat.Pavement)
	plaza:AddTag("Ground")
	-- 장대석 테두리
	for _, s in { { 0, -31, 64, 2 }, { 0, 31, 64, 2 }, { -31, 0, 2, 60 }, { 31, 0, 2, 60 } } do
		block(village, "Teduri", V3(s[3], 3.2, s[4]), CF(s[1], PLAZA_TOP + 0.2 - 1.6, s[2]), P.granite, Mat.Granite)
	end
	-- 영맥 둘레 팔각 돌판과 네 갈래 길 무늬, 율점 자리 둥근 돌판
	for _, a in { 22.5, 67.5 } do
		block(
			village,
			"Palgak",
			V3(31, 0.1, 31),
			CF(0, PLAZA_TOP + 0.02, 0) * CFrame.Angles(0, math.rad(a), 0),
			P.graniteDark,
			Mat.Granite
		)
	end
	for _, d in { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } } do
		local size = if d[1] ~= 0 then V3(14.5, 0.1, 3.2) else V3(3.2, 0.1, 14.5)
		block(village, "Gilmunui", size, CF(d[1] * 22.75, PLAZA_TOP + 0.02, d[2] * 22.75), P.graniteDark, Mat.Granite)
	end
	local lu = folder(village, "율점")
	for cluster, center in LU_CLUSTERS do
		disc(lu, "Jari", center + V3(0, 0.03, 0), 6.4, 0.1, P.granite, Mat.Granite)
		for k = 0, 2 do
			local index = (cluster - 1) * 3 + k + 1
			local angle = math.rad(90 + k * 120)
			luLantern(lu, index, center + V3(math.cos(angle), 0, math.sin(angle)) * 4.5, center)
		end
	end
	siteMarker(model(village, SITE.plaza.name), "plaza", V3(0, 1, 0), 12)
	take(0, 0, 33)
end

-- 연단로: 팔각 받침 위 벽돌 아궁이와 세 발 솥
local function buildFurnace(village: Instance)
	local m = model(village, "연단로")
	local s = SITE.furnace
	local base = V3(s.x, PLAZA_TOP, s.z)
	for _, yaw in { 0, 45 } do
		block(
			m,
			"Batchim",
			V3(7.2, 0.8, 7.2),
			CF(base + V3(0, 0.3, 0)) * CFrame.Angles(0, math.rad(yaw), 0),
			P.granite,
			Mat.Granite
		)
	end
	block(m, "Agungi", V3(4.6, 2.2, 4.6), CF(base + V3(0, 1.8, 0)), Color3.fromRGB(122, 74, 56), Mat.Brick)
	local ember =
		block(m, "Ember", V3(2.0, 1.1, 0.3), CF(base + V3(0, 1.6, 2.32)), Color3.fromRGB(255, 120, 50), Mat.Neon)
	ember.CanCollide = false
	light(ember, Color3.fromRGB(255, 140, 70), 12, 1.6)
	for k = 0, 2 do
		local a = math.rad(90 + k * 120)
		local foot = base + V3(math.cos(a) * 1.6, 2.9, math.sin(a) * 1.6)
		cyl(m, "Bal", foot, foot + V3(0, 1.3, 0), 0.55, BRONZE, Mat.Metal)
	end
	local pot = cyl(m, "Sot", base + V3(0, 4.1, 0), base + V3(0, 6.6, 0), 4.4, BRONZE, Mat.Metal)
	for _, sx in { -1, 1 } do
		block(m, "Gwi", V3(0.35, 1.3, 1.2), CF(base + V3(sx * 2.25, 7.0, 0)), BRONZE:Lerp(P.meok, 0.3), Mat.Metal)
	end
	cyl(m, "Ttukkeong", base + V3(0, 6.6, 0), base + V3(0, 7.1, 0), 4.0, BRONZE:Lerp(P.meok, 0.2), Mat.Metal)
	ball(m, "Kkokji", base + V3(0, 7.45, 0), 0.8, P.hwang, Mat.Metal)
	local smoke = Instance.new("Smoke")
	smoke.Size = 2
	smoke.RiseVelocity = 3
	smoke.Opacity = 0.15
	smoke.Parent = pot
	siteMarker(m, "furnace", base + V3(0, 2.5, 0), 6, "연단")
	signboard(m, V3(base.X + 6, PLAZA_TOP, base.Z + 3), "연단로", V3(0, PLAZA_TOP, 0))
	take(base.X, base.Z, 5)
end

-- 대장간: 동쪽 길 남쪽의 맞배지붕 헛간. 동쪽에 화덕과 굴뚝, 가운데 모루(F: 무기 강화), 서쪽 들보에 현판
local SMITHY = V3(60, 0, 18)
local function buildSmithy(village: Instance)
	local m = model(village, "대장간")
	local b = SMITHY
	block(m, "Badak", V3(16, 0.3, 14), CF(b + V3(0, 0.1, 0)), Color3.fromRGB(110, 92, 74), Mat.Ground)
	local postTop = 8.6
	for _, x in { -7.5, 7.5 } do
		for _, z in { -6.5, 0, 6.5 } do
			block(m, "Post", V3(0.8, postTop + 0.5, 0.8), CF(b + V3(x, postTop / 2 - 0.25, z)), P.wood, Mat.Wood)
		end
		block(m, "Dori", V3(0.9, 0.9, 14.4), CF(b + V3(x, postTop + 0.2, 0)), P.woodDark, Mat.Wood)
	end
	for _, z in { -6.5, 6.5 } do
		block(m, "Bo", V3(16, 0.8, 0.8), CF(b + V3(0, postTop + 0.2, z)), P.woodDark, Mat.Wood)
	end
	-- 맞배지붕 (용마루가 동서로)
	local spec = {
		ex = 9.6,
		ez = 9.2,
		eave = 2.4,
		bands = 2,
		kind = "gable",
		lift = 0,
		flare = 0,
		pitchLow = 20,
		pitchHigh = 36,
		t = 0.6,
		segs = 1,
	}
	local _, _, hh, pitches = Build.profile(spec)
	local under = hh[1] - 0.6 / math.cos(math.rad(pitches[1]))
	Build.roof(m, CF(b + V3(0, postTop + 0.65 - under, 0)), spec)
	-- 화덕과 굴뚝, 풀무
	block(m, "Hwadeok", V3(4.6, 3.4, 5), CF(b + V3(5, 1.7, 0)), Color3.fromRGB(110, 70, 54), Mat.Brick)
	local flame = block(m, "Flame", V3(2.6, 1.2, 2.6), CF(b + V3(5, 3.7, 0)), Color3.fromRGB(255, 120, 50), Mat.Neon)
	flame.CanCollide = false
	local fire = Instance.new("Fire")
	fire.Size = 4
	fire.Heat = 8
	fire.Parent = flame
	light(flame, Color3.fromRGB(255, 150, 80), 18, 1.8)
	block(m, "Gulttuk", V3(2, 13.5, 2), CF(b + V3(6.4, 6.75, -1.6)), Color3.fromRGB(104, 66, 52), Mat.Brick)
	block(m, "Pulmu", V3(2.2, 1.4, 1.6), CF(b + V3(5, 0.85, 4.2)), P.woodDark, Mat.Wood)
	beam(m, "Pulmudae", b + V3(4, 1.6, 4.2), b + V3(2.6, 2.6, 4.2), 0.2, 0.2, P.wood, Mat.Wood)
	-- 모루: 무기를 벼리는 자리 (늙은 대장장이 말 걸기 버튼과 13 넘게 떨어져 있다)
	local iron = Color3.fromRGB(84, 84, 90)
	local anvil = b + V3(-1, 0, 0)
	block(m, "Anvil", V3(1.6, 1.9, 1.6), CF(anvil + V3(0, 0.95, 0)), C.stoneDark, Mat.Slate)
	block(m, "AnvilFace", V3(3.0, 0.5, 1.2), CF(anvil + V3(0, 2.15, 0)), iron, Mat.Metal)
	block(m, "AnvilHorn", V3(0.9, 0.35, 0.7), CF(anvil + V3(1.9, 2.2, 0)), iron, Mat.Metal)
	block(m, "HammerHead", V3(0.45, 0.45, 0.9), CF(anvil + V3(-0.6, 2.62, 0.1)), C.stoneDark, Mat.Metal)
	block(m, "HammerHandle", V3(1.5, 0.18, 0.18), CF(anvil + V3(0.3, 2.52, 0.1)), C.wood, Mat.Wood)
	marketSpot(m, "smith", anvil + V3(0, 2.8, 0), "대장간", "법구 강화·제작")
	-- 담금질 물통과 숯 더미
	block(m, "Multong", V3(2.6, 1.2, 1.4), CF(b + V3(1.5, 0.6, -4.6)), P.woodDark, Mat.Wood)
	block(m, "Mul", V3(2.2, 0.1, 1.0), CF(b + V3(1.5, 1.16, -4.6)), Color3.fromRGB(46, 70, 80), Mat.Glass)
	block(
		m,
		"Sut",
		V3(1.8, 0.8, 1.6),
		CF(b + V3(5.6, 0.4, -4.4)) * CFrame.Angles(0, 0.4, 0.15),
		Color3.fromRGB(40, 38, 38),
		Mat.Slate
	)
	-- 벼린 칼을 세워 둔 시렁 (남쪽)
	local steel = Color3.fromRGB(170, 172, 178)
	for _, x in { -5.4, -1.4 } do
		block(m, "RackPost", V3(0.3, 3.4, 0.3), CF(b + V3(x, 1.7, 5.6)), C.wood, Mat.Wood)
	end
	for _, y in { 0.7, 2.9 } do
		block(m, "RackBar", V3(4.4, 0.25, 0.3), CF(b + V3(-3.4, y, 5.6)), C.wood, Mat.Wood)
	end
	for i = 0, 2 do
		local x = -4.6 + i * 1.2
		block(m, "Blade", V3(0.3, 2.6, 0.08), CF(b + V3(x, 1.9, 5.45)), steel, Mat.Metal)
		block(m, "Guard", V3(0.6, 0.15, 0.2), CF(b + V3(x, 3.25, 5.45)), C.gold, Mat.Metal)
		block(m, "Hilt", V3(0.18, 0.7, 0.18), CF(b + V3(x, 3.65, 5.45)), C.lacquer, Mat.Wood)
	end
	-- 서쪽(광장 쪽) 들보에 매단 현판
	for _, z in { -2.2, 2.2 } do
		block(m, "Cord", V3(0.1, 0.4, 0.1), CF(b + V3(-7.9, postTop - 0.45, z)), C.woodDark, Mat.Fabric)
	end
	local signPos = b + V3(-7.9, postTop - 1.5, 0)
	local sign = block(m, "Board", V3(6.1, 1.7, 0.3), face(signPos, signPos - V3(1, 0, 0)), C.lacquer, Mat.Wood)
	engrave(sign, "대장간", "Front,Back")
	Build.banner(m, b + V3(-9.5, 0, -7.5), b + V3(-20, 0, -7.5), Color3.fromRGB(70, 74, 86), 9)
	take(b.X, b.Z, 10)
end

-- 마을 노인이 앉는 자리. 사람은 서버가 띄울 때 카탈로그 옷을 입혀 앉힌다(Villagers.luau).
-- 여기서는 앉을 돌, 앉는 자리(Seat, 속성 NpcSeat), 과업 자리, 노인마다 곁의 살림만 짓는다.
local function buildElders(village: Instance)
	local elders = folder(village, "노인")
	for _, def in ELDERS do
		local s = SITE[def.id]
		local m = model(elders, s.name)
		local base = V3(s.x, def.y, s.z)
		local look = face(base, V3(def.faces.X, base.Y, def.faces.Z))
		block(m, "Stool", V3(3, 1.6, 3), look * CF(0, 0.8, 0), C.stone, Mat.Slate)
		local seat = Instance.new("Seat")
		seat.Name = "자리"
		seat.Anchored = true
		seat.Size = V3(2, 0.2, 2)
		seat.CFrame = look * CF(0, 1.7, 0)
		seat.Transparency = 1
		seat.CanCollide = false
		seat:SetAttribute("NpcSeat", def.id)
		seat.Parent = m
		if def.id == "elder_1" then
			-- 말리는 약초 시렁과 약초 바구니
			for _, x in { -2.2, 2.2 } do
				block(m, "RackPost", V3(0.3, 4, 0.3), look * CF(x, 2, 2.6), C.wood, Mat.Wood)
			end
			block(m, "RackBar", V3(4.8, 0.25, 0.25), look * CF(0, 3.8, 2.6), C.wood, Mat.Wood)
			for i = -2, 2 do
				block(m, "Herb", V3(0.5, 1, 0.3), look * CF(i * 0.9, 3.2, 2.6), C.leafLight, Mat.Grass)
			end
			local basket = block(
				m,
				"Basket",
				V3(1, 1.6, 1.6),
				look * CF(2.4, 0.5, -0.6) * CFrame.Angles(0, 0, math.rad(90)),
				Color3.fromRGB(176, 140, 86),
				Mat.Fabric
			)
			basket.Shape = Enum.PartType.Cylinder
			block(m, "Herbs", V3(1.2, 0.4, 1.2), look * CF(2.4, 1.1, -0.6), C.leaf, Mat.Grass)
		elseif def.id == "elder_2" then
			-- 쇠막대 몇 개와 물통
			for i = 0, 2 do
				block(m, "Bar", V3(0.3, 0.3, 3), look * CF(-2.2 + i * 0.4, 0.2, 0.4), C.stoneDark, Mat.Metal)
			end
			local bucket = block(
				m,
				"Bucket",
				V3(1.2, 1.4, 1.4),
				look * CF(2.3, 0.6, 0.4) * CFrame.Angles(0, 0, math.rad(90)),
				C.woodDark,
				Mat.Wood
			)
			bucket.Shape = Enum.PartType.Cylinder
		elseif def.id == "elder_3" then
			-- 벽계 물가에 매어 둔 작은 나룻배 (수면 -1)
			local boat = model(m, "나룻배")
			local boatCf = CF(-95, -0.9, 26) * CFrame.Angles(0, math.rad(90), 0)
			block(boat, "Hull", V3(3, 0.6, 9), boatCf, C.wood, Mat.WoodPlanks)
			for _, x in { -1.4, 1.4 } do
				block(boat, "Side", V3(0.3, 0.8, 9), boatCf * CF(x, 0.6, 0), C.woodDark, Mat.WoodPlanks)
			end
			for _, z in { -4.4, 4.4 } do
				block(boat, "Kkeut", V3(2.8, 0.9, 0.4), boatCf * CF(0, 0.55, z), C.woodDark, Mat.WoodPlanks)
			end
			block(boat, "Seat", V3(2.6, 0.3, 0.8), boatCf * CF(0, 0.5, 1.5), C.woodDark, Mat.Wood)
			beam(
				boat,
				"No",
				(boatCf * CF(0.6, 0.9, -1)).Position,
				(boatCf * CF(1.0, 0.7, 3.6)).Position,
				0.2,
				0.2,
				C.wood,
				Mat.Wood
			)
			block(m, "Post", V3(0.5, 7, 0.5), CF(-87.5, -1.5, 26), C.woodDark, Mat.Wood)
			beam(
				m,
				"Batjul",
				V3(-87.5, 1.2, 26),
				(boatCf * CF(0, 0.6, -4)).Position,
				0.12,
				0.12,
				STRAW_DARK,
				Mat.Fabric
			)
		end
		siteMarker(m, def.id, base + V3(0, 3, 0), 7, s.name)
		take(base.X, base.Z, 3)
	end
end

-- 만물상: 줄무늬 차양을 친 판대. 앞 판대에 물건을 늘어놓고, 뒤 벽에 선반과 무기를 건다.
-- 판대 가운데에 상점 자리(F 버튼)를 두고, 주인은 그 뒤 걸상에 앉아 손님 쪽을 본다
local function buildStall(parent: Instance)
	local m = model(parent, "만물상")
	local ground = at(STALL.position.X, STALL.position.Z)
	local look = face(ground, Vector3.new(STALL.faces.X, ground.Y, STALL.faces.Z))
	local function put(name: string, size: Vector3, x: number, y: number, z: number, color: Color3, material)
		return block(m, name, size, look * CFrame.new(x, y, z), color, material)
	end
	local function upright(
		name: string,
		length: number,
		diameter: number,
		x: number,
		y: number,
		z: number,
		color,
		material
	)
		-- 원기둥을 세운다 (Cylinder 의 축은 X)
		local part = block(
			m,
			name,
			Vector3.new(length, diameter, diameter),
			look * CFrame.new(x, y, z) * CFrame.Angles(0, 0, math.rad(90)),
			color,
			material
		)
		part.Shape = Enum.PartType.Cylinder
		return part
	end

	-- 바닥과 기둥: 앞 기둥이 낮아 차양이 앞으로 비탈진다
	put("Deck", Vector3.new(12.4, 0.5, 8), 0, 0.25, 1.4, C.wood, Enum.Material.WoodPlanks)
	local frontTop, backTop = 9.2, 11
	for _, x in { -5.8, 5.8 } do
		put("Post", Vector3.new(0.7, frontTop, 0.7), x, frontTop / 2, -2.2, C.woodDark, Enum.Material.Wood)
		put("Post", Vector3.new(0.7, backTop, 0.7), x, backTop / 2, 5, C.woodDark, Enum.Material.Wood)
	end
	put("Beam", Vector3.new(12.6, 0.5, 0.5), 0, frontTop - 0.25, -2.2, C.wood, Enum.Material.Wood)
	put("Beam", Vector3.new(12.6, 0.5, 0.5), 0, backTop - 0.25, 5, C.wood, Enum.Material.Wood)
	local rise, run = backTop - frontTop, 7.2
	local slope = math.atan2(rise, run)
	local railY = frontTop - 0.25 + rise / 2
	for _, x in { -5.8, 5.8 } do
		block(
			m,
			"Rail",
			Vector3.new(0.5, 0.5, run / math.cos(slope) + 0.4),
			look * CFrame.new(x, railY, 1.4) * CFrame.Angles(-slope, 0, 0),
			C.wood,
			Enum.Material.Wood
		)
	end

	-- 줄무늬 차양과 앞 끝에 늘어뜨린 천
	local stripes, width, length = 7, 13.4, 9.7
	local strip = width / stripes
	local centerZ = 0.9
	local centerY = railY + (centerZ - 1.4) * math.tan(slope) + 0.36
	local edgeZ = centerZ - length / 2 * math.cos(slope)
	local edgeY = centerY - length / 2 * math.sin(slope)
	for i = 1, stripes do
		local x = -width / 2 + (i - 0.5) * strip
		local red = i % 2 == 1
		block(
			m,
			"Awning",
			Vector3.new(strip + 0.02, 0.2, length),
			look * CFrame.new(x, centerY, centerZ) * CFrame.Angles(-slope, 0, 0),
			if red then C.red else C.felt,
			Enum.Material.Fabric
		)
		put(
			"Valance",
			Vector3.new(strip + 0.02, 0.9, 0.12),
			x,
			edgeY - 0.5,
			edgeZ,
			if red then C.felt else C.red,
			Enum.Material.Fabric
		)
	end

	-- 뒤 벽, 선반, 걸어 둔 무기 (만물상에서 파는 창·도·선)
	put("Back", Vector3.new(10.9, 6, 0.3), 0, 3.5, 5.2, C.woodDark, Enum.Material.WoodPlanks)
	-- 뒤 벽 바깥 띠목 (전송진 쪽에서 보이는 면)
	for _, y in { 1.4, 5.6 } do
		put("Batten", Vector3.new(10.9, 0.3, 0.15), 0, y, 5.42, C.wood, Enum.Material.Wood)
	end
	for _, x in { -2.7, 2.7 } do
		put("Batten", Vector3.new(0.3, 6, 0.15), x, 3.5, 5.42, C.wood, Enum.Material.Wood)
	end
	put("Shelf", Vector3.new(10.4, 0.25, 1.1), 0, 4.4, 4.5, C.wood, Enum.Material.Wood)
	for _, x in { -4.6, 4.6 } do
		put("Bracket", Vector3.new(0.3, 0.6, 0.8), x, 3.98, 4.6, C.woodDark, Enum.Material.Wood)
	end
	local shelfTop = 4.525
	for i, color in { C.jade, C.plaster, C.red } do
		local x = -5.2 + i
		upright("Jar", 0.9, 0.7, x, shelfTop + 0.45, 4.5, color, Enum.Material.SmoothPlastic)
		put("Cork", Vector3.new(0.3, 0.2, 0.3), x, shelfTop + 1, 4.5, C.dirt, Enum.Material.Wood)
	end
	put("Box", Vector3.new(1, 0.7, 0.8), 2.4, shelfTop + 0.35, 4.5, C.gold, Enum.Material.Fabric)
	put("Box", Vector3.new(0.9, 0.6, 0.8), 3.6, shelfTop + 0.3, 4.5, C.roof, Enum.Material.Fabric)
	put("Box", Vector3.new(0.7, 0.45, 0.6), 3.0, shelfTop + 0.92, 4.5, C.red, Enum.Material.Fabric)
	for i = 0, 1 do
		local scroll = block(
			m,
			"Scroll",
			Vector3.new(1.6, 0.35, 0.35),
			look * CFrame.new(0.4, shelfTop + 0.18 + i * 0.34, 4.45 - i * 0.08),
			C.felt,
			Enum.Material.Fabric
		)
		scroll.Shape = Enum.PartType.Cylinder
	end
	local steel = Color3.fromRGB(170, 172, 178)
	put("SpearShaft", Vector3.new(8, 0.22, 0.22), -0.4, 6, 4.9, C.wood, Enum.Material.Wood)
	put("SpearHead", Vector3.new(1.2, 0.5, 0.1), 4.2, 6, 4.9, steel, Enum.Material.Metal)
	put("Tassel", Vector3.new(0.4, 0.5, 0.4), 3.4, 5.75, 4.9, C.red, Enum.Material.Fabric)
	put("SaberHilt", Vector3.new(0.22, 0.7, 0.22), -3.8, 3.75, 4.95, C.lacquer, Enum.Material.Wood)
	put("SaberGuard", Vector3.new(0.8, 0.2, 0.22), -3.8, 3.3, 4.95, C.gold, Enum.Material.Metal)
	put("SaberBlade", Vector3.new(0.5, 2.4, 0.08), -3.7, 2.0, 4.97, steel, Enum.Material.Metal)
	for k = -2, 2 do
		block(
			m,
			"FanLeaf",
			Vector3.new(0.45, 1.6, 0.06),
			look * CFrame.new(3.8, 2.0, 4.97) * CFrame.Angles(0, 0, math.rad(k * 18)) * CFrame.new(0, 0.8, 0),
			if k % 2 == 0 then C.felt else C.plaster,
			Enum.Material.Wood
		)
	end

	-- 판대: 붉은 천을 덮고 물건을 늘어놓는다
	put("Plinth", Vector3.new(11.2, 0.4, 2), 0, 0.2, -1.7, C.woodDark, Enum.Material.Wood)
	put("Counter", Vector3.new(11, 2.9, 1.8), 0, 1.45, -1.7, C.wood, Enum.Material.WoodPlanks)
	put("CounterTop", Vector3.new(11.6, 0.3, 2.3), 0, 3.05, -1.75, C.lacquer, Enum.Material.Wood)
	put("Runner", Vector3.new(5.5, 0.06, 2.3), 0, 3.23, -1.75, C.red, Enum.Material.Fabric)
	put("Runner", Vector3.new(5.5, 1.6, 0.08), 0, 2.45, -2.94, C.red, Enum.Material.Fabric)
	local top = 3.2
	-- 영석 한 소반 (빛이 은은히 돈다)
	local stoneColor = Color3.fromRGB(130, 230, 235)
	local tray = put("Tray", Vector3.new(2.2, 0.25, 1.4), -3.8, top + 0.125, -1.7, C.woodDark, Enum.Material.Wood)
	light(tray, stoneColor, 7, 0.8)
	for i, spec in
		{
			{ -0.7, -0.3, 0.45 },
			{ -0.2, 0.25, 0.4 },
			{ 0.4, -0.2, 0.5 },
			{ 0.75, 0.3, 0.38 },
			{ -0.6, 0.35, 0.35 },
			{ 0.1, -0.35, 0.36 },
			{ 0.15, 0.05, 0.42 },
		}
	do
		local size = spec[3]
		local crystal = block(
			m,
			"Stone",
			Vector3.new(size, size * 1.3, size),
			look
				* CFrame.new(-3.8 + spec[1], top + 0.25 + size * 0.5, -1.7 + spec[2])
				* CFrame.Angles(math.rad(i * 23), math.rad(i * 47), math.rad(i * 31)),
			stoneColor,
			Enum.Material.Neon
		)
		crystal.Transparency = 0.15
	end
	-- 영초 다발
	for i = 0, 2 do
		local x = -2.1 + i * 0.5
		put("Herbs", Vector3.new(0.4, 0.4, 1.2), x, top + 0.26, -1.8, C.leafLight, Enum.Material.Grass)
		put("Tie", Vector3.new(0.45, 0.45, 0.15), x, top + 0.26, -1.8, C.felt, Enum.Material.Fabric)
	end
	-- 주판
	put("Abacus", Vector3.new(1.8, 0.12, 1), 0.9, top + 0.1, -1.6, C.woodDark, Enum.Material.Wood)
	for row = 0, 2 do
		local z = -1.9 + row * 0.3
		put("Rod", Vector3.new(1.6, 0.06, 0.06), 0.9, top + 0.2, z, C.gold, Enum.Material.Metal)
		for bead = 0, 1 do
			put("Bead", Vector3.new(0.18, 0.16, 0.18), 0.5 + bead * 0.25 + row * 0.15, top + 0.24, z, C.red)
		end
	end
	-- 영약 병과 요단 한 사발
	for i, color in { C.jade, C.plaster } do
		local x = 1.6 + i * 0.75
		upright("Bottle", 0.8, 0.5, x, top + 0.46, -1.8, color, Enum.Material.SmoothPlastic)
		put("Cork", Vector3.new(0.22, 0.16, 0.22), x, top + 0.94, -1.8, C.red, Enum.Material.Wood)
	end
	disc(m, "Bowl", (look * CFrame.new(4.3, top + 0.18, -1.75)).Position, 0.65, 0.3, C.woodDark, Enum.Material.Wood)
	for _, offset in
		{ Vector3.new(-0.2, 0, -0.15), Vector3.new(0.2, 0, -0.1), Vector3.new(0, 0, 0.2), Vector3.new(0.05, 0.25, 0) }
	do
		ball(
			m,
			"Yodan",
			(look * CFrame.new(4.3 + offset.X, top + 0.5 + offset.Y, -1.75 + offset.Z)).Position,
			0.35,
			Color3.fromRGB(230, 120, 60),
			Enum.Material.Neon
		)
	end
	marketSpot(m, "market", (look * CFrame.new(0, top + 0.3, -1.7)).Position, "상점", "만물상")

	-- 주인이 앉는 걸상 (Villagers.luau 가 앉힌다)
	put("Stool", Vector3.new(2.2, 1.9, 2.2), 0, 1.45, 1.4, C.woodDark, Enum.Material.Wood)
	local seat = Instance.new("Seat")
	seat.Name = "자리"
	seat.Anchored = true
	seat.Size = Vector3.new(2, 0.2, 2)
	seat.CFrame = look * CFrame.new(0, 2.5, 1.4)
	seat.Transparency = 1
	seat.CanCollide = false
	seat:SetAttribute("NpcSeat", STALL.id)
	seat.Parent = m

	-- 앞 들보에 매단 현판과 양쪽 기둥의 등롱
	for _, x in { -2.2, 2.2 } do
		put("Cord", Vector3.new(0.1, 0.5, 0.1), x, frontTop - 0.75, -2.2, C.woodDark, Enum.Material.Fabric)
	end
	local board = put("Board", Vector3.new(6.1, 1.7, 0.3), 0, frontTop - 1.85, -2.2, C.lacquer, Enum.Material.Wood)
	engrave(board, "만물상", "Front,Back")
	put("Trim", Vector3.new(6.5, 0.2, 0.4), 0, frontTop - 0.9, -2.2, C.red)
	for _, x in { -5.8, 5.8 } do
		put("Bracket", Vector3.new(0.2, 0.2, 1.1), x, frontTop - 1.3, -3, C.woodDark, Enum.Material.Wood)
		put("Cord", Vector3.new(0.08, 0.5, 0.08), x, frontTop - 1.6, -3.45, C.woodDark, Enum.Material.Fabric)
		local lamp = put("Lamp", Vector3.new(1, 1.3, 1), x, frontTop - 2.5, -3.45, C.red, Enum.Material.Neon)
		light(lamp, Color3.fromRGB(255, 170, 120), 12, 1.2)
	end

	-- 곁에 쌓은 궤짝과 자루, 나무통
	put("Crate", Vector3.new(2, 2, 2), 7.6, 1, 2.6, C.wood, Enum.Material.WoodPlanks)
	put("Band", Vector3.new(2.06, 0.25, 2.06), 7.6, 1.6, 2.6, C.woodDark, Enum.Material.Wood)
	block(
		m,
		"Crate",
		Vector3.new(1.6, 1.6, 1.6),
		look * CFrame.new(7.5, 2.8, 2.5) * CFrame.Angles(0, math.rad(15), 0),
		C.wood,
		Enum.Material.WoodPlanks
	)
	block(
		m,
		"Sack",
		Vector3.new(1.4, 1.5, 1.2),
		look * CFrame.new(7.5, 0.75, 0.3) * CFrame.Angles(0, math.rad(-10), 0),
		C.felt,
		Enum.Material.Fabric
	)
	put("SackTie", Vector3.new(0.5, 0.3, 0.5), 7.5, 1.6, 0.3, C.dirt, Enum.Material.Fabric)
	upright("Barrel", 2.4, 1.8, -7.3, 1.2, 2.8, C.wood, Enum.Material.Wood)
	for _, y in { 0.5, 1.9 } do
		upright("Hoop", 0.15, 1.9, -7.3, y, 2.8, C.woodDark, Enum.Material.Metal)
	end
	put("Herbs", Vector3.new(1.2, 0.5, 1.2), -7.3, 2.65, 2.8, C.leaf, Enum.Material.Grass)
	take(STALL.position.X, STALL.position.Z, 9)
	return m
end

-- 집 자리 ---------------------------------------------------------------------------------

local HOUSE_3 = { bays = { 3, 2 }, bay = 5.2, roof = "gable", detail = 0, bands = 3 }
local HOUSES = {
	{ x = -22, z = -52, tx = -22, tz = 0, opts = HOUSE_3, tree = "persimmon" },
	{
		x = 24,
		z = -54,
		tx = 24,
		tz = 0,
		opts = { bays = { 4, 2 }, bay = 5.2, roof = "paljak", detail = 1, bands = 3, name = "촌장댁" },
		tree = "pine",
	},
	{
		x = -54,
		z = -24,
		tx = 0,
		tz = -24,
		opts = { bays = { 3, 2 }, bay = 5.2, roof = "paljak", detail = 1, bands = 3 },
		tree = "blossom",
	},
	{ x = -52, z = 26, tx = 0, tz = 26, opts = HOUSE_3, tree = "persimmon" },
	{ x = -24, z = 54, tx = -24, tz = 0, opts = HOUSE_3, tree = "blossom" },
	{ x = 60, z = 46, tx = 0, tz = 46, opts = HOUSE_3, tree = "persimmon" },
}

-- 초가: { x, z, 앞이 볼 곳 x, z, 너비, 깊이, 울타리, 장독, 볏가리, 장작 }
local CHOGA = {
	{ 96, -42, 96, 0, 11, 8.5, true, true, false, true },
	{ 40, -98, 40, -60, 10, 8, true, false, true, false },
	{ -40, -92, -40, -50, 11, 8.5, false, true, true, true },
	{ -46, 92, -46, 40, 11, 8.5, true, true, true, false },
	{ 28, 100, 28, 50, 10, 8, false, false, true, true },
	{ 112, 30, 60, 30, 11, 8.5, true, true, true, false },
}

local function yardTree(parent: Instance, kind: string, base: Vector3, rng)
	if kind == "persimmon" then
		persimmon(parent, base, rng)
	elseif kind == "pine" then
		Build.pine(parent, base, rng, { height = rng(13, 16) })
	else
		Build.blossom(parent, base, rng, { blobs = 7 })
	end
end

local function buildHouses(village: Instance, rng)
	local houses = folder(village, "집")
	for _, def in HOUSES do
		local m, cf = houseAt(houses, def.x, def.z, def.tx, def.tz, def.opts)
		-- 뒤뜰: 기와 얹은 돌담 셋 (왼쪽 담에 쪽문 틈), 장독대와 나무 한 그루
		local W = def.opts.bays[1] * def.opts.bay + 4.4
		local D = def.opts.bays[2] * def.opts.bay + 4.4
		local hw, back, far = W / 2, D / 2 - 3, D / 2 + 11
		local function p(x: number, z: number): Vector3
			local q = cf:PointToWorldSpace(V3(x, 0, z))
			return V3(q.X, Land.surface(q.X, q.Z), q.Z)
		end
		Build.stoneWall(m, p(-hw, back), p(-hw, far - 5.5))
		Build.stoneWall(m, p(-hw, far - 2.5), p(-hw, far))
		Build.stoneWall(m, p(-hw, far), p(hw, far))
		Build.stoneWall(m, p(hw, far), p(hw, back))
		Build.jars(m, cf * CF(hw * 0.45, 0, D / 2 + 5.6) * CFrame.Angles(0, math.rad(180), 0), rng, 4)
		local t = cf:PointToWorldSpace(V3(-hw * 0.45, 0, D / 2 + 6))
		yardTree(m, def.tree, V3(t.X, Land.surface(t.X, t.Z), t.Z), rng)
		local q = cf:PointToWorldSpace(V3(0, 0, D / 2 + 4))
		take(q.X, q.Z, math.max(W, 12) / 2 + 1)
		if def.opts.name == "촌장댁" then
			-- 촌장댁 앞마당: 소나무 둘과 깃발
			for _, sx in { -1, 1 } do
				local f = cf:PointToWorldSpace(V3(sx * (hw + 3.5), 0, -D / 2 - 1))
				Build.pine(m, V3(f.X, Land.surface(f.X, f.Z), f.Z), rng, { height = rng(14, 17) })
				take(f.X, f.Z, 3)
			end
		end
	end
	for _, def in CHOGA do
		local x, z, w, d = def[1], def[2], def[5], def[6]
		local m, cf = choga(houses, x, z, def[3], def[4], w, d)
		local function p(lx: number, lz: number): Vector3
			local q = cf:PointToWorldSpace(V3(lx, 0, lz))
			return V3(q.X, Land.surface(q.X, q.Z), q.Z)
		end
		local fx, fz = w / 2 + 2.6, -(d / 2 + 9)
		if def[7] then
			-- 앞마당 싸리 울타리 (가운데 사립문 틈)
			wattle(m, p(-fx, -d / 2 - 1.5), p(-fx, fz))
			wattle(m, p(-fx, fz), p(-1.8, fz))
			wattle(m, p(1.8, fz), p(fx, fz))
			wattle(m, p(fx, fz), p(fx, -d / 2 - 1.5))
		end
		if def[8] then
			Build.jars(m, CF(p(w / 2 - 0.5, -d / 2 - 6)) * (cf - cf.Position), rng, 4)
		end
		if def[9] then
			haystack(m, p(-w / 2 + 1, -d / 2 - 6), rng(2.6, 3.4))
		end
		if def[10] then
			woodpile(m, CF(p(-(w / 2 + 2.2), 0.5)) * (cf - cf.Position))
		end
		local q = cf:PointToWorldSpace(V3(0, 0, -d / 2 - 5))
		take(q.X, q.Z, w / 2 + 2)
	end
end

-- 마을 어귀 -------------------------------------------------------------------------------

-- 길(Land.ROADS[i])이 송계에서 반지름 r 을 넘는 자리와 그 안쪽(마을 쪽) 점
local function roadCrossing(index: number, r: number): (Vector3, Vector3)
	local road = Land.ROADS[index]
	for i = 1, #road - 1 do
		local a, b = road[i], road[i + 1]
		local ra, rb = math.sqrt(a[1] ^ 2 + a[2] ^ 2), math.sqrt(b[1] ^ 2 + b[2] ^ 2)
		if ra <= r and rb >= r then
			local lo, hi = 0, 1
			for _ = 1, 30 do
				local mid = (lo + hi) / 2
				local x, z = a[1] + (b[1] - a[1]) * mid, a[2] + (b[2] - a[2]) * mid
				if x * x + z * z < r * r then
					lo = mid
				else
					hi = mid
				end
			end
			local x, z = a[1] + (b[1] - a[1]) * lo, a[2] + (b[2] - a[2]) * lo
			return V3(x, 0, z), V3(a[1], 0, a[2])
		end
	end
	error("길이 그 반지름을 넘지 않는다: " .. index)
end

-- 홍살문: 붉은 두 기둥과 가로대 둘, 위로 솟은 붉은 살, 가운데 둥근 태극 판. 현판(board)을 돌려준다
local function hongsalmun(parent: Instance, ground: Vector3, toward: Vector3, width: number?)
	local w = width or 12
	local m = model(parent, "홍살문")
	local look = face(ground, V3(toward.X, ground.Y, toward.Z))
	local red = Color3.fromRGB(168, 52, 40)
	local H = 10.5
	local function W(x: number, y: number, z: number): Vector3
		return (look * CF(x, y, z)).Position
	end
	for _, s in { -1, 1 } do
		block(m, "Choseok", V3(1.9, 1.0, 1.9), look * CF(s * w / 2, 0.1, 0), P.granite, Mat.Granite)
		cyl(m, "Gidung", W(s * w / 2, 0.5, 0), W(s * w / 2, H + 0.4, 0), 1.1, red, Mat.Wood)
	end
	for _, y in { H - 3.4, H - 0.6 } do
		beam(m, "Garodae", W(-w / 2 - 0.9, y, 0), W(w / 2 + 0.9, y, 0), 0.5, 0.6, red, Mat.Wood)
	end
	for i = 1, 8 do
		local x = -w / 2 + w * i / 9
		if math.abs(x) > 1.4 then
			beam(m, "Sal", W(x, H - 3.4, 0), W(x, H + 2.0, 0), 0.24, 0.24, red, Mat.Wood)
		end
	end
	cyl(m, "Taegeuk", W(0, H + 1.0, -0.15), W(0, H + 1.0, 0.15), 2.3, P.juhong, Mat.Wood)
	cyl(m, "Taegeuk", W(-0.3, H + 0.62, -0.18), W(-0.3, H + 0.62, -0.16), 1.15, P.gunjeong, Mat.Wood)
	beam(m, "Samjichang", W(0, H + 2.15, 0), W(0, H + 3.6, 0), 0.22, 0.22, red, Mat.Wood)
	local board = block(m, "Hyeonpan", V3(4.4, 1.6, 0.3), look * CF(0, H - 2.0, -0.4), P.meok, Mat.Wood)
	block(m, "Te", V3(4.9, 2.0, 0.25), look * CF(0, H - 2.0, -0.28), P.hwang, Mat.Wood)
	return m, board
end

-- 마을 어귀 문 셋: 북(명경호 길)·동(만년목 길)은 일주문, 남동(홍로성 길)은 홍살문. 현판 앞이 마을을 본다
local GATES = {
	{ road = 1, sign = "명경호, 북진대", kind = "iljumun" },
	{ road = 4, sign = "만년목, 조양대", kind = "iljumun" },
	{ road = 5, sign = "홍로성, 무택", kind = "hongsal" },
}
local GATE_R = 118

local function buildGates(village: Instance)
	local gates = folder(village, "어귀")
	for _, def in GATES do
		local p, inner = roadCrossing(def.road, GATE_R)
		local dir = (inner - p).Unit -- 마을 쪽
		local side = V3(-dir.Z, 0, dir.X)
		local lo, hi = math.huge, -math.huge
		for _, s in { -1, 0, 1 } do
			local q = p + side * s * 7
			local y = Land.surface(q.X, q.Z)
			lo, hi = math.min(lo, y), math.max(hi, y)
		end
		local ground = V3(p.X, hi, p.Z)
		if hi - lo > 0.4 then
			block(
				gates,
				"Badak",
				V3(17, hi - lo + 1, 3),
				face(ground - V3(0, (hi - lo + 1) / 2 - 0.2, 0), ground + dir),
				P.graniteDark,
				Mat.Granite
			)
		end
		local m, board
		if def.kind == "hongsal" then
			m, board = hongsalmun(gates, ground, ground + dir * 10, 12)
		else
			m, board = Build.iljumun(gates, ground, ground + dir * 10, 12)
		end
		m.Name = "송계 문"
		engrave(board, "송계", "Front,Back")
		-- 문 안쪽 석등, 바깥 갈림길 현판
		local lamp = p + dir * 3.5 + side * 9.5
		Build.stoneLantern(m, V3(lamp.X, Land.surface(lamp.X, lamp.Z), lamp.Z))
		local sign = p - dir * 4 - side * 9
		signboard(m, V3(sign.X, Land.surface(sign.X, sign.Z), sign.Z), def.sign, Vector3.zero)
		take(p.X, p.Z, 9)
		take(lamp.X, lamp.Z, 2)
		take(sign.X, sign.Z, 3)
	end
	-- 서쪽 다리머리: 장승 한 쌍과 갈림길 현판
	jangseung(gates, at(-75, -6.5), V3(-200, 0, -6.5), "천하대장군", false)
	jangseung(gates, at(-75, 6.5), V3(-200, 0, 6.5), "지하여장군", true)
	signboard(gates, at(-69, -12), "청송림, 운곡, 관운봉", V3(-200, 0, -12))
	take(-69, -12, 3)
	-- 남쪽 벼랑길 들머리 현판
	signboard(gates, at(-46, 104), "벽담", Vector3.zero)
	take(-46, 104, 3)
end

-- 당산나무: 북쪽 어귀의 큰 느티나무. 돌로 두른 둔덕, 금줄, 돌 제단
local function guardianTree(village: Instance, x: number, z: number, rng)
	local m = model(village, "당산나무")
	local g = Land.surface(x, z)
	for _, a in { 0, 45 } do
		block(
			m,
			"Dundeok",
			V3(11, 1.4, 11),
			CF(x, g + 0.2, z) * CFrame.Angles(0, math.rad(a), 0),
			P.graniteDark,
			Mat.Cobblestone
		)
	end
	local top = V3(x, g + 0.9, z)
	block(
		m,
		"Heuk",
		V3(10, 0.1, 10),
		CF(top + V3(0, 0.02, 0)) * CFrame.Angles(0, math.rad(22.5), 0),
		Color3.fromRGB(96, 110, 66),
		Mat.Grass
	)
	local height = 27
	Build.broadleaf(m, top, rng, { name = "느티나무", height = height, blobs = 12, branches = 4 })
	local rr = height * 0.11 * 0.62 + 0.35
	local h = top.Y + 3.2
	for k = 0, 3 do
		local a0, a1 = math.rad(45 + k * 90), math.rad(135 + k * 90)
		beam(
			m,
			"Geumjul",
			V3(x + math.cos(a0) * rr * 1.42, h, z + math.sin(a0) * rr * 1.42),
			V3(x + math.cos(a1) * rr * 1.42, h, z + math.sin(a1) * rr * 1.42),
			0.22,
			0.22,
			STRAW_DARK,
			Mat.Fabric
		)
	end
	for k = 0, 7 do
		local a = math.rad(k * 45 + 20)
		local q = V3(x + math.cos(a) * (rr * 1.25 + 0.15), h - 0.55, z + math.sin(a) * (rr * 1.25 + 0.15))
		deco(block(m, "Sul", V3(0.3, 0.9, 0.06), face(q, V3(x, q.Y, z)), P.hanji, Mat.SmoothPlastic))
	end
	-- 제단: 길 쪽
	local toRoad = V3(1, 0, 0)
	local altar = top + toRoad * 5.2
	block(m, "Jedan", V3(2.2, 0.5, 4), CF(altar + V3(0, 0.75, 0)), P.granite, Mat.Granite)
	for _, s in { -1, 1 } do
		block(m, "Dari", V3(1.6, 0.6, 0.6), CF(altar + V3(0, 0.2, s * 1.4)), P.graniteDark, Mat.Granite)
	end
	cyl(m, "Hyangno", altar + V3(0, 1.0, 0), altar + V3(0, 1.5, 0), 0.8, BRONZE, Mat.Metal)
	take(x, z, 9)
end

-- 길가 청사초롱: 마을 안 길을 따라 번갈아
local function streetLamps(village: Instance)
	local lamps = folder(village, "청사초롱")
	for _, index in { 1, 4, 5, 9, 12 } do
		local road = Land.ROADS[index]
		local travelled, nextAt, sideSign = 0, 12, 1
		for i = 1, #road - 1 do
			local a, b = V3(road[i][1], 0, road[i][2]), V3(road[i + 1][1], 0, road[i + 1][2])
			local len = (b - a).Magnitude
			local dir = (b - a) / len
			while nextAt <= travelled + len do
				local p = a + dir * (nextAt - travelled)
				local r = p.Magnitude
				local q = p + V3(-dir.Z, 0, dir.X) * 6.2 * sideSign
				if r > 36 and r < GATE_R - 6 and clearOf(q.X, q.Z, 1.2, 1.6) then
					Build.chorong(lamps, V3(q.X, Land.surface(q.X, q.Z), q.Z), V3(p.X, 0, p.Z))
					take(q.X, q.Z, 1.5)
					sideSign = -sideSign
				end
				nextAt += 21
			end
			travelled += len
		end
	end
end

-- 마을 살림: 우물, 수레, 깃발, 나무
local function buildYards(village: Instance, rng)
	local yards = folder(village, "살림")
	for _, spot in { { -38, 40 }, { 86, 50 } } do
		if clearOf(spot[1], spot[2], 3.5, 2) then
			Build.well(yards, at(spot[1], spot[2]))
			take(spot[1], spot[2], 3.5)
		end
	end
	for _, spot in { { 62, -38, 0.6 }, { 108, -26, 2.4 }, { -32, 106, 1.2 } } do
		if clearOf(spot[1], spot[2], 4, 2) then
			local g = at(spot[1], spot[2])
			Build.cart(yards, CF(g) * CFrame.Angles(0, spot[3], 0))
			take(spot[1], spot[2], 4)
		end
	end
	-- 만물상 곁 깃발 둘
	for _, spot in { { 38, -36 }, { 58, -14 } } do
		if clearOf(spot[1], spot[2], 1, 1.5) then
			Build.banner(yards, at(spot[1], spot[2]), V3(0, 0, 0), P.juhong:Lerp(P.plaster, 0.25), 10)
			take(spot[1], spot[2], 1.5)
		end
	end
	-- 마을 나무: 길가와 집 사이 빈 곳에
	local planted = 0
	for _ = 1, 260 do
		if planted >= 12 then
			break
		end
		local a = rng(0, math.pi * 2)
		local r = rng(40, 112)
		local x, z = math.cos(a) * r, math.sin(a) * r
		if x > -84 and clearOf(x, z, 3.2, 3) then
			local base = at(x, z)
			local kind = rng(0, 1)
			if kind < 0.35 then
				persimmon(yards, base, rng)
			elseif kind < 0.6 then
				Build.blossom(yards, base, rng, { blobs = 7 })
			elseif kind < 0.85 then
				Build.pine(yards, base, rng, { height = rng(12, 16), tiers = 4 })
			else
				Build.broadleaf(yards, base, rng, { height = rng(11, 14), blobs = 7 })
			end
			take(x, z, 6)
			planted += 1
		end
	end
	-- 덤불과 꽃: 담 밑, 길가
	local bushes = 0
	for _ = 1, 300 do
		if bushes >= 16 then
			break
		end
		local a = rng(0, math.pi * 2)
		local r = rng(36, 118)
		local x, z = math.cos(a) * r, math.sin(a) * r
		if x > -84 and clearOf(x, z, 1.4, 2.5) then
			local flowers = if rng(0, 1) > 0.7
				then (if rng(0, 1) > 0.5 then P.blossomDeep else Color3.fromRGB(240, 210, 90))
				else nil
			Build.shrub(yards, at(x, z), rng, { size = rng(2.2, 3.6), flowers = flowers })
			take(x, z, 2)
			bushes += 1
		end
	end
end

-- 들판: 마을 동쪽 다랑이 논, 북쪽 어귀 밖 밭
local function buildFields(village: Instance, rng)
	local fields = folder(village, "들판")
	for i = 0, 2 do
		for j = 0, 3 do
			local x, z = 140 + i * 25 + rng(-1.5, 1.5), 18 + j * 19 + rng(-1, 1)
			if clearOf(x, z, 5.5, 8) and roadDist(x, z) > 18 then
				paddy(fields, x, z, 22, 15, rng(-0.04, 0.04))
			end
		end
	end
	for _, spot in { { -42, -146 }, { -64, -150 }, { -46, -168 }, { -68, -172 }, { 36, -150 } } do
		if clearOf(spot[1], spot[2], 5, 6) then
			field(fields, spot[1], spot[2], 18, 12, rng(-0.1, 0.1))
		end
	end
	-- 논두렁 볏가리와 허수아비
	for _, spot in { { 128, 20 }, { 128, 48 }, { 241, 30 }, { 241, 70 }, { 128, 92 } } do
		if clearOf(spot[1], spot[2], 2, 3) then
			haystack(fields, at(spot[1], spot[2]), rng(2.6, 3.4))
			take(spot[1], spot[2], 2.5)
		end
	end
	for _, spot in { { 165, 46 }, { 215, 84 } } do
		scarecrow(fields, at(spot[1], spot[2], 0.3), rng(0, 6))
	end
end

local function buildVillage(root: Instance, rng)
	local village = folder(root, "송계 마을")
	buildPlaza(village)
	buildFurnace(village)
	buildSmithy(village)
	buildStall(village)
	buildElders(village)

	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "SpawnLocation"
	spawn.Anchored = true
	spawn.Neutral = true
	spawn.Duration = 0
	spawn.Size = V3(10, 1, 10)
	spawn.CFrame = CF(0, 0.6, 24)
	spawn.Color = P.granite
	spawn.Material = Mat.Granite
	spawn.TopSurface = Enum.SurfaceType.Smooth
	spawn.Parent = village

	buildGates(village)
	guardianTree(village, -28, -110, rng)
	buildHouses(village, rng)
	streetLamps(village)
	buildFields(village, rng)
	buildYards(village, rng)
end

-- 벽계: 다리, 징검돌, 폭포와 벽담 ---------------------------------------------------------

-- 벽계 다리: 귀틀석 위 널마루, 물속 교각 둘, 돌난간
local function buildBridge(river: Instance)
	local def = Sites.BRIDGES[1]
	local a, b = V3(def[1], def[5], def[2]), V3(def[3], def[5], def[4])
	local len = (b - a).Magnitude
	local mid = (a + b) / 2
	local look = face(mid, b) -- 앞(-Z)이 b 쪽, 다리 길이 방향이 Z
	local m = model(river, "벽계 다리")
	local deck = block(m, "Deck", V3(8.4, 1, len + 2), look * CF(0, -0.5, 0), P.wood, Mat.WoodPlanks)
	deck:AddTag("Ground")
	for _, s in { -1, 1 } do
		block(m, "Gwiteul", V3(1.1, 1.5, len + 2.4), look * CF(s * 4.6, -0.55, 0), P.granite, Mat.Granite)
		-- 돌난간: 기둥 다섯과 난간대 둘
		local posts = {}
		for i = 0, 4 do
			local z = -len / 2 + i * len / 4
			local post = look * CF(s * 4.6, 1.15, z)
			block(m, "Nangan", V3(0.8, 2.3, 0.8), post, P.granite, Mat.Granite)
			ball(m, "Boju", (post * CF(0, 1.35, 0)).Position, 0.75, P.granite, Mat.Granite)
			table.insert(posts, post)
		end
		beam(
			m,
			"Nangandae",
			(posts[1] * CF(0, 0.75, 0)).Position,
			(posts[5] * CF(0, 0.75, 0)).Position,
			0.45,
			0.45,
			P.granite,
			Mat.Granite
		)
		beam(
			m,
			"Nangandae",
			(posts[1] * CF(0, -0.35, 0)).Position,
			(posts[5] * CF(0, -0.35, 0)).Position,
			0.35,
			0.35,
			P.graniteDark,
			Mat.Granite
		)
	end
	for _, z in { -len / 6, len / 6 } do
		block(m, "Gyogak", V3(7.6, 6.6, 2.2), look * CF(0, -4.3, z), P.graniteDark, Mat.Granite)
	end
	for _, e in { -1, 1 } do
		block(m, "Meori", V3(11, 2.4, 3.2), look * CF(0, -1.25, e * (len / 2 + 0.4)), P.granite, Mat.Granite)
		-- 다리 끝 비탈 (땅 높이 0 에서 널마루 0.9 로)
		Build.wedge(
			m,
			"Gyeongsa",
			V3(8.4, def[5], 2.6),
			look * CF(0, def[5] / 2 - 0.02, e * (len / 2 + 2.3)) * CFrame.Angles(0, if e > 0 then math.pi else 0, 0),
			P.wood,
			Mat.WoodPlanks
		)
	end
	take(mid.X, mid.Z, len / 2 + 3)
	-- 숲 쪽 다리머리 석등 (마을 쪽은 장승)
	local q = look * CF(6.8, 0, len / 2 + 3)
	Build.stoneLantern(m, at(q.X, q.Z))
	take(q.X, q.Z, 2)
end

-- 징검돌: 명경호 길이 벽계를 건너는 곳 (WorldSites.BRIDGES[2])
local function buildFord(river: Instance, rng)
	local def = Sites.BRIDGES[2]
	local a, b = V3(def[1], 0, def[2]), V3(def[3], 0, def[4])
	local m = model(river, "징검돌")
	local n = math.floor((b - a).Magnitude / 3.4)
	for i = 0, n do
		local p = a:Lerp(b, i / n)
		local g = Land.height(p.X, p.Z)
		if g < def[5] - 0.2 then
			local s = rng(2.4, 3.2)
			local h = def[5] - g + 0.8
			block(
				m,
				"Dol",
				V3(s, h, s * rng(0.8, 1)),
				CF(p.X, def[5] - h / 2, p.Z) * CFrame.Angles(0, rng(0, 3), 0),
				P.granite:Lerp(P.graniteDark, rng(0, 0.6)),
				Mat.Granite
			)
		end
	end
end

-- 벽담 벼랑길 밧줄 난간: 길 바깥(협곡 쪽) 가장자리를 따라
local function benchRail(river: Instance)
	local m = model(river, "벼랑길 난간")
	local pts = Land.BENCHES.pool.pts
	local posts = {}
	for i = 1, #pts - 1 do
		local a, b = V3(pts[i][1], 0, pts[i][2]), V3(pts[i + 1][1], 0, pts[i + 1][2])
		local dir = (b - a).Unit
		local out = V3(dir.Z, 0, -dir.X) -- 길의 서쪽(협곡 쪽)
		if out.X > 0 then
			out = -out
		end
		local steps = math.max(1, math.floor((b - a).Magnitude / 6))
		for k = (if i == 1 then 0 else 1), steps do
			local p = a:Lerp(b, k / steps) + out * 4.2
			table.insert(posts, V3(p.X, Land.height(p.X, p.Z), p.Z))
		end
	end
	for i, p in posts do
		beam(m, "Malttuk", p - V3(0, 0.8, 0), p + V3(0, 3.2, 0), 0.4, 0.4, P.woodDark, Mat.Wood)
		if i > 1 then
			beam(m, "Batjul", posts[i - 1] + V3(0, 2.9, 0), p + V3(0, 2.9, 0), 0.16, 0.16, STRAW_DARK, Mat.Fabric)
		end
	end
end

local function buildRiver(root: Instance, rng)
	local river = folder(root, "벽계")
	buildBridge(river)
	buildFord(river, rng)

	-- 벽계 폭포: 강(수면 -1)이 벽계협의 벽담(수면 -20)으로 떨어진다. 물이 넘는 턱 양옆에 바위
	Build.waterfall(river, V3(-95, -0.9, 128.2), V3(0, 0, 1), 16, 19)
	for _, spot in { { -106.5, 126, 6.5 }, { -83.5, 125, 5.5 }, { -110, 133, 4.5 }, { -80, 131, 4 } } do
		Build.rocks(river, V3(spot[1], Land.height(spot[1], spot[2]), spot[2]), spot[3], rng, { count = 2 })
	end
	-- 벽담 서쪽 벼랑: 바위 판을 겹쳐 세운다 (복셀 계단 대신)
	local function rimTop(x: number, z: number): number
		return Land.height(x - 7, z) - 0.5
	end
	local function poolFloor(_x: number, _z: number): number
		return -20.5
	end
	Build.cliffFace(river, V3(-121, 0, 136), V3(-125, 0, 214), V3(1, 0, 0), rimTop, poolFloor, rng, { spacing = 4.6 })
	local function rimTopE(x: number, z: number): number
		return Land.height(x + 7, z) - 0.5
	end
	Build.cliffFace(river, V3(-66, 0, 192), V3(-58, 0, 236), V3(-1, 0, 0), rimTopE, poolFloor, rng, { spacing = 4.6 })
	benchRail(river)

	-- 너럭바위 ('아래' 자리): 벽담가 넓은 바위
	local down = SITE.down
	local slab = block(
		river,
		"너럭바위",
		V3(15, 3, 11),
		CF(down.x, -20.5, down.z) * CFrame.Angles(0, 0.12, 0),
		C.stone,
		Mat.Slate
	)
	slab:AddTag("Ground")
	for _, spot in { { 9, 4, 3.5 }, { -7, -6, 2.6 }, { 4, -7, 2.2 } } do
		Build.rocks(river, V3(down.x + spot[1], -19.4, down.z + spot[2]), spot[3], rng, { count = 1 })
	end
	local downModel = model(river, down.name)
	siteMarker(downModel, "down", V3(down.x, -18.4, down.z), down.radius)

	-- 관폭정: 벽담 동쪽 벼랑 위 정자 (폭포와 못을 본다)
	local px, pz = -44, 166
	local y = bed(river, px, pz, 14, 14, 0)
	Build.pavilion(river, face(V3(px, y, pz), V3(-95, y, 170)), { name = "관폭정", bay = 8.5, detail = 1 })
	take(px, pz, 10)

	-- 물가 버드나무와 갈대 (마을 쪽 둑과 숲 쪽 둑)
	for _, spot in { { -79, -112 }, { -80, -44 }, { -78, 56 }, { -113, -70 }, { -112, -170 } } do
		if clearOf(spot[1], spot[2], 3, 2) then
			Build.willow(river, at(spot[1], spot[2]), rng, { strands = 14, blobs = 5 })
			take(spot[1], spot[2], 6)
		end
	end
	for _, spot in
		{
			{ -85.5, -90 },
			{ -85.5, -24 },
			{ -104.5, -40 },
			{ -104.5, 40 },
			{ -85.5, 112 },
		}
	do
		Build.reeds(
			river,
			V3(spot[1], math.max(Land.height(spot[1], spot[2]), -1.2), spot[2]),
			rng,
			{ count = 6, radius = 1.8 }
		)
	end
end

-- 청송림 ----------------------------------------------------------------------------------
--
-- 다리 건너 서쪽 솔숲 (영초가 돋는다). 적송 사이에 참나무·은행·벚나무가 섞이고, 길가는 빽빽하게,
-- 안쪽은 무리 지어 자란다. 남쪽 골짜기에 영천굴(중품 영맥), 숲 들머리에 약초막.

local GROVE = { x0 = -465, x1 = -118, z0 = -335, z1 = 325 }

local function inGrove(x: number, z: number): boolean
	if x < GROVE.x0 or x > GROVE.x1 or z < GROVE.z0 or z > GROVE.z1 then
		return false
	end
	local vw = Land.VILLAGE_W -- 운곡 마을 (다른 땅)
	if (x - vw.x) ^ 2 + (z - vw.z) ^ 2 < 120 ^ 2 then
		return false
	end
	local k = Land.KNOLL -- 백금굴 바위 언덕
	if (x - k.x) ^ 2 + (z - k.z) ^ 2 < 75 ^ 2 then
		return false
	end
	return true
end

local function jitterColor(color: Color3, rng, amount: number): Color3
	local k = 1 + rng(-amount, amount)
	return Color3.new(math.clamp(color.R * k, 0, 1), math.clamp(color.G * k, 0, 1), math.clamp(color.B * k, 0, 1))
end

-- 영천굴: 서쪽 반원으로 큰 바위를 두르고 덮개바위를 얹은 굴 어귀. 덮개 끝에서 실폭포가 못(영맥)으로 떨어진다
local function buildCave(grove: Instance, rng)
	local v = SITE["mid@grove"]
	local c = V3(v.x, Land.surface(v.x, v.z), v.z)
	local m = model(grove, "영천굴")
	local rock = Color3.fromRGB(104, 106, 100)
	for k = 0, 8 do
		local a = math.rad(100 + k * 20)
		local r = v.radius + 5 + rng(-0.4, 1)
		local p = c + V3(math.cos(a) * r, 0, math.sin(a) * r)
		local g = Land.surface(p.X, p.Z)
		local h = 8 + 7 * -math.cos(a) + rng(-1, 1)
		local cf = face(V3(p.X, g + h / 2 - 1.4, p.Z), V3(c.X, g + h / 2, c.Z))
			* CFrame.Angles(math.rad(rng(-8, 2)), 0, math.rad(rng(-6, 6)))
		block(m, "Bawi", V3(rng(6.5, 8.5), h, rng(5, 7)), cf, jitterColor(rock, rng, 0.07), Mat.Slate)
	end
	for k = 0, 4 do
		local a = math.rad(130 + k * 25)
		local r = v.radius + 11 + rng(0, 1.5)
		local p = c + V3(math.cos(a) * r, 0, math.sin(a) * r)
		local g = Land.surface(p.X, p.Z)
		local h = rng(15, 19)
		local cf = face(V3(p.X, g + h / 2 - 1.6, p.Z), V3(c.X, g + h / 2, c.Z))
			* CFrame.Angles(math.rad(rng(-10, -2)), rng(-0.3, 0.3), 0)
		block(
			m,
			"Bawi",
			V3(rng(9, 12), h, rng(7, 9)),
			cf,
			jitterColor(rock:Lerp(P.graniteDark, 0.25), rng, 0.06),
			Mat.Rock
		)
	end
	local lintel = block(
		m,
		"Deopgae",
		V3(17, 3.2, 26),
		CF(c + V3(-10, 14.2, 0)) * CFrame.Angles(0, 0, math.rad(-7)),
		rock:Lerp(P.graniteDark, 0.3),
		Mat.Slate
	)
	deco(
		block(
			m,
			"Ikki",
			V3(14.5, 0.5, 21),
			lintel.CFrame * CF(-0.5, 1.7, 0),
			Color3.fromRGB(84, 112, 62),
			Mat.LeafyGrass
		)
	)
	for _, s in { -1, 1 } do
		deco(
			block(
				m,
				"Ikki",
				V3(6, 0.5, 5),
				lintel.CFrame * CF(-3, 1.8, s * 12) * CFrame.Angles(0, 0.4 * s, 0.2),
				Color3.fromRGB(78, 108, 58),
				Mat.LeafyGrass
			)
		)
	end
	Build.waterfall(m, c + V3(-2.2, 12.3, 0), V3(1, 0, 0), 3, 11.6)
	-- 어귀 석등 둘, 비석, 둘레 고사리
	for _, s in { -1, 1 } do
		local q = c + V3(v.radius + 5.5, 0, s * 7)
		Build.stoneLantern(m, at(q.X, q.Z))
	end
	local st = c + V3(v.radius + 8, 0, 13)
	stele(m, at(st.X, st.Z), "영천굴", V3(c.X + 60, 0, c.Z))
	for k = 0, 7 do
		local a = math.rad(110 + k * 20)
		local r = v.radius + 13 + rng(0, 4)
		local q = c + V3(math.cos(a) * r, 0, math.sin(a) * r)
		Build.shrub(m, at(q.X, q.Z), rng, { size = rng(2.4, 3.6), leaves = { P.leafDeep, P.pine, P.leaf } })
	end
	take(c.X - 6, c.Z, 24)
	take(c.X + v.radius + 6, c.Z, 9)
	-- 숲길에서 굴로 내려오는 오솔길
	local road = Land.ROADS[11]
	local from =
		V3(-372, 0, road[1][2] + (road[2][2] - road[1][2]) * ((-372 - road[1][1]) / (road[2][1] - road[1][1])) + 5)
	local to = V3(c.X + v.radius + 9, 0, c.Z + 1)
	local pts = {}
	for i = 0, 8 do
		local t = i / 8
		local q = from:Lerp(to, t) + V3(math.sin(t * math.pi * 2) * 9, 0, 0)
		table.insert(pts, V3(q.X, Land.surface(q.X, q.Z) + 0.05, q.Z))
	end
	local path = model(grove, "영천굴 오솔길")
	for i = 1, #pts - 1 do
		trail(path, pts[i], pts[i + 1], 3.4, Color3.fromRGB(118, 96, 72))
		local mid = (pts[i] + pts[i + 1]) / 2
		take(mid.X, mid.Z, 4)
	end
end

-- 약초막: 숲 들머리 초가와 약초 말리는 덕, 바구니
local function buildHerbHut(grove: Instance, rng)
	local x, z = -206, -80
	local m, cf = choga(grove, x, z, x, z + 40, 9.5, 7.5)
	m.Name = "약초막"
	local function p(lx: number, lz: number): Vector3
		local q = cf:PointToWorldSpace(V3(lx, 0, lz))
		return V3(q.X, Land.surface(q.X, q.Z), q.Z)
	end
	-- 덕: 기둥 넷에 발을 얹고 약초 다발을 늘어놓는다
	local corners = { p(-9, -6), p(-3, -6), p(-9, -10), p(-3, -10) }
	local topY = math.max(corners[1].Y, corners[2].Y, corners[3].Y, corners[4].Y) + 3
	for _, q in corners do
		beam(m, "Deokgidung", q - V3(0, 0.5, 0), V3(q.X, topY, q.Z), 0.35, 0.35, P.woodDark, Mat.Wood)
	end
	local center = (corners[1] + corners[4]) / 2
	local rack = CF(center.X, topY + 0.1, center.Z) * (cf - cf.Position)
	block(m, "Bal", V3(6.4, 0.2, 4.4), rack, STRAW, Mat.Fabric)
	for i = 0, 4 do
		block(
			m,
			"Yakcho",
			V3(0.6, 0.35, 3.4),
			rack * CF(-2.4 + i * 1.2, 0.25, 0),
			if i % 2 == 0 then P.leafLight else P.leaf,
			Mat.Grass
		)
	end
	for i, q in { p(5.2, -6.5), p(6.4, -4.8), p(-1.5, -7.5) } do
		local basket = block(
			m,
			"Baguni",
			V3(1.0, 1.4 + i * 0.1, 1.4 + i * 0.1),
			CF(q + V3(0, 0.5, 0)) * CFrame.Angles(0, 0, math.rad(90)),
			Color3.fromRGB(176, 140, 86),
			Mat.Fabric
		)
		basket.Shape = Enum.PartType.Cylinder
		deco(block(m, "Yakcho", V3(1.0, 0.35, 1.0), CF(q + V3(0, 1.05, 0)), P.leafLight, Mat.Grass))
	end
	local pot = p(4.5, -10)
	for k = 0, 2 do
		local a = math.rad(k * 120)
		block(
			m,
			"Dol",
			V3(0.9, 0.8, 0.9),
			CF(pot + V3(math.cos(a) * 1.1, 0.3, math.sin(a) * 1.1)),
			P.graniteDark,
			Mat.Slate
		)
	end
	cyl(m, "Sot", pot + V3(0, 0.6, 0), pot + V3(0, 1.9, 0), 1.8, P.meok, Mat.Metal)
	take(x, z - 6, 9)
end

-- 나무, 덤불, 바위
local function plantGrove(grove: Instance, rng)
	local trees = folder(grove, "나무")
	local floor = folder(grove, "숲바닥")
	local planted, cap = 0, 125
	local step = 14
	for gx = GROVE.x0, GROVE.x1, step do
		for gz = GROVE.z0, GROVE.z1, step do
			if planted >= cap then
				break
			end
			local x, z = gx + rng(0, step), gz + rng(0, step)
			if inGrove(x, z) then
				local h = Land.height(x, z)
				local roadD = roadDist(x, z)
				local clump = math.noise(x / 70, z / 70, 0.731)
				local edge = math.min(x - GROVE.x0, GROVE.x1 - x, z - GROVE.z0, GROVE.z1 - z)
				local density = if roadD < 36 then 0.34 elseif clump > 0.08 then 0.26 else 0.05
				if edge < 30 then
					density *= 0.6
				end
				if rng(0, 1) < density and h > 1.5 and Land.water(x, z, h) == nil then
					local slope = math.abs(Land.height(x + 3, z) - h) + math.abs(Land.height(x, z + 3) - h)
					if slope < 4.5 and clearOf(x, z, 2.4, 3.6) then
						local base = V3(x, h, z)
						local near = roadD < 36
						local kind = rng(0, 1)
						if kind < 0.56 then
							Build.pine(trees, base, rng, { height = rng(13, 19), tiers = if near then 4 else 3 })
						elseif kind < 0.8 then
							Build.broadleaf(trees, base, rng, {
								height = rng(10, 15),
								blobs = if near then 6 else 3,
								branches = if near then 2 else 1,
							})
						elseif kind < 0.88 and near then
							Build.blossom(trees, base, rng, { blobs = 7 })
						elseif kind < 0.94 then
							-- 은행: 노란 잎
							Build.broadleaf(trees, base, rng, {
								name = "은행나무",
								height = rng(12, 15),
								blobs = 5,
								branches = 2,
								leaves = {
									P.leafYellow,
									Color3.fromRGB(196, 186, 84),
									Color3.fromRGB(224, 204, 96),
								},
							})
						else
							Build.pine(trees, base, rng, { height = rng(16, 21), tiers = 4 })
						end
						take(x, z, 4.6)
						planted += 1
						-- 나무 밑 덤불·고사리
						if rng(0, 1) < 0.32 then
							local a = rng(0, math.pi * 2)
							local q = V3(x + math.cos(a) * 4, 0, z + math.sin(a) * 4)
							if clearOf(q.X, q.Z, 1.2, 3) then
								local fern = rng(0, 1) < 0.5
								Build.shrub(floor, at(q.X, q.Z), rng, {
									size = if fern then rng(1.8, 2.6) else rng(2.4, 3.8),
									blobs = if fern then 2 else 3,
									leaves = if fern then { P.pine, P.leafDeep } else nil,
									flowers = if not fern and rng(0, 1) < 0.25
										then Color3.fromRGB(236, 226, 240)
										else nil,
								})
							end
						end
					end
				end
			end
		end
	end
	-- 이끼 낀 바위와 쓰러진 통나무
	local rocks = 0
	for _ = 1, 400 do
		if rocks >= 22 then
			break
		end
		local x, z = rng(GROVE.x0, GROVE.x1), rng(GROVE.z0, GROVE.z1)
		if inGrove(x, z) and clearOf(x, z, 3, 4) then
			local h = Land.height(x, z)
			if h > 1 and Land.water(x, z, h) == nil then
				Build.rocks(floor, V3(x, h, z), rng(2.5, 6), rng, { count = 2 })
				take(x, z, 4)
				rocks += 1
			end
		end
	end
	local logs = 0
	for _ = 1, 200 do
		if logs >= 6 then
			break
		end
		local x, z = rng(GROVE.x0, GROVE.x1), rng(GROVE.z0, GROVE.z1)
		if inGrove(x, z) and clearOf(x, z, 4, 5) then
			local a = rng(0, math.pi)
			local d = V3(math.cos(a), 0, math.sin(a)) * rng(3.5, 5)
			local p0, p1 = V3(x, 0, z) - d, V3(x, 0, z) + d
			local y0, y1 = Land.height(p0.X, p0.Z), Land.height(p1.X, p1.Z)
			if math.abs(y0 - y1) < 2 then
				local log = cyl(
					floor,
					"Tongnamu",
					V3(p0.X, y0 + 0.5, p0.Z),
					V3(p1.X, y1 + 0.5, p1.Z),
					rng(1.1, 1.5),
					P.bark,
					Mat.Wood
				)
				deco(
					block(
						floor,
						"Ikki",
						V3(log.Size.X * 0.6, 0.2, 0.9),
						log.CFrame * CF(0, 0, 0) * CFrame.new(0, log.Size.Y * 0.48, 0),
						Color3.fromRGB(84, 112, 62),
						Mat.LeafyGrass
					)
				)
				take(x, z, 5)
				logs += 1
			end
		end
	end
end

local function buildGrove(root: Instance, rng)
	local grove = folder(root, "청송림")
	stele(grove, at(-121, 18), "청송림", V3(0, 0, 18))
	take(-121, 18, 3)
	buildCave(grove, rng)
	buildHerbHut(grove, rng)
	plantGrove(grove, rng)
end

-- 땅마다 쓰는 자리 ------------------------------------------------------------------------
--
-- 자리 둘레(전송진 9, 과업 자리·영맥 7)는 땅마다의 모듈이 비워 둔다. 여기 것은 그 안에 든다.

-- 송계 쪽 수평 방향 (비석·표석이 그쪽을 본다)
local function homeward(x: number, z: number): Vector3
	local v = V3(-x, 0, -z)
	return if v.Magnitude > 1 then v.Unit else V3(0, 0, 1)
end

-- 오행처 받침: 팔각 두 단, 가운데 속성 빛 돌, 청동 받침 위 빛 구슬, 송계 쪽 비석
local function buildElementDais(parent: Instance, s)
	local color = Sites.ELEMENT_COLORS[s.id]
	local label = string.match(s.name, "^(.-):") or s.name
	local m = model(parent, s.name)
	local yaw = yawTo(s.x, s.z, 0, 0)
	local rockBed = s.id == "el_water" -- 물가 바위
	local y = bed(
		m,
		s.x,
		s.z,
		12.4,
		12.4,
		yaw,
		if rockBed then Color3.fromRGB(100, 104, 108) else P.graniteDark,
		if rockBed then Mat.Slate else Mat.Cobblestone
	)
	local base = V3(s.x, y, s.z)
	for _, a in { 22.5, 67.5 } do
		local rot = CFrame.Angles(0, yaw + math.rad(a), 0)
		block(m, "Dan", V3(11, 1.0, 11), CF(base + V3(0, 0.2, 0)) * rot, P.granite, Mat.Granite)
		block(m, "Dan2", V3(7.6, 0.6, 7.6), CF(base + V3(0, 1.0, 0)) * rot, P.granite:Lerp(color, 0.12), Mat.Granite)
	end
	disc(m, "Inlay", base + V3(0, 1.32, 0), 2.6, 0.06, color:Lerp(P.granite, 0.3), Mat.SmoothPlastic)
	cyl(m, "Batchimdae", base + V3(0, 1.3, 0), base + V3(0, 3.0, 0), 0.7, BRONZE, Mat.Metal)
	cyl(m, "Batchim", base + V3(0, 3.0, 0), base + V3(0, 3.35, 0), 1.7, BRONZE, Mat.Metal)
	local orb = ball(m, "Orb", base + V3(0, 4.45, 0), 2, color, Mat.Neon)
	orb.CanCollide = false
	light(orb, color, 14, 1.5)
	motes(orb, color, 6)
	siteMarker(m, s.id, base + V3(0, 1.9, 0), 7)
	local q = base + homeward(s.x, s.z) * 9.5
	stele(m, V3(q.X, Land.surface(q.X, q.Z), q.Z), label, Vector3.zero, color:Lerp(C.stone, 0.7))
end

-- 사방 성대: 두 단 장대석 단, 네 귀 돌기둥, 가운데 돌기둥 위 별 구슬, 송계 쪽 계단과 비석·새긴 돌
local function buildStarAltar(parent: Instance, def)
	local s = SITE[def.id]
	local m = model(parent, def.name)
	local yaw = yawTo(s.x, s.z, 0, 0)
	local y = bed(m, s.x, s.z, 18, 18, yaw, P.graniteDark, Mat.Slate)
	local cf = CF(s.x, y, s.z) * CFrame.Angles(0, yaw, 0) -- 앞(-Z)이 송계 쪽
	local stone = P.granite:Lerp(def.color, 0.06)
	block(m, "Dan", V3(18, 1.4, 18), cf * CF(0, 0.1, 0), stone, Mat.Granite)
	block(m, "Dan2", V3(12, 1.0, 12), cf * CF(0, 1.3, 0), stone, Mat.Granite)
	block(m, "Gyedan", V3(4.4, 0.45, 1.2), cf * CF(0, 1.025, -6.6), P.granite, Mat.Granite)
	block(m, "Gyedan", V3(5, 0.45, 1.4), cf * CF(0, 0.22, -9.7), P.granite, Mat.Granite)
	for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
		local p = cf * CF(c[1] * 7.6, 0, c[2] * 7.6)
		block(m, "Gidung", V3(1.3, 6.4, 1.3), p * CF(0, 0.8 + 3.2, 0), stone, Mat.Granite)
		block(m, "Gat", V3(2.0, 0.5, 2.0), p * CF(0, 0.8 + 6.65, 0), P.graniteDark, Mat.Granite)
		ball(m, "Boju", (p * CF(0, 0.8 + 7.25, 0)).Position, 0.8, def.color:Lerp(P.granite, 0.4), Mat.Granite)
	end
	cyl(m, "Byeolgidung", (cf * CF(0, 1.8, 0)).Position, (cf * CF(0, 5.6, 0)).Position, 1.3, stone, Mat.Granite)
	cyl(m, "Batchim", (cf * CF(0, 5.6, 0)).Position, (cf * CF(0, 6.0, 0)).Position, 2.4, BRONZE, Mat.Metal)
	for k = 0, 3 do
		local a = math.rad(45 + k * 90)
		local tip = cf * CF(math.cos(a) * 1.4, 7.6, math.sin(a) * 1.4)
		beam(
			m,
			"Gal",
			(cf * CF(math.cos(a) * 0.9, 5.9, math.sin(a) * 0.9)).Position,
			tip.Position,
			0.22,
			0.22,
			BRONZE,
			Mat.Metal
		)
	end
	local orb = ball(m, "Star", (cf * CF(0, 8.0, 0)).Position, 2.6, def.color, Mat.Neon)
	orb.CanCollide = false
	light(orb, def.color, 24, 2)
	motes(orb, def.color, 4)
	siteMarker(m, def.id, (cf * CF(0, 2.4, 0)).Position, 8)
	-- 비석(이름)과 새긴 돌(방위 신수)
	local q = (cf * CF(6.5, 0, -13)).Position
	stele(m, V3(q.X, Land.surface(q.X, q.Z), q.Z), def.name, Vector3.zero, def.color:Lerp(C.stone, 0.6))
	local t = (cf * CF(-6.5, 0, -12.5)).Position
	local tg = Land.surface(t.X, t.Z)
	local look = face(V3(t.X, tg, t.Z), V3(0, tg, 0))
	block(m, "Badim", V3(4.8, 1.0, 1.8), look * CF(0, 0.2, 0), P.graniteDark, Mat.Granite)
	local tablet = block(m, "Saegin", V3(4.2, 2.2, 0.7), look * CF(0, 1.8, 0), def.color:Lerp(C.stone, 0.75), Mat.Slate)
	engrave(tablet, def.carve, "Front", false, "ink")
end

-- 관성대 칠성단: 둥근 돌바닥, 세 단 칠성단과 제상, 북두칠성 등 일곱, 팔괘 기둥 여덟, 오르막 끝 비석
local function buildMesaAltar(parent: Instance)
	local mesa = Land.MESA
	local m = model(parent, "관성대")
	local g = Land.surface(mesa.x, mesa.z)
	local center = V3(mesa.x, g, mesa.z)
	local sand = Color3.fromRGB(186, 152, 114)
	disc(m, "Badak", center + V3(0, 0.15, 0), 37, 0.5, sand, Mat.Sandstone)
	disc(m, "Tti", center + V3(0, 0.2, 0), 34.5, 0.5, sand:Lerp(P.graniteDark, 0.35), Mat.Sandstone)
	disc(m, "An", center + V3(0, 0.25, 0), 27.5, 0.5, sand:Lerp(P.plaster, 0.15), Mat.Sandstone)
	local floor = g + 0.5
	local dan = model(m, "칠성단")
	disc(dan, "Dan1", V3(center.X, floor + 0.5, center.Z), 10, 1.0, P.granite, Mat.Granite)
	disc(dan, "Dan2", V3(center.X, floor + 1.5, center.Z), 7.4, 1.0, P.granite, Mat.Granite)
	disc(dan, "Dan3", V3(center.X, floor + 2.3, center.Z), 4.8, 0.6, P.graniteDark, Mat.Granite)
	local top = floor + 2.6
	-- 제상과 향로, 정화수 그릇
	block(dan, "Jesang", V3(3.6, 1.1, 2.0), CF(center + V3(0, top - g + 0.55, 0)), P.woodDark, Mat.Wood)
	cyl(
		dan,
		"Hyangno",
		V3(center.X - 0.9, top + 1.1, center.Z),
		V3(center.X - 0.9, top + 1.6, center.Z),
		0.8,
		BRONZE,
		Mat.Metal
	)
	cyl(
		dan,
		"Geureut",
		V3(center.X + 0.9, top + 1.1, center.Z),
		V3(center.X + 0.9, top + 1.35, center.Z),
		0.9,
		P.hanji,
		Mat.SmoothPlastic
	)
	siteMarker(dan, "altar", V3(center.X, floor + 2.7, center.Z), 10, "칠성단")
	-- 북두칠성: 칠성단 북쪽 바닥에 국자 모양으로 (돌 받침 위 별빛)
	local DIPPER = { { 0, 0 }, { 0, 1.0 }, { 1.3, 1.25 }, { 1.55, 0.3 }, { 2.6, 0.15 }, { 3.6, 0.3 }, { 4.7, -0.3 } }
	for i, d in DIPPER do
		local p = V3(center.X - 8 + d[1] * 3.4, floor, center.Z - 15 - d[2] * 3.4)
		block(dan, "Byeolbatchim", V3(1.0, 1.2, 1.0), CF(p + V3(0, 0.6, 0)), P.granite, Mat.Granite)
		local star = ball(dan, "Byeol", p + V3(0, 1.65, 0), 0.9, Color3.fromRGB(170, 205, 255), Mat.Neon)
		star.CanCollide = false
		if i == 1 or i == 7 then
			light(star, Color3.fromRGB(170, 205, 255), 10, 1)
		end
	end
	-- 팔괘 기둥: 이름은 네 면에 세로로, 괘(효 셋)는 기둥머리 위 검은 돌판에 (가운데를 본다)
	for i, trigram in World.TRIGRAMS do
		local s = SITE["tri_" .. i]
		local pos = V3(s.x, floor, s.z)
		local pm = model(m, trigram.name .. " 기둥")
		local height = 9.5 + (i * 37 % 5) * 0.5
		local look = face(pos, V3(center.X, floor, center.Z))
		block(pm, "Chumdol", V3(3.8, 1.0, 3.8), look * CF(0, 0.3, 0), P.granite, Mat.Granite)
		local pillar = block(
			pm,
			"Pillar",
			V3(2.4, height, 2.4),
			look * CF(0, 0.8 + height / 2, 0),
			C.sandstone:Lerp(sand, 0.4),
			Mat.Sandstone
		)
		engrave(pillar, trigram.name, "Front,Back,Left,Right", true, "gold")
		local capY = 0.8 + height
		block(pm, "Gaeseok", V3(3.2, 0.7, 3.2), look * CF(0, capY + 0.35, 0), P.graniteDark, Mat.Granite)
		block(pm, "Gwaepan", V3(2.4, 2.6, 0.45), look * CF(0, capY + 2.0, 0), P.meok, Mat.Slate)
		for k, yang in GUA[trigram.name] do
			local yy = capY + 1.1 + (k - 1) * 0.72
			if yang == 1 then
				block(pm, "Hyo", V3(1.8, 0.42, 0.1), look * CF(0, yy, -0.27), P.hwang, Mat.SmoothPlastic)
			else
				for _, sx in { -1, 1 } do
					block(pm, "Hyo", V3(0.72, 0.42, 0.1), look * CF(sx * 0.54, yy, -0.27), P.hwang, Mat.SmoothPlastic)
				end
			end
		end
		siteMarker(pm, "tri_" .. i, pos + V3(0, 2.6, 0), 6, trigram.name)
	end
	-- 오르막(서쪽에서 올라선다) 끝 비석과 석등 둘
	local a = math.rad(190)
	local st = V3(center.X + math.cos(a) * 62, 0, center.Z + math.sin(a) * 62)
	stele(m, V3(st.X, Land.surface(st.X, st.Z), st.Z), "관성대", center)
	for _, da in { -9, 9 } do
		local b = math.rad(190 + da)
		local q = V3(center.X + math.cos(b) * 58, 0, center.Z + math.sin(b) * 58)
		Build.stoneLantern(m, at(q.X, q.Z))
	end
end

-- 영맥 못: Kit.vein 을 땅에 맞춰 놓는다. 비탈이면 못을 조금 들고 아래를 돌로 받친다. 등급 돌은 땅에 박는다
local function placeVein(parent: Instance, s)
	local r = s.radius
	local sf = Land.surface(s.x, s.z)
	local lo, hi = Kit.spanAt(s.x, s.z, r + 1.5)
	local y = sf
	if s.id == "low@plaza" then
		y = PLAZA_TOP
	elseif hi - sf > 0.6 then
		y = sf + math.min(hi - sf - 0.4, 4)
	end
	local m = Kit.vein(parent, s.grade, V3(s.x, y, s.z), r)
	m.Name = s.name
	if s.id ~= "low@plaza" and y - 2.4 > lo - 0.5 then
		local bottom = lo - 1.5
		local depth = (y - 2.4) - bottom
		if depth > 0.4 then
			disc(m, "Footing", V3(s.x, bottom + depth / 2, s.z), r + 1.5, depth, C.stoneDark, Mat.Slate)
		end
	end
	local mark = m:FindFirstChild("Mark") :: BasePart?
	if mark then
		local p = mark.CFrame.Position
		local g = Land.surface(p.X, p.Z)
		mark.CFrame = (mark.CFrame - p) + V3(p.X, math.max(g, y - 0.4) + 1.9, p.Z)
	end
	return m
end

-- 영초가 돋는 범위: 땅(하늘섬은 섬 윗면) 높낮이를 다 덮는 보이지 않는 상자. Herbs 는 상자 위에서 아래로 쏜다
local function placeHerbZone(parent: Instance, def)
	local lo, hi = math.huge, -math.huge
	for x = def.x - def.sx / 2, def.x + def.sx / 2, 10 do
		for z = def.z - def.sz / 2, def.z + def.sz / 2, 10 do
			local y = if def.sky then select(2, Land.island(x, z)) else Land.height(x, z)
			if y then
				lo, hi = math.min(lo, y), math.max(hi, y)
			end
		end
	end
	local zone =
		block(parent, "HerbZone", V3(def.sx, hi - lo + 24, def.sz), CF(def.x, (lo + hi) / 2 + 4, def.z), C.grass)
	zone.Transparency = 1
	zone.CanCollide = false
	zone.CanQuery = false
	zone.CanTouch = false
	zone.CastShadow = false
	zone:SetAttribute("Name", def.name)
	zone:SetAttribute("RareMult", def.rare or 1)
	zone:SetAttribute("Weight", def.weight or 1)
	zone:AddTag("HerbZone")
	return zone
end

local function buildShared(root: Instance)
	local sites = folder(root, "자리")
	local daises = folder(sites, "오행처")
	for _, s in World.ELEMENT_SITES do
		buildElementDais(daises, s)
	end
	local altars = folder(sites, "성대")
	for _, def in Sites.STAR_ALTARS do
		buildStarAltar(altars, def)
	end
	buildMesaAltar(sites)
	-- '위' 자리: 관운봉 꼭대기 (꼭대기 꾸밈은 산 담당)
	local up = SITE.up
	local upModel = model(sites, up.name)
	siteMarker(upModel, "up", at(up.x, up.z, 1), 8)

	local pads = folder(root, "전송진")
	for order, def in Sites.WAYPOINTS do
		Kit.waypoint(pads, def, order)
	end
	local veins = folder(root, "영맥")
	for _, s in Sites.VEINS do
		placeVein(veins, s)
	end
	local zones = folder(root, "영초 범위")
	for _, def in Sites.HERB_ZONES do
		placeHerbZone(zones, def)
	end
	local spots = folder(root, "비급자리")
	for _, position in MANUAL_SPOTS do
		local spot = block(spots, "ManualSpot", V3(2, 0.2, 2), CF(position), C.stone)
		spot.Transparency = 1
		spot.CanCollide = false
		spot.CanQuery = false
		spot.CanTouch = false
		spot:AddTag("ManualSpot")
	end
end

-- 짓기 ------------------------------------------------------------------------------------

-- 송계와 자리만 (땅마다의 모듈 없이). 미리보기와 테스트가 따로 부른다
function World.buildHub(root: Instance)
	table.clear(taken)
	buildVillage(root, makeRng(20261003))
	buildRiver(root, makeRng(20261004))
	buildGrove(root, makeRng(20261005))
	buildShared(root)
end

-- 땅마다의 모듈: 차례와 시드 (시드를 바꾸면 그 땅 모양이 바뀐다)
World.REGIONS = {
	{ module = "WorldNorth", seed = 7101 },
	{ module = "WorldMountains", seed = 7202 },
	{ module = "WorldEast", seed = 7303 },
	{ module = "WorldSouth", seed = 7404 },
	{ module = "WorldWest", seed = 7505 },
	{ module = "WorldSea", seed = 7606 },
}
World.REGION_ERRORS = {} :: { string }
World.TIMINGS = {} :: { [string]: number }

function World.build(workspaceRoot: Instance, lighting: Instance): Model
	local root = Instance.new("Model")
	root.Name = World.MODEL_NAME

	local started = os.clock()
	World.buildHub(root)
	World.TIMINGS.hub = os.clock() - started
	table.clear(World.REGION_ERRORS)
	for _, region in World.REGIONS do
		local t0 = os.clock()
		-- 한 땅이 잘못돼도 나머지 맵은 짓는다 (테스트가 REGION_ERRORS 를 본다)
		local ok, err = pcall(function()
			require((script.Parent :: any)[region.module]).build(root, makeRng(region.seed))
		end)
		World.TIMINGS[region.module] = os.clock() - t0
		if not ok then
			local message = region.module .. ": " .. tostring(err)
			table.insert(World.REGION_ERRORS, message)
			warn("[옥반] 땅을 짓지 못했다 " .. message)
		end
	end

	require(script.Parent.WorldLighting)(lighting)

	root.Parent = workspaceRoot
	return root
end

return World
