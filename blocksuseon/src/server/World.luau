-- 연국(連國) 맵을 블록으로 짓는다.
--
-- 플레이스 파일에는 tools/bake_place.luau 가 이 함수로 미리 지은 맵이 들어가고,
-- 게임 서버는 Workspace 에 "연국" 이 없을 때만 이걸 다시 부른다.
-- 다른 시스템은 이름이 아니라 태그로 맵을 찾는다:
--   Ground        - 영초가 돋는 바닥
--   Vein          - 영맥 (속성 VeinId, Radius)
--   HerbZone      - 영초가 돋는 범위
--   ManualSpot    - 비급이 나타나는 자리
-- Studio 에서 맵을 직접 고쳐도 태그만 유지하면 그대로 동작한다.

local World = {}

World.MODEL_NAME = "연국"

-- 비급이 나타날 수 있는 자리 (바닥 높이까지 맞춘 좌표).
-- 영산 층계 모서리, 숲, 마을 바깥, 강가, 천겁대, 맵 가장자리에 흩어 둔다.
local MANUAL_SPOTS = {
	-- 영산: 중심 (0, -250), i 층 윗면 높이 (i+1)*4, 모서리는 비탈이 없는 자리
	Vector3.new(78.75, 8, -171.25),
	Vector3.new(-63.75, 16, -313.75),
	Vector3.new(48.75, 24, -298.75),
	Vector3.new(-33.75, 32, -216.25),
	Vector3.new(0, 40, -232),
	-- 영초숲
	Vector3.new(-150, 0, -120),
	Vector3.new(-235, 0, -40),
	Vector3.new(-250, 0, 150),
	Vector3.new(-160, 0, 40),
	-- 마을 바깥과 강가
	Vector3.new(0, 0, 80),
	Vector3.new(-62, 0, -58),
	Vector3.new(96, 0, 10),
	Vector3.new(-80, 0, 120),
	-- 천겁대 위
	Vector3.new(191, 1, -137.7),
	-- 맵 가장자리
	Vector3.new(260, 0, 180),
	Vector3.new(-310, 0, -260),
	Vector3.new(150, 0, 250),
	Vector3.new(300, 0, -300),
}
World.MANUAL_SPOTS = MANUAL_SPOTS

-- 매번 같은 지형이 나오도록 고정 시드 난수 (Park–Miller)
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
	roof = Color3.fromRGB(52, 74, 86),
	red = Color3.fromRGB(168, 46, 40),
	leaf = Color3.fromRGB(66, 122, 70),
	leafLight = Color3.fromRGB(96, 150, 82),
	blossom = Color3.fromRGB(240, 172, 196),
	water = Color3.fromRGB(80, 150, 200),
	snow = Color3.fromRGB(240, 244, 248),
	dirt = Color3.fromRGB(150, 116, 82),
}

local VEIN_COLORS = {
	low = Color3.fromRGB(110, 230, 220),
	mid = Color3.fromRGB(110, 150, 255),
	high = Color3.fromRGB(255, 205, 100),
}

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

local function sign(parent: Instance, position: Vector3, title: string, subtitle: string?, color: Color3?)
	local anchor = block(parent, "표지", Vector3.new(1, 1, 1), CFrame.new(position), C.stone)
	anchor.Transparency = 1
	anchor.CanCollide = false
	anchor.CanQuery = false
	anchor.CanTouch = false

	local gui = Instance.new("BillboardGui")
	gui.Name = "Label"
	gui.Size = UDim2.fromOffset(240, 64)
	gui.MaxDistance = 160
	gui.LightInfluence = 0
	gui.Parent = anchor

	local titleLabel = Instance.new("TextLabel")
	titleLabel.Name = "Title"
	titleLabel.BackgroundTransparency = 1
	titleLabel.Size = UDim2.new(1, 0, 0.6, 0)
	titleLabel.FontFace = Font.fromEnum(Enum.Font.GothamBold)
	titleLabel.TextScaled = true
	titleLabel.Text = title
	titleLabel.TextColor3 = color or Color3.fromRGB(255, 244, 220)
	titleLabel.TextStrokeTransparency = 0.4
	titleLabel.Parent = gui

	if subtitle then
		local sub = Instance.new("TextLabel")
		sub.Name = "Subtitle"
		sub.BackgroundTransparency = 1
		sub.Position = UDim2.new(0, 0, 0.6, 0)
		sub.Size = UDim2.new(1, 0, 0.4, 0)
		sub.FontFace = Font.fromEnum(Enum.Font.Gotham)
		sub.TextScaled = true
		sub.Text = subtitle
		sub.TextColor3 = Color3.fromRGB(230, 230, 230)
		sub.TextStrokeTransparency = 0.5
		sub.Parent = gui
	end
end

local function lantern(parent: Instance, position: Vector3)
	local m = model(parent, "등롱")
	block(
		m,
		"Post",
		Vector3.new(0.8, 7, 0.8),
		CFrame.new(position + Vector3.new(0, 3.5, 0)),
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
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 170, 120)
	light.Range = 16
	light.Brightness = 1.5
	light.Parent = lamp
end

local function vein(parent: Instance, id: string, center: Vector3, radius: number)
	local color = VEIN_COLORS[id]
	local m = model(parent, "영맥_" .. id)
	disc(m, "Rim", center + Vector3.new(0, 0.3, 0), radius + 1.5, 0.6, C.stoneDark, Enum.Material.Slate)
	local pool = disc(m, "Pool", center + Vector3.new(0, 0.7, 0), radius, 0.4, color, Enum.Material.Neon)
	pool.Transparency = 0.35
	pool.CanCollide = false
	pool:SetAttribute("VeinId", id)
	pool:SetAttribute("Radius", radius)
	pool:AddTag("Vein")

	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = radius * 2.5
	light.Brightness = 2
	light.Parent = pool

	local motes = Instance.new("ParticleEmitter")
	motes.Name = "Motes"
	motes.Color = ColorSequence.new(color)
	motes.LightEmission = 1
	motes.Rate = radius * 1.5
	motes.Lifetime = NumberRange.new(2, 3.5)
	motes.Speed = NumberRange.new(2, 4)
	motes.SpreadAngle = Vector2.new(15, 15)
	motes.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.4),
		NumberSequenceKeypoint.new(1, 0),
	})
	motes.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.2),
		NumberSequenceKeypoint.new(1, 1),
	})
	-- 원판이 Z 로 누워 있어서 파티클이 위로 솟도록 방향을 옆(Right)으로 준다
	motes.EmissionDirection = Enum.NormalId.Right
	motes.Shape = Enum.ParticleEmitterShape.Cylinder
	motes.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
	motes.Parent = pool
end

-- 정면(LookVector)을 바라보는 기와집 한 채
local function house(parent: Instance, cf: CFrame, width: number, depth: number, roofColor: Color3)
	local m = model(parent, "민가")
	local wallH = 9
	block(m, "Base", Vector3.new(width + 2, 1, depth + 2), cf * CFrame.new(0, 0.5, 0), C.stone, Enum.Material.Slate)
	block(m, "Walls", Vector3.new(width, wallH, depth), cf * CFrame.new(0, 1 + wallH / 2, 0), C.plaster)
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
end

local function tree(parent: Instance, base: Vector3, rng, blossom: boolean)
	local m = model(parent, if blossom then "벚나무" else "나무")
	local height = rng(8, 14)
	local trunkW = rng(1.4, 2.2)
	block(
		m,
		"Trunk",
		Vector3.new(trunkW, height, trunkW),
		CFrame.new(base + Vector3.new(0, height / 2, 0)),
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

local function path(parent: Instance, from: Vector3, to: Vector3, width: number)
	local flat = Vector3.new(to.X - from.X, 0, to.Z - from.Z)
	local mid = (from + to) / 2
	block(
		parent,
		"길",
		Vector3.new(width, 0.4, flat.Magnitude),
		CFrame.lookAt(Vector3.new(mid.X, 0.2, mid.Z), Vector3.new(to.X, 0.2, to.Z)),
		C.stone,
		Enum.Material.Cobblestone
	)
end

local function buildVillage(root: Instance, rng)
	local village = folder(root, "마을")
	block(village, "광장", Vector3.new(64, 1, 64), CFrame.new(0, 0, 0), C.stone, Enum.Material.Slate)
	vein(village, "low", Vector3.new(0, 0.5, 0), 12)
	sign(village, Vector3.new(0, 10, 0), "하품 영맥", "누구나, 흡수 ×1.5", VEIN_COLORS.low)

	for _, angle in { 30, 70, 110, 150, 215, 250 } do
		local rad = math.rad(angle)
		local pos = Vector3.new(math.cos(rad) * 54, 0, math.sin(rad) * 54)
		local cf = CFrame.lookAt(pos, Vector3.new(0, 0, 0))
		local roofColor = if rng(0, 1) > 0.6 then C.red else C.roof
		house(village, cf, rng(13, 17), rng(10, 13), roofColor)
	end

	for _, corner in
		{ Vector3.new(30, 0, 30), Vector3.new(-30, 0, 30), Vector3.new(30, 0, -30), Vector3.new(-30, 0, -30) }
	do
		lantern(village, corner + Vector3.new(0, 0.5, 0))
	end

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

	sign(village, Vector3.new(0, 14, 40), "연국 (連國)", "블록수선전", Color3.fromRGB(255, 220, 150))
end

local function buildForest(root: Instance, rng)
	local forest = folder(root, "영초숲")
	local center = Vector3.new(-190, 0, 0)
	local size = Vector3.new(170, 1, 340)

	local zone = block(forest, "HerbZone", size, CFrame.new(center + Vector3.new(0, 0.5, 0)), C.grass)
	zone.Transparency = 1
	zone.CanCollide = false
	zone.CanQuery = false
	zone.CanTouch = false
	zone:AddTag("HerbZone")

	local trees = folder(forest, "Trees")
	for _ = 1, 80 do
		local x = rng(center.X - size.X / 2, center.X + size.X / 2)
		local z = rng(center.Z - size.Z / 2, center.Z + size.Z / 2)
		-- 중품 영맥 자리와 다리 앞은 비워 둔다
		local nearVein = (Vector3.new(x, 0, z) - Vector3.new(-200, 0, 100)).Magnitude < 22
		local nearBridge = x > -140 and math.abs(z) < 8
		local nearManual = false
		for _, spot in MANUAL_SPOTS do
			if (Vector3.new(x, 0, z) - Vector3.new(spot.X, 0, spot.Z)).Magnitude < 9 then
				nearManual = true
			end
		end
		if not nearVein and not nearBridge and not nearManual then
			tree(trees, Vector3.new(x, 0, z), rng, rng(0, 1) > 0.8)
		end
	end

	vein(forest, "mid", Vector3.new(-200, 0, 100), 11)
	sign(forest, Vector3.new(-200, 10, 100), "중품 영맥", "축기기부터, 흡수 ×2.5", VEIN_COLORS.mid)
	sign(
		forest,
		Vector3.new(-115, 12, 0),
		"영초숲",
		"영초와 천년영지가 돋는 숲",
		Color3.fromRGB(170, 240, 170)
	)

	-- 마을과 숲 사이 개울과 다리
	local river =
		block(root, "개울", Vector3.new(16, 0.3, 760), CFrame.new(-95, 0.15, 0), C.water, Enum.Material.Glass)
	river.Transparency = 0.25
	river.CanCollide = false
	river.CanQuery = false
	local bridge = model(root, "다리")
	block(bridge, "Deck", Vector3.new(22, 1, 10), CFrame.new(-95, 0.9, 0), C.wood, Enum.Material.WoodPlanks)
	for _, z in { -4.6, 4.6 } do
		block(bridge, "Rail", Vector3.new(22, 1.6, 0.6), CFrame.new(-95, 2.2, z), C.red)
	end
end

local function buildMountain(root: Instance)
	local mountain = folder(root, "영산")
	local center = Vector3.new(0, 0, -250)
	local layers = 10
	local layerH = 4
	local baseSize = 180
	local shrink = 15
	local sides = { Vector3.new(0, 0, 1), Vector3.new(1, 0, 0), Vector3.new(0, 0, -1), Vector3.new(-1, 0, 0) }

	for i = 0, layers - 1 do
		local size = baseSize - i * shrink
		local color = if i >= layers - 2 then C.snow elseif i % 2 == 0 then C.grassDark else C.stoneDark
		local material = if i >= layers - 2
			then Enum.Material.Snow
			elseif i % 2 == 0 then Enum.Material.Grass
			else Enum.Material.Rock
		block(
			mountain,
			"Terrace",
			Vector3.new(size, layerH, size),
			CFrame.new(center + Vector3.new(0, i * layerH + layerH / 2, 0)),
			color,
			material
		)

		-- 한 층 아래에서 이 층으로 올라오는 비탈. 층마다 방향을 돌려 산을 감아 오르게 한다.
		if i > 0 then
			local side = sides[(i - 1) % 4 + 1]
			local depth = shrink / 2
			local pos = center + side * (size / 2 + depth / 2) + Vector3.new(0, i * layerH + layerH / 2, 0)
			wedge(
				mountain,
				Vector3.new(10, layerH, depth),
				CFrame.lookAt(pos, pos + side),
				C.stone,
				Enum.Material.Cobblestone
			)
		end
	end

	local top = center + Vector3.new(0, layers * layerH, 0)
	vein(mountain, "high", top, 9)
	sign(mountain, top + Vector3.new(0, 11, 0), "상품 영맥", "결단기부터, 흡수 ×4", VEIN_COLORS.high)
	for _, corner in
		{ Vector3.new(13, 0, 13), Vector3.new(-13, 0, 13), Vector3.new(13, 0, -13), Vector3.new(-13, 0, -13) }
	do
		lantern(mountain, top + corner)
	end
	sign(
		mountain,
		center + Vector3.new(0, 10, baseSize / 2 + 8),
		"영산",
		"비탈을 따라 산을 감아 오르라",
		Color3.fromRGB(200, 220, 255)
	)
end

local function buildTribulationAltar(root: Instance)
	local altar = folder(root, "천겁대")
	local center = Vector3.new(200, 0, -160)
	disc(altar, "Floor", center + Vector3.new(0, 0.5, 0), 34, 1, C.stone, Enum.Material.Slate)
	disc(altar, "Inner", center + Vector3.new(0, 1.05, 0), 10, 0.1, C.stoneDark, Enum.Material.Slate)
	for i = 1, 8 do
		local a = math.rad(i * 45)
		local pos = center + Vector3.new(math.cos(a) * 31, 0, math.sin(a) * 31)
		block(
			altar,
			"Pillar",
			Vector3.new(2.4, 12, 2.4),
			CFrame.new(pos + Vector3.new(0, 6, 0)),
			C.stoneDark,
			Enum.Material.Rock
		)
	end
	sign(
		altar,
		center + Vector3.new(0, 14, 0),
		"천겁대",
		"탁 트인 곳에서 겁을 맞이하라",
		Color3.fromRGB(255, 160, 160)
	)
end

local function setupLighting(lighting: Instance)
	lighting.ClockTime = 15.5
	lighting.Brightness = 2.2
	lighting.Ambient = Color3.fromRGB(90, 90, 100)
	lighting.OutdoorAmbient = Color3.fromRGB(135, 135, 150)
	lighting.GlobalShadows = true

	if not lighting:FindFirstChildOfClass("Atmosphere") then
		local atmosphere = Instance.new("Atmosphere")
		atmosphere.Density = 0.32
		atmosphere.Offset = 0.2
		atmosphere.Color = Color3.fromRGB(205, 215, 225)
		atmosphere.Decay = Color3.fromRGB(110, 118, 135)
		atmosphere.Glare = 0.2
		atmosphere.Haze = 1.4
		atmosphere.Parent = lighting
	end
	if not lighting:FindFirstChildOfClass("BloomEffect") then
		local bloom = Instance.new("BloomEffect")
		bloom.Intensity = 0.6
		bloom.Size = 24
		bloom.Threshold = 1.4
		bloom.Parent = lighting
	end
end

function World.build(workspaceRoot: Instance, lighting: Instance): Model
	local rng = makeRng(20261002)
	local root = Instance.new("Model")
	root.Name = World.MODEL_NAME

	local ground = block(root, "땅", Vector3.new(760, 4, 760), CFrame.new(0, -2, 0), C.grass, Enum.Material.Grass)
	ground:AddTag("Ground")

	-- 맵 밖으로 나가지 못하게 막는 투명 벽
	for _, side in { Vector3.new(1, 0, 0), Vector3.new(-1, 0, 0), Vector3.new(0, 0, 1), Vector3.new(0, 0, -1) } do
		local wall = block(
			root,
			"경계",
			Vector3.new(if side.X ~= 0 then 4 else 760, 300, if side.Z ~= 0 then 4 else 760),
			CFrame.new(side * 380 + Vector3.new(0, 150, 0)),
			C.stone
		)
		wall.Transparency = 1
	end

	local paths = folder(root, "길")
	path(paths, Vector3.new(0, 0, -32), Vector3.new(0, 0, -158), 8)
	path(paths, Vector3.new(-32, 0, 0), Vector3.new(-106, 0, 0), 8)
	path(paths, Vector3.new(24, 0, -24), Vector3.new(176, 0, -146), 8)

	buildVillage(root, rng)
	buildForest(root, rng)
	buildMountain(root)
	buildTribulationAltar(root)

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
