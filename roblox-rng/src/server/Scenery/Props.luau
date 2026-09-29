-- 풍경 장식 파트 만들기(Plan 의 Item 하나 → 파트 몇 개). 게임 전체와 같은 통통한 만화풍:
-- SmoothPlastic/Grass/Wood, 선명한 색, 공·원기둥·상자·쐐기만(메시·텍스처·에셋 Id 없음).
-- 모두 Anchored. 잎·꽃·작은 소품은 CanCollide/CanQuery/CanTouch 끔(카메라가 잎에 걸려 당겨지지 않음).
-- 줄기·바위·벤치·언덕처럼 부딪혀도 되는 것만 solid(산책로 위에는 Plan 이 두지 않음).
-- 그림자: 나무·덤불·벤치·가로등처럼 땅 위에 선 것만(SHADOW_KINDS). 광장 나무(World)처럼 그림자가 있어야
-- 땅에 붙어 보임. 바닥 판·잔디 무늬·꽃·먼 산·언덕은 그림자 없음.

local Props = {}

-- 색 ------------------------------------------------------------------------
local rgb = Color3.fromRGB

Props.GRASS = Color3.new(0.42, 0.66, 0.31) -- default.project.json Baseplate 색과 같게
Props.PATH = rgb(215, 198, 165) -- ParkService PATH_COLOR 와 같게

local TRUNK = rgb(122, 78, 45) -- World 나무와 같게
local LEAF = rgb(72, 184, 84)
local LEAF_LIGHT = rgb(122, 214, 104)
local LEAF_WARM = rgb(120, 196, 70) -- 잎 색 변화(연두 쪽)
local PINE = rgb(40, 140, 88)
local PINE_LIGHT = rgb(70, 170, 104)
local PALM_TRUNK = rgb(186, 138, 88)
local PALM_LEAF = rgb(56, 180, 90)
local BUSH = rgb(64, 170, 78)
local BUSH_LIGHT = rgb(122, 214, 104)
local SOIL = rgb(120, 82, 58)
local ROCK = rgb(156, 158, 170)
local ROCK_DARK = rgb(116, 120, 136)
local STONE = rgb(196, 192, 184)
local MARBLE = rgb(240, 238, 232)
local WOOD = rgb(181, 120, 66) -- 간판 판자와 같은 따뜻한 갈색
local WOOD_DARK = rgb(122, 78, 45)
local IRON = rgb(45, 48, 60) -- 가로등 기둥(World 와 같게)
local LAMP_LIGHT = rgb(255, 235, 190)
local POND = rgb(74, 172, 230)
local POND_LIGHT = rgb(150, 220, 255)
local LILY = rgb(78, 190, 96)
local PINK = rgb(255, 140, 190)
local WHITE = rgb(255, 250, 240)
local CORAL = rgb(255, 94, 91)
local SUN = rgb(255, 197, 61)
local SKY = rgb(90, 180, 255)
local SAND = rgb(240, 222, 170)
local RED = rgb(230, 70, 64)
local HILL = rgb(104, 182, 84)
local HILL_DARK = rgb(76, 152, 72)
local FOREST = rgb(50, 136, 74)
local FOREST_LIGHT = rgb(78, 166, 86)
local PEAK = rgb(150, 158, 194)
local PEAK_DARK = rgb(122, 130, 170)
local CLIFF = rgb(124, 128, 152) -- 폭포 절벽(산과 같은 푸른 회색, 조금 짙게)
local CLIFF_LIGHT = rgb(146, 150, 174)
local SNOW = rgb(248, 250, 255)
local WATERFALL = rgb(170, 225, 255)

-- 꽃밭 색 짝(Style 1~6)
local FLOWERS = {
	{ CORAL, SUN },
	{ PINK, WHITE },
	{ rgb(170, 120, 255), SUN },
	{ SKY, WHITE },
	{ SUN, CORAL },
	{ PINK, rgb(170, 120, 255) },
}
-- 잔디 무늬 색(Style 1~3): 밝은 풀, 짙은 풀, 노르스름한 풀
-- 바닥 풀(107, 168, 79)과 조금만 달라서 얼룩이 아니라 풀빛 변화로 보이게
local PATCH_COLORS = { rgb(118, 178, 84), rgb(99, 158, 73), rgb(128, 176, 80) }
-- 파라솔·돗자리 색(Style)
local CANOPY = { CORAL, SKY, SUN, PINK }

-- 원기둥 파트는 X 축이 기둥 방향이므로 세우려면 Z 축으로 90도 돌림(World 와 같음)
local UPRIGHT = CFrame.Angles(0, 0, math.rad(90))
-- 앞(LookVector) 방향 원기둥: lookAt 뒤에 곱함
local ALONG_LOOK = CFrame.Angles(0, math.rad(90), 0)

-- 파트 수 세기(구역별) --------------------------------------------------------------
local counts: { [string]: number } = {}
local zone = "Misc"
local castShadow = false -- 지금 만드는 장식이 그림자를 드리우는지(Props.build 가 종류별로 정함)

-- 그림자를 드리우는 장식 종류
local SHADOW_KINDS = {
	RoundTree = true,
	PineTree = true,
	PalmTree = true,
	Bush = true,
	Topiary = true,
	Rock = true,
	Lamp = true,
	Bench = true,
	Picnic = true,
	Fountain = true,
	Umbrella = true,
	Lighthouse = true,
	Pier = true,
	Boat = true,
	Waterfall = true,
}

function Props.setZone(name: string)
	zone = name
end

function Props.counts(): { [string]: number }
	return counts
end

function Props.resetCounts()
	counts = {}
end

-- 파트 헬퍼 ----------------------------------------------------------------------

-- solid: 부딪힘(줄기·바위·벤치 등). 아니면 충돌·검색·터치 모두 끔
local function setup(
	part: BasePart,
	parent: Instance,
	name: string,
	color: Color3,
	material: Enum.Material,
	solid: boolean?
)
	part.Name = name
	part.Color = color
	part.Material = material
	part.Anchored = true
	part.CanCollide = solid == true
	part.CanTouch = false
	if not solid then
		part.CanQuery = false
	end
	part.CastShadow = castShadow
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = parent
	counts[zone] = (counts[zone] or 0) + 1
end

function Props.part(
	parent: Instance,
	name: string,
	shape: Enum.PartType,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material,
	solid: boolean?
): Part
	local part = Instance.new("Part")
	part.Shape = shape
	part.Size = size
	part.CFrame = cframe
	setup(part, parent, name, color, material, solid)
	return part
end
local part = Props.part

function Props.block(
	parent: Instance,
	name: string,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material?,
	solid: boolean?
): Part
	return part(parent, name, Enum.PartType.Block, size, cframe, color, material or Enum.Material.SmoothPlastic, solid)
end
local block = Props.block

function Props.ball(
	parent: Instance,
	name: string,
	center: Vector3,
	diameter: number,
	color: Color3,
	material: Enum.Material?,
	solid: boolean?
): Part
	return part(
		parent,
		name,
		Enum.PartType.Ball,
		Vector3.new(diameter, diameter, diameter),
		CFrame.new(center),
		color,
		material or Enum.Material.SmoothPlastic,
		solid
	)
end
local ball = Props.ball

-- bottom(바닥 중앙)에서 위로 height 만큼 세운 원기둥
function Props.disc(
	parent: Instance,
	name: string,
	bottom: Vector3,
	height: number,
	diameter: number,
	color: Color3,
	material: Enum.Material?,
	solid: boolean?
): Part
	return part(
		parent,
		name,
		Enum.PartType.Cylinder,
		Vector3.new(height, diameter, diameter),
		CFrame.new(bottom + Vector3.new(0, height / 2, 0)) * UPRIGHT,
		color,
		material or Enum.Material.SmoothPlastic,
		solid
	)
end
local disc = Props.disc

-- a 에서 b 까지 이어지는 원기둥(지름 d)
local function rod(
	parent: Instance,
	name: string,
	a: Vector3,
	b: Vector3,
	d: number,
	color: Color3,
	material: Enum.Material,
	solid: boolean?
): Part
	local length = (b - a).Magnitude
	return part(
		parent,
		name,
		Enum.PartType.Cylinder,
		Vector3.new(length, d, d),
		CFrame.lookAt((a + b) / 2, b) * ALONG_LOOK,
		color,
		material,
		solid
	)
end

-- 쐐기: 높은 면이 +Z(뒤), 경사면이 -Z(앞) 쪽을 봄
function Props.wedge(
	parent: Instance,
	name: string,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material?,
	solid: boolean?
): WedgePart
	local part = Instance.new("WedgePart")
	part.Size = size
	part.CFrame = cframe
	setup(part, parent, name, color, material or Enum.Material.SmoothPlastic, solid)
	return part
end
local wedge = Props.wedge

-- 네 모서리 쐐기(CornerWedgePart)로 만든 정사각뿔. cf = 바닥 중앙, 바닥 한 변 width, 높이 height.
-- CornerWedgePart 는 바닥 사각형 + 꼭대기 점 하나(로컬 (+X/2, +Y/2, -Z/2))인 뿔이라
-- (-X, +Z) 사분면 조각은 돌리지 않아도 꼭대기가 뿔 가운데에 옴 → 90도씩 돌려 네 조각
-- (꼭짓점 표: Stravant roblox-geometry, tools/world_preview/scene.js 와 같음)
function Props.pyramid(
	parent: Instance,
	name: string,
	cf: CFrame,
	width: number,
	height: number,
	color: Color3,
	material: Enum.Material?,
	solid: boolean?
)
	local half = width / 2
	for k = 0, 3 do
		local piece = Instance.new("CornerWedgePart")
		piece.Size = Vector3.new(half, height, half)
		piece.CFrame = cf * CFrame.Angles(0, k * math.pi / 2, 0) * CFrame.new(-half / 2, height / 2, half / 2)
		setup(piece, parent, name, color, material or Enum.Material.SmoothPlastic, solid)
	end
end
local pyramid = Props.pyramid

local SEAM_OVERLAP = 0.08

-- 세 점을 잇는 두께 thickness 인 삼각 판(직각 쐐기 두 개). 가장 긴 변을 밑변으로 하면
-- 맞은편 꼭짓점의 수선의 발이 항상 밑변 안에 떨어짐
function Props.triangle(
	parent: Instance,
	name: string,
	a: Vector3,
	b: Vector3,
	c: Vector3,
	thickness: number,
	color: Color3,
	material: Enum.Material?
)
	local apex, p, q = c, a, b
	local ab, bc, ca = (b - a).Magnitude, (c - b).Magnitude, (a - c).Magnitude
	if bc >= ab and bc >= ca then
		apex, p, q = a, b, c
	elseif ca >= ab and ca >= bc then
		apex, p, q = b, c, a
	end
	local edge = q - p
	local foot = p + edge * ((apex - p):Dot(edge) / edge:Dot(edge))
	local rise = apex - foot
	local height = rise.Magnitude
	if height < 1e-3 then
		return
	end
	local up = rise.Unit
	for _, corner in { p, q } do
		local toFoot = foot - corner
		local length = toFoot.Magnitude
		if length > 1e-3 then
			-- 두 쐐기가 수선(foot-apex) 너머로 SEAM_OVERLAP 만큼 서로 겹치게 늘려서 이음새 틈(흰 선)이 안 보이게
			local direction = toFoot.Unit
			local center = (corner + apex) / 2 + direction * (SEAM_OVERLAP / 2)
			wedge(
				parent,
				name,
				Vector3.new(thickness, height, length + SEAM_OVERLAP),
				CFrame.lookAt(center, center - direction, up),
				color,
				material
			)
		end
	end
end

-- 수평 회전: (x, z) 를 turn 만큼(각도가 커지는 쪽으로) 돌림
local function spin(x: number, z: number, turn: number): (number, number)
	local c, s = math.cos(turn), math.sin(turn)
	return x * c - z * s, x * s + z * c
end

-- 바닥 중앙 base 에서 turn 방향(앞 = LookVector)을 보는 CFrame
local function heading(base: Vector3, turn: number): CFrame
	return CFrame.lookAt(base, base + Vector3.new(math.cos(turn), 0, math.sin(turn)))
end

local function basePoint(item): Vector3
	return Vector3.new(item.X, item.Y, item.Z)
end

-- 모양별 만들기 --------------------------------------------------------------------
local BUILD = {}

-- 동글동글한 나무(World.tree 와 같은 모양): 줄기 + 큰 잎 공 + 작은 밝은 공
function BUILD.RoundTree(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	disc(parent, "TreeTrunk", base, 6 * s, 1.6 * s, TRUNK, Enum.Material.Wood, true)
	local leaf = LEAF:Lerp(LEAF_WARM, item.Tint * 0.6)
	ball(parent, "TreeLeaves", base + Vector3.new(0, 8 * s, 0), 7.5 * s, leaf)
	local ox, oz = spin(1.2, -0.6, item.Turn)
	ball(parent, "TreeLeaves", base + Vector3.new(ox * s, 11 * s, oz * s), 4.6 * s, LEAF_LIGHT:Lerp(leaf, 0.2))
end

-- 뾰족 나무: 줄기 + 네모뿔 잎. Style 1 = 긴 뿔 하나(먼 숲), Style 2 = 뿔 두 층(위층은 45도 돌려 작게)
local PINE_TIERS = {
	[1] = { { Bottom = 1.8, Height = 9, Width = 7.4, Turn = 0 } },
	[2] = {
		{ Bottom = 1.8, Height = 5.4, Width = 7.2, Turn = 0 },
		{ Bottom = 4.6, Height = 5.2, Width = 5, Turn = math.pi / 4 },
	},
}
function BUILD.PineTree(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	disc(parent, "TreeTrunk", base, 2.4 * s, 1.2 * s, TRUNK, Enum.Material.Wood, true)
	local leaf = PINE:Lerp(PINE_LIGHT, item.Tint * 0.5)
	local tiers = PINE_TIERS[item.Style] or PINE_TIERS[2]
	for k, tier in tiers do
		local color = if k > 1 then leaf:Lerp(PINE_LIGHT, 0.45) else leaf
		local cf = CFrame.new(base + Vector3.new(0, tier.Bottom * s, 0)) * CFrame.Angles(0, item.Turn + tier.Turn, 0)
		pyramid(parent, "PineLeaves", cf, tier.Width * s, tier.Height * s, color)
	end
end

-- 야자수: 기운 줄기 두 마디 + 늘어진 잎 다섯 장. Turn = 기우는 방향
function BUILD.PalmTree(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local lean = Vector3.new(math.cos(item.Turn), 0, math.sin(item.Turn))
	local knee = base + Vector3.new(0, 5.2 * s, 0) + lean * (0.7 * s)
	local top = knee + Vector3.new(0, 4.4 * s, 0) + lean * (1.9 * s)
	rod(parent, "PalmTrunk", base - Vector3.new(0, 0.3, 0), knee, 1.2 * s, PALM_TRUNK, Enum.Material.Wood, true)
	rod(parent, "PalmTrunk", knee, top, 1 * s, PALM_TRUNK:Lerp(TRUNK, 0.25), Enum.Material.Wood, true)
	local leaf = PALM_LEAF:Lerp(LEAF_WARM, item.Tint * 0.5)
	for k = 0, 4 do
		local a = item.Turn + k / 5 * math.pi * 2 + 0.3
		local out = Vector3.new(math.cos(a), -0.38, math.sin(a)).Unit
		block(
			parent,
			"PalmLeaf",
			Vector3.new(1.8 * s, 0.3 * s, 5.6 * s),
			CFrame.lookAt(top, top + out) * CFrame.new(0, 0, -2.6 * s),
			leaf,
			Enum.Material.Grass
		)
	end
end

-- 덤불: 큰 공 + 작은 밝은 공(Style 2 는 공 하나 더)
function BUILD.Bush(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local color = BUSH:Lerp(LEAF_WARM, item.Tint * 0.4)
	ball(parent, "Bush", base + Vector3.new(0, 1.1 * s, 0), 3.2 * s, color)
	local ox, oz = spin(0.9, -0.5, item.Turn)
	ball(parent, "Bush", base + Vector3.new(ox * s, 1.9 * s, oz * s), 2.2 * s, BUSH_LIGHT)
	if item.Style == 2 then
		ox, oz = spin(-1.2, 0.7, item.Turn)
		ball(parent, "Bush", base + Vector3.new(ox * s, 0.9 * s, oz * s), 2.3 * s, color:Lerp(BUSH_LIGHT, 0.3))
	end
end

-- 꽃밭: 흙 원판 + 가운데 잎 공 + 둘레 꽃 공(두 색 번갈아)
function BUILD.FlowerBed(parent: Instance, item)
	local r, base = item.Radius, basePoint(item)
	local colors = FLOWERS[(item.Style - 1) % #FLOWERS + 1]
	disc(parent, "FlowerSoil", base - Vector3.new(0, 0.1, 0), 0.5, r * 2, SOIL)
	ball(parent, "FlowerLeaves", base + Vector3.new(0, 0.6, 0), r * 0.7, BUSH)
	local count = math.clamp(math.floor(r * 1.6 + 0.5), 4, 6)
	local size = math.clamp(r * 0.45, 1.1, 1.6)
	for k = 1, count do
		local a = item.Turn + k / count * math.pi * 2
		local center = base + Vector3.new(math.cos(a) * r * 0.6, 0.4 + size * 0.3, math.sin(a) * r * 0.6)
		ball(parent, "Flower", center, size, colors[k % 2 + 1])
	end
end

-- 바위: 비스듬히 박힌 상자 하나(Style 2 는 작은 것 하나 더)
function BUILD.Rock(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local color = ROCK:Lerp(ROCK_DARK, item.Tint)
	local t = item.Turn
	-- 납작한 판처럼 보이지 않게 높이를 키우고 두 축으로 기울여 한 모서리가 땅에 박힌 바위로
	block(
		parent,
		"Rock",
		Vector3.new(2.7, 2.3, 2.4) * s,
		CFrame.new(base + Vector3.new(0, 0.75 * s, 0))
			* CFrame.Angles(0.3 + 0.12 * math.sin(t * 3), t, 0.28 * math.cos(t * 5)),
		color,
		Enum.Material.Slate,
		true
	)
	if item.Style == 2 then
		local ox, oz = spin(1.9, 0.8, t)
		block(
			parent,
			"Rock",
			Vector3.new(1.5, 1.1, 1.3) * s,
			CFrame.new(base + Vector3.new(ox * s, 0.3 * s, oz * s)) * CFrame.Angles(0.3, t * 1.7, -0.25),
			color:Lerp(ROCK, 0.5),
			Enum.Material.Slate,
			true
		)
	end
end

-- 잔디 언덕: 땅에 거의 다 묻힌 큰 공의 윗부분(반지름 Radius, 높이 Height). 올라설 수 있음
function BUILD.Mound(parent: Instance, item)
	local a, h = item.Radius, math.max(item.Height, 0.3)
	local sphere = (a * a + h * h) / (2 * h)
	local color = Props.GRASS:Lerp(LEAF_LIGHT, 0.15 + item.Tint * 0.2)
	ball(parent, "Mound", basePoint(item) + Vector3.new(0, h - sphere, 0), sphere * 2, color, Enum.Material.Grass, true)
end

-- 잔디 색 무늬: 아주 얇은 원판(윗면이 땅보다 0.1 위)
function BUILD.Patch(parent: Instance, item)
	local color = PATCH_COLORS[(item.Style - 1) % #PATCH_COLORS + 1]
	disc(
		parent,
		"GrassPatch",
		basePoint(item) - Vector3.new(0, 0.1, 0),
		0.2,
		item.Radius * 2,
		color,
		Enum.Material.Grass
	)
end

-- 가로등(World 광장 가로등과 같은 모양)
function BUILD.Lamp(parent: Instance, item)
	local base = basePoint(item)
	block(
		parent,
		"LampPost",
		Vector3.new(0.6, 9, 0.6),
		CFrame.new(base + Vector3.new(0, 4.5, 0)),
		IRON,
		Enum.Material.Metal,
		true
	)
	local bulb = ball(parent, "LampBulb", base + Vector3.new(0, 9.6, 0), 1.8, LAMP_LIGHT, Enum.Material.Neon)
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 16
	light.Brightness = 1
	light.Parent = bulb
end

-- 벤치: 앉는 판 + 등받이 + 다리 둘. Turn = 앉은 사람이 보는 쪽
function BUILD.Bench(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	block(parent, "BenchSeat", Vector3.new(5, 0.4, 1.6), cf * CFrame.new(0, 1.5, 0), WOOD, Enum.Material.Wood, true)
	block(parent, "BenchBack", Vector3.new(5, 1.3, 0.3), cf * CFrame.new(0, 2.55, 0.75), WOOD, Enum.Material.Wood, true)
	for _, x in { -2.1, 2.1 } do
		block(
			parent,
			"BenchLeg",
			Vector3.new(0.4, 1.3, 1.5),
			cf * CFrame.new(x, 0.65, 0.05),
			IRON,
			Enum.Material.Metal,
			true
		)
	end
end

-- 연못: 돌 테두리 원판 + 물 + 둘레 조약돌 + 수련 잎(+ 분홍 꽃). Style 2 는 수련이 더 많음
function BUILD.Pond(parent: Instance, item)
	local r, base, t = item.Radius, basePoint(item), item.Turn
	disc(parent, "PondRim", base - Vector3.new(0, 0.2, 0), 0.5, r * 2, STONE)
	disc(parent, "PondWater", base - Vector3.new(0, 0.2, 0), 0.62, r * 2 - 1.6, POND)
	for k = 1, 5 do
		local a = t + k / 5 * math.pi * 2
		local size = 1.3 + ((k * 37) % 5) / 10
		ball(parent, "Pebble", base + Vector3.new(math.cos(a) * (r - 0.5), 0.3, math.sin(a) * (r - 0.5)), size, ROCK)
	end
	local pads = if item.Style == 2 then 4 else 3
	for k = 1, pads do
		local a = t + 0.9 + k * 2.1
		local d = r * (0.25 + 0.12 * k)
		local pad = base + Vector3.new(math.cos(a) * d, 0.42, math.sin(a) * d)
		disc(parent, "LilyPad", pad, 0.1, 1.6 + 0.2 * k, LILY)
		if k == 1 or (k == 3 and item.Style == 2) then
			ball(parent, "LilyFlower", pad + Vector3.new(0, 0.35, 0), 0.8, PINK)
		end
	end
end

-- 분수: 대리석 수반(물이 찰랑) + 기둥 + 위 접시 + 물줄기 공
function BUILD.Fountain(parent: Instance, item)
	local r, base = item.Radius, basePoint(item)
	disc(parent, "FountainBasin", base, 1.2, r * 2, MARBLE, Enum.Material.Marble, true)
	disc(parent, "FountainWater", base + Vector3.new(0, 1.2, 0), 0.12, r * 2 - 1.4, POND)
	disc(parent, "FountainColumn", base + Vector3.new(0, 1.2, 0), 2.6, 1.2, MARBLE, Enum.Material.Marble, true)
	disc(parent, "FountainBowl", base + Vector3.new(0, 3.8, 0), 0.5, 3.8, MARBLE, Enum.Material.Marble)
	disc(parent, "FountainWater", base + Vector3.new(0, 4.3, 0), 0.1, 3.2, POND)
	local jet = ball(parent, "FountainJet", base + Vector3.new(0, 5, 0), 1.5, POND_LIGHT)
	jet.Transparency = 0.2
end

-- 소풍 탁자(긴 의자 둘) + 앞에 돗자리·바구니. Turn = 돗자리 쪽
function BUILD.Picnic(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	block(
		parent,
		"PicnicTop",
		Vector3.new(5.6, 0.35, 2.6),
		cf * CFrame.new(0, 2.3, 1.8),
		WOOD,
		Enum.Material.Wood,
		true
	)
	for _, z in { -0.4, 4 } do
		block(
			parent,
			"PicnicSeat",
			Vector3.new(5.6, 0.3, 0.9),
			cf * CFrame.new(0, 1.3, z),
			WOOD,
			Enum.Material.Wood,
			true
		)
	end
	for _, x in { -2.2, 2.2 } do
		block(
			parent,
			"PicnicLeg",
			Vector3.new(0.4, 2.1, 4.8),
			cf * CFrame.new(x, 1.05, 1.8),
			WOOD_DARK,
			Enum.Material.Wood,
			true
		)
	end
	local color = CANOPY[(item.Style - 1) % #CANOPY + 1]
	block(parent, "Blanket", Vector3.new(4.4, 0.08, 3.2), cf * CFrame.new(0, 0.04, -2.8), color, Enum.Material.Fabric)
	block(
		parent,
		"BlanketStripe",
		Vector3.new(4.4, 0.1, 0.6),
		cf * CFrame.new(0, 0.05, -2.8),
		WHITE,
		Enum.Material.Fabric
	)
	block(parent, "Basket", Vector3.new(1.1, 0.8, 0.8), cf * CFrame.new(1.3, 0.45, -3.2), WOOD, Enum.Material.Wood)
end

-- 토피어리: 막대 + 동그란 잎(Style 2 는 공 둘)
function BUILD.Topiary(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	disc(parent, "TopiaryStem", base, 2.6 * s, 0.5 * s, WOOD_DARK, Enum.Material.Wood, true)
	ball(parent, "Topiary", base + Vector3.new(0, 3.2 * s, 0), 2.6 * s, BUSH)
	if item.Style == 2 then
		ball(parent, "Topiary", base + Vector3.new(0, 4.9 * s, 0), 1.6 * s, BUSH_LIGHT)
	end
end

-- 파라솔 + 수건
function BUILD.Umbrella(parent: Instance, item)
	local base = basePoint(item)
	local color = CANOPY[(item.Style - 1) % #CANOPY + 1]
	disc(parent, "UmbrellaPole", base - Vector3.new(0, 0.5, 0), 6.6, 0.35, WHITE, Enum.Material.SmoothPlastic, true)
	disc(parent, "UmbrellaCanopy", base + Vector3.new(0, 5.6, 0), 0.5, 6.4, color, Enum.Material.Fabric)
	disc(parent, "UmbrellaCanopy", base + Vector3.new(0, 6.1, 0), 0.4, 3, WHITE, Enum.Material.Fabric)
	local cf = heading(base, item.Turn)
	local towel = CANOPY[item.Style % #CANOPY + 1]
	block(parent, "Towel", Vector3.new(2.2, 0.1, 4.2), cf * CFrame.new(0, 0.05, -3.4), towel, Enum.Material.Fabric)
end

-- 작은 돛단배: 배 몸통 + 뾰족한 뱃머리(쐐기 둘) + 돛대 + 삼각 돛. Turn = 뱃머리 쪽, Scale = 크기 배율
function BUILD.Boat(parent: Instance, item)
	local s = item.Scale
	local cf = heading(basePoint(item), item.Turn)
	local function at(x: number, y: number, z: number): CFrame
		return cf * CFrame.new(x * s, y * s, z * s)
	end
	local hull = if item.Tint < 0.5 then WHITE else CORAL
	block(parent, "BoatHull", Vector3.new(3.2, 1.3, 5.2) * s, at(0, 0.25, 0.8), hull)
	for _, side in { -1, 1 } do
		-- 쐐기를 Z 축으로 눕혀서(쐐기 +Y → 바깥 옆) 위에서 보면 삼각형(뱃머리 반쪽, 끝이 가운데 앞)
		wedge(
			parent,
			"BoatBow",
			Vector3.new(1.3, 1.6, 2.6) * s,
			at(side * 0.8, 0.25, -3.1) * CFrame.Angles(0, 0, -side * math.rad(90)),
			hull
		)
	end
	block(parent, "BoatRim", Vector3.new(3.3, 0.25, 5.3) * s, at(0, 0.95, 0.8), SKY)
	disc(parent, "BoatMast", at(0, 0.9, 0).Position, 6.5 * s, 0.3 * s, WOOD_DARK, Enum.Material.Wood)
	wedge(parent, "BoatSail", Vector3.new(0.15, 5.4, 3.4) * s, at(0, 4.3, -1.7), WHITE, Enum.Material.Fabric)
end

-- 먼 작은 섬: 모래 원판 + 풀 원판(야자수·바위는 Plan 이 따로 올림)
function BUILD.Islet(parent: Instance, item)
	local r, base = item.Radius, basePoint(item)
	disc(parent, "IsletSand", base - Vector3.new(0, 3, 0), 4, r * 2, SAND, Enum.Material.Sand)
	disc(parent, "IsletGrass", base - Vector3.new(0, 2, 0), 4, r * 1.3, Props.GRASS, Enum.Material.Grass)
end

-- 등대: 바위 받침 + 빨강·하양 줄무늬 탑 + 난간 + 불빛 + 지붕
function BUILD.Lighthouse(parent: Instance, item)
	local base = basePoint(item)
	block(
		parent,
		"LighthouseRock",
		Vector3.new(9, 3.2, 8),
		CFrame.new(base + Vector3.new(0, 1, 0)) * CFrame.Angles(0.08, item.Turn, -0.06),
		ROCK_DARK,
		Enum.Material.Slate,
		true
	)
	block(
		parent,
		"LighthouseRock",
		Vector3.new(6, 2.4, 6.5),
		CFrame.new(base + Vector3.new(2.5, 1.4, 1.5)) * CFrame.Angles(-0.1, item.Turn + 0.7, 0.1),
		ROCK,
		Enum.Material.Slate,
		true
	)
	local y = 2.4
	for k, diameter in { 6.4, 5.9, 5.4, 4.9 } do
		disc(
			parent,
			"LighthouseTower",
			base + Vector3.new(0, y, 0),
			5.5,
			diameter,
			if k % 2 == 1 then RED else WHITE,
			Enum.Material.SmoothPlastic,
			true
		)
		y += 5.5
	end
	disc(parent, "LighthouseGallery", base + Vector3.new(0, y, 0), 0.6, 6.8, IRON, Enum.Material.Metal, true)
	local lantern =
		disc(parent, "LighthouseLantern", base + Vector3.new(0, y + 0.6, 0), 3, 3.6, LAMP_LIGHT, Enum.Material.Neon)
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 40
	light.Brightness = 2
	light.Parent = lantern
	disc(parent, "LighthouseRoof", base + Vector3.new(0, y + 3.6, 0), 1, 4.8, RED)
	ball(parent, "LighthouseTop", base + Vector3.new(0, y + 5, 0), 1.3, IRON)
end

-- 부두: 모래사장에서 바다로 뻗은 나무 판 + 말뚝 + 입구 밧줄(보이지 않는 벽 자리를 알려 줌)
function BUILD.Pier(parent: Instance, item)
	local length, width = item.Height, item.Radius * 2
	local cf = heading(basePoint(item), item.Turn)
	local deckTop = 0.35 - item.Y -- 부두 윗면 y = 0.35
	block(
		parent,
		"PierDeck",
		Vector3.new(width, 0.5, length),
		cf * CFrame.new(0, deckTop - 0.25, -length / 2),
		WOOD,
		Enum.Material.WoodPlanks,
		true
	)
	for k = 1, 3 do
		local z = -length * (0.3 + 0.23 * k)
		for _, side in { -1, 1 } do
			local post = cf * Vector3.new(side * (width / 2 - 0.3), 0, z)
			disc(parent, "PierPost", Vector3.new(post.X, -3, post.Z), 3.8 + deckTop, 0.9, WOOD_DARK, Enum.Material.Wood)
		end
	end
	for _, side in { -1, 1 } do
		disc(
			parent,
			"RopePost",
			(cf * Vector3.new(side * (width / 2 - 0.3), deckTop, -8)),
			2.8,
			0.6,
			WOOD_DARK,
			Enum.Material.Wood
		)
	end
	block(
		parent,
		"Rope",
		Vector3.new(width - 0.6, 0.25, 0.25),
		cf * CFrame.new(0, deckTop + 2.2, -8),
		CORAL,
		Enum.Material.Fabric
	)
end

-- 먼 숲 덩어리: 반쯤 묻힌 큰 공(지름 Scale, 땅 위 높이 Height)
function BUILD.Blob(parent: Instance, item)
	local d = item.Scale
	local color = FOREST:Lerp(FOREST_LIGHT, item.Tint)
	ball(parent, "ForestBlob", basePoint(item) + Vector3.new(0, item.Height - d / 2, 0), d, color)
end

-- 초록 언덕: 아주 큰 공의 윗부분(지름 Scale, 땅 위 높이 Height)
function BUILD.Hill(parent: Instance, item)
	local d = item.Scale
	local color = HILL:Lerp(HILL_DARK, item.Tint)
	ball(parent, "Hill", basePoint(item) + Vector3.new(0, item.Height - d / 2, 0), d, color, Enum.Material.Grass)
end

-- 폭포 절벽: 풀 언덕(반구)에 박힌 바위 두 층. 층마다 크기·각도가 다른 바위 셋(가운데 바위가 조금 들어가서
-- 물길 홈이 됨)이라 윤곽이 울퉁불퉁하고, 바위 윗면은 풀로 덮임. 물은 두 단으로 떨어지고(흰 물결 줄)
-- 아래에 물거품 + 물웅덩이 + 둘레 바위. Turn = 앞(섬 쪽, 로컬 -Z)
local function grassCap(parent: Instance, size: Vector3, cf: CFrame)
	-- 바위 윗면을 살짝 넘치게 덮는 풀 판(만화풍 절벽 꼭대기)
	block(
		parent,
		"CliffGrass",
		Vector3.new(size.X + 1.2, 1.4, size.Z + 1.2),
		cf * CFrame.new(0, size.Y / 2 + 0.3, 0),
		HILL,
		Enum.Material.Grass,
		true
	)
end

function BUILD.Waterfall(parent: Instance, item)
	local h = item.Height
	local cf = heading(basePoint(item), item.Turn)
	local lowerH, upperH = h * 0.58, h * 0.46
	local ledge = lowerH - 2 -- 윗층 바닥(아래층에 묻힘)
	local top = ledge + upperH -- 윗층 가운데 바위 윗면
	-- 절벽 뒤 풀 언덕(반구, 절벽보다 높음): 바위 옆면·뒷부분을 덮어서 산비탈에 드러난 바위 벽처럼 보이게.
	-- 반구 가장자리가 가운데 바위 앞면(z = -5) 뒤(z = -4)에서 땅에 닿아서 물줄기·물웅덩이는 가리지 않음
	local hillRadius = h + 16
	ball(
		parent,
		"Hill",
		cf * Vector3.new(0, 0, hillRadius - 4),
		hillRadius * 2,
		HILL:Lerp(HILL_DARK, 0.3),
		Enum.Material.Grass
	)
	local rocks = {
		-- 크기, 로컬 위치(바닥 중앙 기준 가운데), Y 회전, 색
		-- 아래층: 가운데(물길, 앞면 z = -5) + 왼쪽·오른쪽(앞면 z 약 -7)
		{ Vector3.new(12, lowerH, 20), Vector3.new(-1, lowerH / 2, 5), 0, CLIFF },
		{ Vector3.new(18, lowerH * 1.06, 22), Vector3.new(-14, lowerH * 0.53, 4), 0.14, CLIFF_LIGHT },
		{ Vector3.new(17, lowerH * 0.9, 21), Vector3.new(12, lowerH * 0.45, 4.5), -0.12, CLIFF },
		-- 윗층: 가운데(앞면 z = 3) + 양옆
		{ Vector3.new(10, upperH, 16), Vector3.new(-1, ledge + upperH / 2, 11), 0, CLIFF },
		{ Vector3.new(15, upperH * 1.12, 17), Vector3.new(-11, ledge + upperH * 0.56, 10), 0.18, CLIFF_LIGHT },
		{ Vector3.new(14, upperH * 0.88, 16), Vector3.new(9, ledge + upperH * 0.44, 11), -0.15, CLIFF },
		-- 왼쪽 앞 바위(오른쪽은 이웃 언덕이 덮음)
		{ Vector3.new(13, h * 0.3, 13), Vector3.new(-26, h * 0.15, -1), 0.4, CLIFF },
	}
	for _, rock in rocks do
		local size: Vector3 = rock[1]
		local rockCf = cf * CFrame.new(rock[2]) * CFrame.Angles(0, rock[3], 0)
		block(parent, "Cliff", size, rockCf, rock[4], Enum.Material.Slate, true)
		grassCap(parent, size, rockCf)
	end
	-- 물: 윗층 윗면 개울 → 윗단 물줄기 → 아래층 윗면(턱) → 아랫단 물줄기.
	-- 물 윗면은 풀 판(바위 윗면 + 1)보다 0.3 위, 물줄기는 가운데 바위 앞면보다 0.6 앞(양옆 바위보다는 안쪽)
	local waters = {
		{ Vector3.new(6, 0.4, 16.6), Vector3.new(-1, top + 1.1, 10.7) },
		{ Vector3.new(7, upperH - 1.6, 1), Vector3.new(-1, (lowerH + 0.9 + top + 1.3) / 2, 2.4) },
		{ Vector3.new(7, 0.4, 8), Vector3.new(-1, lowerH + 1.1, -1.6) },
		{ Vector3.new(8, lowerH + 1.3, 1), Vector3.new(-1, (lowerH + 1.3) / 2, -5.6) },
	}
	for _, water in waters do
		block(parent, "Waterfall", water[1], cf * CFrame.new(water[2]), WATERFALL, Enum.Material.SmoothPlastic)
	end
	-- 흰 물결 줄(물줄기 앞에 얇게)
	local streaks = {
		{ -2.6, lowerH * 0.55, -6.2, lowerH * 0.7 },
		{ 1.4, lowerH * 0.45, -6.2, lowerH * 0.55 },
		{ 0.8, ledge + 2 + upperH * 0.45, 1.8, upperH * 0.6 },
	}
	for _, streak in streaks do
		block(
			parent,
			"WaterStreak",
			Vector3.new(0.7, streak[4], 0.3),
			cf * CFrame.new(streak[1], streak[2], streak[3]),
			WHITE,
			Enum.Material.SmoothPlastic
		)
	end
	-- 물거품(반쯤 잠긴 흰 공 셋)
	for _, foam in { { -1, -7.5, 6.5 }, { -4.5, -8.5, 4.2 }, { 2.8, -8, 3.6 } } do
		ball(parent, "Splash", cf * Vector3.new(foam[1], 0.1, foam[2]), foam[3], WHITE)
	end
	disc(parent, "Pool", cf * Vector3.new(-1, -0.2, -17), 0.32, 22, POND) -- 윗면 = 들판 + 0.12(개울과 같게)
	-- 물웅덩이 둘레 바위
	for _, stone in { { -12.5, -13, 1.3, 0.5 }, { 9.5, -21, 1, 2.1 }, { -9, -25.5, 0.8, 1.2 } } do
		local s = stone[3]
		block(
			parent,
			"Rock",
			Vector3.new(3.4, 2.2, 2.8) * s,
			cf * CFrame.new(stone[1], 0.6 * s, stone[2]) * CFrame.Angles(0.15, stone[4], -0.1),
			ROCK,
			Enum.Material.Slate,
			true
		)
	end
end

Props.BUILD = BUILD

-- item 하나 만들기. 모르는 종류면 false
function Props.build(parent: Instance, item): boolean
	local build = BUILD[item.Kind]
	if not build then
		return false
	end
	castShadow = SHADOW_KINDS[item.Kind] == true
	build(parent, item)
	castShadow = false
	return true
end

-- 산 면(Plan.Triangle) 하나
function Props.peakFace(parent: Instance, triangle)
	local a = Vector3.new(triangle.A[1], triangle.A[2], triangle.A[3])
	local b = Vector3.new(triangle.B[1], triangle.B[2], triangle.B[3])
	local c = Vector3.new(triangle.C[1], triangle.C[2], triangle.C[3])
	local color = if triangle.Snow then SNOW else PEAK:Lerp(PEAK_DARK, triangle.Tint)
	Props.triangle(parent, if triangle.Snow then "PeakSnow" else "PeakFace", a, b, c, triangle.Thickness, color)
end

-- 곧은 길 조각(Plan.Segment): 윗면 Top, 두께 height. solid 면 걸을 수 있음
function Props.segment(
	parent: Instance,
	name: string,
	segment,
	height: number,
	color: Color3,
	material: Enum.Material,
	solid: boolean?
): Part
	local a = Vector3.new(segment.X1, segment.Top - height / 2, segment.Z1)
	local b = Vector3.new(segment.X2, segment.Top - height / 2, segment.Z2)
	local length = (b - a).Magnitude
	return block(
		parent,
		name,
		Vector3.new(segment.Width, height, length),
		CFrame.lookAt((a + b) / 2, b),
		color,
		material,
		solid
	)
end

return Props
