-- 명소 3D 모형 (서버·클라이언트 공용, 양보(yield) 없음)
--
-- Models.build(landmark): 에셋 없이 기본 파트(Block/Ball/Cylinder/Wedge)만으로 만든 임시 미니어처.
--   설계 공간: 바닥 가로·세로 10 스터드(원점 중심) 안, 높이 22 스터드 이하, 바닥 y = 0, 정면은 -Z 쪽.
--   투명한 "Root" 파트(10 x 0.2 x 10)가 바닥 중앙에 있고 PrimaryPart(피벗 = 바닥 중앙).
--   모든 파트 Anchored = true, CanCollide = false. 색은 명소의 Primary / Secondary / Accent, 재질은 Material.
-- Models.create(landmark, size, opts?): 실제로 쓰는 함수.
--   ReplicatedStorage.LandmarkModels 에 명소 Id 와 같은 이름의 Model 이 있으면 복제(AI 메쉬 교체용), 없으면 build().
--   가로·세로 중 큰 쪽이 size 스터드가 되도록 Model:ScaleTo(높이는 size * 2.2 까지). 피벗 = 바닥 중앙, 부모 없음.
--   opts.Anchored == false 면 모든 BasePart: Anchored/CanCollide/CanQuery/CanTouch 끔 + Massless(캐릭터에 용접할 때).

local Landmarks = require(script.Parent.Landmarks)

type Landmark = Landmarks.Landmark

local Models = {}

local DESIGN_WIDTH = 10 -- 설계 공간 가로·세로(스터드)
local MAX_HEIGHT_RATIO = 2.2 -- 높이 한도 = size * 2.2 (설계 공간 22 / 10)
local OVERRIDE_FOLDER = "LandmarkModels"

local V = Vector3.new
local rgb = Color3.fromRGB
local Mat = Enum.Material
local PI = math.pi
local TAU = math.pi * 2

local UPRIGHT = CFrame.Angles(0, 0, PI / 2) -- 원기둥(길이 축 = X)을 세움
local ALONG_Z = CFrame.Angles(0, PI / 2, 0) -- 원기둥 길이 축을 Z 로(정면을 보는 원판)
local CORNERS = { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } }

-- 명소 색으로 표현하기 어려운 자연물/그늘 색
local GRASS = rgb(96, 168, 78)
local LEAF = rgb(58, 132, 62)
local WATER = rgb(60, 145, 225)
local DARK = rgb(38, 32, 30)
local TILE = rgb(62, 66, 74)
local ROCK = rgb(120, 114, 106)
local WOOD = rgb(105, 72, 48)
local SAND = rgb(226, 204, 156)
local CLOUD = rgb(248, 250, 255)
local BLACK = rgb(0, 0, 0)
local WHITE = rgb(255, 255, 255)

type Ctx = {
	model: Model,
	id: string, -- 명소 Id(같은 모형을 쓰는 명소끼리 작은 차이를 줄 때)
	origin: CFrame, -- 파트 좌표에 앞에서 곱하는 기준 좌표계(기울어진 탑 등)
	P: Color3, -- 주 색
	S: Color3, -- 보조 색
	A: Color3, -- 강조 색(빛/장식)
	M: Enum.Material, -- 주 재질
	grand: boolean, -- 불가사의 이상 등급: 같은 모형을 쓰는 흔한 명소보다 웅장하게
}

local function mix(a: Color3, b: Color3, t: number): Color3
	return Color3.new(a.R + (b.R - a.R) * t, a.G + (b.G - a.G) * t, a.B + (b.B - a.B) * t)
end

-- 파트 생성 헬퍼 ------------------------------------------------------------

local function add(
	c: Ctx,
	part: BasePart,
	cf: CFrame,
	size: Vector3,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
): BasePart
	part.Anchored = true
	part.CanCollide = false
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Size = size
	part.CFrame = c.origin * cf
	part.Color = color
	part.Material = material or c.M
	part.Transparency = transparency or 0
	part.Parent = c.model
	return part
end

local function shaped(
	c: Ctx,
	shape: Enum.PartType,
	cf: CFrame,
	size: Vector3,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
): BasePart
	local part = Instance.new("Part")
	part.Shape = shape -- 크기보다 먼저(공 모양은 크기가 균일해짐)
	return add(c, part, cf, size, color, material, transparency)
end

-- 중심 좌표계 cf 에 놓는 직육면체
local function block(c: Ctx, cf: CFrame, size: Vector3, color: Color3, material: Enum.Material?, transparency: number?)
	return shaped(c, Enum.PartType.Block, cf, size, color, material, transparency)
end

-- 바닥 중앙이 (x, y, z) 인 직육면체
local function box(
	c: Ctx,
	x: number,
	y: number,
	z: number,
	sx: number,
	sy: number,
	sz: number,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
)
	return block(c, CFrame.new(x, y + sy / 2, z), V(sx, sy, sz), color, material, transparency)
end

-- 중심이 (x, y, z), 지름 d 인 공
local function ball(
	c: Ctx,
	x: number,
	y: number,
	z: number,
	d: number,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
)
	return shaped(c, Enum.PartType.Ball, CFrame.new(x, y, z), V(d, d, d), color, material, transparency)
end

-- 길이 축이 cf 의 X 축인 원기둥
local function cyl(
	c: Ctx,
	cf: CFrame,
	length: number,
	d: number,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
)
	return shaped(c, Enum.PartType.Cylinder, cf, V(length, d, d), color, material, transparency)
end

-- 바닥 중앙이 (x, y, z) 인 세운 원기둥(높이 h, 지름 d)
local function col(
	c: Ctx,
	x: number,
	y: number,
	z: number,
	h: number,
	d: number,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
)
	return cyl(c, CFrame.new(x, y + h / 2, z) * UPRIGHT, h, d, color, material, transparency)
end

-- 쐐기: 높은 면이 +Z(뒤), 경사면이 -Z(앞, cf.LookVector) 쪽을 봄
local function wedge(c: Ctx, cf: CFrame, size: Vector3, color: Color3, material: Enum.Material?, transparency: number?)
	return add(c, Instance.new("WedgePart"), cf, size, color, material, transparency)
end

-- a 에서 b 까지 이어지는 각재(단면 t x t)
local function beam(
	c: Ctx,
	a: Vector3,
	b: Vector3,
	t: number,
	color: Color3,
	material: Enum.Material?,
	transparency: number?
)
	local delta = b - a
	local length = delta.Magnitude
	local mid = (a + b) / 2
	local cf
	if math.abs(delta.Y) > length * 0.999 then
		cf = CFrame.new(mid) * CFrame.Angles(PI / 2, 0, 0) -- 수직이면 lookAt 대신 직접 세움
	else
		cf = CFrame.lookAt(mid, b)
	end
	return block(c, cf, V(t, t, length), color, material, transparency)
end

-- (dx, dz) 쪽을 정면(LookVector)으로 보는 회전
local function facing(dx: number, dz: number): CFrame
	return CFrame.Angles(0, math.atan2(-dx, -dz), 0)
end

-- 개구부 위쪽 모서리를 채우는 쐐기(아치처럼 보이게). xWall = 벽면 x, side = -1(왼쪽 벽) / 1(오른쪽 벽)
local function archCorner(
	c: Ctx,
	xWall: number,
	yTop: number,
	z: number,
	leg: number,
	depth: number,
	color: Color3,
	side: number
)
	-- 뒤집은(roll 180도) 쐐기를 벽 쪽으로 돌림: 직각이 벽과 천장이 만나는 모서리에 옴
	local cf = CFrame.new(xWall - side * leg / 2, yTop - leg / 2, z)
		* CFrame.Angles(0, side * PI / 2, 0)
		* CFrame.Angles(0, 0, PI)
	return wedge(c, cf, V(depth, leg, leg), color)
end

-- 기와지붕: 처마 판 + 앞뒤 경사 + 용마루 + 네 귀퉁이 들린 추녀. 바닥이 y, 전체 높이 ≈ 0.3 + h + 0.2
local function roof(c: Ctx, x: number, y: number, z: number, w: number, d: number, h: number, color: Color3)
	box(c, x, y, z, w, 0.3, d, color)
	local top = y + 0.3
	wedge(c, CFrame.new(x, top + h / 2, z - d / 4), V(w - 0.3, h, d / 2), color)
	wedge(c, CFrame.new(x, top + h / 2, z + d / 4) * CFrame.Angles(0, PI, 0), V(w - 0.3, h, d / 2), color)
	box(c, x, top + h - 0.2, z, w - 0.2, 0.4, 0.45, mix(color, BLACK, 0.25))
	for _, s in CORNERS do
		local cf = CFrame.new(x + s[1] * (w / 2 - 0.35), top + 0.3, z + s[2] * (d / 2 - 0.35))
		wedge(c, cf * CFrame.Angles(0, math.atan2(s[1], s[2]), 0), V(0.55, 0.6, 1.1), color)
	end
end

-- 박공지붕(쐐기 두 개). 바닥이 y
local function gable(c: Ctx, x: number, y: number, z: number, w: number, d: number, h: number, color: Color3)
	wedge(c, CFrame.new(x, y + h / 2, z - d / 4), V(w, h, d / 2), color)
	wedge(c, CFrame.new(x, y + h / 2, z + d / 4) * CFrame.Angles(0, PI, 0), V(w, h, d / 2), color)
end

-- 나무: 줄기 + 잎 공
local function plant(c: Ctx, x: number, y: number, z: number, h: number, d: number, leaf: Color3)
	col(c, x, y, z, h, math.max(0.2, d * 0.22), WOOD, Mat.Wood)
	ball(c, x, y + h + d * 0.3, z, d, leaf, Mat.Grass)
end

-- 계단식 피라미드(steps 단). 꼭대기 높이를 돌려줌
local function stepped(
	c: Ctx,
	x: number,
	z: number,
	y: number,
	base: number,
	height: number,
	steps: number,
	color: Color3
)
	local stepHeight = height / steps
	for i = 0, steps - 1 do
		local w = base * (1 - i / steps)
		box(c, x, y + i * stepHeight, z, w, stepHeight, w, color)
	end
	return y + height
end

-- 시계 판: cf 는 벽면 중앙, -Z 가 바깥
local function clockFace(c: Ctx, cf: CFrame, d: number)
	cyl(c, cf * CFrame.new(0, 0, -0.1) * ALONG_Z, 0.2, d, c.A, Mat.Neon)
	block(c, cf * CFrame.new(0, d * 0.14, -0.25), V(d * 0.08, d * 0.3, 0.1), c.S)
	block(c, cf * CFrame.Angles(0, 0, -2.1) * CFrame.new(0, d * 0.2, -0.27), V(d * 0.06, d * 0.42, 0.1), c.S)
end

-- 모형들 ------------------------------------------------------------------

local BUILDERS: { [string]: (Ctx) -> () } = {}

-- 시계탑 / 빅벤: 기단 + 탑신 + 네 면 시계 + 종루 + 뾰족 지붕
function BUILDERS.clocktower(c)
	box(c, 0, 0, 0, 6, 0.6, 6, c.S)
	box(c, 0, 0.6, 0, 3.6, 10, 3.6, c.P)
	for _, s in CORNERS do
		box(c, s[1] * 1.8, 0.6, s[2] * 1.8, 0.6, 10, 0.6, c.S)
	end
	box(c, 0, 5.4, 0, 3.9, 0.3, 3.9, c.S)
	box(c, 0, 10.6, 0, 4.4, 3.6, 4.4, c.P)
	for i = 0, 3 do
		clockFace(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 12.4, -2.2), 3)
	end
	box(c, 0, 14.2, 0, 5, 0.4, 5, c.S)
	box(c, 0, 14.6, 0, 3.6, 1.6, 3.6, c.P)
	for i = 0, 3 do
		block(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 15.4, -1.8), V(1.8, 1, 0.1), DARK)
	end
	box(c, 0, 16.2, 0, 4, 0.3, 4, c.S)
	local y = 16.5
	for _, step in { { 3, 0.9 }, { 2.2, 0.9 }, { 1.4, 1 }, { 0.7, 1 } } do
		box(c, 0, y, 0, step[1], step[2], step[1], c.S)
		y += step[2]
	end
	col(c, 0, y, 0, 1, 0.25, c.A, Mat.Metal)
	ball(c, 0, y + 1.25, 0, 0.5, c.A, Mat.Neon)
end

-- 등대 / 알렉산드리아 등대: 줄무늬 탑(흔한 것) 또는 3단 석탑(불가사의) + 유리 등롱 + 불빛 줄기
function BUILDERS.lighthouse(c)
	local top
	if c.grand then
		box(c, 0, 0, 0, 9.6, 0.6, 9.6, c.S)
		box(c, 0, 0.6, 0, 6.4, 6.4, 6.4, c.P)
		for i = 0, 3 do
			block(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 4.6, -3.2), V(0.6, 1.6, 0.1), DARK)
		end
		box(c, 0, 7, 0, 6.9, 0.5, 6.9, c.S)
		box(c, 0, 7.5, 0, 4.4, 4.2, 4.4, c.P)
		block(c, CFrame.new(0, 9.6, 0) * CFrame.Angles(0, PI / 4, 0), V(4.4, 4.2, 4.4), c.P)
		col(c, 0, 11.7, 0, 0.4, 5.2, c.S)
		col(c, 0, 12.1, 0, 3.8, 3.2, c.P)
		top = 15.9
	else
		col(c, 0, 0, 0, 0.8, 8.6, ROCK, Mat.Slate)
		box(c, 2.2, 0.8, 1.3, 2, 1.4, 1.8, c.P)
		gable(c, 2.2, 2.2, 1.3, 2.3, 2.1, 0.9, c.S)
		local y = 0.8
		for i = 0, 5 do
			col(c, 0, y, 0, 1.9, 3.4 - i * 0.18, if i % 2 == 0 then c.P else c.S)
			y += 1.9
		end
		top = y
	end
	col(c, 0, top, 0, 0.3, 3.8, c.S)
	col(c, 0, top + 0.3, 0, 1.8, 2.2, c.A, Mat.Glass, 0.45)
	ball(c, 0, top + 1.2, 0, 1.3, c.A, Mat.Neon)
	col(c, 0, top + 2.1, 0, 0.3, 2.6, c.S)
	col(c, 0, top + 2.4, 0, 0.6, 1.6, c.S)
	if c.grand then
		-- 꼭대기의 신상
		col(c, 0, top + 3, 0, 1.1, 0.5, c.P)
		ball(c, 0, top + 4.3, 0, 0.45, c.P)
	else
		col(c, 0, top + 3, 0, 0.5, 0.8, c.S)
		ball(c, 0, top + 3.7, 0, 0.5, c.A, Mat.Neon)
	end
	block(c, CFrame.new(0, top + 1.2, 0) * CFrame.Angles(0, math.rad(30), 0), V(9.4, 0.5, 0.5), c.A, Mat.Neon, 0.6)
end

-- 풍차: 잔디 + 원뿔형 탑 + 둥근 지붕 + 네 날개
function BUILDERS.windmill(c)
	col(c, 0, 0, 0, 0.4, 9.4, GRASS, Mat.Grass)
	col(c, 0, 0.4, 0, 3, 5.4, c.P)
	col(c, 0, 3.4, 0, 3, 4.8, c.P)
	col(c, 0, 6.4, 0, 3, 4.2, c.P)
	col(c, 0, 3.3, 0, 0.3, 6.2, c.S)
	ball(c, 0, 9.4, 0, 4.4, c.S)
	box(c, 0, 0.4, -2.65, 1.1, 1.8, 0.3, c.S)
	box(c, 0, 4.4, -2.35, 0.7, 0.9, 0.2, DARK)
	box(c, 0, 7.2, -2.05, 0.6, 0.8, 0.2, DARK)
	local hub = CFrame.new(0, 9.6, -2.4)
	cyl(c, hub * ALONG_Z, 1.2, 0.8, c.S)
	for i = 0, 3 do
		local arm = CFrame.new(0, 9.6, -3.1) * CFrame.Angles(0, 0, PI / 4 + i * PI / 2)
		block(c, arm * CFrame.new(0, 2.5, 0), V(0.25, 5, 0.25), c.S)
		block(c, arm * CFrame.new(0.55, 2.9, -0.05), V(0.9, 3.8, 0.1), c.A, nil, 0.05)
	end
end

-- 분수대: 팔각 수반 + 2단 물받이 + 물줄기(유리/네온)
function BUILDERS.fountain(c)
	col(c, 0, 0, 0, 0.3, 9.8, c.P)
	local r = 4
	local side = 2 * r * math.tan(PI / 8) + 0.1
	for i = 0, 7 do
		block(c, CFrame.Angles(0, i * PI / 4, 0) * CFrame.new(0, 0.85, -r), V(side, 1.1, 0.5), c.P)
	end
	col(c, 0, 0.3, 0, 0.6, 7.5, c.S, Mat.Glass, 0.25)
	col(c, 0, 0.3, 0, 3.2, 1.2, c.P)
	col(c, 0, 3.1, 0, 0.4, 2.6, c.P)
	col(c, 0, 3.5, 0, 0.5, 4.6, c.P)
	col(c, 0, 4, 0, 0.12, 4, c.S, Mat.Glass, 0.2)
	col(c, 0, 0.9, 0, 3, 4.5, c.A, Mat.Glass, 0.65)
	col(c, 0, 4, 0, 1.8, 0.7, c.P)
	col(c, 0, 5.8, 0, 0.35, 2.4, c.P)
	col(c, 0, 6.15, 0, 0.1, 2, c.S, Mat.Glass, 0.2)
	col(c, 0, 4.12, 0, 1.68, 2.3, c.A, Mat.Glass, 0.65)
	col(c, 0, 6.15, 0, 2.2, 0.35, c.A, Mat.Neon, 0.3)
	ball(c, 0, 8.4, 0, 1, c.A, Mat.Glass, 0.45)
	for i = 0, 3 do
		local rot = CFrame.Angles(0, i * PI / 2 + PI / 4, 0)
		beam(c, rot * V(0, 1.4, -3.4), rot * V(0, 2.8, -2.3), 0.2, c.A, Mat.Neon, 0.3)
	end
end

-- 개선문: 원형 광장 + 네 기둥(앞뒤·옆 아치) + 코니스 + 아틱
function BUILDERS.arch(c)
	col(c, 0, 0, 0, 0.2, 9.8, c.S)
	box(c, 0, 0.2, 0, 9.2, 0.35, 5, c.S)
	local y = 0.55
	for _, sx in { -1, 1 } do
		local x = sx * 3
		box(c, x, y, -1.55, 3.2, 7, 1.3, c.P)
		box(c, x, y, 1.55, 3.2, 7, 1.3, c.P)
		box(c, x, y + 4, 0, 3.2, 3, 1.8, c.P)
		box(c, x, y + 1.2, -2.25, 1.8, 2.2, 0.15, c.S)
		box(c, x, y + 1.2, 2.25, 1.8, 2.2, 0.15, c.S)
	end
	box(c, 0, y + 5.6, 0, 2.8, 1.4, 4.4, c.P)
	archCorner(c, -1.4, y + 5.6, 0, 1.1, 4.4, c.P, -1)
	archCorner(c, 1.4, y + 5.6, 0, 1.1, 4.4, c.P, 1)
	box(c, 0, 7.55, 0, 9.6, 0.5, 4.8, c.S)
	box(c, 0, 8.05, 0, 9.2, 1.9, 4.4, c.P)
	box(c, 0, 8.6, -2.22, 8.4, 0.35, 0.1, c.A, Mat.Metal)
	box(c, 0, 8.6, 2.22, 8.4, 0.35, 0.1, c.A, Mat.Metal)
	box(c, 0, 9.95, 0, 9.6, 0.3, 4.8, c.S)
	ball(c, 0, 0.75, 0, 0.4, c.A, Mat.Neon)
end

-- 숭례문: 홍예문이 뚫린 석축 + 붉은 문루 2층 + 들린 추녀의 기와지붕 2겹
function BUILDERS.gate(c)
	box(c, -2.8, 0, 0, 3.6, 3.6, 4.6, c.P)
	box(c, 2.8, 0, 0, 3.6, 3.6, 4.6, c.P)
	box(c, 0, 2.3, 0, 2, 1.3, 4.6, c.P)
	archCorner(c, -1, 2.3, 0, 0.7, 4.6, c.P, -1)
	archCorner(c, 1, 2.3, 0, 0.7, 4.6, c.P, 1)
	box(c, 0, 3.6, 0, 9.2, 0.25, 4.8, mix(c.P, WHITE, 0.2))
	box(c, 0, 3.85, 0, 7.4, 0.25, 3.6, WOOD, Mat.Wood)
	box(c, 0, 4.1, 0, 6.8, 1.6, 3, c.A)
	box(c, 0, 5.4, 0, 7, 0.35, 3.2, c.S)
	roof(c, 0, 5.75, 0, 9, 5, 1.3, TILE)
	box(c, 0, 6.6, 0, 5.6, 1.6, 2.4, c.A)
	box(c, 0, 7.3, -1.22, 0.9, 0.6, 0.1, DARK)
	box(c, 0, 8.2, 0, 5.8, 0.3, 2.6, c.S)
	roof(c, 0, 8.5, 0, 8.2, 4.4, 1.5, TILE)
end

-- 피사의 사탑: 잔디 광장 위에 기울어진 원통형 8층 탑
function BUILDERS.leaning(c)
	box(c, 0, 0, 0, 9.6, 0.25, 9.6, GRASS, Mat.Grass)
	col(c, 0, 0.25, 0, 0.4, 5, c.S)
	c.origin = CFrame.new(0, 0.65, 0) * CFrame.Angles(0, 0, math.rad(-7))
	col(c, 0, 0, 0, 2.2, 3.6, c.P)
	local y = 2.2
	for _ = 1, 6 do
		col(c, 0, y, 0, 0.25, 4, c.S)
		col(c, 0, y + 0.25, 0, 1.45, 3.4, c.P)
		y += 1.7
	end
	col(c, 0, y, 0, 0.25, 3.6, c.S)
	col(c, 0, y + 0.25, 0, 1.5, 2.6, c.P)
	col(c, 0, y + 1.75, 0, 0.3, 2.9, c.S)
	c.origin = CFrame.new()
end

-- 서 있는 인물의 상체(어깨 윗면 높이 y): 목, 머리, 햇살 왕관, 횃불 든 오른팔, 서판 든 왼팔
local function figureTop(c: Ctx, y: number)
	col(c, 0, y, 0, 0.5, 0.6, c.P)
	local head = V(0, y + 0.95, 0)
	ball(c, 0, head.Y, 0, 1.2, c.P)
	col(c, 0, head.Y + 0.2, 0, 0.25, 1.35, c.P)
	for k = -3, 3 do
		local angle = k * PI / 7
		local dir = V(math.sin(angle), 0.45, -math.cos(angle)).Unit
		beam(c, head + dir * 0.5, head + dir * 1.25, 0.14, c.P)
	end
	beam(c, V(1, y - 0.2, 0), V(1.5, y + 2.6, 0), 0.5, c.P)
	col(c, 1.5, y + 2.4, 0, 0.9, 0.35, c.P)
	col(c, 1.5, y + 3.2, 0, 0.3, 0.75, c.A, Mat.Metal)
	ball(c, 1.5, y + 3.85, 0, 0.8, c.A, Mat.Neon)
	beam(c, V(-1, y - 0.2, 0), V(-1.2, y - 2, -0.6), 0.45, c.P)
	block(c, CFrame.new(-1.35, y - 1.4, -0.4) * CFrame.Angles(0, 0, 0.12), V(0.3, 1.5, 1), c.P)
end

-- 자유의 여신상(별 모양 요새 + 받침대) / 로도스 거상(항구를 가로질러 두 다리로 선 청동상)
function BUILDERS.statue(c)
	if c.grand then
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, WATER, Mat.Glass, 0.15)
		for _, sx in { -1, 1 } do
			box(c, sx * 3.3, 0, 0, 2.8, 1, 9.6, c.S)
			box(c, sx * 2.2, 1, 0, 2, 2.4, 2, c.S)
			beam(c, V(sx * 2.2, 3.3, 0), V(sx * 0.6, 8.3, 0), 0.9, c.P)
		end
		box(c, 0, 7.8, 0, 2, 1.2, 1.2, c.P)
		box(c, 0, 9, 0, 2.2, 2.4, 1.3, c.P)
		figureTop(c, 11.4)
	else
		box(c, 0, 0, 0, 6.8, 0.6, 6.8, c.S)
		block(c, CFrame.new(0, 0.3, 0) * CFrame.Angles(0, PI / 4, 0), V(6.8, 0.6, 6.8), c.S)
		box(c, 0, 0.6, 0, 4.2, 0.8, 4.2, c.S)
		box(c, 0, 1.4, 0, 3.4, 4, 3.4, c.S)
		box(c, 0, 5.4, 0, 3.9, 0.4, 3.9, c.S)
		col(c, 0, 5.8, 0, 2.8, 2.6, c.P)
		col(c, 0, 8.6, 0, 2.6, 2.2, c.P)
		box(c, 0, 10.8, 0, 2.3, 1.3, 1.3, c.P)
		figureTop(c, 12.1)
	end
end

-- 스카이타워: 오클랜드 도심 블록(도로 + 빌딩들 + 뒤쪽 스카이시티) 위에 바로 선 탑.
--   밑동의 네 다리 + 긴 탑신 + 아래가 벌어진 전망대(유리 2층 + 빛 띠) + 긴 안테나
local function skyTower(c: Ctx)
	box(c, 0, 0, 0, 9.8, 0.3, 9.8, rgb(96, 100, 108), Mat.Concrete)
	box(c, 0, 0.3, 0, 3.8, 0.08, 3.8, rgb(190, 188, 182), Mat.Concrete)
	local glass = rgb(120, 160, 200)
	-- 빌딩: { x, z, 가로, 높이, 세로, 색, 재질 }
	local buildings = {
		{ -3.3, 3.3, 2.8, 4.8, 2.6, glass, Mat.Glass },
		{ 3.3, 3.3, 2.8, 3.8, 2.6, rgb(215, 205, 185), Mat.Concrete },
		{ 3.5, -0.1, 2.2, 5.6, 2.4, mix(c.S, glass, 0.5), Mat.Glass },
		{ -3.5, -0.3, 2.2, 2.6, 2.6, rgb(200, 190, 175), Mat.Concrete },
		{ -3.4, -3.6, 2.4, 1.6, 2, rgb(225, 225, 220), Mat.Concrete },
		{ 3.4, -3.6, 2.4, 2.2, 2, mix(glass, WHITE, 0.3), Mat.Glass },
	}
	for _, b in buildings do
		box(c, b[1], 0.3, b[2], b[3], b[4], b[5], b[6], b[7])
	end
	box(c, 0, 0.3, 3.1, 3.4, 1.6, 2.6, mix(c.P, c.S, 0.35))
	for _, s in CORNERS do
		beam(c, V(s[1] * 1.1, 0.35, s[2] * 1.1), V(s[1] * 0.3, 3.2, s[2] * 0.3), 0.45, c.P)
	end
	col(c, 0, 0.3, 0, 11, 1.15, c.P)
	col(c, 0, 11.2, 0, 0.5, 1.9, c.P)
	col(c, 0, 11.7, 0, 0.5, 2.7, c.P)
	col(c, 0, 12.2, 0, 1.1, 3.2, c.S, Mat.Glass)
	col(c, 0, 12.6, 0, 0.3, 3.3, c.A, Mat.Neon)
	col(c, 0, 13.3, 0, 0.35, 3.4, c.P)
	col(c, 0, 13.65, 0, 0.7, 2.4, c.S, Mat.Glass)
	col(c, 0, 14.35, 0, 0.35, 2, c.P)
	col(c, 0, 14.7, 0, 1.2, 0.9, c.P)
	col(c, 0, 15.9, 0, 4.2, 0.45, c.P)
	col(c, 0, 20.1, 0, 1, 0.22, c.A)
	ball(c, 0, 21.3, 0, 0.4, c.A, Mat.Neon)
end

-- 남산타워: 계단식 초록 언덕 + 가느다란 탑신 + 전망대 원반 + 안테나 (스카이타워는 도심 블록 위 버전)
function BUILDERS.needle(c)
	if c.id == "skytower" then
		skyTower(c)
		return
	end
	col(c, 0, 0, 0, 1.2, 9.8, GRASS, Mat.Grass)
	col(c, 0.3, 1.2, 0.2, 1.1, 7.4, GRASS, Mat.Grass)
	col(c, 0.2, 2.3, 0.1, 1, 4.8, GRASS, Mat.Grass)
	for i = 0, 5 do
		local angle = i * TAU / 6 + 0.4
		local r = if i % 2 == 0 then 4.1 else 3.1
		ball(c, math.cos(angle) * r, if i % 2 == 0 then 1.6 else 2.6, math.sin(angle) * r, 1.1, LEAF, Mat.Grass)
	end
	col(c, 0, 3.3, 0, 1, 2.6, c.P)
	col(c, 0, 4.3, 0, 7.6, 1.1, c.P)
	col(c, 0, 11.9, 0, 0.4, 2.6, c.S)
	col(c, 0, 12.3, 0, 1.5, 3.2, c.S, Mat.Glass)
	col(c, 0, 12.8, 0, 0.35, 3.3, c.A, Mat.Neon)
	col(c, 0, 13.8, 0, 0.5, 3.4, c.P)
	col(c, 0, 14.3, 0, 0.8, 1.6, c.P)
	col(c, 0, 15.1, 0, 2.6, 0.6, c.P)
	col(c, 0, 17.7, 0, 1.8, 0.35, c.A)
	ball(c, 0, 19.7, 0, 0.45, c.A, Mat.Neon)
end

-- 에펠탑: 네 다리가 모이며 가늘어지는 격자 탑 + 다리 사이 아치 + 전망대 3곳
function BUILDERS.lattice(c)
	box(c, 0, 0, 0, 9.8, 0.2, 9.8, GRASS, Mat.Grass)
	local function legAt(y: number): number
		return 4 - 1.5 * (y - 0.5) / 3.7
	end
	for _, s in CORNERS do
		local sx, sz = s[1], s[2]
		beam(c, V(sx * 4, 0.5, sz * 4), V(sx * 2.5, 4.2, sz * 2.5), 0.9, c.P)
		beam(c, V(sx * 2.4, 4.6, sz * 2.4), V(sx * 1.3, 9.2, sz * 1.3), 0.6, c.P)
		beam(c, V(sx * 1.2, 9.6, sz * 1.2), V(sx * 0.35, 17, sz * 0.35), 0.4, c.P)
	end
	-- 다리 사이 아치(3토막)
	for i = 0, 3 do
		local rot = CFrame.Angles(0, i * PI / 2, 0)
		local low, high = legAt(1), legAt(3.2)
		local points = { V(-low, 1, -low), V(-1.7, 3.2, -high), V(1.7, 3.2, -high), V(low, 1, -low) }
		for k = 1, 3 do
			beam(c, rot * points[k], rot * points[k + 1], 0.35, c.S)
		end
	end
	box(c, 0, 4.2, 0, 6, 0.5, 6, c.S)
	box(c, 0, 4.05, 0, 6.2, 0.15, 6.2, c.A, Mat.Neon)
	box(c, 0, 9.2, 0, 3.3, 0.45, 3.3, c.S)
	box(c, 0, 9.05, 0, 3.5, 0.15, 3.5, c.A, Mat.Neon)
	box(c, 0, 13, 0, 1.9, 0.25, 1.9, c.S)
	box(c, 0, 17, 0, 1.3, 0.4, 1.3, c.S)
	box(c, 0, 17.4, 0, 0.8, 0.9, 0.8, c.P)
	col(c, 0, 18.3, 0, 2.6, 0.22, c.P)
	ball(c, 0, 21.05, 0, 0.45, c.A, Mat.Neon)
end

-- 콜로세움: 타원형 아케이드(기둥 + 층 띠), 앞쪽은 무너져 낮고 뒤쪽은 3층, 안쪽 관중석과 모래 경기장
function BUILDERS.ring(c)
	local a, b = 4.5, 3.7
	local count = 14
	local function point(i: number): Vector3
		local t = i / count * TAU
		return V(a * math.cos(t), 0, b * math.sin(t))
	end
	local function tall(i: number): boolean
		return i % count <= 8 -- 뒤쪽(+Z) 절반 남짓만 온전함
	end
	box(c, 0, 0, 0, 9.8, 0.2, 8.4, c.S)
	box(c, 0, 0.2, 0, 5.2, 0.15, 3.8, c.A)
	for i = 0, count - 1 do
		local t = i / count * TAU
		local p = point(i)
		local h = if tall(i) then 5.4 else 3.6
		local yaw = math.atan2(-b * math.cos(t), -a * math.sin(t))
		block(c, CFrame.new(p.X, 0.2 + h / 2, p.Z) * CFrame.Angles(0, yaw, 0), V(0.62, h, 0.7), c.P)
	end
	for j = 0, count / 2 - 1 do
		local i1, i2 = 2 * j, 2 * j + 2
		local p1, p2 = point(i1), point(i2)
		local levels = if tall(i1) and tall(i2) then { 1.9, 3.4, 5.2 } else { 1.9, 3.4 }
		for _, y in levels do
			local mid = (p1 + p2) / 2
			local cf = CFrame.lookAt(V(mid.X, y + 0.2, mid.Z), V(p2.X, y + 0.2, p2.Z))
			block(c, cf, V(0.75, 0.4, (p2 - p1).Magnitude + 0.3), c.P)
		end
	end
	-- 관중석(안쪽으로 기운 쐐기)
	local seats = 7
	for j = 0, seats - 1 do
		local t1, t2 = j / seats * TAU, (j + 1) / seats * TAU
		local q1 = V(3.5 * math.cos(t1), 0, 2.75 * math.sin(t1))
		local q2 = V(3.5 * math.cos(t2), 0, 2.75 * math.sin(t2))
		local mid = (q1 + q2) / 2
		local chord = q2 - q1
		local inward = V(chord.Z, 0, -chord.X).Unit
		if inward:Dot(mid) > 0 then
			inward = -inward
		end
		wedge(c, CFrame.new(mid.X, 1.2, mid.Z) * facing(inward.X, inward.Z), V(chord.Magnitude + 0.2, 2, 1.2), c.S)
	end
end

-- 타지마할: 대리석 기단 + 본당(아치 입구) + 양파 돔 + 작은 정자 4 + 첨탑 4 + 연못
function BUILDERS.dome(c)
	box(c, 0, 0, 0, 9.6, 1, 9.6, c.S)
	box(c, 0, 1, 0, 5.6, 4, 5.6, c.P)
	local portal = mix(c.S, BLACK, 0.3)
	for i = 0, 3 do
		block(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 2.6, -2.8), V(2, 3, 0.12), portal)
	end
	col(c, 0, 5, 0, 1.2, 3.8, c.P)
	ball(c, 0, 8.2, 0, 4.8, c.P)
	ball(c, 0, 10.4, 0, 2.2, c.P)
	col(c, 0, 11.3, 0, 1.3, 0.25, c.A, Mat.Metal)
	ball(c, 0, 12.75, 0, 0.4, c.A, Mat.Neon)
	for _, s in CORNERS do
		local x, z = s[1] * 2, s[2] * 2
		col(c, x, 5, z, 0.8, 0.9, c.P)
		ball(c, x, 6.05, z, 1, c.P)
	end
	for _, s in CORNERS do
		local x, z = s[1] * 4.2, s[2] * 4.2
		col(c, x, 1, z, 8, 0.8, c.P)
		col(c, x, 4.4, z, 0.2, 1.2, c.S)
		col(c, x, 9, z, 0.3, 1.2, c.S)
		ball(c, x, 9.75, z, 0.9, c.P)
	end
	box(c, 0, 1, -3.9, 0.9, 0.08, 1.7, WATER, Mat.Glass, 0.1)
end

-- 앙코르와트: 해자 + 섬 + 3단 기단 + 정면 계단 + 연꽃 봉오리 탑 5개(가운데가 가장 높음)
function BUILDERS.temple(c)
	box(c, 0, 0, 0, 9.8, 0.25, 9.8, WATER, Mat.Glass, 0.1)
	box(c, 0, 0.25, 0, 8.4, 0.3, 8.4, c.S)
	box(c, 0, 0.25, -4.55, 1.2, 0.3, 0.7, c.P)
	box(c, 0, 0.55, 0, 7.2, 1, 7.2, c.P)
	box(c, 0, 1.55, 0, 5.6, 1.1, 5.6, c.P)
	box(c, 0, 2.65, 0, 4, 1.2, 4, c.P)
	wedge(c, CFrame.new(0, 0.55 + 1.65, -3.1), V(1, 3.3, 2.2), c.A)
	local function lotus(x: number, z: number, base: number, tiers: number)
		local y = 3.85
		box(c, x, y, z, base, base * 0.8, base, c.P)
		y += base * 0.8
		for k = 1, tiers do
			local w = base * (1 - k / (tiers + 1.5))
			local h = base * 0.55
			box(c, x, y, z, w, h, w, c.P)
			y += h
		end
		ball(c, x, y + 0.1, z, base * 0.28, c.A)
	end
	lotus(0, 0, 1.8, 4)
	for _, s in CORNERS do
		lotus(s[1] * 1.35, s[2] * 1.35, 1.2, 3)
	end
	plant(c, -3.9, 0.55, -3.9, 1.4, 1.1, LEAF)
	plant(c, 3.9, 0.55, -3.9, 1.4, 1.1, LEAF)
end

-- 스핑크스: 엎드린 사자 몸 + 앞발 + 사람 머리(네메스 두건, 파란 줄무늬)
function BUILDERS.sphinx(c)
	box(c, 0, 0, 0, 9.8, 0.3, 7, c.S)
	local y = 0.3
	box(c, 0, y, 1.5, 2.8, 1.9, 5.4, c.P)
	cyl(c, CFrame.new(0, 2, 1.6) * ALONG_Z, 5, 2.8, c.P)
	ball(c, -1, y + 1.4, 3.2, 2.2, c.P)
	ball(c, 1, y + 1.4, 3.2, 2.2, c.P)
	box(c, 0, y, -1.9, 2.6, 3.1, 1.6, c.P)
	box(c, -0.85, y, -3.5, 0.8, 0.7, 2.6, c.P)
	box(c, 0.85, y, -3.5, 0.8, 0.7, 2.6, c.P)
	box(c, 0, 3.3, -1.95, 1.5, 1.9, 1.5, c.P)
	box(c, 0, 3.6, -1.6, 2.2, 2, 1.5, c.S)
	box(c, -0.95, 2.6, -2.75, 0.5, 1.6, 0.6, c.S)
	box(c, 0.95, 2.6, -2.75, 0.5, 1.6, 0.6, c.S)
	for _, sx in { -1, 1 } do
		box(c, sx * 1.12, 3.9, -1.6, 0.05, 0.25, 1.4, c.A)
		box(c, sx * 1.12, 4.5, -1.6, 0.05, 0.25, 1.4, c.A)
		box(c, sx * 0.35, 4.45, -2.72, 0.3, 0.15, 0.08, DARK)
	end
	box(c, 1.55, y, 2.8, 0.3, 0.3, 2.4, c.P)
end

-- 만리장성: 초록 봉우리 두 개를 넘어 지그재그로 이어지는 성벽(앞쪽 성가퀴, 뒤쪽 여장) + 봉우리 망루 + 골짜기 초소
function BUILDERS.wall(c)
	local ground = 0.3
	box(c, 0, 0, 0, 9.8, ground, 9.8, mix(c.S, WHITE, 0.25), Mat.Grass)
	local path = {
		V(-3.6, ground, -2),
		V(-1.9, 2.4, 0.2),
		V(0.1, ground, -1),
		V(2.2, 3, 1.4),
		V(3.7, ground, -0.8),
	}
	local dark = mix(c.P, BLACK, 0.2)
	for k = 1, #path - 1 do
		local p1, p2 = path[k], path[k + 1]
		-- 성벽 아래 비탈(쐐기): 높은 면이 봉우리 쪽
		local high, low = p2, p1
		if p1.Y > p2.Y then
			high, low = p1, p2
		end
		local flat = V(high.X - low.X, 0, high.Z - low.Z)
		local rise = high.Y - ground
		local mid = V((high.X + low.X) / 2, ground + rise / 2, (high.Z + low.Z) / 2)
		wedge(c, CFrame.lookAt(mid, mid - flat), V(2.8, rise, flat.Magnitude), c.S, Mat.Grass)
		-- 성벽 몸체 + 뒤쪽 여장 + 앞쪽 성가퀴 3개 (경로가 +X 로 가므로 로컬 -X 가 정면)
		local cf = CFrame.lookAt((p1 + p2) / 2, p2)
		local length = (p2 - p1).Magnitude + 0.3
		block(c, cf * CFrame.new(0, 0.5, 0), V(1.1, 1, length), c.P)
		block(c, cf * CFrame.new(0.46, 1.15, 0), V(0.18, 0.3, length), dark)
		for _, t in { -1, 0, 1 } do
			block(c, cf * CFrame.new(-0.46, 1.2, t * length / 3.2), V(0.18, 0.4, 0.45), dark)
		end
	end
	-- 봉우리 망루(깃발) + 골짜기 초소
	for _, k in { 2, 4 } do
		local p = path[k]
		box(c, p.X, p.Y - 0.3, p.Z, 1.7, 2, 1.7, c.P)
		box(c, p.X, p.Y + 1.7, p.Z, 2, 0.35, 2, dark)
		col(c, p.X + 0.6, p.Y + 2.05, p.Z + 0.6, 1.2, 0.1, DARK)
		box(c, p.X + 0.9, p.Y + 2.8, p.Z + 0.6, 0.6, 0.4, 0.05, c.A)
	end
	box(c, path[3].X, ground, path[3].Z, 1.4, 1.5, 1.4, c.P)
	box(c, path[3].X, ground + 1.5, path[3].Z, 1.6, 0.3, 1.6, dark)
	ball(c, -3.6, 0.9, 2.8, 1.2, LEAF, Mat.Grass)
	ball(c, 3.7, 0.9, 3.4, 1.3, LEAF, Mat.Grass)
	ball(c, 1, 0.8, -3.8, 1, LEAF, Mat.Grass)
end

-- 기자 피라미드: 모래 바닥 + 크기가 다른 계단식 피라미드 3개(금빛 꼭대기) + 야자수
function BUILDERS.pyramid(c)
	box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Sand)
	local top = stepped(c, -2.4, 1.4, 0.3, 4.8, 3.9, 8, c.P)
	box(c, -2.4, top, 1.4, 0.4, 0.3, 0.4, c.A, Mat.Neon)
	top = stepped(c, 2.1, 0.9, 0.3, 4.2, 3.4, 7, c.P)
	box(c, 2.1, top, 0.9, 0.35, 0.3, 0.35, c.A, Mat.Neon)
	stepped(c, 0.4, -3.3, 0.3, 2.6, 2.1, 5, mix(c.P, c.S, 0.5))
	plant(c, -3.9, 0.3, -2.4, 1.6, 1.1, LEAF)
	plant(c, -2.9, 0.3, -3.8, 1.2, 0.9, LEAF)
end

-- 치첸이트사 / 엘도라도: 9단 계단 피라미드 + 사면 계단 + 꼭대기 신전 (+ 불가사의 등급은 황금 태양)
function BUILDERS.steps(c)
	box(c, 0, 0, 0, 9.8, 0.25, 9.8, c.S, Mat.Grass)
	local y = 0.25
	for i = 0, 8 do
		local w = 7.8 - i * 0.55
		box(c, 0, y, 0, w, 0.72, w, c.P)
		y += 0.72
	end
	local rise = y - 0.25
	for i = 0, 3 do
		local rot = CFrame.Angles(0, i * PI / 2, 0)
		wedge(c, rot * CFrame.new(0, 0.25 + rise / 2, -3.15), V(1.4, rise, 2.9), c.A)
	end
	box(c, -0.85, 0.25, -4.45, 0.35, 0.5, 0.35, c.A)
	box(c, 0.85, 0.25, -4.45, 0.35, 0.5, 0.35, c.A)
	box(c, 0, y, 0, 2.6, 1.7, 2.6, c.P)
	box(c, 0, y + 1.7, 0, 3, 0.35, 3, c.P)
	box(c, 0, y, -1.28, 1, 1.1, 0.1, DARK)
	box(c, 0, y, 1.28, 1, 1.1, 0.1, DARK)
	for _, s in CORNERS do
		plant(c, s[1] * 4.3, 0.25, s[2] * 4.3, 1, 1.2, c.S)
	end
	if c.grand then
		cyl(c, CFrame.new(0, y + 3.6, 0) * ALONG_Z, 0.3, 2.4, c.A, Mat.Neon)
		for _, s in CORNERS do
			ball(c, s[1] * 1.3, y + 0.35, s[2] * 1.3, 0.5, c.A, Mat.Neon)
		end
	end
end

-- 마추픽추: 앞으로 내려가는 계단식 밭 + 뒤쪽의 뾰족한 와이나픽추 봉우리 + 돌집 유적
function BUILDERS.terraces(c)
	box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.S, BLACK, 0.2), Mat.Grass)
	for i = 0, 4 do
		local top = 3.4 - i * 0.65
		local front = -0.6 - i * 0.95
		local depth = 4.7 - front
		local w = 9.2 - i * 0.6
		local z = (front + 4.7) / 2
		box(c, 0, 0.25, z, w, top - 0.45, depth, c.P)
		box(c, 0, top - 0.2, z, w, 0.2, depth, c.S, Mat.Grass)
	end
	-- 와이나픽추: 조금씩 비틀어 쌓은 바위 덩어리로 만든 가파른 봉우리(위로 갈수록 바위색)
	local crags = {
		{ 3.8, 3, 3.4, 0.3 },
		{ 3, 2.7, 2.8, -0.35 },
		{ 2.2, 2.5, 2.1, 0.55 },
		{ 1.4, 2, 1.4, -0.2 },
		{ 0.7, 1, 0.7, 0.4 },
	}
	local y = 3.2
	for k, crag in crags do
		local color = mix(c.S, c.P, (k - 1) / 4)
		local cf = CFrame.new(2.2 + k * 0.1, y + crag[2] / 2, 2.3 + k * 0.05) * CFrame.Angles(0.06, crag[4], -0.05)
		block(c, cf, V(crag[1], crag[2], crag[3]), color, if k < 4 then Mat.Grass else nil)
		y += crag[2] * 0.85
	end
	box(c, -3.2, 3.4, 0.6, 1.6, 0.8, 1.2, c.P)
	box(c, -1.4, 3.4, 1.5, 1.2, 0.9, 1.6, c.P)
	box(c, -3, 3.4, 3.3, 1.8, 1, 1.4, c.P)
	box(c, -0.6, 3.4, 3.8, 1, 0.7, 1, c.P)
	box(c, -1.2, 3.4, -0.1, 1.3, 0.9, 1, c.P)
	gable(c, -1.2, 4.3, -0.1, 1.5, 1.2, 0.7, rgb(180, 150, 90))
end

-- 페트라(알카즈네): 붉은 절벽 + 협곡 벽 + 바위를 깎은 2층 신전 정면(기둥, 박공, 원형 정자)
function BUILDERS.facade(c)
	box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.P, SAND, 0.6), Mat.Sand)
	box(c, 0, 0.25, 3.2, 9.8, 14, 3.2, c.S)
	block(c, CFrame.new(-2.5, 14.6, 3.4) * CFrame.Angles(0, 0, 0.3), V(4.2, 2.2, 2.6), c.S)
	block(c, CFrame.new(2.6, 14.9, 3) * CFrame.Angles(0.2, 0, -0.25), V(3.6, 2.6, 2.4), c.S)
	box(c, -4.35, 0.25, 0.5, 1.1, 11, 2.2, c.S)
	box(c, 4.35, 0.25, 0.5, 1.1, 12, 2.2, c.S)
	-- 아래층: 기둥 6개 + 엔타블러처 + 박공 + 입구
	box(c, 0, 0.25, 1.1, 6.6, 0.45, 1.3, c.P)
	for k = 0, 5 do
		col(c, -2.75 + k * 1.1, 0.7, 0.85, 4.3, 0.55, c.P)
	end
	box(c, 0, 5, 1, 6.8, 0.7, 1.2, c.P)
	wedge(c, CFrame.new(-1.15, 6.3, 1) * CFrame.Angles(0, PI / 2, 0), V(1, 1.2, 2.3), c.P)
	wedge(c, CFrame.new(1.15, 6.3, 1) * CFrame.Angles(0, -PI / 2, 0), V(1, 1.2, 2.3), c.P)
	box(c, 0, 0.7, 1.57, 1.3, 2.6, 0.06, DARK)
	-- 위층: 양쪽 누각(반쪽 박공) + 가운데 원형 정자와 항아리
	box(c, 0, 6.9, 1, 6.8, 0.4, 1.2, c.P)
	for _, sx in { -1, 1 } do
		box(c, sx * 2.6, 7.3, 1, 1.6, 3, 1, c.P)
		wedge(c, CFrame.new(sx * 2.6, 10.7, 1) * CFrame.Angles(0, -sx * PI / 2, 0), V(1, 0.8, 1.6), c.P)
	end
	col(c, 0, 7.3, 1, 3.2, 1.9, c.P)
	col(c, 0, 10.5, 1, 0.35, 2.3, c.P)
	col(c, 0, 10.85, 1, 0.8, 1.4, c.P)
	ball(c, 0, 12, 1, 0.7, c.A)
end

-- 모아이: 잔디 + 뒤쪽 바다 + 제단(아후) 위에 긴 얼굴의 석상 5개(일부는 붉은 모자 푸카오)
function BUILDERS.moai(c)
	box(c, 0, 0, -0.95, 9.8, 0.3, 7.9, c.S, Mat.Grass)
	box(c, 0, 0, 3.95, 9.8, 0.2, 1.9, WATER, Mat.Glass, 0.1)
	box(c, 0, 0.3, 1.2, 9.6, 0.8, 2.2, mix(c.P, WHITE, 0.15))
	local xs = { -3.7, -1.85, 0, 1.85, 3.7 }
	local scales = { 0.9, 1, 1.12, 1, 0.92 }
	for k, x in xs do
		local s = scales[k]
		local y = 1.1
		box(c, x, y, 1.2, 1.3 * s, 1.5 * s, s, c.P)
		local headY = y + 1.5 * s
		local depth = 1.05 * s
		local front = 1.25 - depth / 2
		box(c, x, headY, 1.25, 1.15 * s, 2.3 * s, depth, c.P)
		box(c, x, headY + 1.35 * s, front - 0.1, 1.2 * s, 0.35 * s, 0.35 * s, c.P)
		wedge(c, CFrame.new(x, headY + 0.85 * s, front - 0.2 * s), V(0.35 * s, 0.9 * s, 0.4 * s), c.P)
		for _, sx in { -1, 1 } do
			box(c, x + sx * (0.575 * s + 0.05), headY + 0.8 * s, 1.25, 0.12, 1 * s, 0.35 * s, c.P)
		end
		if k % 2 == 1 then
			col(c, x, headY + 2.3 * s, 1.25, 0.55 * s, s, c.A)
		end
	end
end

-- 스톤헨지: 둥근 잔디 + 상인방을 얹은 바깥 원(일부 무너짐) + 안쪽 말굽 모양 삼석탑 5개 + 제단석 + 힐스톤
function BUILDERS.stones(c)
	col(c, 0, 0, 0, 0.25, 9.8, c.S, Mat.Grass)
	local y = 0.25
	local r = 3.9
	local count = 12
	local missing = { [4] = true, [9] = true }
	for i = 0, count - 1 do
		if not missing[i] then
			block(c, CFrame.Angles(0, i / count * TAU, 0) * CFrame.new(0, y + 1.1, -r), V(0.75, 2.2, 0.5), c.P)
		end
	end
	local chord = 2 * r * math.sin(PI / count) + 0.5
	for _, i in { 0, 1, 2, 5, 6, 10, 11 } do
		local cf = CFrame.Angles(0, (i + 0.5) / count * TAU, 0) * CFrame.new(0, y + 2.4, -r * math.cos(PI / count))
		block(c, cf, V(chord, 0.4, 0.5), c.P)
	end
	block(c, CFrame.Angles(0, 4 / count * TAU, 0) * CFrame.new(0, y + 0.25, -r), V(2, 0.5, 0.75), c.P)
	-- 안쪽 말굽(정면 -Z 쪽이 열림)
	for k, angle in { PI, PI - 0.9, PI + 0.9, PI - 1.8, PI + 1.8 } do
		local h = if k == 1 then 3.2 elseif k <= 3 then 2.8 else 2.5
		local frame = CFrame.Angles(0, angle, 0) * CFrame.new(0, y, -2)
		block(c, frame * CFrame.new(-0.45, h / 2, 0), V(0.55, h, 0.5), c.P)
		block(c, frame * CFrame.new(0.45, h / 2, 0), V(0.55, h, 0.5), c.P)
		block(c, frame * CFrame.new(0, h + 0.2, 0), V(1.6, 0.4, 0.55), c.P)
	end
	box(c, 0, y, 0.6, 1.4, 0.25, 0.5, mix(c.P, BLACK, 0.2))
	block(c, CFrame.new(0.9, y + 0.9, -4.6) * CFrame.Angles(0, 0, 0.12), V(0.7, 1.8, 0.5), c.P)
end

-- 바빌론 공중정원: 4단 테라스(그늘진 회랑 띠) + 초록 정원 + 늘어진 덩굴 + 정면 폭포 + 연못
function BUILDERS.gardens(c)
	box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.P, WHITE, 0.15))
	box(c, 0, 0.3, -4.4, 4, 0.12, 0.9, c.A, Mat.Glass, 0.2)
	local sizes = { 8.2, 6.4, 4.6, 2.8 }
	local shade = mix(c.P, BLACK, 0.45)
	local y = 0.3
	for i, w in sizes do
		box(c, 0, y, 0, w, 2, w, c.P)
		box(c, 0, y + 0.5, 0, w + 0.06, 0.8, w + 0.06, shade)
		box(c, 0, y + 2, 0, w - 0.2, 0.25, w - 0.2, c.S, Mat.Grass)
		box(c, 0, y, -w / 2 - 0.08, 0.9, 2.3, 0.12, c.A, Mat.Neon, 0.35)
		if i < #sizes then
			for _, sx in { -1, 1 } do
				box(c, sx * w * 0.3, y + 0.9, -w / 2 - 0.08, 0.6, 1.35, 0.15, c.S, Mat.Grass)
				ball(c, sx * (w / 2 - 0.45), y + 2.6, -(w / 2 - 0.45), 0.9, c.S, Mat.Grass)
			end
		end
		y += 2
	end
	box(c, 0, y + 0.25, 0, 1.2, 1.2, 1.2, c.P)
	plant(c, 0.9, y + 0.25, 0.9, 1.6, 1.2, c.S)
end

-- 바벨탑: 점점 좁아지는 원통 5층(어두운 회랑 + 밝은 난간) + 층 사이를 감아 오르는 경사로 + 미완성 꼭대기
function BUILDERS.spiral(c)
	local diameters = { 9.4, 7.6, 5.8, 4, 2.4 }
	local h = 3
	local shade = mix(c.S, BLACK, 0.2)
	for k, d in diameters do
		local y = (k - 1) * h
		col(c, 0, y, 0, h, d, shade)
		col(c, 0, y + h - 0.45, 0, 0.45, d + 0.1, c.P)
		col(c, 0, y, 0, 0.5, d + 0.1, c.P)
	end
	-- 경사로: 층 k 의 윗면(난간 고리)에서 한 바퀴 돌며 다음 층 윗면까지 올라감
	for k = 1, #diameters - 1 do
		local outer, inner = diameters[k] / 2, diameters[k + 1] / 2
		local segments = 9 - k
		local r = (outer + inner) / 2 / math.cos(PI / segments)
		local base = k * h
		for j = 0, segments - 1 do
			local t1 = (j / segments + k * 0.3) * TAU
			local t2 = ((j + 1) / segments + k * 0.3) * TAU
			local p1 = V(r * math.cos(t1), base + j / segments * h, r * math.sin(t1))
			local p2 = V(r * math.cos(t2), base + (j + 1) / segments * h, r * math.sin(t2))
			local cf = CFrame.lookAt((p1 + p2) / 2, p2)
			block(c, cf * CFrame.new(0, 0.15, 0), V(0.7, 0.3, (p2 - p1).Magnitude + 0.1), c.P)
		end
	end
	local top = #diameters * h
	box(c, -0.4, top, 0.3, 1, 1.4, 0.9, c.P)
	block(c, CFrame.new(0.5, top + 0.4, -0.3) * CFrame.Angles(0, 0.4, 0.2), V(0.8, 0.8, 0.8), c.P)
end

-- 무 대륙: 가라앉는 밀림 대륙(바다 + 얕은 여울 + 두 덩어리 땅) + 가운데 계단식 석조 신전(금 지붕, 금빛 태양 원반)
--   + 금빛 화로 + 밀림 나무 + 물에 잠겨 가는 무너진 돌기둥과 돌문
local function lostContinent(c: Ctx)
	local jungle = rgb(62, 140, 70)
	col(c, 0, 0, 0, 0.3, 9.8, c.S, Mat.Glass, 0.1)
	col(c, 0, 0, 0, 0.35, 8.8, mix(c.S, WHITE, 0.3), Mat.Glass, 0.1)
	col(c, 0.3, 0, 0.5, 0.75, 7.2, c.P)
	col(c, 0.3, 0.75, 0.5, 0.2, 6.9, jungle, Mat.Grass)
	col(c, -2.5, 0, -2.2, 0.55, 3.2, c.P)
	col(c, -2.5, 0.55, -2.2, 0.15, 2.9, jungle, Mat.Grass)
	local ground = 0.95
	local tx, tz = 0.4, 0.9
	local y = ground
	for _, tier in { { 4.4, 0.8 }, { 3.5, 0.8 }, { 2.6, 0.8 }, { 1.8, 0.7 } } do
		box(c, tx, y, tz, tier[1], tier[2], tier[1], c.P)
		y += tier[2]
	end
	wedge(c, CFrame.new(tx, (ground + y) / 2, tz - 1.95), V(1, y - ground, 2.1), mix(c.P, WHITE, 0.2))
	for _, s in CORNERS do
		ball(c, tx + s[1] * 1.55, ground + 1.8, tz + s[2] * 1.55, 0.4, c.A, Mat.Neon)
	end
	box(c, tx, y, tz + 0.1, 1.3, 1, 1.2, mix(c.P, WHITE, 0.12))
	box(c, tx, y, tz - 0.51, 0.45, 0.7, 0.05, DARK)
	box(c, tx, y + 1, tz + 0.1, 1.6, 0.2, 1.5, c.A, Mat.Metal)
	box(c, tx, y + 1.2, tz + 0.1, 0.9, 0.3, 0.9, c.A, Mat.Metal)
	cyl(c, CFrame.new(tx, y + 1.95, tz + 0.1) * ALONG_Z, 0.12, 0.9, c.A, Mat.Neon)
	-- 밀림: { x, z, 줄기 높이, 잎 지름, 바닥 높이 }
	for k, t in
		{
			{ -2.6, 2.7, 1.4, 1.6, ground },
			{ 2.9, 2.8, 1.2, 1.4, ground },
			{ 3.2, -0.9, 1.6, 1.5, ground },
			{ -2.8, 0.4, 1.1, 1.3, ground },
			{ -2.6, -2.3, 1.2, 1.3, 0.7 },
			{ 2.1, -2.2, 1, 1.2, ground },
		}
	do
		plant(c, t[1], t[5], t[2], t[3], t[4], if k % 2 == 0 then LEAF else jungle)
	end
	ball(c, -1, ground + 0.15, 3.3, 1, LEAF, Mat.Grass)
	ball(c, 3.3, ground + 0.1, 1.2, 0.9, jungle, Mat.Grass)
	ball(c, -1.4, 0.8, -3, 0.8, LEAF, Mat.Grass)
	-- 물에 잠겨 가는 유적
	block(c, CFrame.new(3, 0.95, -3.1) * CFrame.Angles(0.25, 0.3, 0.35), V(0.55, 1.6, 0.55), c.P)
	col(c, 3.9, 0, -1.9, 0.9, 0.5, c.P)
	box(c, -3.9, 0, 1, 0.45, 1.5, 0.45, c.P)
	box(c, -3.9, 0, 2.2, 0.45, 1.2, 0.45, c.P)
	block(c, CFrame.new(-3.9, 1.55, 1.6) * CFrame.Angles(0.12, 0, 0), V(0.55, 0.35, 1.8), c.P)
end

-- 아틀란티스: 물과 땅이 번갈아 도는 동심원 섬 + 가운데 원형 신전(빛나는 수정 첨탑) + 흰 탑 6개 + 다리
-- (무 대륙은 밀림 + 계단식 석조 신전 버전)
function BUILDERS.island(c)
	if c.id == "mu" then
		lostContinent(c)
		return
	end
	col(c, 0, 0, 0, 0.3, 9.8, c.S, Mat.Glass, 0.1)
	col(c, 0, 0, 0, 0.55, 8.4, c.P)
	col(c, 0, 0, 0, 0.6, 6.8, c.S, Mat.Glass, 0.1)
	col(c, 0, 0, 0, 0.8, 5.4, GRASS, Mat.Grass)
	col(c, 0, 0, 0, 0.85, 4, c.S, Mat.Glass, 0.1)
	col(c, 0, 0, 0, 1.2, 2.8, c.P)
	box(c, 0, 0.6, -2.45, 0.5, 0.15, 2.3, c.P)
	col(c, 0, 1.2, 0, 0.3, 2.4, c.P)
	for i = 0, 5 do
		local angle = i * TAU / 6
		col(c, 0.9 * math.cos(angle), 1.5, 0.9 * math.sin(angle), 1.5, 0.25, c.P)
	end
	col(c, 0, 1.5, 0, 1.5, 0.9, c.A, Mat.Neon)
	col(c, 0, 3, 0, 0.3, 2.4, c.P)
	ball(c, 0, 3.3, 0, 1.9, c.P)
	col(c, 0, 4.1, 0, 2.6, 0.35, c.A, Mat.Neon)
	ball(c, 0, 6.8, 0, 0.6, c.A, Mat.Neon)
	for i = 0, 5 do
		local angle = i * TAU / 6 + PI / 6
		local x, z = 3.8 * math.cos(angle), 3.8 * math.sin(angle)
		col(c, x, 0.55, z, 1.8, 0.55, c.P)
		ball(c, x, 2.5, z, 0.45, c.A, Mat.Neon)
	end
end

-- 용궁 / 샹그릴라: 계단 기단 위 3층 전각(들린 추녀 기와지붕) + 꼭대기 보주 + 등롱 + 떠다니는 빛 구슬
function BUILDERS.pagoda(c)
	box(c, 0, 0, 0, 9.6, 0.6, 9.6, c.S)
	box(c, 0, 0.6, 0, 7.4, 0.4, 7, mix(c.P, WHITE, 0.5))
	wedge(c, CFrame.new(0, 0.5, -4.2), V(1.6, 1, 1.2), mix(c.P, WHITE, 0.5))
	box(c, 0, 1, 0, 6, 2, 5.2, c.P)
	box(c, 0, 1, -2.62, 1.4, 1.5, 0.1, DARK)
	roof(c, 0, 3, 0, 8.4, 7.2, 1.4, c.S)
	box(c, 0, 4.2, 0, 4.4, 1.9, 3.8, c.P)
	roof(c, 0, 6.1, 0, 6.6, 5.6, 1.3, c.S)
	box(c, 0, 7.2, 0, 3, 1.7, 2.6, c.P)
	roof(c, 0, 8.9, 0, 4.8, 4, 1.2, c.S)
	col(c, 0, 10.3, 0, 1.4, 0.3, c.A, Mat.Metal)
	ball(c, 0, 12, 0, 0.7, c.A, Mat.Neon)
	for _, sx in { -1, 1 } do
		col(c, sx * 4.2, 0.6, -4.2, 1.2, 0.2, DARK)
		ball(c, sx * 4.2, 2, -4.2, 0.5, c.A, Mat.Neon)
	end
	ball(c, -4.1, 7.5, 1.5, 0.9, c.A, Mat.Glass, 0.5)
	ball(c, 4.2, 9.2, -0.8, 0.7, c.A, Mat.Glass, 0.5)
	ball(c, 3.6, 11.4, 2.4, 0.6, c.A, Mat.Glass, 0.5)
end

-- 하늘섬: 땅에 닿지 않고 떠 있는 바위섬(아래로 뾰족) + 잔디 + 나무 + 연못과 폭포 + 구름 + 작은 신전
function BUILDERS.skyisland(c)
	local rock = Mat.Slate
	col(c, 0, 7.2, 0, 1.2, 9, c.S, rock)
	col(c, 0.3, 5.8, -0.2, 1.4, 7, c.S, rock)
	col(c, -0.2, 4.4, 0.3, 1.4, 5, c.S, rock)
	col(c, 0.2, 3.1, 0.1, 1.3, 3, c.S, rock)
	ball(c, 0.1, 2.8, 0.1, 1.6, c.S, rock)
	ball(c, -2.6, 6.8, 1.6, 2.4, c.S, rock)
	ball(c, 2.4, 6.2, -1.8, 2.2, c.S, rock)
	col(c, 0, 8.4, 0, 0.5, 9.4, c.P)
	col(c, 1.8, 8.9, 1.6, 2.8, 0.6, WOOD, Mat.Wood)
	ball(c, 1.8, 12.4, 1.6, 2.6, mix(c.P, BLACK, 0.25))
	ball(c, 1, 11.8, 2.3, 1.8, mix(c.P, BLACK, 0.15))
	ball(c, 2.6, 11.9, 1, 1.7, mix(c.P, BLACK, 0.15))
	col(c, -1.2, 8.85, -2.6, 0.12, 2.2, WATER, Mat.Glass, 0.15)
	box(c, -1.2, 8.85, -4.1, 0.9, 0.12, 1.4, WATER, Mat.Glass, 0.15)
	box(c, -1.2, 2.4, -4.75, 1, 6.55, 0.2, c.A, Mat.Neon, 0.35)
	ball(c, -1.2, 2.4, -4.3, 1.2, c.A, Mat.SmoothPlastic, 0.4)
	ball(c, -3, 3.4, -1.5, 2, CLOUD, Mat.SmoothPlastic, 0.2)
	ball(c, 3, 4, 1.8, 2.4, CLOUD, Mat.SmoothPlastic, 0.2)
	ball(c, 0.6, 2.2, 2.6, 1.8, CLOUD, Mat.SmoothPlastic, 0.2)
	box(c, -2.9, 8.9, 1.2, 0.35, 1.6, 0.35, CLOUD, Mat.Marble)
	box(c, -1.7, 8.9, 1.2, 0.35, 1.6, 0.35, CLOUD, Mat.Marble)
	box(c, -2.3, 10.5, 1.2, 1.7, 0.3, 0.6, CLOUD, Mat.Marble)
	ball(c, 4.2, 6.6, -2.8, 0.9, c.S, rock)
	ball(c, -4.2, 9.8, -0.8, 0.7, c.S, rock)
end

-- 세계수: 뻗은 뿌리 + 굵은 줄기 + 가지 + 잎 공 캐노피 + 빛나는 열매
function BUILDERS.tree(c)
	col(c, 0, 0, 0, 0.3, 9.6, mix(c.S, BLACK, 0.4), Mat.Grass)
	for i = 0, 5 do
		local angle = i * TAU / 6 + 0.3
		local dir = V(math.cos(angle), 0, math.sin(angle))
		beam(c, dir * 0.9 + V(0, 2.2, 0), dir * 4.1 + V(0, 0.45, 0), 0.85, c.P)
	end
	col(c, 0, 0.3, 0, 5.2, 3, c.P)
	col(c, 0, 5.5, 0, 3, 2.4, c.P)
	col(c, 0, 8.5, 0, 2.5, 1.8, c.P)
	local leaves = {}
	for i = 0, 4 do
		local angle = i * TAU / 5 + 0.2
		local dir = V(math.cos(angle), 0, math.sin(angle))
		beam(c, V(0, 9.3, 0), dir * 2.8 + V(0, 12.4, 0), 0.8, c.P)
		table.insert(leaves, dir * 2.9 + V(0, 13.2, 0))
	end
	ball(c, 0, 15, 0, 7, c.S, Mat.Grass)
	ball(c, 0, 18.6, 0, 4.4, c.S, Mat.Grass)
	for _, p in leaves do
		ball(c, p.X, p.Y, p.Z, 3.8, mix(c.S, BLACK, 0.12), Mat.Grass)
	end
	-- 열매: 잎 공 표면 바로 바깥
	local fruits = {
		V(0, 15, 0) + V(-0.6, 0.3, -1).Unit * 3.5,
		V(0, 15, 0) + V(0.8, 0.6, -0.4).Unit * 3.5,
		V(0, 18.6, 0) + V(-0.3, 0.5, -1).Unit * 2.2,
		leaves[1] + V(0.2, 0.4, -1).Unit * 1.9,
		leaves[2] + V(-0.4, 0.2, -1).Unit * 1.9,
		leaves[3] + V(-1, 0.3, -0.2).Unit * 1.9,
		leaves[4] + V(0.3, -0.2, -1).Unit * 1.9,
	}
	for _, p in fruits do
		ball(c, p.X, p.Y, p.Z, 0.7, c.A, Mat.Neon)
	end
	col(c, 0, 0.3, 0, 0.08, 6, c.A, Mat.Neon, 0.5)
end

-- 하버 브리지: 항구 물 + 양쪽 기슭 + 끝마다 화강암 탑문 2개 + 나란한 강철 아치 두 줄(끝은 두껍고 꼭대기는 얇음)
--   + 아치를 꿰뚫고 지나는 도로 상판 + 아치에 매단 멜대 + 아치 사이 가새
--   (오페라하우스는 건물 이미지 상표 문제로 넣지 않음)
function BUILDERS.bridge(c)
	local granite = rgb(208, 196, 172)
	local deckY, deckTop = 2.2, 2.55
	box(c, 0, 0, 0, 9.8, 0.25, 9.8, WATER, Mat.Glass, 0.1)
	for _, sx in { -1, 1 } do
		box(c, sx * 4.2, 0, 0, 1.4, 0.6, 9.8, GRASS, Mat.Grass)
		box(c, sx * 4.3, 0.6, 0, 1.2, deckY - 0.6, 4.4, granite, Mat.Granite)
		for _, sz in { -1, 1 } do
			box(c, sx * 4.3, deckY, sz * 1.75, 1.1, 1.85, 0.9, granite, Mat.Granite)
			box(c, sx * 4.3, deckY + 1.85, sz * 1.75, 0.8, 0.4, 0.65, granite, Mat.Granite)
		end
	end
	box(c, 0, deckY, 0, 9.8, deckTop - deckY, 2.6, c.S)
	-- 아치: 위·아래 현(포물선) 사이를 비스듬한 토막으로 채움. 발은 탑문 아래 기슭(x = ±span)
	local span = 3.7
	local function curve(x: number, crown: number, foot: number): number
		local u = x / span
		return crown - (crown - foot) * u * u
	end
	local function upper(x: number): number
		return curve(x, 5.9, 3.3)
	end
	local function lower(x: number): number
		return curve(x, 5.3, 0.6)
	end
	local function middle(x: number): number
		return (upper(x) + lower(x)) / 2
	end
	local segments = 7
	for _, sz in { -1, 1 } do
		for k = 0, segments - 1 do
			local x1 = span * (2 * k / segments - 1)
			local x2 = span * (2 * (k + 1) / segments - 1)
			local p1, p2 = V(x1, middle(x1), sz), V(x2, middle(x2), sz)
			local along = p2 - p1
			local depth = (upper(x1) - lower(x1) + upper(x2) - lower(x2)) / 2 * math.abs(along.X) / along.Magnitude
			block(c, CFrame.lookAt((p1 + p2) / 2, p2), V(0.35, depth, along.Magnitude + depth * 0.4), c.P)
		end
		-- 멜대(아치 아래 현에서 상판까지)
		for _, x in { -2.1, -0.8, 0.8, 2.1 } do
			box(c, x, deckTop, sz, 0.12, lower(x) - deckTop + 0.1, 0.12, c.S)
		end
	end
	for _, x in { -2.4, 0, 2.4 } do
		beam(c, V(x, middle(x), -1), V(x, middle(x), 1), 0.2, c.S)
	end
	beam(c, V(-2.4, middle(-2.4), -1), V(0, middle(0), 1), 0.16, c.S)
	beam(c, V(2.4, middle(2.4), -1), V(0, middle(0), 1), 0.16, c.S)
end

-- 12사도 바위: 바다 + 왼쪽(-X)을 두른 사암 절벽(덤불 윗면, 아래가 젖어 어두움) + 절벽 밑 모래 해변과 물거품
--   + 탁 트인 바다에 흩어져 솟은 사암 기둥들(밑동은 파도에 파먹히고 위로 갈수록 좁고 비틀림) + 무너진 기둥 밑동
function BUILDERS.seastacks(c)
	box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
	local wet = mix(c.P, BLACK, 0.22)
	local pale = mix(c.P, WHITE, 0.15)
	local cliff = mix(c.P, ROCK, 0.25)
	local scrub = mix(LEAF, c.P, 0.2)
	-- 절벽: { x, z, 가로, 깊이, 높이 }
	local cliffs = {
		{ -4, 0.9, 1.8, 8, 5.2 },
		{ -2.4, 4.1, 1.6, 1.6, 4.6 },
		{ -4.2, -4, 1.4, 1.8, 2.8 },
	}
	for _, cl in cliffs do
		local x, z, w, d, h = cl[1], cl[2], cl[3], cl[4], cl[5]
		box(c, x, 0, z, w, h * 0.25, d, wet)
		box(c, x, h * 0.25, z, w - 0.2, h * 0.75, d - 0.2, cliff)
		box(c, x, h, z, w - 0.3, 0.3, d - 0.3, scrub, Mat.Grass)
	end
	box(c, -2.75, 0.3, 0.4, 0.7, 0.12, 5.2, SAND, Mat.Sand)
	box(c, -2.3, 0.3, 0.4, 0.3, 0.1, 5.2, c.A, Mat.SmoothPlastic, 0.15)
	-- 바위 기둥: 밑동(파먹혀 가늘고 젖음) → 몸통(가장 넓음) → 꼭대기(좁고 비틀림)
	local function stack(x: number, z: number, h: number, w: number, twist: number)
		col(c, x, 0.3, z, 0.1, w * 1.35, c.A, Mat.SmoothPlastic, 0.2)
		local y = 0.3
		block(c, CFrame.new(x, y + h * 0.12, z) * CFrame.Angles(0, twist, 0), V(w * 0.7, h * 0.24 + 0.1, w * 0.68), wet)
		y += h * 0.24
		local cf = CFrame.new(x + w * 0.05, y + h * 0.2, z - w * 0.04) * CFrame.Angles(0, twist + 0.3, 0.035)
		block(c, cf, V(w, h * 0.42, w * 0.88), c.P)
		y += h * 0.4
		cf = CFrame.new(x - w * 0.06, y + h * 0.17, z + w * 0.05) * CFrame.Angles(0.04, twist - 0.25, -0.04)
		block(c, cf, V(w * 0.66, h * 0.34, w * 0.6), pale)
	end
	stack(-1.3, 2.5, 5.4, 1.2, 0.2)
	stack(0.6, 3.6, 4.2, 1.05, -0.4)
	stack(0, 0.5, 6.4, 1.3, 0.6)
	stack(2.4, 1.7, 4.8, 1.1, 0.1)
	stack(1.7, -1.6, 5.6, 1.2, -0.3)
	stack(-1.4, -1.7, 3.4, 1, 0.9)
	stack(3.4, -3.5, 3, 1, 0.4)
	-- 무너진 기둥(밑동만)
	col(c, 0, 0.3, -3.6, 0.1, 1.6, c.A, Mat.SmoothPlastic, 0.2)
	block(c, CFrame.new(0, 0.75, -3.6) * CFrame.Angles(0.1, 0.4, 0.08), V(1, 1, 0.9), wet)
end

-- 그레이트 배리어 리프: 짙은 바다 + 밝은 청록 산호 여울 + 가지 산호(분홍·주황) + 뇌 산호(노랑·보라 공)
--   + 탁자 산호 + 부채 산호 + 관 산호 + 헤엄치는 바다거북. 낮고 넓게(위에서 잘 보이도록)
function BUILDERS.reef(c)
	local purple = rgb(150, 90, 215)
	local orange = rgb(255, 140, 60)
	local tableColor = rgb(110, 205, 170)
	box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.S, rgb(20, 60, 140), 0.45), Mat.Glass, 0.1)
	local shallow = mix(c.S, WHITE, 0.4)
	col(c, -1.4, 0.3, 1.2, 0.15, 6, shallow, Mat.Sand)
	col(c, 2.2, 0.3, -1.4, 0.15, 4.6, shallow, Mat.Sand)
	col(c, -2.6, 0.3, -2.4, 0.15, 3, shallow, Mat.Sand)
	local ground = 0.45
	-- 가지 산호: 밑동에서 위·바깥으로 뻗는 가지 + 동그란 끝
	local function branching(x: number, z: number, h: number, color: Color3, count: number, turn: number)
		for k = 0, count - 1 do
			local angle = k / count * TAU + turn
			local lean = if k % 2 == 0 then 0.7 else 0.45
			local rise = if k % 2 == 0 then 0.8 else 1
			local tip = V(x + math.cos(angle) * h * lean, ground + h * rise, z + math.sin(angle) * h * lean)
			beam(c, V(x, ground - 0.1, z), tip, 0.22, color)
			ball(c, tip.X, tip.Y, tip.Z, 0.3, color)
		end
	end
	branching(-2.4, 2.2, 1.8, c.P, 4, 0.3)
	branching(2.9, 0, 1.5, orange, 3, 0.9)
	branching(-2.7, -2.5, 1.3, c.P, 3, 0.5)
	-- 뇌 산호(바닥에 얹힌 공): { x, z, 지름, 색 }
	for _, b in
		{
			{ -0.3, 2.9, 1.6, c.A },
			{ -1.2, 0.2, 1, purple },
			{ 1.4, -2.6, 1.3, purple },
			{ 3.4, -2.4, 1.1, mix(c.P, WHITE, 0.3) },
			{ -3.5, -0.4, 1.2, c.A },
		}
	do
		ball(c, b[1], b[3] / 2, b[2], b[3], b[4])
	end
	-- 탁자 산호(줄기 + 넓은 판)
	col(c, 0.5, ground, 1.2, 0.7, 0.25, tableColor)
	col(c, 0.5, ground + 0.7, 1.2, 0.15, 1.7, tableColor)
	col(c, 1.2, ground, -0.6, 0.45, 0.2, tableColor)
	col(c, 1.2, ground + 0.45, -0.6, 0.12, 1.2, tableColor)
	-- 부채 산호(바닥에 반쯤 묻힌 얇은 원판)
	cyl(c, CFrame.new(-3.6, 0.75, 3.5) * CFrame.Angles(0, 0.4, 0) * ALONG_Z, 0.08, 1.5, purple)
	cyl(c, CFrame.new(3.8, 0.6, 1.6) * CFrame.Angles(0, -1.2, 0) * ALONG_Z, 0.08, 1.2, orange)
	-- 관 산호
	for k, t in { { -3.9, 0.9, 0.9 }, { -3.5, 1.4, 0.6 }, { -4.1, 1.6, 0.7 } } do
		col(c, t[1], ground - 0.1, t[2], t[3] + 0.1, 0.35 - k * 0.03, orange)
	end
	-- 바다거북(앞쪽 깊은 물 위를 헤엄침, 정면을 봄)
	local turtle = CFrame.new(0.9, 1.2, -3.7) * CFrame.Angles(0, 0.35, 0)
	local shell = rgb(125, 105, 60)
	local skin = rgb(175, 170, 115)
	cyl(c, turtle * UPRIGHT, 0.25, 1.5, shell)
	cyl(c, turtle * CFrame.new(0, 0.2, 0) * UPRIGHT, 0.2, 1.05, mix(shell, BLACK, 0.15))
	local head = turtle * V(0, 0.05, -0.95)
	ball(c, head.X, head.Y, head.Z, 0.5, skin)
	for _, sx in { -1, 1 } do
		block(c, turtle * CFrame.new(sx * 0.95, 0, -0.35) * CFrame.Angles(0, sx * 0.5, 0), V(0.9, 0.08, 0.35), skin)
		block(c, turtle * CFrame.new(sx * 0.6, 0, 0.7) * CFrame.Angles(0, -sx * 0.5, 0), V(0.45, 0.08, 0.28), skin)
	end
end

-- 난마돌: 물길 사이 인공섬들 + 가운데 큰 섬의 현무암 기둥 성벽(통나무집처럼 가로세로 엇갈려 쌓음, 정면 입구)
--   + 안쪽 단과 무덤 + 작은 섬들의 낮은 벽 + 성벽을 덮은 초록 수풀
function BUILDERS.ruins(c)
	box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
	local rubble = mix(c.P, ROCK, 0.55)
	local d = 0.5 -- 현무암 기둥 굵기
	local n = 0
	-- 누운 현무암 기둥. along = "x" 또는 "z"(길이 축). 조금씩 비틀고 색을 달리해 돌기둥처럼
	local function log(x: number, y: number, z: number, length: number, along: string, diameter: number?)
		n += 1
		local cf = CFrame.new(x, y, z) * CFrame.Angles(0, (n % 3 - 1) * 0.025, 0)
		if along == "z" then
			cf *= CFrame.Angles(0, PI / 2, 0)
		end
		local color = if n % 2 == 0 then c.P else mix(c.P, ROCK, 0.18)
		cyl(c, cf, length + (n % 4 - 1.5) * 0.08, (diameter or d) * (0.92 + n % 3 * 0.06), color)
	end
	-- 가운데 큰 섬 + 성벽(앞뒤 기둥 층과 옆 기둥 층이 반 단씩 엇갈림)
	local cx, cz = 0.6, 0.8
	local hx, hz = 2.3, 2.1
	local base = 0.6
	box(c, cx, 0, cz, 6, base, 5.8, rubble)
	for k = 0, 3 do
		local y = base + d / 2 + k * d
		for _, sz in { -1, 1 } do
			if sz == -1 and k < 2 then
				for _, sx in { -1, 1 } do
					log(cx + sx * 1.675, y, cz - hz, 2.15, "x")
				end
			else
				log(cx, y, cz + sz * hz, 2 * hx + 0.7, "x")
			end
		end
		for _, sx in { -1, 1 } do
			log(cx + sx * hx, y + d / 2, cz, 2 * hz + 0.7, "z")
		end
	end
	box(c, cx, base, cz + 0.4, 2.6, 0.6, 2.2, mix(c.P, BLACK, 0.12))
	box(c, cx, base + 0.6, cz + 0.4, 1.1, 0.35, 1.1, c.P)
	plant(c, cx + 1.4, base, cz + 1.3, 2.3, 1.8, c.A)
	plant(c, cx - 1.3, base, cz + 1.2, 1.7, 1.3, mix(c.A, LEAF, 0.4))
	ball(c, cx - hx, base + 4 * d + 0.1, cz - hz, 0.9, c.A, Mat.Grass)
	ball(c, cx + 2.8, base + 0.1, cz - 2.3, 0.8, c.A, Mat.Grass)
	ball(c, cx - 2.8, base + 0.1, cz + 2.4, 0.9, c.A, Mat.Grass)
	-- 작은 섬들: { x, z, 가로, 세로 }
	local islets = {
		{ -3.8, -3.7, 1.9, 1.8 },
		{ -3.9, 1.6, 1.6, 2.6 },
		{ 2, -3.9, 2.6, 1.5 },
	}
	for k, islet in islets do
		local x, z, w, depth = islet[1], islet[2], islet[3], islet[4]
		box(c, x, 0, z, w, 0.45, depth, rubble)
		log(x, 0.45 + 0.2, z - depth / 2 + 0.25, w + 0.1, "x", 0.4)
		log(x - w / 2 + 0.25, 0.45 + 0.4, z, depth + 0.1, "z", 0.4)
		if k == 2 then
			plant(c, x + 0.3, 0.45, z + 0.5, 1.3, 1.2, c.A)
		else
			ball(c, x + 0.35, 0.75, z + 0.3, 0.9, c.A, Mat.Grass)
		end
	end
end

-- 지구본 땅 표(GlobeLand.luau, tools/model_preview/globe_land.py 가 진짜 세계 지도로 만듦).
-- 한 줄 = { 위도, 경도, 돔 반지름(도), 색 종류[, 높이] }. 없거나 깨지면 땅 없이 바다만
local GLOBE_LAND: { { number } } = (function()
	local module = script:FindFirstChild("GlobeLand")
	if module and module:IsA("ModuleScript") then
		local ok, result = pcall(require, module)
		if ok and type(result) == "table" then
			return result :: any
		end
	end
	return {}
end)()

local GLOBE_GOLD = rgb(235, 190, 80) -- 광장 받침대 윗판(PedestalTop)과 같은 금색
-- 땅 색 종류(GlobeLand 넷째 칸): 1 눈(그린란드·남극·북극 섬·히말라야), 2 초록(명소 보조 색), 3 짙은 초록(열대림), 4 사막
local GLOBE_SNOW = rgb(244, 248, 252)
local GLOBE_TONES = {
	[1] = GLOBE_SNOW,
	[3] = rgb(44, 138, 70),
	[4] = rgb(238, 202, 122),
}
local GLOBE_MATERIALS = { [1] = Mat.Snow, [4] = Mat.Sand } -- 나머지(초록·숲)는 Grass
-- 바탕 돔 높이 = clamp(SLOPE * 지구 반지름 * 돔 반지름(라디안), MIN, MAX) — globe_land.py 와 같은 값이어야 함.
-- 낮고 넓은 돔(가라앉힌 큰 공)이라 겹친 자리의 골이 얕음. MIN 0.04 = 광장 크기(2.6배)에서 0.1 스터드
local DOME_SLOPE, DOME_MIN, DOME_MAX = 0.1, 0.04, 0.05

-- 지구본: 금색 받침 + 23.5도 기운 파란 공 + 진짜 지도를 따른 대륙(겹친 돔 공 약 140개, 해안선이 둥글게 굽이짐)
-- + 극지방 눈 + 받침 기둥에 닿는 금색 자오선 고리(32조각) + 극 축받이. 파트 약 185개
-- (광장에서는 클라이언트가 모형 전체를 매 프레임 PivotTo 로 돌리므로 파트를 더 늘리지 말 것)
-- 땅·극 돔은 그림자를 만들지 않음(지구 공 위 얇은 돔이라 보이는 그림자가 거의 없는데, 돌 때마다 그림자 계산만 늘어남)
function BUILDERS.globe(c)
	local goldDark = mix(GLOBE_GOLD, BLACK, 0.18)
	col(c, 0, 0, 0, 0.5, 4.2, goldDark, Mat.Metal)
	col(c, 0, 0.5, 0, 0.4, 2.6, GLOBE_GOLD, Mat.Metal)
	col(c, 0, 0.9, 0, 1.6, 0.6, GLOBE_GOLD, Mat.Metal)

	local radius = 4
	local center = V(0, 7, 0)
	local tilt = CFrame.new(center) * CFrame.Angles(0, 0, math.rad(23.5)) -- 북극이 -X 쪽으로 기움
	local ocean = ball(c, 0, 7, 0, radius * 2, c.P, Mat.SmoothPlastic)
	ocean.Reflectance = 0.06

	-- 위도/경도(도) → 지구 중심에서 r 떨어진 점. 경도 20도(아프리카)가 정면(-Z), 동쪽이 정면에서 볼 때 오른쪽
	local function surface(lat: number, lon: number, r: number): Vector3
		local phi, lambda = math.rad(lat), math.rad(lon - 20)
		return tilt * V(-r * math.cos(phi) * math.sin(lambda), r * math.sin(phi), -r * math.cos(phi) * math.cos(lambda))
	end
	-- 돔: 지표에서 height 만큼 솟고, 지표와 만나는 둘레가 중심에서 cap 도인 공(가라앉힌 공의 튀어나온 부분).
	-- 공은 돌리지 않음(돌린 공은 경계 상자가 커져서 Models.create 의 크기 맞춤·굴림 연출 틀이 달라짐)
	local function dome(lat: number, lon: number, cap: number, height: number, color: Color3, material: Enum.Material)
		local top = radius + height
		local cosCap = math.cos(math.rad(cap))
		local r = (radius * radius + top * top - 2 * radius * top * cosCap) / (2 * (top - radius * cosCap))
		local p = surface(lat, lon, top - r)
		ball(c, p.X, p.Y, p.Z, r * 2, color, material).CastShadow = false
	end

	-- 대륙: 해안 쪽 작은 돔은 0.04, 큰(내륙) 돔은 0.05 (DOME_*).
	-- 다섯째 칸이 있는 줄은 색 덧칠 공(마른 띠·히말라야 눈·열대림 등): 표에 적힌 높이 그대로(바탕 돔보다 살짝 위)
	for _, row in GLOBE_LAND do
		local cap, tone = row[3], row[4]
		local height = row[5] or math.clamp(DOME_SLOPE * radius * math.rad(cap), DOME_MIN, DOME_MAX)
		dome(row[1], row[2], cap, height, GLOBE_TONES[tone] or c.S, GLOBE_MATERIALS[tone] or Mat.Grass)
	end
	-- 북극 바다 얼음(남극은 땅 표에 있음)
	dome(90, 0, 11, DOME_MAX, GLOBE_SNOW, Mat.Snow)

	-- 자오선 고리: 지구 중심을 도는 금색 띠(원 둘레 32조각). 맨 아래 조각이 받침 기둥 꼭대기에 얹힘
	local ring, band, width = 4.5, 0.2, 0.34
	local pieces = 32
	local step = TAU / pieces
	local length = 2 * (ring + band / 2) * math.tan(step / 2) -- 바깥 모서리까지 맞닿게
	for k = 0, pieces - 1 do
		local cf = CFrame.new(center) * CFrame.Angles(0, 0, -PI / 2 + k * step) * CFrame.new(ring, 0, 0)
		block(c, cf, V(band, length, width), GLOBE_GOLD, Mat.Metal)
	end
	ball(c, 0, center.Y - ring, 0, 0.6, GLOBE_GOLD, Mat.Metal) -- 기둥과 고리가 만나는 마디
	-- 축: 지구를 꿰뚫어 고리의 두 극 축받이까지
	cyl(c, tilt * UPRIGHT, 9.5, 0.22, GLOBE_GOLD, Mat.Metal)
	for _, side in { 1, -1 } do
		cyl(c, tilt * CFrame.new(0, side * ring, 0) * UPRIGHT, 0.4, 0.62, GLOBE_GOLD, Mat.Metal)
	end
end

-- 모르는 모형: 기단 + 오벨리스크
local function fallback(c: Ctx)
	box(c, 0, 0, 0, 5, 1, 5, c.S)
	box(c, 0, 1, 0, 1.4, 7, 1.4, c.P)
	box(c, 0, 8, 0, 1, 0.5, 1, c.A)
	box(c, 0, 8.5, 0, 0.5, 0.5, 0.5, c.A, Mat.Neon)
end

-- 명소별 전용 모형 ------------------------------------------------------------
-- 대륙별 모듈(Models/Asia.luau 등)이 `return function(K) return { [명소 Id] = function(c) ... end } end`
-- 형태로 전용 모형을 돌려줌. K = 아래 KIT(파트 헬퍼·색·기존 모양 builders). 전용 모형이 없는 명소는 Shape 모양을 씀.
local KIT = {
	V = V,
	rgb = rgb,
	Mat = Mat,
	PI = PI,
	TAU = TAU,
	UPRIGHT = UPRIGHT,
	ALONG_Z = ALONG_Z,
	CORNERS = CORNERS,
	GRASS = GRASS,
	LEAF = LEAF,
	WATER = WATER,
	DARK = DARK,
	TILE = TILE,
	ROCK = ROCK,
	WOOD = WOOD,
	SAND = SAND,
	CLOUD = CLOUD,
	BLACK = BLACK,
	WHITE = WHITE,
	mix = mix,
	add = add,
	shaped = shaped,
	block = block,
	box = box,
	ball = ball,
	cyl = cyl,
	col = col,
	wedge = wedge,
	beam = beam,
	facing = facing,
	archCorner = archCorner,
	roof = roof,
	gable = gable,
	plant = plant,
	stepped = stepped,
	clockFace = clockFace,
	figureTop = figureTop,
	shapes = BUILDERS, -- 기존 모양을 바탕으로 쓰고 싶을 때: K.shapes.dome(c)
}

local CONTINENT_MODULES = { "Asia", "Asia2", "Europe", "Europe2", "Americas", "Americas2", "Africa", "Oceania" }
local CUSTOM: { [string]: (Ctx) -> () } = {}
for _, name in CONTINENT_MODULES do
	local moduleScript = script:FindFirstChild(name)
	if moduleScript and moduleScript:IsA("ModuleScript") then
		local ok, result = pcall(function()
			return (require(moduleScript) :: any)(KIT)
		end)
		if ok and type(result) == "table" then
			for id, builder in result do
				CUSTOM[id] = builder
			end
		else
			warn("[Models] " .. name .. " 전용 모형을 불러오지 못했습니다: " .. tostring(result))
		end
	end
end

-- 공개 API ------------------------------------------------------------------

-- 코드로 만든 모형이 있는 Shape 이름 집합
Models.SHAPES = {} :: { [string]: boolean }
for name in BUILDERS do
	Models.SHAPES[name] = true
end

-- 전용 모형이 있는 명소 Id 집합
Models.CUSTOM = {} :: { [string]: boolean }
for id in CUSTOM do
	Models.CUSTOM[id] = true
end

function Models.build(landmark: Landmark): Model
	local model = Instance.new("Model")
	model.Name = landmark.Id

	local root = Instance.new("Part")
	root.Name = "Root"
	root.Size = V(DESIGN_WIDTH, 0.2, DESIGN_WIDTH)
	root.CFrame = CFrame.new(0, 0.1, 0)
	root.PivotOffset = CFrame.new(0, -0.1, 0) -- 피벗 = 바닥 중앙(y = 0)
	root.Transparency = 1
	root.Anchored = true
	root.CanCollide = false
	root.Parent = model
	model.PrimaryPart = root

	local ctx: Ctx = {
		model = model,
		id = landmark.Id,
		origin = CFrame.new(),
		P = landmark.Primary or rgb(200, 200, 200),
		S = landmark.Secondary or rgb(140, 140, 140),
		A = landmark.Accent or rgb(255, 240, 180),
		M = landmark.Material or Mat.SmoothPlastic,
		grand = landmark.Tier ~= nil and landmark.Tier.Rank >= 5,
	}
	local builder = CUSTOM[landmark.Id] or BUILDERS[landmark.Shape] or fallback
	local ok, err = pcall(builder, ctx)
	if not ok then
		-- 모형 코드에 문제가 있어도 게임은 계속되도록: 만들던 파트를 지우고 기본 모형으로
		warn(
			"[Models] "
				.. tostring(landmark.Id)
				.. " 모형 생성 실패, 기본 모형으로 대체: "
				.. tostring(err)
		)
		for _, child in model:GetChildren() do
			if child ~= root then
				child:Destroy()
			end
		end
		ctx.origin = CFrame.new()
		fallback(ctx)
	end
	return model
end

local function findOverride(landmark: Landmark): Model?
	local folder = game:GetService("ReplicatedStorage"):FindFirstChild(OVERRIDE_FOLDER)
	local source = folder and folder:FindFirstChild(landmark.Id)
	if source and source:IsA("Model") then
		return source
	end
	return nil
end

-- 교체 모형: 경계 상자의 바닥 중앙을 피벗으로. 경계 상자 크기를 돌려줌
local function pivotToBottom(model: Model): Vector3
	local cf, extents = model:GetBoundingBox()
	local bottom = cf * CFrame.new(0, -extents.Y / 2, 0)
	local primary = model.PrimaryPart
	if primary then
		-- PrimaryPart 가 있으면 WorldPivot 은 무시되므로 PrimaryPart 의 피벗을 옮김
		primary.PivotOffset = primary.CFrame:ToObjectSpace(bottom)
	else
		model.WorldPivot = bottom
	end
	return extents
end

function Models.create(landmark: Landmark, size: number, opts: { Anchored: boolean? }?): Model
	local model: Model? = nil
	local source = findOverride(landmark)
	if source then
		local clone = source:Clone()
		if clone and clone:FindFirstChildWhichIsA("BasePart", true) then
			model = clone
		end
	end

	local extents
	if model then
		extents = pivotToBottom(model)
		if math.max(extents.X, extents.Z) <= 1e-3 then
			model:Destroy()
			model = nil
		end
	end
	local built = model == nil
	if not model then
		model = Models.build(landmark)
		local _, buildExtents = (model :: Model):GetBoundingBox()
		extents = buildExtents
	end
	local result = model :: Model

	-- 가로·세로 중 큰 쪽이 size, 단 높이는 size * 2.2 까지
	local factor = size / math.max(extents.X, extents.Z)
	if extents.Y * factor > size * MAX_HEIGHT_RATIO then
		factor = size * MAX_HEIGHT_RATIO / extents.Y
	end
	if factor > 0 and factor < math.huge and math.abs(factor - 1) > 1e-4 then
		result:ScaleTo(result:GetScale() * factor)
	end

	-- 크기를 바꾼 뒤에도 피벗이 정확히 바닥 중앙이도록 다시 맞춤
	if built then
		local root = result.PrimaryPart :: BasePart
		root.PivotOffset = CFrame.new(0, -root.Size.Y / 2, 0)
	else
		pivotToBottom(result)
	end

	local loose = opts ~= nil and opts.Anchored == false
	for _, descendant in result:GetDescendants() do
		if descendant:IsA("BasePart") then
			if loose then
				descendant.Anchored = false
				descendant.Massless = true
				descendant.CanCollide = false
				descendant.CanQuery = false
				descendant.CanTouch = false
			else
				descendant.Anchored = true
				descendant.CanCollide = false
			end
		end
	end

	result.Name = landmark.Id
	return result
end

return Models
