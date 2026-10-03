-- 서남(황구·한해). World.luau 가 build(root, rng) 를 부른다. 모두 "서남" 폴더 하나에 넣는다.
--
--   황구     누런 흙 언덕, 지층 띠를 두른 탁상 바위 다섯, 바위 굴집 마을, 황구 토단(오색토 제단과 흙 무사)
--   단애곡   붉은 지층 벼랑, 서쪽 벽의 잔도, 돌기둥(후두), 마른 나무
--   관성대   지층 벼랑, 오르막 난간과 축대, 꼭대기 천문 옛터 (혼천의, 첨성대, 성도 비석, 부러진 열주, 규표)
--   한해     바람구멍 바위(길을 가로지른다), 바람등과 버섯바위, 큰 요수 뼈, 모래에 묻힌 대상 수레, 묻힌 기둥, 경계 비석,
--            마른 나무와 사막 덤불, 돌무더기 길표
--   침사국 옛터  모래에 잠긴 성벽과 홍예문, 쓰러진 거상 머리, 열주, 부서진 계단, 모래 찬 뜰
--   녹주     종려, 갈대, 돌 우물, 대상 천막과 깔개, 낙타
--   소금벌   소금 껍질 무늬, 소금 결정, 거울 못, 소금 더미와 고무래, 소금막
--
-- 지층(사암 띠): 낮은 곳에서 높은 쪽으로 땅을 한 줄로 재어, 띠 높이(y0~y1)가 땅과 만나는 자리에 앞면을 세운다.
-- 띠 높이는 바위 하나(골짜기 하나)에서 같은 값을 써서 둘레를 돌며 띠가 이어진다. 앞면은 땅보다 조금 나오고 뒤는 땅에 묻힌다.
-- 자리는 비워 둔다 (전송진 9, 과업·영맥 7, 칠성단 둘레 38 은 0.5 넘는 것 없이): CLEAR 를 본다.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")
local Land = require(Shared.Land)
local Places = require(Shared.Places)
local Build = require(script.Parent.WorldBuild)
local Kit = require(script.Parent.WorldKit)
local Sites = require(script.Parent.WorldSites)

local Region = {}

local P = Build.P
local V3 = Vector3.new
local face = Build.face
local block, wedge, beam, cyl, ball = Build.block, Build.wedge, Build.beam, Build.cyl, Build.ball
local deco = Build.deco
local M = Enum.Material
local rad, cos, sin, sqrt, floor, min, max, abs =
	math.rad, math.cos, math.sin, math.sqrt, math.floor, math.min, math.max, math.abs
local TAU = math.pi * 2

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- 빛깔 ---------------------------------------------------------------------------------
local C = {
	sand = rgb(214, 186, 132), -- 지형 Sand 와 같은 빛 (모래 둔덕을 부품으로 쌓을 때)
	sandDeep = rgb(200, 168, 116),
	loess = rgb(198, 156, 94), -- 지형 Limestone (황구 누런 흙)
	earth = rgb(176, 132, 84), -- 다진 흙 (판축)
	earthDark = rgb(140, 100, 64),
	bone = rgb(226, 218, 196),
	boneDark = rgb(184, 172, 148),
	deadwood = rgb(124, 108, 92),
	deadwoodPale = rgb(166, 152, 132),
	bronze = rgb(150, 112, 62),
	bronzeDark = rgb(104, 78, 46),
	verdigris = rgb(96, 138, 116),
	salt = rgb(242, 240, 234),
	saltShade = rgb(214, 212, 204),
	ochreCloth = rgb(196, 146, 62), -- 황구 깃발
	madder = rgb(150, 62, 48), -- 꼭두서니 물 (천막)
	indigo = rgb(62, 74, 108),
	felt = rgb(222, 208, 178),
	sage = rgb(128, 134, 96), -- 사막 덤불
	sageDark = rgb(102, 108, 78),
	straw = rgb(184, 164, 108),
	dustLeaf = rgb(118, 128, 76), -- 황구 마른 잎
	ash = rgb(92, 84, 78),
	pepper = rgb(170, 44, 34),
}
-- 지층 띠 (아래에서 위로 되풀이한다). 사암의 붉은 띠, 황토 띠, 옅은 띠
local BANDS = {
	rgb(194, 136, 86),
	rgb(212, 170, 118),
	rgb(172, 100, 66),
	rgb(200, 150, 96),
	rgb(222, 188, 138),
	rgb(156, 86, 60),
	rgb(190, 128, 80),
}
local CAPROCK = rgb(222, 196, 152)

local function jitter(color: Color3, rng, amount: number): Color3
	local k = 1 + rng(-amount, amount)
	return Color3.new(math.clamp(color.R * k, 0, 1), math.clamp(color.G * k, 0, 1), math.clamp(color.B * k, 0, 1))
end

local function model(parent: Instance, name: string): Model
	local m = Instance.new("Model")
	m.Name = name
	m.Parent = parent
	return m
end

local function folder(parent: Instance, name: string): Folder
	local f = Instance.new("Folder")
	f.Name = name
	f.Parent = parent
	return f
end

-- 땅 ----------------------------------------------------------------------------------
local function H(x: number, z: number): number
	return Land.surface(x, z)
end
local function at(x: number, z: number, lift: number?): Vector3
	return V3(x, H(x, z) + (lift or 0), z)
end
-- 둘레(반지름 r) 여덟 곳과 가운데의 가장 낮은 땅 (비탈에서 밑동을 묻을 때)
local function lowAt(x: number, z: number, r: number): number
	local low = H(x, z)
	for i = 0, 7 do
		local a = i * TAU / 8
		low = min(low, H(x + cos(a) * r, z + sin(a) * r))
	end
	return low
end
local function highAt(x: number, z: number, r: number): number
	local high = H(x, z)
	for i = 0, 7 do
		local a = i * TAU / 8
		high = max(high, H(x + cos(a) * r, z + sin(a) * r))
	end
	return high
end
-- 비탈 정도 (둘레 높낮이 차)
local function relief(x: number, z: number, r: number): number
	return highAt(x, z, r) - lowAt(x, z, r)
end

-- 비워 둘 자리 ---------------------------------------------------------------------------
local CLEAR: { { number } } = {} -- { x, z, 반지름 }
local function addClear(x: number, z: number, r: number)
	table.insert(CLEAR, { x, z, r })
end
local MESA = Land.MESA
local EARTH = Land.EARTH
local RUINS = Land.RUINS
local OASIS = Land.OASIS
local SALT = Land.SALT
local function inArea(x: number, z: number): boolean
	return x < -60 and z > 330
end
for _, s in Sites.WAYPOINTS do
	if inArea(s.x, s.z) then
		addClear(s.x, s.z, 10)
	end
end
for _, s in Sites.VEINS do
	if inArea(s.x, s.z) then
		addClear(s.x, s.z, 8)
	end
end
for _, s in Sites.TASK do
	if inArea(s.x, s.z) and not string.match(s.id, "^tri_") and s.id ~= "altar" then
		addClear(s.x, s.z, 8)
	end
end
addClear(MESA.x, MESA.z, 39) -- 칠성단과 팔괘 기둥 (반지름 31)
for _, spot in Sites.MANUALS do
	if inArea(spot[1], spot[2]) then
		addClear(spot[1], spot[2], 4)
	end
end
local function clearOf(x: number, z: number, pad: number): boolean
	for _, c in CLEAR do
		local dx, dz = x - c[1], z - c[2]
		local r = c[3] + pad
		if dx * dx + dz * dz < r * r then
			return false
		end
	end
	return true
end

-- 길 (Land.ROADS) 곁인가
local ROADS = {}
for _, road in Land.ROADS do
	table.insert(ROADS, Land.poly(road))
end
local function roadDist(x: number, z: number): number
	local best = math.huge
	for _, road in ROADS do
		best = min(best, (Land.polyDist(x, z, road, 40)))
	end
	return best
end

-- 이 땅(서남)의 자리인가: Places 의 땅 이름으로 가른다 (이웃 땅을 넘지 않게)
local function regionId(x: number, z: number): string
	return Places.regionAt(x, z).id
end

-- 흩뿌리기: 네모 [x0,x1]×[z0,z1] 에서 accept 를 통과한 자리 count 곳 (taken 의 자리와 spacing 넘게)
local function scatter(
	rng,
	count: number,
	box: { number },
	spacing: number,
	accept: (number, number) -> boolean,
	taken: { { number } }?
): { { number } }
	local out = taken or {}
	local made = {}
	local tries = 0
	while #made < count and tries < count * 60 do
		tries += 1
		local x, z = rng(box[1], box[2]), rng(box[3], box[4])
		local ok = true
		for _, p in out do
			local dx, dz = p[1] - x, p[2] - z
			local s = max(spacing, p[3] or 0)
			if dx * dx + dz * dz < s * s then
				ok = false
				break
			end
		end
		if ok and accept(x, z) then
			table.insert(out, { x, z })
			table.insert(made, { x, z })
		end
	end
	return made
end

-- 작은 것들 ------------------------------------------------------------------------------

-- 바위 하나: 세 축으로 돌린 덩이 + 깎인 모서리 (밑 30% 를 묻는다)
local function boulder(
	parent: Instance,
	x: number,
	z: number,
	size: number,
	rng,
	color: Color3,
	material: Enum.Material?
)
	local m = model(parent, "바위")
	local y = lowAt(x, z, size * 0.4)
	local s = V3(size, size * rng(0.55, 0.85), size * rng(0.7, 1.05))
	local cf = CFrame.new(x, y + s.Y * 0.28, z) * CFrame.Angles(rng(-0.3, 0.3), rng(0, TAU), rng(-0.3, 0.3))
	block(m, "Dol", s, cf, jitter(color, rng, 0.07), material or M.Sandstone)
	if size > 2.5 then
		local cut = CFrame.new(s.X * 0.18, s.Y * 0.3, 0) * CFrame.Angles(rng(-0.5, 0.5), rng(0, 1), rng(0.3, 0.6))
		block(m, "Dol", s * V3(0.7, 0.6, 0.7), cf * cut, jitter(color, rng, 0.09), material or M.Sandstone)
	end
	return m
end

-- 마른 풀 포기: 가는 잎 셋을 벌려 세운다
local function tuft(parent: Instance, x: number, z: number, rng, color: Color3?, y: number?)
	local m = model(parent, "마른풀")
	local base = V3(x, (y or H(x, z)) - 0.2, z)
	local c = color or C.straw
	for k = 1, 2 do
		local a = k * TAU / 2 + rng(-0.6, 0.6)
		local h = rng(1.2, 2.2)
		local tip = base + V3(cos(a) * h * 0.45, h, sin(a) * h * 0.45)
		deco(beam(m, "Pul", base, tip, 0.5, 0.12, jitter(c, rng, 0.1), M.Grass)).CastShadow = false
	end
	return m
end

-- 마른 덤불 (사막·황구): 납작한 덩이 둘셋, 잿빛 풀빛
local function dryShrub(parent: Instance, x: number, z: number, rng, size: number?, palette: { Color3 }?, y: number?)
	local s = size or rng(2, 3.6)
	return Build.shrub(parent, V3(x, (y or H(x, z)) - 0.25, z), rng, {
		size = s,
		blobs = 2 + floor(rng(0, 1.99)),
		leaves = palette or { C.sageDark, C.sage, C.dustLeaf },
	})
end

-- 마른 나무: 비틀린 줄기와 잎 없는 가지 (가지 끝에 잔가지 하나)
local function deadTree(parent: Instance, x: number, z: number, rng, opts)
	opts = opts or {}
	local m = model(parent, "마른나무")
	local base = V3(x, (opts.y or lowAt(x, z, 1)) - 0.5, z)
	local height = opts.height or rng(7, 12)
	local color = opts.color or (if rng(0, 1) > 0.5 then C.deadwood else C.deadwoodPale)
	local w = height * 0.09
	local dir = V3(rng(-0.25, 0.25), 1, rng(-0.25, 0.25)).Unit
	local p = base
	local joints = {}
	for i = 1, 3 do
		local q = p + dir * (height / 3)
		local wi = w * (1 - 0.22 * (i - 1))
		beam(m, "Julgi", p, q + dir * w * 0.3, wi, wi, color, M.Wood)
		table.insert(joints, q)
		p = q
		dir = (dir + V3(rng(-0.35, 0.35), 0, rng(-0.35, 0.35))).Unit
	end
	local a0 = rng(0, TAU)
	local nb = opts.branches or 4
	for i = 1, nb do
		local from = joints[1]:Lerp(joints[3], rng(0.25, 1))
		local a = a0 + i * TAU / nb + rng(-0.5, 0.5)
		local len = height * rng(0.28, 0.45)
		local to = from + V3(cos(a) * len, len * rng(0.35, 0.9), sin(a) * len)
		beam(m, "Gaji", from, to, w * 0.42, w * 0.42, color, M.Wood)
		if i % 2 == 1 then
			local b = a + rng(-1, 1)
			local tip = to + V3(cos(b) * len * 0.45, len * rng(0.2, 0.5), sin(b) * len * 0.45)
			deco(beam(m, "Jan", to, tip, w * 0.22, w * 0.22, color, M.Wood)).CastShadow = false
		end
	end
	return m
end

-- 돌무더기 길표: 납작한 돌 서넛을 쌓는다
local function cairn(parent: Instance, x: number, z: number, rng, color: Color3?)
	local m = model(parent, "돌무더기")
	local y = lowAt(x, z, 1.2) - 0.3
	local c = color or rgb(150, 120, 92)
	local s = rng(2.2, 2.8)
	for _ = 1, 4 do
		local h = s * 0.42
		local cf = CFrame.new(x + rng(-0.15, 0.15), y + h / 2, z + rng(-0.15, 0.15))
			* CFrame.Angles(rng(-0.12, 0.12), rng(0, TAU), rng(-0.12, 0.12))
		block(m, "Dol", V3(s, h, s * rng(0.8, 1)), cf, jitter(c, rng, 0.1), M.Sandstone)
		y += h * 0.92
		s *= 0.74
	end
	return m
end

-- 다진 흙담 (기와 갓): a 에서 b 까지, 땅을 따라 밑을 묻는다
local function earthWall(parent: Instance, a: Vector3, b: Vector3, height: number, rng)
	local m = model(parent, "흙담")
	local mid = (a + b) / 2
	local len = (b - a).Magnitude
	local low = math.huge
	for i = 0, 4 do
		local p = a:Lerp(b, i / 4)
		low = min(low, H(p.X, p.Z))
	end
	local top = max(a.Y, b.Y) + height
	local look = face(V3(mid.X, 0, mid.Z), V3(b.X, 0, b.Z))
	local bodyH = top - low + 1
	block(m, "Dam", V3(1.3, bodyH, len), look + V3(0, low - 1 + bodyH / 2, 0), jitter(C.earth, rng, 0.04), M.Sandstone)
	-- 판축 자국 (가는 띠)
	block(m, "Ttiban", V3(1.36, 0.25, len + 0.02), look + V3(0, top - 1.4, 0), C.earthDark, M.Sandstone)
	for _, s in { 1, -1 } do
		local cap = look * CFrame.new(s * 0.55, top + 0.3, 0) * CFrame.Angles(0, s * rad(90), 0)
		wedge(m, "Giwa", V3(len + 0.4, 0.6, 1.1), cap + V3(0, 0, 0), P.giwa, M.ClayRoofTiles)
	end
	block(m, "Maru", V3(0.45, 0.32, len + 0.5), look + V3(0, top + 0.72, 0), P.giwaDark, M.Slate)
	return m
end

-- 지층 ---------------------------------------------------------------------------------

-- (x, z) 에서 (dx, dz) 쪽으로 0..len 의 땅 높이 (STEP 간격)
local STEP = 0.75
local function profile(x: number, z: number, dx: number, dz: number, len: number): { number }
	local hs = {}
	for i = 0, floor(len / STEP) do
		local t = i * STEP
		hs[i + 1] = H(x + dx * t, z + dz * t)
	end
	return hs
end
-- 처음으로 y 에 닿는 거리 (선형 보간). 끝까지 못 닿으면 nil
local function reach(hs: { number }, y: number): number?
	for i, h in hs do
		if h >= y then
			if i == 1 then
				return 0
			end
			local a = hs[i - 1]
			return (i - 2 + (y - a) / (h - a)) * STEP
		end
	end
	return nil
end
-- 띠 하나: 기준점 (x, z) 에서 (dx, dz) 쪽 거리 tFront~tBack, 높이 y0~y1, 옆 너비 width
local function slabAlong(
	parent: Instance,
	x: number,
	z: number,
	dx: number,
	dz: number,
	tFront: number,
	tBack: number,
	y0: number,
	y1: number,
	width: number,
	color: Color3,
	material: Enum.Material?
): BasePart
	local tc = (tFront + tBack) / 2
	local c = V3(x + dx * tc, (y0 + y1) / 2, z + dz * tc)
	return block(
		parent,
		"Jicheung",
		V3(width, y1 - y0, tBack - tFront),
		face(c, c + V3(dx, 0, dz)),
		color,
		material or M.Sandstone
	)
end

-- 띠 높이 목록 { {y0, y1, color} }: yLow 에서 yTop 까지, 두께 thinMin..thinMax
local function bandStack(rng, yLow: number, yTop: number, thinMin: number, thinMax: number): { any }
	local bands = {}
	local y = yLow
	local k = floor(rng(0, #BANDS))
	while y < yTop - 0.01 do
		local th = rng(thinMin, thinMax)
		if yTop - (y + th) < thinMin * 0.6 then
			th = yTop - y
		end
		table.insert(bands, { y, y + th, BANDS[k % #BANDS + 1] })
		y += th
		k += 1
	end
	return bands
end

-- 한 줄(기준점에서 높은 쪽으로)에 띠들을 세운다. 땅이 이미 그 띠 위까지 올라와 있으면 건너뛴다
-- band.cap: 꼭대기 갓바위 (뒤끝은 band.surface 높이에 닿는 곳). opts.minY: 이보다 낮은 띠는 건너뛴다
local function strataRay(
	parent: Instance,
	x: number,
	z: number,
	dx: number,
	dz: number,
	len: number,
	bands,
	width: (number) -> number,
	rng,
	opts
): number
	opts = opts or {}
	local hs = profile(x, z, dx, dz, len)
	local g0 = hs[1]
	local made = 0
	local tb = nil -- 맨 아래 띠의 앞 (opts.steep < 1 이면 위 띠들을 이 쪽으로 당겨 벼랑을 세운다)
	for i, b in bands do
		local y0, y1 = b[1], min(b[2], opts.maxY or math.huge)
		if y1 > g0 + 0.8 and y0 >= (opts.minY or -math.huge) and y0 < y1 - 0.5 then
			local t0 = reach(hs, max(y0, g0) + 0.3) or 0
			local t1 = reach(hs, if b.cap and not opts.maxY then b.surface - 0.15 else y1)
			if t1 then
				tb = tb or t0
				local tt = tb + (t0 - tb) * (opts.steep or 1)
				local vary = opts.vary or 0
				local front = tt
					- (if b.cap then 1.9 else rng(0.9, 1.4) + rng(-vary, vary))
					- (opts.proud or 0)
					- (opts.jut or 0)
				local back = t1 + (opts.tuck or 1.6)
				local bottom = if i == 1 or y0 < g0 then min(y0, g0 - 1.2) else y0 - 0.5
				local col = jitter(b[3], rng, 0.05)
				slabAlong(parent, x, z, dx, dz, front, back, bottom, y1, width(front), col, opts.material)
				made += 1
			end
		end
	end
	return made
end

-- 둥근 바위(탁상 바위, 관성대 벼랑)에 띠를 두른다. arc = {a0, a1} (도) 이면 그 둘레만
local function strataRing(
	parent: Instance,
	cx: number,
	cz: number,
	rIn: number,
	rOut: number,
	bands,
	n: number,
	rng,
	arc: { number }?,
	opts
)
	local a0 = if arc then rad(arc[1]) else 0
	local a1 = if arc then rad(arc[2]) else TAU
	local span = a1 - a0
	local count = if arc then max(1, floor(n * span / TAU + 0.5)) else n
	local da = span / count
	local half = math.tan(da / 2)
	for k = 0, count - 1 do
		local a = a0 + (k + 0.5) * da
		local ox, oz = cos(a), sin(a)
		local bx, bz = cx + ox * rOut, cz + oz * rOut
		local o = if type(opts) == "function" then opts(math.deg(a) % 360) else opts
		-- 비바람에 패인 골과 튀어나온 등: 면마다 조금씩 들고 난다
		o = table.clone(o or {})
		o.jut = rng(-0.5, 0.9) * (o.jutK or 1)
		strataRay(parent, bx, bz, -ox, -oz, rOut - rIn + 2, bands, function(front)
			return 2 * (rOut - front) * half + 1.4
		end, rng, o)
	end
end

-- 황구 ---------------------------------------------------------------------------------

-- 탁상 바위: 지층 띠 (땅이 깎인 비탈), 꼭대기 갓바위 테, 꼭대기 덤불과 굽은 소나무, 기슭 굴러떨어진 바위
-- hollow = { a0, a1, minY }: 그 둘레(도)에서는 minY 보다 낮은 띠를 빼고 둔다 (굴집 벽이 들어선다)
local function butte(parent: Instance, b, rng, hollow: { number }?)
	local cx, cz, r, top = b[1], b[2], b[3], b[4]
	local m = model(parent, "탁상바위")
	local toe = r + 16
	local g = math.huge
	for i = 0, 11 do
		local a = i * TAU / 12
		g = min(g, H(cx + cos(a) * toe, cz + sin(a) * toe))
	end
	local yLow = g + 0.1 * (top - g)
	local bands = bandStack(rng, yLow, top - 3.2, 5, 9)
	table.insert(bands, { top - 3.2, top + 0.9, CAPROCK, cap = true, surface = top })
	local n = math.clamp(floor(TAU * (r + 8) / 13 + 0.5), 9, 16)
	local function inHollow(deg: number): boolean
		return hollow ~= nil and ((deg - hollow[1]) % 360) < ((hollow[2] - hollow[1]) % 360)
	end
	strataRing(m, cx, cz, r - 2, toe, bands, n, rng, nil, function(deg)
		return if inHollow(deg) then { minY = hollow and hollow[3] } else nil
	end)
	-- 꼭대기: 덤불, 마른 풀, 굽은 소나무 하나
	local topF = model(parent, "탁상바위 꼭대기")
	for _ = 1, 1 + floor(r / 10) do
		local a, d = rng(0, TAU), rng(0, r - 4)
		dryShrub(topF, cx + cos(a) * d, cz + sin(a) * d, rng, rng(2, 3.2), { C.sageDark, C.dustLeaf, C.sage })
	end
	do
		local a, d = rng(0, TAU), rng(0, r - 3)
		tuft(topF, cx + cos(a) * d, cz + sin(a) * d, rng)
	end
	if r >= 18 then
		local a, d = rng(0, TAU), rng(r * 0.3, r - 5)
		Build.pine(topF, at(cx + cos(a) * d, cz + sin(a) * d), rng, { height = rng(8, 11), tiers = 4 })
	end
	-- 기슭: 무너져 내린 바위
	local foot = model(parent, "탁상바위 기슭")
	for _ = 1, 3 + floor(r / 6) do
		local a = rng(0, TAU)
		local d = toe + rng(-3, 5)
		local x, z = cx + cos(a) * d, cz + sin(a) * d
		if clearOf(x, z, 3) and roadDist(x, z) > 6 and not inHollow(math.deg(a) % 360) then
			boulder(foot, x, z, rng(1.6, 4.2), rng, BANDS[floor(rng(1, #BANDS + 0.99))])
		end
	end
	return m
end

-- 땅이 올려 주지 않은 탁상 바위 (황구 무늬 밖이라 지형이 솟지 않은 자리): 띠 덩이를 쌓아 부품으로 세운다
local function standingButte(parent: Instance, b, rng)
	local cx, cz, r, top = b[1], b[2], b[3], b[4]
	local m = model(parent, "탁상바위")
	local g = lowAt(cx, cz, r + 4)
	local y = g - 2
	local k = floor(rng(0, #BANDS))
	local radius = r + 3.2
	local capTop = top
	while y < top - 0.01 do
		local th = rng(3.2, 6)
		if top - (y + th) < 2.4 then
			th = top - y
		end
		local isCap = y + th >= top - 0.01
		local col = if isCap then CAPROCK else BANDS[k % #BANDS + 1]
		-- 띠 하나 = 30도씩 돌린 네모 셋 (열두모 바위처럼)
		for j = 0, 2 do
			local rr = radius * (if isCap then 1.05 else rng(0.97, 1.03))
			local cf = CFrame.new(cx + rng(-0.3, 0.3), y + th / 2, cz + rng(-0.3, 0.3))
				* CFrame.Angles(0, j * math.pi / 6 + rng(-0.05, 0.05), 0)
			block(m, "Jicheung", V3(rr * 1.86, th, rr * 1.86), cf, jitter(col, rng, 0.05), M.Sandstone)
		end
		y += th
		k += 1
		radius -= rng(0.15, 0.5) -- 위로 갈수록 조금 좁아진다
	end
	-- 기슭에 쌓인 부스러기 (지형과 바위 사이를 메운다)
	local foot = model(parent, "탁상바위 기슭")
	for j = 0, 9 do
		local a = j * TAU / 10 + rng(-0.15, 0.15)
		local d = r + 4.2
		local x, z = cx + cos(a) * d, cz + sin(a) * d
		local gy = lowAt(x, z, 2)
		local s = V3(rng(6, 9), rng(4, 6.5), rng(5, 7))
		local cf = face(V3(x, gy + s.Y * 0.12, z), V3(cx, gy, cz)) * CFrame.Angles(rad(rng(-26, -16)), 0, 0)
		block(foot, "Busureogi", s, cf, jitter(BANDS[(k + j) % #BANDS + 1], rng, 0.06), M.Sandstone)
	end
	local topF = model(parent, "탁상바위 꼭대기")
	for _ = 1, 2 do
		local a, d = rng(0, TAU), rng(0, r - 3)
		dryShrub(topF, cx + cos(a) * d, cz + sin(a) * d, rng, rng(2, 3), nil, capTop)
	end
	tuft(topF, cx + 2, cz - 3, rng, nil, capTop)
	return m
end

-- 흙 무사 (토단을 지키는 흙으로 빚은 장수): look 의 앞(-Z)을 본다. s 는 크기 배율
local function guardian(parent: Instance, look: CFrame, s: number, rng)
	local m = model(parent, "흙무사")
	local clay = jitter(rgb(176, 122, 80), rng, 0.04)
	local clayDark = jitter(rgb(140, 92, 60), rng, 0.04)
	local paint = rgb(150, 70, 52)
	local function put(name, size: Vector3, x, y, z, color, rot: CFrame?)
		return block(
			m,
			name,
			size * s,
			look * CFrame.new(x * s, y * s, z * s) * (rot or CFrame.new()),
			color,
			M.Sandstone
		)
	end
	put("Badachim", V3(3.4, 1.2, 3.2), 0, 0.4, 0, rgb(150, 140, 124))
	for _, x in { -0.62, 0.62 } do
		put("Dari", V3(0.95, 2.6, 1.1), x, 2.3, 0.1, clayDark)
	end
	-- 갑옷 자락 (아래로 퍼진다), 몸통, 어깨 갑옷
	put("Jarak", V3(2.6, 1.9, 1.7), 0, 3.6, 0.05, clay)
	put("Mom", V3(2.3, 2.6, 1.45), 0, 5.6, 0.05, clay)
	put("Ttibal", V3(2.42, 0.38, 1.55), 0, 4.55, 0.05, paint)
	for _, x in { -1.45, 1.45 } do
		put("Eokkae", V3(1.0, 0.8, 1.6), x, 6.6, 0.05, clayDark, CFrame.Angles(0, 0, rad(x > 0 and -12 or 12)))
		put("Pal", V3(0.7, 2.4, 0.8), x * 0.92, 5.4, -0.25, clay, CFrame.Angles(rad(18), 0, 0))
	end
	-- 두 손을 모아 짚은 큰 칼 (몸 앞, 끝이 바닥에)
	put("Son", V3(1.3, 0.7, 0.8), 0, 4.25, -0.95, clay)
	put("Kal", V3(0.32, 4.2, 0.6), 0, 2.15, -1.05, rgb(118, 108, 98))
	-- 머리와 투구
	put("Meori", V3(1.15, 1.3, 1.2), 0, 7.95, 0.0, clay)
	put("Tugu", V3(1.45, 0.75, 1.45), 0, 8.75, 0.05, clayDark)
	put("Jang", V3(0.3, 0.9, 0.3), 0, 9.5, 0.05, paint)
	return m
end

-- 세발 청동 솥 (정): 몸, 테, 귀 둘, 발 셋
local function ding(parent: Instance, base: Vector3, rng)
	local m = model(parent, "청동정")
	local body = cyl(m, "Mom", base + V3(0, 1.6, 0), base + V3(0, 3.2, 0), 3.4, C.bronze, M.Metal)
	body.Reflectance = 0.05
	cyl(m, "Te", base + V3(0, 3.2, 0), base + V3(0, 3.45, 0), 3.7, C.bronzeDark, M.Metal)
	cyl(m, "Bae", base + V3(0, 1.25, 0), base + V3(0, 1.6, 0), 2.8, C.verdigris, M.Metal)
	for k = 0, 2 do
		local a = k * TAU / 3 + 0.4
		local o = V3(cos(a) * 1.1, 0, sin(a) * 1.1)
		cyl(m, "Bal", base + o * 1.15, base + o + V3(0, 1.5, 0), 0.5, C.bronzeDark, M.Metal)
	end
	for _, s in { -1, 1 } do
		block(m, "Gwi", V3(0.3, 1, 0.9), CFrame.new(base + V3(s * 1.45, 3.85, 0)), C.bronzeDark, M.Metal)
	end
	-- 향 연기
	local smoke = deco(block(m, "Yeon", V3(1, 0.2, 1), CFrame.new(base + V3(0, 3.4, 0)), C.ash))
	smoke.Transparency = 1
	local e = Instance.new("ParticleEmitter")
	e.Name = "Hyang"
	e.Texture = "rbxasset://textures/particles/smoke_main.dds"
	e.Rate = 2.5
	e.Lifetime = NumberRange.new(4, 6)
	e.Speed = NumberRange.new(1, 2)
	e.SpreadAngle = Vector2.new(8, 8)
	e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 3.5) })
	e.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.55), NumberSequenceKeypoint.new(1, 1) })
	e.Color = ColorSequence.new(rgb(220, 214, 204))
	e.Parent = smoke
	return m
end

-- 거북 비석 (귀부와 이수): 거북 등 위에 세운 비. 글은 세로로 새긴다 (Plaque). toward 쪽이 앞
local function monument(parent: Instance, x: number, z: number, text: string, toward: Vector3, rng, color: Color3?)
	local m = model(parent, "비석")
	local g = lowAt(x, z, 2.6)
	local look = face(V3(x, g, z), V3(toward.X, g, toward.Z))
	local stone = color or rgb(132, 126, 116)
	local dark = rgb(104, 98, 90)
	local function put(name, size: Vector3, ox, oy, oz, col, rot: CFrame?)
		return block(m, name, size, look * CFrame.new(ox, oy, oz) * (rot or CFrame.new()), col, M.Granite)
	end
	-- 거북: 몸, 등딱지(엇돌린 두 판), 머리, 발 넷
	put("Mom", V3(4.4, 1.5, 5.6), 0, 0.55, 0.2, dark)
	put("Deung", V3(3.9, 0.9, 4.9), 0, 1.55, 0.2, stone)
	put("Deung", V3(3.3, 0.9, 3.3), 0, 1.6, 0.2, stone, CFrame.Angles(0, rad(45), 0))
	put("Meori", V3(1.3, 1.1, 1.7), 0, 1.0, -3.3, dark, CFrame.Angles(rad(-12), 0, 0))
	for _, c in { { -1, -1 }, { 1, -1 }, { -1, 1 }, { 1, 1 } } do
		put("Bal", V3(1.1, 0.7, 1.3), c[1] * 2.3, 0.15, c[2] * 2.1 + 0.2, dark)
	end
	-- 비몸과 이수 (반달 머리)
	local n = utf8.len(text) or 2
	local hgt = 1.7 * n + 1.4
	local slab = put("Bimom", V3(2.6, hgt, 0.75), 0, 2.0 + hgt / 2, 0.2, stone)
	Kit.engrave(slab, text, "Front,Back", true, "ink")
	put("Isu", V3(3.2, 1.0, 1.05), 0, 2.0 + hgt + 0.5, 0.2, dark)
	local capC = look * CFrame.new(0, 2.0 + hgt + 1.0, 0.2)
	cyl(
		m,
		"Isu",
		(capC * CFrame.new(0, 0, -0.52)).Position,
		(capC * CFrame.new(0, 0, 0.52)).Position,
		3.2,
		dark,
		M.Granite
	)
	return m
end

-- 황구 토단: 오색토 마당(가운데는 비워 둔다: 오행처 단이 들어선다), 다진 흙 세 층 축대, 앞뒤 돌계단과 소맷돌,
-- 계단 머리의 흙 무사 넷, 황토 깃발, 청동 정, 비석. 길(북동→남서)을 따라 돌려 앉힌다
local function earthAltar(parent: Instance, rng)
	local f = model(parent, "황구 토단")
	local cx, cz = EARTH.x, EARTH.z
	local court = H(cx, cz) -- 16
	local fwd = V3(0.664, 0, -0.747) -- 북동 (송계에서 오는 길)
	local L = face(V3(cx, 0, cz), V3(cx, 0, cz) + fwd) -- 앞(-Z)이 북동
	local function W(x: number, y: number, z: number): Vector3
		return L:PointToWorldSpace(V3(x, y, z))
	end
	local function groundUnder(x0: number, x1: number, z0: number, z1: number): (number, number)
		local low, high = math.huge, -math.huge
		for i = 0, 4 do
			for j = 0, 2 do
				local p = W(x0 + (x1 - x0) * i / 4, 0, z0 + (z1 - z0) * j / 2)
				local h = H(p.X, p.Z)
				low, high = min(low, h), max(high, h)
			end
		end
		return low, high
	end
	-- 오색토 마당: 가운데 황(땅 그대로, 반너비 7.5), 둘레 네 사다리꼴 (북동 청, 남동 적, 남서 백, 북서 흑을 길 방향에 맞춘다)
	local plateTop = court + 0.4
	local soils = {
		{ 0, -1, rgb(96, 112, 104) }, -- 앞(북동): 청
		{ 1, 0, rgb(156, 74, 52) }, -- 오른쪽(남동): 적
		{ 0, 1, rgb(214, 204, 182) }, -- 뒤(남서): 백
		{ -1, 0, rgb(64, 56, 50) }, -- 왼쪽(북서): 흑
	}
	local inner, outer = 7.5, 18
	local up = Vector3.yAxis
	for _, s in soils do
		local nx, nz = s[1], s[2]
		local tx, tz = -nz, nx -- 변을 따라
		local function Q(u: number, v: number): Vector3
			-- u: 변을 따라, v: 가운데에서 바깥으로
			return W(tx * u + nx * v, plateTop, tz * u + nz * v)
		end
		local col = s[3]
		Build.slab(
			f,
			"Osaekto",
			Q(-inner, inner),
			Q(inner, inner) - Q(-inner, inner),
			Q(-inner, outer) - Q(-inner, inner),
			0.6,
			up,
			col,
			M.Ground
		)
		Build.rightTri(f, "Osaekto", Q(-inner, outer), Q(-inner, inner), Q(-outer, outer), 0.6, up, col, M.Ground)
		Build.rightTri(f, "Osaekto", Q(inner, outer), Q(inner, inner), Q(outer, outer), 0.6, up, col, M.Ground)
	end
	-- 마당 테두리 장대석, 둘레 다진 흙 단, 그 밖으로 세 층 축대 (판축 줄).
	-- 둔덕 꼭대기(반지름 22)가 평평하고 바깥으로 비탈지므로, 층마다 윗면은 그 층 안쪽 테 둘레의 가장 높은 땅에 맞춘다
	-- (어디서도 묻히지 않는다). 땅이 낮은 남동쪽은 축대가 높게 선다
	local function ringHigh(a: number): number
		local hi = -math.huge
		for k = 0, 23 do
			local u = -a + 2 * a * k / 23
			for _, p in { { u, -a }, { u, a }, { -a, u }, { a, u } } do
				local w = W(p[1], 0, p[2])
				hi = max(hi, H(w.X, w.Z))
			end
		end
		return hi
	end
	local tiers = {
		{ 18, 19.6, court + 0.95, rgb(158, 150, 136), M.Granite },
		{ 19.6, 27, court + 0.55, C.earth, M.Sandstone },
	}
	local edges = { 27, 32.5, 38, 43.5 }
	for i = 1, 3 do
		local a, b = edges[i], edges[i + 1]
		local top = min(tiers[#tiers][3] - 0.9, ringHigh(a) + 0.35)
		table.insert(tiers, { a, b, top, jitter(C.earth, rng, 0.05), M.Sandstone })
	end
	for ti, t in tiers do
		local a, b, top, col, mat = t[1], t[2], t[3], t[4], t[5]
		local mid, th = (a + b) / 2, b - a
		for _, side in { { 0, -1 }, { 0, 1 }, { -1, 0 }, { 1, 0 } } do
			local long = side[1] == 0
			-- 변을 22 남짓 토막으로: 비탈을 따라 밑을 묻고, 땅이 이미 윗면까지 올라온 토막은 건너뛴다
			local span = if long then b else a
			local nseg = math.ceil(2 * span / 22)
			for k = 0, nseg - 1 do
				local u0, u1 = -span + 2 * span * k / nseg, -span + 2 * span * (k + 1) / nseg
				local x0, x1, z0, z1
				if long then
					x0, x1, z0, z1 = u0, u1, side[2] * mid - th / 2, side[2] * mid + th / 2
				else
					x0, x1, z0, z1 = side[1] * mid - th / 2, side[1] * mid + th / 2, u0, u1
				end
				local low = groundUnder(x0, x1, z0, z1)
				if low < top - 0.5 then
					local bottom = low - 1.2
					local size = V3(x1 - x0, top - bottom, z1 - z0)
					local cf = L * CFrame.new((x0 + x1) / 2, (top + bottom) / 2, (z0 + z1) / 2)
					block(f, "Chukdae", size, cf, col, mat)
				end
			end
			if ti > 2 then
				-- 판축 줄 (축대 앞면, 변 하나에 한 줄. 땅에 묻힌 토막 앞은 땅속이라 보이지 않는다)
				local c = if long
					then V3(0, top - 0.7, side[2] * (b + 0.02))
					else V3(side[1] * (b + 0.02), top - 0.7, 0)
				local stripe = if long then V3(2 * b + 0.04, 0.22, 0.1) else V3(0.1, 0.22, 2 * a + 0.04)
				block(f, "Panchuk", stripe, L * CFrame.new(c), C.earthDark, M.Sandstone)
			end
		end
	end
	-- 앞뒤 돌계단 (축대를 타고 내려간다) + 소맷돌
	for _, dir in { -1, 1 } do
		local start = 19.6
		local endZ = 46
		local gEnd = H(W(0, 0, dir * endZ).X, W(0, 0, dir * endZ).Z)
		local topY = court + 0.95
		local count = max(3, math.ceil((topY - gEnd) / 0.55))
		local depth = (endZ - start) / count
		for i = 1, count do
			local y = topY - (i - 0.5) * (topY - gEnd) / count
			local z0 = start + (i - 1) * depth
			local low = gEnd - 1.5
			block(
				f,
				"Gyedan",
				V3(6.4, y - low, depth + 0.05),
				L * CFrame.new(0, (y + low) / 2, dir * (z0 + depth / 2)),
				P.granite,
				M.Granite
			)
		end
		for _, x in { -3.75, 3.75 } do
			local a = W(x, topY + 0.9, dir * (start - 0.4))
			local b = W(x, gEnd + 0.7, dir * (endZ + 0.2))
			beam(f, "Somaet", a, b, 1.1, 1.6, P.graniteDark, M.Granite)
		end
		-- 계단 머리의 흙 무사 둘 (바깥을 본다)
		for _, x in { -7.2, 7.2 } do
			local base = W(x, court + 0.55, dir * 23.4)
			base = V3(base.X, max(base.Y, H(base.X, base.Z)), base.Z)
			local look = face(base, base + fwd * -dir)
			guardian(f, look, 1.05, rng)
		end
	end
	-- 둘째 층 귀와 옆 가운데에 황토 깃발
	local t3 = tiers[3]
	local bp = (t3[1] + t3[2]) / 2
	for _, p in { { -bp, -bp }, { bp, -bp }, { -bp, bp }, { bp, bp }, { -bp, 0 }, { bp, 0 } } do
		local g = W(p[1], t3[3], p[2])
		g = V3(g.X, max(g.Y, H(g.X, g.Z)), g.Z)
		local toward = g + (W(p[1], 0, p[2]) - W(0, 0, 0)).Unit * 5
		Build.banner(f, g, toward, jitter(C.ochreCloth, rng, 0.05), 12)
	end
	-- 오행처 앞의 청동 정 (가운데 단에서 12 떨어진 앞쪽)
	ding(f, W(0, plateTop, -12.5), rng)
	-- 거북 비석: 앞 계단 아래 길섶
	local st = W(13, 0, -52)
	monument(f, st.X, st.Z, "황구토단", W(13, 0, -80), rng)
	-- 길 어귀의 깃발 줄
	for _, z in { -60, 60 } do
		for _, x in { -6.5, 6.5 } do
			local p = W(x, 0, z)
			Build.banner(
				f,
				at(p.X, p.Z),
				at(p.X, p.Z) + fwd * (if z < 0 then 1 else -1),
				jitter(C.ochreCloth, rng, 0.06),
				10
			)
		end
	end
	return f
end

-- 굴집 마을: 넷째 탁상 바위 북쪽 기슭을 깎아 세운 흙벽에 아치 굴 셋, 앞마당(흙담, 대문), 장독대, 수레, 맷돌, 장작,
-- 고추 말리는 시렁, 대추나무, 마당 밖 조밭. 대문은 북쪽(송계에서 오는 길 쪽)을 본다
local HAMLET = { x = -350, z = 534, half = 17 } -- 흙벽 앞면 가운데 (탁상 바위 가운데에서 북쪽 26)
local function caveHamlet(parent: Instance, rng)
	local f = model(parent, "굴집 마을")
	local fx, fz, half = HAMLET.x, HAMLET.z, HAMLET.half
	local g = H(fx, fz - 3)
	local wallTop = 27
	-- 깎아 세운 흙벽 (뒤는 바위 속으로 묻힌다) + 판축 줄 + 위 낮은 담
	local base = g - 3
	block(
		f,
		"Heukbyeok",
		V3(2 * half, wallTop - base, 11),
		CFrame.new(fx, (wallTop + base) / 2, fz + 5.5),
		C.loess,
		M.Sandstone
	)
	for _, y in { g + 9.6, g + 12.4 } do
		block(f, "Panchuk", V3(2 * half + 0.04, 0.3, 0.12), CFrame.new(fx, y, fz - 0.02), C.earthDark, M.Sandstone)
	end
	block(f, "Yeojang", V3(2 * half, 1.1, 1), CFrame.new(fx, wallTop + 0.55, fz + 0.5), C.earth, M.Sandstone)
	-- 굴 앞 기와 처마 (흙벽에 붙은 홑처마)
	local eaveY = g + 7.9
	local eave = CFrame.new(fx, eaveY, fz - 0.8) * CFrame.Angles(0, math.pi, 0)
	wedge(f, "Cheoma", V3(2 * half - 3, 0.8, 1.8), eave, P.giwa, M.ClayRoofTiles)
	block(f, "Maru", V3(2 * half - 2.6, 0.35, 0.4), CFrame.new(fx, eaveY + 0.55, fz + 0.1), P.giwaDark, M.Slate)
	-- 아치 굴 셋: 어두운 굴 입 + 반달 머리, 창호지 문살 벽, 문, 문살, 붉은 글씨 띠, 고추 꿰미
	local dark = rgb(46, 36, 30)
	for _, ox in { -8, 0, 8 } do
		local x = fx + ox
		local gx = H(x, fz - 1)
		local zf = fz - 0.15
		block(f, "Gurip", V3(4.8, 4.6, 0.3), CFrame.new(x, gx + 2.3 - 0.4, zf), dark, M.Slate)
		cyl(f, "Gurip", V3(x, gx + 4.2, zf - 0.15), V3(x, gx + 4.2, zf + 0.15), 4.8, dark, M.Slate)
		block(f, "Changho", V3(4.1, 4.0, 0.3), CFrame.new(x, gx + 2.0, zf - 0.12), P.hanji, M.SmoothPlastic)
		cyl(f, "Changho", V3(x, gx + 4.0, zf - 0.27), V3(x, gx + 4.0, zf + 0.03), 4.1, P.hanji, M.SmoothPlastic)
		block(f, "Mun", V3(1.7, 3.4, 0.2), CFrame.new(x, gx + 1.3, zf - 0.32), P.woodDark, M.Wood)
		for _, dx in { -1.4, 1.4 } do
			block(f, "Munsal", V3(0.14, 4.6, 0.12), CFrame.new(x + dx, gx + 2.6, zf - 0.33), P.woodDark, M.Wood)
		end
		block(f, "Munsal", V3(4.1, 0.14, 0.12), CFrame.new(x, gx + 3.6, zf - 0.33), P.woodDark, M.Wood)
		for _, dx in { -2.9, 2.9 } do
			deco(
				block(
					f,
					"Ipchun",
					V3(0.55, 2.2, 0.06),
					CFrame.new(x + dx, gx + 2.6, zf - 0.2),
					rgb(176, 52, 40),
					M.Fabric
				)
			)
		end
		deco(block(f, "Gochu", V3(0.45, 2.6, 0.45), CFrame.new(x + 3.6, gx + 4.4, zf - 0.5), C.pepper, M.SmoothPlastic))
	end
	-- 굴뚝 둘 (흙벽 위)
	for _, ox in { -12, 6 } do
		local c = V3(fx + ox, wallTop, fz + 3)
		block(f, "Gulttuk", V3(1.4, 3.2, 1.4), CFrame.new(c + V3(0, 1.6, 0)), C.earthDark, M.Brick)
		block(f, "Gulttukgat", V3(1.9, 0.4, 1.9), CFrame.new(c + V3(0, 3.4, 0)), P.giwaDark, M.Slate)
	end
	-- 마당 흙담 (앞 가운데 대문)
	local z0 = fz - 20
	local wx0, wx1 = fx - half + 1, fx + half - 1
	local function gp(x: number, z: number): Vector3
		return V3(x, H(x, z), z)
	end
	earthWall(f, gp(wx0, fz - 0.5), gp(wx0, z0), 3.6, rng)
	earthWall(f, gp(wx1, fz - 0.5), gp(wx1, z0), 3.6, rng)
	earthWall(f, gp(wx0, z0), gp(fx - 3.2, z0), 3.6, rng)
	earthWall(f, gp(fx + 3.2, z0), gp(wx1, z0), 3.6, rng)
	-- 대문: 기둥 둘, 인방, 맞배 기와 지붕, 반쯤 연 문짝
	local gy = H(fx, z0)
	local gate = model(f, "대문")
	for _, s in { -1, 1 } do
		block(gate, "Gidung", V3(0.8, 6.2, 0.8), CFrame.new(fx + s * 2.8, gy + 2.6, z0), P.wood, M.Wood)
		block(
			gate,
			"Munjjak",
			V3(2.5, 4.8, 0.25),
			CFrame.new(fx + s * 2.6, gy + 2.4, z0 + 1.1) * CFrame.Angles(0, s * rad(62), 0),
			P.woodDark,
			M.WoodPlanks
		)
	end
	block(gate, "Inbang", V3(6.6, 0.6, 0.7), CFrame.new(fx, gy + 5.6, z0), P.wood, M.Wood)
	for _, s in { -1, 1 } do
		wedge(
			gate,
			"Giwa",
			V3(8, 1.1, 1.7),
			CFrame.new(fx, gy + 6.5, z0 + s * 0.85) * CFrame.Angles(0, if s > 0 then 0 else math.pi, 0),
			P.giwa,
			M.ClayRoofTiles
		)
	end
	block(gate, "Maru", V3(8.4, 0.4, 0.45), CFrame.new(fx, gy + 7.12, z0), P.giwaDark, M.Slate)
	-- 마당 살림
	Build.jars(f, face(at(fx + 11, fz - 4.5), at(fx + 11, fz - 12)), rng, 4)
	Build.cart(f, face(at(fx - 11, fz - 12), at(fx - 9, fz - 2)) * CFrame.Angles(0, 0.3, 0))
	local mill = at(fx + 3, fz - 11)
	cyl(f, "Matdol", mill + V3(0, -0.2, 0), mill + V3(0, 0.6, 0), 3.6, P.granite, M.Granite)
	cyl(f, "Matdol", mill + V3(0, 0.6, 0), mill + V3(0, 1.3, 0), 3.0, P.graniteDark, M.Granite)
	beam(f, "Eoi", mill + V3(0.9, 1.0, 0), mill + V3(2.6, 1.0, 0.3), 0.25, 0.25, P.wood, M.Wood)
	-- 장작 더미 (오른쪽 담에 기대)
	local wy = lowAt(wx1 - 1.6, fz - 12, 1.5)
	for i = 0, 5 do
		local row = i // 3
		local p = V3(wx1 - 1.6 - (i % 3) * 0.85 - row * 0.42, wy + 0.4 + row * 0.75, fz - 12)
		cyl(f, "Jangjak", p - V3(0, 0, 1.4), p + V3(0, 0, 1.4), 0.8, P.wood, M.Wood)
	end
	-- 고추·옥수수 말리는 시렁
	local rack = at(fx - 9, fz - 4)
	for _, s in { -1, 1 } do
		beam(f, "Sireong", rack + V3(s * 2.2, -0.3, 0), rack + V3(s * 2.2, 4.4, 0), 0.3, 0.3, P.woodDark, M.Wood)
	end
	beam(f, "Sireong", rack + V3(-2.4, 4.2, 0), rack + V3(2.4, 4.2, 0), 0.25, 0.25, P.woodDark, M.Wood)
	for i, col in { C.pepper, rgb(214, 170, 64), C.pepper, rgb(214, 170, 64) } do
		deco(
			block(
				f,
				"Kkwemi",
				V3(0.5, 2.4, 0.5),
				CFrame.new(rack + V3(-1.65 + (i - 1) * 1.1, 2.85, 0)),
				col,
				M.SmoothPlastic
			)
		)
	end
	-- 대추나무
	Build.broadleaf(
		f,
		at(fx + 9, fz - 15),
		rng,
		{ height = 8.5, leaves = { rgb(86, 108, 60), rgb(110, 128, 70), rgb(140, 150, 84) } }
	)
	-- 대문 앞 디딤돌 (길 쪽으로)
	for i = 1, 7 do
		local px, pz = fx - i * 2.6, z0 - 2 - i * 4.6
		local s = rng(1.6, 2.2)
		block(
			f,
			"Didim",
			V3(s, 0.5, s * 0.8),
			CFrame.new(px, H(px, pz) + 0.05, pz) * CFrame.Angles(0, rng(0, 3), 0),
			P.granite,
			M.Granite
		)
	end
	-- 조밭: 마당 동쪽, 낮은 흙둑 안에 이랑
	local fx0, fz0 = fx + half + 6, fz - 22
	local fw, fd = 16, 18
	local fg = lowAt(fx0 + fw / 2, fz0 + fd / 2, 8)
	for _, e in
		{
			{ fw / 2, -0.3, fw + 0.6, 0.6 },
			{ fw / 2, fd + 0.3, fw + 0.6, 0.6 },
			{ -0.3, fd / 2, 0.6, fd },
			{ fw + 0.3, fd / 2, 0.6, fd },
		}
	do
		local px, pz = fx0 + e[1], fz0 + e[2]
		block(f, "Dunk", V3(e[3], 1.4, e[4]), CFrame.new(px, H(px, pz) + 0.2, pz), C.earth, M.Ground)
	end
	for i = 1, 5 do
		local pz = fz0 + i * fd / 6
		local px = fx0 + fw / 2
		local y = H(px, pz)
		deco(
			block(
				f,
				"Jo",
				V3(fw - 1.4, 1.5, 1.1),
				CFrame.new(px, y + 0.5, pz),
				jitter(rgb(150, 150, 78), rng, 0.06),
				M.LeafyGrass
			)
		)
		deco(block(f, "Isak", V3(fw - 1.6, 0.4, 0.9), CFrame.new(px, y + 1.35, pz), rgb(204, 172, 92), M.Grass))
	end
	-- 허수아비
	local sc = at(fx0 + fw / 2, fz0 + fd / 2)
	beam(f, "Heosu", sc - V3(0, 0.5, 0), sc + V3(0, 5, 0), 0.3, 0.3, P.wood, M.Wood)
	beam(f, "Heosu", sc + V3(-1.8, 3.6, 0), sc + V3(1.8, 3.6, 0), 0.25, 0.25, P.wood, M.Wood)
	block(f, "Ot", V3(1.6, 2, 0.7), CFrame.new(sc + V3(0, 3.1, 0)), rgb(120, 104, 150), M.Fabric)
	block(f, "Satgat", V3(2.2, 0.35, 2.2), CFrame.new(sc + V3(0, 5.1, 0)), C.straw, M.Fabric)
	return f
end

-- 황구 들판: 굽은 소나무, 먼지 낀 활엽수(느릅·대추), 마른 덤불, 바위, 마른 풀
local function loessNature(parent: Instance, rng)
	local f = folder(parent, "황구 숲")
	local function free(x: number, z: number, pad: number): boolean
		local id = regionId(x, z)
		if id ~= "loess" and id ~= "earth" and id ~= "canyon" then
			return false
		end
		if not clearOf(x, z, pad) or roadDist(x, z) < 6 + pad then
			return false
		end
		if Land.polyDist(x, z, Land.CANYON, 60) < 36 then
			return false
		end
		for _, b in Land.BUTTES do
			local dx, dz = x - b[1], z - b[2]
			if dx * dx + dz * dz < (b[3] + 19 + pad) ^ 2 then
				return false
			end
		end
		local dE = sqrt((x - EARTH.x) ^ 2 + (z - EARTH.z) ^ 2)
		if dE < 64 + pad then
			return false
		end
		if abs(x - HAMLET.x) < 45 and z > HAMLET.z - 48 and z < HAMLET.z + 6 then
			return false
		end
		return H(x, z) < 32 and relief(x, z, 3) < 3
	end
	local box = { -760, -60, 220, 960 }
	local taken = {}
	for _, p in
		scatter(rng, 6, box, 40, function(x, z)
			return free(x, z, 4)
		end, taken)
	do
		Build.pine(
			f,
			V3(p[1], lowAt(p[1], p[2], 1), p[2]),
			rng,
			{ height = rng(10, 15), tiers = 4 + floor(rng(0, 1.99)) }
		)
	end
	local dusty = { rgb(86, 104, 60), rgb(112, 124, 72), rgb(146, 148, 86) }
	for _, p in
		scatter(rng, 4, box, 34, function(x, z)
			return free(x, z, 4)
		end, taken)
	do
		Build.broadleaf(
			f,
			V3(p[1], lowAt(p[1], p[2], 1), p[2]),
			rng,
			{ height = rng(7, 10), leaves = dusty, blobs = 7 }
		)
	end
	for _, p in
		scatter(rng, 2, box, 30, function(x, z)
			return free(x, z, 3)
		end, taken)
	do
		deadTree(f, p[1], p[2], rng)
	end
	for _, p in
		scatter(rng, 24, box, 10, function(x, z)
			return free(x, z, 1)
		end, taken)
	do
		dryShrub(f, p[1], p[2], rng, nil, { C.sageDark, C.dustLeaf, rgb(140, 140, 84) })
	end
	for _, p in
		scatter(rng, 10, box, 16, function(x, z)
			return free(x, z, 2)
		end, taken)
	do
		boulder(f, p[1], p[2], rng(1.8, 4.5), rng, BANDS[floor(rng(1, #BANDS + 0.99))])
	end
	for _, p in
		scatter(rng, 16, box, 7, function(x, z)
			return free(x, z, 0)
		end, taken)
	do
		tuft(f, p[1], p[2], rng)
	end
end

-- 단애곡 ---------------------------------------------------------------------------------
-- 골짜기 바닥은 -14, 벽은 가운데 줄에서 10~40 사이 비탈. 띠 높이는 골짜기 전체에 같다 (양쪽 벽과 굽이를 돌아 이어진다).
-- 지형은 황구·한해 무늬가 옅은 가운데 토막(s 300~405)을 깎지 않아 골짜기가 둘로 끊긴다: 끊긴 끝은 무너진 바위로 막는다.
local CANYON_BANDS = {
	{ -13.6, -6.6, BANDS[6] },
	{ -6.6, 0.4, BANDS[1] },
	{ 0.4, 7.4, BANDS[3] },
	{ 7.4, 14.4, BANDS[2] },
	{ 14.4, 21.4, BANDS[7] },
}
local function canyonCarved(x: number, z: number): boolean
	return H(x, z) < -12.5
end
-- 꺾은선을 len 남짓 토막으로: { x, z (가운데 줄), dx, dz (흐름), nx, nz (왼쪽 법선), seg, s (처음부터 거리), len }
local function canyonPieces(len: number)
	local out = {}
	local pts = Land.CANYON.pts
	local s0 = 0
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local dx, dz = b[1] - a[1], b[2] - a[2]
		local l = sqrt(dx * dx + dz * dz)
		dx, dz = dx / l, dz / l
		local n = max(1, floor(l / len + 0.5))
		local pl = l / n
		for k = 0, n - 1 do
			local t = (k + 0.5) * pl
			table.insert(out, {
				x = a[1] + dx * t,
				z = a[2] + dz * t,
				dx = dx,
				dz = dz,
				nx = -dz,
				nz = dx,
				seg = i,
				s = s0 + t,
				len = pl,
			})
		end
		s0 += l
	end
	return out
end
-- 가운데 줄 위 s 자리 (점과 흐름 방향)
local function canyonAt(s: number): (number, number, number, number)
	local pts = Land.CANYON.pts
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local dx, dz = b[1] - a[1], b[2] - a[2]
		local l = sqrt(dx * dx + dz * dz)
		if s <= l or i == #pts - 1 then
			local t = math.clamp(s, 0, l)
			return a[1] + dx * t / l, a[2] + dz * t / l, dx / l, dz / l
		end
		s -= l
	end
	return pts[1][1], pts[1][2], 1, 0
end

-- 부채꼴 띠: 가운데 (cx, cz) 에서 각 a0..a1 (라디안) 쪽으로 (굽이 바깥, 골짜기 끝)
local function strataFan(parent: Instance, cx: number, cz: number, a0: number, a1: number, bands, rng)
	local count = max(1, math.ceil(abs(a1 - a0) / rad(26)))
	local da = (a1 - a0) / count
	local half = math.tan(abs(da) / 2)
	for k = 0, count - 1 do
		local a = a0 + (k + 0.5) * da
		strataRay(parent, cx, cz, cos(a), sin(a), 46, bands, function(front)
			return 2 * front * half + 1.8
		end, rng, { steep = 0.45 })
	end
end

-- 돌기둥 (후두): 아래가 넓고 허리가 잘록하며 위에 옅은 갓바위
local function hoodoo(parent: Instance, x: number, z: number, height: number, rng)
	local m = model(parent, "돌기둥")
	local y = lowAt(x, z, 3) - 1.2
	local k = floor(rng(0, #BANDS))
	local widths = { 1, 0.78, 0.62, 0.7 }
	local w0 = height * rng(0.2, 0.26)
	local seg = (height + 1.2) / 4
	for i = 1, 4 do
		local w = w0 * widths[i] * rng(0.92, 1.08)
		local cf = CFrame.new(x + rng(-0.3, 0.3), y + seg / 2, z + rng(-0.3, 0.3))
			* CFrame.Angles(rng(-0.04, 0.04), rng(0, TAU), rng(-0.04, 0.04))
		block(
			m,
			"Dol",
			V3(w, seg + 0.2, w * rng(0.85, 1)),
			cf,
			jitter(BANDS[(k + i) % #BANDS + 1], rng, 0.05),
			M.Sandstone
		)
		y += seg
	end
	local cap = w0 * rng(0.95, 1.15)
	block(
		m,
		"Gatbawi",
		V3(cap, w0 * 0.32, cap * rng(0.8, 1)),
		CFrame.new(x, y + w0 * 0.12, z) * CFrame.Angles(rng(-0.08, 0.08), rng(0, TAU), rng(-0.08, 0.08)),
		jitter(CAPROCK, rng, 0.04),
		M.Sandstone
	)
	return m
end

-- 잔도: 깎아지른 벽(wallT: 가운데 줄에서 벽 앞면까지)을 따라 s0 에서 s1 까지, 높이 y0 에서 y1 로 내려가는 널길.
-- 널판, 벽에 박은 받침, 바깥 난간
local function plankWalk(parent: Instance, s0: number, s1: number, y0: number, y1: number, wallT: (number) -> number)
	local m = model(parent, "잔도")
	local n = math.ceil((s1 - s0) / 7.5)
	local W = 3.4
	local prevTop = nil
	for i = 0, n do
		local s = s0 + (s1 - s0) * i / n
		local x, z, dx, dz = canyonAt(s)
		local nx, nz = -dz, dx
		local t = wallT(s)
		local y = y0 + (y1 - y0) * i / n
		local inner = V3(x + nx * t, y, z + nz * t)
		local outer = V3(x + nx * (t - W), y, z + nz * (t - W))
		if i < n then
			local s2 = s0 + (s1 - s0) * (i + 1) / n
			local x2, z2 = canyonAt(s2)
			local t2 = wallT(s2)
			local y2 = y0 + (y1 - y0) * (i + 1) / n
			local a = V3(x + nx * (t - W / 2), y - 0.2, z + nz * (t - W / 2))
			local b = V3(x2 + nx * (t2 - W / 2), y2 - 0.2, z2 + nz * (t2 - W / 2))
			beam(
				m,
				"Neolpan",
				a - (b - a).Unit * 0.15,
				b + (b - a).Unit * 0.15,
				W,
				0.4,
				jitter(P.wood, function(lo, hi)
					return (lo + hi) / 2 + (hi - lo) * 0.3 * sin(i * 2.1)
				end, 0.06),
				M.WoodPlanks
			)
		end
		-- 받침: 널판 바깥 밑에서 벽 속으로 비스듬히
		beam(
			m,
			"Batchim",
			outer + V3(0, -0.45, 0),
			inner + V3(nx * 0.8, -3.2, nz * 0.8),
			0.45,
			0.45,
			P.woodDark,
			M.Wood
		)
		-- 난간 기둥과 띠
		local top = outer + V3(0, 3.0, 0) - V3(nx, 0, nz) * -0.2
		beam(m, "Gidung", outer + V3(0, -0.4, 0), top, 0.35, 0.35, P.woodDark, M.Wood)
		if prevTop then
			beam(m, "Nangan", prevTop, top, 0.28, 0.3, P.wood, M.Wood)
		end
		prevTop = top
	end
	return m
end

local function canyon(parent: Instance, rng)
	local f = folder(parent, "단애곡")
	local walls = model(f, "단애곡 벼랑")
	local pts = Land.CANYON.pts
	-- 잔도가 붙는 벽: 둘째 선분(남쪽으로 곧게 뻗은 토막)의 서쪽 벽은 바닥에서 벼랑 끝까지 한 장으로 깎아지른다
	local sheerFront = {}
	for _, p in canyonPieces(30) do
		if canyonCarved(p.x, p.z) then
			for _, side in { 1, -1 } do
				local nx, nz = p.nx * side, p.nz * side
				if p.seg == 2 and side == 1 then
					-- 토막 앞·가운데·뒤 세 줄을 재어 벼랑 끝 높이는 가장 낮은 곳에, 뒤끝은 가장 먼 곳에 맞춘다
					local yTop, t0, t1 = math.huge, math.huge, 0
					local lines = {}
					for _, u in { -0.45, 0, 0.45 } do
						local hs = profile(p.x + p.dx * u * p.len, p.z + p.dz * u * p.len, nx, nz, 46)
						for j = #hs - 12, #hs do
							yTop = min(yTop, hs[j] - 0.5)
						end
						t0 = min(t0, reach(hs, -13.3) or 9)
						table.insert(lines, hs)
					end
					for _, hs in lines do
						t1 = max(t1, reach(hs, yTop) or 40)
					end
					local front = t0 - 1.3
					table.insert(sheerFront, { p.s, front, p.len, yTop })
					slabAlong(
						walls,
						p.x,
						p.z,
						nx,
						nz,
						front,
						t1 + 1.6,
						-15.5,
						yTop,
						p.len + 1.4,
						jitter(BANDS[6], rng, 0.04)
					)
					-- 벽 앞면의 지층 줄 (조금 나온 얇은 띠)
					for bi, b in CANYON_BANDS do
						if bi > 1 and b[1] < yTop - 1.5 then
							local y = b[1]
							slabAlong(
								walls,
								p.x,
								p.z,
								nx,
								nz,
								front - 0.3,
								front + 0.4,
								y - 0.9,
								min(y + 1.4, yTop - 0.3),
								p.len + 1.5,
								jitter(b[3], rng, 0.05)
							)
						end
					end
				else
					strataRay(walls, p.x, p.z, nx, nz, 46, CANYON_BANDS, function()
						return p.len + 2
					end, rng, { jut = rng(-0.3, 0.6), steep = 0.45 })
				end
			end
		end
	end
	-- 굽이 바깥 (안쪽은 토막이 겹친다)
	for i = 2, #pts - 1 do
		local v, a, b = pts[i], pts[i - 1], pts[i + 1]
		if canyonCarved(v[1], v[2]) then
			local f1 = V3(v[1] - a[1], 0, v[2] - a[2]).Unit
			local f2 = V3(b[1] - v[1], 0, b[2] - v[2]).Unit
			for _, side in { 1, -1 } do
				local n1 = V3(-f1.Z, 0, f1.X) * side
				local n2 = V3(-f2.Z, 0, f2.X) * side
				if f2:Dot(n1) < -0.02 then
					local a0 = math.atan2(n1.Z, n1.X)
					local a1 = math.atan2(n2.Z, n2.X)
					local d = (a1 - a0 + math.pi) % TAU - math.pi
					strataFan(walls, v[1], v[2], a0 + d * 0.1, a0 + d * 0.9, CANYON_BANDS, rng)
				end
			end
		end
	end
	-- 두 끝 (둥글게 막힌 머리)
	for _, e in { { 1, 2 }, { #pts, #pts - 1 } } do
		local p, q = pts[e[1]], pts[e[2]]
		local back = V3(p[1] - q[1], 0, p[2] - q[2]).Unit
		local ab = math.atan2(back.Z, back.X)
		strataFan(walls, p[1], p[2], ab - rad(68), ab + rad(68), CANYON_BANDS, rng)
	end
	-- 끊긴 끝: 무너져 쌓인 바위 (골짜기를 막는다)
	local fall = model(f, "무너진 바위")
	for _, r in { { 278, 300, 1 }, { 425, 404, -1 } } do
		for k = 0, 8 do
			local s = r[1] + (r[2] - r[1]) * (k / 8) ^ 0.8
			local x, z, dx, dz = canyonAt(s)
			local o = rng(-13, 13) * (0.4 + 0.6 * k / 8)
			local px, pz = x - dz * o, z + dx * o
			boulder(fall, px, pz, rng(4, 8) * (0.6 + 0.5 * k / 8), rng, BANDS[floor(rng(1, #BANDS + 0.99))])
		end
	end
	-- 잔도: 둘째 토막 서쪽 벽, 벼랑 위(북쪽)에서 바닥(남쪽)으로
	local function wallT(s: number): number
		local best, bt = math.huge, 9
		for _, sf in sheerFront do
			local d = abs(sf[1] - s)
			if d < best then
				best, bt = d, sf[2]
			end
		end
		return bt
	end
	local s0, s1 = 152, 262
	local rimY = 0
	for _, sf in sheerFront do
		if abs(sf[1] - s0) < 14 then
			rimY = sf[4]
		end
	end
	plankWalk(f, s0, s1, rimY - 0.6, -12.2, wallT)
	-- 잔도 아래 끝 계단 (바닥으로)
	do
		local x, z, dx, dz = canyonAt(s1)
		local nx, nz = -dz, dx
		local t = wallT(s1)
		for k = 1, 3 do
			local px, pz = x + nx * (t - 1.7) + dx * (k * 1.6 + 0.8), z + nz * (t - 1.7) + dz * (k * 1.6 + 0.8)
			local y = -12.2 - k * 0.45
			block(
				f,
				"Didim",
				V3(3.4, y + 15, 1.7),
				face(V3(px, (y - 15) / 2, pz), V3(px + dx, (y - 15) / 2, pz + dz)),
				P.wood,
				M.WoodPlanks
			)
		end
	end
	-- 잔도 위 끝: 벼랑 위 들머리 비석
	do
		local x, z, dx, dz = canyonAt(s0 - 6)
		local nx, nz = -dz, dx
		local px, pz = x + nx * (wallT(s0) + 8), z + nz * (wallT(s0) + 8)
		monument(f, px, pz, "단애곡", V3(px - dz * 10, 0, pz - dx * 10) - V3(nx, 0, nz) * 0 + V3(0, 0, -6), rng)
	end
	-- 돌기둥: 굽이 바닥, 벼랑 위
	local spots = {
		{ 135, 0, 16 },
		{ 128, 6, 11 },
		{ 470, -4, 18 },
		{ 476, 5, 12 },
		{ 600, 0, 14 },
		{ 60, 44, 17 },
		{ 200, -46, 20 },
		{ 214, -50, 13 },
		{ 540, 46, 15 },
		{ 520, -48, 19 },
	}
	for _, sp in spots do
		local x, z, dx, dz = canyonAt(sp[1])
		local px, pz = x - dz * sp[2], z + dx * sp[2]
		if clearOf(px, pz, 4) and roadDist(px, pz) > 8 then
			hoodoo(f, px, pz, sp[3], rng)
		end
	end
	-- 바닥: 마른 나무, 바위, 덤불
	for _, s in { 40, 230, 450, 560 } do
		local x, z, dx, dz = canyonAt(s)
		local o = rng(-6, 6)
		deadTree(f, x - dz * o, z + dx * o, rng, { height = rng(7, 10) })
	end
	for k = 1, 14 do
		local s = rng(10, 610)
		if s < 270 or s > 430 then
			local x, z, dx, dz = canyonAt(s)
			local o = rng(-9, 9)
			if k % 2 == 0 then
				boulder(f, x - dz * o, z + dx * o, rng(1.5, 3.5), rng, BANDS[floor(rng(1, #BANDS + 0.99))])
			else
				dryShrub(f, x - dz * o, z + dx * o, rng, rng(1.8, 3))
			end
		end
	end
	return f
end

-- 관성대 ---------------------------------------------------------------------------------
-- 꼭대기(반지름 72, 높이 96) 가운데 반지름 38 안은 칠성단과 팔괘 기둥 자리라 0.5 넘는 것을 두지 않는다.
-- 오르막은 북동(315°)에서 시계 반대쪽(각이 줄어드는 쪽)으로 130° 돌아 서쪽(185°)에서 꼭대기에 닿는다 (반지름 72~90)
local function mesaPoint(deg: number, d: number, y: number?): Vector3
	local a = rad(deg)
	return V3(MESA.x + cos(a) * d, y or 0, MESA.z + sin(a) * d)
end
local function rampY(deg: number): number
	return 30 + 66 * ((315 - deg) % 360) / 130
end

-- 둥근 고리 (혼천의): 가운데 c, 평면 축 u, v, 반지름 R, 마디 n, 굵기 t
local function ring(
	parent: Instance,
	c: Vector3,
	u: Vector3,
	v: Vector3,
	R: number,
	n: number,
	t: number,
	color: Color3
)
	local prev = c + u * R
	for i = 1, n do
		local a = i * TAU / n
		local p = c + (u * cos(a) + v * sin(a)) * R
		local d = (p - prev).Unit
		beam(parent, "Gori", prev - d * 0.12, p + d * 0.12, t, t, color, M.Metal)
		prev = p
	end
end

-- 혼천의: 지평환, 자오환, 적도환, 황도환, 극축과 가운데 옥구슬, 네 발과 받침
local function armillary(parent: Instance, base: Vector3)
	local m = model(parent, "혼천의")
	block(m, "Badachim", V3(13, 1.6, 13), CFrame.new(base + V3(0, 0.3, 0)), P.granite, M.Granite)
	block(m, "Badachim", V3(9.5, 1, 9.5), CFrame.new(base + V3(0, 1.6, 0)), P.graniteDark, M.Granite)
	local top = base + V3(0, 2.1, 0)
	local c = top + V3(0, 9.4, 0)
	local R = 8
	local lat = rad(37)
	local pole = V3(0, sin(lat), -cos(lat)) -- 북쪽(-z)으로 기운 극축
	local ex = Vector3.xAxis
	local ev = V3(0, cos(lat), sin(lat))
	local tilt = rad(23.5)
	ring(m, c, ex, Vector3.zAxis, R, 12, 0.6, C.bronze) -- 지평환
	ring(m, c, Vector3.yAxis, Vector3.zAxis, R + 0.4, 12, 0.55, C.bronzeDark) -- 자오환
	ring(m, c, ex, ev, R - 0.9, 12, 0.5, C.bronze) -- 적도환
	ring(m, c, ex, ev * cos(tilt) + pole * sin(tilt), R - 1.7, 12, 0.45, C.verdigris) -- 황도환
	cyl(m, "Geukchuk", c - pole * (R + 1.2), c + pole * (R + 1.2), 0.35, C.bronzeDark, M.Metal)
	local orb = ball(m, "Okgu", c, 1.5, C.verdigris, M.Glass)
	orb.Transparency = 0.15
	for k = 0, 3 do
		local a = rad(45 + k * 90)
		local o = V3(cos(a), 0, sin(a))
		beam(m, "Bal", c + o * R * 0.98 - V3(0, 0.2, 0), top + o * 5.2, 0.7, 0.7, C.bronzeDark, M.Metal)
	end
	cyl(m, "Batchimdae", top, c - V3(0, R + 0.4, 0), 1.0, C.bronzeDark, M.Metal)
	return m
end

-- 첨성대처럼 돌을 둥글게 쌓은 별 보는 탑 (꼭대기 정자석 하나는 떨어져 밑에 뒹군다)
local function starTower(parent: Instance, base: Vector3, toward: Vector3, rng)
	local m = model(parent, "첨성대")
	local look = face(base, toward)
	block(m, "Gidan", V3(9.6, 1.2, 9.6), look * CFrame.new(0, 0.2, 0), P.graniteDark, M.Granite)
	block(m, "Gidan", V3(8.2, 1, 8.2), look * CFrame.new(0, 1.2, 0), P.granite, M.Granite)
	local y = 1.7
	local h = 1.3
	local stone = rgb(176, 166, 146)
	for k = 0, 10 do
		local d = if k <= 9 then 4.1 + 2.7 * (1 - k / 9) ^ 1.7 else 4.3
		local p = look * CFrame.new(0, y, 0)
		cyl(m, "Dan", p.Position, (p * CFrame.new(0, h, 0)).Position, d, jitter(stone, rng, 0.04), M.Granite)
		y += h
	end
	-- 앞(남) 창
	local wd = 4.1 + 2.7 * (1 - 5 / 9) ^ 1.7
	block(m, "Chang", V3(1.6, 1.7, 0.5), look * CFrame.new(0, 1.7 + 5.5 * h, -wd / 2 + 0.12), rgb(40, 34, 30), M.Slate)
	-- 정자석 (# 모양 두 켜). 한 장은 떨어져 기단 곁에 누웠다
	local top = 1.7 + 11 * h
	for i, s in { -1, 1, -1, 1 } do
		local along = i <= 2
		local size = if along then V3(5.4, 0.7, 0.75) else V3(0.75, 0.7, 5.4)
		local off = if along then CFrame.new(0, top + 0.35, s * 1.75) else CFrame.new(s * 1.75, top + 1.05, 0)
		if i == 4 then
			block(
				m,
				"Jeongjaseok",
				size,
				look * CFrame.new(5.6, 0.75, 2.5) * CFrame.Angles(0, rad(28), rad(4)),
				stone,
				M.Granite
			)
		else
			block(m, "Jeongjaseok", size, look * off, stone, M.Granite)
		end
	end
	return m
end

-- 북두칠성 (비석 앞면에 새긴 별): 가로 x, 세로 y (비석 위가 +y)
local DIPPER =
	{ { 6.75, 11.5 }, { 1.38, 11.8 }, { -1.3, 4.3 }, { 2.03, 1.2 }, { 0.96, -4.3 }, { -0.07, -8.6 }, { -5.7, -12 } }
local function starTablet(parent: Instance, ground: Vector3, toward: Vector3, rng, broken: boolean?)
	local m = model(parent, "성도 비석")
	local look = face(ground, toward)
	local stone = rgb(120, 116, 112)
	block(m, "Badachim", V3(3.4, 1, 1.9), look * CFrame.new(0, 0.3, 0), P.graniteDark, M.Granite)
	local hgt = 5.6
	local slab = block(m, "Bimom", V3(2.8, hgt, 0.6), look * CFrame.new(0, 0.8 + hgt / 2, 0), stone, M.Slate)
	if broken then
		slab.CFrame = slab.CFrame * CFrame.Angles(rad(-4), 0, rad(6))
	else
		block(m, "Gaeseok", V3(3.3, 0.55, 1.0), look * CFrame.new(0, 0.8 + hgt + 0.27, 0), P.graniteDark, M.Granite)
	end
	for _, s in DIPPER do
		local p = slab.CFrame * CFrame.new(s[1] * 0.17, s[2] * 0.19, -0.31)
		local star = cyl(
			m,
			"Byeol",
			(p * CFrame.new(0, 0, 0.05)).Position,
			(p * CFrame.new(0, 0, -0.06)).Position,
			0.34,
			rgb(206, 226, 255),
			M.Neon
		)
		deco(star).CastShadow = false
	end
	return m
end

-- 부러진 돌기둥 (열주): kind 1 온전, 2 부러짐, 3 쓰러짐
local function brokenColumn(parent: Instance, ground: Vector3, height: number, kind: number, rng, color: Color3?)
	local m = model(parent, "돌기둥")
	local col = color or rgb(196, 186, 166)
	local y = ground.Y
	block(
		m,
		"Chuchu",
		V3(2.6, 1.0, 2.6),
		CFrame.new(ground + V3(0, 0.3, 0)) * CFrame.Angles(0, rng(0, 1.5), 0),
		jitter(P.graniteDark, rng, 0.05),
		M.Granite
	)
	if kind == 1 then
		cyl(
			m,
			"Gidung",
			V3(ground.X, y + 0.7, ground.Z),
			V3(ground.X, y + height, ground.Z),
			1.7,
			jitter(col, rng, 0.05),
			M.Marble
		)
		block(
			m,
			"Judu",
			V3(2.5, 0.9, 2.5),
			CFrame.new(ground.X, y + height + 0.4, ground.Z) * CFrame.Angles(0, rng(0, 1.5), 0),
			jitter(col, rng, 0.06),
			M.Marble
		)
	elseif kind == 2 then
		local h = height * rng(0.3, 0.6)
		cyl(
			m,
			"Gidung",
			V3(ground.X, y + 0.7, ground.Z),
			V3(ground.X + rng(-0.2, 0.2), y + h, ground.Z + rng(-0.2, 0.2)),
			1.7,
			jitter(col, rng, 0.05),
			M.Marble
		)
	else
		local a = rng(0, TAU)
		local dir = V3(cos(a), 0, sin(a))
		local p0 = V3(ground.X, y + 0.75, ground.Z) + dir * 1.8
		cyl(
			m,
			"Gidung",
			p0,
			p0 + dir * height * rng(0.45, 0.7) + V3(0, rng(-0.3, 0.1), 0),
			1.7,
			jitter(col, rng, 0.05),
			M.Marble
		)
	end
	return m
end

-- 돌 등 (작은 석등): 받침, 기둥, 불집, 지붕돌
local function smallLantern(parent: Instance, ground: Vector3)
	local m = model(parent, "돌등")
	block(m, "Badachim", V3(1.8, 0.8, 1.8), CFrame.new(ground + V3(0, 0.2, 0)), P.graniteDark, M.Granite)
	block(m, "Gidung", V3(0.8, 2.6, 0.8), CFrame.new(ground + V3(0, 1.8, 0)), P.granite, M.Granite)
	local fire = block(m, "Bul", V3(1.2, 1.1, 1.2), CFrame.new(ground + V3(0, 3.65, 0)), rgb(255, 196, 120), M.Neon)
	Kit.light(fire, rgb(255, 190, 120), 14, 1.2)
	Build.pyramid(m, "Jibung", ground + V3(0, 4.2, 0), 2.2, 0.9, 0, P.graniteDark, M.Granite)
	return m
end

local function mesa(parent: Instance, rng)
	local f = folder(parent, "관성대")
	local cliff = model(f, "관성대 벼랑")
	local cx, cz = MESA.x, MESA.z
	local bands = bandStack(rng, 27, 92.8, 3.5, 12)
	table.insert(bands, { 92.8, 96.9, CAPROCK, cap = true, surface = 96 })
	-- 벼랑 (오르막 밖): 띠마다 앞이 들쭉날쭉하게
	strataRing(cliff, cx, cz, 64, 100, bands, 34, rng, { 317, 543 }, { vary = 0.7, jutK = 1.6 })
	-- 오르막 들머리의 벼랑 끝면 (오르막이 벼랑을 파고드는 자리, 오르막 쪽을 본다)
	do
		local a0 = rad(316.2)
		local tx, tz = sin(a0), -cos(a0) -- 각이 줄어드는 쪽 (오르막)
		for _, b in bands do
			local y0, y1 = max(b[1], 29), min(b[2], 96.6)
			if y1 > y0 + 0.4 then
				local mid = mesaPoint(318.5, 83)
				local back = rad(4.5) * 83
				slabAlong(
					cliff,
					mid.X,
					mid.Z,
					-tx,
					-tz,
					-back * 0.5 - rng(0.2, 0.9),
					back * 0.5,
					y0,
					y1,
					23,
					jitter(b[3], rng, 0.05)
				)
			end
		end
	end
	-- 오르막 바깥 축대: 오르막 높이 밑까지만
	local nRamp = 11
	for k = 0, nRamp - 1 do
		local deg = 186 + (k + 0.5) * 128 / nRamp
		local a = rad(deg)
		local ox, oz = cos(a), sin(a)
		local half = math.tan(rad(128 / nRamp) / 2)
		strataRay(cliff, cx + ox * 100, cz + oz * 100, -ox, -oz, 16, bands, function(front)
			return 2 * (100 - front) * half + 1.2
		end, rng, { maxY = rampY(deg) - 0.4, jut = rng(-0.3, 0.5) })
	end
	-- 오르막 안쪽 벽 (오르막에서 꼭대기까지 깎아 세운 벽): 같은 띠 높이로
	local nIn = 12
	for k = 0, nIn - 1 do
		local deg = 186 + (k + 0.5) * 128 / nIn
		local yr = rampY(deg)
		if yr < 94.5 then
			local a = rad(deg)
			local ox, oz = cos(a), sin(a)
			local half = math.tan(rad(128 / nIn) / 2)
			local jut = rng(-0.3, 0.4)
			for _, b in bands do
				local y0, y1 = max(b[1], yr - 1.2), min(b[2], 96.6)
				if y1 > y0 + 0.4 then
					local front = 74 + jut + (if b.cap then 0.5 else 0)
					slabAlong(
						cliff,
						cx + ox * 100,
						cz + oz * 100,
						-ox,
						-oz,
						100 - front,
						100 - 66,
						y0,
						y1,
						2 * front * half + 1.2,
						jitter(b[3], rng, 0.05)
					)
				end
			end
		end
	end
	-- 오르막 들머리 돌문 (이름판)
	do
		local deg = 303
		local a = rad(deg)
		local g = mesaPoint(deg, 81, rampY(deg))
		local tangentDown = V3(-sin(a), 0, cos(a)) -- 각이 커지는 쪽 = 내리막
		local look = face(g, g + tangentDown)
		local gate = model(f, "관성대 돌문")
		for _, s in { -1, 1 } do
			block(gate, "Gidung", V3(1.8, 11, 1.8), look * CFrame.new(s * 7.4, 4.5, 0), P.granite, M.Granite)
		end
		block(gate, "Inbang", V3(17.2, 1.5, 2.0), look * CFrame.new(0, 10.1, 0), P.graniteDark, M.Granite)
		block(gate, "Gat", V3(18.6, 0.7, 2.8), look * CFrame.new(0, 11.2, 0), rgb(92, 88, 84), M.Slate)
		local board = block(gate, "Hyeonpan", V3(6.4, 1.8, 0.35), look * CFrame.new(0, 8.4, -0.9), P.meok, M.Wood)
		Kit.engrave(board, "관성대", "Front,Back")
		block(gate, "Te", V3(7.0, 2.3, 0.3), look * CFrame.new(0, 8.4, -0.75), P.hwang, M.Wood)
	end
	-- 오르막 난간 (바깥 가장자리 돌기둥과 띠돌)과 안쪽 돌등
	local rail = model(f, "관성대 난간")
	local prev = nil
	local n = 15
	for i = 0, n do
		local deg = 299 - i * (299 - 187) / n
		local p = mesaPoint(deg, 88.4, rampY(deg))
		block(rail, "Nangangidung", V3(0.9, 3.2, 0.9), CFrame.new(p + V3(0, 0.9, 0)), P.granite, M.Granite)
		local t = p + V3(0, 2.4, 0)
		if prev then
			beam(rail, "Ttidol", prev, t, 0.5, 0.45, P.graniteDark, M.Granite)
		end
		prev = t
	end
	for _, deg in { 285, 255, 225, 195 } do
		smallLantern(f, mesaPoint(deg, 75.6, rampY(deg)))
	end
	-- 꼭대기 천문 옛터 (반지름 40~70)
	local topY = MESA.height
	local obs = folder(f, "관성대 꼭대기")
	armillary(obs, mesaPoint(0, 54, topY))
	starTower(obs, mesaPoint(118, 56, topY), mesaPoint(118, 56, topY) + V3(0, 0, 10), rng)
	for i, deg in { 166, 204, 62, 292 } do
		local g = mesaPoint(deg, 47, topY)
		starTablet(obs, g, V3(MESA.x, topY, MESA.z), rng, i == 3)
	end
	-- 규표: 그림자 재는 돌 막대와 바닥 눈금돌
	do
		local g = mesaPoint(330, 52, topY)
		local tg = V3(-sin(rad(330)), 0, cos(rad(330)))
		local gm = model(obs, "규표")
		block(gm, "Pyo", V3(1.3, 12, 1.3), CFrame.new(g + V3(0, 5.6, 0)), P.granite, M.Granite)
		block(
			gm,
			"Hoengmok",
			V3(3.4, 0.6, 0.8),
			face(g + V3(0, 11.8, 0), g + V3(0, 11.8, 0) + tg),
			P.graniteDark,
			M.Granite
		)
		block(
			gm,
			"Gyu",
			V3(1.8, 0.45, 15),
			face(g + tg * 8 + V3(0, 0.12, 0), g + tg * 20 + V3(0, 0.12, 0)),
			rgb(176, 168, 150),
			M.Granite
		)
	end
	-- 오르막 끝에서 가운데로 가는 박석 길 (낮은 판)
	for k = 0, 2 do
		local d = 68 - k * 9.6
		local g = mesaPoint(185, d, topY)
		block(
			obs,
			"Bakseok",
			V3(5.4, 0.45, 9.2),
			face(g + V3(0, 0.12, 0), V3(MESA.x, topY, MESA.z)),
			rgb(168, 160, 146),
			M.Granite
		)
	end
	-- 가장자리 부러진 열주
	local colors = { rgb(196, 186, 166), rgb(184, 172, 150) }
	for k = 0, 17 do
		local deg = k * 20 + 5
		if abs(((deg - 185 + 180) % 360) - 180) > 14 then
			local kind = if rng(0, 1) < 0.4 then 1 elseif rng(0, 1) < 0.6 then 2 else 3
			brokenColumn(obs, mesaPoint(deg, 66.5, topY), rng(9.5, 11.5), kind, rng, colors[k % 2 + 1])
		end
	end
	-- 꼭대기 마른 풀과 덤불
	for _ = 1, 8 do
		local deg, d = rng(0, 360), rng(42, 69)
		local p = mesaPoint(deg, d)
		if abs(((deg - 185 + 180) % 360) - 180) > 8 then
			if rng(0, 1) < 0.5 then
				tuft(obs, p.X, p.Z, rng)
			else
				dryShrub(obs, p.X, p.Z, rng, rng(1.6, 2.6))
			end
		end
	end
	return f
end

-- 한해 ---------------------------------------------------------------------------------
-- 모래 언덕 물결은 WIND 쪽으로 오르내리고 (Land 의 dunes: x*0.83 + z*0.55), 등성이는 CREST 쪽으로 달린다.
-- 바람 깎인 바위는 긴 쪽이 바람결: 바람 오는 쪽(머리)이 뭉툭하고 가는 쪽(꼬리)이 가늘다. 모래 더미는 바람 그늘에 쌓인다.
-- 흩뿌리는 것은 길과 관성대·옛터·녹주·소금벌을 비켜 간다 (desertFree).
local WIND = V3(0.83, 0, 0.55).Unit
local CREST = V3(-WIND.Z, 0, WIND.X)
local BONE = M.Limestone
local RUIN_STONE = rgb(206, 180, 136) -- 침사국 돌 (모래빛 사암)
local RUIN_DARK = rgb(168, 138, 98)

local function dist2(x: number, z: number, c): number
	return (x - c.x) ^ 2 + (z - c.z) ^ 2
end

local function desertFree(x: number, z: number, pad: number): boolean
	if regionId(x, z) ~= "desert" then
		return false
	end
	if not clearOf(x, z, pad) or roadDist(x, z) < 8 + pad then
		return false
	end
	if
		dist2(x, z, MESA) < (120 + pad) ^ 2
		or dist2(x, z, RUINS) < (108 + pad) ^ 2
		or dist2(x, z, OASIS) < (75 + pad) ^ 2
	then
		return false
	end
	if Land.polyDist(x, z, Land.CANYON, 60) < 50 then
		return false
	end
	local g = H(x, z)
	return g > 5 and g < 60 and relief(x, z, 2 + pad) < 2.6 + pad * 0.4
end

-- 모래 더미 (쐐기): foot 에서 out 쪽으로 length 만큼 가며 낮아진다. foot 쪽 높이는 foot.Y + h
local function drift(parent: Instance, foot: Vector3, out: Vector3, width: number, length: number, h: number, rng)
	local far = foot + out * length
	local bottom = min(H(far.X, far.Z), H(foot.X, foot.Z)) - 0.8
	local top = foot.Y + h
	local c = (foot + far) / 2
	return wedge(
		parent,
		"Morae",
		V3(width, top - bottom, length),
		face(V3(c.X, (top + bottom) / 2, c.Z), far),
		jitter(C.sand, rng, 0.03),
		M.Sand
	)
end

-- 바람등 (바람에 깎인 긴 바위 등성이): 켜 셋, 위 켜일수록 짧고 좁다. 켜마다 몸(네모)과 꼬리(쐐기, 바람 가는 쪽으로 낮아진다)
local function yardang(parent: Instance, x: number, z: number, rng)
	local m = model(parent, "바람등")
	local L, W = rng(24, 38), rng(7, 10)
	local dir = (WIND + CREST * rng(-0.15, 0.15)).Unit
	local y = lowAt(x, z, L * 0.5) - 1
	local frame = face(V3(x, 0, z), V3(x, 0, z) + dir) -- 앞(-Z)이 바람 가는 쪽, 뒤(+Z)가 머리
	local k = floor(rng(0, #BANDS))
	for i = 1, 3 do
		local len = L * (1 - 0.26 * (i - 1))
		local wid = W * (1 - 0.17 * (i - 1))
		local th = rng(3, 4.2) + (if i == 1 then 1.2 else 0)
		local head = L / 2 - (i - 1) * rng(0.5, 1.4)
		local bodyLen = len * 0.58
		local tailLen = len - bodyLen
		local col = jitter(BANDS[(k + i) % #BANDS + 1], rng, 0.05)
		local yaw = CFrame.Angles(0, rng(-0.04, 0.04), 0)
		block(
			m,
			"Mom",
			V3(wid, th, bodyLen),
			frame * CFrame.new(0, y + th / 2, head - bodyLen / 2) * yaw,
			col,
			M.Sandstone
		)
		wedge(
			m,
			"Kkori",
			V3(wid * 0.92, th, tailLen),
			frame * CFrame.new(0, y + th / 2, head - bodyLen - tailLen / 2 + 0.05) * yaw,
			col,
			M.Sandstone
		)
		y += th - 0.15
	end
	return m
end

-- 버섯바위: 넓은 밑동, 잘록한 허리, 넓고 납작한 갓 (갓 위에 옅은 갓바위 한 켜), 떨어진 조각, 바람 그늘 모래 더미
local function mushroomRock(parent: Instance, x: number, z: number, rng)
	local m = model(parent, "버섯바위")
	local h = rng(9, 14)
	local y = lowAt(x, z, 3) - 0.8
	local k = floor(rng(0, #BANDS))
	local w0 = rng(5, 7)
	block(
		m,
		"Mitdong",
		V3(w0, h * 0.4, w0 * rng(0.8, 1)),
		CFrame.new(x, y + h * 0.2, z) * CFrame.Angles(0, rng(0, TAU), 0),
		jitter(BANDS[k % #BANDS + 1], rng, 0.05),
		M.Sandstone
	)
	local neck = h * 0.45
	block(
		m,
		"Heori",
		V3(w0 * 0.52, neck + 0.4, w0 * 0.48),
		CFrame.new(x + rng(-0.3, 0.3), y + h * 0.4 + neck / 2, z + rng(-0.3, 0.3))
			* CFrame.Angles(rng(-0.05, 0.05), rng(0, TAU), rng(-0.05, 0.05)),
		jitter(BANDS[(k + 1) % #BANDS + 1], rng, 0.05),
		M.Sandstone
	)
	local capW = w0 * rng(1.5, 1.85)
	local capCf = CFrame.new(x, y + h * 0.95, z) * CFrame.Angles(rng(-0.1, 0.1), rng(0, TAU), rng(-0.1, 0.1))
	block(
		m,
		"Gat",
		V3(capW, h * 0.2, capW * rng(0.75, 0.95)),
		capCf,
		jitter(BANDS[(k + 2) % #BANDS + 1], rng, 0.05),
		M.Sandstone
	)
	block(
		m,
		"Gatbawi",
		V3(capW * 0.8, h * 0.14, capW * 0.66),
		capCf * CFrame.new(rng(-0.5, 0.5), h * 0.16, rng(-0.5, 0.5)) * CFrame.Angles(0, rad(40), 0),
		jitter(CAPROCK, rng, 0.04),
		M.Sandstone
	)
	local a = rng(0, TAU)
	boulder(m, x + cos(a) * (w0 + 1.2), z + sin(a) * (w0 + 1.2), rng(1.8, 2.6), rng, BANDS[(k + 2) % #BANDS + 1])
	local foot = V3(x, 0, z) + WIND * w0 * 0.35
	drift(m, V3(foot.X, H(foot.X, foot.Z), foot.Z), WIND, w0 * 0.8, rng(5, 7.5), rng(1.4, 2.2), rng)
	return m
end

-- 바람구멍 바위: 바람에 뚫린 돌다리. 길(along 쪽으로 달린다)을 가로질러 다리 둘이 선다
local function rockArch(parent: Instance, cx: number, cz: number, along: Vector3, rng)
	local m = model(parent, "바람구멍바위")
	local side = V3(-along.Z, 0, along.X)
	local span, legW, thick = 18, 8, 7
	local off = span / 2 + legW / 2
	local legs = {}
	local gMax = H(cx, cz)
	for _, s in { -1, 1 } do
		local p = V3(cx, 0, cz) + side * s * off
		gMax = max(gMax, highAt(p.X, p.Z, 3))
		table.insert(legs, { p = p, g = lowAt(p.X, p.Z, 4.5), s = s })
	end
	local yTop = gMax + 20
	local yUnder = yTop - 6
	local k = floor(rng(0, #BANDS))
	for _, leg in legs do
		local look = face(V3(leg.p.X, 0, leg.p.Z), V3(leg.p.X, 0, leg.p.Z) + along)
		-- 다리: 띠 셋, 아래가 넓고 띠마다 조금씩 들고 난다 (바깥쪽이 더 깎였다)
		local y0 = leg.g - 1.5
		local cuts = { 0, rng(0.3, 0.42), rng(0.62, 0.74), 1 }
		for j = 1, 3 do
			local ya, yb = y0 + (yUnder - y0) * cuts[j], y0 + (yUnder - y0) * cuts[j + 1] + 0.3
			local wj = legW + 2.2 - j * 0.8 + rng(-0.4, 0.4)
			block(
				m,
				"Dari",
				V3(wj, yb - ya, thick + 1.6 - j * 0.45),
				look
					* CFrame.new(-leg.s * (j - 1) * 0.35, (ya + yb) / 2, rng(-0.3, 0.3))
					* CFrame.Angles(0, rng(-0.07, 0.07), 0),
				jitter(BANDS[(k + j) % #BANDS + 1], rng, 0.05),
				M.Sandstone
			)
		end
		for _ = 1, 2 do
			local a = rng(0, TAU)
			local bx, bz = leg.p.X + cos(a) * (legW * 0.7 + 2), leg.p.Z + sin(a) * (legW * 0.7 + 2)
			if roadDist(bx, bz) > 5 then
				boulder(m, bx, bz, rng(2, 3.4), rng, BANDS[(k + 2) % #BANDS + 1])
			end
		end
	end
	-- 돌다리 (두 토막이 가운데에서 조금 솟는다), 갓바위, 안쪽 귀 (둥글게 깎인 자리)
	local c = V3(cx, 0, cz)
	local look = face(c, c + along)
	for _, s in { -1, 1 } do
		block(
			m,
			"Hongye",
			V3(span / 2 + legW + 1, 6 - (s + 1) * 0.3, thick + s * 0.3),
			look * CFrame.new(s * (span / 4 + legW / 2 - 0.5), yTop - 3, 0) * CFrame.Angles(0, 0, rad(s * 3)),
			jitter(BANDS[(k + 4) % #BANDS + 1], rng, 0.05),
			M.Sandstone
		)
	end
	block(
		m,
		"Gatbawi",
		V3(span + legW * 1.1, 2.0, thick - 1),
		look * CFrame.new(rng(-1, 1), yTop + 0.7, 0) * CFrame.Angles(0, rng(-0.05, 0.05), rad(rng(-2, 2))),
		jitter(CAPROCK, rng, 0.04),
		M.Sandstone
	)
	block(
		m,
		"Gatbawi",
		V3(span * 0.6, 1.4, thick - 2.2),
		look * CFrame.new(rng(-3, 3), yTop + 2.2, rng(-0.4, 0.4)) * CFrame.Angles(0, rng(-0.1, 0.1), 0),
		jitter(CAPROCK, rng, 0.05),
		M.Sandstone
	)
	for _, s in { -1, 1 } do
		local R = c + side * s * (span / 2) + V3(0, yUnder + 0.1, 0)
		Build.rightTri(
			m,
			"Gwi",
			R,
			R - V3(0, 7.5, 0),
			R - side * s * 6.5,
			thick,
			nil,
			jitter(BANDS[(k + 1) % #BANDS + 1], rng, 0.05),
			M.Sandstone
		)
	end
	return m
end

-- 큰 요수 뼈: 꼬리는 모래에 묻히고 등뼈가 솟았다가 목에서 다시 내려와 머리뼈가 모래 위에 눕는다.
-- 갈비 여덟 쌍 (몇은 부러져 끝 토막이 모래에 떨어졌다), 머리뼈 (뿔 둘, 벌어진 아래턱, 엄니), 앞다리 뼈, 골반
local function beastBones(parent: Instance, cx: number, cz: number, dir: Vector3, s: number, rng)
	local m = model(parent, "요수 뼈")
	local side = V3(-dir.Z, 0, dir.X)
	local L = 58 * s
	local up = Vector3.yAxis
	local function spine(t: number): Vector3
		local p = V3(cx, 0, cz) + dir * (t - 0.5) * L
		local lift
		if t < 0.24 then
			lift = -1.2 + 6.2 * (t / 0.24)
		elseif t < 0.7 then
			lift = 5 + 2.6 * sin((t - 0.24) / 0.46 * math.pi)
		else
			lift = 5 - 3.4 * ((t - 0.7) / 0.3)
		end
		return V3(p.X, H(p.X, p.Z) + lift * s, p.Z)
	end
	local function ground(p: Vector3, lift: number): Vector3
		return V3(p.X, H(p.X, p.Z) + lift, p.Z)
	end
	-- 등뼈 마디와 가시 돌기
	local n = 20
	for i = 0, n - 1 do
		local t = 0.03 + i * 0.84 / (n - 1)
		local w = (if t > 0.7 then 1.3 elseif t < 0.24 then 0.9 + t * 2 else 1.7) * s
		beam(m, "Cheokchu", spine(t - 0.016), spine(t + 0.016), w, w * 0.9, jitter(C.bone, rng, 0.04), BONE)
		if t > 0.26 and t < 0.68 and i % 2 == 0 then
			local p = spine(t)
			beam(m, "Dolgi", p, p + (up * 2.6 - dir * 0.9) * s, 0.9 * s, 0.5 * s, jitter(C.boneDark, rng, 0.04), BONE)
		end
	end
	-- 갈비
	local nr = 8
	for i = 1, nr do
		local t = 0.31 + (i - 1) * 0.34 / (nr - 1)
		local P = spine(t)
		local f = (0.78 + 0.22 * sin(math.pi * (i - 0.5) / nr)) * s
		local hgt = P.Y - H(P.X, P.Z)
		for _, sg in { -1, 1 } do
			local out = side * sg
			local col = jitter(C.bone, rng, 0.05)
			local w = 0.8 * s
			local q0 = P + out * 0.6 * s
			local q1 = P + out * 3.8 * f + up * 0.9 * f - dir * 0.4 * f
			local q2 = P + out * 6.4 * f - up * hgt * 0.42 - dir * 1.0 * f
			local q3 = ground(P + out * 7.0 * f - dir * 1.3 * f, -0.7)
			beam(m, "Galbi", q0, q1, w, w * 0.7, col, BONE)
			if rng(0, 1) < 0.2 then
				-- 부러진 갈비: 끝 토막이 모래에 떨어졌다
				beam(m, "Galbi", q1, q1:Lerp(q2, 0.45), w, w * 0.7, col, BONE)
				local a = ground(q3 + out * 1.2, 0.25)
				local b = ground(a + (out + dir * rng(-0.8, 0.8)).Unit * 3.6 * f, 0.25)
				beam(m, "Tomak", a, b, w, w * 0.7, col, BONE)
			else
				beam(m, "Galbi", q1, q2, w, w * 0.7, col, BONE)
				beam(m, "Galbi", q2, q3, w * 0.9, w * 0.65, col, BONE)
			end
		end
	end
	-- 골반 (꼬리 쪽, 반쯤 묻혔다)
	do
		local p = spine(0.24) - up * 0.3 * s
		local look = face(p, p + dir)
		for _, sg in { -1, 1 } do
			block(
				m,
				"Golban",
				V3(3.6, 0.7, 3.0) * s,
				look * CFrame.new(sg * 1.9 * s, -0.4 * s, 0) * CFrame.Angles(rad(rng(-10, 10)), 0, rad(sg * 28)),
				jitter(C.boneDark, rng, 0.04),
				BONE
			)
		end
	end
	-- 앞다리 뼈: 갈비 곁에 하나씩 누웠다 (긴 뼈 + 두 끝 마디)
	for _, sg in { -1, 1 } do
		local base = spine(0.62) + side * sg * 9 * s
		local a = rng(0, TAU)
		local d = V3(cos(a), 0, sin(a))
		local p0 = ground(base - d * 3.6 * s, 0.35 * s)
		local p1 = ground(base + d * 3.6 * s, 0.35 * s)
		beam(m, "Darippyeo", p0, p1, 1.0 * s, 0.9 * s, jitter(C.bone, rng, 0.04), BONE)
		ball(m, "Madi", p0, 1.7 * s, jitter(C.boneDark, rng, 0.04), BONE)
		ball(m, "Madi", p1, 1.5 * s, jitter(C.boneDark, rng, 0.04), BONE)
	end
	-- 머리뼈 (앞 -Z 가 dir 쪽, 조금 기울어 모래에 앉았다)
	local hp = spine(0.94)
	hp = V3(hp.X, H(hp.X, hp.Z) - 0.6 * s, hp.Z)
	local F = face(hp, hp + dir) * CFrame.Angles(0, 0, rad(rng(-14, 14)))
	local function at3(x: number, y: number, z: number): Vector3
		return F:PointToWorldSpace(V3(x, y, z) * s)
	end
	local function put(name: string, size: Vector3, x: number, y: number, z: number, color: Color3)
		return block(m, name, size * s, F * CFrame.new(x * s, y * s, z * s), color, BONE)
	end
	put("Meori", V3(4.4, 3.4, 4.6), 0, 1.5, 0, jitter(C.bone, rng, 0.03))
	put("Nunsseop", V3(4.8, 1.0, 1.5), 0, 2.8, -1.9, jitter(C.bone, rng, 0.03))
	put("Judung", V3(2.9, 2.0, 4.8), 0, 1.0, -4.4, jitter(C.bone, rng, 0.03))
	put("Kkeut", V3(2.3, 1.7, 1.8), 0, 0.85, -7.2, jitter(C.boneDark, rng, 0.03))
	for _, sg in { -1, 1 } do
		put("Nunkumeong", V3(1.2, 1.1, 1.4), sg * 1.85, 2.0, -1.7, rgb(64, 54, 44))
		local h0, h1 = at3(sg * 1.9, 2.9, 0.6), at3(sg * 3.0, 4.2, 2.6)
		local h2, h3 = at3(sg * 3.4, 4.6, 5.0), at3(sg * 2.8, 3.9, 6.8)
		beam(m, "Ppul", h0, h1, 1.0 * s, 1.0 * s, C.boneDark, BONE)
		beam(m, "Ppul", h1, h2, 0.8 * s, 0.8 * s, C.boneDark, BONE)
		beam(m, "Ppul", h2, h3, 0.55 * s, 0.55 * s, C.boneDark, BONE)
		beam(m, "Teok", at3(sg * 1.8, 0.35, 0.4), at3(sg * 2.1, 0.3, -6.0), 0.7 * s, 0.8 * s, C.bone, BONE)
		beam(m, "Eomni", at3(sg * 1.0, 0.7, -6.8), at3(sg * 1.4, 2.4, -8.6), 0.5 * s, 0.5 * s, C.bone, BONE)
	end
	-- 꼬리 끝을 덮은 모래
	drift(m, ground(spine(0.08), 0), -dir, 5 * s, 6 * s, 1.6 * s, rng)
	return m
end

-- 작은 뼈 무더기: 모래에서 솟은 한쪽 갈비 넷, 등뼈 마디 셋, 작은 머리뼈
local function boneRemnant(parent: Instance, x: number, z: number, rng)
	local m = model(parent, "뼈 무더기")
	local a = rng(0, TAU)
	local dir = V3(cos(a), 0, sin(a))
	local side = V3(-dir.Z, 0, dir.X)
	local function ground(p: Vector3, lift: number): Vector3
		return V3(p.X, H(p.X, p.Z) + lift, p.Z)
	end
	local c = V3(x, 0, z)
	for i = 1, 4 do
		local base = ground(c + dir * (i - 2.5) * 2.2, -0.4)
		local top = base + side * 2.2 + V3(0, 3.0 - abs(i - 2.5) * 0.5, 0)
		local tip = ground(c + dir * (i - 2.5) * 2.4 + side * 4.4, -0.5)
		local col = jitter(C.bone, rng, 0.05)
		beam(m, "Galbi", base, top, 0.6, 0.45, col, BONE)
		beam(m, "Galbi", top, tip, 0.55, 0.42, col, BONE)
	end
	for i = 1, 3 do
		local p = ground(c - side * 0.8 + dir * (i - 2) * 2.4, 0.3)
		beam(m, "Cheokchu", p - dir * 0.6, p + dir * 0.6, 1.1, 0.9, jitter(C.boneDark, rng, 0.05), BONE)
	end
	local hp = ground(c + dir * 7 - side * 1.5, 0.1)
	local F = face(hp, hp + dir) * CFrame.Angles(0, 0, rad(rng(-25, 25)))
	block(m, "Meori", V3(2.2, 1.6, 2.4), F * CFrame.new(0, 0.5, 0), jitter(C.bone, rng, 0.04), BONE)
	block(m, "Judung", V3(1.4, 1.1, 2.4), F * CFrame.new(0, 0.3, -2.2), jitter(C.bone, rng, 0.04), BONE)
	beam(
		m,
		"Ppul",
		F:PointToWorldSpace(V3(0.8, 1.1, 0.4)),
		F:PointToWorldSpace(V3(1.8, 2.4, 2.0)),
		0.5,
		0.5,
		C.boneDark,
		BONE
	)
	return m
end

-- 모래에 묻힌 대상: 기운 수레 (한쪽 바퀴가 묻혔다), 거의 묻힌 수레 (바퀴와 끌채 끝만), 짐 상자·자루·독, 쓰러진 깃대
local function buriedCaravan(parent: Instance, cx: number, cz: number, dir: Vector3, rng)
	local m = model(parent, "묻힌 대상")
	local side = V3(-dir.Z, 0, dir.X)
	local c = V3(cx, H(cx, cz), cz)
	local cartCf = face(c - V3(0, 1.3, 0), c - V3(0, 1.3, 0) + dir) * CFrame.Angles(rad(-8), 0, rad(16))
	Build.cart(m, cartCf)
	-- 덮개 친 짐과 묶은 줄
	local load = cartCf * CFrame.new(0.1, 3.0, 0.3)
	block(m, "Jim", V3(3.2, 1.6, 4.2), load, jitter(C.felt, rng, 0.04), M.Fabric)
	for _, z in { -1.1, 1.1 } do
		block(m, "Jul", V3(3.3, 1.7, 0.18), load * CFrame.new(0, 0, z), C.straw, M.Fabric)
	end
	-- 찢어진 덮개 천이 옆으로 늘어졌다
	block(
		m,
		"Cheon",
		V3(0.2, 2.2, 3.6),
		load * CFrame.new(1.9, -1.0, 0) * CFrame.Angles(0, 0, rad(-14)),
		jitter(C.madder, rng, 0.05),
		M.Fabric
	)
	-- 낮은 쪽 옆구리와 앞을 묻은 모래
	local low = cartCf:PointToWorldSpace(V3(-2.4, 0, 0))
	drift(m, V3(low.X, H(low.X, low.Z), low.Z), -side, 6.5, 6, 2.2, rng)
	drift(m, c + dir * 2.8, dir, 4, 5, 1.6, rng)
	-- 거의 묻힌 둘째 수레: 바퀴 반쪽과 들린 끌채
	do
		local p = c + side * 8 - dir * 3
		local g = H(p.X, p.Z)
		local hub = V3(p.X, g - 0.3, p.Z)
		cyl(m, "Bakwi", hub - side * 0.15, hub + side * 0.15, 3.4, P.woodDark, M.Wood)
		cyl(m, "Tong", hub - side * 0.3, hub + side * 0.3, 0.7, P.meok, M.Metal)
		local a = V3(p.X, g - 0.5, p.Z) + dir * 2
		beam(m, "Kkeulchae", a, a + dir * 3.5 + V3(0, 2.2, 0), 0.3, 0.3, P.wood, M.Wood)
	end
	-- 상자·자루·독 (모래에 반쯤)
	local spots = {
		{ -4.5, 3.5, "box" },
		{ -6.2, 0.8, "box" },
		{ 3.5, 5.0, "sack" },
		{ 4.6, 3.0, "sack" },
		{ -3.2, -4.6, "jar" },
		{ 5.2, -3.8, "jar" },
		{ 1.0, 7.4, "lid" },
	}
	for _, sp in spots do
		local p = c + side * sp[1] + dir * sp[2]
		local g = H(p.X, p.Z)
		local kind = sp[3]
		local tilt = CFrame.Angles(rng(-0.3, 0.3), rng(0, TAU), rng(-0.3, 0.3))
		if kind == "box" then
			block(
				m,
				"Sangja",
				V3(2.2, 1.8, 2.6),
				CFrame.new(p.X, g + 0.3, p.Z) * tilt,
				jitter(P.wood, rng, 0.08),
				M.WoodPlanks
			)
		elseif kind == "lid" then
			block(
				m,
				"Ttukkeong",
				V3(2.4, 0.25, 2.8),
				CFrame.new(p.X, g + 0.05, p.Z) * CFrame.Angles(rng(-0.1, 0.1), rng(0, TAU), rng(-0.1, 0.1)),
				jitter(P.wood, rng, 0.08),
				M.WoodPlanks
			)
		elseif kind == "sack" then
			block(
				m,
				"Jaru",
				V3(1.6, 1.2, 2.2),
				CFrame.new(p.X, g + 0.25, p.Z) * tilt,
				jitter(C.straw, rng, 0.08),
				M.Fabric
			)
		else
			local jc = V3(p.X, g + 0.2, p.Z)
			local col = jitter(rgb(120, 76, 48), rng, 0.08)
			ball(m, "Dok", jc, 1.9, col, M.SmoothPlastic).CastShadow = false
			local na = rng(0, TAU)
			local nd = V3(cos(na) * 0.6, 0.6, sin(na) * 0.6)
			cyl(m, "Mok", jc + nd * 0.9, jc + nd * 1.4, 1.0, col, M.SmoothPlastic)
		end
	end
	-- 쓰러진 깃대와 해진 기
	do
		local p0 = c - side * 5 + dir * 7
		local a = V3(p0.X, H(p0.X, p0.Z) + 0.15, p0.Z)
		local b0 = a + (dir + side * 0.6).Unit * 8
		local b = V3(b0.X, H(b0.X, b0.Z) + 0.15, b0.Z)
		beam(m, "Gitdae", a, b, 0.3, 0.3, P.woodDark, M.Wood)
		local q = b:Lerp(a, 0.12)
		block(
			m,
			"Gi",
			V3(2.4, 0.08, 1.6),
			face(q + V3(0, 0.1, 0), q + side) * CFrame.Angles(0, 0, rad(4)),
			jitter(C.ochreCloth, rng, 0.06),
			M.Fabric
		)
	end
	return m
end

-- 모래에 묻힌 옛 기둥 (침사국 둘레): 1 기운 기둥과 주두, 2 주두와 짧은 몸만, 3 기둥 둘과 들보 (모래 위로 나온 문틀)
local function sandPillar(parent: Instance, x: number, z: number, kind: number, rng)
	local m = model(parent, "묻힌 기둥")
	local g = lowAt(x, z, 2)
	local col = jitter(RUIN_STONE, rng, 0.05)
	if kind == 1 then
		local a = rng(0, TAU)
		local lean = V3(cos(a), 0, sin(a)) * math.tan(rad(rng(8, 22)))
		local h = rng(6, 10)
		local base = V3(x, g - 3, z)
		local top = base + (Vector3.yAxis + lean).Unit * (h + 3)
		cyl(m, "Gidung", base, top, 2.6, col, M.Sandstone)
		local cap = CFrame.new(top) * CFrame.Angles(lean.Z * 0.9, rng(0, TAU), -lean.X * 0.9)
		block(m, "Judu", V3(3.8, 1.2, 3.8), cap, jitter(RUIN_DARK, rng, 0.05), M.Sandstone)
	elseif kind == 2 then
		local h = rng(1.2, 2.6)
		cyl(m, "Gidung", V3(x, g - 1, z), V3(x, g + h, z), 2.6, col, M.Sandstone)
		block(
			m,
			"Judu",
			V3(3.8, 1.2, 3.8),
			CFrame.new(x, g + h + 0.4, z) * CFrame.Angles(rng(-0.12, 0.12), rng(0, TAU), rng(-0.12, 0.12)),
			jitter(RUIN_DARK, rng, 0.05),
			M.Sandstone
		)
	else
		local a = rng(0, TAU)
		local d = V3(cos(a), 0, sin(a))
		local gl = math.huge
		for _, s in { -1, 1 } do
			local p = V3(x, 0, z) + d * s * 4.5
			gl = min(gl, lowAt(p.X, p.Z, 1.5))
		end
		local top = gl + rng(4.5, 6.5)
		for _, s in { -1, 1 } do
			local p = V3(x, 0, z) + d * s * 4.5
			cyl(m, "Gidung", V3(p.X, gl - 2, p.Z), V3(p.X, top, p.Z), 2.4, jitter(RUIN_STONE, rng, 0.05), M.Sandstone)
		end
		local mid = V3(x, top + 0.8, z)
		block(
			m,
			"Deulbo",
			V3(2.6, 1.6, 13),
			face(mid, mid + d) * CFrame.Angles(rad(rng(-4, 4)), 0, 0),
			jitter(RUIN_DARK, rng, 0.05),
			M.Sandstone
		)
		-- 문틀 밑으로 불어 든 모래
		drift(m, V3(x, H(x, z), z), V3(-d.Z, 0, d.X), 7, 6, 1.8, rng)
	end
	return m
end

-- 모래에 반쯤 묻힌 경계 비석 (거북 받침): 옛 나라 이름이 새겨져 있다. 앞(-Z)이 toward 쪽
local function borderStele(parent: Instance, x: number, z: number, toward: Vector3, rng)
	local m = model(parent, "경계 비석")
	local g = lowAt(x, z, 3)
	local look = face(V3(x, g, z), toward)
	block(
		m,
		"Gwibu",
		V3(4.6, 2.4, 6.4),
		look * CFrame.new(0, 0.2, 0.4) * CFrame.Angles(rad(3), 0, rad(-4)),
		jitter(RUIN_DARK, rng, 0.05),
		M.Sandstone
	)
	block(
		m,
		"Gwibumeori",
		V3(1.8, 1.4, 2.0),
		look * CFrame.new(0, 0.6, -3.6) * CFrame.Angles(rad(-10), 0, 0),
		jitter(RUIN_DARK, rng, 0.05),
		M.Sandstone
	)
	local slab = block(
		m,
		"Bimom",
		V3(3.4, 7.4, 1.1),
		look * CFrame.new(0, 4.4, 0.6) * CFrame.Angles(rad(-6), 0, rad(8)),
		jitter(RUIN_STONE, rng, 0.04),
		M.Sandstone
	)
	Kit.engrave(slab, "침사국", "Front", true)
	return m
end

-- 길 곁 돌무더기 길표: 사막을 지나는 길을 따라 every 마다 (길 양옆을 번갈아)
local function roadCairns(parent: Instance, every: number, rng)
	local n = 0
	for _, road in Land.ROADS do
		for i = 1, #road - 1 do
			local a, b = road[i], road[i + 1]
			local dx, dz = b[1] - a[1], b[2] - a[2]
			local len = sqrt(dx * dx + dz * dz)
			local ux, uz = dx / len, dz / len
			local t = every * 0.5
			while t < len do
				n += 1
				local s = if n % 2 == 0 then 1 else -1
				local x, z = a[1] + ux * t - uz * s * 7, a[2] + uz * t + ux * s * 7
				if
					regionId(x, z) == "desert"
					and clearOf(x, z, 3)
					and dist2(x, z, MESA) > 125 ^ 2
					and dist2(x, z, RUINS) > 100 ^ 2
					and dist2(x, z, OASIS) > 70 ^ 2
				then
					cairn(parent, x, z, rng, rgb(168, 132, 96))
				end
				t += every
			end
		end
	end
end

-- 관성대에서 옛터로 가는 길 (Land.ROADS 의 14 번째 길 끝 토막)
local RUIN_ROAD_A, RUIN_ROAD_B = V3(-900, 0, 850), V3(-1100, 0, 1010)

local function desert(parent: Instance, rng)
	local f = folder(parent, "한해")
	local along = (RUIN_ROAD_B - RUIN_ROAD_A).Unit
	local across = V3(-along.Z, 0, along.X)
	-- 바람구멍 바위: 옛터 가는 길을 가로지른다
	local archAt = RUIN_ROAD_A + along * 160
	rockArch(f, archAt.X, archAt.Z, along, rng)
	-- 큰 요수 뼈: 길 서쪽 골 (등성이를 따라 눕는다)
	beastBones(f, -1000, 868, V3(-0.49, 0, 0.87).Unit, 1, rng)
	-- 묻힌 대상: 녹주 가는 길 곁 골
	buriedCaravan(f, -978, 800, V3(-0.66, 0, -0.75).Unit, rng)
	-- 경계 비석: 옛터 가는 길 곁 (길을 본다)
	local steleAt = RUIN_ROAD_A + along * 205 - across * 11
	borderStele(f, steleAt.X, steleAt.Z, steleAt + across * 11, rng)
	local box = { -1460, -440, 600, 1500 }
	local taken = {
		{ -1000, 868, 40 },
		{ -978, 800, 24 },
		{ archAt.X, archAt.Z, 34 },
		{ steleAt.X, steleAt.Z, 12 },
	}
	local function pick(count: number, spacing: number, pad: number, accept: ((number, number) -> boolean)?)
		return scatter(rng, count, box, spacing, function(x, z)
			return desertFree(x, z, pad) and (accept == nil or accept(x, z))
		end, taken)
	end
	local function reserve(p, r: number)
		table.insert(taken, { p[1], p[2], r })
	end
	-- 바람 깎인 바위들
	for _, p in
		pick(5, 120, 12, function(x, z)
			return relief(x, z, 10) < 4
		end)
	do
		yardang(f, p[1], p[2], rng)
		reserve(p, 24)
	end
	for _, p in pick(4, 110, 8) do
		mushroomRock(f, p[1], p[2], rng)
		reserve(p, 16)
	end
	-- 옛 나라의 흔적: 옛터 둘레 (125~270) 에 묻힌 기둥
	local kinds = { 1, 2, 3, 1, 2, 1, 3, 2 }
	for i, p in
		pick(8, 45, 6, function(x, z)
			local d = dist2(x, z, RUINS)
			return d > 125 ^ 2 and d < 270 ^ 2
		end)
	do
		sandPillar(f, p[1], p[2], kinds[i], rng)
		reserve(p, 14)
	end
	-- 작은 뼈 무더기
	for _, p in pick(2, 200, 6) do
		boneRemnant(f, p[1], p[2], rng)
		reserve(p, 12)
	end
	-- 마른 나무, 사막 덤불, 마른 풀, 바위
	for _, p in pick(5, 70, 3) do
		deadTree(f, p[1], p[2], rng, {
			height = rng(6, 10),
			color = if rng(0, 1) < 0.6 then C.deadwoodPale else C.deadwood,
		})
	end
	local palettes = {
		{ C.sageDark, C.sage, C.dustLeaf },
		{ rgb(140, 132, 90), C.sage, rgb(160, 150, 104) },
		{ rgb(150, 116, 90), rgb(128, 110, 84), C.sageDark }, -- 붉게 마른 위성류
	}
	for _, p in pick(24, 22, 1) do
		dryShrub(f, p[1], p[2], rng, rng(1.8, 3.4), palettes[floor(rng(1, #palettes + 0.99))])
	end
	for _, p in pick(14, 18, 0) do
		tuft(f, p[1], p[2], rng)
	end
	for _, p in pick(9, 40, 2) do
		boulder(f, p[1], p[2], rng(1.6, 3.8), rng, BANDS[floor(rng(1, #BANDS + 0.99))])
	end
	roadCairns(f, 85, rng)
	return f
end

-- 침사국 옛터 ----------------------------------------------------------------------------
-- 모래에 가라앉은 나라: 지형이 가운데(반지름 62)를 18 높이로 판판하게 파 두었고 둘레는 모래 언덕(30~47)이 덮는다.
-- 큰길(RU)은 가운데에서 북동쪽 대문으로 (관성대에서 오는 길이 이 쪽으로 들어온다). RV 는 큰길을 가로지르는 쪽.
-- (a, p): 가운데에서 큰길 쪽 a, 가로 p. 성벽은 a, p = ±58 네모 (모서리는 모래 언덕에 묻혔다).
-- 큰길: 대문(a 58) → 전송진(a 42) → 열주(a 30~-20) → 영맥(가운데) → 부서진 계단과 궁 터 기단(a -34~-54).
-- 서쪽 뜰(p<0)에 쓰러진 거상 머리와 발만 남은 받침, 동쪽 뜰(p>0)에 모래 찬 못. 영맥 7·전송진 9 는 비워 둔다.
local RU = V3(0.783, 0, -0.622).Unit
local RV = V3(-RU.Z, 0, RU.X)
local FLOOR = RUINS.height
local function rxz(a: number, p: number): (number, number)
	return RUINS.x + RU.X * a + RV.X * p, RUINS.z + RU.Z * a + RV.Z * p
end
-- (a, p) 의 높이 y 에 서서 대문 쪽(-Z = RU)을 본다. 로컬 +X 가 +p
local function rframe(a: number, p: number, y: number): CFrame
	local x, z = rxz(a, p)
	return face(V3(x, y, z), V3(x + RU.X, y, z + RU.Z))
end

-- 옛터 기둥 (굵은 돌기둥): kind 1 온전 (두 마디, 주두와 대접받침), 2 부러짐 (떨어진 마디 하나), 3 쓰러짐 (마디들이 fall 쪽으로 누웠다)
local function ruinColumn(parent: Instance, x: number, z: number, height: number, kind: number, rng, fall: Vector3?)
	local m = model(parent, "옛터 기둥")
	local g = lowAt(x, z, 2.2)
	local col = jitter(RUIN_STONE, rng, 0.05)
	local d = 2.8
	block(
		m,
		"Chuchu",
		V3(4.2, 1.6, 4.2),
		CFrame.new(x, g + 0.3, z) * CFrame.Angles(0, rng(0, 1.5), 0),
		jitter(RUIN_DARK, rng, 0.05),
		M.Sandstone
	)
	local y0 = g + 1.05
	if kind == 1 then
		local yTop = g + height - 1.7
		local ym = (y0 + yTop) / 2 + rng(-0.5, 0.5)
		cyl(m, "Gidung", V3(x, y0, z), V3(x, ym, z), d, col, M.Sandstone)
		cyl(m, "Gidung", V3(x, ym - 0.05, z), V3(x, yTop, z), d * 0.96, jitter(col, rng, 0.03), M.Sandstone)
		block(m, "Judu", V3(3.6, 1.0, 3.6), CFrame.new(x, yTop + 0.5, z), jitter(RUIN_DARK, rng, 0.04), M.Sandstone)
		block(m, "Daejeop", V3(4.6, 0.7, 4.6), CFrame.new(x, yTop + 1.35, z), col, M.Sandstone)
		return m, yTop + 1.7
	elseif kind == 2 then
		local h = height * rng(0.3, 0.6)
		cyl(m, "Gidung", V3(x, y0, z), V3(x + rng(-0.15, 0.15), y0 + h, z + rng(-0.15, 0.15)), d, col, M.Sandstone)
		local a = rng(0, TAU)
		local p = V3(x, 0, z) + V3(cos(a), 0, sin(a)) * rng(4, 6)
		local b = rng(0, TAU)
		local dd = V3(cos(b), 0, sin(b)) * 1.6
		local gp = H(p.X, p.Z) + d * 0.4
		cyl(m, "Madi", V3(p.X, gp, p.Z) - dd, V3(p.X, gp, p.Z) + dd, d, jitter(col, rng, 0.04), M.Sandstone)
	else
		local dir = fall or V3(1, 0, 0)
		cyl(m, "Gidung", V3(x, y0, z), V3(x, y0 + rng(0.8, 1.8), z), d, col, M.Sandstone)
		local t = 2.2
		local seg = (height - 3) / 3
		for i = 1, 3 do
			local p0 = V3(x, 0, z) + dir * t
			local p1 = p0 + dir * (seg - 0.3)
			local yy = min(H(p0.X, p0.Z), H(p1.X, p1.Z)) + d * 0.4
			local kink = V3(-dir.Z, 0, dir.X) * rng(-0.6, 0.6)
			cyl(m, "Madi", V3(p0.X, yy, p0.Z) + kink, V3(p1.X, yy, p1.Z) - kink, d, jitter(col, rng, 0.04), M.Sandstone)
			t += seg + rng(0.1, 0.8)
			dir = (dir + V3(-dir.Z, 0, dir.X) * rng(-0.12, 0.12)).Unit
		end
		local p = V3(x, 0, z) + dir * (t + 1.2)
		block(
			m,
			"Judu",
			V3(4.6, 1.4, 4.6),
			CFrame.new(p.X, H(p.X, p.Z) + 0.9, p.Z) * CFrame.Angles(rng(-0.2, 0.2), rng(0, TAU), rad(rng(60, 80))),
			jitter(RUIN_DARK, rng, 0.04),
			M.Sandstone
		)
	end
	return m, nil
end

-- 큰 대문: 두 문대, 홍예(귀를 깎은 문길), 문 위 여장과 무너진 문루 (기둥 밑동, 떨어진 지붕 조각), 돌 현판.
-- 바깥(+a)쪽은 모래가 문대 허리까지 쌓였다. 문길 바닥은 비워 둔다 (길이 지난다)
local function greatGate(parent: Instance, rng)
	local m = model(parent, "침사국 대문")
	local G = rframe(58, 0, 0)
	local function put(name: string, size: Vector3, x: number, y: number, z: number, color: Color3?, rot: CFrame?, mat)
		return block(
			m,
			name,
			size,
			G * CFrame.new(x, y, z) * (rot or CFrame.new()),
			color or jitter(RUIN_STONE, rng, 0.04),
			mat or M.Sandstone
		)
	end
	local function wp(x: number, y: number, z: number): Vector3
		return G:PointToWorldSpace(V3(x, y, z))
	end
	local base, top, under = FLOOR - 3, FLOOR + 20, FLOOR + 13
	for _, s in { -1, 1 } do
		put("Mundae", V3(12, top - base, 10), s * 11, (base + top) / 2, 0)
		put("Ttidol", V3(12.5, 1.2, 10.5), s * 11, FLOOR + 6.5, 0, jitter(RUIN_DARK, rng, 0.04))
		Build.rightTri(
			m,
			"Hongye",
			wp(s * 5, under + 0.05, 0),
			wp(s * 5, under - 4.6, 0),
			wp(s * 1.6, under + 0.05, 0),
			10,
			nil,
			jitter(RUIN_STONE, rng, 0.04),
			M.Sandstone
		)
	end
	put("Inbang", V3(10.4, top - under, 10), 0, (under + top) / 2, 0)
	put("Cheomdol", V3(35, 1.2, 11), 0, top - 0.6, 0, jitter(RUIN_DARK, rng, 0.04))
	put("Yeojang", V3(34, 1.6, 9), 0, top + 0.8, 0)
	-- 여장 위 타(垜): 바깥 여섯 (둘은 무너졌다), 안쪽 셋
	for i = 0, 5 do
		if rng(0, 1) > 0.3 then
			put("Ta", V3(2.8, 2.2, 1.4), -15 + i * 6, top + 2.7, -3.9)
		end
	end
	for i = 0, 2 do
		put("Ta", V3(2.8, rng(1.2, 2.2), 1.4), -12 + i * 12, top + 2.4, 3.9)
	end
	-- 문루 기둥 밑동과 떨어진 지붕 조각, 위에 쌓인 모래
	for _, q in { { -7, -2.4 }, { 7, -2.4 }, { -7, 2.4 }, { 7, 2.4 } } do
		local h = rng(1.2, 5)
		cyl(
			m,
			"Mullu",
			wp(q[1], top + 1.5, q[2]),
			wp(q[1], top + 1.6 + h, q[2]),
			1.6,
			jitter(rgb(96, 70, 52), rng, 0.08),
			M.Wood
		)
	end
	put(
		"Jibung",
		V3(9, 0.8, 6),
		2.5,
		top + 2.6,
		0.4,
		P.giwa,
		CFrame.Angles(rad(16), rad(20), rad(-12)),
		M.ClayRoofTiles
	)
	put("Maru", V3(0.6, 0.5, 6.4), 2.5, top + 3.1, 0.4, P.giwaDark, CFrame.Angles(rad(16), rad(20), rad(-12)), M.Slate)
	put("Morae", V3(7, 1.2, 5.6), -8, top + 2.0, 0.8, C.sand, CFrame.Angles(0, rad(12), rad(4)), M.Sand)
	-- 돌 현판 (바깥을 본다)
	put("Te", V3(8.8, 3.4, 0.35), 0, under + 2.6, -5.12, jitter(RUIN_DARK, rng, 0.04))
	local board = put("Hyeonpan", V3(8, 2.6, 0.5), 0, under + 2.6, -5.3, rgb(150, 124, 92))
	Kit.engrave(board, "침사국", "Front")
	-- 안쪽 문대에 기대 쓰러진 청동 문짝
	put("Munjjak", V3(4.6, 9, 0.6), 10, FLOOR + 3.2, 7.0, C.verdigris, CFrame.Angles(rad(-20), rad(8), 0), M.Metal)
	-- 바깥 모래 더미 (문대 허리까지), 안쪽 작은 더미
	for _, s in { -1, 1 } do
		local f0 = wp(s * 11, 0, -5)
		drift(m, V3(f0.X, H(f0.X, f0.Z), f0.Z), RU, 12, 14, 8, rng)
		local f1 = wp(s * 14, 0, 5)
		drift(m, V3(f1.X, H(f1.X, f1.Z), f1.Z), -RU, 6, 3.5, 2.2, rng)
	end
	return m
end

-- 성벽: 네모 (a, p = ±58), 토막마다 높이가 다르고 (무너진 토막은 낮다) 몇 토막은 뚫렸다. 모래가 덮은 토막은 건너뛴다.
-- 북쪽 모서리에 기운 망루, 서쪽 모서리에 망루 밑동
local function ruinWalls(parent: Instance, rng)
	local m = model(parent, "침사국 성벽")
	local S, n = 58, 16
	local seg = 2 * S / n
	for side = 1, 4 do
		for i = 0, n - 1 do
			local u = -S + (i + 0.5) * seg
			local a, p, ra, rp
			if side == 1 then
				a, p, ra, rp = S, u, 0, 1
			elseif side == 2 then
				a, p, ra, rp = -S, u, 0, 1
			elseif side == 3 then
				a, p, ra, rp = u, S, 1, 0
			else
				a, p, ra, rp = u, -S, 1, 0
			end
			local gate = side == 1 and abs(u) < 18
			if not gate and rng(0, 1) > 0.12 then
				local x, z = rxz(a, p)
				local x0, z0 = rxz(a - ra * seg / 2, p - rp * seg / 2)
				local x1, z1 = rxz(a + ra * seg / 2, p + rp * seg / 2)
				local intact = rng(0, 1) < 0.6
				local top = FLOOR + (if intact then 9 + rng(-0.6, 0.6) else rng(3, 7.5))
				local g = max(H(x, z), H(x0, z0), H(x1, z1))
				if g < top - 1.2 then
					local low = min(H(x0, z0), H(x1, z1), H(x, z)) - 1.5
					local run = V3(x1 - x0, 0, z1 - z0).Unit
					local look = face(V3(x, 0, z), V3(x, 0, z) + run)
					block(
						m,
						"Seongbyeok",
						V3(4.5, top - low, seg + 0.15),
						look * CFrame.new(0, (low + top) / 2, 0) * CFrame.Angles(0, 0, rad(rng(-0.8, 0.8))),
						jitter(RUIN_STONE, rng, 0.05),
						M.Sandstone
					)
					if intact then
						block(
							m,
							"Gatdol",
							V3(5.1, 0.8, seg + 0.2),
							look * CFrame.new(0, top + 0.4, 0),
							jitter(RUIN_DARK, rng, 0.04),
							M.Sandstone
						)
						if side == 1 and abs(u) < 34 then
							block(
								m,
								"Ta",
								V3(1.3, 2, 2.4),
								look * CFrame.new(-1.9, top + 1.8, 0),
								jitter(RUIN_STONE, rng, 0.04),
								M.Sandstone
							)
						end
					end
				end
			end
		end
	end
	-- 북쪽 모서리 망루: 모래 언덕에서 기울어 솟는다 (멀리서 옛터를 알린다)
	do
		local x, z = rxz(62, -62)
		local g = lowAt(x, z, 6) - 2
		local look = face(V3(x, g, z), V3(RUINS.x, g, RUINS.z)) * CFrame.Angles(rad(-4), 0, rad(3))
		local tw = model(m, "망루")
		block(tw, "Mom", V3(10, 15, 10), look * CFrame.new(0, 7.5, 0), jitter(RUIN_STONE, rng, 0.04), M.Sandstone)
		block(tw, "Mom", V3(8.8, 11, 8.8), look * CFrame.new(0, 20.5, 0), jitter(RUIN_STONE, rng, 0.04), M.Sandstone)
		block(tw, "Ttidol", V3(10.4, 1, 10.4), look * CFrame.new(0, 15, 0), jitter(RUIN_DARK, rng, 0.04), M.Sandstone)
		block(tw, "Cheomdol", V3(9.8, 1, 9.8), look * CFrame.new(0, 26.4, 0), jitter(RUIN_DARK, rng, 0.04), M.Sandstone)
		for _, q in { { -3.6, -3.6 }, { 3.6, -3.6 }, { 3.6, 3.6 } } do
			block(
				tw,
				"Ta",
				V3(2.2, 2.2, 2.2),
				look * CFrame.new(q[1], 28, q[2]),
				jitter(RUIN_STONE, rng, 0.04),
				M.Sandstone
			)
		end
		for _, y in { 19, 23 } do
			block(tw, "Chang", V3(1.2, 2.6, 0.4), look * CFrame.new(0, y, -4.5), rgb(54, 44, 36), M.Slate)
		end
	end
	-- 서쪽 모서리 망루 밑동
	do
		local x, z = rxz(-60, -60)
		local g = lowAt(x, z, 6) - 2
		local look = face(V3(x, g, z), V3(RUINS.x, g, RUINS.z))
		local h = max(H(x, z) - g + 7, 9)
		block(
			m,
			"Mangrumitdong",
			V3(10, h, 10),
			look * CFrame.new(0, h / 2, 0) * CFrame.Angles(0, 0, rad(2)),
			jitter(RUIN_STONE, rng, 0.04),
			M.Sandstone
		)
		block(
			m,
			"Mangrumitdong",
			V3(6, 3, 5),
			look * CFrame.new(-1.5, h + 1, 1) * CFrame.Angles(rad(8), rad(15), 0),
			jitter(RUIN_STONE, rng, 0.04),
			M.Sandstone
		)
	end
	return m
end

-- 궁 터 기단 (a -34~-54, p ±30): 장대석 단, 앞의 부서진 계단과 소맷돌, 초석과 기둥 밑동, 쓰러진 들보, 무너진 지붕 조각,
-- 뒤쪽 가운데 깨진 돌 옥좌. 옆구리로 모래가 타고 올랐다
local function palaceTerrace(parent: Instance, rng)
	local m = model(parent, "궁 터")
	local A0, A1, W = -34, -54, 30
	local topY = FLOOR + 5.9
	local ac = (A0 + A1) / 2
	local depth = A0 - A1
	block(
		m,
		"Gidan",
		V3(W * 2, topY - 1 - (FLOOR - 1.5), depth),
		rframe(ac, 0, (topY - 1 + FLOOR - 1.5) / 2),
		jitter(RUIN_STONE, rng, 0.03),
		M.Sandstone
	)
	block(
		m,
		"Gapseok",
		V3(W * 2 + 0.8, 1, depth + 0.8),
		rframe(ac, 0, topY - 0.5),
		jitter(RUIN_DARK, rng, 0.03),
		M.Sandstone
	)
	-- 계단 여섯 (기단 앞, 큰길 쪽으로 내려간다). 셋째·다섯째는 가운데가 깨져 나갔다
	local rise, tread, half = (topY - FLOOR) / 6, 1.5, 8
	for i = 1, 6 do
		local aFront = A0 + tread * (7 - i)
		local yTop = FLOOR + rise * i
		local len = aFront - A0
		local ac2 = A0 + len / 2
		local col = jitter(RUIN_STONE, rng, 0.04)
		if i == 3 or i == 5 then
			local gap = rng(-3, 3)
			local wl = gap + half - 1.4
			local wr = half - gap - 1.4
			block(
				m,
				"Gyedan",
				V3(wl, yTop - FLOOR + 1, len),
				rframe(ac2, -half + wl / 2, (yTop + FLOOR - 1) / 2),
				col,
				M.Sandstone
			)
			block(
				m,
				"Gyedan",
				V3(wr, yTop - FLOOR + 1, len),
				rframe(ac2, half - wr / 2, (yTop + FLOOR - 1) / 2),
				col,
				M.Sandstone
			)
			block(
				m,
				"Gyedan",
				V3(2.8, yTop - FLOOR + 1 - rise, len),
				rframe(ac2, gap, (yTop - rise + FLOOR - 1) / 2),
				col,
				M.Sandstone
			)
		else
			block(
				m,
				"Gyedan",
				V3(half * 2, yTop - FLOOR + 1, len),
				rframe(ac2, 0, (yTop + FLOOR - 1) / 2),
				col,
				M.Sandstone
			)
		end
	end
	-- 떨어진 계단 돌
	block(
		m,
		"Gyedandol",
		V3(4, 0.9, 1.5),
		rframe(A0 + 10.5, half + 3, FLOOR + 0.3) * CFrame.Angles(rad(8), rad(35), rad(-6)),
		jitter(RUIN_STONE, rng, 0.04),
		M.Sandstone
	)
	-- 소맷돌 (비탈 쐐기: 높은 쪽 +Z 가 기단 쪽). 왼쪽은 온전, 오른쪽은 아래 토막만 남고 윗토막이 떨어졌다
	local run = tread * 6
	local cheekH = topY - FLOOR + 1
	wedge(
		m,
		"Somaet",
		V3(1.4, cheekH, run),
		rframe(A0 + run / 2, -half - 0.7, FLOOR - 1 + cheekH / 2),
		jitter(RUIN_DARK, rng, 0.04),
		M.Sandstone
	)
	wedge(
		m,
		"Somaet",
		V3(1.4, cheekH * 0.55, run * 0.55),
		rframe(A0 + run * 0.725, half + 0.7, FLOOR - 1 + cheekH * 0.275),
		jitter(RUIN_DARK, rng, 0.04),
		M.Sandstone
	)
	block(
		m,
		"Somaetjogak",
		V3(1.4, 1.6, 3.6),
		rframe(A0 + run + 2, half + 3.5, FLOOR + 0.5) * CFrame.Angles(rad(-12), rad(50), rad(70)),
		jitter(RUIN_DARK, rng, 0.04),
		M.Sandstone
	)
	-- 초석과 기둥 밑동, 쓰러진 들보
	local stumps = { [2] = rng(1.5, 2.5), [3] = rng(4, 6.5), [6] = rng(2.5, 4) }
	local k = 0
	for _, a in { -38.5, -50 } do
		for _, p in { -21, -7, 7, 21 } do
			k += 1
			block(m, "Choseok", V3(2.8, 0.5, 2.8), rframe(a, p, topY + 0.2), jitter(RUIN_DARK, rng, 0.05), M.Sandstone)
			if stumps[k] then
				local x, z = rxz(a, p)
				cyl(
					m,
					"Gidung",
					V3(x, topY + 0.4, z),
					V3(x, topY + 0.4 + stumps[k], z),
					2.1,
					jitter(rgb(96, 70, 52), rng, 0.08),
					M.Wood
				)
			end
		end
	end
	block(
		m,
		"Deulbo",
		V3(1.3, 1.2, 15),
		rframe(-44, 12, topY + 0.6) * CFrame.Angles(0, rad(64), rad(5)),
		rgb(70, 52, 40),
		M.Wood
	)
	-- 무너진 지붕 조각 (뒤 구석, 모래에 반쯤)
	block(
		m,
		"Jibung",
		V3(14, 1, 9),
		rframe(-52, -22, topY + 1.5) * CFrame.Angles(rad(14), rad(-18), rad(10)),
		P.giwa,
		M.ClayRoofTiles
	)
	block(
		m,
		"Maru",
		V3(0.7, 0.6, 14.5),
		rframe(-52, -22, topY + 2.4) * CFrame.Angles(rad(14), rad(-18 + 90), rad(10)),
		P.giwaDark,
		M.Slate
	)
	-- 돌 옥좌 (등받이가 깨져 기울었다)
	local tf = rframe(-51.5, 0, topY)
	block(m, "Dan", V3(9, 1.2, 4.6), tf * CFrame.new(0, 0.6, 0), jitter(RUIN_DARK, rng, 0.03), M.Sandstone)
	block(m, "Jari", V3(3.8, 1.3, 2.6), tf * CFrame.new(0, 1.85, -0.2), jitter(RUIN_STONE, rng, 0.03), M.Marble)
	block(
		m,
		"Deungbadi",
		V3(3.8, 3.6, 0.8),
		tf * CFrame.new(0.3, 3.8, 1.0) * CFrame.Angles(rad(9), 0, rad(-7)),
		jitter(RUIN_STONE, rng, 0.03),
		M.Marble
	)
	for _, s in { -1, 1 } do
		block(
			m,
			"Paltong",
			V3(0.8, 1.4, 2.6),
			tf * CFrame.new(s * 2.3, 2.9, -0.2),
			jitter(RUIN_STONE, rng, 0.03),
			M.Marble
		)
	end
	-- 기단 옆구리로 타고 오른 모래
	for _, s in { -1, 1 } do
		local x, z = rxz(ac + rng(-3, 3), s * W)
		drift(m, V3(x, FLOOR, z), RV * s, 9, 9, topY - FLOOR - 0.6, rng)
	end
	return m
end

-- 쓰러진 거상 머리: 관을 쓴 옛 왕의 얼굴. 오른뺨을 대고 누워 반쯤 모래에 묻혔다 (얼굴이 큰길을 본다)
local function colossusHead(parent: Instance, a: number, p: number, rng)
	local m = model(parent, "거상 머리")
	local x, z = rxz(a, p)
	local c = V3(x, H(x, z) + 3.2, z)
	local F = face(c, c + RV) * CFrame.Angles(rad(14), 0, rad(80))
	local stone = rgb(204, 182, 142)
	local function put(name: string, size: Vector3, px: number, py: number, pz: number, color: Color3?, rot: CFrame?)
		return block(
			m,
			name,
			size,
			F * CFrame.new(px, py, pz) * (rot or CFrame.new()),
			color or jitter(stone, rng, 0.03),
			M.Sandstone
		)
	end
	put("Eolgul", V3(8.4, 10, 8.6), 0, 0, 0.4)
	put("Teok", V3(7.4, 3.6, 7.6), 0, -5.4, 0.1)
	put("Gwan", V3(9.2, 3.4, 9.2), 0, 6.4, 0.4, jitter(RUIN_DARK, rng, 0.03))
	put("Gwanmeori", V3(6.4, 1.6, 6.4), 0, 8.7, 0.4, jitter(RUIN_DARK, rng, 0.03))
	put("Gwanjang", V3(3.0, 3.4, 0.8), 0, 8.3, -4.2, jitter(C.verdigris, rng, 0.05), CFrame.new()).Material = M.Metal
	put("Ima", V3(7.6, 2.2, 0.8), 0, 3.6, -4.3)
	for _, s in { -1, 1 } do
		put("Nunsseop", V3(3.2, 0.8, 1.2), s * 2.0, 2.4, -4.6, nil, CFrame.Angles(0, 0, rad(s * -6)))
		put("Nun", V3(2.6, 0.7, 0.6), s * 2.0, 1.3, -4.7, rgb(84, 70, 56))
		put("Gwangdae", V3(2.2, 2.4, 0.8), s * 2.6, -1.4, -4.3)
		put("Gwi", V3(1.2, 6.2, 2.6), s * 4.7, -0.2, 0.6)
	end
	put("Ko", V3(2.2, 4.2, 2.2), 0, -0.4, -4.6, nil, CFrame.Angles(rad(12), 0, 0))
	put("Kotbang", V3(2.8, 0.9, 1.4), 0, -2.3, -5.0)
	put("Ip", V3(3.6, 1.0, 1.0), 0, -3.6, -4.5, rgb(150, 100, 76))
	put("Mok", V3(6.2, 3, 6.2), 0, -8.4, 0.6, rgb(160, 136, 100))
	-- 머리 둘레에 튄 돌 조각과 쌓인 모래
	for _ = 1, 3 do
		local q = c + RU * rng(-10, 10) + RV * rng(5, 9)
		boulder(m, q.X, q.Z, rng(1.2, 2.2), rng, stone)
	end
	drift(m, V3(x, H(x, z), z) - RV * 4, -RV, 14, 6, 3, rng)
	return m
end

-- 발만 남은 거상 받침: 두 발과 깨진 발목
local function colossusFeet(parent: Instance, a: number, p: number, rng)
	local m = model(parent, "거상 받침")
	local x, z = rxz(a, p)
	local g = lowAt(x, z, 6)
	local look = face(V3(x, g, z), V3(x, g, z) + RV)
	block(m, "Batchim", V3(12, 3.6, 9), look * CFrame.new(0, 1.2, 0), jitter(RUIN_DARK, rng, 0.03), M.Sandstone)
	block(m, "Batchim", V3(12.8, 0.8, 9.8), look * CFrame.new(0, 3.2, 0), jitter(RUIN_STONE, rng, 0.03), M.Sandstone)
	for _, s in { -1, 1 } do
		block(m, "Bal", V3(3.2, 2.0, 5.6), look * CFrame.new(s * 2.4, 4.6, -0.6), rgb(204, 182, 142), M.Sandstone)
		cyl(
			m,
			"Balmok",
			look:PointToWorldSpace(V3(s * 2.4, 5.2, 0.8)),
			look:PointToWorldSpace(V3(s * 2.4 + s * 0.2, 5.2 + rng(1.6, 3.4), 0.9)),
			2.6,
			rgb(198, 176, 136),
			M.Sandstone
		)
	end
	return m
end

-- 모래 찬 못 (동쪽 뜰): 네모 돌 테, 모래가 찬 바닥, 가운데 깨진 물그릇 받침
local function dryPool(parent: Instance, a: number, p: number, rng)
	local m = model(parent, "마른 못")
	local half = 7
	for k = 0, 3 do
		local ang = k * math.pi / 2
		local oa, op = cos(ang) * half, sin(ang) * half
		local rot = if k % 2 == 0 then 0 else 90
		local x, z = rxz(a + oa, p + op)
		block(
			m,
			"Dolte",
			V3(1.4, 1.6, half * 2 + 1.4),
			rframe(a + oa, p + op, H(x, z) + 0.3) * CFrame.Angles(0, rad(rot + 90), 0),
			jitter(RUIN_DARK, rng, 0.04),
			M.Sandstone
		)
	end
	local x, z = rxz(a, p)
	block(
		m,
		"Morae",
		V3(half * 2 - 0.4, 0.8, half * 2 - 0.4),
		rframe(a, p, H(x, z) + 0.2),
		jitter(C.sand, rng, 0.03),
		M.Sand
	)
	cyl(m, "Batchim", V3(x, H(x, z), z), V3(x, H(x, z) + 2.6, z), 2.4, jitter(RUIN_STONE, rng, 0.04), M.Sandstone)
	block(
		m,
		"Geureut",
		V3(4.2, 0.6, 3.2),
		CFrame.new(x, H(x, z) + 2.9, z) * CFrame.Angles(rad(9), rng(0, TAU), rad(-5)),
		jitter(RUIN_STONE, rng, 0.04),
		M.Sandstone
	)
	return m
end

local function ruins(parent: Instance, rng)
	local f = folder(parent, "침사국 옛터")
	greatGate(f, rng)
	ruinWalls(f, rng)
	palaceTerrace(f, rng)
	-- 열주: 큰길 양옆 (p ±13), 대문 쪽은 거의 서 있고 안쪽일수록 부러지고 쓰러졌다. 나란히 선 둘에 들보를 얹는다
	local cols = folder(f, "열주")
	local kinds = { { 1, 1, 1, 2, 3, 1 }, { 1, 1, 2, 1, 1, 3 } }
	for side, s in { -1, 1 } do
		local prevTop = nil
		for i, a in { 30, 20, 10, 0, -10, -20 } do
			local x, z = rxz(a, s * 13)
			local kind = kinds[side][i]
			local fall = (RU * (if rng(0, 1) < 0.5 then 1 else -1) + RV * s * rng(0.2, 0.6)).Unit
			local _, topY = ruinColumn(cols, x, z, 14, kind, rng, fall)
			if topY and prevTop and rng(0, 1) < 0.75 then
				local px, pz = rxz(a + 10, s * 13)
				local y = max(topY, prevTop) + 0.55
				local mid = V3((x + px) / 2, y, (z + pz) / 2)
				block(
					cols,
					"Pyeongbang",
					V3(2.4, 1.1, 14),
					face(mid, V3(px, y, pz)),
					jitter(RUIN_DARK, rng, 0.04),
					M.Sandstone
				)
				prevTop = nil
			else
				prevTop = topY
			end
		end
	end
	-- 서쪽 뜰: 쓰러진 거상 머리, 발만 남은 받침
	colossusHead(f, -6, -36, rng)
	colossusFeet(f, -24, -44, rng)
	-- 동쪽 뜰: 모래 찬 못
	dryPool(f, -2, 38, rng)
	-- 뜰을 가르는 낮은 담 (p ±24, 무너져 드문드문)
	local walls = model(f, "뜰 담")
	for _, s in { -1, 1 } do
		for i = 0, 7 do
			local a = 26 - i * 7.2
			if rng(0, 1) > 0.3 and not (s < 0 and a < 6 and a > -18) then
				local x, z = rxz(a, s * 24)
				local h = rng(2.2, 4.4)
				local g = H(x, z)
				block(
					walls,
					"Dam",
					V3(2, h + 1, 7.4),
					rframe(a, s * 24, g + h / 2 - 0.5) * CFrame.Angles(0, 0, rad(rng(-1, 1))),
					jitter(RUIN_STONE, rng, 0.05),
					M.Sandstone
				)
				if rng(0, 1) < 0.4 then
					drift(walls, V3(x, g, z) + RV * s * 1, RV * s, 6.5, 5, h * 0.7, rng)
				end
			end
		end
	end
	-- 흩어진 다듬돌과 들뜬 박석, 뜰에 쌓인 모래 둔덕
	local taken = {
		{ RUINS.x, RUINS.z, 10 },
		{ (rxz(-6, -36)), select(2, rxz(-6, -36)), 14 },
		{ (rxz(-24, -44)), select(2, rxz(-24, -44)), 9 },
		{ (rxz(-2, 38)), select(2, rxz(-2, 38)), 10 },
	}
	local function inside(x: number, z: number, pad: number): boolean
		local dx, dz = x - RUINS.x, z - RUINS.z
		local a, p = dx * RU.X + dz * RU.Z, dx * RV.X + dz * RV.Z
		if abs(a) > 52 or abs(p) > 52 or (a < -31 and abs(p) < 32) then
			return false
		end
		if abs(p) < 7 + pad or abs(abs(p) - 13) < 3 + pad or abs(abs(p) - 24) < 1.6 + pad then
			return false
		end
		return clearOf(x, z, pad) and H(x, z) < FLOOR + 1.5
	end
	local box = { RUINS.x - 75, RUINS.x + 75, RUINS.z - 75, RUINS.z + 75 }
	local rubble = folder(f, "돌 부스러기")
	for _, q in
		scatter(rng, 12, box, 7, function(x, z)
			return inside(x, z, 1.5)
		end, taken)
	do
		local g = H(q[1], q[2])
		local s = V3(rng(2.4, 4.2), rng(1.2, 2), rng(1.6, 2.6))
		block(
			rubble,
			"Dadeumdol",
			s,
			CFrame.new(q[1], g + s.Y * 0.25, q[2]) * CFrame.Angles(rng(-0.25, 0.25), rng(0, TAU), rng(-0.25, 0.25)),
			jitter(RUIN_STONE, rng, 0.06),
			M.Sandstone
		)
	end
	for _, q in
		scatter(rng, 7, box, 9, function(x, z)
			return inside(x, z, 1)
		end, taken)
	do
		local g = H(q[1], q[2])
		block(
			rubble,
			"Bakseok",
			V3(rng(3, 4.5), 0.5, rng(2.6, 3.6)),
			CFrame.new(q[1], g + 0.15, q[2]) * CFrame.Angles(rng(0.05, 0.16), rng(0, TAU), rng(-0.1, 0.1)),
			jitter(rgb(176, 160, 132), rng, 0.05),
			M.Pavement
		)
	end
	for _, q in
		scatter(rng, 5, box, 16, function(x, z)
			return inside(x, z, 4)
		end, taken)
	do
		local g = H(q[1], q[2])
		block(
			rubble,
			"Moraedundeok",
			V3(rng(7, 11), 1.6, rng(5, 8)),
			CFrame.new(q[1], g + 0.1, q[2]) * CFrame.Angles(rng(-0.06, 0.06), rng(0, TAU), rng(-0.06, 0.06)),
			jitter(C.sand, rng, 0.03),
			M.Sand
		)
	end
	-- 옛터 마른 덤불 몇
	for _, q in
		scatter(rng, 6, box, 12, function(x, z)
			return inside(x, z, 1)
		end, taken)
	do
		dryShrub(f, q[1], q[2], rng, rng(1.6, 2.6))
	end
	return f
end

-- 녹주 ---------------------------------------------------------------------------------
-- 마른 바다 한가운데 샘: 지형이 가운데 못(수면 16, 반지름 14~17)과 둘레 판판한 테(18, 반지름 30 안팎)를 지어 두었다.
-- 못가에 대추야자를 두르고, 서쪽 테에 대상 천막 셋, 북동쪽에 돌 우물과 구유, 남쪽 길머리에 이름 비석.
-- 영맥(Sites 의 low@oasis, 북동 못가) 7 과 볼거리 자리(동쪽) 둘레는 비워 둔다.
local OASIS_WATER = 16
local PALM_LEAF = { rgb(84, 118, 62), rgb(104, 136, 70), rgb(124, 148, 82) }

-- 대추야자: 굽은 줄기 (마디 빛깔을 번갈아), 위아래 두 켜의 잎 (잎마다 오르는 마디와 처지는 마디), 열매 송이 둘
local function palm(parent: Instance, x: number, z: number, rng, opts)
	opts = opts or {}
	local m = model(parent, "대추야자")
	local height = opts.height or rng(11, 15)
	local base = V3(x, lowAt(x, z, 0.8) - 0.6, z)
	local la = opts.lean or rng(0, TAU)
	local lean = V3(cos(la), 0, sin(la)) * rng(0.12, 0.3)
	local p = base
	for i = 1, 4 do
		local t = i / 4
		local dir = (Vector3.yAxis + lean * (0.5 + 1.5 * t)).Unit
		local q = p + dir * (height / 4)
		cyl(
			m,
			"Julgi",
			p,
			q + dir * 0.2,
			1.35 - 0.3 * t,
			if i % 2 == 0 then rgb(118, 96, 70) else rgb(140, 116, 86),
			M.Wood
		)
		p = q
	end
	local top = p
	block(m, "Mokdeol", V3(1.8, 1.4, 1.8), CFrame.new(top) * CFrame.Angles(0, rng(0, TAU), 0), rgb(112, 92, 60), M.Wood)
	local nf = opts.fronds or 6
	local a0 = rng(0, TAU)
	for k = 1, nf do
		local upper = k % 2 == 0
		local a = a0 + k * TAU / nf + rng(-0.2, 0.2)
		local out = V3(cos(a), 0, sin(a))
		local len = rng(3.4, 4.4)
		local root = top + V3(0, 0.5, 0)
		local mid = root + out * len + V3(0, if upper then len * 0.55 else len * 0.12, 0)
		local tip = mid + out * len * 0.95 - V3(0, if upper then len * 0.45 else len * 0.95, 0)
		local col = jitter(PALM_LEAF[1 + k % #PALM_LEAF], rng, 0.06)
		deco(beam(m, "Ip", root, mid, if upper then 1.7 else 1.9, 0.2, col, M.LeafyGrass))
		deco(beam(m, "Ipkkeut", mid, tip, 1.5, 0.18, col, M.LeafyGrass))
	end
	for _ = 1, 1 do
		local a = rng(0, TAU)
		local d = ball(m, "Yeolmae", top + V3(cos(a) * 0.9, -1.0, sin(a) * 0.9), 1.1, rgb(176, 98, 40), M.SmoothPlastic)
		deco(d).CastShadow = false
	end
	return m
end

-- 대상 천막: 앞(-Z, toward 쪽)이 열린 맞배 천막. 용마루 기둥 둘, 앞 차양과 차양 기둥, 뒤·옆 휘장 (옆은 뒤 반만 막았다),
-- 앞에 깐 깔개(테두리와 가운데 무늬), 방석, 짐, 버팀줄
local function tent(
	parent: Instance,
	x: number,
	z: number,
	toward: Vector3,
	roof: Color3,
	awning: Color3,
	rug: Color3,
	rng
)
	local m = model(parent, "대상 천막")
	local g = H(x, z)
	local look = face(V3(x, g, z), V3(toward.X, g, toward.Z))
	local function wp(px: number, py: number, pz: number): Vector3
		return look:PointToWorldSpace(V3(px, py, pz))
	end
	local rel = lowAt(x, z, 5) - 0.5 - g -- 땅이 기운 곳은 기둥과 휘장 밑을 더 묻는다
	local pole = P.woodDark
	for _, s in { -1, 1 } do
		beam(m, "Gidung", wp(s * 3.9, rel, 0), wp(s * 3.9, 6.5, 0), 0.4, 0.4, pole, M.Wood)
		beam(m, "Chayanggidung", wp(s * 4.4, rel, -6.3), wp(s * 4.4, 3.55, -6.3), 0.3, 0.3, pole, M.Wood)
	end
	beam(m, "Yongmaru", wp(-4.7, 6.3, 0), wp(4.7, 6.3, 0), 0.3, 0.3, pole, M.Wood)
	local X = look.RightVector
	local Y = Vector3.yAxis
	local Zb = -look.LookVector -- 뒤쪽
	Build.slab(m, "Jibung", wp(-4.8, 6.2, 0), X * 9.6, Y * -2.0 - Zb * 3.4, 0.2, Y, jitter(roof, rng, 0.04), M.Fabric)
	Build.slab(m, "Jibung", wp(-4.8, 6.2, 0), X * 9.6, Y * -3.8 + Zb * 3.6, 0.2, Y, jitter(roof, rng, 0.04), M.Fabric)
	Build.slab(
		m,
		"Chayang",
		wp(-4.8, 4.2, -3.4),
		X * 9.6,
		Y * -0.7 - Zb * 3.0,
		0.18,
		Y,
		jitter(awning, rng, 0.04),
		M.Fabric
	)
	block(
		m,
		"Dwitwijang",
		V3(9.6, 2.4 - rel + 0.1, 0.15),
		look * CFrame.new(0, (2.4 + rel) / 2, 3.55),
		jitter(roof, rng, 0.06),
		M.Fabric
	)
	for _, s in { -1, 1 } do
		local xs = s * 4.75
		block(
			m,
			"Yeopwijang",
			V3(0.15, 2.4 - rel, 3.6),
			look * CFrame.new(xs, (2.4 + rel) / 2, 1.8),
			jitter(roof, rng, 0.06),
			M.Fabric
		)
		Build.rightTri(
			m,
			"Bakgong",
			wp(xs, 2.4, 0),
			wp(xs, 6.2, 0),
			wp(xs, 2.4, 3.55),
			0.15,
			nil,
			jitter(roof, rng, 0.06),
			M.Fabric
		)
		Build.rightTri(
			m,
			"Bakgong",
			wp(xs, 4.2, 0),
			wp(xs, 6.2, 0),
			wp(xs, 4.2, -3.4),
			0.15,
			nil,
			jitter(roof, rng, 0.06),
			M.Fabric
		)
		deco(beam(m, "Jul", wp(s * 3.9, 6.4, 0), wp(s * 7.6, -0.3, 0.4), 0.08, 0.08, C.straw, M.Fabric))
	end
	-- 깔개, 방석, 짐
	block(m, "Kkalgae", V3(7, 0.1, 5.6), look * CFrame.new(0, 0.04, -1.6), rgb(70, 50, 40), M.Fabric)
	block(m, "Kkalgae", V3(6.4, 0.1, 5.0), look * CFrame.new(0, 0.1, -1.6), jitter(rug, rng, 0.04), M.Fabric)
	block(
		m,
		"Munui",
		V3(2.2, 0.1, 1.8),
		look * CFrame.new(0, 0.16, -1.6) * CFrame.Angles(0, rad(45), 0),
		C.ochreCloth,
		M.Fabric
	)
	for _, s in { -1, 1 } do
		block(
			m,
			"Bangseok",
			V3(1.5, 0.6, 1.1),
			look * CFrame.new(s * 1.8, 0.4, 1.2),
			jitter(if s < 0 then C.ochreCloth else C.felt, rng, 0.05),
			M.Fabric
		)
	end
	block(
		m,
		"Sangja",
		V3(1.8, 1.4, 1.6),
		look * CFrame.new(3.3, 0.6, 2.6) * CFrame.Angles(0, rng(-0.3, 0.3), 0),
		jitter(P.wood, rng, 0.06),
		M.WoodPlanks
	)
	block(
		m,
		"Jaru",
		V3(1.4, 1.1, 1.8),
		look * CFrame.new(-3.3, 0.5, 2.4) * CFrame.Angles(0, rng(-0.4, 0.4), rad(6)),
		jitter(C.straw, rng, 0.06),
		M.Fabric
	)
	ball(m, "Dok", wp(-3.4, 0.75, 0.4), 1.5, jitter(rgb(150, 92, 56), rng, 0.06), M.SmoothPlastic).CastShadow = false
	return m
end

-- 낙타: 앞(-Z)이 toward 쪽. kneel 이면 다리를 접고 엎드린다. 등에 꼭두서니 깔개와 짐 자루 둘
local function camel(parent: Instance, ground: Vector3, toward: Vector3, kneel: boolean, rng)
	local m = model(parent, "낙타")
	local look = face(ground, V3(toward.X, ground.Y, toward.Z))
	local fur = jitter(rgb(178, 140, 94), rng, 0.05)
	local function put(name: string, size: Vector3, x: number, y: number, z: number, color: Color3?, rot: CFrame?)
		return block(m, name, size, look * CFrame.new(x, y, z) * (rot or CFrame.new()), color or fur, M.Fabric)
	end
	local function wp(x: number, y: number, z: number): Vector3
		return look:PointToWorldSpace(V3(x, y, z))
	end
	local by = if kneel then 1.7 else 5.6
	put("Mom", V3(2.4, 2.6, 5.2), 0, by, 0)
	put("Hok", V3(1.9, 1.6, 2.6), 0, by + 1.8, 0.3)
	put("Kkalgae", V3(2.7, 1.4, 1.8), 0, by + 0.7, 0.3, jitter(C.madder, rng, 0.05))
	for _, s in { -1, 1 } do
		put("Jimjaru", V3(0.8, 1.3, 1.5), s * 1.6, by - 0.1, 0.7, jitter(if s < 0 then C.indigo else C.felt, rng, 0.05))
	end
	local neck0 = wp(0, by + 0.4, -2.4)
	local neck1 = wp(0, by - 0.2, -3.8)
	local head = if kneel then wp(0, by + 3.4, -4.4) else wp(0, by + 2.6, -4.8)
	beam(m, "Mok", neck0, neck1, 1.0, 1.2, fur, M.Fabric)
	beam(m, "Mok", neck1, head, 0.9, 1.0, fur, M.Fabric)
	put(
		"Meori",
		V3(1.0, 1.0, 2.2),
		0,
		if kneel then by + 3.6 else by + 2.8,
		if kneel then -5.0 else -5.4,
		fur,
		CFrame.Angles(rad(-12), 0, 0)
	)
	beam(m, "Kkori", wp(0, by + 0.6, 2.6), wp(0, by - 1.2, 3.0), 0.3, 0.3, fur, M.Fabric)
	if kneel then
		for _, z in { -1.6, 1.8 } do
			put("Dari", V3(2.8, 0.8, 1.4), 0, 0.2, z, jitter(fur, rng, 0.04))
		end
	else
		for _, q in { { -0.8, -1.9 }, { 0.8, -1.9 }, { -0.8, 1.9 }, { 0.8, 1.9 } } do
			beam(m, "Dari", wp(q[1], by - 1.1, q[2]), wp(q[1] * 1.1, -0.2, q[2] * 1.05), 0.55, 0.55, fur, M.Fabric)
		end
	end
	return m
end

local function oasis(parent: Instance, rng)
	local f = folder(parent, "녹주")
	local ox, oz = OASIS.x, OASIS.z
	local vein = Sites.byId["low@oasis"]
	local poi = Sites.byId.oasis
	local function polar(deg: number, r: number): (number, number)
		local a = rad(deg)
		return ox + cos(a) * r, oz + sin(a) * r
	end
	local function free(x: number, z: number, pad: number): boolean
		if vein and (x - vein.x) ^ 2 + (z - vein.z) ^ 2 < (8 + pad) ^ 2 then
			return false
		end
		if poi and (x - poi.x) ^ 2 + (z - poi.z) ^ 2 < (6 + pad) ^ 2 then
			return false
		end
		return clearOf(x, z, pad)
	end
	local center = V3(ox, OASIS_WATER, oz)
	-- 대상 천막 셋 (못을 본다)
	local tents = {
		{ 205, 27, C.madder, C.felt, C.indigo },
		{ 150, 27, C.indigo, C.madder, C.madder },
		{ 250, 26, C.felt, C.indigo, rgb(120, 70, 52) },
	}
	for _, t in tents do
		local x, z = polar(t[1], t[2])
		if free(x, z, 8) then
			tent(f, x, z, center, t[3], t[4], t[5], rng)
		end
	end
	-- 대추야자: 못가에 둘러 (못 쪽으로 기운다), 천막 뒤로 둘
	local palms = folder(f, "대추야자")
	local spots = {
		{ 5, 19.5 },
		{ 72, 20 },
		{ 104, 19.5 },
		{ 132, 20 },
		{ 178, 19.5 },
		{ 228, 20 },
		{ 276, 19.5 },
		{ 322, 20 },
		{ 190, 36 },
		{ 140, 37 },
	}
	for _, q in spots do
		local x, z = polar(q[1] + rng(-4, 4), q[2] + rng(-0.8, 0.8))
		if free(x, z, 2) and H(x, z) < 30 then
			palm(palms, x, z, rng, { lean = math.atan2(oz - z, ox - x) + rng(-0.4, 0.4), height = rng(11, 15.5) })
		end
	end
	-- 물가 갈대와 연잎
	for _, deg in { 30, 95, 160, 215, 260, 340 } do
		local x, z = polar(deg + rng(-6, 6), rng(15.2, 16.6))
		if free(x, z, 1) then
			Build.reeds(f, V3(x, H(x, z), z), rng, { count = 3, radius = 1.4 })
		end
	end
	for _ = 1, 6 do
		local x, z = polar(rng(0, 360), rng(4, 11))
		deco(
			cyl(
				f,
				"Yeonip",
				V3(x, OASIS_WATER + 0.02, z),
				V3(x, OASIS_WATER + 0.1, z),
				rng(1.6, 2.6),
				jitter(rgb(86, 132, 70), rng, 0.08),
				M.LeafyGrass
			)
		)
	end
	for _ = 1, 2 do
		local x, z = polar(rng(0, 360), rng(5, 10))
		deco(
			block(
				f,
				"Yeonkkot",
				V3(0.7, 0.5, 0.7),
				CFrame.new(x, OASIS_WATER + 0.3, z) * CFrame.Angles(0, rng(0, 1.5), 0),
				P.blossom,
				M.SmoothPlastic
			)
		)
	end
	-- 돌 우물과 구유 (북동)
	local wellX, wellZ = polar(300, 24)
	if free(wellX, wellZ, 4) then
		Build.well(f, V3(wellX, lowAt(wellX, wellZ, 2.6), wellZ))
		local tx, tz = polar(314, 29)
		local look = face(V3(tx, H(tx, tz), tz), center)
		block(f, "Guyu", V3(6, 1.2, 2), look * CFrame.new(0, 0.35, 0), P.granite, M.Granite)
		block(f, "Guyumul", V3(5.4, 0.12, 1.4), look * CFrame.new(0, 0.92, 0), rgb(60, 104, 116), M.Glass).Transparency =
			0.25
	end
	-- 매어 둔 낙타 (서쪽)와 엎드린 낙타 (남쪽 길머리)
	do
		local x, z = polar(180, 34)
		if free(x, z, 5) then
			camel(f, V3(x, H(x, z), z), V3(ox - 6, 0, oz - 14), false, rng)
			local px, pz = polar(188, 38)
			local post = V3(px, H(px, pz), pz)
			beam(f, "Malttuk", post - V3(0, 0.6, 0), post + V3(0, 3.2, 0), 0.4, 0.4, P.woodDark, M.Wood)
			deco(
				beam(
					f,
					"Gotppi",
					post + V3(0, 2.6, 0),
					V3(x, H(x, z) + 7.6, z):Lerp(post + V3(0, 2.6, 0), 0.5),
					0.08,
					0.08,
					C.straw,
					M.Fabric
				)
			)
		end
	end
	do
		local x, z = polar(118, 31)
		if free(x, z, 5) then
			camel(f, V3(x, H(x, z), z), V3(ox, 0, oz), true, rng)
		end
	end
	-- 길머리 이름 비석 (길 쪽을 본다)
	do
		local x, z = polar(76, 35)
		if free(x, z, 3) then
			Kit.stele(f, V3(x, lowAt(x, z, 2) + 0.4, z), "녹주", V3(x + 8, 0, z + 20), rgb(196, 176, 140))
		end
	end
	-- 푸른 덤불 (협죽도: 둘은 꽃이 핀다)과 풀
	local green = { P.leafDeep, P.leaf, P.leafLight }
	local taken = {}
	local box = { ox - 34, ox + 34, oz - 34, oz + 34 }
	local function ring(x: number, z: number, pad: number): boolean
		local d = sqrt((x - ox) ^ 2 + (z - oz) ^ 2)
		if d < 18.5 or d > 33 or H(x, z) > 24 or not free(x, z, pad) then
			return false
		end
		for _, t in tents do
			local tx, tz = polar(t[1], t[2])
			if (x - tx) ^ 2 + (z - tz) ^ 2 < (8.5 + pad) ^ 2 then
				return false
			end
		end
		return (x - wellX) ^ 2 + (z - wellZ) ^ 2 > (6 + pad) ^ 2
	end
	for i, q in
		scatter(rng, 7, box, 7, function(x, z)
			return ring(x, z, 1.5)
		end, taken)
	do
		Build.shrub(f, V3(q[1], H(q[1], q[2]) - 0.3, q[2]), rng, {
			size = rng(2.4, 3.6),
			blobs = 2,
			leaves = green,
			flowers = if i == 1 then rgb(232, 140, 170) else nil,
		})
	end
	for _, q in
		scatter(rng, 6, box, 4, function(x, z)
			return ring(x, z, 0.5)
		end, taken)
	do
		tuft(f, q[1], q[2], rng, P.leafLight)
	end
	return f
end

-- 소금벌 ---------------------------------------------------------------------------------
-- 옛 바다가 마른 흰 벌 (지형 높이 6, Salt 재질). 껍질이 갈라져 솟은 육각 무늬, 소금 결정 무리, 하늘이 비치는 얕은 거울 못.
-- 북동쪽 가장자리에 소금 일꾼 자리: 둑으로 나눈 소금밭 (물 고인 칸, 소금 앉은 칸), 소금 더미와 고무래, 소금막, 소금 수레.
local MIRROR = rgb(176, 204, 220)

-- 육각 무늬 한 무리: 가운데 칸과 둘레 여섯 칸 (꼭짓점을 조금씩 흔들되 이웃 칸과 같은 자리를 쓴다)
local function saltPolygons(parent: Instance, cx: number, cz: number, R: number, rng)
	local m = model(parent, "소금 껍질")
	local verts = {}
	local function vert(x: number, z: number): Vector3
		local key = string.format("%d,%d", floor(x * 2 + 0.5), floor(z * 2 + 0.5))
		local v = verts[key]
		if not v then
			local jx, jz = x + rng(-0.6, 0.6), z + rng(-0.6, 0.6)
			v = V3(jx, H(jx, jz) + 0.12, jz)
			verts[key] = v
		end
		return v
	end
	local done = {}
	local centers = { { cx, cz } }
	local step = sqrt(3) * R
	for k = 0, 5 do
		local a = rad(k * 60)
		table.insert(centers, { cx + cos(a) * step, cz + sin(a) * step })
	end
	for _, c in centers do
		for k = 0, 5 do
			local a0, a1 = rad(30 + k * 60), rad(90 + k * 60)
			local va = vert(c[1] + cos(a0) * R, c[2] + sin(a0) * R)
			local vb = vert(c[1] + cos(a1) * R, c[2] + sin(a1) * R)
			local mx, mz = (va.X + vb.X) / 2, (va.Z + vb.Z) / 2
			local key = string.format("%d,%d", floor(mx + 0.5), floor(mz + 0.5))
			if not done[key] then
				done[key] = true
				local d = (vb - va).Unit
				deco(
					beam(m, "Teol", va - d * 0.3, vb + d * 0.3, 0.75, rng(0.3, 0.45), jitter(C.salt, rng, 0.02), M.Salt)
				)
			end
		end
	end
	return m
end

-- 소금 결정 무리: 흰 덩이 하나에 비스듬히 솟은 결정 넷
local function saltCrystals(parent: Instance, x: number, z: number, rng)
	local m = model(parent, "소금 결정")
	local g = H(x, z)
	block(
		m,
		"Deongi",
		V3(rng(2, 2.8), 0.8, rng(1.8, 2.6)),
		CFrame.new(x, g + 0.2, z) * CFrame.Angles(0, rng(0, TAU), 0),
		C.saltShade,
		M.Salt
	)
	for k = 1, 4 do
		local a = rng(0, TAU)
		local h = rng(1.6, 3.6)
		local base = V3(x + cos(a) * rng(0.2, 0.8), g, z + sin(a) * rng(0.2, 0.8))
		local tip = base + V3(cos(a) * h * 0.35, h, sin(a) * h * 0.35)
		local w = rng(0.5, 0.9)
		local p = beam(
			m,
			"Gyeoljeong",
			base - V3(0, 0.4, 0),
			tip,
			w,
			w,
			if k == 2 then rgb(240, 222, 222) else C.salt,
			M.Glass
		)
		p.Transparency = 0.15
	end
	return m
end

-- 거울 못: 겹친 둥근 판 둘 (하늘빛, 반쯤 비친다). 둘레에서 가장 판판한 자리를 골라, 윗면을 가장 높은 땅에 맞춘다
local function mirrorPool(parent: Instance, x: number, z: number, r: number, rng)
	local m = model(parent, "거울 못")
	local best = math.huge
	local bx, bz = x, z
	for dx = -15, 15, 5 do
		for dz = -15, 15, 5 do
			local rl = relief(x + dx, z + dz, r) + relief(x + dx, z + dz, r * 0.5)
			if rl < best then
				best, bx, bz = rl, x + dx, z + dz
			end
		end
	end
	local top = max(highAt(bx, bz, r), highAt(bx, bz, r * 0.5)) + 0.05
	local low = min(lowAt(bx, bz, r), lowAt(bx, bz, r * 0.5)) - 0.1
	for k = 1, 2 do
		local a = rng(0, TAU)
		local px = bx + (if k == 1 then 0 else cos(a) * r * 0.45)
		local pz = bz + (if k == 1 then 0 else sin(a) * r * 0.45)
		local d = if k == 1 then r * 2 else r * rng(1.1, 1.5)
		local y = top + (k - 1) * 0.01
		local p = cyl(m, "Mul", V3(px, low, pz), V3(px, y, pz), d, MIRROR, M.Glass)
		p.Transparency = 0.3
		p.Reflectance = 0.25
		p.CanCollide = false
	end
	return m
end

-- 소금 일꾼 자리: look 의 앞(-Z)이 소금밭 쪽
local function saltWorks(parent: Instance, x: number, z: number, toward: Vector3, rng)
	local m = model(parent, "소금 일꾼 자리")
	local g = H(x, z)
	local look = face(V3(x, g, z), V3(toward.X, g, toward.Z))
	local dike = rgb(150, 128, 104)
	-- 소금밭: 셋 × 둘 칸, 둑 (흙)
	local pc = look:PointToWorldSpace(V3(0, 0, -16))
	local pan = look * CFrame.new(0, max(highAt(pc.X, pc.Z, 12), highAt(pc.X, pc.Z, 6)) - g, -16)
	for i = 0, 3 do
		block(m, "Duk", V3(0.9, 1.3, 14.9), pan * CFrame.new(-12 + i * 8, -0.15, 0), dike, M.Ground)
	end
	for j = 0, 2 do
		block(m, "Duk", V3(24.9, 1.3, 0.9), pan * CFrame.new(0, -0.15, -7 + j * 7), dike, M.Ground)
	end
	for i = 0, 2 do
		for j = 0, 1 do
			local c = pan * CFrame.new(-8 + i * 8, 0.12, -3.5 + j * 7)
			if (i + j) % 2 == 0 then
				local p = block(m, "Mul", V3(7.1, 0.6, 6.1), c * CFrame.new(0, -0.25, 0), MIRROR, M.Glass)
				p.Transparency = 0.3
				p.Reflectance = 0.2
				p.CanCollide = false
			else
				block(m, "Sogeum", V3(7.1, 0.7, 6.1), c * CFrame.new(0, -0.2, 0), C.salt, M.Salt)
			end
		end
	end
	-- 소금 더미 (뿔) 넷과 고무래
	local piles = { { -9, -2.5, 3.4 }, { -4, -0.5, 4.2 }, { 4.5, -1.5, 3.6 }, { 9.5, -3, 2.8 } }
	for _, q in piles do
		local c = look:PointToWorldSpace(V3(q[1], 0, q[2]))
		Build.pyramid(m, "Sogeumdeomi", V3(c.X, H(c.X, c.Z) - 0.1, c.Z), q[3] * 1.5, q[3], rng(0, 1.5), C.salt, M.Salt)
	end
	local function rake(a: Vector3, b: Vector3)
		beam(m, "Jaru", a, b, 0.22, 0.22, P.wood, M.Wood)
		local d = (b - a).Unit
		local side = V3(-d.Z, 0, d.X)
		block(m, "Gomurae", V3(2.2, 0.45, 0.3), face(b, b + side) * CFrame.Angles(0, rad(90), 0), P.woodDark, M.Wood)
	end
	do
		local a = look:PointToWorldSpace(V3(-4, 3.2, 2.6))
		local b = look:PointToWorldSpace(V3(-4.6, 0.25, -1.6))
		rake(a, V3(b.X, H(b.X, b.Z) + 0.25, b.Z))
		local c = look:PointToWorldSpace(V3(2, 0, -9))
		local d = look:PointToWorldSpace(V3(6.5, 0, -10.2))
		rake(V3(c.X, H(c.X, c.Z) + 0.3, c.Z), V3(d.X, H(d.X, d.Z) + 0.3, d.Z))
	end
	-- 소금막: 앞이 높은 외쪽 지붕 (짚), 뒤 엮은 벽, 안에 소금 자루와 바구니
	local hut = look * CFrame.new(0, 0, 9)
	local function hp(px: number, py: number, pz: number): Vector3
		return hut:PointToWorldSpace(V3(px, py, pz))
	end
	for _, q in { { -4, -3, 4.6 }, { 4, -3, 4.6 }, { -4, 3, 3.0 }, { 4, 3, 3.0 } } do
		beam(m, "Gidung", hp(q[1], -0.6, q[2]), hp(q[1], q[3], q[2]), 0.4, 0.4, P.wood, M.Wood)
	end
	local X = hut.RightVector
	local back = -hut.LookVector
	Build.slab(
		m,
		"Jibung",
		hp(-4.8, 4.8, -3.8),
		X * 9.6,
		back * 7.8 + V3(0, -1.75, 0),
		0.4,
		Vector3.yAxis,
		C.straw,
		M.Grass
	)
	block(m, "Byeok", V3(8.2, 3.2, 0.3), hut * CFrame.new(0, 1.2, 3.1), rgb(150, 126, 88), M.WoodPlanks)
	for k = 0, 2 do
		block(
			m,
			"Sogeumjaru",
			V3(1.5, 1.0, 2.2),
			hut
				* CFrame.new(-2.6 + k * 1.7, 0.4 + (if k == 1 then 0.9 else 0), 1.6)
				* CFrame.Angles(0, rng(-0.2, 0.2), 0),
			jitter(C.felt, rng, 0.04),
			M.Fabric
		)
	end
	for _, q in { { 2.6, 0.2 }, { 3.0, -2.2 } } do
		local c = hp(q[1], 0, q[2])
		cyl(m, "Bagani", c - V3(0, 0.3, 0), c + V3(0, 1.1, 0), 1.6, C.straw, M.Fabric)
		cyl(m, "Sogeum", c + V3(0, 1.05, 0), c + V3(0, 1.2, 0), 1.4, C.salt, M.Salt)
	end
	-- 소금 실은 수레
	local cartCf = look * CFrame.new(-11, 0, 6) * CFrame.Angles(0, rad(-35), 0)
	Build.cart(m, cartCf)
	block(m, "Sogeumjim", V3(3.2, 1.0, 4.4), cartCf * CFrame.new(0, 2.6, 0), C.salt, M.Salt)
	return m
end

local function saltFlat(parent: Instance, rng)
	local f = folder(parent, "소금벌")
	saltWorks(f, -1236, 738, V3(-1260, 0, 752), rng)
	local pools = { { -1330, 745, 14 }, { -1372, 800, 11 }, { -1296, 815, 12 }, { -1396, 736, 9 } }
	for _, q in pools do
		mirrorPool(f, q[1], q[2], q[3], rng)
	end
	saltPolygons(f, -1346, 782, 5.5, rng)
	saltPolygons(f, -1288, 770, 5, rng)
	local taken = {
		{ -1250, 742, 26 },
		{ -1346, 782, 20 },
		{ -1288, 770, 18 },
	}
	for _, q in pools do
		table.insert(taken, { q[1], q[2], q[3] + 5 })
	end
	for _, q in
		scatter(rng, 7, { -1420, -1210, 670, 860 }, 22, function(x, z)
			return regionId(x, z) == "salt" and H(x, z) < 7.5 and clearOf(x, z, 3)
		end, taken)
	do
		saltCrystals(f, q[1], q[2], rng)
	end
	return f
end

function Region.build(root: Instance, rng: (number, number) -> number)
	local top = folder(root, "서남")
	local loess = folder(top, "황구")
	-- 탁상 바위 다섯 (넷째는 굴집 마을이 기댄다)
	for i, b in Land.BUTTES do
		local cx, cz = b[1], b[2]
		if H(cx, cz) < b[4] - 4 then
			standingButte(loess, b, rng)
		elseif i == 4 then
			butte(loess, b, rng, { 232, 308, 27 })
		else
			butte(loess, b, rng)
		end
	end
	earthAltar(loess, rng)
	caveHamlet(loess, rng)
	loessNature(loess, rng)
	canyon(top, rng)
	mesa(top, rng)
	desert(top, rng)
	ruins(top, rng)
	oasis(top, rng)
	saltFlat(top, rng)
end

return Region
