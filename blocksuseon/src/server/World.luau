-- 수계(하계) 맵. 땅은 지형(Terrain)이고, 그 위의 마을·자리·진은 블록으로 짓는다.
--
-- 땅 모양은 Shared.Land 한 곳에 있다. 지형은 tools/bake_place.luau 가 그 모양대로 플레이스 파일에
-- 구워 넣고, 여기서는 그 높이(Land.height)를 따라 나머지를 놓는다 (맵을 굽는 Lune 에서는 레이캐스트가 없다).
-- 게임 서버는 Workspace 에 "연국" 이 없을 때만 이걸 다시 부른다 (지형은 server/TerrainGen.luau).
-- 다른 시스템은 이름이 아니라 태그로 맵을 찾는다:
--   Ground        - 영초가 돋는 바닥 판 (지형 말고)
--   Vein          - 영맥 (속성 VeinId, Radius)
--   HerbZone      - 영초가 돋는 범위 (속성 RareMult 가 있으면 귀한 영초가 더 잘 돋는다)
--   ManualSpot    - 비급이 나타나는 자리
--   Site          - 과업 자리 (속성 Site = 자리 id, Radius). 오행처 el_wood 등
--   Waypoint      - 전송진 (속성 WaypointId, Name, Order)
--   Plaque        - 글자를 새길 판 (속성 Text 등, client/Plaques.luau)
--   MarketSpot    - 상점 자리 (속성 Shop = "market" 만물상 | "smith" 대장간). F 버튼이 붙어 있다 (server/Market.luau)
-- 땅마다 원작 수계의 방위를 따른다 (Land.luau 머리말).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")

local Land = require(Shared.Land)

local World = {}

World.MODEL_NAME = "연국"

local function at(x: number, z: number, lift: number?): Vector3
	return Vector3.new(x, Land.surface(x, z) + (lift or 0), z)
end
World.at = at

-- 땅 위 (등선향 아래의 폐허처럼 떠 있는 섬 밑에 놓을 때)
local function atGround(x: number, z: number, lift: number?): Vector3
	return Vector3.new(x, Land.height(x, z) + (lift or 0), z)
end

-- 비급이 나타날 수 있는 자리. 마을 둘레에 몇 곳, 나머지는 땅마다 흩어 둔다
local MANUAL_XZ = {
	-- 연국 둘레
	{ 0, 80 },
	{ -62, -58 },
	{ 96, 10 },
	{ 70, 140 },
	-- 영초숲
	{ -200, -200 },
	{ -420, -20 },
	{ -250, 220 },
	{ -360, 180 },
	-- 쇄천봉과 서쪽
	{ -660, -150 },
	{ -620, -330 },
	{ -980, -640 },
	{ -600, 120 },
	{ -1100, 70 },
	-- 북방 대초원
	{ -200, -950 },
	{ 300, -1100 },
	{ 110, -790 },
	-- 벽라국
	{ 470, -245 },
	{ 330, 320 },
	{ 480, 180 },
	-- 답천사막
	{ 800, -300 },
	{ 1000, 250 },
	{ 880, -750 },
	{ 1130, -560 },
	-- 등선향
	{ 960, -20 },
	-- 남해
	{ -330, 735 },
	{ 40, 1150 },
	{ 700, 700 },
}
local MANUAL_SPOTS = {}
for _, xz in MANUAL_XZ do
	table.insert(MANUAL_SPOTS, at(xz[1], xz[2], 0.2))
end
World.MANUAL_SPOTS = MANUAL_SPOTS

-- 오행처: 영근 속성마다 운기하는 자리 (Tasks.luau 의 el_* 와 맞춘다)
local ELEMENT_SITES = {
	{ id = "el_wood", name = "목 오행처", x = -330, z = -90, color = Color3.fromRGB(110, 200, 120) },
	{ id = "el_fire", name = "화 오행처", x = 420, z = -66, color = Color3.fromRGB(240, 120, 80) },
	{ id = "el_earth", name = "토 오행처", x = 860, z = 10, color = Color3.fromRGB(210, 170, 100) },
	{ id = "el_metal", name = "금 오행처", x = -458, z = -66, color = Color3.fromRGB(235, 235, 240) },
	{ id = "el_water", name = "수 오행처", x = -80, z = 650, color = Color3.fromRGB(90, 140, 230) },
}
World.ELEMENT_SITES = ELEMENT_SITES

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
local LU_CLUSTERS = {
	Vector3.new(24, 0.5, 24),
	Vector3.new(-24, 0.5, 24),
	Vector3.new(-24, 0.5, -24),
	Vector3.new(24, 0.5, -24),
}

-- 팔괘: 답천대 천겁대 기둥에 선천팔괘 자리대로 단다 (건은 남, 곤은 북, 리는 동, 감은 서).
-- 각도는 천겁대 중심에서 (cos, sin) = (x, z). 순서는 건 태 리 진 손 감 간 곤
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

-- 천인기 천순: 마지막 부탁을 하는 마을 노인 셋
local ELDERS = {
	{ id = "elder_1", name = "늙은 약초꾼", position = Vector3.new(-26, 0.5, 8), faces = Vector3.new(0, 0.5, 0) },
	{ id = "elder_2", name = "늙은 대장장이", position = Vector3.new(42, 0, 14), faces = Vector3.new(60, 0, 2) },
	{ id = "elder_3", name = "늙은 뱃사공", position = Vector3.new(-82, 0, 20), faces = Vector3.new(-95, 0, 20) },
}

-- 만물상: 광장 동북쪽, 대장간과 연국 전송진 사이. 판대 앞이 광장을 본다.
-- 주인(Npcs.luau 의 merchant)은 판대 뒤 걸상에 앉는다 (Npcs 의 position 은 그 걸상 자리)
local STALL = { id = "merchant", position = Vector3.new(48, 0, -26), faces = Vector3.zero }
World.STALL = STALL

-- 사방 성대 (육합만로, 축기·결단에서도 다시 쓴다)
local STAR_ALTARS = {
	{
		id = "star_east",
		name = "동쪽 성대",
		carve = "동방 청룡",
		x = 1190,
		z = -40,
		color = Color3.fromRGB(80, 200, 170),
	},
	{
		id = "star_west",
		name = "서쪽 성대",
		carve = "서방 백호",
		x = -1180,
		z = 40,
		color = Color3.fromRGB(235, 235, 240),
	},
	{
		id = "star_south",
		name = "남쪽 성대",
		carve = "남방 주작",
		x = 40,
		z = 1150,
		color = Color3.fromRGB(230, 90, 70),
	},
	{
		id = "star_north",
		name = "북쪽 성대",
		carve = "북방 현무",
		x = 0,
		z = -1180,
		color = Color3.fromRGB(90, 100, 170),
	},
}

-- 전송진 (Travel.luau). 연국 진은 처음부터 열려 있다
local WAYPOINTS = {
	{ id = "wp_yeonguk", name = "연국", x = 60, z = -60 },
	{ id = "wp_yeonsan", name = "영초숲", x = -300, z = -70 },
	{ id = "wp_seoak", name = "서악 마을", x = -490, z = 0 },
	{ id = "wp_summit", name = "쇄천봉 꼭대기", x = -842, z = -206 },
	{ id = "wp_star_west", name = "서천 설원", x = -1160, z = 60 },
	{ id = "wp_star_north", name = "북방 성대", x = 24, z = -1160 },
	{ id = "wp_cheonsaek", name = "천색성", x = 420, z = 10 },
	{ id = "wp_dapcheon", name = "답천대", x = 740, z = -340 },
	{ id = "wp_ruins", name = "중령성국 폐허", x = 830, z = -60, ground = true }, -- 등선향 밑
	{ id = "wp_star_east", name = "동쪽 성대", x = 1170, z = -20 },
	{ id = "wp_coast", name = "연하 하구", x = -55, z = 640 },
	{ id = "wp_star_south", name = "남천도", x = 62, z = 1130 },
	{ id = "wp_deungseon", name = "등선향", x = 840, z = -168 },
}
World.WAYPOINTS = WAYPOINTS

-- 매번 같은 모양이 나오도록 고정 시드 난수 (Park–Miller)
local function makeRng(seed: number)
	local state = seed
	return function(min: number, max: number): number
		state = (state * 16807) % 2147483647
		return min + (max - min) * (state / 2147483647)
	end
end

local C = {
	grass = Color3.fromRGB(104, 150, 82),
	grassDark = Color3.fromRGB(86, 128, 70),
	stone = Color3.fromRGB(170, 164, 150),
	stoneDark = Color3.fromRGB(118, 114, 108),
	plaster = Color3.fromRGB(236, 230, 214),
	wood = Color3.fromRGB(110, 74, 50),
	woodDark = Color3.fromRGB(70, 46, 34),
	lacquer = Color3.fromRGB(58, 34, 28),
	roof = Color3.fromRGB(52, 74, 86),
	red = Color3.fromRGB(168, 46, 40),
	leaf = Color3.fromRGB(66, 122, 70),
	leafLight = Color3.fromRGB(96, 150, 82),
	blossom = Color3.fromRGB(240, 172, 196),
	water = Color3.fromRGB(80, 150, 200),
	snow = Color3.fromRGB(240, 244, 248),
	dirt = Color3.fromRGB(150, 116, 82),
	sandstone = Color3.fromRGB(196, 140, 92),
	sandstoneDark = Color3.fromRGB(150, 96, 62),
	basalt = Color3.fromRGB(56, 52, 52),
	lava = Color3.fromRGB(255, 110, 40),
	gold = Color3.fromRGB(214, 170, 80),
	jade = Color3.fromRGB(110, 190, 160),
	felt = Color3.fromRGB(226, 214, 186),
}

local VEIN_COLORS = {
	low = Color3.fromRGB(110, 230, 220),
	mid = Color3.fromRGB(110, 150, 255),
	high = Color3.fromRGB(255, 205, 100),
	top = Color3.fromRGB(214, 170, 255),
}

-- position 에 서서 target 쪽(수평)을 보는 CFrame.
-- CFrame.lookAt 은 Lune(맵을 굽는 곳)에서 Z 방향이 뒤집혀 나오므로 쓰지 않는다. Angles 는 Lune 과 Roblox 가 같다.
local function face(position: Vector3, target: Vector3): CFrame
	local dx, dz = target.X - position.X, target.Z - position.Z
	if dx * dx + dz * dz < 1e-6 then
		return CFrame.new(position)
	end
	return CFrame.new(position) * CFrame.Angles(0, math.atan2(-dx, -dz), 0)
end

local function block(
	parent: Instance,
	name: string,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material?
): Part
	local part = Instance.new("Part")
	part.Name = name
	part.Anchored = true
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = material or Enum.Material.SmoothPlastic
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = parent
	return part
end

local function wedge(
	parent: Instance,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material?
): WedgePart
	local part = Instance.new("WedgePart")
	part.Name = "Wedge"
	part.Anchored = true
	part.Size = size
	part.CFrame = cframe
	part.Color = color
	part.Material = material or Enum.Material.SmoothPlastic
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = parent
	return part
end

-- 바닥에 납작하게 누운 원판 (Cylinder 의 축은 X 라서 Z 로 90도 눕힌다)
local function disc(
	parent: Instance,
	name: string,
	center: Vector3,
	radius: number,
	thickness: number,
	color: Color3,
	material: Enum.Material?
): Part
	local part = block(
		parent,
		name,
		Vector3.new(thickness, radius * 2, radius * 2),
		CFrame.new(center) * CFrame.Angles(0, 0, math.rad(90)),
		color,
		material
	)
	part.Shape = Enum.PartType.Cylinder
	return part
end

local function ball(
	parent: Instance,
	name: string,
	center: Vector3,
	size: number,
	color: Color3,
	material: Enum.Material?
)
	local part = block(parent, name, Vector3.new(size, size, size), CFrame.new(center), color, material)
	part.Shape = Enum.PartType.Ball
	return part
end

local function folder(parent: Instance, name: string): Folder
	local f = Instance.new("Folder")
	f.Name = name
	f.Parent = parent
	return f
end

local function model(parent: Instance, name: string): Model
	local m = Instance.new("Model")
	m.Name = name
	m.Parent = parent
	return m
end

local function light(part: BasePart, color: Color3, range: number, brightness: number)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Parent = part
end

local function motes(part: BasePart, color: Color3, rate: number)
	local emitter = Instance.new("ParticleEmitter")
	emitter.Name = "Motes"
	emitter.Color = ColorSequence.new(color)
	emitter.LightEmission = 1
	emitter.Rate = rate
	emitter.Lifetime = NumberRange.new(1.5, 2.5)
	emitter.Speed = NumberRange.new(0.5, 1.5)
	emitter.SpreadAngle = Vector2.new(180, 180)
	emitter.Size = NumberSequence.new(0.25)
	emitter.Parent = part
	return emitter
end

-- 둘레 몇 군데 땅 높이 가운데 가장 낮은 곳과 높은 곳 (비탈에 놓을 때 바닥을 메우려고)
local function spanAt(x: number, z: number, radius: number): (number, number)
	local low, high = math.huge, -math.huge
	for i = 0, 8 do
		local px, pz = x, z
		if i > 0 then
			local a = math.rad(i * 45)
			px, pz = x + math.cos(a) * radius, z + math.sin(a) * radius
		end
		local h = Land.surface(px, pz)
		low, high = math.min(low, h), math.max(high, h)
	end
	return low, high
end

-- 비탈에서도 평평한 바닥: 가장 높은 곳에 윗면을 맞추고 아래를 돌로 메운다. 윗면 높이를 돌려준다
local function footing(parent: Instance, x: number, z: number, sizeX: number, sizeZ: number, color: Color3?): number
	local low, high = spanAt(x, z, math.max(sizeX, sizeZ) / 2)
	local depth = high - low + 3
	block(
		parent,
		"Footing",
		Vector3.new(sizeX, depth, sizeZ),
		CFrame.new(x, high - depth / 2 + 0.3, z),
		color or C.stoneDark,
		Enum.Material.Slate
	)
	return high + 0.3
end

-- 글자를 새길 판에 표시만 한다. 글자는 클라이언트(Plaques.luau)가 붓글씨 글자판으로 겉면에 새긴다.
-- 공중에 띄우는 이름표(BillboardGui)는 쓰지 않는다.
local function engrave(part: BasePart, text: string, faces: string?, vertical: boolean?, ink: string?)
	part:SetAttribute("Text", text)
	part:SetAttribute("Faces", faces or "Front")
	if vertical then
		part:SetAttribute("Vertical", true)
	end
	if ink then
		part:SetAttribute("Ink", ink)
	end
	part:AddTag("Plaque")
end

local function facing(position: Vector3, toward: Vector3?): CFrame
	local target = toward or Vector3.zero
	local flat = Vector3.new(target.X, position.Y, target.Z)
	if (flat - position).Magnitude < 0.1 then
		flat = position + Vector3.new(0, 0, 1)
	end
	return face(position, flat)
end

-- 땅에 박은 나무 현판. 앞면이 toward 쪽(기본은 연국 광장)을 본다. 앞뒤 두 면에 새긴다
local function signboard(parent: Instance, ground: Vector3, text: string, toward: Vector3?)
	local look = facing(ground, toward)
	local m = model(parent, "현판")
	local width = math.max(4.2, (utf8.len(text) or 2) * 1.5 + 1.6)
	for _, x in { -1, 1 } do
		block(
			m,
			"Post",
			Vector3.new(0.45, 6, 0.45),
			look * CFrame.new(x * (width / 2 - 0.35), 1.8, 0),
			C.woodDark,
			Enum.Material.Wood
		)
	end
	local board =
		block(m, "Board", Vector3.new(width, 1.7, 0.3), look * CFrame.new(0, 3.5, 0), C.lacquer, Enum.Material.Wood)
	engrave(board, text, "Front,Back")
	block(m, "Cap", Vector3.new(width + 0.8, 0.3, 0.9), look * CFrame.new(0, 4.55, 0), C.roof)
	return m
end

-- 돌 비석. 세로로 새긴다 (땅 이름, 성대)
local function stele(parent: Instance, ground: Vector3, text: string, toward: Vector3?, color: Color3?)
	local look = facing(ground, toward)
	local count = utf8.len(text) or 2
	local height = 2.2 * count + 1.6
	local m = model(parent, "비석")
	block(m, "Base", Vector3.new(4.6, 2, 2.6), look, C.stoneDark, Enum.Material.Slate)
	local slab = block(
		m,
		"Slab",
		Vector3.new(3, height, 1),
		look * CFrame.new(0, 1 + height / 2, 0),
		color or C.stone,
		Enum.Material.Slate
	)
	engrave(slab, text, "Front,Back", true, "ink")
	block(m, "Cap", Vector3.new(3.6, 0.6, 1.5), look * CFrame.new(0, 1.3 + height, 0), C.stoneDark, Enum.Material.Slate)
	return m
end

-- 붉은 패루(문). 현판은 가로대에 달려 양쪽에서 보인다
local function gateway(parent: Instance, ground: Vector3, toward: Vector3, text: string, width: number?)
	local w = width or 14
	local look = facing(ground, toward)
	local m = model(parent, text .. " 문")
	for _, x in { -1, 1 } do
		block(m, "Post", Vector3.new(1.2, 14, 1.2), look * CFrame.new(x * w / 2, 6, 0), C.red, Enum.Material.Wood)
		block(m, "Foot", Vector3.new(2, 1.4, 2), look * CFrame.new(x * w / 2, 0, 0), C.stoneDark, Enum.Material.Slate)
	end
	block(m, "Beam", Vector3.new(w + 2, 1, 1.4), look * CFrame.new(0, 12.2, 0), C.red, Enum.Material.Wood)
	block(m, "Roof", Vector3.new(w + 4, 0.8, 3), look * CFrame.new(0, 13.4, 0), C.roof)
	local board = block(
		m,
		"Board",
		Vector3.new(math.max(5, (utf8.len(text) or 2) * 1.8 + 1.4), 2.2, 0.3),
		look * CFrame.new(0, 10.6, 0),
		C.lacquer,
		Enum.Material.Wood
	)
	engrave(board, text, "Front,Back")
	return m
end

-- 과업 자리 표시: 보이지 않는 판에 Site 태그를 단다. prompt 면 F 로 만지는 자리 (TaskService 가 버튼을 단다)
local function siteMarker(parent: Instance, id: string, position: Vector3, radius: number, prompt: string?): Part
	local marker = block(parent, "Site_" .. id, Vector3.new(2, 0.2, 2), CFrame.new(position), C.stone)
	marker.Transparency = 1
	marker.CanCollide = false
	marker.CanQuery = false
	marker.CanTouch = false
	marker:SetAttribute("Site", id)
	marker:SetAttribute("Radius", radius)
	if prompt then
		marker:SetAttribute("Prompt", prompt)
	end
	marker:AddTag("Site")
	return marker
end

-- 상점 자리: 보이지 않는 판에 MarketSpot 태그(속성 Shop)와 F 버튼을 단다. 버튼은 화면에 창만 연다.
-- 사고 강화하는 요청은 서버(Market.luau)가 이 판 곁에 섰는지 다시 본다
local function marketSpot(parent: Instance, kind: string, position: Vector3, action: string, object: string): Part
	local spot = block(parent, "MarketSpot_" .. kind, Vector3.new(2, 0.2, 2), CFrame.new(position), C.stone)
	spot.Transparency = 1
	spot.CanCollide = false
	spot.CanQuery = false
	spot.CanTouch = false
	spot:SetAttribute("Shop", kind)
	spot:AddTag("MarketSpot")
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "ShopPrompt"
	prompt.ActionText = action
	prompt.ObjectText = object
	prompt.KeyboardKeyCode = Enum.KeyCode.F
	prompt.HoldDuration = 0.2
	prompt.RequiresLineOfSight = false
	prompt.MaxActivationDistance = 10
	prompt:SetAttribute("Shop", kind)
	prompt.Parent = spot
	return spot
end

local function lantern(parent: Instance, position: Vector3)
	local m = model(parent, "등롱")
	block(
		m,
		"Post",
		Vector3.new(0.8, 7.6, 0.8),
		CFrame.new(position + Vector3.new(0, 3.2, 0)),
		C.woodDark,
		Enum.Material.Wood
	)
	local lamp = block(
		m,
		"Lamp",
		Vector3.new(1.8, 2.2, 1.8),
		CFrame.new(position + Vector3.new(0, 7.6, 0)),
		C.red,
		Enum.Material.Neon
	)
	light(lamp, Color3.fromRGB(255, 170, 120), 16, 1.5)
	return m
end

-- 영맥: 돌 테두리 안의 빛나는 못. 곁에 세운 돌에 등급을 새긴다
local VEIN_NAMES = { low = "하품 영맥", mid = "중품 영맥", high = "상품 영맥", top = "극품 영맥" }
local function vein(parent: Instance, id: string, center: Vector3, radius: number)
	local color = VEIN_COLORS[id]
	local m = model(parent, "영맥_" .. id)
	disc(m, "Rim", center + Vector3.new(0, 0.3, 0), radius + 1.5, 0.6, C.stoneDark, Enum.Material.Slate)
	disc(m, "Bed", center + Vector3.new(0, -1.2, 0), radius + 1.5, 2.4, C.stoneDark, Enum.Material.Slate)
	local pool = disc(m, "Pool", center + Vector3.new(0, 0.7, 0), radius, 0.4, color, Enum.Material.Neon)
	pool.Transparency = 0.35
	pool.CanCollide = false
	pool:SetAttribute("VeinId", id)
	pool:SetAttribute("Radius", radius)
	pool:AddTag("Vein")
	light(pool, color, radius * 2.5, 2)

	local emitter = Instance.new("ParticleEmitter")
	emitter.Name = "Motes"
	emitter.Color = ColorSequence.new(color)
	emitter.LightEmission = 1
	emitter.Rate = radius * 1.5
	emitter.Lifetime = NumberRange.new(2, 3.5)
	emitter.Speed = NumberRange.new(2, 4)
	emitter.SpreadAngle = Vector2.new(15, 15)
	emitter.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.4),
		NumberSequenceKeypoint.new(1, 0),
	})
	emitter.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.2),
		NumberSequenceKeypoint.new(1, 1),
	})
	-- 원판이 Z 로 누워 있어서 파티클이 위로 솟도록 방향을 옆(Right)으로 준다
	emitter.EmissionDirection = Enum.NormalId.Right
	emitter.Shape = Enum.ParticleEmitterShape.Cylinder
	emitter.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
	emitter.Parent = pool

	-- 못가에 세운 작은 돌. 연국 광장 쪽을 보고 등급을 새긴다
	local toward = Vector3.new(-center.X, 0, -center.Z)
	local dir = if toward.Magnitude > 1 then toward.Unit else Vector3.new(0, 0, 1)
	local stonePos = center + dir * (radius + 2.6) + Vector3.new(0, 1, 0)
	local mark =
		block(m, "Mark", Vector3.new(2.4, 4.6, 0.8), facing(stonePos, stonePos + dir), C.stone, Enum.Material.Slate)
	engrave(mark, VEIN_NAMES[id], "Front", true, "ink")
	return m
end

-- 정면(LookVector)을 바라보는 기와집 한 채
local function house(parent: Instance, cf: CFrame, width: number, depth: number, roofColor: Color3, wallColor: Color3?)
	local m = model(parent, "민가")
	local wallH = 9
	block(m, "Base", Vector3.new(width + 2, 3, depth + 2), cf * CFrame.new(0, -0.5, 0), C.stone, Enum.Material.Slate)
	block(m, "Walls", Vector3.new(width, wallH, depth), cf * CFrame.new(0, 1 + wallH / 2, 0), wallColor or C.plaster)
	for _, corner in { Vector3.new(1, 0, 1), Vector3.new(-1, 0, 1), Vector3.new(1, 0, -1), Vector3.new(-1, 0, -1) } do
		block(
			m,
			"Pillar",
			Vector3.new(1.2, wallH, 1.2),
			cf * CFrame.new(corner.X * width / 2, 1 + wallH / 2, corner.Z * depth / 2),
			C.wood,
			Enum.Material.Wood
		)
	end
	block(
		m,
		"Beam",
		Vector3.new(width + 0.6, 1, depth + 0.6),
		cf * CFrame.new(0, 1 + wallH, 0),
		C.wood,
		Enum.Material.Wood
	)
	block(m, "Door", Vector3.new(3.4, 6, 0.4), cf * CFrame.new(0, 4, -depth / 2 - 0.1), C.woodDark, Enum.Material.Wood)
	for _, x in { -width / 3, width / 3 } do
		block(
			m,
			"Window",
			Vector3.new(2.4, 2.4, 0.3),
			cf * CFrame.new(x, 6, -depth / 2 - 0.1),
			C.woodDark,
			Enum.Material.Wood
		)
	end

	-- 맞배지붕: 앞뒤로 비탈진 쐐기 두 개
	local roofH = 4.5
	local half = depth / 2 + 1.5
	local roofY = 1.5 + wallH + roofH / 2
	local size = Vector3.new(width + 3, roofH, half)
	wedge(m, size, cf * CFrame.new(0, roofY, -half / 2), roofColor)
	wedge(m, size, cf * CFrame.new(0, roofY, half / 2) * CFrame.Angles(0, math.pi, 0), roofColor)
	block(m, "Ridge", Vector3.new(width + 3.4, 0.8, 1), cf * CFrame.new(0, 1.5 + wallH + roofH, 0), C.woodDark)
	return m
end

-- 땅 위에 집 한 채 (x, z 에서 toward 를 본다)
local function houseAt(
	parent: Instance,
	x: number,
	z: number,
	toward: Vector3,
	width: number,
	depth: number,
	roof: Color3
)
	local top = footing(parent, x, z, width + 2, depth + 2, C.stone)
	return house(parent, face(Vector3.new(x, top, z), toward), width, depth, roof)
end

local function tree(parent: Instance, base: Vector3, rng, blossom: boolean)
	local m = model(parent, if blossom then "벚나무" else "나무")
	local height = rng(8, 14)
	local trunkW = rng(1.4, 2.2)
	block(
		m,
		"Trunk",
		Vector3.new(trunkW, height + 2, trunkW),
		CFrame.new(base + Vector3.new(0, height / 2 - 1, 0)),
		C.wood,
		Enum.Material.Wood
	)
	local leafColor = if blossom then C.blossom elseif rng(0, 1) > 0.5 then C.leaf else C.leafLight
	local s1 = rng(8, 11)
	block(
		m,
		"Leaves",
		Vector3.new(s1, s1 * 0.7, s1),
		CFrame.new(base + Vector3.new(0, height, 0)),
		leafColor,
		Enum.Material.Grass
	)
	local s2 = s1 * 0.6
	block(
		m,
		"Leaves",
		Vector3.new(s2, s2 * 0.8, s2),
		CFrame.new(base + Vector3.new(rng(-1, 1), height + s1 * 0.5, rng(-1, 1))),
		leafColor,
		Enum.Material.Grass
	)
end

-- 사막의 종려나무
local function palm(parent: Instance, base: Vector3, rng)
	local m = model(parent, "종려")
	local lean = rng(-0.25, 0.25)
	local height = rng(10, 15)
	local top = base
	for i = 0, 4 do
		local seg = base + Vector3.new(lean * i * 1.2, i * height / 5 + height / 10, 0)
		block(m, "Trunk", Vector3.new(1.1, height / 5 + 0.4, 1.1), CFrame.new(seg), C.wood, Enum.Material.Wood)
		top = seg + Vector3.new(0, height / 10, 0)
	end
	for k = 0, 5 do
		local a = math.rad(k * 60 + rng(-10, 10))
		local dir = Vector3.new(math.cos(a), 0, math.sin(a))
		block(
			m,
			"Frond",
			Vector3.new(1.4, 0.3, 6),
			face(top + dir * 2.6 - Vector3.new(0, 0.6, 0), top + dir * 6) * CFrame.Angles(math.rad(-18), 0, 0),
			C.leafLight,
			Enum.Material.Grass
		)
	end
end

local function rock(parent: Instance, base: Vector3, size: number, rng, color: Color3?)
	block(
		parent,
		"Rock",
		Vector3.new(size, size * rng(0.5, 0.9), size * rng(0.7, 1.1)),
		CFrame.new(base + Vector3.new(0, size * 0.25, 0)) * CFrame.Angles(rng(-0.3, 0.3), rng(0, 6), rng(-0.3, 0.3)),
		color or C.stoneDark,
		Enum.Material.Rock
	)
end

-- 전송진: 돌 원판과 옥빛 고리, 곁에 이름을 새긴 표석
local function waypoint(parent: Instance, def, order: number)
	local m = model(parent, "전송진_" .. def.name)
	local heightAt = if def.ground then Land.height else Land.surface
	local top = heightAt(def.x, def.z)
	local low = top
	for i = 1, 8 do
		local a = math.rad(i * 45)
		low = math.min(low, heightAt(def.x + math.cos(a) * 7, def.z + math.sin(a) * 7))
	end
	local depth = top - low + 3
	block(
		m,
		"Footing",
		Vector3.new(15, depth, 15),
		CFrame.new(def.x, top - depth / 2, def.z) * CFrame.Angles(0, math.rad(45), 0),
		C.stoneDark,
		Enum.Material.Slate
	)
	local pad = disc(m, "Pad", Vector3.new(def.x, top + 0.4, def.z), 7, 0.8, C.stone, Enum.Material.Slate)
	pad:SetAttribute("WaypointId", def.id)
	pad:SetAttribute("Name", def.name)
	pad:SetAttribute("Order", order)
	pad:AddTag("Waypoint")
	local ring = disc(
		m,
		"Ring",
		Vector3.new(def.x, top + 0.85, def.z),
		5.4,
		0.1,
		Color3.fromRGB(130, 210, 255),
		Enum.Material.Neon
	)
	ring.Transparency = 0.45
	ring.CanCollide = false
	ring.CanQuery = false
	light(ring, Color3.fromRGB(130, 210, 255), 14, 1)
	for k = 0, 7 do
		local a = math.rad(k * 45 + 22.5)
		local p = Vector3.new(def.x + math.cos(a) * 6.2, top + 1.1, def.z + math.sin(a) * 6.2)
		block(m, "Rune", Vector3.new(0.9, 0.5, 0.9), CFrame.new(p), C.stoneDark, Enum.Material.Slate)
	end
	-- 표석: 진 바깥, 연국 쪽
	local toward = Vector3.new(-def.x, 0, -def.z)
	local dir = if toward.Magnitude > 1 then toward.Unit else Vector3.new(0, 0, 1)
	local base = Vector3.new(def.x, 0, def.z) + dir * 9.5
	local ground = Vector3.new(base.X, heightAt(base.X, base.Z), base.Z)
	local stone = block(
		m,
		"Marker",
		Vector3.new(2.6, 5.4, 1),
		facing(ground + Vector3.new(0, 1.9, 0), ground + Vector3.new(0, 1.9, 0) - dir),
		C.stone,
		Enum.Material.Slate
	)
	engrave(stone, def.name, "Front,Back", (utf8.len(def.name) or 0) <= 3, "ink")
	return m
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
	return m
end

-- 연국 ---------------------------------------------------------------------------------

local function buildVillage(root: Instance, rng)
	local village = folder(root, "마을")
	local plaza = block(village, "광장", Vector3.new(64, 3, 64), CFrame.new(0, -1, 0), C.stone, Enum.Material.Slate)
	plaza:AddTag("Ground")
	vein(village, "low", Vector3.new(0, 0.5, 0), 12)

	for _, angle in { 30, 70, 110, 150, 215, 250 } do
		local rad = math.rad(angle)
		local pos = Vector3.new(math.cos(rad) * 54, 0, math.sin(rad) * 54)
		local roofColor = if rng(0, 1) > 0.6 then C.red else C.roof
		house(village, face(pos, Vector3.zero), rng(13, 17), rng(10, 13), roofColor)
	end
	-- 바깥 마을: 들길 가의 집 몇 채
	for _, spot in { { 96, -36 }, { -60, 95 }, { 85, 75 }, { -66, -96 }, { 112, 40 } } do
		houseAt(
			village,
			spot[1],
			spot[2],
			Vector3.zero,
			rng(12, 15),
			rng(9, 12),
			if rng(0, 1) > 0.5 then C.red else C.roof
		)
	end

	-- 율점 등롱: 귀퉁이마다 셋. 가운데 앉으면 셋 모두 곁이다
	local lu = folder(village, "율점")
	for cluster, center in LU_CLUSTERS do
		for k = 0, 2 do
			local index = (cluster - 1) * 3 + k + 1
			local angle = math.rad(90 + k * 120)
			local position = center + Vector3.new(math.cos(angle), 0, math.sin(angle)) * 4.5
			local m = model(lu, World.LU_NAMES[index])
			lantern(m, position)
			siteMarker(m, "lu_" .. index, position, 6)
			-- 기둥에 건 나무 패. 가운데(운기하는 자리)를 본다
			local inward = (center - position).Unit
			local tag = block(
				m,
				"Tag",
				Vector3.new(0.9, 2.4, 0.15),
				face(position + inward * 0.5 + Vector3.new(0, 4, 0), center + Vector3.new(0, 4, 0)),
				C.lacquer,
				Enum.Material.Wood
			)
			tag.CanCollide = false
			engrave(tag, World.LU_NAMES[index], "Front,Back", true)
		end
	end
	siteMarker(village, "plaza", Vector3.new(0, 1, 0), 12)

	-- 연단로
	local furnace = model(village, "연단로")
	local fpos = Vector3.new(-12, 0.5, -22)
	block(
		furnace,
		"Base",
		Vector3.new(7, 2, 7),
		CFrame.new(fpos + Vector3.new(0, 1, 0)),
		C.stoneDark,
		Enum.Material.Brick
	)
	local pot = block(
		furnace,
		"Cauldron",
		Vector3.new(4, 5, 5),
		CFrame.new(fpos + Vector3.new(0, 4.4, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		Color3.fromRGB(150, 110, 60),
		Enum.Material.Metal
	)
	pot.Shape = Enum.PartType.Cylinder
	for _, offset in { Vector3.new(2, 0, 2), Vector3.new(-2, 0, 2), Vector3.new(0, 0, -2.6) } do
		block(
			furnace,
			"Leg",
			Vector3.new(0.8, 2.4, 0.8),
			CFrame.new(fpos + offset + Vector3.new(0, 2.6, 0)),
			Color3.fromRGB(120, 86, 46),
			Enum.Material.Metal
		)
	end
	local ember = block(
		furnace,
		"Ember",
		Vector3.new(3, 0.6, 3),
		CFrame.new(fpos + Vector3.new(0, 2.2, 0)),
		Color3.fromRGB(255, 120, 50),
		Enum.Material.Neon
	)
	ember.CanCollide = false
	local smoke = Instance.new("Smoke")
	smoke.Size = 2
	smoke.RiseVelocity = 3
	smoke.Opacity = 0.15
	smoke.Parent = pot
	siteMarker(furnace, "furnace", fpos + Vector3.new(0, 3, 0), 6, "연단")
	signboard(furnace, Vector3.new(fpos.X + 6, 0.5, fpos.Z + 3), "연단로", Vector3.new(0, 0.5, 0))

	-- 마을 대장간 (늙은 대장장이가 바라보는 화덕)
	local smithy = model(village, "대장간")
	local sbase = Vector3.new(54, 0, 2)
	block(
		smithy,
		"Hearth",
		Vector3.new(6, 4, 5),
		CFrame.new(sbase + Vector3.new(6, 2, 0)),
		C.stoneDark,
		Enum.Material.Brick
	)
	local flame = block(
		smithy,
		"Flame",
		Vector3.new(3, 1.5, 2.5),
		CFrame.new(sbase + Vector3.new(6, 4.6, 0)),
		Color3.fromRGB(255, 120, 50),
		Enum.Material.Neon
	)
	flame.CanCollide = false
	local fire = Instance.new("Fire")
	fire.Size = 5
	fire.Heat = 8
	fire.Parent = flame
	for _, z in { -5, 5 } do
		for _, x in { 9, -3 } do
			block(
				smithy,
				"Post",
				Vector3.new(1, 11, 1),
				CFrame.new(sbase + Vector3.new(x, 4.5, z)),
				C.wood,
				Enum.Material.Wood
			)
		end
	end
	block(smithy, "Roof", Vector3.new(15, 1, 13), CFrame.new(sbase + Vector3.new(3, 10.5, 0)), C.roof)
	block(
		smithy,
		"Anvil",
		Vector3.new(2.4, 2, 1.4),
		CFrame.new(sbase + Vector3.new(1, 1, 3.5)),
		C.stoneDark,
		Enum.Material.Metal
	)
	-- 모루 머리와 뿔, 올려 둔 망치. 무기를 벼리는 자리(F)는 모루 위다 (노인 말 걸기 버튼과 떨어져 있다)
	local iron = Color3.fromRGB(84, 84, 90)
	block(
		smithy,
		"AnvilFace",
		Vector3.new(3.2, 0.5, 1.3),
		CFrame.new(sbase + Vector3.new(1, 2.25, 3.5)),
		iron,
		Enum.Material.Metal
	)
	block(
		smithy,
		"AnvilHorn",
		Vector3.new(0.9, 0.35, 0.7),
		CFrame.new(sbase + Vector3.new(3, 2.3, 3.5)),
		iron,
		Enum.Material.Metal
	)
	block(
		smithy,
		"HammerHead",
		Vector3.new(0.45, 0.45, 0.9),
		CFrame.new(sbase + Vector3.new(0.4, 2.72, 3.5)),
		C.stoneDark,
		Enum.Material.Metal
	)
	block(
		smithy,
		"HammerHandle",
		Vector3.new(1.5, 0.18, 0.18),
		CFrame.new(sbase + Vector3.new(1.3, 2.62, 3.5)),
		C.wood,
		Enum.Material.Wood
	)
	marketSpot(smithy, "smith", sbase + Vector3.new(1, 2.9, 3.5), "대장간", "무기 강화")
	-- 벼린 칼을 세워 둔 시렁 (북쪽 기둥 곁)
	local steel = Color3.fromRGB(170, 172, 178)
	for _, x in { 0.5, 4.5 } do
		block(
			smithy,
			"RackPost",
			Vector3.new(0.3, 3.4, 0.3),
			CFrame.new(sbase + Vector3.new(x, 1.7, -4.2)),
			C.wood,
			Enum.Material.Wood
		)
	end
	for _, y in { 0.7, 2.9 } do
		block(
			smithy,
			"RackBar",
			Vector3.new(4.4, 0.25, 0.3),
			CFrame.new(sbase + Vector3.new(2.5, y, -4.2)),
			C.wood,
			Enum.Material.Wood
		)
	end
	for i = 0, 3 do
		local x = 1.3 + i * 0.8
		block(
			smithy,
			"Blade",
			Vector3.new(0.3, 2.6, 0.08),
			CFrame.new(sbase + Vector3.new(x, 1.9, -4.05)),
			steel,
			Enum.Material.Metal
		)
		block(
			smithy,
			"Guard",
			Vector3.new(0.6, 0.15, 0.2),
			CFrame.new(sbase + Vector3.new(x, 3.25, -4.05)),
			C.gold,
			Enum.Material.Metal
		)
		block(
			smithy,
			"Hilt",
			Vector3.new(0.18, 0.7, 0.18),
			CFrame.new(sbase + Vector3.new(x, 3.65, -4.05)),
			C.lacquer,
			Enum.Material.Wood
		)
	end
	-- 서쪽(광장 쪽) 들보에 매단 현판
	block(
		smithy,
		"SignBeam",
		Vector3.new(0.6, 0.6, 9.4),
		CFrame.new(sbase + Vector3.new(-3, 9.6, 0)),
		C.wood,
		Enum.Material.Wood
	)
	for _, z in { -2.2, 2.2 } do
		block(
			smithy,
			"Cord",
			Vector3.new(0.1, 0.4, 0.1),
			CFrame.new(sbase + Vector3.new(-3, 9.1, z)),
			C.woodDark,
			Enum.Material.Fabric
		)
	end
	local signPos = sbase + Vector3.new(-3, 8.05, 0)
	local sign = block(
		smithy,
		"Board",
		Vector3.new(6.1, 1.7, 0.3),
		face(signPos, signPos - Vector3.new(1, 0, 0)),
		C.lacquer,
		Enum.Material.Wood
	)
	engrave(sign, "대장간", "Front,Back")

	buildStall(village)

	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "SpawnLocation"
	spawn.Anchored = true
	spawn.Neutral = true
	spawn.Duration = 0
	spawn.Size = Vector3.new(10, 1, 10)
	spawn.CFrame = CFrame.new(0, 0.6, 24)
	spawn.Color = C.stoneDark
	spawn.Material = Enum.Material.Slate
	spawn.TopSurface = Enum.SurfaceType.Smooth
	spawn.Parent = village

	-- 마을 어귀의 패루 셋 (서쪽은 다리)
	gateway(village, at(0, -125), Vector3.zero, "연국")
	gateway(village, at(125, 0), Vector3.zero, "연국")
	gateway(village, at(0, 125), Vector3.zero, "연국")
	-- 갈림길 현판: 어귀마다 그 길이 가는 곳
	signboard(village, at(12, -132), "북방 대초원", Vector3.zero)
	signboard(village, at(132, 12), "천색성, 답천사막", Vector3.zero)
	signboard(village, at(-12, 132), "용소, 남해", Vector3.zero)
	signboard(village, at(-118, 12), "영초숲, 서악, 쇄천봉", Vector3.zero)
end

-- 연하: 다리, 징검돌, 폭포와 용소 ---------------------------------------------------------

local function buildRiver(root: Instance)
	local river = folder(root, "연하")
	local bridge = model(river, "다리")
	local deck =
		block(bridge, "Deck", Vector3.new(24, 1, 10), CFrame.new(-95, 0.9, 0), C.wood, Enum.Material.WoodPlanks)
	deck:AddTag("Ground")
	for _, z in { -4.6, 4.6 } do
		block(bridge, "Rail", Vector3.new(24, 1.6, 0.6), CFrame.new(-95, 2.2, z), C.red)
	end
	for _, x in { -104, -86 } do
		block(bridge, "Pier", Vector3.new(1.4, 7, 9), CFrame.new(x, -2.6, 0), C.stoneDark, Enum.Material.Slate)
	end

	-- 북쪽 들길이 강을 건너는 징검돌
	local ford = model(river, "징검돌")
	for i = -3, 3 do
		local p = Vector3.new(-260 + i * 4, -0.6, -405 + i * 0.6)
		block(ford, "Stone", Vector3.new(3, 1.6, 3), CFrame.new(p), C.stone, Enum.Material.Slate)
	end

	-- 폭포: 강(수면 -1)이 협곡의 용소(수면 -20)로 떨어진다
	local falls = model(river, "폭포")
	local sheet = block(
		falls,
		"Sheet",
		Vector3.new(17, 20, 1),
		CFrame.new(-95, -10.5, 131.5),
		Color3.fromRGB(200, 230, 245),
		Enum.Material.Glass
	)
	sheet.Transparency = 0.35
	sheet.CanCollide = false
	sheet.CanQuery = false
	local mist = block(falls, "Mist", Vector3.new(16, 1, 6), CFrame.new(-95, -19.5, 136), C.water)
	mist.Transparency = 1
	mist.CanCollide = false
	mist.CanQuery = false
	local spray = Instance.new("ParticleEmitter")
	spray.Color = ColorSequence.new(Color3.fromRGB(235, 245, 255))
	spray.Rate = 40
	spray.Lifetime = NumberRange.new(1.5, 3)
	spray.Speed = NumberRange.new(2, 5)
	spray.SpreadAngle = Vector2.new(60, 60)
	spray.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2), NumberSequenceKeypoint.new(1, 5) })
	spray.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 1) })
	spray.Parent = mist

	-- 용소 벼랑길 난간과 너럭바위 ('아래' 자리)
	local bench = { Vector3.new(-58, 0, 112), Vector3.new(-62, -10, 150), Vector3.new(-68, -19, 176) }
	for i = 1, #bench - 1 do
		local a, b = bench[i], bench[i + 1]
		local steps = math.floor((b - a).Magnitude / 6)
		local side = Vector3.new(-(b.Z - a.Z), 0, b.X - a.X).Unit * 5.5
		for k = 0, steps do
			local p = a:Lerp(b, k / steps) + side
			local post = Vector3.new(p.X, Land.height(p.X, p.Z), p.Z)
			block(
				river,
				"Rail",
				Vector3.new(0.5, 4, 0.5),
				CFrame.new(post + Vector3.new(0, 1.2, 0)),
				C.wood,
				Enum.Material.Wood
			)
		end
	end
	local slab =
		block(river, "너럭바위", Vector3.new(14, 3, 10), CFrame.new(-70, -20.5, 180), C.stone, Enum.Material.Slate)
	slab:AddTag("Ground")
	siteMarker(river, "down", Vector3.new(-70, -18.4, 180), 7)
	signboard(river, at(-48, 108), "용소", Vector3.zero)
end

-- 영초숲 ---------------------------------------------------------------------------------

local function buildForest(root: Instance, rng)
	local forest = folder(root, "영초숲")
	local zone = block(forest, "HerbZone", Vector3.new(330, 70, 660), CFrame.new(-280, 25, 0), C.grass)
	zone.Transparency = 1
	zone.CanCollide = false
	zone.CanQuery = false
	zone.CanTouch = false
	zone:AddTag("HerbZone")

	local keepClear = {
		{ -330, -90, 26 }, -- 고목
		{ -300, -70, 14 }, -- 전송진
		{ -380, 110, 24 }, -- 용혈샘
		{ -118, 30, 8 }, -- 숲 비석
	}
	for _, spot in MANUAL_XZ do
		table.insert(keepClear, { spot[1], spot[2], 8 })
	end
	local trees = folder(forest, "Trees")
	local planted = 0
	for _ = 1, 700 do
		if planted >= 240 then
			break
		end
		local x, z = rng(-460, -120), rng(-330, 330)
		local h = Land.height(x, z)
		local clear = h > 1
			and Land.water(x, z, h) == nil
			and Land.polyDist(x, z, Land.ROADS[5]) > 8
			and Land.polyDist(x, z, Land.ROADS[6]) > 8
		for _, spot in keepClear do
			if (x - spot[1]) ^ 2 + (z - spot[2]) ^ 2 < spot[3] ^ 2 then
				clear = false
			end
		end
		local slope = math.abs(Land.height(x + 4, z) - h) + math.abs(Land.height(x, z + 4) - h)
		if clear and slope < 5 then
			tree(trees, Vector3.new(x, h, z), rng, rng(0, 1) > 0.8)
			planted += 1
		end
	end

	-- 목 오행처: 고목
	local def = ELEMENT_SITES[1]
	local base = at(def.x, def.z)
	local m = model(forest, def.name)
	block(m, "Trunk", Vector3.new(8, 46, 8), CFrame.new(base + Vector3.new(0, 21, -10)), C.woodDark, Enum.Material.Wood)
	for k = 0, 3 do
		local a = math.rad(k * 90 + 45)
		block(
			m,
			"Root",
			Vector3.new(3, 4, 9),
			face(base + Vector3.new(math.cos(a) * 5, 1, math.sin(a) * 5 - 10), base + Vector3.new(0, 1, -10)),
			C.woodDark,
			Enum.Material.Wood
		)
	end
	block(m, "Leaves", Vector3.new(44, 14, 44), CFrame.new(base + Vector3.new(0, 44, -10)), C.leaf, Enum.Material.Grass)
	block(
		m,
		"Leaves",
		Vector3.new(28, 10, 28),
		CFrame.new(base + Vector3.new(2, 54, -8)),
		C.leafLight,
		Enum.Material.Grass
	)
	block(m, "Leaves", Vector3.new(24, 8, 20), CFrame.new(base + Vector3.new(-14, 38, 2)), C.leaf, Enum.Material.Grass)

	-- 중품 영맥 용혈샘: 바위 틈 동굴
	local grotto = model(forest, "용혈샘")
	local gpos = at(-380, 110)
	for k = 0, 5 do
		local a = math.rad(k * 50 + 200)
		rock(grotto, gpos + Vector3.new(math.cos(a) * 17, 0, math.sin(a) * 17), rng(8, 12), rng)
	end
	block(
		grotto,
		"Lintel",
		Vector3.new(30, 4, 14),
		CFrame.new(gpos + Vector3.new(0, 16, -8)) * CFrame.Angles(0.1, 0.3, 0),
		C.stoneDark,
		Enum.Material.Rock
	)
	vein(grotto, "mid", gpos, 11)

	stele(forest, at(-118, 30), "영초숲", Vector3.new(0, 0, 30))
end

-- 쇄천봉, 서악 마을, 서천 설원 -----------------------------------------------------------

local function buildMountain(root: Instance, rng)
	local mountain = folder(root, "쇄천봉")
	local peak = Land.PEAK
	local top = at(peak.x, peak.z)
	vein(mountain, "high", top, 9)
	siteMarker(mountain, "up", top + Vector3.new(0, 0.6, 0), 9)
	for _, corner in { { -13, 13 }, { 13, -13 }, { -13, -13 } } do
		lantern(mountain, at(top.X + corner[1], top.Z + corner[2]))
	end
	-- 천뢰번: 쇠 장대와 깃발
	local pole = top + Vector3.new(-18, 0, 10)
	block(
		mountain,
		"천뢰번",
		Vector3.new(0.8, 26, 0.8),
		CFrame.new(pole + Vector3.new(0, 12, 0)),
		C.stoneDark,
		Enum.Material.Metal
	)
	block(
		mountain,
		"깃발",
		Vector3.new(0.2, 8, 5),
		CFrame.new(pole + Vector3.new(0, 20, 2.6)),
		C.gold,
		Enum.Material.Fabric
	)
	stele(mountain, top + Vector3.new(16, 0, -6), "쇄천봉", Vector3.new(peak.x, 0, peak.z))
	-- 들머리 비석
	stele(mountain, at(-436, -138), "쇄천봉", Vector3.zero)

	-- 금신천뢰문 옛터: 무너진 문과 아홉 빛 띠 깃발
	local ruin = model(mountain, "금신천뢰문 옛터")
	local rpos = at(-660, -165)
	local floorTop = footing(ruin, rpos.X, rpos.Z, 34, 26, C.stone)
	for _, x in { -8, 8 } do
		local height = if x < 0 then 16 else 9
		block(
			ruin,
			"Pillar",
			Vector3.new(2.4, height, 2.4),
			CFrame.new(rpos.X + x, floorTop + height / 2, rpos.Z - 8),
			C.stoneDark,
			Enum.Material.Rock
		)
	end
	block(
		ruin,
		"FallenBeam",
		Vector3.new(18, 2, 2.4),
		CFrame.new(rpos.X + 2, floorTop + 1, rpos.Z - 2) * CFrame.Angles(0, 0.4, 0.1),
		C.stoneDark,
		Enum.Material.Rock
	)
	local belts = {
		Color3.fromRGB(200, 50, 40),
		Color3.fromRGB(230, 110, 50),
		Color3.fromRGB(230, 200, 60),
		Color3.fromRGB(70, 160, 80),
		Color3.fromRGB(60, 110, 200),
		Color3.fromRGB(60, 60, 140),
		Color3.fromRGB(130, 70, 170),
		C.gold,
		Color3.fromRGB(240, 240, 240),
	}
	for i, color in belts do
		local x = rpos.X - 14 + (i - 1) * 3.5
		block(
			ruin,
			"BannerPole",
			Vector3.new(0.3, 9, 0.3),
			CFrame.new(x, floorTop + 4.5, rpos.Z + 10),
			C.woodDark,
			Enum.Material.Wood
		)
		block(
			ruin,
			"Banner",
			Vector3.new(1.6, 4, 0.1),
			CFrame.new(x + 0.9, floorTop + 6.6, rpos.Z + 10),
			color,
			Enum.Material.Fabric
		)
	end
	signboard(ruin, Vector3.new(rpos.X + 14, floorTop, rpos.Z - 12), "금신천뢰문", Vector3.new(-560, 0, -110))

	-- 금 오행처: 금맥굴 입구 (바위 언덕 동쪽 면)
	local def = ELEMENT_SITES[4]
	local base = at(def.x, def.z)
	local mine = model(mountain, def.name)
	local mineFace = face(base, Vector3.new(def.x + 1, base.Y, def.z))
	for _, z in { -4, 4 } do
		block(mine, "Post", Vector3.new(1.2, 10, 1.2), mineFace * CFrame.new(z, 4, 6), C.wood, Enum.Material.Wood)
	end
	block(mine, "Lintel", Vector3.new(10, 1.2, 1.4), mineFace * CFrame.new(0, 9, 6), C.wood, Enum.Material.Wood)
	block(mine, "Dark", Vector3.new(7, 8, 1), mineFace * CFrame.new(0, 4, 7.5), Color3.fromRGB(20, 18, 18))
	block(
		mine,
		"Pillar",
		Vector3.new(3, 14, 3),
		CFrame.new(base + Vector3.new(0, 6, -7)),
		Color3.fromRGB(150, 156, 166),
		Enum.Material.DiamondPlate
	)
	block(
		mine,
		"Cap",
		Vector3.new(4.4, 1, 4.4),
		CFrame.new(base + Vector3.new(0, 13.5, -7)),
		Color3.fromRGB(190, 196, 206),
		Enum.Material.Metal
	)
	for k = 1, 5 do
		block(
			mine,
			"Ore",
			Vector3.new(0.6, rng(2, 5), 0.6),
			mineFace * CFrame.new(rng(-3, 3), rng(2, 8), 7.2 + k * 0.05) * CFrame.Angles(0, 0, rng(-0.6, 0.6)),
			C.gold,
			Enum.Material.Metal
		)
	end
	local board = block(
		mine,
		"Board",
		Vector3.new(6, 1.6, 0.3),
		mineFace * CFrame.new(0, 10.4, 5.4),
		C.lacquer,
		Enum.Material.Wood
	)
	engrave(board, "금맥굴", "Front")
end

local function buildSeoak(root: Instance, rng)
	local seoak = folder(root, "서악 마을")
	local cx, cz, y = Land.SEOAK.x, Land.SEOAK.z, Land.SEOAK.height
	local center = Vector3.new(cx, y, cz)
	for _, spot in { { 40, -30 }, { -42, -26 }, { -45, 30 }, { 30, 42 }, { -10, 50 } } do
		houseAt(
			seoak,
			cx + spot[1],
			cz + spot[2],
			center,
			rng(12, 15),
			rng(9, 12),
			if rng(0, 1) > 0.5 then C.red else C.roof
		)
	end
	-- 쌍선무 마당: 둘레에 등롱
	local square =
		block(seoak, "마당", Vector3.new(30, 2, 30), CFrame.new(cx, y - 0.8, cz), C.stone, Enum.Material.Slate)
	square:AddTag("Ground")
	for k = 0, 3 do
		local a = math.rad(k * 90 + 45)
		lantern(seoak, Vector3.new(cx + math.cos(a) * 16, y, cz + math.sin(a) * 16))
	end
	gateway(seoak, at(-490, -16), center, "서악 마을")

	-- 오공굴: 지네 요괴가 살던 동굴, 안에 중품 영맥
	local cave = model(seoak, "오공굴")
	local cpos = at(-588, 22)
	for k = 0, 6 do
		local a = math.rad(k * 40 + 100)
		rock(cave, cpos + Vector3.new(math.cos(a) * 16, 0, math.sin(a) * 16), rng(9, 13), rng)
	end
	block(
		cave,
		"Roof",
		Vector3.new(34, 4, 30),
		CFrame.new(cpos + Vector3.new(-6, 15, 0)) * CFrame.Angles(0, 0, 0.12),
		C.stoneDark,
		Enum.Material.Rock
	)
	vein(cave, "mid", cpos, 11)
	signboard(cave, at(-566, 34), "오공굴", center)
end

local function buildSnowfield(root: Instance, rng)
	local snow = folder(root, "서천 설원")
	for _ = 1, 30 do
		local x, z = rng(-1260, -1010), rng(-640, 400)
		if (x + 1180) ^ 2 + (z - 40) ^ 2 > 30 ^ 2 and (x + 1160) ^ 2 + (z - 60) ^ 2 > 20 ^ 2 then
			rock(snow, at(x, z, -1), rng(4, 10), rng, Color3.fromRGB(150, 156, 166))
		end
	end
	-- 백호 석상
	local base = at(-1180, 40)
	local tiger = model(snow, "백호")
	local t = base + Vector3.new(0, 0, -15)
	block(tiger, "Body", Vector3.new(4, 4, 10), CFrame.new(t + Vector3.new(0, 3, 0)), C.snow, Enum.Material.Marble)
	block(tiger, "Head", Vector3.new(4.4, 4, 4), CFrame.new(t + Vector3.new(0, 5.5, 6)), C.snow, Enum.Material.Marble)
	for _, leg in { { 1.4, 3.5 }, { -1.4, 3.5 }, { 1.4, -3.5 }, { -1.4, -3.5 } } do
		block(
			tiger,
			"Leg",
			Vector3.new(1.2, 3, 1.2),
			CFrame.new(t + Vector3.new(leg[1], 0.5, leg[2])),
			C.snow,
			Enum.Material.Marble
		)
	end
	for k = 0, 2 do
		block(tiger, "Stripe", Vector3.new(4.2, 0.4, 0.6), CFrame.new(t + Vector3.new(0, 5.1, -3 + k * 2.5)), C.basalt)
	end
end

-- 북방 대초원 ----------------------------------------------------------------------------

local function buildSteppe(root: Instance, rng)
	local steppe = folder(root, "북방 대초원")
	-- 유목민 천막
	local camp = at(140, -820)
	for k = 0, 4 do
		local a = math.rad(k * 72 + 10)
		local p = at(140 + math.cos(a) * 22, -820 + math.sin(a) * 22)
		local ger = model(steppe, "천막")
		disc(ger, "Floor", p + Vector3.new(0, -0.4, 0), 5.4, 1.6, C.wood, Enum.Material.WoodPlanks)
		local wall = block(
			ger,
			"Wall",
			Vector3.new(4.4, 10, 10),
			CFrame.new(p + Vector3.new(0, 2.2, 0)) * CFrame.Angles(0, 0, math.rad(90)),
			C.felt,
			Enum.Material.Fabric
		)
		wall.Shape = Enum.PartType.Cylinder
		disc(ger, "Roof", p + Vector3.new(0, 4.8, 0), 5.6, 0.8, C.felt, Enum.Material.Fabric)
		disc(ger, "Roof", p + Vector3.new(0, 5.6, 0), 3.8, 0.8, C.felt, Enum.Material.Fabric)
		disc(ger, "Crown", p + Vector3.new(0, 6.3, 0), 1.6, 0.6, C.wood, Enum.Material.Wood)
		block(
			ger,
			"Door",
			Vector3.new(2, 3, 0.4),
			face(p + Vector3.new(0, 1.5, 0), camp) * CFrame.new(0, 0, -5),
			C.red,
			Enum.Material.Wood
		)
	end
	vein(steppe, "low", at(180, -860, 0.3), 10)
	-- 창경천라진: 푸른 빛 바닥의 선돌 여덟
	local ring = model(steppe, "창경천라진")
	local rc = at(-200, -950)
	for k = 0, 7 do
		local a = math.rad(k * 45)
		local p = at(rc.X + math.cos(a) * 16, rc.Z + math.sin(a) * 16)
		block(
			ring,
			"Stone",
			Vector3.new(2.4, 8, 1.6),
			face(p + Vector3.new(0, 3, 0), rc),
			C.stoneDark,
			Enum.Material.Slate
		)
	end
	local glow =
		disc(ring, "Glow", rc + Vector3.new(0, 0.3, 0), 13, 0.2, Color3.fromRGB(90, 140, 255), Enum.Material.Neon)
	glow.Transparency = 0.7
	glow.CanCollide = false
	-- 흩어진 바위와 나무 몇 그루
	for _ = 1, 50 do
		local x, z = rng(-600, 560), rng(-1240, -640)
		local h = Land.height(x, z)
		local near = (x - 140) ^ 2 + (z + 820) ^ 2 < 50 ^ 2
			or (x + 200) ^ 2 + (z + 950) ^ 2 < 30 ^ 2
			or x * x + (z + 1180) ^ 2 < 40 ^ 2
			or Land.polyDist(x, z, Land.ROADS[1]) < 8
		if Land.water(x, z, h) == nil and not near then
			if rng(0, 1) > 0.5 then
				rock(steppe, Vector3.new(x, h - 1, z), rng(3, 7), rng)
			else
				tree(steppe, Vector3.new(x, h, z), rng, false)
			end
		end
	end
	-- 현무 석상: 거북 등에 뱀이 감겼다
	local base = at(0, -1180)
	local tortoise = model(steppe, "현무")
	local t = base + Vector3.new(0, 0, 14)
	block(
		tortoise,
		"Shell",
		Vector3.new(10, 4, 12),
		CFrame.new(t + Vector3.new(0, 2.5, 0)),
		C.basalt,
		Enum.Material.Slate
	)
	block(
		tortoise,
		"Head",
		Vector3.new(3, 2.4, 3.4),
		CFrame.new(t + Vector3.new(0, 2, -7.4)),
		C.basalt,
		Enum.Material.Slate
	)
	for k = 0, 9 do
		local a = math.rad(k * 40)
		local p = t + Vector3.new(math.cos(a) * 5.4, 4.4 + k * 0.3, math.sin(a) * 6.2)
		local q = t + Vector3.new(math.cos(a + 0.5) * 5.4, 4.4 + k * 0.3, math.sin(a + 0.5) * 6.2)
		block(tortoise, "Snake", Vector3.new(1.2, 1.2, 2.6), face(p, q), C.jade, Enum.Material.Slate)
	end
end

-- 벽라국: 천색성과 화구산 -----------------------------------------------------------------

local function buildByeokra(root: Instance, rng)
	local land = folder(root, "벽라국")
	local town = Land.TOWN
	local y = town.height
	local center = Vector3.new(town.x, y, town.z)
	-- 성벽 (서문과 동문을 비운다)
	local walls = model(land, "천색성 성벽")
	local half, wallH = 70, 14
	for _, side in { -1, 1 } do
		block(
			walls,
			"Wall",
			Vector3.new(half * 2, wallH, 3),
			CFrame.new(town.x, y + wallH / 2 - 1, town.z + side * half),
			C.sandstone,
			Enum.Material.Brick
		)
		for _, piece in { -1, 1 } do
			block(
				walls,
				"Wall",
				Vector3.new(3, wallH, 56),
				CFrame.new(town.x + side * half, y + wallH / 2 - 1, town.z + piece * 42),
				C.sandstone,
				Enum.Material.Brick
			)
		end
	end
	for _, corner in { { -1, -1 }, { 1, -1 }, { -1, 1 }, { 1, 1 } } do
		block(
			walls,
			"Tower",
			Vector3.new(8, wallH + 6, 8),
			CFrame.new(town.x + corner[1] * half, y + (wallH + 6) / 2 - 1, town.z + corner[2] * half),
			C.sandstoneDark,
			Enum.Material.Brick
		)
	end
	gateway(land, Vector3.new(town.x - half - 4, y, town.z), Vector3.new(0, y, town.z), "천색성", 16)
	-- 공방과 법기 가게
	for _, spot in { { -40, -40 }, { 0, -42 }, { 40, -40 }, { -40, 40 }, { 0, 42 }, { 40, 40 } } do
		house(
			land,
			face(Vector3.new(town.x + spot[1], y, town.z + spot[2]), center),
			rng(14, 18),
			rng(10, 12),
			if rng(0, 1) > 0.5 then C.red else C.roof,
			Color3.fromRGB(226, 206, 176)
		)
	end
	-- 추모 묘역
	for k = 0, 5 do
		local p = Vector3.new(town.x + 30 + (k % 3) * 6, y, town.z - 4 + (k // 3) * 8)
		block(
			land,
			"Grave",
			Vector3.new(1.6, 3, 0.6),
			CFrame.new(p + Vector3.new(0, 1, 0)),
			C.stone,
			Enum.Material.Slate
		)
	end
	signboard(land, Vector3.new(town.x + 36, y, town.z + 14), "추모비", center)

	-- 화 오행처: 용암 화로 (북쪽 성벽 안)
	local def = ELEMENT_SITES[2]
	local base = Vector3.new(def.x, y, def.z)
	local forge = model(land, def.name)
	block(
		forge,
		"Hearth",
		Vector3.new(10, 5, 4),
		CFrame.new(base + Vector3.new(0, 2, -8.5)),
		C.basalt,
		Enum.Material.Basalt
	)
	local fire = block(
		forge,
		"Lava",
		Vector3.new(7, 1, 2.6),
		CFrame.new(base + Vector3.new(0, 4.8, -8.5)),
		C.lava,
		Enum.Material.Neon
	)
	fire.CanCollide = false
	local flames = Instance.new("Fire")
	flames.Size = 6
	flames.Heat = 9
	flames.Parent = fire
	-- 용암 물길: 화구산 가장자리에서 북쪽 성벽 밖까지 땅을 따라 흘러내린다
	local from, to = Vector2.new(470, -245), Vector2.new(def.x, town.z - half - 4)
	local steps = math.floor((to - from).Magnitude / 8)
	for k = 0, steps - 1 do
		local p = from:Lerp(to, k / steps)
		local q = from:Lerp(to, (k + 1) / steps)
		local hp, hq = Land.height(p.X, p.Y), Land.height(q.X, q.Y)
		local a, b = Vector3.new(p.X, hp + 0.15, p.Y), Vector3.new(q.X, hq + 0.15, q.Y)
		-- 수평 방향은 face 로 (CFrame.new(p, q) 도 Lune 에서 Z 가 뒤집힌다), 기울기는 Angles 로
		local pitch = math.atan2(b.Y - a.Y, Vector2.new(b.X - a.X, b.Z - a.Z).Magnitude)
		local seg = block(
			forge,
			"Flow",
			Vector3.new(3, 0.5, (b - a).Magnitude + 0.6),
			face((a + b) / 2, b) * CFrame.Angles(pitch, 0, 0),
			C.lava,
			Enum.Material.Neon
		)
		seg.CanCollide = false
	end

	-- 화구산: 용암 못과 높은 연기
	local volcano = model(land, "화구산")
	local vc = Land.VOLCANO
	local lava = disc(volcano, "Lava", Vector3.new(vc.x, 126, vc.z), 34, 1, C.lava, Enum.Material.Neon)
	light(lava, C.lava, 60, 3)
	local plume = Instance.new("ParticleEmitter")
	plume.Color = ColorSequence.new(Color3.fromRGB(90, 86, 84), Color3.fromRGB(160, 156, 150))
	plume.Rate = 12
	plume.Lifetime = NumberRange.new(10, 16)
	plume.Speed = NumberRange.new(14, 22)
	plume.SpreadAngle = Vector2.new(12, 12)
	plume.EmissionDirection = Enum.NormalId.Right
	plume.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 18), NumberSequenceKeypoint.new(1, 60) })
	plume.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.4), NumberSequenceKeypoint.new(1, 1) })
	plume.Parent = lava
	stele(volcano, at(500, -150), "화구산", center)
end

-- 답천사막 ------------------------------------------------------------------------------

local function buildDesert(root: Instance, rng)
	local desert = folder(root, "답천사막")

	-- 답천대: 탁상 바위 위 천겁대
	local altar = model(desert, "천겁대")
	local mesa = Land.MESA
	local center = Vector3.new(mesa.x, mesa.height, mesa.z)
	disc(altar, "Floor", center + Vector3.new(0, 0.5, 0), 34, 1, C.sandstone, Enum.Material.Slate)
	disc(altar, "Inner", center + Vector3.new(0, 1.05, 0), 10, 0.1, C.sandstoneDark, Enum.Material.Slate)
	local dan = model(altar, "칠성단")
	block(
		dan,
		"Table",
		Vector3.new(6, 2.2, 3),
		CFrame.new(center + Vector3.new(0, 2.1, -6)),
		C.woodDark,
		Enum.Material.Wood
	)
	for i = 0, 6 do
		local a = math.rad(200 + i * 20)
		ball(
			dan,
			"Lamp",
			center + Vector3.new(math.cos(a) * 8, 1.6, math.sin(a) * 8),
			0.7,
			Color3.fromRGB(160, 200, 255),
			Enum.Material.Neon
		)
	end
	siteMarker(dan, "altar", center + Vector3.new(0, 1.2, 0), 10, "칠성단")
	-- 중령성국의 부서진 하늘 제단 기둥 여덟 (꼭대기에 뱀 머리)
	for i, trigram in World.TRIGRAMS do
		local a = math.rad(trigram.angle)
		local pos = center + Vector3.new(math.cos(a) * 31, 0, math.sin(a) * 31)
		local m = model(altar, trigram.name .. " 기둥")
		local height = 9 + (i * 37 % 6)
		local pillar = block(
			m,
			"Pillar",
			Vector3.new(2.6, height, 2.6),
			face(pos + Vector3.new(0, height / 2, 0), center + Vector3.new(0, height / 2, 0)),
			C.sandstoneDark,
			Enum.Material.Sandstone
		)
		engrave(pillar, trigram.name, "Front,Back,Left,Right", true, "gold")
		block(
			m,
			"SnakeHead",
			Vector3.new(2.4, 1.6, 3.6),
			face(pos + Vector3.new(0, height + 0.8, 0), center + Vector3.new(0, height + 0.8, 0))
				* CFrame.new(0, 0, -0.8),
			C.jade,
			Enum.Material.Slate
		)
		siteMarker(m, "tri_" .. i, pos + Vector3.new(0, 3, 0), 6, trigram.name)
	end
	stele(desert, at(704, -306), "답천대", Vector3.zero)

	-- 운제: 답천대에서 등선향으로 오르는 구름 계단
	local stair = model(desert, "운제")
	local hub = Vector2.new(811, -235)
	local startAngle = math.atan2(-55, -14)
	local count = 51
	for k = 0, count - 1 do
		local t = k / (count - 1)
		local a = startAngle + t * math.pi * 3
		-- 마지막 두 칸은 섬 가장자리 윗면(약 302~305)에 얹힌다
		local p = Vector3.new(hub.X + math.cos(a) * 60, 98 + t * 208, hub.Y + math.sin(a) * 60)
		local tangent = Vector3.new(-math.sin(a), 0, math.cos(a))
		local step = block(stair, "Step", Vector3.new(9, 1.6, 10), face(p, p + tangent), C.stone, Enum.Material.Slate)
		if k % 3 == 0 then
			local cloud = Instance.new("ParticleEmitter")
			cloud.Color = ColorSequence.new(Color3.fromRGB(250, 250, 255))
			cloud.Rate = 3
			cloud.Lifetime = NumberRange.new(3, 5)
			cloud.Speed = NumberRange.new(0.3, 0.8)
			cloud.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 4), NumberSequenceKeypoint.new(1, 7) })
			cloud.Transparency =
				NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 1) })
			cloud.Parent = step
		end
	end

	-- 중령성국 폐허: 부러진 기둥과 반쯤 묻힌 뱀 머리
	local ruins = model(desert, "중령성국 폐허")
	local rc = Vector3.new(Land.RUINS.x, Land.RUINS.height, Land.RUINS.z)
	for k = 0, 11 do
		local a = math.rad(k * 30 + 15)
		local p = rc + Vector3.new(math.cos(a) * 48, 0, math.sin(a) * 48)
		local height = rng(4, 16)
		block(
			ruins,
			"Column",
			Vector3.new(3, height, 3),
			CFrame.new(p + Vector3.new(0, height / 2 - 1, 0)),
			C.sandstone,
			Enum.Material.Sandstone
		)
		if height < 8 then
			block(
				ruins,
				"Drum",
				Vector3.new(3, 3, 3),
				CFrame.new(p + Vector3.new(rng(2, 5), 0.8, rng(-3, 3))) * CFrame.Angles(0, 0, math.rad(90)),
				C.sandstone,
				Enum.Material.Sandstone
			)
		end
	end
	local def = ELEMENT_SITES[3]
	local base = Vector3.new(def.x, Land.height(def.x, def.z), def.z)
	local head = model(ruins, def.name)
	local hcf = face(base + Vector3.new(0, 0, 16), base)
	block(head, "Skull", Vector3.new(16, 10, 18), hcf * CFrame.new(0, 3, 0), C.sandstoneDark, Enum.Material.Sandstone)
	block(
		head,
		"Jaw",
		Vector3.new(14, 3, 10),
		hcf * CFrame.new(0, -0.5, -10) * CFrame.Angles(-0.15, 0, 0),
		C.sandstoneDark,
		Enum.Material.Sandstone
	)
	for _, x in { -5, 5 } do
		ball(head, "Eye", (hcf * CFrame.new(x, 6, -8.6)).Position, 2.4, C.jade, Enum.Material.Neon)
	end
	-- 하늘에서 떨어진 양수진 비석 윗동 (북쪽 잔해밭)
	local debris = at(880, -760)
	local fallen = block(
		desert,
		"비석 윗동",
		Vector3.new(4, 12, 1.6),
		CFrame.new(debris + Vector3.new(0, 3, 0)) * CFrame.Angles(0.5, 0.4, 0.2),
		C.stone,
		Enum.Material.Slate
	)
	engrave(fallen, "금신자", "Front", true, "ink")

	-- 오아시스: 종려나무와 마른 용맥의 마지막 한 줄기
	for k = 0, 7 do
		local a = math.rad(k * 45 + 10)
		palm(desert, at(Land.OASIS.x + math.cos(a) * 24, Land.OASIS.z + math.sin(a) * 24, -0.5), rng)
	end
	vein(desert, "low", at(752, 210, 0.3), 10)

	-- 동쪽 성대 바위의 청룡 아치
	local arch = model(desert, "청룡 아치")
	local ac = at(1190, -40)
	for _, x in { -9, 9 } do
		block(
			arch,
			"Leg",
			Vector3.new(4, 16, 4),
			CFrame.new(ac + Vector3.new(x, 7, 15)),
			C.sandstone,
			Enum.Material.Sandstone
		)
	end
	block(
		arch,
		"Top",
		Vector3.new(24, 4, 5),
		CFrame.new(ac + Vector3.new(0, 16, 15)),
		C.sandstone,
		Enum.Material.Sandstone
	)
	for k = 0, 6 do
		block(
			arch,
			"Dragon",
			Vector3.new(2.6, 1.4, 1),
			CFrame.new(ac + Vector3.new(-9 + k * 3, 16 + math.sin(k) * 1.2, 12.4)),
			Color3.fromRGB(80, 200, 170),
			Enum.Material.Slate
		)
	end

	-- 모래 속 바위
	for _ = 1, 40 do
		local x, z = rng(640, 1260), rng(-1240, 600)
		local h = Land.height(x, z)
		local far = (x - mesa.x) ^ 2 + (z - mesa.z) ^ 2 > 110 ^ 2
			and (x - rc.X) ^ 2 + (z - rc.Z) ^ 2 > 110 ^ 2
			and (x - 1190) ^ 2 + (z + 40) ^ 2 > 40 ^ 2
			and (x - Land.OASIS.x) ^ 2 + (z - Land.OASIS.z) ^ 2 > 50 ^ 2
		if far and Land.water(x, z, h) == nil then
			rock(desert, Vector3.new(x, h - 1.5, z), rng(4, 12), rng, C.sandstoneDark)
		end
	end
end

-- 등선향 --------------------------------------------------------------------------------

local function buildIsland(root: Instance, rng)
	local island = folder(root, "등선향")
	local isle = Land.ISLAND
	local zone = block(island, "HerbZone", Vector3.new(220, 50, 220), CFrame.new(isle.x, 315, isle.z), C.grass)
	zone.Transparency = 1
	zone.CanCollide = false
	zone.CanQuery = false
	zone.CanTouch = false
	zone:SetAttribute("RareMult", 3)
	zone:AddTag("HerbZone")
	local clearings =
		{ { 875, -70, 22 }, { 900, -110, 24 }, { 840, -168, 18 }, { 960, -20, 20 }, { 830, -110, 18 }, { 846, -94, 8 } }
	local trees = folder(island, "Trees")
	local planted = 0
	for _ = 1, 200 do
		if planted >= 60 then
			break
		end
		local x, z = isle.x + rng(-140, 140), isle.z + rng(-140, 140)
		local _, top = Land.island(x, z)
		local clear = true
		for _, c in clearings do
			if (x - c[1]) ^ 2 + (z - c[2]) ^ 2 < c[3] ^ 2 then
				clear = false
			end
		end
		if top and top > 300 and clear then
			tree(trees, Vector3.new(x, top, z), rng, rng(0, 1) > 0.6)
			planted += 1
		end
	end
	vein(island, "top", at(875, -70, 0.3), 8)
	-- 승천문: 돌 고리 안에 비친 하늘 틈
	local gate = model(island, "승천문")
	local gc = at(900, -110)
	local gateFace = face(gc, gc + Vector3.new(-1, 0, 1))
	for k = 0, 19 do
		local a = math.rad(k * 18)
		block(
			gate,
			"Stone",
			Vector3.new(3.4, 4.6, 3),
			gateFace * CFrame.new(math.cos(a) * 13, 14 + math.sin(a) * 13, 0) * CFrame.Angles(0, 0, a),
			C.basalt,
			Enum.Material.Slate
		)
	end
	local rift = block(
		gate,
		"Rift",
		Vector3.new(0.4, 23, 23),
		gateFace * CFrame.new(0, 14, 0) * CFrame.Angles(0, math.rad(90), 0),
		Color3.fromRGB(200, 220, 255),
		Enum.Material.ForceField
	)
	rift.Shape = Enum.PartType.Cylinder
	rift.CanCollide = false
	light(rift, Color3.fromRGB(200, 220, 255), 40, 2)
	-- 양수진 사당과 경고비
	local shrineAt = at(830, -110)
	local shrineTop = footing(island, shrineAt.X, shrineAt.Z, 14, 12, C.stone)
	house(
		island,
		face(Vector3.new(shrineAt.X, shrineTop, shrineAt.Z), gc),
		12,
		10,
		C.red,
		Color3.fromRGB(236, 226, 206)
	)
	stele(island, at(846, -94), "금신자 경고비", gc)
	-- 시호 굴
	local den = model(island, "시호 굴")
	local dc = at(960, -20)
	for k = 0, 5 do
		local a = math.rad(k * 45 + 80)
		rock(den, dc + Vector3.new(math.cos(a) * 12, 0, math.sin(a) * 12), rng(7, 10), rng)
	end
	block(
		den,
		"Roof",
		Vector3.new(24, 3, 22),
		CFrame.new(dc + Vector3.new(4, 11, 0)) * CFrame.Angles(0.1, 0, 0.1),
		C.stoneDark,
		Enum.Material.Rock
	)
end

-- 남해 ----------------------------------------------------------------------------------

local function buildCoast(root: Instance, rng)
	local coast = folder(root, "남해")
	-- 수 오행처: 연하 하구 갯바위와 나무 잔교
	local def = ELEMENT_SITES[5]
	local base = Vector3.new(def.x, -20.2, def.z)
	local m = model(coast, def.name)
	local tide = block(
		m,
		"갯바위",
		Vector3.new(16, 6, 14),
		CFrame.new(base + Vector3.new(0, -2.6, 0)),
		C.stoneDark,
		Enum.Material.Slate
	)
	tide:AddTag("Ground")
	for k = 0, 4 do
		block(
			m,
			"Jetty",
			Vector3.new(4.2, 0.6, 4),
			CFrame.new(base + Vector3.new(-10 - k * 4, 0.3, 2)),
			C.wood,
			Enum.Material.WoodPlanks
		)
		block(
			m,
			"Post",
			Vector3.new(0.6, 6, 0.6),
			CFrame.new(base + Vector3.new(-10 - k * 4, -2.6, 4)),
			C.woodDark,
			Enum.Material.Wood
		)
	end

	-- 해룡 사당: 곶 끝의 정자, 중품 영맥
	local shrine = model(coast, "해룡 사당")
	local sc = at(-330, 735)
	for _, corner in { { 10, 10 }, { -10, 10 }, { 10, -10 }, { -10, -10 } } do
		block(
			shrine,
			"Pillar",
			Vector3.new(1.4, 13, 1.4),
			CFrame.new(sc + Vector3.new(corner[1], 5, corner[2])),
			C.red,
			Enum.Material.Wood
		)
	end
	block(shrine, "Roof", Vector3.new(26, 1.2, 26), CFrame.new(sc + Vector3.new(0, 11.5, 0)), C.roof)
	block(shrine, "Ridge", Vector3.new(16, 2, 16), CFrame.new(sc + Vector3.new(0, 13, 0)), C.roof)
	vein(shrine, "mid", sc + Vector3.new(0, 0.3, 0), 8)
	local lintel = block(
		shrine,
		"Lintel",
		Vector3.new(8, 1.6, 0.3),
		face(sc + Vector3.new(0, 9.6, -10.8), sc + Vector3.new(0, 9.6, -40)),
		C.lacquer,
		Enum.Material.Wood
	)
	engrave(lintel, "해룡 사당", "Front,Back")

	-- 난파한 유령선
	local wreck = model(coast, "난파선")
	local tilt = CFrame.new(520, -24, 780) * CFrame.Angles(0.12, 0.6, 0.25)
	block(wreck, "Hull", Vector3.new(10, 5, 34), tilt, Color3.fromRGB(46, 40, 38), Enum.Material.WoodPlanks)
	block(wreck, "Deck", Vector3.new(9, 0.6, 26), tilt * CFrame.new(0, 2.6, -2), C.woodDark, Enum.Material.WoodPlanks)
	block(
		wreck,
		"Mast",
		Vector3.new(1, 18, 1),
		tilt * CFrame.new(0, 10, 4) * CFrame.Angles(0.3, 0, 0.2),
		C.woodDark,
		Enum.Material.Wood
	)
	local ghost = block(
		wreck,
		"Lantern",
		Vector3.new(1.2, 1.6, 1.2),
		tilt * CFrame.new(0, 4, -12),
		Color3.fromRGB(120, 255, 200),
		Enum.Material.Neon
	)
	light(ghost, Color3.fromRGB(120, 255, 200), 24, 1.5)

	-- 남천도 해룡족 천문대 터: 별 지도 바닥과 혼천의 고리, 밤에 보이는 등대 빛
	local isle = Land.SOUTH_ISLE
	local oc = at(isle.x, isle.z)
	local observatory = model(coast, "천문대")
	disc(observatory, "Floor", oc + Vector3.new(0, 0.2, 0), 20, 1, Color3.fromRGB(34, 40, 70), Enum.Material.Slate)
	for _ = 1, 24 do
		local a, r = rng(0, math.pi * 2), rng(3, 18)
		block(
			observatory,
			"StarMark",
			Vector3.new(0.6, 0.12, 0.6),
			CFrame.new(oc + Vector3.new(math.cos(a) * r, 0.75, math.sin(a) * r)),
			Color3.fromRGB(200, 220, 255),
			Enum.Material.Neon
		)
	end
	local ringCenter = oc + Vector3.new(0, 12, 14)
	for ringIndex, tiltAngle in { 0, 60, 120 } do
		for k = 0, 17 do
			local a = math.rad(k * 20)
			block(
				observatory,
				"Ring" .. ringIndex,
				Vector3.new(0.6, 0.6, 2.2),
				CFrame.new(ringCenter)
					* CFrame.Angles(0, math.rad(tiltAngle), 0)
					* CFrame.new(math.cos(a) * 7, math.sin(a) * 7, 0)
					* CFrame.Angles(0, 0, a),
				C.gold,
				Enum.Material.Metal
			)
		end
	end
	block(
		observatory,
		"Stand",
		Vector3.new(1.2, 5, 1.2),
		CFrame.new(ringCenter - Vector3.new(0, 9.5, 0)),
		C.stoneDark,
		Enum.Material.Metal
	)
	local beacon = ball(observatory, "Beacon", ringCenter, 2.4, Color3.fromRGB(255, 220, 160), Enum.Material.Neon)
	light(beacon, Color3.fromRGB(255, 220, 160), 60, 2)
	local lintelStone = block(
		observatory,
		"Lintel",
		Vector3.new(8, 1.6, 0.6),
		face(oc + Vector3.new(0, 4, -21), oc + Vector3.new(0, 4, -60)),
		C.stone,
		Enum.Material.Slate
	)
	for _, x in { -4.4, 4.4 } do
		block(
			observatory,
			"Post",
			Vector3.new(1.2, 6, 1.2),
			CFrame.new(oc + Vector3.new(x, 1.5, -21)),
			C.stone,
			Enum.Material.Slate
		)
	end
	engrave(lintelStone, "천문대", "Front,Back", false, "ink")
end

-- 사방 성대 -----------------------------------------------------------------------------

local function buildStarAltars(root: Instance)
	local altars = folder(root, "성대")
	for _, def in STAR_ALTARS do
		local m = model(altars, def.name)
		local top = footing(m, def.x, def.z, 18, 18, C.stoneDark)
		local base = Vector3.new(def.x, top, def.z)
		disc(m, "Floor", base + Vector3.new(0, 0.1, 0), 9, 0.8, C.stoneDark, Enum.Material.Slate)
		for k = 0, 3 do
			local a = math.rad(45 + k * 90)
			block(
				m,
				"Post",
				Vector3.new(1.2, 7, 1.2),
				CFrame.new(base + Vector3.new(math.cos(a) * 7, 3.5, math.sin(a) * 7)),
				C.stone,
				Enum.Material.Rock
			)
		end
		local orb = ball(m, "Star", base + Vector3.new(0, 11, 0), 2.6, def.color, Enum.Material.Neon)
		orb.CanCollide = false
		light(orb, def.color, 24, 2)
		siteMarker(m, def.id, base + Vector3.new(0, 0.5, 0), 8)
		local toward = Vector3.new(-def.x, 0, -def.z).Unit
		local stonePos = base + toward * 12
		stele(
			m,
			Vector3.new(stonePos.X, Land.surface(stonePos.X, stonePos.Z), stonePos.Z),
			def.carve,
			Vector3.zero,
			def.color:Lerp(C.stone, 0.6)
		)
	end
end

-- 오행처 받침 (곁의 모양은 땅마다 위에서 지었다) ----------------------------------------------

local function buildElementDais(root: Instance)
	local sites = folder(root, "오행처")
	for _, def in ELEMENT_SITES do
		local m = model(sites, def.name .. " 자리")
		local base = if def.id == "el_water"
			then Vector3.new(def.x, -20.2, def.z)
			elseif def.id == "el_fire" then Vector3.new(def.x, Land.TOWN.height, def.z)
			elseif def.id == "el_earth" then atGround(def.x, def.z) -- 등선향 밑 폐허
			else at(def.x, def.z)
		disc(m, "Dais", base + Vector3.new(0, 0.3, 0), 6, 0.6, C.stone, Enum.Material.Slate)
		disc(m, "DaisFoot", base + Vector3.new(0, -1.2, 0), 6, 2.4, C.stoneDark, Enum.Material.Slate)
		local orb = ball(m, "Orb", base + Vector3.new(0, 4, 0), 2, def.color, Enum.Material.Neon)
		orb.CanCollide = false
		light(orb, def.color, 14, 1.5)
		motes(orb, def.color, 6)
		siteMarker(m, def.id, base + Vector3.new(0, 0.6, 0), 7)
		local toward = Vector3.new(-def.x, 0, -def.z).Unit
		local stonePos = base + toward * 9
		local ground = if def.id == "el_water" or def.id == "el_fire"
			then Vector3.new(stonePos.X, base.Y, stonePos.Z)
			elseif def.id == "el_earth" then atGround(stonePos.X, stonePos.Z)
			else Vector3.new(stonePos.X, Land.surface(stonePos.X, stonePos.Z), stonePos.Z)
		stele(m, ground, def.name, Vector3.zero, def.color:Lerp(C.stone, 0.7))
	end
end

-- 마을 노인이 앉는 자리. 사람은 서버가 띄울 때 카탈로그 옷을 입혀 앉힌다(Villagers.luau).
-- 여기서는 앉을 돌, 앉는 자리(Seat, 속성 NpcSeat), 과업 자리, 노인마다 곁의 살림만 짓는다.
local function buildElders(root: Instance)
	local elders = folder(root, "노인")
	for _, def in ELDERS do
		local m = model(elders, def.name)
		local base = def.position
		local look = face(base, Vector3.new(def.faces.X, base.Y, def.faces.Z))
		block(m, "Stool", Vector3.new(3, 1.6, 3), look * CFrame.new(0, 0.8, 0), C.stone, Enum.Material.Slate)
		local seat = Instance.new("Seat")
		seat.Name = "자리"
		seat.Anchored = true
		seat.Size = Vector3.new(2, 0.2, 2)
		seat.CFrame = look * CFrame.new(0, 1.7, 0)
		seat.Transparency = 1
		seat.CanCollide = false
		seat:SetAttribute("NpcSeat", def.id)
		seat.Parent = m

		if def.id == "elder_1" then
			-- 말리는 약초 시렁과 약초 바구니
			for _, x in { -2.2, 2.2 } do
				block(m, "RackPost", Vector3.new(0.3, 4, 0.3), look * CFrame.new(x, 2, 2.6), C.wood, Enum.Material.Wood)
			end
			block(
				m,
				"RackBar",
				Vector3.new(4.8, 0.25, 0.25),
				look * CFrame.new(0, 3.8, 2.6),
				C.wood,
				Enum.Material.Wood
			)
			for i = -2, 2 do
				block(
					m,
					"Herb",
					Vector3.new(0.5, 1, 0.3),
					look * CFrame.new(i * 0.9, 3.2, 2.6),
					C.leafLight,
					Enum.Material.Grass
				)
			end
			local basket = block(
				m,
				"Basket",
				Vector3.new(1.6, 1, 1.6),
				look * CFrame.new(2.4, 0.5, -0.6) * CFrame.Angles(0, 0, math.rad(90)),
				Color3.fromRGB(176, 140, 86),
				Enum.Material.Fabric
			)
			basket.Shape = Enum.PartType.Cylinder
			block(
				m,
				"Herbs",
				Vector3.new(1.2, 0.4, 1.2),
				look * CFrame.new(2.4, 1.1, -0.6),
				C.leaf,
				Enum.Material.Grass
			)
		elseif def.id == "elder_2" then
			-- 쇠막대 몇 개와 물통
			for i = 0, 2 do
				block(
					m,
					"Bar",
					Vector3.new(0.3, 0.3, 3),
					look * CFrame.new(-2.2 + i * 0.4, 0.2, 0.4),
					C.stoneDark,
					Enum.Material.Metal
				)
			end
			local bucket = block(
				m,
				"Bucket",
				Vector3.new(1.4, 1.2, 1.2),
				look * CFrame.new(2.3, 0.7, 0.4) * CFrame.Angles(0, 0, math.rad(90)),
				C.woodDark,
				Enum.Material.Wood
			)
			bucket.Shape = Enum.PartType.Cylinder
		elseif def.id == "elder_3" then
			-- 강가에 매어 둔 작은 나룻배 (수면 -1)
			local boat = model(m, "나룻배")
			local boatCf = CFrame.new(-95, -0.9, 26) * CFrame.Angles(0, math.rad(90), 0)
			block(boat, "Hull", Vector3.new(3, 0.6, 9), boatCf, C.wood, Enum.Material.WoodPlanks)
			for _, x in { -1.4, 1.4 } do
				block(
					boat,
					"Side",
					Vector3.new(0.3, 0.8, 9),
					boatCf * CFrame.new(x, 0.6, 0),
					C.woodDark,
					Enum.Material.WoodPlanks
				)
			end
			block(
				boat,
				"Seat",
				Vector3.new(2.6, 0.3, 0.8),
				boatCf * CFrame.new(0, 0.5, 1.5),
				C.woodDark,
				Enum.Material.Wood
			)
			block(m, "Post", Vector3.new(0.5, 7, 0.5), CFrame.new(-87.5, -1.5, 26), C.woodDark, Enum.Material.Wood)
		end

		siteMarker(m, def.id, base + Vector3.new(0, 3, 0), 7, def.name)
	end
end

-- 세계순력: 세상 끝을 두른 힘의 벽
local function buildWorldEdge(root: Instance)
	local edge = folder(root, "세계순력")
	local span = Land.EDGE * 2 + 8
	for _, side in { Vector3.new(1, 0, 0), Vector3.new(-1, 0, 0), Vector3.new(0, 0, 1), Vector3.new(0, 0, -1) } do
		local wall = block(
			edge,
			"Wall",
			Vector3.new(if side.X ~= 0 then 4 else span, 820, if side.Z ~= 0 then 4 else span),
			CFrame.new(side * Land.EDGE + Vector3.new(0, 346, 0)),
			Color3.fromRGB(140, 190, 255),
			Enum.Material.ForceField
		)
		wall.CastShadow = false
	end
end

local function setupLighting(lighting: Instance)
	lighting.ClockTime = 15.5
	lighting.Brightness = 2.2
	lighting.Ambient = Color3.fromRGB(90, 90, 100)
	lighting.OutdoorAmbient = Color3.fromRGB(135, 135, 150)
	lighting.GlobalShadows = true

	local atmosphere = lighting:FindFirstChildOfClass("Atmosphere")
	if not atmosphere then
		atmosphere = Instance.new("Atmosphere")
		atmosphere.Parent = lighting
	end
	atmosphere.Density = 0.38
	atmosphere.Offset = 0.05
	atmosphere.Color = Color3.fromRGB(205, 215, 225)
	atmosphere.Decay = Color3.fromRGB(110, 118, 135)
	atmosphere.Glare = 0.2
	atmosphere.Haze = 1.6
	if not lighting:FindFirstChildOfClass("BloomEffect") then
		local bloom = Instance.new("BloomEffect")
		bloom.Intensity = 0.6
		bloom.Size = 24
		bloom.Threshold = 1.4
		bloom.Parent = lighting
	end
end

function World.build(workspaceRoot: Instance, lighting: Instance): Model
	local rng = makeRng(20261003)
	local root = Instance.new("Model")
	root.Name = World.MODEL_NAME

	buildVillage(root, rng)
	buildRiver(root)
	buildForest(root, rng)
	buildMountain(root, rng)
	buildSeoak(root, rng)
	buildSnowfield(root, rng)
	buildSteppe(root, rng)
	buildByeokra(root, rng)
	buildDesert(root, rng)
	buildIsland(root, rng)
	buildCoast(root, rng)
	buildStarAltars(root)
	buildElementDais(root)
	buildElders(root)
	buildWorldEdge(root)

	local pads = folder(root, "전송진")
	for order, def in WAYPOINTS do
		waypoint(pads, def, order)
	end

	local spots = folder(root, "비급자리")
	for _, position in MANUAL_SPOTS do
		local spot = block(spots, "ManualSpot", Vector3.new(2, 0.2, 2), CFrame.new(position), C.stone)
		spot.Transparency = 1
		spot.CanCollide = false
		spot.CanQuery = false
		spot.CanTouch = false
		spot:AddTag("ManualSpot")
	end

	setupLighting(lighting)

	root.Parent = workspaceRoot
	return root
end

return World
