-- 아이콘 (이모지 대신). 모든 아이콘은 Icons.view 하나로 그립니다(Ui.icon 도 이걸 부름).
--   Shared/ImageIds 에 그림 Id 가 있으면 ImageLabel(그린 그림), 없으면 기본 파트로 만든 3D 미니 모형(ViewportFrame).
--   Icons.view(parent, "coin", { Size = ..., Position = ..., AnchorPoint = ..., Spin = 60 }) -> Frame(이름 "Icon")
--   Icons.set(icon, "plaza")   -- 이미 만든 아이콘의 그림만 바꿈 (그림 <-> 3D 가 바뀌어도 됨)
--   Icons.setSpin(icon, 420)   -- 회전 속도(초당 도). 그림 아이콘은 빠를 때만 빙글 돌고, 느린 회전은 3D 에만 적용
-- 3D 모형은 이름별로 한 번만 만들어 두고 복제해서 씁니다. 파트 수는 아이콘마다 3~15개 정도로 작게 유지.
-- 아이콘: coin, globe(=roll), passport, album(=collection), hammer, park, plaza, dice, clover(=luck), star,
--   star_empty, news, lock, auto, close, check, arrow_up, plane, ticket  (stamp_* 는 그림이 있을 때만 씀)

local RunService = game:GetService("RunService")

local Ui = require(script.Parent.Ui)
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
local STAR_GRAY = rgb(196, 190, 212)

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

-- 도감(컬렉션): 부채꼴로 펼친 카드 3장 (앞 카드에는 작은 그림)
function BUILDERS.album(m)
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

-- 삼각형 화살촉: base 좌표계의 XY 평면에서 baseCenter(밑변 가운데)부터 dir 방향으로 length 만큼.
-- 직각 쐐기 두 개를 가운데 줄 양쪽에 붙임(쐐기의 직각 = 밑변 가운데, 세로 변 = dir, 가로 변 = 바깥 → 가운데)
local function arrowhead(
	model: Model,
	base: CFrame,
	baseCenter: Vector3,
	dir: Vector3,
	length: number,
	halfWidth: number,
	thickness: number,
	color: Color3
)
	local u = dir.Unit
	local v = V(-u.Y, u.X, 0)
	for _, side in { 1, -1 } do
		local yAxis = u
		local zAxis = v * -side
		local xAxis = yAxis:Cross(zAxis)
		local position = baseCenter + u * (length / 2) + v * (side * halfWidth / 2)
		wedge(model, base * CFrame.fromMatrix(position, xAxis, yAxis, zAxis), V(thickness, length, halfWidth), color)
	end
end

-- 별: 가운데 원판 + 뾰족한 끝 5개(직각 쐐기 2개씩)
local function buildStar(m: Model, color: Color3)
	local outerRadius, innerRadius, thickness = 2.2, 0.95, 0.7
	local center = FACE * CFrame.new(0, 2.2, 0) -- 별 평면 = 로컬 XY, 두께 = 로컬 Z
	cyl(m, center * ALONG_Z, thickness, innerRadius * 2, color)
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
			wedge(m, center * CFrame.fromMatrix(position, xAxis, yAxis, zAxis), V(thickness, length, halfBase), color)
		end
	end
end

function BUILDERS.star(m)
	buildStar(m, SUN)
end

-- 빈 별(아직 못 딴 별): 흐린 회색 별
function BUILDERS.star_empty(m)
	buildStar(m, STAR_GRAY)
end

-- 행운: 네잎클로버 (잎 원판 4장 + 가운데 + 줄기)
function BUILDERS.clover(m)
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

-- 주사위(굴림 수): 흰 주사위, 앞 5 · 오른쪽 3 · 위 1(빨강). 앞과 오른쪽 면이 고루 보이게 조금 돌림
function BUILDERS.dice(m)
	local size = 3.4
	local h = size / 2
	local q = size * 0.26
	local pip = 0.74
	local center = CFrame.new(0, h, 0) * CFrame.Angles(0, math.rad(10), 0)
	block(m, center, V(size, size, size), SNOW)
	for _, p in { { -q, q }, { q, q }, { 0, 0 }, { -q, -q }, { q, -q } } do
		ball(m, (center * CFrame.new(p[1], p[2], -h)).Position, pip, INK)
	end
	for _, p in { { q, q }, { 0, 0 }, { -q, -q } } do
		ball(m, (center * CFrame.new(h, p[2], p[1])).Position, pip, INK)
	end
	ball(m, (center * CFrame.new(0, h, 0)).Position, pip * 1.3, CORAL)
end

-- 자물쇠: 금색 몸통 + 반원 쇠고리 + 열쇠 구멍
function BUILDERS.lock(m)
	local base = FACE
	block(m, base * CFrame.new(0, 1.3, 0), V(3.2, 2.6, 1.2), SUN)
	local radius, pieces = 1.05, 7
	local chord = 2 * radius * math.sin(PI / (2 * (pieces - 1))) + 0.1
	local arch = base * CFrame.new(0, 3.1, 0)
	for k = 0, pieces - 1 do
		local angle = k * PI / (pieces - 1)
		block(m, arch * CFrame.Angles(0, 0, angle) * CFrame.new(radius, 0, 0), V(0.5, chord, 0.5), STEEL, Mat.Metal)
	end
	for _, side in { -1, 1 } do
		block(m, base * CFrame.new(side * radius, 2.8, 0), V(0.5, 0.7, 0.5), STEEL, Mat.Metal)
	end
	cyl(m, base * CFrame.new(0, 1.55, -0.6) * ALONG_Z, 0.1, 0.62, INK)
	block(m, base * CFrame.new(0, 1.05, -0.6), V(0.28, 0.75, 0.1), INK)
end

-- 두 점을 잇는 굵은 막대 (base 좌표계의 XY 평면). 양 끝을 조금 늘려서 이음매가 비지 않게
local function bar(m: Model, base: CFrame, a: Vector3, b: Vector3, width: number, color: Color3)
	local d = b - a
	local angle = math.atan2(d.Y, d.X)
	block(m, base * CFrame.new((a + b) / 2) * CFrame.Angles(0, 0, angle), V(d.Magnitude + width, width, 0.8), color)
end

-- 체크: 초록 V 표시
function BUILDERS.check(m)
	local base = FACE * CFrame.new(0, 2.1, 0)
	bar(m, base, V(-1.7, 0.1, 0), V(-0.55, -1.05, 0), 0.95, GRASS)
	bar(m, base, V(-0.55, -1.05, 0), V(1.8, 1.45, 0), 0.95, GRASS)
end

-- 닫기/실패: 흰 X (빨간 바탕 위에 올라감)
function BUILDERS.close(m)
	local base = FACE * CFrame.new(0, 2, 0)
	bar(m, base, V(-1.4, -1.4, 0), V(1.4, 1.4, 0), 1, SNOW)
	bar(m, base, V(-1.4, 1.4, 0), V(1.4, -1.4, 0), 1, SNOW)
end

-- 위 화살표(수입·강화): 초록 기둥 + 화살촉
function BUILDERS.arrow_up(m)
	local base = FACE
	block(m, base * CFrame.new(0, 1.2, 0), V(1.2, 2.4, 0.8), GRASS)
	arrowhead(m, base, V(0, 2.3, 0), V(0, 1, 0), 2, 1.6, 0.8, GRASS)
end

-- 자동: 한 바퀴 도는 화살표(고리 조각 9개 + 화살촉). 오른쪽 위가 비어 있고 화살촉이 그쪽을 가리킴
function BUILDERS.auto(m)
	local center = FACE * CFrame.new(0, 2.3, 0)
	local radius, width, thickness = 1.65, 0.62, 0.7
	local pieces = 12
	local step = 2 * PI / pieces
	local chord = 2 * radius * math.sin(PI / pieces) + 0.08
	local start = math.rad(120)
	for k = 0, 8 do
		local cf = center * CFrame.Angles(0, 0, start + k * step) * CFrame.new(radius, 0, 0)
		block(m, cf, V(width, chord, thickness), SNOW)
	end
	local finish = start + 8 * step + step / 2
	local at = V(math.cos(finish), math.sin(finish), 0) * radius
	arrowhead(m, center, at, V(-math.sin(finish), math.cos(finish), 0), 1.3, 0.95, thickness, SNOW)
end

-- 예전 이름 -> 지금 이름 (ImageIds 와 같은 이름을 씀)
local ALIASES = {
	roll = "globe",
	collection = "album",
	luck = "clover",
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

local function template(key: string): Model
	local cached = templates[key]
	if cached then
		return cached
	end
	local builder = BUILDERS[key]
	if not builder then
		warn("[LandmarkRNG] 모르는 아이콘: " .. tostring(key))
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

-- 업그레이드 Id -> 아이콘 이름 (업그레이드 창, 구매 알림에서 같이 씀)
Icons.UPGRADE = {
	Globe = "globe",
	Agency = "plane",
	Park = "park",
	Ticket = "ticket",
} :: { [string]: string }

-- 그림 아이콘은 이 속도(초당 도) 이상일 때만 돌림. 천천히 도는 건 3D 모형에만 어울림
local FAST_SPIN = 180
local WHITE = Color3.new(1, 1, 1)

local imageSpins: { [ImageLabel]: number } = {}
local imageSpinConnection: RBXScriptConnection? = nil

local function stepImages(dt: number)
	for image, speed in imageSpins do
		if not image.Parent then
			imageSpins[image] = nil -- Destroy 된 아이콘
			continue
		end
		image.Rotation = (image.Rotation + speed * dt) % 360
	end
end

-- 그림 Id (없으면 nil). 예전 이름도 받아 줌
function Icons.imageId(name: string): string?
	return Ui.imageId(ALIASES[name] or name)
end

local function applySpin(icon: Frame)
	local value = icon:GetAttribute("Spin")
	local speed = if type(value) == "number" then value else 0
	local content = icon:FindFirstChild("Content")
	if not content then
		return
	end
	if content:IsA("ViewportFrame") then
		Viewport.setSpin(content, speed)
	elseif content:IsA("ImageLabel") then
		if math.abs(speed) >= FAST_SPIN then
			imageSpins[content] = speed
			if not imageSpinConnection then
				imageSpinConnection = RunService.RenderStepped:Connect(stepImages)
			end
		else
			imageSpins[content] = nil
			content.Rotation = 0
		end
	end
end

-- 색/투명도: 그림(ImageLabel)과 3D 화면(ViewportFrame) 둘 다 ImageColor3 / ImageTransparency 가 있음
local function applyLook(icon: Frame)
	local content = icon:FindFirstChild("Content")
	if content and (content:IsA("ImageLabel") or content:IsA("ViewportFrame")) then
		local color = icon:GetAttribute("Color")
		local transparency = icon:GetAttribute("Transparency")
		content.ImageColor3 = if typeof(color) == "Color3" then color else WHITE
		content.ImageTransparency = if type(transparency) == "number" then transparency else 0
	end
end

-- 이미 있는 아이콘의 그림을 바꿈. 그림이 있으면 ImageLabel, 없으면 3D 모형 (종류가 바뀌면 속을 새로 만듦)
function Icons.set(icon: Frame, name: string)
	local key = ALIASES[name] or name
	local id = Ui.imageId(key)
	local content = icon:FindFirstChild("Content")
	if id then
		local image: ImageLabel
		if content and content:IsA("ImageLabel") then
			image = content
		else
			if content then
				content:Destroy()
			end
			image = Ui.new("ImageLabel", {
				Name = "Content",
				BackgroundTransparency = 1,
				Size = UDim2.fromScale(1, 1),
				ScaleType = Enum.ScaleType.Fit,
				ZIndex = icon.ZIndex,
				Parent = icon,
			})
		end
		image.Image = id
	else
		local vf: ViewportFrame
		if content and content:IsA("ViewportFrame") then
			vf = content
		else
			if content then
				content:Destroy()
			end
			vf = Viewport.new(icon, {
				Name = "Content",
				ZIndex = icon.ZIndex,
				Ambient = rgb(196, 194, 208),
			})
		end
		Viewport.setModel(vf, template(key):Clone())
	end
	icon:SetAttribute("Icon", key)
	applyLook(icon)
	applySpin(icon)
end

-- 새 아이콘. props: { Size, Position, AnchorPoint, ZIndex, LayoutOrder, Rotation, Spin(초당 회전 각도),
--   Color?(ImageColor3), Transparency? }. 반환: 투명한 Frame(이름 "Icon") — 속은 그림 또는 3D 화면
function Icons.view(parent: Instance?, name: string, props: { [string]: any }?): Frame
	local options = props or {}
	local icon = Ui.new("Frame", {
		Name = "Icon",
		BackgroundTransparency = 1,
		Size = options.Size or UDim2.fromScale(1, 1),
		Position = options.Position or UDim2.new(),
		AnchorPoint = options.AnchorPoint or Vector2.new(0, 0),
		ZIndex = options.ZIndex or 1,
		LayoutOrder = options.LayoutOrder or 0,
		Rotation = options.Rotation or 0,
	})
	if type(options.Spin) == "number" then
		icon:SetAttribute("Spin", options.Spin)
	end
	if typeof(options.Color) == "Color3" then
		icon:SetAttribute("Color", options.Color)
	end
	if type(options.Transparency) == "number" then
		icon:SetAttribute("Transparency", options.Transparency)
	end
	Icons.set(icon, name)
	icon.Parent = parent
	return icon
end

-- 회전 속도 바꾸기 (0 이면 멈춤)
function Icons.setSpin(icon: Frame, degreesPerSecond: number)
	icon:SetAttribute("Spin", degreesPerSecond)
	applySpin(icon)
end

-- 흐리게/진하게 (0 = 진하게, 1 = 안 보임)
function Icons.setTransparency(icon: Frame, transparency: number)
	icon:SetAttribute("Transparency", transparency)
	applyLook(icon)
end

-- 물들이기 (흰색 = 원래 색)
function Icons.setColor(icon: Frame, color: Color3)
	icon:SetAttribute("Color", color)
	applyLook(icon)
end

return Icons
