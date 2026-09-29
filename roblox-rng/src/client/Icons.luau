-- 3D 미니 아이콘 (이모지 대신). 기본 파트 몇 개로 만든 작은 모형을 ViewportFrame 에 띄웁니다.
--   Icons.view(parent, "coin", { Size = ..., Position = ..., AnchorPoint = ..., Spin = 60 }) -> ViewportFrame
--   Icons.set(vf, "plaza") -- 이미 만든 화면의 아이콘만 바꿈
-- 모형은 이름별로 한 번만 만들어 두고 복제해서 씁니다. 파트 수는 아이콘마다 3~15개 정도로 작게 유지.
-- 아이콘: coin, globe(=roll), passport, collection, hammer, park, plaza, star, luck, news, plane, ticket

local Viewport = require(script.Parent.Viewport)

local Icons = {}

local V = Vector3.new
local rgb = Color3.fromRGB
local Mat = Enum.Material
local PI = math.pi

local UPRIGHT = CFrame.Angles(0, 0, PI / 2) -- 원기둥(길이 축 = X)을 세움
local ALONG_Z = CFrame.Angles(0, PI / 2, 0) -- 원기둥 길이 축을 Z 로 (정면을 보는 원판)
local FACE = CFrame.Angles(0, math.rad(-18), 0) -- 정면(-Z)을 카메라 쪽으로 살짝 돌려 옆면도 보이게

-- 색 (UI 테마와 맞춤)
local GOLD = rgb(255, 206, 64)
local GOLD_DEEP = rgb(222, 150, 24)
local OCEAN = rgb(57, 160, 255)
local LAND = rgb(76, 205, 96)
local SNOW = rgb(250, 252, 255)
local NAVY = rgb(38, 62, 140)
local CREAM = rgb(255, 244, 220)
local SKY = rgb(57, 160, 255)
local CORAL = rgb(255, 94, 91)
local SUN = rgb(255, 197, 61)
local GRAPE = rgb(155, 107, 255)
local GRASS = rgb(96, 196, 90)
local LEAF = rgb(58, 160, 74)
local LEAF_LIGHT = rgb(110, 210, 100)
local WOOD = rgb(150, 98, 58)
local WOOD_DARK = rgb(105, 68, 42)
local IRON = rgb(70, 70, 86)
local STEEL = rgb(160, 166, 184)
local MARBLE = rgb(246, 240, 228)
local MARBLE_SHADE = rgb(214, 204, 186)
local NEWSPRINT = rgb(236, 232, 220)
local INK = rgb(30, 27, 46)
local CLOVER = rgb(70, 190, 90)
local CLOVER_DARK = rgb(40, 140, 64)

local function style(part: BasePart, cf: CFrame, size: Vector3, color: Color3, material: Enum.Material?)
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.CastShadow = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Size = size
	part.CFrame = cf
	part.Color = color
	part.Material = material or Mat.SmoothPlastic
end

local function part(
	model: Model,
	shape: Enum.PartType,
	cf: CFrame,
	size: Vector3,
	color: Color3,
	material: Enum.Material?
): BasePart
	local p = Instance.new("Part")
	p.Shape = shape -- 크기보다 먼저(공 모양은 크기가 균일해짐)
	style(p, cf, size, color, material)
	p.Parent = model
	return p
end

local function block(model: Model, cf: CFrame, size: Vector3, color: Color3, material: Enum.Material?): BasePart
	return part(model, Enum.PartType.Block, cf, size, color, material)
end

local function ball(model: Model, center: Vector3, d: number, color: Color3, material: Enum.Material?): BasePart
	return part(model, Enum.PartType.Ball, CFrame.new(center), V(d, d, d), color, material)
end

-- 길이 축이 cf 의 X 축인 원기둥
local function cyl(
	model: Model,
	cf: CFrame,
	length: number,
	d: number,
	color: Color3,
	material: Enum.Material?
): BasePart
	return part(model, Enum.PartType.Cylinder, cf, V(length, d, d), color, material)
end

local function wedge(model: Model, cf: CFrame, size: Vector3, color: Color3, material: Enum.Material?): BasePart
	local p = Instance.new("WedgePart")
	style(p, cf, size, color, material)
	p.Parent = model
	return p
end

local BUILDERS: { [string]: (Model) -> () } = {}

-- 동전: 모로 선 금화. 가운데 면 + 도드라진 테두리(조각 12개) + 가운데 마름모 문양
function BUILDERS.coin(m)
	local center = FACE * CFrame.new(0, 2.15, 0) * ALONG_Z -- 로컬 X = 동전 두께 방향
	cyl(m, center, 0.56, 4.1, GOLD)
	local pieces = 12
	local outer, width = 2.12, 0.42
	local chord = 2 * outer * math.sin(PI / pieces) + 0.06
	for k = 0, pieces - 1 do
		local cf = center * CFrame.Angles(k * 2 * PI / pieces, 0, 0) * CFrame.new(0, outer - width / 2, 0)
		block(m, cf, V(0.8, width, chord), GOLD_DEEP, Mat.Foil)
	end
	block(m, center * CFrame.Angles(PI / 4, 0, 0), V(0.66, 1.05, 1.05), GOLD_DEEP)
end

-- 지구본: 파란 공 + 튀어나온 초록 대륙 + 북극 얼음
function BUILDERS.globe(m)
	local radius = 2.1
	local center = V(0, radius, 0)
	ball(m, center, radius * 2, OCEAN)
	local function surface(lat: number, lon: number, r: number): Vector3
		local phi, lambda = math.rad(lat), math.rad(lon)
		return center
			+ V(r * math.cos(phi) * math.sin(lambda), r * math.sin(phi), -r * math.cos(phi) * math.cos(lambda))
	end
	local lands = {
		{ 12, 20, 1.9 },
		{ 45, 70, 2 },
		{ -18, 130, 1.5 },
		{ 38, -100, 2 },
		{ -22, -58, 1.6 },
		{ 55, 170, 1.4 },
	}
	for _, land in lands do
		local d = land[3]
		ball(m, surface(land[1], land[2], radius - d / 2 + 0.28), d, LAND)
	end
	ball(m, surface(90, 0, radius - 0.6 + 0.22), 1.2, SNOW)
end

-- 여권: 남색 수첩 + 오른쪽으로 보이는 종이 + 금색 문장
function BUILDERS.passport(m)
	local base = FACE * CFrame.new(0, 2.1, 0) * CFrame.Angles(0, 0, math.rad(-6))
	block(m, base, V(3, 4.2, 0.55), NAVY)
	block(m, base * CFrame.new(0.1, 0, 0), V(2.92, 4, 0.46), CREAM)
	cyl(m, base * CFrame.new(0, 0.5, -0.3) * ALONG_Z, 0.06, 1.5, GOLD)
	block(m, base * CFrame.new(0, -0.8, -0.3), V(1.7, 0.16, 0.06), GOLD)
	block(m, base * CFrame.new(0, -1.15, -0.3), V(1.2, 0.12, 0.06), GOLD)
end

-- 컬렉션: 부채꼴로 펼친 카드 3장 (앞 카드에는 작은 그림)
function BUILDERS.collection(m)
	local cards = {
		{ Angle = 20, Z = 0.3, Color = SKY },
		{ Angle = 0, Z = 0, Color = GRAPE },
		{ Angle = -20, Z = -0.3, Color = CORAL },
	}
	local front: CFrame? = nil
	for _, card in cards do
		local cf = FACE * CFrame.new(0, 0.2, card.Z) * CFrame.Angles(0, 0, math.rad(card.Angle)) * CFrame.new(0, 1.7, 0)
		block(m, cf, V(2.3, 3.2, 0.16), card.Color)
		block(m, cf * CFrame.new(0, 0.3, -0.05), V(1.8, 1.9, 0.14), CREAM)
		front = cf
	end
	if front then
		ball(m, (front * CFrame.new(0.45, 0.8, -0.12)).Position, 0.5, SUN)
		block(m, front * CFrame.new(0, -0.35, -0.08), V(1.8, 0.55, 0.16), GRASS)
	end
end

-- 망치(업그레이드): 나무 손잡이 + 빨간 손잡이 끝 + 쇠머리
function BUILDERS.hammer(m)
	local base = FACE * CFrame.new(0, 2.5, 0) * CFrame.Angles(0, 0, math.rad(-35))
	block(m, base * CFrame.new(0, -0.5, 0), V(0.55, 4, 0.55), WOOD)
	block(m, base * CFrame.new(0, -2.1, 0), V(0.68, 1.1, 0.68), CORAL)
	block(m, base * CFrame.new(0, 1.6, 0), V(2.8, 1.1, 1.1), STEEL, Mat.Metal)
	block(m, base * CFrame.new(1.45, 1.6, 0), V(0.3, 1.25, 1.25), IRON, Mat.Metal)
end

-- 공원: 잔디 원판 + 나무 + 벤치
function BUILDERS.park(m)
	cyl(m, CFrame.new(0, 0.2, 0) * UPRIGHT, 0.4, 5.2, GRASS)
	cyl(m, CFrame.new(-0.9, 1.4, 0.5) * UPRIGHT, 2, 0.6, WOOD)
	ball(m, V(-0.9, 3.1, 0.5), 2.6, LEAF)
	ball(m, V(-0.1, 2.5, -0.1), 1.6, LEAF_LIGHT)
	local bench = FACE * CFrame.new(1.05, 0, -0.9)
	block(m, bench * CFrame.new(0, 1, 0), V(1.9, 0.2, 0.7), WOOD_DARK)
	block(m, bench * CFrame.new(0, 1.45, 0.28), V(1.9, 0.5, 0.14), WOOD_DARK)
	block(m, bench * CFrame.new(-0.75, 0.65, 0), V(0.18, 0.5, 0.6), IRON)
	block(m, bench * CFrame.new(0.75, 0.65, 0), V(0.18, 0.5, 0.6), IRON)
end

-- 광장: 고전 기둥 (받침 + 기둥 + 소용돌이 머리)
function BUILDERS.plaza(m)
	local base = FACE
	block(m, base * CFrame.new(0, 0.25, 0), V(2.8, 0.5, 2.8), MARBLE_SHADE)
	block(m, base * CFrame.new(0, 0.65, 0), V(2.3, 0.3, 2.3), MARBLE)
	cyl(m, base * CFrame.new(0, 2.7, 0) * UPRIGHT, 3.8, 1.6, MARBLE)
	block(m, base * CFrame.new(0, 4.75, 0), V(2.2, 0.3, 2.2), MARBLE)
	cyl(m, base * CFrame.new(-1.05, 4.7, 0) * ALONG_Z, 2.2, 0.62, MARBLE_SHADE)
	cyl(m, base * CFrame.new(1.05, 4.7, 0) * ALONG_Z, 2.2, 0.62, MARBLE_SHADE)
	block(m, base * CFrame.new(0, 5.1, 0), V(2.9, 0.4, 2.9), MARBLE_SHADE)
end

-- 별: 가운데 원판 + 뾰족한 끝 5개(직각 쐐기 2개씩)
function BUILDERS.star(m)
	local outerRadius, innerRadius, thickness = 2.2, 0.95, 0.7
	local center = FACE * CFrame.new(0, 2.2, 0) -- 별 평면 = 로컬 XY, 두께 = 로컬 Z
	cyl(m, center * ALONG_Z, thickness, innerRadius * 2, SUN)
	local apothem = innerRadius * math.cos(math.rad(36))
	local halfBase = innerRadius * math.sin(math.rad(36))
	local length = outerRadius - apothem
	for k = 0, 4 do
		local a = math.rad(90 + 72 * k)
		local u = V(math.cos(a), math.sin(a), 0) -- 뾰족한 방향
		local v = V(-math.sin(a), math.cos(a), 0) -- 가로 방향
		local mid = u * apothem -- 끝 밑변의 가운데(직각 꼭짓점)
		for _, side in { 1, -1 } do
			-- 쐐기의 직각 = 밑변 가운데, 세로 변(Y) = 뾰족한 방향, 가로 변(Z) = 바깥 꼭짓점 → 가운데
			local yAxis = u
			local zAxis = v * -side
			local xAxis = yAxis:Cross(zAxis)
			local position = mid + u * (length / 2) + v * (side * halfBase / 2)
			wedge(m, center * CFrame.fromMatrix(position, xAxis, yAxis, zAxis), V(thickness, length, halfBase), SUN)
		end
	end
end

-- 행운: 네잎클로버 (잎 원판 4장 + 가운데 + 줄기)
function BUILDERS.luck(m)
	local center = FACE * CFrame.new(0, 2.7, 0)
	for _, offset in { { -0.72, 0.72 }, { 0.72, 0.72 }, { -0.72, -0.72 }, { 0.72, -0.72 } } do
		cyl(m, center * CFrame.new(offset[1], offset[2], 0) * ALONG_Z, 0.35, 1.8, CLOVER)
	end
	ball(m, (center * CFrame.new(0, 0, -0.05)).Position, 0.75, CLOVER_DARK)
	block(m, center * CFrame.new(0.3, -1.75, 0) * CFrame.Angles(0, 0, math.rad(-12)), V(0.26, 2.1, 0.26), CLOVER_DARK)
end

-- 속보: 둘둘 만 신문 (빨간 띠 2개 + 앞쪽에 제목 줄)
function BUILDERS.news(m)
	local base = FACE * CFrame.new(0, 0.9, 0) * CFrame.Angles(0, 0, math.rad(8))
	cyl(m, base, 4.4, 1.6, NEWSPRINT)
	cyl(m, base * CFrame.new(-1.25, 0, 0), 0.3, 1.66, CORAL)
	cyl(m, base * CFrame.new(1.25, 0, 0), 0.3, 1.66, CORAL)
	block(m, base * CFrame.new(0, -0.15, -0.78), V(3.3, 0.95, 0.06), CREAM)
	block(m, base * CFrame.new(-0.35, 0.1, -0.82), V(1.8, 0.18, 0.04), INK)
	block(m, base * CFrame.new(-0.55, -0.25, -0.82), V(1.4, 0.1, 0.04), MARBLE_SHADE)
end

-- 비행기(여행사): 흰 동체 + 파란 날개 + 빨간 꼬리
function BUILDERS.plane(m)
	local base = FACE * CFrame.new(0, 1.4, 0) * CFrame.Angles(0, 0, math.rad(14)) -- 코(+X)가 살짝 위로
	cyl(m, base, 4.2, 0.95, SNOW)
	ball(m, (base * CFrame.new(2.1, 0, 0)).Position, 0.95, SNOW)
	block(m, base * CFrame.new(1.55, 0.3, 0), V(0.6, 0.3, 0.72), NAVY)
	block(m, base * CFrame.new(0.2, -0.1, 0), V(1.2, 0.14, 4.6), SKY)
	block(m, base * CFrame.new(-1.8, 0.75, 0), V(0.8, 1.2, 0.14), CORAL)
	block(m, base * CFrame.new(-1.8, 0.1, 0), V(0.6, 0.12, 1.8), SKY)
end

-- 입장권: 빨간 표 + 떼는 부분 + 가운데 크림 띠
function BUILDERS.ticket(m)
	local base = FACE * CFrame.new(0, 1.6, 0) * CFrame.Angles(0, 0, math.rad(12))
	block(m, base * CFrame.new(-0.45, 0, 0), V(2.9, 1.9, 0.18), CORAL)
	block(m, base * CFrame.new(1.55, 0, 0), V(0.95, 1.9, 0.18), SUN)
	block(m, base * CFrame.new(-0.45, 0, -0.04), V(2.1, 0.55, 0.16), CREAM)
end

local ALIASES = {
	roll = "globe",
}

-- 모든 파트를 옮겨서 경계 상자의 바닥 중앙이 원점에 오게 함 (Viewport 는 원점 기준으로 틀을 잡고 돌림)
local function recenter(model: Model)
	local minX, minY, minZ = math.huge, math.huge, math.huge
	local maxX, maxY, maxZ = -math.huge, -math.huge, -math.huge
	local parts = {}
	for _, child in model:GetChildren() do
		if child:IsA("BasePart") then
			table.insert(parts, child)
			local cf = child.CFrame
			local half = child.Size / 2
			local right, up, look = cf.RightVector, cf.UpVector, cf.LookVector
			local ex = math.abs(right.X) * half.X + math.abs(up.X) * half.Y + math.abs(look.X) * half.Z
			local ey = math.abs(right.Y) * half.X + math.abs(up.Y) * half.Y + math.abs(look.Y) * half.Z
			local ez = math.abs(right.Z) * half.X + math.abs(up.Z) * half.Y + math.abs(look.Z) * half.Z
			local p = cf.Position
			minX, maxX = math.min(minX, p.X - ex), math.max(maxX, p.X + ex)
			minY, maxY = math.min(minY, p.Y - ey), math.max(maxY, p.Y + ey)
			minZ, maxZ = math.min(minZ, p.Z - ez), math.max(maxZ, p.Z + ez)
		end
	end
	if #parts == 0 then
		return
	end
	local shift = V(-(minX + maxX) / 2, -minY, -(minZ + maxZ) / 2)
	for _, p in parts do
		p.CFrame += shift
	end
end

local templates: { [string]: Model } = {}

local function template(name: string): Model
	local key = ALIASES[name] or name
	local cached = templates[key]
	if cached then
		return cached
	end
	local builder = BUILDERS[key]
	if not builder then
		warn("[LandmarkRNG] 모르는 아이콘: " .. tostring(name))
		key = "star"
		builder = BUILDERS.star
		if templates.star then
			return templates.star
		end
	end

	local model = Instance.new("Model")
	model.Name = "Icon_" .. key
	builder(model)
	recenter(model)

	-- 피벗 = 바닥 중앙(원점). Viewport.setModel 이 이 피벗을 돌림
	local root = Instance.new("Part")
	root.Name = "Root"
	style(root, CFrame.new(), V(0.05, 0.05, 0.05), INK)
	root.Transparency = 1
	root.Parent = model
	model.PrimaryPart = root

	templates[key] = model
	return model
end

-- 이미 있는 화면의 아이콘을 바꿈
function Icons.set(vf: ViewportFrame, name: string)
	Viewport.setModel(vf, template(name):Clone())
	vf:SetAttribute("Icon", name)
end

-- 새 아이콘 화면. props: { Size, Position, AnchorPoint, ZIndex, Spin(초당 회전 각도) }
function Icons.view(parent: Instance?, name: string, props: { [string]: any }?): ViewportFrame
	local options = props or {}
	local vf = Viewport.new(nil, {
		Name = "Icon",
		Size = options.Size or UDim2.fromScale(1, 1),
		Position = options.Position or UDim2.new(),
		AnchorPoint = options.AnchorPoint or Vector2.new(0, 0),
		ZIndex = options.ZIndex or 1,
		Ambient = rgb(196, 194, 208),
	})
	Icons.set(vf, name)
	local spin = options.Spin
	if type(spin) == "number" and spin ~= 0 then
		Viewport.setSpin(vf, spin)
	end
	vf.Parent = parent
	return vf
end

return Icons
