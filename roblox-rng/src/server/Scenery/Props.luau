-- 풍경 장식 파트 만들기(Plan 의 Item 하나 → 파트 몇 개). 게임 전체와 같은 통통하고 밝은 만화풍이지만
-- Roblox 기본 재질 질감(LeafyGrass 잎, Wood/WoodPlanks 나무, Slate/Rock 바위, Fabric 천, Cobblestone 돌)을 씀.
-- 공·원기둥·상자·쐐기만(메시·데칼·에셋 Id 없음). 모두 Anchored.
-- 잎·꽃·작은 소품은 CanCollide/CanQuery/CanTouch 끔(카메라가 잎에 걸려 당겨지지 않음).
-- 줄기·바위·벤치·건물처럼 부딪혀도 되는 것만 solid(산책로 위에는 Plan 이 두지 않음).
-- 그림자: 나무·덤불·건물처럼 땅 위에 선 것만(SHADOW_KINDS). 그중에도 가장 긴 변이 1.2 보다 작은 조각은 끔.
-- 비탈(숲띠 언덕·모래사장) 위 장식은 Island.height 로 조각마다 발밑 높이를 다시 잼.

local Island = require(script.Parent.Island)
local Rng = require(script.Parent.Rng)

local Props = {}

-- 색 ------------------------------------------------------------------------
local rgb = Color3.fromRGB

local TRUNK = rgb(128, 86, 52)
local TRUNK_DARK = rgb(98, 66, 42)
-- 나무 잎(Style 별: 1 초록, 2 과일나무, 3 단풍, 4 꽃나무). 아래 → 위로 밝아짐
local CANOPY = {
	[1] = { rgb(52, 150, 66), rgb(80, 186, 78), rgb(138, 218, 98) },
	[2] = { rgb(58, 156, 70), rgb(92, 192, 80), rgb(146, 220, 104) },
	[3] = { rgb(206, 72, 52), rgb(236, 118, 56), rgb(250, 176, 74) },
	[4] = { rgb(234, 130, 172), rgb(255, 172, 204), rgb(255, 214, 230) },
	[5] = { rgb(38, 118, 70), rgb(58, 146, 78), rgb(104, 184, 92) }, -- 기둥 나무(짙은 청록빛 초록)
}
local FRUITS = { rgb(255, 150, 40), rgb(232, 62, 62), rgb(255, 204, 60) }
local PALM_TRUNK = rgb(186, 140, 92)
local PALM_RING = rgb(146, 104, 66)
local PALM_LEAF = rgb(58, 172, 82)
local PALM_LEAF_LIGHT = rgb(112, 204, 90)
local COCONUT = rgb(116, 80, 46)
local BUSH = { rgb(50, 142, 64), rgb(78, 180, 76), rgb(132, 214, 96) }
local HEDGE = rgb(62, 158, 70)
local HEDGE_TOP = rgb(92, 184, 82)
local BLOSSOMS = { rgb(255, 128, 176), rgb(255, 250, 240), rgb(255, 214, 72), rgb(180, 130, 255) }
local SOIL = rgb(126, 88, 60)
local ROCK = rgb(160, 158, 156)
local ROCK_DARK = rgb(120, 122, 128)
local MOSS = rgb(98, 160, 72)
local STONE = rgb(214, 208, 196)
local MARBLE = rgb(244, 240, 232)
local WOOD = rgb(196, 138, 82) -- 따뜻한 나무(벤치·부두·가게)
local WOOD_LIGHT = rgb(226, 186, 136)
local WOOD_DARK = rgb(116, 78, 48)
local PAINT_WHITE = rgb(250, 248, 242)
local IRON = rgb(52, 56, 66)
local GARDEN_GREEN = rgb(46, 86, 66) -- 정원등 기둥(광장 가로등보다 짙은 초록·가늘게)
local LAMP_LIGHT = rgb(255, 232, 180)
local WATER = rgb(96, 200, 236)
local WATER_LIGHT = rgb(170, 232, 255)
local LILY = rgb(70, 176, 84)
local PINK = rgb(255, 140, 190)
local WHITE = rgb(255, 252, 245)
local CORAL = rgb(255, 94, 91)
local SUN = rgb(255, 197, 61)
local SKY = rgb(70, 170, 255)
local MINT = rgb(120, 220, 190)
local TEAL = rgb(64, 168, 160)
local SAND = rgb(236, 214, 160)
local RED = rgb(226, 64, 58)
local NAVY = rgb(40, 60, 110)

-- 꽃밭 색 짝(Style 1~6)
local FLOWER_PAIRS = {
	{ CORAL, SUN },
	{ PINK, WHITE },
	{ rgb(170, 120, 255), SUN },
	{ SKY, WHITE },
	{ SUN, CORAL },
	{ PINK, rgb(170, 120, 255) },
}
-- 파라솔·돗자리·배 색(Style)
local CANVAS = { CORAL, SKY, SUN, rgb(120, 200, 120) }

local UPRIGHT = CFrame.Angles(0, 0, math.rad(90)) -- 원기둥(X 축 기둥)을 세움
local ALONG_LOOK = CFrame.Angles(0, math.rad(90), 0) -- lookAt 뒤에 곱하면 원기둥이 앞(-Z) 방향
local UP = Vector3.new(0, 1, 0)

-- 파트 수 세기(구역별) --------------------------------------------------------------
local counts: { [string]: number } = {}
local zone = "Misc"
local castShadow = false -- 지금 만드는 장식이 그림자를 드리우는지(Props.build 가 종류별로 정함)

local SHADOW_KINDS = {
	Tree = true,
	Palm = true,
	Bush = true,
	Hedge = true,
	Topiary = true,
	Rock = true,
	ShoreRock = true,
	Bench = true,
	Lamp = true,
	Fountain = true,
	Gazebo = true,
	PicnicTable = true,
	Arch = true,
	Lantern = true,
	Birdbath = true,
	Lighthouse = true,
	Pier = true,
	Bridge = true,
	Kiosk = true,
	Lifeguard = true,
	BeachSet = true,
	Sandcastle = true,
	Boat = true,
	Crate = true,
	Telescope = true,
	Surfboards = true,
	Driftwood = true,
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
	local size = part.Size
	part.CastShadow = castShadow and math.max(size.X, size.Y, size.Z) >= 1.2
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

local function ball(
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

-- bottom(바닥 중앙)에서 위로 height 만큼 세운 원기둥
local function disc(
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

-- a 에서 b 까지 이어지는 원기둥(지름 d). 완전히 수직인 막대는 disc 를 씀
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
local function wedge(
	parent: Instance,
	name: string,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material?,
	solid: boolean?
): WedgePart
	local piece = Instance.new("WedgePart")
	piece.Size = size
	piece.CFrame = cframe
	setup(piece, parent, name, color, material or Enum.Material.SmoothPlastic, solid)
	return piece
end

Props.wedge = wedge

-- 수평 회전: (x, z) 를 turn 만큼(각도가 커지는 쪽으로) 돌림
local function spin(x: number, z: number, turn: number): (number, number)
	local c, s = math.cos(turn), math.sin(turn)
	return x * c - z * s, x * s + z * c
end

-- 바닥 중앙 base 에서 turn 방향(앞 = LookVector = -Z)을 보는 CFrame
local function heading(base: Vector3, turn: number): CFrame
	return CFrame.lookAt(base, base + Vector3.new(math.cos(turn), 0, math.sin(turn)))
end

local function basePoint(item): Vector3
	return Vector3.new(item.X, item.Y, item.Z)
end

-- 장식마다 고정된 난수(자리로 시드를 정해서 미리보기와 게임이 같음)
local function itemRng(item, salt: number): Rng.Rng
	return Rng.new(math.floor(item.X * 37 + 0.5) * 7919 + math.floor(item.Z * 53 + 0.5) + salt)
end

-- 그 자리 땅 높이(지형): 발밑이 비탈인 조각(선베드·부두 기둥)용
local function groundAt(x: number, z: number): number
	return Island.height(x, z)
end

-- 비탈 위에 눕힌 납작한 물건(수건)의 자리: cf 의 가운데·방향을 쓰고, 네 귀퉁이(반폭 halfX, 반길이 halfZ)
-- 땅 높이로 기울기를 맞춤. 반환 CFrame 의 원점 = 땅 위 가운데, UpVector = 땅의 위쪽
local function onGround(cf: CFrame, halfX: number, halfZ: number): CFrame
	local function at(x: number, z: number): Vector3
		local p = cf * Vector3.new(x, 0, z)
		return Vector3.new(p.X, groundAt(p.X, p.Z), p.Z)
	end
	local a, b = at(-halfX, -halfZ), at(halfX, halfZ)
	local c, d = at(halfX, -halfZ), at(-halfX, halfZ)
	local center = (a + b + c + d) / 4
	local up = (b - a):Cross(c - d).Unit
	if up.Y < 0 then
		up = -up
	end
	local forward = (a + c) / 2 - (b + d) / 2 -- 로컬 -Z 쪽(앞)
	return CFrame.lookAt(center, center + forward, up)
end

local MAT = Enum.Material
local LEAVES = MAT.LeafyGrass

-- 모양별 만들기 --------------------------------------------------------------------
local BUILD = {}

-- 넓은잎나무: 살짝 기운 두 마디 줄기 + 가지 1~2 + 잎 공 5~7(아래는 짙게, 위는 밝게). Style = 잎 색(CANOPY)
-- 과일나무(2)는 잎 둘레에 열매, 크기는 Scale(0.75~1.45)
-- 기둥 나무(Style 5): 짧은 줄기 + 위로 갈수록 작아지는 잎 공 넷을 쌓고(살짝 비뚤게) 아래쪽 옆에 작은 공 둘.
-- 넓은잎나무보다 가늘고 키가 커서 숲 무리의 윤곽이 들쭉날쭉해짐
local function slimTree(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local rng = itemRng(item, 13)
	local colors = CANOPY[5]
	local lean = Vector3.new(math.cos(item.Turn), 0, math.sin(item.Turn)) * 0.05
	rod(
		parent,
		"TreeTrunk",
		base - Vector3.new(0, 0.6, 0),
		base + Vector3.new(0, 3 * s, 0),
		1 * s,
		TRUNK,
		MAT.Wood,
		true
	)
	local y = 3.6
	for k, d in { 3.9, 3.5, 2.9, 2.1 } do
		local jitter = Vector3.new(rng:NextNumber(-0.25, 0.25), 0, rng:NextNumber(-0.25, 0.25)) * s
		local center = base + Vector3.new(0, y * s, 0) + lean * (y * s) + jitter
		ball(parent, "TreeLeaves", center, d * s, colors[1]:Lerp(colors[3], (k - 1) / 4), LEAVES)
		y += d * 0.62
	end
	local start = rng:NextNumber(0, math.pi * 2)
	for k = 1, 2 do
		local a = start + k * math.pi + rng:NextNumber(-0.4, 0.4)
		local offset = Vector3.new(math.cos(a) * 1.3, 4.6 + k * 0.8, math.sin(a) * 1.3) * s
		ball(parent, "TreeLeaves", base + offset, 2.3 * s, colors[2], LEAVES)
	end
end

function BUILD.Tree(parent: Instance, item)
	if item.Style == 5 then
		slimTree(parent, item)
		return
	end
	local s, base = item.Scale, basePoint(item)
	local rng = itemRng(item, 1)
	local colors = CANOPY[item.Style] or CANOPY[1]
	local lean = Vector3.new(math.cos(item.Turn), 0, math.sin(item.Turn)) * (0.06 + 0.1 * item.Tint)
	local knee = base + Vector3.new(0, 3 * s, 0) + lean * (3 * s)
	local top = knee + Vector3.new(0, 2.6 * s, 0) + lean * (4 * s)
	rod(
		parent,
		"TreeTrunk",
		base - Vector3.new(0, 0.6, 0),
		knee + (knee - base).Unit * 0.4 * s,
		1.5 * s,
		TRUNK,
		MAT.Wood,
		true
	)
	rod(parent, "TreeTrunk", knee, top, 1.1 * s, TRUNK, MAT.Wood, true)
	-- 가지: 줄기 위쪽에서 기운 반대쪽으로 비스듬히(끝은 잎 공 속)
	local branches = if item.Scale > 1.2 then 2 else 1
	for k = 1, branches do
		local a = item.Turn + math.pi + (k - 1.5) * 1.6 + rng:NextNumber(-0.3, 0.3)
		local from = knee + (top - knee) * 0.35
		local to = from + Vector3.new(math.cos(a) * 2 * s, 1.6 * s, math.sin(a) * 2 * s)
		rod(parent, "TreeBranch", from, to, 0.5 * s, TRUNK_DARK, MAT.Wood)
	end
	-- 잎: 가운데 큰 공 + 둘레 공(3~5) + 위 밝은 공(1~2)
	local center = top + Vector3.new(0, 1.3 * s, 0)
	ball(parent, "TreeLeaves", center, 6 * s, colors[2], LEAVES)
	local ring = if item.Scale < 0.9 then 3 elseif item.Scale < 1.25 then 4 else 4 + rng:NextInteger(0, 1)
	local start = rng:NextNumber(0, math.pi * 2)
	for k = 1, ring do
		local a = start + (k - 1) / ring * math.pi * 2 + rng:NextNumber(-0.3, 0.3)
		local out = 2.3 * s * rng:NextNumber(0.9, 1.1)
		local lift = rng:NextNumber(-0.9, 0.4) * s
		local offset = Vector3.new(math.cos(a) * out, lift, math.sin(a) * out)
		local color = if lift < -0.3 * s then colors[1] else colors[1]:Lerp(colors[2], 0.6)
		ball(parent, "TreeLeaves", center + offset, rng:NextNumber(3.6, 4.5) * s, color, LEAVES)
	end
	-- 위 밝은 공: 해 쪽(+X, +Z 조금) 으로 치우침
	local tops = if item.Scale > 1.3 then 2 else 1
	for k = 1, tops do
		local a = 0.6 + (k - 1) * 2.4 + rng:NextNumber(-0.4, 0.4)
		local offset = Vector3.new(math.cos(a) * 1.1 * s, 2.1 * s, math.sin(a) * 1.1 * s)
		ball(parent, "TreeLeaves", center + offset, rng:NextNumber(3.2, 3.8) * s, colors[3], LEAVES)
	end
	if item.Style == 2 then
		-- 열매: 잎 겉(위쪽 반구)에 작은 공
		for k = 1, 4 do
			local a = start + k * 1.57 + rng:NextNumber(-0.3, 0.3)
			local up = rng:NextNumber(-0.2, 0.6)
			local dir = Vector3.new(math.cos(a), up, math.sin(a)).Unit
			ball(parent, "Fruit", center + dir * 3.1 * s, 0.75 * s, FRUITS[k % #FRUITS + 1])
		end
	end
end

-- 야자수: 휘어 올라가는 줄기(가늘어지는 원기둥 5마디, 마디 색 살짝 다르게) + 늘어진 잎 6장(잎마다 세 마디:
-- 솟는 잎자루 → 둥글게 휘는 가운데 → 늘어지며 뾰족한 쐐기 끝) + 잎 뭉치 + 코코넛 둘.
-- Turn = 기우는 쪽. Style 2 = 먼 섬용(파트 적게)
function BUILD.Palm(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local rng = itemRng(item, 2)
	local far = item.Style == 2
	local lean = Vector3.new(math.cos(item.Turn), 0, math.sin(item.Turn))
	local height = 9 * s * (0.9 + 0.2 * item.Tint)
	local bend = 3 * s * (0.7 + 0.6 * rng:NextNumber())
	local function trunkAt(t: number): Vector3
		return base + Vector3.new(0, height * t - 0.5, 0) + lean * (bend * t * t)
	end
	local segments = if far then 2 else 5
	for k = 0, segments - 1 do
		local a, b = trunkAt(k / segments), trunkAt((k + 1) / segments)
		local dir = (b - a).Unit
		local d = s * (1.25 - 0.4 * k / (segments - 1))
		-- 마디끼리 조금씩 겹쳐서(아래 마디가 조금 굵음) 이음매가 줄기 마디 고리로 보임. 색은 마디마다 살짝만 다르게
		rod(
			parent,
			"PalmTrunk",
			a - dir * 0.15 * s,
			b + dir * 0.2 * s,
			d,
			PALM_TRUNK:Lerp(PALM_RING, if k % 2 == 0 then 0.1 else 0.3),
			MAT.Wood,
			true
		)
	end
	local crown = trunkAt(1) + Vector3.new(0, 0.2 * s, 0)
	ball(parent, "PalmCrown", crown, 1.5 * s, PALM_LEAF:Lerp(COCONUT, 0.3), LEAVES)
	if not far then
		for k = 1, 2 do
			local a = item.Turn + k * 3.1
			ball(
				parent,
				"Coconut",
				crown + Vector3.new(math.cos(a) * 0.6 * s, -0.55 * s, math.sin(a) * 0.6 * s),
				0.72 * s,
				COCONUT
			)
		end
	end
	local fronds = if far then 7 else 6
	local start = rng:NextNumber(0, math.pi * 2)
	for k = 1, fronds do
		local a = start + (k - 1) / fronds * math.pi * 2 + rng:NextNumber(-0.18, 0.18)
		local length = s * rng:NextNumber(0.85, 1.1)
		local lift = rng:NextNumber(-0.12, 0.1) -- 잎마다 솟는 정도를 조금씩 다르게
		local color = if k % 2 == 0 then PALM_LEAF else PALM_LEAF:Lerp(PALM_LEAF_LIGHT, 0.5)
		local out = Vector3.new(math.cos(a), 0, math.sin(a))
		local p1 = crown + out * 0.3 * s
		local function piece(from: Vector3, to: Vector3): CFrame
			return CFrame.lookAt((from + to) / 2, to, UP)
		end
		if far then
			-- 두 마디(솟는 넓은 잎 → 늘어지는 뾰족한 끝): 멀리 옆에서 봐도 잎이 보이게(납작하게 누우면 막대만 보임)
			local p2 = p1 + (out * 0.85 + Vector3.new(0, 0.42 + lift, 0)).Unit * 3 * length
			local p3 = p2 + (out * 0.7 + Vector3.new(0, -0.72, 0)).Unit * 3.2 * length
			block(
				parent,
				"PalmLeaf",
				Vector3.new(1.9 * s, 0.2 * s, (p2 - p1).Magnitude + 0.3 * s),
				piece(p1, p2),
				color,
				LEAVES
			)
			wedge(
				parent,
				"PalmLeafTip",
				Vector3.new(0.2 * s, 1.9 * s, (p3 - p2).Magnitude + 0.3 * s),
				piece(p2, p3) * CFrame.Angles(0, 0, math.rad(90)),
				color:Lerp(PALM_LEAF_LIGHT, 0.3),
				LEAVES
			)
			continue
		end
		-- 세 마디(솟는 잎자루 → 둥글게 휘는 가운데 → 늘어지며 뾰족해지는 끝): 마디마다 조금씩 겹쳐 이음매를 덮음
		local p2 = p1 + (out * 0.88 + Vector3.new(0, 0.5 + lift, 0)).Unit * 2.2 * length
		local p3 = p2 + (out + Vector3.new(0, 0.02 + lift, 0)).Unit * 2.5 * length
		local p4 = p3 + (out * 0.66 + Vector3.new(0, -0.75, 0)).Unit * 2.6 * length
		block(
			parent,
			"PalmLeaf",
			Vector3.new(0.9 * s, 0.14 * s, (p2 - p1).Magnitude + 0.3 * s),
			piece(p1, p2),
			color:Lerp(COCONUT, 0.15),
			LEAVES
		)
		block(
			parent,
			"PalmLeaf",
			Vector3.new(1.7 * s, 0.14 * s, (p3 - p2).Magnitude + 0.35 * s),
			piece(p2, p3),
			color,
			LEAVES
		)
		-- 끝: 쐐기를 잎 면에 눕힘(넓은 쪽이 이음매, 뾰족한 쪽이 끝)
		wedge(
			parent,
			"PalmLeafTip",
			Vector3.new(0.14 * s, 1.7 * s, (p4 - p3).Magnitude + 0.25 * s),
			piece(p3, p4) * CFrame.Angles(0, 0, math.rad(90)),
			color:Lerp(PALM_LEAF_LIGHT, 0.3),
			LEAVES
		)
	end
end

-- 잎 공(가운데 center, 지름 size) 겉에 반쯤 박힌 작은 꽃 count 송이(윗쪽 반구에 고루, 두 색 번갈아)
local function blossoms(
	parent: Instance,
	center: Vector3,
	size: number,
	count: number,
	flower: number,
	colors: { Color3 },
	rng: Rng.Rng
)
	local start = rng:NextNumber(0, math.pi * 2)
	for k = 1, count do
		local a = start + k / count * math.pi * 2 + rng:NextNumber(-0.35, 0.35)
		local up = rng:NextNumber(0.35, 0.95)
		local dir = Vector3.new(math.cos(a) * math.sqrt(1 - up * up), up, math.sin(a) * math.sqrt(1 - up * up))
		local d = flower * rng:NextNumber(0.85, 1.1)
		ball(parent, "Flower", center + dir * (size / 2 - d * 0.2), d, colors[k % #colors + 1])
	end
end

-- 덤불: 공 4개 뭉치(짙은 초록 → 밝은 초록). Style 2~4 = 꽃 덤불(겉에 작은 꽃 세 송이: 분홍/하양/노랑)
function BUILD.Bush(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local rng = itemRng(item, 3)
	local t = item.Turn
	local pieces = {
		{ 0, 0, 1.05, 3.1, BUSH[2] },
		{ 1.1, 0.6, 0.8, 2.3, BUSH[1] },
		{ -1.0, 0.9, 0.75, 2.2, BUSH[1]:Lerp(BUSH[2], 0.5) },
		{ 0.3, -0.4, 1.9, 1.9, BUSH[3] },
	}
	for _, p in pieces do
		local ox, oz = spin(p[1], p[2], t)
		ball(parent, "Bush", base + Vector3.new(ox * s, p[3] * s, oz * s), p[4] * s, p[5], LEAVES)
	end
	-- 꽃 덤불(Style 2~4): 가운데 큰 공 겉에 작은 꽃 세 송이(분홍/하양/노랑)
	if item.Style >= 2 then
		local color = BLOSSOMS[(item.Style - 2) % #BLOSSOMS + 1]
		local center = base + Vector3.new(0, 1.05 * s, 0)
		blossoms(parent, center, 3.1 * s, 3, 0.6 * s, { color, color:Lerp(WHITE, 0.35) }, rng)
	end
end

-- 산울타리: 길이 Height 인 잎 판 + 위를 둥글게 덮는 원기둥. Turn = 길이 방향.
-- Style 2 = 조금 짙은 초록, 3 = 꽃 핀 산울타리(둥근 윗면에 작은 꽃이 드문드문, 색은 Tint)
function BUILD.Hedge(parent: Instance, item)
	local length = item.Height
	local cf = CFrame.new(basePoint(item)) * CFrame.Angles(0, -item.Turn, 0)
	local dark = if item.Style == 2 then 0.25 else 0
	block(
		parent,
		"Hedge",
		Vector3.new(length, 1.5, 1.7),
		cf * CFrame.new(0, 0.55, 0),
		HEDGE:Lerp(BUSH[1], dark),
		LEAVES,
		true
	)
	part(
		parent,
		"HedgeTop",
		Enum.PartType.Cylinder,
		Vector3.new(length, 1.7, 1.7),
		cf * CFrame.new(0, 1.3, 0),
		HEDGE_TOP:Lerp(BUSH[2], dark),
		LEAVES
	)
	if item.Style == 3 then
		local rng = itemRng(item, 12)
		local color = BLOSSOMS[math.floor(item.Tint * #BLOSSOMS) % #BLOSSOMS + 1]
		local count = math.max(2, math.floor(length / 2.2))
		for k = 1, count do
			local along = (k - 0.5) / count * length - length / 2 + rng:NextNumber(-0.5, 0.5)
			local around = rng:NextNumber(-0.9, 0.9) -- 둥근 윗면 위 각도(0 = 꼭대기)
			local offset = Vector3.new(along, 1.3 + math.cos(around) * 0.8, math.sin(around) * 0.8)
			ball(parent, "Flower", (cf * CFrame.new(offset)).Position, 0.5, if k % 3 == 0 then WHITE else color)
		end
	end
end

-- 꽃밭 두 가지(Style 로 정함, 같은 모양이 줄지어 반복되지 않게):
--   돌 테두리 꽃밭(Style 1, 2, 4, 5): 흙 + 둘레에 손으로 쌓은 듯한 납작 돌(크기·각도·색이 조금씩 다름, 원이 아니라 울퉁불퉁)
--     + 낮은 잎 둔덕 셋 + 둔덕마다 겉에 박힌 작은 꽃 두세 송이(두 색)
--   들꽃 무더기(Style 3, 6): 테두리·흙 없이 잔디 위에 크기가 다른 잎 둔덕 4~5개를 비뚤게 모으고 꽃을 많이
function BUILD.FlowerBed(parent: Instance, item)
	local r, base = item.Radius, basePoint(item)
	local rng = itemRng(item, 4)
	local colors = FLOWER_PAIRS[(item.Style - 1) % #FLOWER_PAIRS + 1]
	local flower = math.clamp(r * 0.2, 0.5, 0.72)
	if item.Style % 3 == 0 then
		local mounds = if r > 3 then 5 else 4
		for k = 1, mounds do
			local a = item.Turn + k / mounds * math.pi * 2 + rng:NextNumber(-0.4, 0.4)
			local d = if k == 1 then 0 else r * rng:NextNumber(0.35, 0.62)
			local size = r * (if k == 1 then 0.95 else rng:NextNumber(0.55, 0.8))
			local x, z = base.X + math.cos(a) * d, base.Z + math.sin(a) * d
			-- 숲띠 언덕 비탈이면 둔덕마다 발밑(가운데 + 둘레 넷) 가장 높은 땅에 맞춤(아래쪽 꽃이 땅에 묻히지 않게)
			local ground = math.max(base.Y, groundAt(x, z))
			for q = 0, 3 do
				local qa = q * math.pi / 2
				ground = math.max(ground, groundAt(x + math.cos(qa) * size * 0.45, z + math.sin(qa) * size * 0.45))
			end
			local center = Vector3.new(x, ground - size * 0.18, z)
			ball(parent, "FlowerLeaves", center, size, BUSH[1]:Lerp(BUSH[3], rng:NextNumber(0.1, 0.45)), LEAVES)
			blossoms(parent, center, size, if k == 1 then 3 else 2, flower * 0.95, { colors[1], colors[2] }, rng)
		end
		return
	end
	disc(parent, "FlowerSoil", base - Vector3.new(0, 0.3, 0), 0.55, r * 2, SOIL, MAT.Ground)
	-- 테두리 돌: 둘레를 따라 한 줄(돌마다 반지름·높이·방향을 조금씩 흔듦)
	local stones = math.max(8, math.floor(r * 2 * math.pi / 1.7 + 0.5))
	local start = rng:NextNumber(0, math.pi * 2)
	for k = 1, stones do
		local a = start + k / stones * math.pi * 2 + rng:NextNumber(-0.08, 0.08)
		local d = r + 0.15 + rng:NextNumber(-0.12, 0.12)
		local length = 2 * math.pi * r / stones * rng:NextNumber(1.05, 1.3)
		local height = rng:NextNumber(0.5, 0.75)
		block(
			parent,
			"FlowerEdge",
			Vector3.new(0.85, height, length),
			CFrame.new(base.X + math.cos(a) * d, base.Y - 0.2 + height / 2, base.Z + math.sin(a) * d)
				* CFrame.Angles(0, -a + rng:NextNumber(-0.15, 0.15), 0)
				* CFrame.Angles(rng:NextNumber(-0.1, 0.1), 0, rng:NextNumber(-0.12, 0.12)),
			STONE:Lerp(ROCK, rng:NextNumber(0, 0.45)),
			MAT.Slate
		)
	end
	local soilTop = base.Y + 0.25
	for k = 1, 3 do
		local a = item.Turn + k / 3 * math.pi * 2 + rng:NextNumber(-0.25, 0.25)
		local d = r * 0.44
		local size = r * rng:NextNumber(0.95, 1.05)
		local center = Vector3.new(base.X + math.cos(a) * d, soilTop - size * 0.12, base.Z + math.sin(a) * d)
		ball(parent, "FlowerLeaves", center, size, BUSH[1]:Lerp(BUSH[2], 0.25 + 0.2 * k), LEAVES)
		blossoms(parent, center, size, if k == 1 then 3 else 2, flower, { colors[1], colors[2] }, rng)
	end
end

-- 토피어리(화분 + 다듬은 나무). Style 1 막대 사탕, 2 공 두 개, 3 세 단 원뿔(공 셋)
function BUILD.Topiary(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	disc(parent, "TopiaryPot", base, 0.9 * s, 1.5 * s, rgb(214, 110, 72), MAT.Brick, true)
	local green = HEDGE:Lerp(BUSH[1], 0.2)
	if item.Style == 3 then
		ball(parent, "Topiary", base + Vector3.new(0, 1.9 * s, 0), 2.7 * s, green, LEAVES)
		ball(parent, "Topiary", base + Vector3.new(0, 3.5 * s, 0), 2 * s, green:Lerp(BUSH[2], 0.4), LEAVES)
		ball(parent, "Topiary", base + Vector3.new(0, 4.7 * s, 0), 1.3 * s, BUSH[3], LEAVES)
		return
	end
	disc(parent, "TopiaryStem", base + Vector3.new(0, 0.8 * s, 0), 2 * s, 0.35 * s, WOOD_DARK, MAT.Wood, true)
	ball(parent, "Topiary", base + Vector3.new(0, 3.4 * s, 0), 2.5 * s, green, LEAVES)
	if item.Style == 2 then
		ball(parent, "Topiary", base + Vector3.new(0, 5.1 * s, 0), 1.5 * s, BUSH[3], LEAVES)
	end
end

-- 둥근 바윗돌 하나: 크기가 다른 공 셋(가운데 큰 공 + 옆으로 비킨 작은 공 둘)을 겹쳐 아래를 땅에 묻음.
-- 윗부분만 보여서 낮고 넓적한 바위 덩어리(모난 상자보다 게임 전체의 통통한 모양과 어울림). center = 바닥 가운데
local function boulder(parent: Instance, name: string, center: Vector3, size: number, rng: Rng.Rng, tint: number)
	local color = ROCK:Lerp(ROCK_DARK, tint)
	ball(parent, name, center + Vector3.new(0, 0.05 * size, 0), 1.25 * size, color, MAT.Rock, true)
	local start = rng:NextNumber(0, math.pi * 2)
	for k = 1, 2 do
		local a = start + k * 2.5 + rng:NextNumber(-0.4, 0.4)
		local d = size * rng:NextNumber(0.42, 0.55)
		local ds = size * rng:NextNumber(0.72, 0.9)
		local x, z = center.X + math.cos(a) * d, center.Z + math.sin(a) * d
		-- 옆 공 자리의 땅이 더 높으면(지형 바위 턱 비탈) 그만큼 올림: 땅속에 다 묻히지 않게
		local y = math.max(center.Y - 0.12 * size, groundAt(x, z) - 0.2 * ds)
		ball(
			parent,
			name,
			Vector3.new(x, y, z),
			ds,
			color:Lerp(if k == 1 then ROCK_DARK else STONE, 0.25),
			if k == 1 then MAT.Slate else MAT.Rock,
			true
		)
	end
end

-- 바위: 둥근 바윗돌(몸통, 아래 반쯤 묻음) + 옆 작은 돌 1~2 + 윗면 이끼. 회색 두세 가지를 섞음
function BUILD.Rock(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local rng = itemRng(item, 5)
	local t = item.Turn
	-- 비탈(숲띠 언덕)이면 조각마다 그 자리 땅 높이에 맞춤(윗쪽 조각이 땅에 묻히지 않게)
	local function floorAt(ox: number, oz: number): number
		return math.max(base.Y, groundAt(base.X + ox, base.Z + oz))
	end
	local size = 2.4 * s
	boulder(parent, "Rock", Vector3.new(base.X, floorAt(0, 0) - 0.25 * size, base.Z), size, rng, 0.2 + item.Tint * 0.4)
	for k = 1, math.min(item.Style, 2) do
		local ox, oz = spin(if k == 1 then 2.2 else -1.9, if k == 1 then 1.1 else -1.4, t)
		local d = s * rng:NextNumber(0.9, 1.3)
		ball(
			parent,
			"Rock",
			Vector3.new(base.X + ox * s, floorAt(ox * s, oz * s) - 0.1 * d, base.Z + oz * s),
			d,
			ROCK:Lerp(if k == 1 then ROCK_DARK else STONE, 0.4),
			MAT.Slate,
			true
		)
	end
	-- 이끼: 몸통 윗면(해 반대쪽)에 반쯤 박힌 납작한 초록 공
	local mx, mz = spin(-0.35, 0.3, t)
	ball(
		parent,
		"Moss",
		Vector3.new(base.X + mx * size, floorAt(0, 0) + 0.3 * size, base.Z + mz * size),
		0.7 * size,
		MOSS,
		LEAVES
	)
end

-- 물가 바위 무더기: 지형 바위 턱(낮고 울퉁불퉁한 둔덕) 위에 크고 작은 둥근 바윗돌 셋(열대 바닷가의 매끈한 화강암처럼,
-- 아래 반쯤은 턱·물속에 묻힘). 따뜻한 회색 셋을 섞음. Scale = 지형 바위 반지름, Height = 지형 바위 꼭대기 높이
local GRANITE = { rgb(164, 156, 146), rgb(138, 136, 132), rgb(178, 168, 156) }
function BUILD.ShoreRock(parent: Instance, item)
	local r, top = item.Scale, item.Height
	local rng = itemRng(item, 11)
	local t = item.Turn
	local stones = {
		{ 0, 0, 0.66 }, -- 옆, 옆(바위 반지름 비율), 크기(비율)
		{ 0.62, 0.3, 0.44 },
		{ -0.5, -0.42, 0.36 },
	}
	for k, stone in stones do
		local ox, oz = spin(stone[1] * r, stone[2] * r, t)
		local x, z = item.X + ox, item.Z + oz
		local size = stone[3] * r
		local floor = math.max(math.min(top, groundAt(x, z)), Island.WATER_LEVEL - 0.2 * size)
		local color = GRANITE[k]
		ball(parent, "ShoreRock", Vector3.new(x, floor - 0.1 * size, z), 1.2 * size, color, MAT.Rock, true)
		-- 옆에 붙은 작은 공(둥근 돌 두 개가 붙은 모양): 바위마다 방향이 다름
		local a = t + k * 2.1 + rng:NextNumber(-0.5, 0.5)
		local d = 0.5 * size
		local px, pz = x + math.cos(a) * d, z + math.sin(a) * d
		local pfloor = math.max(math.min(top, groundAt(px, pz)), Island.WATER_LEVEL - 0.2 * size)
		ball(
			parent,
			"ShoreRock",
			Vector3.new(px, pfloor - 0.2 * size, pz),
			0.85 * size,
			color:Lerp(ROCK_DARK, 0.2),
			MAT.Rock,
			true
		)
	end
end

-- 정원등: 가는 짙은 초록 기둥 + 등 + 모자(광장 가로등보다 가늘고 낮게, 따뜻한 빛)
function BUILD.Lamp(parent: Instance, item)
	local base = basePoint(item)
	disc(parent, "LampPost", base, 6.6, 0.42, GARDEN_GREEN, MAT.Metal, true)
	local bulb = ball(parent, "LampBulb", base + Vector3.new(0, 7, 0), 1.3, LAMP_LIGHT, MAT.Neon)
	disc(parent, "LampCap", base + Vector3.new(0, 7.55, 0), 0.3, 1.6, GARDEN_GREEN, MAT.Metal)
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 14
	light.Brightness = 0.9
	light.Parent = bulb
end

-- 벤치: 나무판 앉는 판 + 등받이 + 쇠 다리 둘. Turn = 앉은 사람이 보는 쪽
function BUILD.Bench(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	block(parent, "BenchSeat", Vector3.new(5, 0.35, 1.6), cf * CFrame.new(0, 1.5, 0), WOOD, MAT.WoodPlanks, true)
	block(
		parent,
		"BenchBack",
		Vector3.new(5, 1.2, 0.3),
		cf * CFrame.new(0, 2.5, 0.78) * CFrame.Angles(math.rad(-10), 0, 0),
		WOOD,
		MAT.WoodPlanks,
		true
	)
	for _, x in { -2.1, 2.1 } do
		block(parent, "BenchLeg", Vector3.new(0.35, 1.4, 1.5), cf * CFrame.new(x, 0.7, 0.05), IRON, MAT.Metal, true)
		-- 등받이를 받치는 쇠 기둥(앉는 판 뒤 가장자리 → 등받이 위까지, 등받이와 같이 뒤로 기움)
		block(
			parent,
			"BenchFrame",
			Vector3.new(0.3, 1.9, 0.3),
			cf * CFrame.new(x, 2.25, 0.62) * CFrame.Angles(math.rad(-10), 0, 0),
			IRON,
			MAT.Metal,
			true
		)
	end
end

-- 3단 분수: 대리석 수반(찰랑이는 물) + 기둥 + 가운데 접시(물) + 위 작은 접시 + 물줄기
function BUILD.Fountain(parent: Instance, item)
	local r, base = item.Radius, basePoint(item)
	disc(parent, "FountainBasin", base, 1.3, r * 2, MARBLE, MAT.Marble, true)
	local water = disc(parent, "FountainWater", base + Vector3.new(0, 0.2, 0), 1.0, r * 2 - 1.2, WATER, MAT.Glass)
	water.Transparency = 0.25
	disc(parent, "FountainColumn", base, 3.4, 1.4, MARBLE, MAT.Marble, true)
	disc(parent, "FountainBowl", base + Vector3.new(0, 3.2, 0), 0.5, 4.6, MARBLE, MAT.Marble)
	local bowlWater = disc(parent, "FountainWater", base + Vector3.new(0, 3.3, 0), 0.45, 4, WATER, MAT.Glass)
	bowlWater.Transparency = 0.25
	disc(parent, "FountainColumn", base + Vector3.new(0, 3.6, 0), 1.7, 0.8, MARBLE, MAT.Marble)
	disc(parent, "FountainBowl", base + Vector3.new(0, 5.2, 0), 0.4, 2.3, MARBLE, MAT.Marble)
	local jet = ball(parent, "FountainJet", base + Vector3.new(0, 6.1, 0), 1.3, WATER_LIGHT, MAT.Glass)
	jet.Transparency = 0.3
	-- 가운데 접시에서 떨어지는 물(반투명 원기둥 벽 대신 얇은 물줄기 넷)
	for k = 0, 3 do
		local a = item.Turn + k * math.pi / 2
		local p = base + Vector3.new(math.cos(a) * 2.2, 0, math.sin(a) * 2.2)
		local fall = block(
			parent,
			"FountainFall",
			Vector3.new(0.5, 2.2, 0.12),
			CFrame.lookAt(p + Vector3.new(0, 2.2, 0), base + Vector3.new(0, 2.2, 0)),
			WATER_LIGHT,
			MAT.Glass
		)
		fall.Transparency = 0.35
	end
end

-- 지형 연못 꾸밈(물은 지형): 둘레 납작 돌(다리 자리는 비움) + 수련 잎·꽃 + 부들 두 무더기.
-- Scale = 연못 반지름, Height = 연못 시드(Island.pondRadius 와 같은 구불구불 가장자리)
function BUILD.PondDeco(parent: Instance, item)
	local r, base, t = item.Scale, basePoint(item), item.Turn
	local rng = itemRng(item, 6)
	local pond = { X = item.X, Z = item.Z, R = r, Depth = 0, Seed = item.Height }
	for k = 0, 13 do
		local a = t + (k + 0.5) / 14 * math.pi * 2
		-- 다리(Turn 방향 앞뒤)와 겹치는 돌은 뺌
		local across = math.abs(math.sin(a - t))
		if across > 0.3 then
			local edge = Island.pondRadius(pond, a) + 0.4
			local size = rng:NextNumber(1.5, 2.3)
			block(
				parent,
				"PondStone",
				Vector3.new(size, 0.7, size * rng:NextNumber(0.7, 1)),
				CFrame.new(base + Vector3.new(math.cos(a) * edge, 0.05, math.sin(a) * edge))
					* CFrame.Angles(rng:NextNumber(-0.12, 0.12), rng:NextNumber(0, 6.28), rng:NextNumber(-0.12, 0.12)),
				STONE:Lerp(ROCK, rng:NextNumber()),
				MAT.Slate,
				true
			)
		end
	end
	local pads = 0
	for k = 1, 12 do
		if pads >= 6 then
			break
		end
		local a = rng:NextNumber(0, math.pi * 2)
		local d = r * rng:NextNumber(0.3, 0.72)
		local side = math.abs(math.sin(a - t)) * d
		if side > 3.4 then
			pads += 1
			local p = base + Vector3.new(math.cos(a) * d, 0, math.sin(a) * d)
			-- 물 윗면(0) 위로 살짝(잔물결에 가려지지 않게)
			disc(parent, "LilyPad", p + Vector3.new(0, 0.04, 0), 0.1, rng:NextNumber(1.5, 2.2), LILY, LEAVES)
			if pads % 3 == 1 then
				ball(parent, "LilyFlower", p + Vector3.new(0, 0.3, 0), 0.65, PINK)
			end
		end
	end
	-- 부들(줄기 + 갈색 이삭) 두 무더기: 다리 옆쪽 물가
	for _, side in { -1, 1 } do
		local a = t + side * math.rad(118)
		local edge = Island.pondRadius(pond, a) - 0.8
		for k = 1, 2 do
			local p = base + Vector3.new(math.cos(a + k * 0.09) * edge, 0, math.sin(a + k * 0.09) * edge)
			local h = 2.2 + k * 0.5
			disc(parent, "Reed", p - Vector3.new(0, 0.5, 0), h + 0.5, 0.16, LILY:Lerp(BUSH[1], 0.4))
			disc(parent, "Cattail", p + Vector3.new(0, h - 0.9, 0), 0.8, 0.38, COCONUT)
		end
	end
end

-- 연못 위 아치 나무다리: 오르막 + 평평한 가운데 + 내리막(윗면 최고 1.2) + 양옆 난간(기둥 + 손잡이)
function BUILD.Bridge(parent: Instance, item)
	local length, width = item.Height, 4.6
	local cf = heading(basePoint(item), item.Turn)
	local rise, third = 1.2, length / 3
	local slope = math.atan2(rise, third)
	local rampLength = math.sqrt(third * third + rise * rise)
	-- 로컬 -Z = 앞. 오르막(뒤 → 가운데), 가운데, 내리막
	local deck = {
		{ cf * CFrame.new(0, rise / 2, third) * CFrame.Angles(slope, 0, 0), rampLength },
		{ cf * CFrame.new(0, rise, 0), third },
		{ cf * CFrame.new(0, rise / 2, -third) * CFrame.Angles(-slope, 0, 0), rampLength },
	}
	for _, piece in deck do
		block(
			parent,
			"BridgeDeck",
			Vector3.new(width, 0.4, piece[2] + 0.25),
			piece[1] * CFrame.new(0, -0.2, 0),
			WOOD,
			MAT.WoodPlanks,
			true
		)
		for _, side in { -1, 1 } do
			block(
				parent,
				"BridgeRail",
				Vector3.new(0.25, 0.25, piece[2]),
				piece[1] * CFrame.new(side * (width / 2 - 0.15), 2.2, 0),
				WOOD_LIGHT,
				MAT.Wood,
				true
			)
		end
	end
	for _, z in { third * 1.5, third * 0.5, -third * 0.5, -third * 1.5 } do
		local y = if math.abs(z) < third then rise else rise * (1.5 - math.abs(z) / third) * 2 / 2
		for _, side in { -1, 1 } do
			disc(
				parent,
				"BridgePost",
				(cf * CFrame.new(side * (width / 2 - 0.15), y - 1.5, z)).Position,
				3.7,
				0.4,
				WOOD_DARK,
				MAT.Wood,
				true
			)
		end
	end
end

-- 징검돌 다섯(납작 돌, 살짝 휘어진 줄). Turn = 줄 방향
function BUILD.Stones(parent: Instance, item)
	local base = basePoint(item)
	local rng = itemRng(item, 7)
	for k = -2, 2 do
		local along = k * 1.8
		local side = math.sin(k * 0.9) * 0.6
		local ox, oz = spin(along, side, item.Turn)
		disc(
			parent,
			"SteppingStone",
			base + Vector3.new(ox, -0.2, oz),
			0.34,
			rng:NextNumber(1.25, 1.6),
			STONE:Lerp(ROCK, rng:NextNumber(0, 0.5)),
			MAT.Slate,
			true
		)
	end
end

-- 소풍 돗자리: 격자무늬(흰 줄 가로·세로 둘씩) + 바구니(뚜껑) + 접시 둘 + 과일
function BUILD.Blanket(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	local color = if item.Style == 2 then SKY else RED
	-- 땅(지형 윗면 0)에서 0.05 띄움: 지형 면과 겹쳐 깜빡이지 않게. 줄끼리도 윗면 0.03 씩 차이
	block(parent, "Blanket", Vector3.new(4.4, 0.08, 3.6), cf * CFrame.new(0, 0.09, 0), color, MAT.Fabric)
	for _, x in { -1.1, 1.1 } do
		block(parent, "BlanketStripe", Vector3.new(0.5, 0.1, 3.6), cf * CFrame.new(x, 0.11, 0), WHITE, MAT.Fabric)
	end
	for _, z in { -0.9, 0.9 } do
		block(parent, "BlanketStripe", Vector3.new(4.4, 0.1, 0.5), cf * CFrame.new(0, 0.14, z), WHITE, MAT.Fabric)
	end
	block(parent, "Basket", Vector3.new(1.3, 0.8, 0.9), cf * CFrame.new(1.2, 0.45, -0.6), WOOD, MAT.WoodPlanks)
	block(parent, "BasketLid", Vector3.new(1.4, 0.15, 1), cf * CFrame.new(1.2, 0.9, -0.6), WOOD_DARK, MAT.WoodPlanks)
	for _, x in { -1.2, -0.1 } do
		disc(parent, "Plate", (cf * CFrame.new(x, 0.13, 0.5)).Position, 0.1, 0.9, WHITE, MAT.SmoothPlastic)
	end
	ball(parent, "Fruit", (cf * CFrame.new(-1.2, 0.35, 0.5)).Position, 0.45, FRUITS[2])
end

-- 파라솔: 기둥 + 팔각 원뿔 지붕(쐐기 여덟 장, 색·하양 번갈아 = 줄무늬) + 꼭지 공
local UMBRELLA_RADIUS = 3.9
local UMBRELLA_RISE = 1.7 -- 지붕 가장자리 → 꼭대기
local UMBRELLA_RIM = 5.2 -- 지붕 가장자리 높이(발밑 기준)
local function umbrella(parent: Instance, base: Vector3, turn: number, color: Color3)
	disc(
		parent,
		"UmbrellaPole",
		base - Vector3.new(0, 0.6, 0),
		UMBRELLA_RIM + UMBRELLA_RISE + 0.3,
		0.3,
		PAINT_WHITE,
		MAT.Wood,
		true
	)
	local width = 2 * UMBRELLA_RADIUS * math.tan(math.pi / 8) * 1.02
	for k = 0, 7 do
		local a = turn + (k + 0.5) / 8 * math.pi * 2
		local out = Vector3.new(math.cos(a), 0, math.sin(a))
		-- 쐐기 높은 면(+Z)이 기둥 쪽, 비탈이 바깥(-Z)을 봄
		local center = base + Vector3.new(0, UMBRELLA_RIM + UMBRELLA_RISE / 2, 0) + out * (UMBRELLA_RADIUS / 2)
		wedge(
			parent,
			"UmbrellaCanopy",
			Vector3.new(width, UMBRELLA_RISE, UMBRELLA_RADIUS),
			CFrame.lookAt(center, center + out),
			if k % 2 == 0 then color else WHITE,
			MAT.Fabric
		)
	end
	ball(parent, "UmbrellaTop", base + Vector3.new(0, UMBRELLA_RIM + UMBRELLA_RISE + 0.1, 0), 0.7, WHITE)
end

-- 소풍 탁자: 나무판 윗판 + 긴 의자 둘 + A자 다리 둘 + 가운데 줄무늬 파라솔. Turn = 탁자 길이에 수직
function BUILD.PicnicTable(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	block(parent, "PicnicTop", Vector3.new(5.6, 0.35, 2.6), cf * CFrame.new(0, 2.3, 0), WOOD, MAT.WoodPlanks, true)
	for _, z in { -2.2, 2.2 } do
		block(parent, "PicnicSeat", Vector3.new(5.6, 0.3, 0.9), cf * CFrame.new(0, 1.3, z), WOOD, MAT.WoodPlanks, true)
	end
	for _, x in { -2.2, 2.2 } do
		block(parent, "PicnicLeg", Vector3.new(0.4, 2.1, 5), cf * CFrame.new(x, 1.05, 0), WOOD_DARK, MAT.Wood, true)
	end
	umbrella(parent, basePoint(item), item.Turn, CORAL)
end

-- 장미 아치(오솔길 위): 흰 기둥 둘 + 둥근 윗부분(세 토막) + 잎 뭉치 + 장미. Turn = 오솔길 방향
function BUILD.Arch(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	local half = 3.3
	for _, side in { -1, 1 } do
		disc(parent, "ArchPost", (cf * CFrame.new(side * half, 0, 0)).Position, 4.6, 0.35, PAINT_WHITE, MAT.Wood, true)
	end
	-- 반원(4.6 위에서 반지름 half): 60도씩 세 토막
	local points = {}
	for k = 0, 3 do
		local a = math.pi - k / 3 * math.pi
		table.insert(points, (cf * CFrame.new(math.cos(a) * half, 4.6 + math.sin(a) * half * 0.8, 0)).Position)
	end
	for k = 1, 3 do
		rod(parent, "ArchTop", points[k], points[k + 1], 0.35, PAINT_WHITE, MAT.Wood)
	end
	local roses = { PINK, CORAL, WHITE }
	for k = 0, 6 do
		local a = math.pi - (k + 0.5) / 7 * math.pi
		local p = (cf * CFrame.new(math.cos(a) * half, 4.6 + math.sin(a) * half * 0.8, (k % 2 - 0.5) * 0.4)).Position
		if k % 2 == 0 then
			ball(parent, "ArchLeaves", p, 1.2, BUSH[2], LEAVES)
		else
			ball(parent, "Rose", p + Vector3.new(0, 0.2, 0), 0.7, roses[k % 3 + 1])
		end
	end
	for _, side in { -1, 1 } do
		ball(parent, "ArchLeaves", (cf * CFrame.new(side * half, 2.2, 0)).Position, 1.1, BUSH[1], LEAVES)
		ball(parent, "Rose", (cf * CFrame.new(side * half, 2.9, -0.4)).Position, 0.6, PINK)
	end
end

-- 새 물통: 대리석 기둥 + 접시 + 물 + 작은 새(몸통 + 머리 + 부리)
function BUILD.Birdbath(parent: Instance, item)
	local base = basePoint(item)
	disc(parent, "BirdbathFoot", base, 0.4, 1.4, MARBLE, MAT.Marble, true)
	disc(parent, "BirdbathPillar", base, 2.4, 0.7, MARBLE, MAT.Marble, true)
	disc(parent, "BirdbathBowl", base + Vector3.new(0, 2.4, 0), 0.4, 2.4, MARBLE, MAT.Marble, true)
	disc(parent, "BirdbathWater", base + Vector3.new(0, 2.45, 0), 0.4, 2, WATER, MAT.Glass)
	local cf = heading(base + Vector3.new(0, 2.8, 0), item.Turn) * CFrame.new(0.85, 0, 0)
	ball(parent, "Bird", (cf * CFrame.new(0, 0.2, 0)).Position, 0.5, SKY)
	ball(parent, "BirdHead", (cf * CFrame.new(0, 0.5, -0.2)).Position, 0.34, SKY)
	block(parent, "BirdBeak", Vector3.new(0.1, 0.1, 0.22), cf * CFrame.new(0, 0.5, -0.43), SUN)
end

-- 과일 상자: 나무 상자 + 위에 과일 다섯
function BUILD.Crate(parent: Instance, item)
	local cf = heading(basePoint(item), item.Turn)
	block(parent, "Crate", Vector3.new(2.4, 1.1, 1.6), cf * CFrame.new(0, 0.55, 0), WOOD_LIGHT, MAT.WoodPlanks, true)
	for k = 0, 4 do
		local x = -0.8 + (k % 3) * 0.8
		local z = if k < 3 then -0.3 else 0.35
		ball(
			parent,
			"Fruit",
			(cf * CFrame.new(x + (if k >= 3 then 0.4 else 0), 1.25, z)).Position,
			0.6,
			FRUITS[k % 3 + 1]
		)
	end
end

-- 석등(바위 정원): 받침 + 기둥 + 불 상자(안에 빛) + 넓은 지붕 + 꼭지
function BUILD.Lantern(parent: Instance, item)
	local base = basePoint(item)
	local cf = CFrame.new(base) * CFrame.Angles(0, item.Turn, 0)
	block(parent, "LanternBase", Vector3.new(1.6, 0.4, 1.6), cf * CFrame.new(0, 0.2, 0), STONE, MAT.Slate, true)
	disc(parent, "LanternPillar", base + Vector3.new(0, 0.4, 0), 1.6, 0.7, STONE, MAT.Slate, true)
	block(
		parent,
		"LanternBox",
		Vector3.new(1.3, 1, 1.3),
		cf * CFrame.new(0, 2.5, 0),
		STONE:Lerp(ROCK, 0.3),
		MAT.Slate,
		true
	)
	local glow =
		block(parent, "LanternLight", Vector3.new(1.34, 0.45, 0.6), cf * CFrame.new(0, 2.5, 0), LAMP_LIGHT, MAT.Neon)
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 8
	light.Brightness = 0.7
	light.Parent = glow
	block(
		parent,
		"LanternRoof",
		Vector3.new(2.3, 0.45, 2.3),
		cf * CFrame.new(0, 3.2, 0) * CFrame.Angles(0, math.rad(45), 0),
		ROCK,
		MAT.Slate,
		true
	)
	ball(parent, "LanternKnob", base + Vector3.new(0, 3.65, 0), 0.6, ROCK, MAT.Slate)
end

-- 정자: 돌 턱 + 나무 마루(윗면 0.4) + 흰 기둥 여덟(오솔길 방향 앞뒤로 드나듦) + 난간 여섯 + 세 단 지붕 + 꼭지
-- + 안쪽 양옆 벤치 + 가운데 매단 등. Turn = 오솔길 방향
function BUILD.Gazebo(parent: Instance, item)
	local base = basePoint(item)
	local cf = heading(base, item.Turn)
	disc(parent, "GazeboStep", base - Vector3.new(0, 0.3, 0), 0.5, 16.2, STONE, MAT.Cobblestone, true)
	disc(parent, "GazeboFloor", base - Vector3.new(0, 0.1, 0), 0.5, 15, WOOD_LIGHT, MAT.WoodPlanks, true)
	local postR = 6.8
	local posts = {}
	for k = 0, 7 do
		local a = (k + 0.5) / 8 * math.pi * 2 -- 앞뒤(0, 180도)는 기둥 사이
		local p = (cf * CFrame.new(math.sin(a) * postR, 0.4, -math.cos(a) * postR)).Position
		posts[k + 1] = p
		disc(parent, "GazeboPost", p, 6, 0.55, PAINT_WHITE, MAT.Wood, true)
	end
	-- 난간: 앞뒤 입구(기둥 8-1, 4-5 사이)만 비움
	for k = 1, 8 do
		local nextK = k % 8 + 1
		if k ~= 8 and k ~= 4 then
			-- 이웃 난간끼리 기둥에서 겹치는 끝이 같은 높이로 깜빡이지 않게 번갈아 0.05 차이
			local lift = Vector3.new(0, 1.3 + (k % 2) * 0.05, 0)
			local a, b = posts[k] + lift, posts[nextK] + lift
			block(
				parent,
				"GazeboRail",
				Vector3.new(0.25, 0.25, (b - a).Magnitude),
				CFrame.lookAt((a + b) / 2, b),
				PAINT_WHITE,
				MAT.Wood,
				true
			)
		end
	end
	local roof = rgb(84, 172, 156)
	disc(parent, "GazeboRoof", base + Vector3.new(0, 6.3, 0), 0.6, 16.4, PAINT_WHITE, MAT.Wood)
	disc(parent, "GazeboRoof", base + Vector3.new(0, 6.9, 0), 0.9, 13.4, roof, MAT.WoodPlanks)
	disc(parent, "GazeboRoof", base + Vector3.new(0, 7.8, 0), 0.9, 9.6, roof:Lerp(PAINT_WHITE, 0.15), MAT.WoodPlanks)
	disc(parent, "GazeboRoof", base + Vector3.new(0, 8.7, 0), 0.9, 5.6, roof:Lerp(PAINT_WHITE, 0.3), MAT.WoodPlanks)
	ball(parent, "GazeboFinial", base + Vector3.new(0, 10, 0), 1.3, SUN, MAT.Metal)
	disc(parent, "GazeboChain", base + Vector3.new(0, 5.8, 0), 0.7, 0.14, IRON, MAT.Metal) -- 지붕에 매단 줄
	local lamp = ball(parent, "GazeboLamp", base + Vector3.new(0, 5.4, 0), 1.2, LAMP_LIGHT, MAT.Neon)
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 14
	light.Brightness = 0.8
	light.Parent = lamp
	for _, side in { -1, 1 } do
		local seat = cf * CFrame.new(side * 4.6, 0.4, 0) * CFrame.Angles(0, side * math.rad(90), 0)
		block(
			parent,
			"BenchSeat",
			Vector3.new(4.2, 0.35, 1.4),
			seat * CFrame.new(0, 1.3, 0),
			WOOD,
			MAT.WoodPlanks,
			true
		)
		block(parent, "BenchLeg", Vector3.new(3.6, 1.2, 1), seat * CFrame.new(0, 0.6, 0), WOOD_DARK, MAT.Wood, true)
	end
end

-- 등대: 돌 받침(곶 바위에 묻힘) + 빨강·하양 줄무늬 탑 넷(위로 가늘게) + 문·창 + 쇠 발코니 + 팔각 난간
-- + 빛나는 등 + 빨간 지붕 돔 + 꼭지. Turn = 문 쪽(섬 안쪽)
function BUILD.Lighthouse(parent: Instance, item)
	local base = basePoint(item)
	local cf = heading(base, item.Turn)
	disc(parent, "LighthousePlinth", base - Vector3.new(0, 1.6, 0), 3, 9, ROCK:Lerp(STONE, 0.4), MAT.Cobblestone, true)
	local y = 1.4
	local radius = 3.1
	for k, diameter in { 6.2, 5.8, 5.4, 5 } do
		disc(
			parent,
			"LighthouseTower",
			base + Vector3.new(0, y, 0),
			5,
			diameter,
			if k % 2 == 1 then RED else PAINT_WHITE,
			MAT.SmoothPlastic,
			true
		)
		y += 5
	end
	block(
		parent,
		"LighthouseDoor",
		Vector3.new(1.8, 3, 0.4),
		cf * CFrame.new(0, 2.9, -radius + 0.05),
		WOOD_DARK,
		MAT.WoodPlanks
	)
	for _, h in { 9, 14 } do
		local w = cf * CFrame.new(0, h, -(if h > 10 then 2.72 else 2.92) + 0.02)
		block(parent, "LighthouseWindow", Vector3.new(1, 1.4, 0.3), w, NAVY, MAT.Glass)
	end
	disc(parent, "LighthouseGallery", base + Vector3.new(0, y, 0), 0.5, 7.6, IRON, MAT.Metal, true)
	for k = 0, 7 do
		local a1, a2 = k / 8 * math.pi * 2, (k + 1) / 8 * math.pi * 2
		local p1 = base + Vector3.new(math.cos(a1) * 3.6, y + 1.5, math.sin(a1) * 3.6)
		local p2 = base + Vector3.new(math.cos(a2) * 3.6, y + 1.5, math.sin(a2) * 3.6)
		block(
			parent,
			"LighthouseRail",
			Vector3.new(0.2, 1.1, (p2 - p1).Magnitude + 0.1),
			CFrame.lookAt((p1 + p2) / 2, p2) * CFrame.new(0, -0.45 + (k % 2) * 0.05, 0),
			IRON,
			MAT.Metal,
			true
		)
	end
	local lantern = disc(parent, "LighthouseLantern", base + Vector3.new(0, y + 0.5, 0), 3, 3.8, LAMP_LIGHT, MAT.Neon)
	local light = Instance.new("PointLight")
	light.Color = LAMP_LIGHT
	light.Range = 40
	light.Brightness = 2
	light.Parent = lantern
	disc(parent, "LighthouseRoof", base + Vector3.new(0, y + 3.5, 0), 0.7, 5, RED, MAT.SmoothPlastic)
	ball(parent, "LighthouseDome", base + Vector3.new(0, y + 4.2, 0), 4, RED, MAT.SmoothPlastic)
	disc(parent, "LighthouseSpire", base + Vector3.new(0, y + 5.8, 0), 1.4, 0.3, IRON, MAT.Metal)
	ball(parent, "LighthouseTop", base + Vector3.new(0, y + 7.3, 0), 0.7, SUN, MAT.Metal)
end

-- 구명 튜브: 빨강·하양 번갈아 여섯 토막 고리. cf = 고리 가운데, 고리 면 = cf 의 XY 평면
local function lifebuoy(parent: Instance, cf: CFrame)
	for k = 0, 5 do
		local a1, a2 = k / 6 * math.pi * 2, (k + 1) / 6 * math.pi * 2
		local p1 = (cf * CFrame.new(math.cos(a1) * 0.85, math.sin(a1) * 0.85, 0)).Position
		local p2 = (cf * CFrame.new(math.cos(a2) * 0.85, math.sin(a2) * 0.85, 0)).Position
		rod(parent, "Lifebuoy", p1, p2, 0.42, if k % 2 == 0 then CORAL else WHITE, MAT.SmoothPlastic)
	end
end

-- 부두: 풀밭 끝에서 바다로 뻗은 나무판(윗면 Y) + T자 끝 판 + 바닥까지 박힌 기둥(물 위로 난간 기둥이 됨)
-- + 난간 손잡이 + 끝에 정원등 둘·벤치·구명 튜브. Height = 전체 길이, Radius = 반폭, Turn = 바다 쪽
function BUILD.Pier(parent: Instance, item)
	local length, half = item.Height, item.Radius
	local top = item.Y
	local ground = Vector3.new(item.X, 0, item.Z)
	local cf = heading(ground, item.Turn)
	local headDepth, headHalf = 7, 6.5
	local main = length - headDepth
	block(
		parent,
		"PierDeck",
		Vector3.new(half * 2, 0.5, main + 0.2), -- T자 끝 판과 맞닿기만(겹치면 같은 높이라 깜빡임)
		cf * CFrame.new(0, top - 0.25, -(main - 0.2) / 2),
		WOOD,
		MAT.WoodPlanks,
		true
	)
	block(
		parent,
		"PierHead",
		Vector3.new(headHalf * 2, 0.5, headDepth),
		cf * CFrame.new(0, top - 0.25, -(main + headDepth / 2)),
		WOOD,
		MAT.WoodPlanks,
		true
	)
	-- 기둥: 땅이 판 밑보다 0.5 이상 낮은 곳만. 물가 쪽(땅이 판 가까이)은 난간 없음
	local railFrom = nil
	local function post(localX: number, localZ: number, rail: boolean)
		local p = cf * Vector3.new(localX, 0, localZ)
		local floor = groundAt(p.X, p.Z)
		if floor > top - 0.9 and not rail then
			return
		end
		local bottom = math.min(floor, top - 0.9) - 1
		local height = top - bottom + (if rail then 2.6 else -0.2)
		disc(parent, "PierPost", Vector3.new(p.X, bottom, p.Z), height, 0.7, WOOD_DARK, MAT.Wood, true)
	end
	for z = 6, main, 7 do
		local p = cf * Vector3.new(0, 0, -z)
		local rail = groundAt(p.X, p.Z) < top - 1.6
		if rail and not railFrom then
			railFrom = z
		end
		for _, side in { -1, 1 } do
			post(side * (half - 0.3), -z, rail)
		end
	end
	for _, x in { -headHalf + 0.3, headHalf - 0.3 } do
		for _, z in { main + 0.3, length - 0.3 } do
			post(x, -z, true)
		end
	end
	post(0, -(length - 0.3), true)
	-- 난간 손잡이(양옆 긴 것 + T자 끝 앞·옆)
	local railY = top + 2.3
	local from = railFrom or 6
	for _, side in { -1, 1 } do
		local x = side * (half - 0.3)
		block(
			parent,
			"PierRail",
			Vector3.new(0.3, 0.3, main - from),
			cf * CFrame.new(x, railY, -(from + main) / 2),
			WOOD_LIGHT,
			MAT.Wood,
			true
		)
		block(
			parent,
			"PierRail",
			Vector3.new(0.3, 0.3, headDepth),
			cf * CFrame.new(side * (headHalf - 0.3), railY, -(main + headDepth / 2)),
			WOOD_LIGHT,
			MAT.Wood,
			true
		)
		block(
			parent,
			"PierRail",
			Vector3.new(headHalf - half, 0.3, 0.3),
			cf * CFrame.new(side * (half + headHalf) / 2, railY - 0.05, -(main + 0.3)),
			WOOD_LIGHT,
			MAT.Wood,
			true
		)
	end
	block(
		parent,
		"PierRail",
		Vector3.new(headHalf * 2, 0.3, 0.3),
		cf * CFrame.new(0, railY - 0.05, -(length - 0.3)),
		WOOD_LIGHT,
		MAT.Wood,
		true
	)
	-- 끝: 양쪽 모서리 정원등, 바다를 보는 벤치, 난간에 건 구명 튜브(빨강·하양 여섯 토막)
	for _, side in { -1, 1 } do
		BUILD.Lamp(parent, {
			X = (cf * Vector3.new(side * (headHalf - 1.2), 0, -(length - 1.2))).X,
			Y = top,
			Z = (cf * Vector3.new(side * (headHalf - 1.2), 0, -(length - 1.2))).Z,
		})
	end
	BUILD.Bench(parent, {
		X = (cf * Vector3.new(0, 0, -(length - 2.4))).X,
		Y = top,
		Z = (cf * Vector3.new(0, 0, -(length - 2.4))).Z,
		Turn = item.Turn,
	})
	lifebuoy(
		parent,
		cf * CFrame.new(headHalf - 0.1, top + 1.4, -(main + headDepth / 2)) * CFrame.Angles(0, math.rad(90), 0)
	)
end

-- 구조대 망루: 흰 다리 넷(비탈이면 다리 길이를 땅에 맞춤) + 나무 발판 + 빨간 의자(받침 + 앉는 판 + 등받이)
-- + 뒤쪽 비스듬한 사다리 판 + 깃발 + 앞에 건 구명 튜브. Turn = 바다 쪽
function BUILD.Lifeguard(parent: Instance, item)
	local base = basePoint(item)
	local cf = heading(base, item.Turn)
	local deck = 4.2
	for _, c in { { -1.3, -1.1 }, { 1.3, -1.1 }, { -1.3, 1.1 }, { 1.3, 1.1 } } do
		local p = cf * Vector3.new(c[1], 0, c[2])
		local floor = groundAt(p.X, p.Z)
		local bottom = floor - 0.5
		disc(
			parent,
			"LifeguardLeg",
			Vector3.new(p.X, bottom, p.Z),
			base.Y + deck - bottom,
			0.4,
			PAINT_WHITE,
			MAT.Wood,
			true
		)
	end
	block(
		parent,
		"LifeguardDeck",
		Vector3.new(3.4, 0.35, 3.1),
		cf * CFrame.new(0, deck + 0.17, 0),
		WOOD,
		MAT.WoodPlanks,
		true
	)
	block(
		parent,
		"LifeguardSeatBox",
		Vector3.new(2.2, 1, 1.3),
		cf * CFrame.new(0, deck + 0.85, 0.5),
		PAINT_WHITE,
		MAT.WoodPlanks,
		true
	)
	block(
		parent,
		"LifeguardSeat",
		Vector3.new(2.3, 0.3, 1.4),
		cf * CFrame.new(0, deck + 1.5, 0.45),
		RED,
		MAT.WoodPlanks,
		true
	)
	block(
		parent,
		"LifeguardBack",
		Vector3.new(2.3, 1.7, 0.3),
		cf * CFrame.new(0, deck + 2.4, 1.2) * CFrame.Angles(math.rad(-12), 0, 0),
		RED,
		MAT.WoodPlanks,
		true
	)
	-- 사다리: 뒤쪽 땅에서 발판 뒤 가장자리까지 비스듬한 판(가로대 무늬는 WoodPlanks)
	local foot = cf * Vector3.new(0, 0, 3.6)
	local from = Vector3.new(foot.X, groundAt(foot.X, foot.Z), foot.Z)
	local to = (cf * CFrame.new(0, deck + 0.1, 1.5)).Position
	block(
		parent,
		"LifeguardLadder",
		Vector3.new(1.3, 0.25, (to - from).Magnitude),
		CFrame.lookAt((from + to) / 2, to),
		WOOD_LIGHT,
		MAT.WoodPlanks,
		true
	)
	local pole = (cf * CFrame.new(1.45, deck + 0.35, 1.3)).Position
	disc(parent, "LifeguardFlagPole", pole, 4.2, 0.16, PAINT_WHITE, MAT.Metal)
	block(
		parent,
		"LifeguardFlag",
		Vector3.new(0.08, 0.9, 1.4),
		cf * CFrame.new(1.45, deck + 4, 2.05),
		CORAL,
		MAT.Fabric
	)
	lifebuoy(parent, cf * CFrame.new(1.3, deck - 1.4, -1.42)) -- 앞 다리에 걸어 둠(고리가 다리에 닿음)
end

-- 간식 가게: 나무 마루 + 벽 셋(민트 판자) + 흰 계산대 + 줄무늬 차양 + 지붕 + 지붕 위 아이스크림 간판 + 의자 둘.
-- Turn = 계산대가 보는 쪽
function BUILD.Kiosk(parent: Instance, item)
	local base = basePoint(item)
	local cf = heading(base, item.Turn)
	block(parent, "KioskFloor", Vector3.new(7.4, 0.6, 6.4), cf * CFrame.new(0, 0.1, 0), WOOD, MAT.WoodPlanks, true)
	block(parent, "KioskWall", Vector3.new(7, 5, 0.4), cf * CFrame.new(0, 2.9, 2.9), MINT, MAT.WoodPlanks, true)
	for _, side in { -1, 1 } do
		block(
			parent,
			"KioskWall",
			Vector3.new(0.4, 4.9, 6),
			cf * CFrame.new(side * 3.3, 2.85, 0),
			MINT,
			MAT.WoodPlanks,
			true
		)
	end
	block(
		parent,
		"KioskCounter",
		Vector3.new(6.2, 2.4, 1),
		cf * CFrame.new(0, 1.6, -2.5),
		PAINT_WHITE,
		MAT.WoodPlanks,
		true
	)
	block(
		parent,
		"KioskCounterTop",
		Vector3.new(6.8, 0.3, 1.6),
		cf * CFrame.new(0, 2.95, -2.6),
		WOOD,
		MAT.WoodPlanks,
		true
	)
	block(parent, "KioskRoof", Vector3.new(8, 0.5, 7.2), cf * CFrame.new(0, 5.65, 0.1), CORAL, MAT.WoodPlanks, true)
	-- 차양: 앞으로 비스듬히 내려오는 줄무늬 다섯 조각
	for k = 0, 4 do
		local x = -3.2 + k * 1.6
		block(
			parent,
			"KioskAwning",
			Vector3.new(1.6, 0.15, 2.6),
			cf * CFrame.new(x, 5.1, -4) * CFrame.Angles(math.rad(-22), 0, 0),
			if k % 2 == 0 then CORAL else WHITE,
			MAT.Fabric
		)
	end
	-- 아이스크림 간판: 거꾸로 선 원뿔(원판 셋) + 공 둘
	local sign = cf * CFrame.new(0, 5.9, 0.5)
	for k, d in { 0.5, 1, 1.5 } do
		disc(
			parent,
			"IceCreamCone",
			(sign * CFrame.new(0, k * 0.6 - 0.6, 0)).Position,
			0.6,
			d,
			SUN:Lerp(WOOD, 0.4),
			MAT.WoodPlanks
		)
	end
	ball(parent, "IceCream", (sign * CFrame.new(0, 1.9, 0)).Position, 1.7, PINK)
	ball(parent, "IceCream", (sign * CFrame.new(0, 3.1, 0)).Position, 1.3, MINT)
	for _, x in { -1.8, 1.8 } do
		local p = cf * Vector3.new(x, 0, -5)
		local floor = groundAt(p.X, p.Z)
		disc(parent, "StoolLeg", Vector3.new(p.X, floor - 0.3, p.Z), 1.9, 0.25, IRON, MAT.Metal, true)
		disc(parent, "StoolSeat", Vector3.new(p.X, floor + 1.6, p.Z), 0.3, 1.2, CORAL, MAT.Fabric, true)
	end
end

-- 선베드 하나: 머리 쪽(head) → 발 쪽(foot) 땅을 따라 기울임. 틀 + 받침 + 등받이 + 쿠션
local function lounger(parent: Instance, head: Vector3, foot: Vector3, cushion: Color3)
	local h1 = Vector3.new(head.X, groundAt(head.X, head.Z) + 0.75, head.Z)
	local h2 = Vector3.new(foot.X, groundAt(foot.X, foot.Z) + 0.75, foot.Z)
	local cf = CFrame.lookAt((h1 + h2) / 2, h2, UP)
	local length = (h2 - h1).Magnitude
	block(parent, "LoungerFrame", Vector3.new(1.7, 0.3, length), cf, PAINT_WHITE, MAT.WoodPlanks, true)
	block(parent, "LoungerLegs", Vector3.new(1.3, 1.1, length - 0.8), cf * CFrame.new(0, -0.6, 0), WOOD_DARK, MAT.Wood)
	block(
		parent,
		"LoungerBack",
		Vector3.new(1.6, 0.3, 1.9),
		cf * CFrame.new(0, 0.6, length / 2 - 0.7) * CFrame.Angles(math.rad(40), 0, 0),
		PAINT_WHITE,
		MAT.WoodPlanks,
		true
	)
	block(
		parent,
		"LoungerCushion",
		Vector3.new(1.45, 0.2, length - 1.9),
		cf * CFrame.new(0, 0.24, -0.9),
		cushion,
		MAT.Fabric
	)
end

-- 파라솔 묶음: 줄무늬 파라솔 + 양옆 선베드 + 앞 수건. Turn = 바다 쪽(선베드가 바다를 봄)
function BUILD.BeachSet(parent: Instance, item)
	local base = basePoint(item)
	local color = CANVAS[(item.Style - 1) % #CANVAS + 1]
	local cf = heading(base, item.Turn)
	umbrella(parent, base, item.Turn, color)
	for _, side in { -1, 1 } do
		local head = cf * Vector3.new(side * 1.25, 0, 2.4)
		local foot = cf * Vector3.new(side * 1.25, 0, -2.2)
		lounger(parent, head, foot, if side < 0 then color else CANVAS[item.Style % #CANVAS + 1])
	end
	local towelCf = onGround(cf * CFrame.new(3.4, 0, -3.2) * CFrame.Angles(0, 0.35, 0), 1.1, 2)
	block(
		parent,
		"Towel",
		Vector3.new(2.2, 0.12, 4),
		towelCf * CFrame.new(0, 0.1, 0),
		CANVAS[(item.Style + 1) % #CANVAS + 1],
		MAT.Fabric
	)
	block(parent, "TowelStripe", Vector3.new(2.2, 0.14, 0.5), towelCf * CFrame.new(0, 0.11, 1.2), WHITE, MAT.Fabric)
end

-- 모래성: 모래 받침 + 모퉁이 탑 넷 + 가운데 큰 탑 + 깃발
function BUILD.Sandcastle(parent: Instance, item)
	local base = basePoint(item)
	local cf = CFrame.new(base) * CFrame.Angles(0, item.Turn, 0)
	block(parent, "Sandcastle", Vector3.new(3, 1, 3), cf * CFrame.new(0, 0.3, 0), SAND, MAT.Sand, true)
	for _, c in { { -1.3, -1.3 }, { 1.3, -1.3 }, { -1.3, 1.3 }, { 1.3, 1.3 } } do
		disc(parent, "SandTower", (cf * CFrame.new(c[1], 0.5, c[2])).Position, 1.2, 0.9, SAND, MAT.Sand)
	end
	disc(parent, "SandKeep", base + Vector3.new(0, 0.6, 0), 1.9, 1.6, SAND, MAT.Sand)
	disc(parent, "FlagPole", base + Vector3.new(0, 2.4, 0), 1.3, 0.1, WOOD_DARK, MAT.Wood)
	block(parent, "Flag", Vector3.new(0.05, 0.45, 0.7), cf * CFrame.new(0, 3.45, -0.35), CORAL, MAT.Fabric)
end

-- 동전 망원경(부지 뒤 바다 전망): 쇠 받침 + 기둥 + 머리 상자 + 바다 쪽으로 살짝 치켜든 통 + 눈대개. Turn = 바다 쪽
function BUILD.Telescope(parent: Instance, item)
	local base = basePoint(item)
	local cf = heading(base, item.Turn)
	disc(parent, "TelescopeFoot", base - Vector3.new(0, 0.2, 0), 0.5, 1.4, IRON, MAT.Metal, true)
	disc(parent, "TelescopePost", base, 3.5, 0.45, TEAL, MAT.Metal, true)
	block(parent, "TelescopeHead", Vector3.new(1, 1, 1.1), cf * CFrame.new(0, 3.9, 0), TEAL, MAT.Metal, true)
	local front = (cf * CFrame.new(0, 4.25, -1.9)).Position
	local back = (cf * CFrame.new(0, 3.75, 0.3)).Position
	rod(parent, "TelescopeTube", back, front, 0.75, SUN:Lerp(WOOD, 0.3), MAT.Metal, true)
	local eye = (cf * CFrame.new(0, 3.62, 1)).Position
	rod(parent, "TelescopeEye", back, eye, 0.4, IRON, MAT.Metal)
end

-- 서핑보드 거치대: 낮은 나무 받침 + 모래에 꽂혀 기운 보드 셋(판 + 둥근 끝 원판). 색이 다름. Turn = 보드 면이 보는 쪽
function BUILD.Surfboards(parent: Instance, item)
	local base = basePoint(item)
	local cf = heading(base, item.Turn)
	local colors = { CORAL, SUN, SKY, MINT }
	block(parent, "SurfRack", Vector3.new(5.2, 0.5, 1), cf * CFrame.new(0, 1.6, 0.9), WOOD, MAT.WoodPlanks, true)
	for _, x in { -2.3, 2.3 } do
		disc(parent, "SurfRackPost", (cf * CFrame.new(x, -0.4, 0.9)).Position, 2.3, 0.4, WOOD_DARK, MAT.Wood, true)
	end
	for k = 1, 3 do
		local x = (k - 2) * 1.7
		local board = cf * CFrame.new(x, 2, 0.35) * CFrame.Angles(math.rad(-14), 0, math.rad((k - 2) * 6))
		local color = colors[(k + item.Style) % #colors + 1]
		block(parent, "Surfboard", Vector3.new(1.4, 4.4, 0.22), board, color, MAT.SmoothPlastic, true)
		-- 둥근 끝(원판을 보드 면에 세움)
		part(
			parent,
			"SurfboardTip",
			Enum.PartType.Cylinder,
			Vector3.new(0.2, 1.4, 1.4),
			board * CFrame.new(0, 2.2, 0) * CFrame.Angles(0, math.rad(90), 0),
			color,
			MAT.SmoothPlastic
		)
		block(parent, "SurfboardStripe", Vector3.new(0.3, 4.1, 0.26), board, WHITE, MAT.SmoothPlastic)
	end
end

-- 떠밀려 온 나무(모래 위에 누운 줄기: 굵은 밑동 → 가는 끝 두 토막 + 뿌리 혹 + 곁가지 둘, 햇볕에 바랜 색). Turn = 누운 방향
function BUILD.Driftwood(parent: Instance, item)
	local s, base = item.Scale, basePoint(item)
	local dx, dz = math.cos(item.Turn), math.sin(item.Turn)
	local half = 2.6 * s
	local function onSand(x: number, z: number, lift: number): Vector3
		return Vector3.new(x, groundAt(x, z) + lift, z)
	end
	local a = onSand(base.X - dx * half, base.Z - dz * half, 0.25 * s)
	local b = onSand(base.X + dx * half, base.Z + dz * half, 0.18 * s)
	local mid = a:Lerp(b, 0.45) + Vector3.new(0, 0.05 * s, 0)
	local bleached = rgb(196, 180, 154)
	rod(parent, "Driftwood", a, mid, 0.8 * s, bleached, MAT.Wood, true)
	rod(parent, "Driftwood", mid, b, 0.55 * s, bleached:Lerp(WOOD_LIGHT, 0.2), MAT.Wood, true)
	ball(parent, "Driftwood", a - Vector3.new(dx, 0, dz) * 0.2 * s, 1.05 * s, bleached:Lerp(WOOD_DARK, 0.15), MAT.Wood)
	for k, t in { 0.35, 0.7 } do
		local from = a:Lerp(b, t)
		local side = if k == 1 then 1 else -1
		local to = from
			+ Vector3.new(
				-dz * side * 1.5 * s + dx * 0.7 * s,
				(0.45 - 0.15 * k) * s,
				dx * side * 1.5 * s + dz * 0.7 * s
			)
		rod(parent, "Driftwood", from, to, (0.34 - 0.06 * k) * s, bleached:Lerp(WOOD_DARK, 0.1 * k), MAT.Wood)
	end
end

-- 수영 구역 부표: 반쯤 잠긴 공 + 작은 꼭지(빨강/하양)
function BUILD.Buoy(parent: Instance, item)
	local base = basePoint(item)
	local color = if item.Style == 1 then CORAL else WHITE
	ball(parent, "Buoy", base + Vector3.new(0, 0.15, 0), 1.3, color)
	disc(parent, "BuoyTop", base + Vector3.new(0, 0.6, 0), 0.7, 0.3, if item.Style == 1 then WHITE else CORAL)
end

-- 돛단배: 배 몸통 + 뾰족한 뱃머리(쐐기 둘) + 테두리 + 돛대 + 큰 돛 + 앞 돛 + 깃발. Turn = 뱃머리 쪽, Scale = 크기
function BUILD.Boat(parent: Instance, item)
	local s = item.Scale
	local cf = heading(basePoint(item), item.Turn)
	local function at(x: number, y: number, z: number): CFrame
		return cf * CFrame.new(x * s, y * s, z * s)
	end
	local hull = if item.Tint < 0.4 then WHITE elseif item.Tint < 0.7 then CORAL else SKY
	local trim = if hull == SKY then WHITE else SKY
	block(parent, "BoatHull", Vector3.new(3.2, 1.3, 5.2) * s, at(0, 0.1, 0.8), hull, MAT.WoodPlanks)
	for _, side in { -1, 1 } do
		-- 쐐기를 Z 축으로 눕혀서(쐐기 +Y → 바깥 옆) 위에서 보면 삼각형(뱃머리 반쪽, 끝이 가운데 앞)
		wedge(
			parent,
			"BoatBow",
			Vector3.new(1.3, 1.6, 2.6) * s,
			at(side * 0.8, 0.1, -3.1) * CFrame.Angles(0, 0, -side * math.rad(90)),
			hull,
			MAT.WoodPlanks
		)
	end
	block(parent, "BoatRim", Vector3.new(3.3, 0.25, 5.3) * s, at(0, 0.8, 0.8), trim, MAT.Wood)
	disc(parent, "BoatMast", at(0, 0.75, 0).Position, 7 * s, 0.3 * s, WOOD_DARK, MAT.Wood)
	local sail = if item.Style == 3 then SUN:Lerp(WHITE, 0.4) else WHITE
	wedge(
		parent,
		"BoatSail",
		Vector3.new(0.12, 5.6, 3.6) * s,
		at(0, 4.2, 1.9) * CFrame.Angles(0, math.pi, 0),
		sail,
		MAT.Fabric
	)
	wedge(
		parent,
		"BoatJib",
		Vector3.new(0.12, 4.2, 2.4) * s,
		at(0, 3.4, -1.3),
		if item.Style == 2 then CORAL else SKY,
		MAT.Fabric
	)
	block(parent, "BoatFlag", Vector3.new(0.06, 0.5, 0.9) * s, at(0, 7.9, 0.45), CORAL, MAT.Fabric)
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

-- 곧은 길 조각(Plan.Segment 모양): 윗면 Top, 두께 height. solid 면 걸을 수 있음
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

-- 둥근 판(광장 원판): 윗면 top
function Props.disc(
	parent: Instance,
	name: string,
	x: number,
	z: number,
	radius: number,
	top: number,
	height: number,
	color: Color3,
	material: Enum.Material,
	solid: boolean?
): Part
	return disc(parent, name, Vector3.new(x, top - height, z), height, radius * 2, color, material, solid)
end

return Props
