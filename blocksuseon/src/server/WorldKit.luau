-- 맵을 짓는 작은 도구들 (World.luau 와 땅마다의 World*.luau 가 같이 쓴다).
-- Lune(맵 굽기)과 엔진에서 똑같이 돈다. CFrame.lookAt / CFrame.new(pos, target) 은 Lune 에서 Z 가 뒤집혀 쓰지 않는다 (face 를 쓴다).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")

local Land = require(Shared.Land)

local Kit = {}

-- 땅 겉면 위 (떠 있는 섬이 있으면 섬 위)
local function at(x: number, z: number, lift: number?): Vector3
	return Vector3.new(x, Land.surface(x, z) + (lift or 0), z)
end

-- 땅 위 (떠 있는 섬 밑에 놓을 때)
local function atGround(x: number, z: number, lift: number?): Vector3
	return Vector3.new(x, Land.height(x, z) + (lift or 0), z)
end

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

Kit.at = at
Kit.atGround = atGround
Kit.makeRng = makeRng
Kit.C = C
Kit.VEIN_COLORS = VEIN_COLORS
Kit.face = face
Kit.block = block
Kit.wedge = wedge
Kit.disc = disc
Kit.ball = ball
Kit.folder = folder
Kit.model = model
Kit.light = light
Kit.motes = motes
Kit.spanAt = spanAt
Kit.footing = footing
Kit.engrave = engrave
Kit.facing = facing
Kit.signboard = signboard
Kit.stele = stele
Kit.gateway = gateway
Kit.siteMarker = siteMarker
Kit.lantern = lantern
Kit.VEIN_NAMES = VEIN_NAMES
Kit.vein = vein
Kit.house = house
Kit.houseAt = houseAt
Kit.tree = tree
Kit.palm = palm
Kit.rock = rock
Kit.waypoint = waypoint

return Kit
