-- 남쪽 땅: 홍로성(불 다루는 장인들의 성)과 대용광로, 주염산, 벽계협, 무택과 무택 고탑, 남명대 둘레, 백사포, 검총.
-- World.luau 가 build(root, rng) 를 부른다. 땅 모양은 Shared.Land, 자리는 WorldSites (허브가 놓는 과업 자리·진·영맥 둘레는 비운다).
-- 짓는 모양은 WorldBuild(Build), 땅 위 자리 잡기는 WorldKit(Kit). CFrame.lookAt 은 쓰지 않는다 (Lune 에서 Z 가 뒤집힌다: Build.face).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")

local Land = require(Shared.Land)
local Build = require(script.Parent.WorldBuild)
local Kit = require(script.Parent.WorldKit)
local Sites = require(script.Parent.WorldSites)

local Region = {}

local P = Build.P
local V3 = Vector3.new
local CF = CFrame.new
local rad = math.rad
local huge = math.huge
local block, beam, cyl, ball, wedge = Build.block, Build.beam, Build.cyl, Build.ball, Build.wedge
local deco = Build.deco
local face = Build.face
local M = Enum.Material

-- 빛깔 ---------------------------------------------------------------------------------
local C = {
	brick = Color3.fromRGB(132, 72, 54), -- 노 벽돌
	brickDark = Color3.fromRGB(92, 52, 42),
	iron = Color3.fromRGB(54, 52, 52),
	soot = Color3.fromRGB(40, 36, 34),
	glow = Color3.fromRGB(255, 118, 40), -- 숯불, 쇳물
	glowHot = Color3.fromRGB(255, 170, 70),
	lava = Color3.fromRGB(255, 96, 30),
	lavaDeep = Color3.fromRGB(214, 58, 26),
	basalt = Color3.fromRGB(56, 52, 52),
	basaltLight = Color3.fromRGB(78, 72, 70),
	ash = Color3.fromRGB(96, 90, 86),
	charred = Color3.fromRGB(38, 34, 32),
	wallStone = Color3.fromRGB(174, 164, 146),
	pave = Color3.fromRGB(150, 142, 128),
	cobble = Color3.fromRGB(132, 126, 116),
	dirt = Color3.fromRGB(138, 108, 76),
	sand = Color3.fromRGB(226, 214, 186),
	plank = Color3.fromRGB(122, 92, 64),
	plankOld = Color3.fromRGB(104, 92, 78),
	rope = Color3.fromRGB(176, 152, 108),
	thatch = Color3.fromRGB(176, 146, 92), -- 초가 이엉
	thatchDark = Color3.fromRGB(138, 112, 70),
	mudWall = Color3.fromRGB(196, 172, 134), -- 흙벽
	rust = Color3.fromRGB(122, 70, 44),
	rustDark = Color3.fromRGB(86, 56, 42),
	moss = Color3.fromRGB(84, 112, 62),
	fern = Color3.fromRGB(76, 120, 60),
	marshWater = Color3.fromRGB(46, 74, 66),
	lily = Color3.fromRGB(74, 120, 62),
	reedDry = Color3.fromRGB(160, 150, 96),
	deadWood = Color3.fromRGB(96, 88, 78),
	cloth = Color3.fromRGB(150, 54, 44), -- 홍로성 깃발
	clothDark = Color3.fromRGB(110, 40, 36),
	clothWhite = Color3.fromRGB(226, 220, 204),
	foam = Color3.fromRGB(236, 244, 248),
	net = Color3.fromRGB(110, 104, 84),
	fish = Color3.fromRGB(176, 180, 182),
	boat = Color3.fromRGB(116, 88, 62),
}

-- 땅 -----------------------------------------------------------------------------------

local function gy(x: number, z: number): number
	return Land.surface(x, z)
end

-- 빛깔 조금 흔들기
local function jitter(color: Color3, rng, amount: number): Color3
	local k = 1 + rng(-amount, amount)
	return Color3.new(math.clamp(color.R * k, 0, 1), math.clamp(color.G * k, 0, 1), math.clamp(color.B * k, 0, 1))
end

-- look 기준 네모(가로 w, 세로 d, 가운데에서 dz 만큼 민) 안 가장 낮은·높은 땅
local function rectSpan(look: CFrame, w: number, d: number, dz: number?): (number, number)
	local low, high = huge, -huge
	for _, u in { -0.5, -0.25, 0, 0.25, 0.5 } do
		for _, v in { -0.5, 0, 0.5 } do
			local p = look:PointToWorldSpace(V3(u * w, 0, v * d + (dz or 0)))
			local h = gy(p.X, p.Z)
			low, high = math.min(low, h), math.max(high, h)
		end
	end
	return low, high
end

local function spanAt(x: number, z: number, r: number): (number, number)
	return Kit.spanAt(x, z, r)
end

-- 비워 둘 자리 (허브가 놓는 진·과업 자리·영맥) ------------------------------------------------
local CLEAR = {}
local function addClear(x: number, z: number, r: number)
	table.insert(CLEAR, { x = x, z = z, r = r })
end
for _, s in Sites.WAYPOINTS do
	addClear(s.x, s.z, 9)
end
for _, s in Sites.TASK do
	addClear(s.x, s.z, math.max(7, s.radius or 0))
end
for _, s in Sites.VEINS do
	addClear(s.x, s.z, 7)
end
-- (x, z) 둘레 r 이 비워 둘 자리와 겹치는가
local function blocked(x: number, z: number, r: number?): boolean
	for _, c in CLEAR do
		local dx, dz = x - c.x, z - c.z
		local rr = c.r + (r or 0)
		if dx * dx + dz * dz < rr * rr then
			return true
		end
	end
	return false
end

-- 길 (Land.ROADS 와 깎은 길) 곁인가
local ROADS = {}
for _, road in Land.ROADS do
	table.insert(ROADS, Land.poly(road))
end
local function nearRoad(x: number, z: number, w: number): boolean
	for _, road in ROADS do
		if Land.polyDist(x, z, road, w) < w then
			return true
		end
	end
	for _, bench in Land.BENCHES do
		if Land.polyDist(x, z, bench, w) < w then
			return true
		end
	end
	if Land.spiralAt(x, z, Land.VOLCANO_TRAIL) < w then
		return true
	end
	return false
end

-- 지형 물 위인가
local function wet(x: number, z: number): boolean
	local h = Land.height(x, z)
	local w = Land.water(x, z, h)
	return w ~= nil and w > h + 0.2
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

local function kp(t: number, v: number)
	return NumberSequenceKeypoint.new(t, v)
end

-- 연기 (굴뚝, 김 오르는 틈). 원기둥(축이 X) 에 달 때는 dir = Right
local function smoke(part: BasePart, opts)
	opts = opts or {}
	local e = Instance.new("ParticleEmitter")
	e.Name = "Yeongi"
	e.Texture = "rbxasset://textures/particles/smoke_main.dds"
	e.Rate = opts.rate or 2.5
	e.Lifetime = NumberRange.new(opts.life or 5, (opts.life or 5) * 1.6)
	e.Speed = NumberRange.new(opts.speed or 2.5, (opts.speed or 2.5) * 1.6)
	e.SpreadAngle = Vector2.new(opts.spread or 12, opts.spread or 12)
	e.Size = NumberSequence.new({ kp(0, opts.size0 or 1.8), kp(1, opts.size1 or 8) })
	e.Transparency = NumberSequence.new({ kp(0, opts.alpha or 0.55), kp(0.7, 0.8), kp(1, 1) })
	e.Color = ColorSequence.new(opts.color or Color3.fromRGB(78, 72, 70))
	e.Acceleration = opts.accel or V3(0.8, 0.6, 0.4)
	e.Drag = opts.drag or 0.3
	e.RotSpeed = NumberRange.new(-20, 20)
	e.Rotation = NumberRange.new(0, 360)
	e.LightEmission = opts.light or 0
	if opts.dir then
		e.EmissionDirection = opts.dir
	end
	e.Parent = part
	return e
end

-- 불티 (노 위, 쇳물)
local function sparks(part: BasePart, rate: number, dir: Enum.NormalId?)
	local e = Instance.new("ParticleEmitter")
	e.Name = "Bulti"
	e.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	e.Rate = rate
	e.Lifetime = NumberRange.new(0.8, 1.6)
	e.Speed = NumberRange.new(4, 9)
	e.SpreadAngle = Vector2.new(25, 25)
	e.Acceleration = V3(0, -6, 0)
	e.Size = NumberSequence.new({ kp(0, 0.35), kp(1, 0) })
	e.Color = ColorSequence.new(Color3.fromRGB(255, 190, 90), Color3.fromRGB(255, 90, 30))
	e.LightEmission = 1
	if dir then
		e.EmissionDirection = dir
	end
	e.Parent = part
	return e
end

local function glowLight(part: BasePart, color: Color3, range: number, brightness: number)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = false
	l.Parent = part
	return l
end

-- 빛나는 판 (네온, 그림자·충돌 없이)
local function neon(parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3): BasePart
	local p = deco(block(parent, name, size, cf, color, M.Neon))
	p.CastShadow = false
	return p
end

-- 땅을 따라 까는 판: a→b 를 마디로 나눠 마디 끝마다 땅 높이(가로 양끝 포함 가장 높은 곳)에 맞춘다. 윗면이 땅보다 lift 위
local function pave(
	parent: Instance,
	a: Vector2,
	b: Vector2,
	width: number,
	color: Color3,
	material: Enum.Material,
	opts
)
	opts = opts or {}
	local len = (b - a).Magnitude
	local n = math.max(1, math.ceil(len / (opts.seg or 12)))
	local lift = opts.lift or 0.22
	local t = opts.thick or 2
	local dir = (b - a).Unit
	local nx, nz = -dir.Y, dir.X
	local pts = {}
	for i = 0, n do
		local q = a:Lerp(b, i / n)
		local h = opts.y or gy(q.X, q.Y)
		if not opts.y then
			for _, s in { -0.45, 0.45 } do
				h = math.max(h, gy(q.X + nx * width * s, q.Y + nz * width * s))
			end
		end
		pts[i] = V3(q.X, h + lift - t / 2, q.Y)
	end
	local out = {}
	for i = 1, n do
		local d = (pts[i] - pts[i - 1]).Unit
		local p = beam(parent, opts.name or "Gil", pts[i - 1] - d * 0.3, pts[i] + d * 0.3, width, t, color, material)
		table.insert(out, p)
	end
	return out
end

-- 모델 하나를 피벗 둘레로 돌린다 (Lune 에 PivotTo 가 없어 부품마다)
local function transformModel(m: Instance, pivot: CFrame, by: CFrame)
	local k = pivot * by * pivot:Inverse()
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			d.CFrame = k * d.CFrame
		end
	end
end

-- 보이지 않거나 맞지 않는 부품 덜기: 닫힌 집의 마루 바닥, 맞배지붕 네 귀의 망와(우진각·팔작에만 있다), 난간 동자
local function prune(m: Instance, gable: boolean, open: boolean)
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			local n = d.Name
			if (n == "Floor" and not open) or n == "Dongja" then
				d:Destroy()
			elseif gable and n == "Mangwa" and math.abs(d.Size.Z - 0.35) < 0.01 then
				d:Destroy()
			end
		end
	end
end

-- 땅에 흩어진 조각 (기와, 돌): 아무 방향으로 돌리고 조금 기울인다
local function tiltedPiece(parent: Instance, c: Vector3, size: Vector3, rng, color: Color3, material)
	return block(
		parent,
		"Jogak",
		size,
		CF(c) * CFrame.Angles(rng(-0.25, 0.25), rng(0, math.pi), rng(-0.25, 0.25)),
		color,
		material
	)
end

-- 바닥이 땅에 맞는 기와집 한 채. x, z 에 서서 toward 를 본다. 기단을 비탈 높은 쪽까지 올린다
local function houseAt(parent: Instance, x: number, z: number, toward: Vector3, opts)
	local bays = opts.bays or { 3, 2 }
	local bay = opts.bay or 5
	local W, D = bays[1] * bay + 4.4, bays[2] * bay + 4.4
	local look = face(V3(x, 0, z), toward)
	local low, high = rectSpan(look, W, D + 2, -1)
	opts.plinth = (opts.plinth or 1.6) + (high - low)
	local cf = CF(x, low, z) * (look - look.Position)
	local m, info = Build.house(parent, cf, opts)
	prune(m, (opts.roof or "paljak") == "gable", opts.open == true)
	return m, info
end

-- 초가: 이엉 지붕 (Build.roof 우진각, 귀를 들지 않고 마루도 이엉 빛), 흙벽, 낮은 돌 기단. cf 는 기단 밑 가운데, 앞 -Z
local function thatchHouse(parent: Instance, cf: CFrame, w: number, d: number, opts)
	opts = opts or {}
	local m = model(parent, opts.name or "초가")
	local wallH = opts.wallH or 6.2
	local plinth = opts.plinth or 1
	block(
		m,
		"Gidan",
		V3(w + 2.4, plinth + 0.6, d + 2.4),
		cf * CF(0, (plinth - 0.6) / 2, 0),
		P.granite:Lerp(C.dirt, 0.3),
		M.Cobblestone
	)
	block(m, "Byeok", V3(w, wallH, d), cf * CF(0, plinth + wallH / 2, 0), opts.wall or C.mudWall, M.Plaster)
	local bays = opts.bays or 2
	for i = 0, bays do
		local x = -w / 2 + i * w / bays
		for _, z in (if i == 0 or i == bays then { -d / 2, d / 2 } else { -d / 2 }) do
			beam(
				m,
				"Gidung",
				cf:PointToWorldSpace(V3(x, plinth, z)),
				cf:PointToWorldSpace(V3(x, plinth + wallH + 0.2, z)),
				0.75,
				0.75,
				P.wood,
				M.Wood
			)
		end
	end
	block(m, "Dori", V3(w + 0.9, 0.7, d + 0.9), cf * CF(0, plinth + wallH - 0.1, 0), P.woodDark, M.Wood)
	-- 문과 창 (앞 -Z)
	local bw = w / bays
	block(m, "Mun", V3(2.6, 4.4, 0.3), cf * CF(-w / 2 + bw / 2, plinth + 2.4, -d / 2 - 0.05), P.woodDark, M.Wood)
	block(
		m,
		"Hanji",
		V3(2.0, 3.6, 0.32),
		cf * CF(-w / 2 + bw / 2, plinth + 2.5, -d / 2 - 0.06),
		P.hanji,
		M.SmoothPlastic
	)
	if bays > 1 then
		block(m, "Chang", V3(2.4, 1.8, 0.3), cf * CF(w / 2 - bw / 2, plinth + 3.8, -d / 2 - 0.05), P.woodDark, M.Wood)
		block(
			m,
			"Hanji",
			V3(1.9, 1.4, 0.32),
			cf * CF(w / 2 - bw / 2, plinth + 3.8, -d / 2 - 0.06),
			P.hanji,
			M.SmoothPlastic
		)
	end
	-- 툇마루
	block(m, "Toemaru", V3(w - 0.4, 0.4, 1.6), cf * CF(0, plinth + 0.6, -d / 2 - 0.85), P.wood, M.WoodPlanks)
	local eave = 2.4
	local spec = {
		ex = w / 2 + eave,
		ez = d / 2 + eave,
		eave = eave,
		bands = 1,
		kind = "hip",
		pitchLow = 26,
		pitchHigh = 38,
		lift = 0,
		flare = 0,
		segs = 1,
		t = 1.1,
		color = opts.thatch or C.thatch,
		material = M.Grass,
		ridgeColor = C.thatchDark,
	}
	local _, _, hh, pitches = Build.profile(spec)
	local under = hh[1] - spec.t / math.cos(rad(pitches[1]))
	local top = plinth + wallH + 0.25
	local r = Build.roof(m, cf * CF(0, top - under, 0), spec)
	-- 이엉에는 망와·양성이 없다. 마루는 이엉 빛 용마름으로
	for _, d2 in r.model:GetChildren() do
		if d2.Name == "Mangwa" or d2.Name == "Yangseong" or d2.Name == "Jeolbyeong" then
			d2:Destroy()
		elseif d2.Name == "Maru" and d2:IsA("BasePart") then
			d2.Material = M.Grass
		end
	end
	return m
end

-- 사당 (1칸 법당 모양, 축대 위). 앞(-Z)이 toward. 화구 둘레·해신당이 같이 쓴다
local function smallShrine(parent: Instance, x: number, z: number, toward: Vector3, opts)
	opts = opts or {}
	local m = model(parent, opts.name or "사당")
	local look = face(V3(x, 0, z), toward)
	local size = opts.footing or 13
	local low, high = rectSpan(look, size, size)
	local top = high + (opts.raise or 0.4)
	block(
		m,
		"Chukdae",
		V3(size + 0.5, top - low + 3, size + 0.5),
		look * CF(0, (top + low - 3) / 2, 0),
		opts.stone or C.ash,
		opts.stoneMat or M.Slate
	)
	block(m, "Gapseok", V3(size + 1.1, 0.6, size + 1.1), look * CF(0, top - 0.1, 0), P.graniteDark, M.Granite)
	local h = Build.house(m, CF(x, top, z) * (look - look.Position), {
		bays = { 1, 1 },
		bay = opts.bay or 7,
		pillarH = 6.4,
		plinth = 1.0,
		eave = 3,
		style = "temple",
		detail = 0,
		roof = "hip",
		bands = 1,
		name = "사당",
		noSteps = true,
		roofColor = opts.roofColor,
	})
	prune(h, false, false)
	return m, look, top
end

-- 땅에 맞춘 초가 한 채: x, z 에 서서 toward 를 본다 (비탈이면 기단을 높인다)
local function thatchAt(parent: Instance, x: number, z: number, toward: Vector3, w: number, d: number, opts)
	opts = opts or {}
	local look = face(V3(x, 0, z), toward)
	local low, high = rectSpan(look, w + 2.6, d + 4.6, -0.8)
	opts.plinth = (opts.plinth or 0.8) + (high - low)
	return thatchHouse(parent, CF(x, low, z) * (look - look.Position), w, d, opts)
end

-- 홍로성 ---------------------------------------------------------------------------------

local CITY = Land.CITY
local CX, CZ, HALF, FLOOR = CITY.x, CITY.z, CITY.half, CITY.height
local WALL_TOP = FLOOR + 15

-- 성벽 한 줄: a→b (오른쪽이 바깥). 땅이 기우므로 마디로 나눠 마디마다 밑을 가장 낮은 땅에 맞추고 윗면은 WALL_TOP
local function wallRun(parent: Instance, ax: number, az: number, bx: number, bz: number)
	local a, b = Vector2.new(ax, az), Vector2.new(bx, bz)
	local len = (b - a).Magnitude
	local n = math.max(1, math.ceil(len / 48))
	local dir = (b - a).Unit
	for i = 0, n - 1 do
		local p, q = a:Lerp(b, i / n), a:Lerp(b, (i + 1) / n)
		local low = huge
		for k = 0, 6 do
			local s = p:Lerp(q, k / 6)
			for _, off in { -3.5, 0, 3.5 } do
				low = math.min(low, Land.height(s.X - dir.Y * off, s.Y + dir.X * off))
			end
		end
		local base = low - 0.4
		-- 마디끼리 조금 겹치게 (틈이 없게)
		local p2, q2 = p - dir * (if i == 0 then 0 else 0.3), q + dir * (if i == n - 1 then 0 else 0.3)
		local w = Build.cityWall(parent, V3(p2.X, base, p2.Y), V3(q2.X, base, q2.Y), {
			height = WALL_TOP - base,
			thick = 5,
			merlon = 7.6,
			gap = 1.5,
			color = C.wallStone,
		})
		-- 긴 성벽의 타구 갓돌은 덜고 타구를 조금 높인다 (부품 절반)
		for _, d in w:GetChildren() do
			if d.Name == "Gat" then
				d:Destroy()
			elseif d.Name == "Tagu" and d:IsA("BasePart") then
				d.Size += V3(0, 0.35, 0)
				d.CFrame *= CF(0, 0.175, 0)
			end
		end
	end
end

-- 여장만 (문 위, 치성 위): 선 a→b 위에 타구
local function parapet(parent: Instance, a: Vector3, b: Vector3, merlon: number?, gap: number?)
	local mw, g = merlon or 6.4, gap or 1.5
	local len = (b - a).Magnitude
	local cf = face((a + b) / 2, b)
	local count = math.floor((len + g) / (mw + g))
	local start = -len / 2 + (len - (count * (mw + g) - g)) / 2
	for i = 0, count - 1 do
		local z = start + i * (mw + g) + mw / 2
		block(parent, "Tagu", V3(1, 2.6, mw), cf * CF(0, 1.3, z), Color3.fromRGB(96, 96, 100), M.Brick)
		block(parent, "Gat", V3(1.4, 0.35, mw + 0.2), cf * CF(0, 2.75, z), P.giwaDark, M.Slate)
	end
end

-- 치성 (성 모퉁이 네모 망대): 성벽보다 2 높고 둘레에 여장, 깃발
local function bastion(parent: Instance, x: number, z: number)
	local m = model(parent, "치성")
	local s = 13
	local low = math.min(spanAt(x, z, s * 0.7))
	local top = WALL_TOP + 2
	block(
		m,
		"Mom",
		V3(s + 1.2, (top - low) * 0.45, s + 1.2),
		CF(x, low + (top - low) * 0.225 - 0.8, z),
		C.wallStone,
		M.Cobblestone
	)
	block(m, "Mom", V3(s, top - low, s), CF(x, (top + low) / 2, z), C.wallStone, M.Cobblestone)
	block(m, "Gapseok", V3(s + 0.6, 0.5, s + 0.6), CF(x, top + 0.05, z), P.graniteDark, M.Granite)
	local h = s / 2 - 0.5
	local corners = { V3(x - h, top, z - h), V3(x + h, top, z - h), V3(x + h, top, z + h), V3(x - h, top, z + h) }
	for i = 1, 4 do
		parapet(m, corners[i], corners[i % 4 + 1], 6, 6)
	end
	Build.banner(m, V3(x, top, z), V3(x + 1, top, z + 1), C.cloth, 9)
	return m
end

-- 문루 없는 무지개문 + 위에 여장 + 열어 둔 문짝
local function plainGate(parent: Instance, cf: CFrame, H: number, name: string)
	local m = Build.gatehouse(
		parent,
		cf,
		{
			height = H,
			thick = 6,
			span = 20,
			radius = 5,
			spring = 6.5,
			loft = false,
			name = name,
			color = C.wallStone,
			voussoirs = 7,
		}
	)
	parapet(m, cf:PointToWorldSpace(V3(-10, H, -2.5)), cf:PointToWorldSpace(V3(10, H, -2.5)))
	for _, s in { 1, -1 } do
		block(m, "Munjjak", V3(4.6, 10, 0.5), cf * CF(s * 7.4, 5.0, 3.3), P.woodDark, M.WoodPlanks)
	end
	return m
end

-- 성문 현판: 바깥 면, 홍예 위
local function gateBoard(parent: Instance, cf: CFrame, y: number, text: string)
	local board = block(parent, "Hyeonpan", V3(7.2, 2.4, 0.4), cf * CF(0, y, -3.25), P.meok, M.Wood)
	block(parent, "Te", V3(7.9, 3.0, 0.3), cf * CF(0, y, -3.12), P.hwang, M.Wood)
	Kit.engrave(board, text, "Front", false)
	return board
end

-- 문길 바닥: 성 밖 땅에서 성 안 땅까지
local function gateRamp(parent: Instance, cf: CFrame, outLen: number, inLen: number)
	local a = cf:PointToWorldSpace(V3(0, 0, -outLen))
	local b = cf:PointToWorldSpace(V3(0, 0, inLen))
	pave(parent, Vector2.new(a.X, a.Z), Vector2.new(b.X, b.Z), 9, C.pave, M.Pavement, { seg = 6, name = "Mungil" })
end

-- 대장간: 앞이 트인 맞배 헛간, 뒤에 화덕과 굴뚝. cf 는 바닥 가운데, 앞 -Z
local function forge(parent: Instance, cf: CFrame, rng)
	local m = model(parent, "대장간")
	local w, d, h = 12, 9, 7.2
	block(m, "Badak", V3(w + 1.2, 1.4, d + 1.2), cf * CF(0, -0.1, 0), P.graniteDark, M.Slate)
	local y0 = 0.6
	-- 뒤 벽(돌) 과 왼쪽 낮은 벽
	block(
		m,
		"Dwitbyeok",
		V3(w, h, 0.9),
		cf * CF(0, y0 + h / 2, d / 2 - 0.45),
		C.wallStone:Lerp(C.soot, 0.25),
		M.Cobblestone
	)
	block(
		m,
		"Yeopbyeok",
		V3(0.9, 2.4, d - 1),
		cf * CF(-w / 2 + 0.45, y0 + 1.2, 0.2),
		C.wallStone:Lerp(C.soot, 0.2),
		M.Cobblestone
	)
	for _, x in { -w / 2, 0, w / 2 } do
		beam(
			m,
			"Gidung",
			cf:PointToWorldSpace(V3(x, y0, -d / 2)),
			cf:PointToWorldSpace(V3(x, y0 + h + 0.4, -d / 2)),
			0.8,
			0.8,
			P.woodDark,
			M.Wood
		)
	end
	beam(
		m,
		"Gidung",
		cf:PointToWorldSpace(V3(w / 2, y0, d / 2 - 0.4)),
		cf:PointToWorldSpace(V3(w / 2, y0 + h + 0.4, d / 2 - 0.4)),
		0.8,
		0.8,
		P.woodDark,
		M.Wood
	)
	block(m, "Dori", V3(w + 1, 0.8, 0.8), cf * CF(0, y0 + h + 0.2, -d / 2), P.woodDark, M.Wood)
	-- 지붕: 맞배 (길이 X)
	local eave = 2.4
	local spec = {
		ex = w / 2 + 1.4,
		ez = d / 2 + eave,
		eave = eave,
		bands = 1,
		kind = "gable",
		pitchLow = 22,
		pitchHigh = 36,
		gableX = w / 2 + 0.05,
		gableOver = 0,
		t = 0.6,
	}
	local _, _, hh, pitches = Build.profile(spec)
	local under = hh[1] - 0.6 / math.cos(rad(pitches[1]))
	Build.roof(m, cf * CF(0, y0 + h + 0.65 - under, 0), spec)
	-- 화덕: 벽돌 단 위 숯불, 굴뚝은 지붕을 뚫고
	local hx, hz = -2.6, d / 2 - 2.4
	block(m, "Hwadeok", V3(4.4, 2.6, 3.4), cf * CF(hx, y0 + 1.3, hz), C.brick, M.Brick)
	local coal = neon(m, "Sutbul", V3(3.4, 0.35, 2.4), cf * CF(hx, y0 + 2.7, hz), C.glow)
	glowLight(coal, C.glowHot, 14, 1.8)
	sparks(coal, 3)
	local chimneyTop = y0 + h + 7
	block(
		m,
		"Gulttuk",
		V3(2.2, chimneyTop - y0 - 2.6, 2.2),
		cf * CF(hx, (chimneyTop + y0 + 2.6) / 2, hz + 1.0),
		C.brickDark,
		M.Brick
	)
	local cap = block(m, "Gulttuk", V3(2.8, 0.6, 2.8), cf * CF(hx, chimneyTop + 0.3, hz + 1.0), C.soot, M.Slate)
	smoke(cap, { rate = 1.6, size0 = 1.4, size1 = 6 })
	-- 풀무 (화덕 곁)
	block(m, "Pulmu", V3(1.8, 1.4, 2.6), cf * CF(hx - 3.2, y0 + 0.7, hz), P.woodDark, M.Wood)
	wedge(
		m,
		"Pulmu",
		V3(1.8, 0.7, 2.6),
		cf * CF(hx - 3.2, y0 + 1.75, hz) * CFrame.Angles(0, math.pi / 2, 0),
		Color3.fromRGB(96, 70, 50),
		M.Fabric
	)
	-- 모루와 받침 나무
	cyl(
		m,
		"Batchim",
		cf:PointToWorldSpace(V3(1.6, y0, -0.6)),
		cf:PointToWorldSpace(V3(1.6, y0 + 2.0, -0.6)),
		1.6,
		P.wood,
		M.Wood
	)
	block(m, "Moru", V3(2.2, 0.8, 0.9), cf * CF(1.6, y0 + 2.4, -0.6), C.iron, M.Metal)
	wedge(
		m,
		"Moru",
		V3(0.9, 0.6, 0.9),
		cf * CF(3.1, y0 + 2.5, -0.6) * CFrame.Angles(0, -math.pi / 2, 0),
		C.iron,
		M.Metal
	)
	-- 담금질 물통
	block(m, "Mulgu", V3(2.4, 1.3, 1.5), cf * CF(4.2, y0 + 0.65, 1.6), P.woodDark, M.WoodPlanks)
	deco(block(m, "Mul", V3(2.0, 0.1, 1.1), cf * CF(4.2, y0 + 1.25, 1.6), Color3.fromRGB(40, 60, 66), M.Glass)).Transparency =
		0.2
	-- 뒤 벽의 칼과 도구
	for i, x in { 1.4, 2.4, 3.4, 4.4 } do
		local len = 3.6 - (i % 2) * 0.8
		block(
			m,
			"Kal",
			V3(0.18, len, 0.5),
			cf * CF(x, y0 + 3.4 + len / 2, d / 2 - 1.0) * CFrame.Angles(0, 0, rad(rng(-6, 6))),
			Color3.fromRGB(176, 178, 180),
			M.Metal
		)
	end
	return m
end

-- 장터 좌판: 네 기둥에 천 차양, 앞 판대와 물건. cf 는 바닥, 앞 -Z
local function stall(parent: Instance, cf: CFrame, rng, cloth: Color3)
	local m = model(parent, "좌판")
	local w, d = 6, 4
	for _, x in { -w / 2, w / 2 } do
		for _, z in { -d / 2, d / 2 } do
			local hgt = if z < 0 then 4.6 else 5.4
			beam(
				m,
				"Gidung",
				cf:PointToWorldSpace(V3(x, -0.3, z)),
				cf:PointToWorldSpace(V3(x, hgt, z)),
				0.35,
				0.35,
				P.woodDark,
				M.Wood
			)
		end
	end
	block(
		m,
		"Chayang",
		V3(w + 1.2, 0.15, d + 1.4),
		cf * CF(0, 5.1, -0.2) * CFrame.Angles(rad(-11), 0, 0),
		cloth,
		M.Fabric
	)
	block(m, "Pandae", V3(w - 0.4, 2.2, 1.6), cf * CF(0, 1.1, -d / 2 + 0.9), P.wood, M.WoodPlanks)
	for i = 1, 3 do
		local x = -w / 2 + 1.2 + (i - 1) * 1.8
		local kind = math.floor(rng(0, 2.99))
		if kind == 0 then
			ball(
				m,
				"Dok",
				cf:PointToWorldSpace(V3(x, 2.75, -d / 2 + 0.9)),
				1.1,
				Color3.fromRGB(96, 62, 44),
				M.SmoothPlastic
			)
		elseif kind == 1 then
			block(
				m,
				"Cheon",
				V3(1.4, 0.6, 1.0),
				cf * CF(x, 2.5, -d / 2 + 0.9),
				C.cloth:Lerp(P.samcheong, rng(0, 1)),
				M.Fabric
			)
		else
			cyl(
				m,
				"Geureut",
				cf:PointToWorldSpace(V3(x, 2.2, -d / 2 + 0.9)),
				cf:PointToWorldSpace(V3(x, 2.6, -d / 2 + 0.9)),
				1.2,
				Color3.fromRGB(150, 150, 140),
				M.Metal
			)
		end
	end
	return m
end

-- 무더기 (숯, 광석): 기운 덩이 몇
local function heap(parent: Instance, c: Vector3, size: number, rng, color: Color3, material, n: number?)
	local m = model(parent, "무더기")
	for i = 1, n or 3 do
		local a = rng(0, math.pi * 2)
		local r = size * 0.35 * (i - 1) / 2
		local s = size * rng(0.55, 0.9) * (if i == 1 then 1 else 0.7)
		local p = c + V3(math.cos(a) * r, s * 0.18, math.sin(a) * r)
		block(
			m,
			"Deongi",
			V3(s, s * 0.5, s * rng(0.7, 1)),
			CF(p) * CFrame.Angles(rng(-0.3, 0.3), rng(0, 3), rng(-0.3, 0.3)),
			color,
			material
		)
	end
	return m
end

-- 나무 궤짝
local function crates(parent: Instance, cf: CFrame, rng, n: number)
	local m = model(parent, "궤짝")
	for i = 1, n do
		local s = rng(1.6, 2.2)
		local x = (i - 1) * 2.3 - (n - 1) * 1.15
		local cfi = cf * CF(x, s / 2, rng(-0.3, 0.3)) * CFrame.Angles(0, rng(-0.3, 0.3), 0)
		block(m, "Gwe", V3(s, s, s), cfi, P.wood:Lerp(P.woodDark, rng(0, 0.6)), M.WoodPlanks)
		if i == 1 and n > 2 then
			block(
				m,
				"Gwe",
				V3(1.5, 1.5, 1.5),
				cfi * CF(0.3, s / 2 + 0.75, 0) * CFrame.Angles(0, 0.4, 0),
				P.wood,
				M.WoodPlanks
			)
		end
	end
	return m
end

-- 대용광로 (el_fire 자리 바로 뒤). 쇳물 입이 남쪽 장터를 본다
local function furnace(parent: Instance, rng)
	local m = model(parent, "대용광로")
	local site = Sites.byId.el_fire
	local fx, fz = site.x, site.z - 24 -- 노 몸 가운데
	local y = FLOOR
	-- 바닥 단
	block(m, "Dan", V3(36, 2, 26), CF(fx, y + 0.3, fz - 1), P.granite, M.Granite)
	block(m, "Dan", V3(36.6, 0.5, 26.6), CF(fx, y + 1.35, fz - 1), P.graniteDark, M.Granite)
	local base = y + 1.6
	-- 노 몸: 굵은 벽돌 원통, 쇠테 셋, 위로 좁아지는 목
	local R = 11
	cyl(m, "Mitdol", V3(fx, base - 0.2, fz), V3(fx, base + 3, fz), R * 2 + 2.4, P.graniteDark, M.Granite)
	cyl(m, "Nomom", V3(fx, base, fz), V3(fx, base + 19, fz), R * 2, C.brick, M.Brick)
	for _, h in { 7, 12.5, 17.5 } do
		cyl(m, "Soetae", V3(fx, base + h - 0.4, fz), V3(fx, base + h + 0.4, fz), R * 2 + 0.5, C.iron, M.Metal)
	end
	cyl(m, "Moktong", V3(fx, base + 19, fz), V3(fx, base + 25, fz), 17, C.brickDark, M.Brick)
	cyl(m, "Moktong", V3(fx, base + 25, fz), V3(fx, base + 29.5, fz), 13, C.brick, M.Brick)
	cyl(m, "Gat", V3(fx, base + 29.5, fz), V3(fx, base + 31, fz), 14.6, P.graniteDark, M.Granite)
	-- 노 꼭대기 아가리 (쇳물빛)
	local throat = neon(m, "Agari", V3(0.4, 8, 8), CF(fx, base + 31.05, fz) * CFrame.Angles(0, 0, rad(90)), C.glow)
	throat.Shape = Enum.PartType.Cylinder
	-- 굴뚝: 노 뒤(북)에 따로 선 높은 굴뚝 (연도로 잇는다)
	local sx, sz = fx - 6, fz - 15
	cyl(m, "Gulttuk", V3(sx, base - 0.5, sz), V3(sx, base + 52, sz), 6.4, C.brickDark, M.Brick)
	for _, h in { 18, 34 } do
		cyl(m, "Soetae", V3(sx, base + h, sz), V3(sx, base + h + 0.7, sz), 6.9, C.iron, M.Metal)
	end
	local stackCap = cyl(m, "Gulttuk", V3(sx, base + 52, sz), V3(sx, base + 53.4, sz), 7.6, C.soot, M.Slate)
	smoke(stackCap, { dir = Enum.NormalId.Right, rate = 3, size0 = 3, size1 = 14, life = 7, speed = 3, alpha = 0.45 })
	beam(m, "Yeondo", V3(fx - 2, base + 24, fz - 6.5), V3(sx, base + 26, sz + 2.6), 3.2, 3.2, C.brickDark, M.Brick)
	-- 버팀벽 넷 (앞을 비우고 비스듬히)
	for _, deg in { 45, 135, 225, 315 } do
		local a = rad(deg)
		local dir = V3(math.cos(a), 0, math.sin(a))
		local p = V3(fx, base, fz) + dir * (R + 1.2)
		local look = face(p, p + dir)
		block(m, "Beotim", V3(3.2, 14, 3.4), look * CF(0, 7, 0), C.brickDark, M.Brick)
		wedge(m, "Beotim", V3(3.2, 4, 3.4), look * CF(0, 16, 0) * CFrame.Angles(0, math.pi, 0), C.brickDark, M.Brick)
	end
	-- 쇳물 입: 앞(남) 쪽 돌집, 안에 이글거리는 불
	local mz = fz + R + 1.2
	block(m, "Ipjip", V3(10, 9.5, 4.4), CF(fx, base + 4.75, mz - 0.6), C.brickDark, M.Brick)
	block(m, "Ipdol", V3(11, 1.4, 5.0), CF(fx, base + 10.2, mz - 0.4), P.granite, M.Granite)
	block(m, "Ipdol", V3(1.4, 7, 4.8), CF(fx - 3.4, base + 3.5, mz - 0.3), P.granite, M.Granite)
	block(m, "Ipdol", V3(1.4, 7, 4.8), CF(fx + 3.4, base + 3.5, mz - 0.3), P.granite, M.Granite)
	local mouth = neon(m, "Bulgil", V3(5.4, 6.4, 0.6), CF(fx, base + 3.4, mz + 1.4), C.glowHot)
	glowLight(mouth, C.glow, 28, 3.2)
	sparks(mouth, 6, Enum.NormalId.Back)
	-- 쇳물 고랑: 입에서 서쪽 거푸집 바닥으로 (과업 자리를 비켜서)
	local chA, chB = V3(fx - 3.5, base + 0.05, mz + 2.2), V3(fx - 16, base + 0.05, mz + 4.4)
	beam(m, "Gorang", chA, chB, 2.4, 0.5, P.graniteDark, M.Slate)
	neon(m, "Soemul", V3(1.1, 0.2, (chB - chA).Magnitude), face((chA + chB) / 2 + V3(0, 0.3, 0), chB), C.glow)
	block(m, "Geopuzip", V3(9, 0.7, 6.5), CF(fx - 21, base + 0.05, mz + 5.2), C.sand:Lerp(C.dirt, 0.5), M.Sand)
	for i = 0, 2 do
		neon(
			m,
			"Ingot",
			V3(1.6, 0.35, 4.2),
			CF(fx - 24 + i * 2.6, base + 0.55, mz + 5.2),
			C.glow:Lerp(C.soot, 0.25 * i)
		)
	end
	-- 풀무 둘 (발풀무): 나무 통, 가죽 덮개, 지렛대, 바람관
	for _, s in { -1, 1 } do
		local bx, bz = fx + s * 15, fz + 6
		block(m, "Pulmu", V3(5, 2.6, 7), CF(bx, base + 1.3, bz), P.woodDark, M.WoodPlanks)
		block(
			m,
			"Gajuk",
			V3(4.4, 0.8, 6.4),
			CF(bx, base + 2.9, bz) * CFrame.Angles(rad(s * 4), 0, 0),
			Color3.fromRGB(104, 72, 50),
			M.Fabric
		)
		beam(m, "Jiret", V3(bx, base + 3.6, bz - 4.5), V3(bx, base + 5.4, bz + 4.5), 0.6, 0.6, P.wood, M.Wood)
		beam(m, "Gidung", V3(bx, base, bz + 4.5), V3(bx, base + 5.8, bz + 4.5), 0.7, 0.7, P.wood, M.Wood)
		cyl(
			m,
			"Baramgwan",
			V3(bx - s * 2.5, base + 1.4, bz),
			V3(fx + s * (R - 1), base + 2.4, fz + 3),
			1.2,
			C.iron,
			M.Metal
		)
	end
	-- 장입대: 북동쪽 나무 비계, 노 아가리로 건너는 널다리, 도르래
	local gx, gz = fx + 12, fz - 11
	for _, o in { { -3, -3 }, { 3, -3 }, { -3, 3 }, { 3, 3 } } do
		beam(
			m,
			"Bigye",
			V3(gx + o[1], base, gz + o[2]),
			V3(gx + o[1], base + 20.6, gz + o[2]),
			0.8,
			0.8,
			P.wood,
			M.Wood
		)
	end
	block(m, "Pyeongsang", V3(8, 0.6, 8), CF(gx, base + 20.6, gz), P.wood, M.WoodPlanks)
	beam(m, "Beotim", V3(gx - 3, base + 1, gz - 3), V3(gx + 3, base + 19, gz - 3), 0.5, 0.5, P.woodDark, M.Wood)
	beam(m, "Beotim", V3(gx + 3, base + 1, gz + 3), V3(gx + 3, base + 19, gz - 3), 0.5, 0.5, P.woodDark, M.Wood)
	beam(
		m,
		"Dari",
		V3(gx - 4, base + 20.9, gz + 1.5),
		V3(fx + 4.5, base + 30.5, fz - 4),
		3.2,
		0.5,
		P.wood,
		M.WoodPlanks
	)
	beam(m, "Doraepal", V3(gx + 2, base + 26, gz + 2), V3(gx + 8, base + 22, gz - 4), 0.6, 0.6, P.woodDark, M.Wood)
	beam(m, "Gidung", V3(gx + 2, base + 20.9, gz + 2), V3(gx + 2, base + 26, gz + 2), 0.6, 0.6, P.woodDark, M.Wood)
	beam(m, "Jul", V3(gx + 8, base + 22, gz - 4), V3(gx + 8, base + 9, gz - 4), 0.12, 0.12, C.rope, M.Fabric)
	block(m, "Gwangju", V3(1.8, 1.4, 1.8), CF(gx + 8, base + 8.3, gz - 4), P.woodDark, M.WoodPlanks)
	-- 광석과 숯 무더기, 수레
	heap(m, V3(fx + 22, y, fz - 4), 6, rng, C.rust, M.Slate, 4)
	heap(m, V3(fx - 21, y, fz - 6), 6, rng, C.soot, M.Slate, 4)
	heap(m, V3(fx - 18, y, fz - 14), 4, rng, C.soot, M.Slate, 2)
	Build.cart(m, CF(fx + 22, y, fz - 14) * CFrame.Angles(0, rad(150), 0))
	return m
end

local function buildCity(root: Instance, rng)
	local city = folder(root, "홍로성")
	local x0, x1, z0, z1 = CX - HALF, CX + HALF, CZ - HALF, CZ + HALF
	local walls = folder(city, "성벽")

	-- 성문 자리: 북문은 송계에서 오는 길(Land.ROADS 5), 동문은 주염산 길(6), 남문은 무택 길(8), 서문은 벽계협 쪽, 북동 암문은 청음암 길(7)
	local NX, EZ, SX, WZ, PX = 228, 560, 300, 560, 360
	local gates = {
		{ name = "north", cf = CF(NX, 0, z0), full = true },
		{ name = "west", cf = face(V3(x0, 0, WZ), V3(x0 - 10, 0, WZ)), board = true },
		{ name = "east", cf = face(V3(x1, 0, EZ), V3(x1 + 10, 0, EZ)) },
		{ name = "south", cf = face(V3(SX, 0, z1), V3(SX, 0, z1 + 10)) },
	}
	for _, g in gates do
		local p = g.cf.Position
		local low = huge
		for _, o in { V3(-9, 0, -3), V3(9, 0, -3), V3(-9, 0, 3), V3(9, 0, 3), V3(0, 0, 0), V3(0, 0, -3), V3(0, 0, 3) } do
			local q = g.cf:PointToWorldSpace(o)
			low = math.min(low, Land.height(q.X, q.Z))
		end
		local cf = CF(p.X, low - 0.3, p.Z) * (g.cf - g.cf.Position)
		local H = WALL_TOP - (low - 0.3)
		if g.full then
			local gm = Build.gatehouse(walls, cf, {
				height = H,
				thick = 6,
				span = 20,
				radius = 5,
				spring = 6.5,
				voussoirs = 7,
				detail = if g.name == "north" then 1 else 0,
				name = if g.name == "north" then "북문" else "서문",
				color = C.wallStone,
			})
			-- 문루 난간 동자·주춧돌·마루판은 덜어 낸다 (성 밖에서 보이지 않고 부품만 많다)
			for _, d in gm:GetDescendants() do
				if d.Name == "Dongja" or d.Name == "Choseok" or d.Name == "Floor" or d.Name == "Nangan" then
					d:Destroy()
				end
			end
			gateBoard(gm, cf, 6.5 + 6.1 + 1.9, "홍로성")
			for _, s in { -1, 1 } do
				local q = cf:PointToWorldSpace(V3(s * 12.5, 0, -5.5))
				Build.banner(gm, V3(q.X, gy(q.X, q.Z), q.Z), cf:PointToWorldSpace(V3(s * 20, 0, -12)), C.cloth, 12)
			end
		else
			local gm = plainGate(
				walls,
				cf,
				H,
				if g.name == "east" then "동문" elseif g.name == "west" then "서문" else "남문"
			)
			if g.board then
				gateBoard(gm, cf, 6.5 + 6.1 + 1.9, "홍로성")
				for _, s in { -1, 1 } do
					local q = cf:PointToWorldSpace(V3(s * 12.5, 0, -5.5))
					Build.banner(gm, V3(q.X, gy(q.X, q.Z), q.Z), cf:PointToWorldSpace(V3(s * 20, 0, -12)), C.cloth, 12)
				end
			end
		end
		gateRamp(walls, cf, 10, 14)
	end
	-- 성벽 (바깥이 오른쪽: 북 동→서, 서 북→남, 남 서→동, 동 남→북). 모퉁이는 치성이 덮는다
	local b = 6.5
	wallRun(walls, x1 - b, z0, PX + 5, z0)
	wallRun(walls, PX - 5, z0, NX + 10, z0)
	wallRun(walls, NX - 10, z0, x0 + b, z0)
	wallRun(walls, x0, z0 + b, x0, WZ - 10)
	wallRun(walls, x0, WZ + 10, x0, z1 - b)
	wallRun(walls, x0 + b, z1, SX - 10, z1)
	wallRun(walls, SX + 10, z1, x1 - b, z1)
	wallRun(walls, x1, z1 - b, x1, EZ + 10)
	wallRun(walls, x1, EZ - 10, x1, z0 + b)
	for _, c in { { x0, z0 }, { x1, z0 }, { x0, z1 }, { x1, z1 } } do
		bastion(walls, c[1], c[2])
	end
	-- 북동 암문: 성벽을 비운 자리에 돌 문틀
	do
		local low =
			math.min(Land.height(PX - 4, z0), Land.height(PX + 4, z0), Land.height(PX, z0 - 3), Land.height(PX, z0 + 3))
		local pm = model(walls, "암문")
		for _, s in { -1, 1 } do
			block(pm, "Munseol", V3(1.2, 9, 5.6), CF(PX + s * 4.4, low + 4.2, z0), P.granite, M.Granite)
		end
		block(pm, "Inbang", V3(10, 1.6, 5.6), CF(PX, low + 9.4, z0), P.granite, M.Granite)
		block(
			pm,
			"Wibyeok",
			V3(10, WALL_TOP - low - 10.2, 5),
			CF(PX, (WALL_TOP + low + 10.2) / 2, z0),
			C.wallStone,
			M.Cobblestone
		)
		parapet(pm, V3(PX + 5, WALL_TOP, z0 - 2.5), V3(PX - 5, WALL_TOP, z0 - 2.5))
		pave(pm, Vector2.new(PX, z0 - 8), Vector2.new(PX, z0 + 14), 7, C.pave, M.Pavement, { seg = 6, name = "Mungil" })
	end

	-- 길 --------------------------------------------------------------------------------------
	local streets = folder(city, "길")
	local function plate(name: string, ax: number, az: number, bx: number, bz: number, color: Color3, mat)
		-- 성 안 평지: 판 하나 (윗면 FLOOR + 0.22)
		block(
			streets,
			name,
			V3(math.abs(bx - ax), 1, math.abs(bz - az)),
			CF((ax + bx) / 2, FLOOR + 0.22 - 0.5, (az + bz) / 2),
			color,
			mat
		)
	end
	-- 성 안 평지는 다진 흙 (풀밭 대신)
	block(streets, "Madang", V3(144, 1, 144), CF(CX, FLOOR + 0.05 - 0.5, CZ), Color3.fromRGB(150, 128, 98), M.Ground)
	plate("Jangteo", 256, 492, 344, 554, C.pave, M.Pavement) -- 장터 마당 (노 앞)
	plate("Keungil", 233, 554, 367, 566, C.cobble, M.Cobblestone) -- 동서 큰길
	pave(streets, Vector2.new(x0 + 3, WZ), Vector2.new(233.5, WZ), 12, C.cobble, M.Cobblestone, { seg = 6 })
	pave(streets, Vector2.new(366.5, EZ), Vector2.new(x1 - 3, EZ), 12, C.cobble, M.Cobblestone, { seg = 6 })
	plate("Namgil", 294, 566, 306, 596, C.cobble, M.Cobblestone) -- 남북 큰길
	plate("Munan", 284, 596, 316, 622, C.pave, M.Pavement) -- 남문 안 마당 (전송진 둘레를 넓게 비운다)
	pave(streets, Vector2.new(SX, 621.5), Vector2.new(SX, z1 - 3), 12, C.cobble, M.Cobblestone, { seg = 6 })
	plate("Bukgil", NX - 5, 470, NX + 5, 554, C.cobble, M.Cobblestone) -- 북문 길
	pave(streets, Vector2.new(NX, z0 + 3), Vector2.new(NX, 470.5), 10, C.cobble, M.Cobblestone, { seg = 6 })
	plate("Dwitgil", NX + 5, 462, PX + 4, 470, C.cobble, M.Cobblestone) -- 노 뒷길
	pave(streets, Vector2.new(PX, z0 + 3), Vector2.new(PX, 462.5), 7, C.cobble, M.Cobblestone, { seg = 6 })

	-- 대용광로 -----------------------------------------------------------------------------
	furnace(city, rng)

	-- 집 ---------------------------------------------------------------------------------------
	local houses = folder(city, "집")
	local function H(x: number, z: number, tx: number, tz: number, opts)
		return houseAt(houses, x, z, V3(tx, 0, tz), opts)
	end
	-- 장인회관: 장터 서쪽, 동쪽(장터)을 본다
	H(
		244,
		515,
		300,
		515,
		{
			bays = { 4, 2 },
			bay = 5.5,
			pillarH = 9,
			plinth = 2.2,
			style = "palace",
			detail = 1,
			bands = 2,
			roof = "paljak",
			name = "장인회관",
		}
	)
	-- 장터 서쪽 가게 둘 (회관 앞뒤)
	H(244, 486, 300, 486, { bays = { 2, 1 }, bay = 5, detail = 0, roof = "gable", bands = 1, name = "가게" })
	H(244, 545, 300, 545, { bays = { 2, 1 }, bay = 5, detail = 0, roof = "gable", bands = 1, name = "가게" })
	-- 대장간 셋: 장터 동쪽, 서쪽(장터)을 본다
	for i, z in { 497, 518, 539 } do
		forge(houses, face(V3(357, FLOOR, z), V3(300, FLOOR, z)), rng)
		if i == 2 then
			Build.banner(houses, V3(349.5, FLOOR, z - 7.5), V3(300, FLOOR, z - 7.5), C.clothDark, 9)
		end
	end
	-- 남서: 살림집 셋 (남향). 앞 두 채는 돌담 두른 한 마당에 장독대
	local yards = folder(city, "마당")
	for i, hx in { 244, 270 } do
		local hz = 576
		thatchAt(
			houses,
			hx,
			hz,
			V3(hx, 0, hz + 10),
			10,
			6.5,
			{ name = "살림집", bays = 2, thatch = jitter(C.thatch, rng, 0.06) }
		)
		Build.jars(yards, CF(hx - 6, FLOOR, hz + 12) * CFrame.Angles(0, rad(90 * (i - 1)), 0), rng, 4)
	end
	local wy = FLOOR
	for _, seg in
		{
			{ 233, 568, 233, 594 },
			{ 233, 594, 240, 594 },
			{ 248, 594, 266, 594 },
			{ 274, 594, 283, 594 },
			{ 283, 594, 283, 568 },
			{ 257, 582, 257, 594 },
		}
	do
		Build.stoneWall(yards, V3(seg[1], wy, seg[2]), V3(seg[3], wy, seg[4]), { height = 3, width = 1.4 })
	end
	Build.cart(yards, CF(279, FLOOR, 588) * CFrame.Angles(0, rad(-20), 0))
	thatchAt(
		houses,
		244,
		604,
		V3(244, 0, 614),
		13,
		6.5,
		{ name = "살림집", bays = 3, thatch = jitter(C.thatch, rng, 0.06) }
	)
	-- 남동: 객주(큰 가게)와 가게, 우물
	H(330, 582, 300, 582, { bays = { 3, 1 }, bay = 5.5, detail = 0, roof = "gable", bands = 1, name = "객주" })
	H(358, 580, 358, 566, { bays = { 2, 1 }, bay = 5, detail = 0, roof = "gable", bands = 1, name = "가게" })
	Build.well(yards, V3(350, FLOOR, 604))
	Build.jars(yards, CF(336, FLOOR, 614), rng, 4)
	-- 노 북서: 숯 헛간 (열린 맞배)
	do
		local look = face(V3(262, FLOOR, 476), V3(262, FLOOR, 520))
		local shed = model(houses, "숯광")
		for _, x in { -6, 6 } do
			for _, z in { -4, 4 } do
				beam(
					shed,
					"Gidung",
					look:PointToWorldSpace(V3(x, -0.3, z)),
					look:PointToWorldSpace(V3(x, 6.4, z)),
					0.7,
					0.7,
					P.wood,
					M.Wood
				)
			end
		end
		local spec = {
			ex = 7.6,
			ez = 6.4,
			eave = 2.4,
			bands = 1,
			kind = "gable",
			pitchLow = 22,
			pitchHigh = 34,
			gableX = 6.05,
			gableOver = 0,
		}
		local _, _, hh, pitches = Build.profile(spec)
		Build.roof(shed, look * CF(0, 6.6 - (hh[1] - 0.6 / math.cos(rad(pitches[1]))), 0), spec)
		heap(shed, look:PointToWorldSpace(V3(-2.5, 0, 0)), 5, rng, C.soot, M.Slate, 3)
		heap(shed, look:PointToWorldSpace(V3(3, 0, 1)), 4, rng, C.soot, M.Slate, 2)
	end

	-- 장터: 좌판, 초롱, 깃발, 수레, 궤짝 -------------------------------------------------------
	local market = folder(city, "장터")
	local cloths = {
		C.cloth,
		Color3.fromRGB(196, 168, 112),
		P.samcheong:Lerp(P.plaster, 0.3),
		Color3.fromRGB(120, 140, 96),
		C.clothDark,
	}
	for i, sx in { 268, 281, 319, 332 } do
		stall(market, face(V3(sx, FLOOR + 0.22, 547), V3(sx, FLOOR, 520)), rng, cloths[i])
	end
	stall(market, face(V3(286, FLOOR + 0.22, 528), V3(320, FLOOR, 528)), rng, cloths[4])
	stall(market, face(V3(314, FLOOR + 0.22, 528), V3(280, FLOOR, 528)), rng, cloths[3])
	-- 갓 부은 큰 종 (나무 종틀)
	do
		local bm = model(market, "종틀")
		local bx, bz = 274, 514
		for _, s in { -1, 1 } do
			beam(bm, "Gidung", V3(bx + s * 4, FLOOR, bz), V3(bx + s * 4, FLOOR + 11, bz), 1, 1, P.woodDark, M.Wood)
			beam(
				bm,
				"Beotim",
				V3(bx + s * 4, FLOOR, bz - 2.5),
				V3(bx + s * 4, FLOOR + 6, bz),
				0.6,
				0.6,
				P.woodDark,
				M.Wood
			)
		end
		beam(bm, "Dori", V3(bx - 5, FLOOR + 10.6, bz), V3(bx + 5, FLOOR + 10.6, bz), 1.1, 1.1, P.woodDark, M.Wood)
		cyl(bm, "Jong", V3(bx, FLOOR + 3.4, bz), V3(bx, FLOOR + 8.6, bz), 4.4, Color3.fromRGB(96, 104, 88), M.Metal)
		ball(bm, "Jong", V3(bx, FLOOR + 8.6, bz), 4.2, Color3.fromRGB(96, 104, 88), M.Metal)
		cyl(bm, "Yongnyu", V3(bx, FLOOR + 10, bz), V3(bx, FLOOR + 10.6, bz), 1.2, Color3.fromRGB(84, 92, 78), M.Metal)
		block(bm, "Dan", V3(10, 0.8, 5), CF(bx, FLOOR + 0.62, bz), P.graniteDark, M.Granite)
	end
	for _, p in { { 258, 495 }, { 342, 495 }, { 258, 551 }, { 342, 551 } } do
		Build.chorong(market, V3(p[1], FLOOR + 0.22, p[2]), V3(300, FLOOR, if p[2] > 560 then p[2] else 523))
	end
	Build.banner(market, V3(287, FLOOR + 0.22, 556), V3(300, FLOOR, 600), C.cloth, 11)
	Build.banner(market, V3(313, FLOOR + 0.22, 556), V3(300, FLOOR, 600), C.cloth, 11)
	Build.cart(market, CF(318, FLOOR + 0.22, 570) * CFrame.Angles(0, rad(-80), 0))
	Build.cart(market, CF(240, FLOOR + 0.22, 466) * CFrame.Angles(0, rad(10), 0))
	crates(market, CF(256, FLOOR + 0.22, 535) * CFrame.Angles(0, rad(90), 0), rng, 3)
	crates(market, CF(324, FLOOR + 0.22, 572), rng, 2)
	crates(market, CF(368, FLOOR + 0.22, 552), rng, 3)
	-- 성 안 나무: 우물 곁 버드나무, 회관 앞 매화, 성벽 안쪽 소나무
	local trees = folder(city, "나무")
	Build.willow(trees, V3(376, gy(376, 612), 612), rng, { height = 11, strands = 10, blobs = 4 })
	Build.willow(trees, V3(218, gy(218, 590), 590), rng, { height = 12, strands = 10, blobs = 4 })
	Build.blossom(trees, V3(257, gy(257, 530), 530), rng, { height = 8, blobs = 6 })
	Build.pine(trees, V3(216, gy(216, 470), 470), rng, { height = 14 })
	return city
end

-- 자연 조각 (여러 땅이 같이 쓴다) ------------------------------------------------------------

-- 마른 나무 (불탄 나무, 늪의 고사목): 굽은 줄기 두 마디, 꺾인 가지 둘셋
local function deadTree(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = model(parent, opts.name or "고사목")
	local h = opts.height or rng(6, 11)
	local color = jitter(opts.color or C.charred, rng, 0.08)
	local w = h * (opts.girth or 0.09)
	local lean = V3(rng(-0.25, 0.25), 1, rng(-0.25, 0.25)).Unit
	local mid = base + lean * (h * 0.55)
	beam(m, "Julgi", base - V3(0, 0.8, 0), mid, w, w, color, M.Wood)
	local lean2 = (lean + V3(rng(-0.4, 0.4), 0, rng(-0.4, 0.4))).Unit
	local top = mid + lean2 * (h * 0.45)
	beam(m, "Julgi", mid - lean * 0.3, top, w * 0.7, w * 0.7, color, M.Wood)
	for i = 1, opts.branches or 2 do
		local from = if i == 1 then mid else mid:Lerp(top, rng(0.4, 0.8))
		local a = rng(0, math.pi * 2)
		local to = from + V3(math.cos(a) * h * 0.32, h * rng(0.1, 0.3), math.sin(a) * h * 0.32)
		beam(m, "Gaji", from, to, w * 0.42, w * 0.42, color, M.Wood)
	end
	return m
end

-- 고사리 포기: 잎 셋을 돌려 비스듬히
local function fern(parent: Instance, base: Vector3, rng, s: number)
	local m = model(parent, "고사리")
	local a0 = rng(0, math.pi * 2)
	for i = 1, 3 do
		local a = a0 + i * math.pi * 2 / 3 + rng(-0.3, 0.3)
		local dir = V3(math.cos(a), 0, math.sin(a))
		local len = s * rng(0.8, 1.2)
		local c = base + dir * len * 0.42 + V3(0, len * 0.2, 0)
		local p = deco(
			block(
				m,
				"Ip",
				V3(len * 0.42, 0.14, len),
				face(c, c + dir) * CFrame.Angles(rad(rng(18, 32)), 0, 0),
				jitter(C.fern, rng, 0.1),
				M.LeafyGrass
			)
		)
		p.CastShadow = false
	end
	return m
end

-- 바위 하나 (땅에 반쯤 묻은 기운 덩이 + 깎인 모서리)
local function boulder(parent: Instance, base: Vector3, size: number, rng, color: Color3, material)
	local m = model(parent, "바위")
	local main = block(
		m,
		"Rock",
		V3(size, size * rng(0.55, 0.8), size * rng(0.7, 1)),
		CF(base + V3(0, size * 0.12, 0)) * CFrame.Angles(rng(-0.25, 0.25), rng(0, math.pi), rng(-0.25, 0.25)),
		jitter(color, rng, 0.06),
		material
	)
	block(
		m,
		"Rock",
		V3(size * 0.75, size * 0.45, size * 0.65),
		main.CFrame * CF(size * 0.12, size * 0.25, 0) * CFrame.Angles(rng(-0.5, 0.5), rng(0, 1), rng(0.3, 0.6)),
		jitter(color, rng, 0.08),
		material
	)
	return m, main
end

-- 비탈에서 바위·나무 밑동이 뜨지 않게: 둘레 가장 낮은 땅
local function lowAt(x: number, z: number, r: number): number
	return (spanAt(x, z, r))
end

-- 주염산 -------------------------------------------------------------------------------------

local VOL = Land.VOLCANO
local TRAIL = Land.VOLCANO_TRAIL

-- 화구 길 k 번째(1° 마다) 점: 길 가운데(땅 위), 바깥(지름) 방향, 화구 가운데에서 거리
local function trailPoint(k: number): (Vector3, Vector3, number)
	local kk = math.clamp(k, 0, TRAIL.n)
	local i = math.floor(kk)
	local p, q = TRAIL.pts[i], TRAIL.pts[math.min(i + 1, TRAIL.n)]
	local d = p[1] + (q[1] - p[1]) * (kk - i)
	local a = rad(TRAIL.a0 + TRAIL.dir * kk)
	local out = V3(math.cos(a), 0, math.sin(a))
	local x, z = TRAIL.cx + out.X * d, TRAIL.cz + out.Z * d
	return V3(x, Land.height(x, z), z), out, d
end

-- 길을 따라 거리 every 마다 k 값들
local function trailStations(every: number, k0: number, k1: number): { number }
	local out = { k0 }
	local prev = trailPoint(k0)
	local acc = 0
	local k = k0
	while k < k1 do
		k += 0.25
		local p = trailPoint(k)
		acc += (p - prev).Magnitude
		prev = p
		if acc >= every then
			table.insert(out, k)
			acc = 0
		end
	end
	return out
end

-- 열에 갈라진 석등: Build.stoneLantern 을 그을린 빛으로 바꾸고 조금 기울인다
local function crackedLantern(parent: Instance, ground: Vector3, rng)
	local m = Build.stoneLantern(parent, ground)
	m.Name = "갈라진 석등"
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			if d.Material == M.Neon then
				d.Color = C.glow
			else
				d.Color = d.Color:Lerp(C.soot, 0.45)
				d.Material = M.Basalt
			end
		elseif d:IsA("PointLight") then
			d.Color = C.glow
			d.Range = 12
		end
	end
	-- 갈라진 금 (검은 판)
	block(
		m,
		"Geum",
		V3(0.12, 2.6, 0.95),
		CF(ground + V3(0.3, 2.6, 0)) * CFrame.Angles(0, rng(0, 3), rad(8)),
		C.soot,
		M.Slate
	)
	transformModel(m, CF(ground), CFrame.Angles(rad(rng(-6, 6)), 0, rad(rng(-6, 6))))
	return m
end

-- 용암 줄기: 화구 가장자리에서 바깥 비탈을 따라 흘러내리는 빛 띠 (마디마다 땅에 맞춘다)
local function lavaFlow(parent: Instance, theta: number, len: number, rng)
	local m = model(parent, "용암 줄기")
	local a = rad(theta)
	local d = VOL.crater + 0.5
	local seed = rng(0, 100)
	local step = 7
	local n = math.floor(len / step)
	local prev = nil
	for i = 0, n do
		local x, z = VOL.x + math.cos(a) * d, VOL.z + math.sin(a) * d
		local p = V3(x, Land.height(x, z) + 0.3, z)
		if prev then
			local t = i / n
			local w = 5.2 - 3.4 * t + rng(-0.4, 0.4)
			local seg = deco(
				beam(m, "Yongam", prev, p + (p - prev).Unit * 0.8, w, 1.0, C.lava:Lerp(C.lavaDeep, t * 0.7), M.Neon)
			)
			seg.CastShadow = false
			-- 굳은 껍질 (가장자리 검붉은 띠)
			if i % 3 == 0 then
				local crust = beam(
					m,
					"Kkeopjil",
					prev - V3(0, 0.1, 0),
					p - V3(0, 0.1, 0),
					w + 2.2,
					0.9,
					C.basalt:Lerp(C.rustDark, 0.4),
					M.Basalt
				)
				crust.CastShadow = false
			end
		end
		prev = p
		d += step
		a += rad(math.noise(i * 0.4, seed, 0.5) * 10)
	end
	-- 끝에 고인 용암 웅덩이
	local x, z = prev.X, prev.Z
	local pool =
		neon(m, "Ungdeongi", V3(0.6, 9, 7), CF(x, prev.Y - 0.1, z) * CFrame.Angles(0, rng(0, 3), rad(90)), C.lavaDeep)
	pool.Shape = Enum.PartType.Cylinder
	return m
end

local function buildVolcano(root: Instance, rng)
	local vol = folder(root, "주염산")
	local vein = Sites.byId["high@volcano"]

	-- 화구 용암 못: 빛 판 하나를 화구 바닥 높이에 (바닥이 솟은 곳은 굳은 껍질처럼 비친다)
	local crater = model(vol, "화구")
	local lake = neon(
		crater,
		"Yongamot",
		V3(0.6, 92, 92),
		CF(VOL.x, VOL.height - 44.2, VOL.z) * CFrame.Angles(0, 0, rad(90)),
		C.lava
	)
	lake.Shape = Enum.PartType.Cylinder
	glowLight(lake, C.glow, 60, 2.2)
	for i = 1, 3 do
		local a = rad(i * 120 + 20)
		local p = V3(VOL.x + math.cos(a) * 22, VOL.height - 44, VOL.z + math.sin(a) * 22)
		local vent = deco(block(crater, "Gimgu", V3(6, 1, 6), CF(p), C.basalt, M.Basalt))
		vent.Transparency = 1
		smoke(
			vent,
			{
				rate = 2,
				size0 = 6,
				size1 = 26,
				life = 9,
				speed = 5,
				alpha = 0.6,
				color = Color3.fromRGB(150, 128, 118),
				accel = V3(1.5, 1, 0.5),
			}
		)
	end

	-- 바깥 비탈의 용암 줄기 (화구 길(북서~동)을 비켜 남·동남·서쪽으로)
	local lava = folder(vol, "용암")
	for _, f in { { 22, 115 }, { 78, 130 }, { 140, 105 }, { 196, 90 } } do
		lavaFlow(lava, f[1] + rng(-6, 6), f[2], rng)
	end

	-- 김 오르는 틈 (윗비탈)
	for i = 1, 6 do
		local a = rad(rng(0, 360))
		local d = rng(95, 190)
		local x, z = VOL.x + math.cos(a) * d, VOL.z + math.sin(a) * d
		if not nearRoad(x, z, 10) then
			local h = Land.height(x, z)
			local crack = block(
				lava,
				"Teum",
				V3(rng(3, 5), 0.6, rng(1, 1.6)),
				CF(x, h + 0.05, z) * CFrame.Angles(0, rng(0, 3), 0),
				C.soot,
				M.Basalt
			)
			crack.CastShadow = false
			smoke(
				crack,
				{
					rate = 1.2,
					size0 = 2,
					size1 = 10,
					life = 5,
					speed = 3,
					alpha = 0.7,
					color = Color3.fromRGB(196, 190, 186),
				}
			)
		end
	end

	-- 화구 길: 바깥 가장자리에 밧줄 말뚝, 윗길엔 통나무 디딤
	local path = folder(vol, "화구 길")
	local posts = trailStations(21, 4, TRAIL.n - 3)
	local prevTop = nil
	for _, k in posts do
		local c, out = trailPoint(k)
		local p = c + out * 6.4
		local g = Land.height(p.X, p.Z)
		local top = V3(p.X, g + 3.2, p.Z)
		beam(
			path,
			"Malttuk",
			V3(p.X, g - 0.8, p.Z),
			top + V3(0, 0.3, 0),
			0.55,
			0.55,
			C.charred:Lerp(P.woodDark, 0.5),
			M.Wood
		)
		if prevTop and (top - prevTop).Magnitude < 30 then
			local r = beam(path, "Batjul", prevTop, top, 0.16, 0.16, C.rope, M.Fabric)
			r.CastShadow = false
		end
		prevTop = top
	end
	for _, k in trailStations(14, TRAIL.n * 0.55, TRAIL.n - 6) do
		local c, out = trailPoint(k)
		local log = cyl(
			path,
			"Dimdol",
			c - out * 3.4 + V3(0, 0.05, 0),
			c + out * 3.4 + V3(0, 0.05, 0),
			0.9,
			C.charred:Lerp(P.wood, 0.4),
			M.Wood
		)
		log.CastShadow = false
	end
	-- 들머리: 비석과 갈라진 석등, 붉은 깃발
	local s0, out0 = trailPoint(0)
	local side0 = V3(-out0.Z, 0, out0.X)
	Kit.stele(path, V3(s0.X, gy(s0.X, s0.Z), s0.Z) - out0 * 9 - side0 * 4, "주염산", V3(300, 0, 540))
	crackedLantern(
		path,
		s0 - out0 * 6.5 + side0 * 3 + V3(0, gy(s0.X - out0.X * 6.5, s0.Z - out0.Z * 6.5) - s0.Y, 0),
		rng
	)
	for _, s in { -1, 1 } do
		local q = s0 + out0 * s * 8.5 - side0 * 6
		Build.banner(path, V3(q.X, gy(q.X, q.Z), q.Z), V3(VOL.x, 0, VOL.z), C.cloth, 10)
	end
	-- 길 가운데와 꼭대기 앞 석등
	for _, k in { TRAIL.n - 9 } do
		local c, out = trailPoint(k)
		local q = c - out * 6.2
		crackedLantern(path, V3(q.X, Land.height(q.X, q.Z), q.Z), rng)
	end

	-- 화구 둘레 사당: 길 끝 상품 영맥에서 화구 둘레를 따라 조금 더 간 곳, 영맥을 본다
	do
		local aV = math.atan2(vein.z - VOL.z, vein.x - VOL.x)
		local a = aV + rad(17)
		local d = 78
		local x, z = VOL.x + math.cos(a) * d, VOL.z + math.sin(a) * d
		local shrine, look, top = smallShrine(
			vol,
			x,
			z,
			V3(vein.x, 0, vein.z),
			{ name = "화신당", stone = C.basaltLight, stoneMat = M.Basalt }
		)
		-- 영맥 쪽으로 내려가는 돌계단
		local vy = gy(vein.x, vein.z)
		local front = look:PointToWorldSpace(V3(0, 0, -6.8))
		local dirV = (V3(vein.x, 0, vein.z) - V3(front.X, 0, front.Z)).Unit
		local nsteps = math.max(2, math.ceil((top - vy) / 1.1))
		for i = 1, nsteps do
			local y = top - i * (top - vy) / (nsteps + 1)
			local p = V3(front.X, 0, front.Z) + dirV * (i * 1.2 - 0.6)
			local ground = Land.height(p.X, p.Z)
			block(
				shrine,
				"Gyedan",
				V3(4.6, y - ground + 1.4, 1.4),
				face(V3(p.X, (y + ground - 1.4) / 2, p.Z), V3(vein.x, (y + ground) / 2, vein.z)),
				C.ash,
				M.Slate
			)
		end
		local q = look:PointToWorldSpace(V3(5.6, 0, -5.6))
		Build.banner(shrine, V3(q.X, top, q.Z), V3(vein.x, top, vein.z), C.cloth, 8)
		-- 사당 안 불 그릇
		local bowl = cyl(
			shrine,
			"Hwaro",
			look:PointToWorldSpace(V3(0, top + 1.1, 1)),
			look:PointToWorldSpace(V3(0, top + 2.4, 1)),
			2.2,
			C.iron,
			M.Metal
		)
		bowl.CastShadow = false
		local flame = neon(shrine, "Bul", V3(1.4, 1.2, 1.4), look * CF(0, top + 3.0, 1), C.glowHot)
		glowLight(flame, C.glow, 16, 1.6)
	end

	-- 현무암 바위와 불탄 나무: 아랫비탈 (길과 비워 둘 자리를 비켜서)
	local nature = folder(vol, "비탈")
	local placed = 0
	local tries = 0
	while placed < 13 and tries < 200 do
		tries += 1
		local a = rad(rng(0, 360))
		local d = rng(150, 292)
		local x, z = VOL.x + math.cos(a) * d, VOL.z + math.sin(a) * d
		if not nearRoad(x, z, 9) and not blocked(x, z, 6) then
			local s = rng(4, 9)
			boulder(nature, V3(x, lowAt(x, z, s * 0.4), z), s, rng, C.basalt, M.Basalt)
			placed += 1
		end
	end
	placed, tries = 0, 0
	while placed < 9 and tries < 200 do
		tries += 1
		-- 홍로성 쪽(북서) 기슭에 더 많이
		local a = rad(if tries % 3 == 0 then rng(0, 360) else rng(170, 300))
		local d = rng(215, 310)
		local x, z = VOL.x + math.cos(a) * d, VOL.z + math.sin(a) * d
		if not nearRoad(x, z, 7) and not blocked(x, z, 4) then
			deadTree(
				nature,
				V3(x, lowAt(x, z, 0.8), z),
				rng,
				{ name = "탄 나무", height = rng(6, 12), branches = if rng(0, 1) > 0.5 then 3 else 2 }
			)
			placed += 1
		end
	end
	-- 들머리 둘레 바위 몇 (길 곁)
	for i = 1, 4 do
		local k = ({ 8, 30, 62, 95 })[i]
		local c, out = trailPoint(k)
		local q = c - out * rng(9, 12)
		boulder(nature, V3(q.X, lowAt(q.X, q.Z, 2), q.Z), rng(4, 6.5), rng, C.basaltLight, M.Basalt)
	end
	return vol
end

-- 벽계협 ------------------------------------------------------------------------------------

local GPTS = Land.GORGE.pts
local GLEN = { 0 }
for i = 2, #GPTS do
	local a, b = GPTS[i - 1], GPTS[i]
	GLEN[i] = GLEN[i - 1] + math.sqrt((b[1] - a[1]) ^ 2 + (b[2] - a[2]) ^ 2)
end
-- 협곡 물길 길이 s 의 점, 흐름 방향, 동쪽(오른쪽) 법선
local function gorgeAt(s: number): (Vector2, Vector2, Vector2)
	for i = 2, #GPTS do
		if s <= GLEN[i] or i == #GPTS then
			local a, b = GPTS[i - 1], GPTS[i]
			local t = math.clamp((s - GLEN[i - 1]) / (GLEN[i] - GLEN[i - 1]), 0, 1)
			local dir = Vector2.new(b[1] - a[1], b[2] - a[2]).Unit
			return Vector2.new(a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t), dir, Vector2.new(-dir.Y, dir.X)
		end
	end
	error("gorge")
end
-- 물길 s, 옆 거리 off (동쪽 +) 의 땅 위 점
local function gorgePoint(s: number, off: number): Vector3
	local p, _, n = gorgeAt(s)
	local q = p + n * off
	return V3(q.X, Land.height(q.X, q.Y), q.Y)
end
local function gorgeS(z: number): number
	-- z 가 처음 닿는 s (협곡은 남으로만 흐른다)
	local lo, hi = 0, GLEN[#GLEN]
	for _ = 1, 30 do
		local mid = (lo + hi) / 2
		local p = gorgeAt(mid)
		if p.Y < z then
			lo = mid
		else
			hi = mid
		end
	end
	return lo
end

-- 출렁다리: a, b (양끝 땅 위) 사이 늘어진 널판, 손 밧줄, 말뚝
local function ropeBridge(parent: Instance, a: Vector3, b: Vector3, sag: number, width: number)
	local m = model(parent, "출렁다리")
	local n = 9
	local flat = V3(b.X - a.X, 0, b.Z - a.Z).Unit
	local side = V3(-flat.Z, 0, flat.X)
	local function pt(t: number): Vector3
		return a:Lerp(b, t) - V3(0, sag * 4 * t * (1 - t), 0)
	end
	for i = 1, n do
		local p, q = pt((i - 1) / n), pt(i / n)
		local d = (q - p).Unit
		beam(m, "Neolpan", p - d * 0.15, q + d * 0.15, width, 0.4, C.plankOld, M.WoodPlanks)
		for _, s in { -1, 1 } do
			local r = beam(
				m,
				"Sonjul",
				p + side * s * (width / 2) + V3(0, 3.1, 0),
				q + side * s * (width / 2) + V3(0, 3.1, 0),
				0.18,
				0.18,
				C.rope,
				M.Fabric
			)
			r.CastShadow = false
			if i % 3 == 0 then
				local hng = beam(
					m,
					"Deuljul",
					q + side * s * (width / 2),
					q + side * s * (width / 2) + V3(0, 3.1, 0),
					0.12,
					0.12,
					C.rope,
					M.Fabric
				)
				hng.CastShadow = false
			end
		end
	end
	for _, e in { a, b } do
		for _, s in { -1, 1 } do
			local o = e + side * s * (width / 2 + 0.2)
			beam(m, "Malttuk", o - V3(0, 2, 0), o + V3(0, 3.8, 0), 0.8, 0.8, P.woodDark, M.Wood)
		end
	end
	return m
end

local function buildGorge(root: Instance, rng)
	local gorge = folder(root, "벽계협")
	local cliffs = folder(gorge, "벼랑")
	local sStart, sRapids = gorgeS(232), gorgeS(Land.RAPIDS.z - 8)
	-- 다리 자리
	local sHigh = gorgeS(530)
	local sLow = gorgeS(815)
	-- 벼랑 면: 물길 양쪽 벽 가운데쯤(옆 27)에 기운 바위 판. 다리 곁은 비운다
	local stretches = {
		{ 130, 172, 1 },
		{ 225, 262, -1 },
		{ sHigh - 62, sHigh - 22, -1 },
		{ sHigh + 22, sHigh + 62, 1 },
		{ 640, 685, 1 },
		{ sLow + 22, sLow + 62, -1 },
		{ 955, 994, -1 },
		{ 960, 996, 1 },
	}
	for _, st in stretches do
		local side = st[3]
		local s = math.max(st[1], sStart)
		while s < st[2] - 4 do
			local s2 = math.min(st[2], s + 24)
			local a, b = gorgePoint(s, side * 27), gorgePoint(s2, side * 27)
			local _, _, n = gorgeAt((s + s2) / 2)
			local out = V3(-n.X * side, 0, -n.Y * side) -- 물길 쪽
			local cm = Build.cliffFace(cliffs, a, b, out, function(x, z)
				-- 여울 근처는 땅이 바닥(-19.6)보다 낮다: 낮은 바위턱만 남긴다
				return math.max(Land.height(x - out.X * 9, z - out.Z * 9) + 0.5, -17.6)
			end, function()
				return -19.6
			end, rng, { spacing = 5.2, color = Color3.fromRGB(104, 108, 100) })
			local k = 0
			for _, part in cm:GetChildren() do
				k += 1
				if part:IsA("BasePart") and k % 3 == 1 then
					local top = part.CFrame * CF(0, part.Size.Y / 2 + 0.12, 0)
					deco(
						block(
							cm,
							"Ikki",
							V3(part.Size.X * 0.8, 0.3, part.Size.Z * 0.7),
							top,
							jitter(C.moss, rng, 0.08),
							M.LeafyGrass
						)
					).CastShadow =
						false
				end
			end
			s = s2
		end
	end

	-- 물길 바위, 흰 물보라
	local stream = folder(gorge, "물길")
	local s = sStart + 30
	while s < sRapids - 20 do
		local off = (if rng(0, 1) > 0.5 then 1 else -1) * rng(3.5, 7.5)
		local q = gorgePoint(s, off)
		local size = rng(5, 7.5)
		local _, main = boulder(stream, V3(q.X, q.Y, q.Z), size, rng, Color3.fromRGB(96, 100, 94), M.Slate)
		if q.Y < -21 then
			local foam = deco(
				block(
					stream,
					"Mulbora",
					V3(size * 1.5, 0.15, size * 1.1),
					CF(q.X, -19.88, q.Z) * CFrame.Angles(0, main.CFrame:ToEulerAnglesYXZ(), 0),
					C.foam,
					M.SmoothPlastic
				)
			)
			foam.Transparency = 0.45
			foam.CastShadow = false
		end
		s += rng(60, 100)
	end
	-- 여울: 협곡 물(-20)이 턱을 넘어 무택(-24)으로. 흰 물 판 셋, 물보라 파티클, 턱 양쪽 바위
	do
		local rap = model(stream, "여울")
		local sl = gorgeS(Land.RAPIDS.z - 6)
		local p, dir, n = gorgeAt(sl)
		local look = face(V3(p.X, 0, p.Y), V3(p.X + dir.X, 0, p.Y + dir.Y)) -- -Z 가 흐르는 쪽
		for i, o in { { -1, -20.05, 0 }, { 3.5, -21.6, 24 }, { 7.5, -23.4, 14 } } do
			local w = deco(
				block(
					rap,
					"Huinmul",
					V3(15 - i, 0.25, 5.2),
					look * CF(0, o[2], -o[1]) * CFrame.Angles(rad(-o[3]), 0, 0),
					C.foam,
					M.SmoothPlastic
				)
			)
			w.Transparency = 0.25 + 0.1 * i
			w.CastShadow = false
		end
		local em = deco(block(rap, "Mulbora", V3(12, 0.4, 3), look * CF(0, -23.6, -8), C.foam, M.SmoothPlastic))
		em.Transparency = 1
		local foam = Instance.new("ParticleEmitter")
		foam.Name = "Mulbora"
		foam.Texture = "rbxasset://textures/particles/smoke_main.dds"
		foam.Rate = 14
		foam.Lifetime = NumberRange.new(1, 2)
		foam.Speed = NumberRange.new(2, 5)
		foam.SpreadAngle = Vector2.new(40, 40)
		foam.Acceleration = V3(0, -4, 0)
		foam.Size = NumberSequence.new({ kp(0, 2), kp(1, 5) })
		foam.Transparency = NumberSequence.new({ kp(0, 0.4), kp(1, 1) })
		foam.Color = ColorSequence.new(C.foam)
		foam.Parent = em
		for _, side in { -1, 1 } do
			for k = 0, 1 do
				local q = p + n * side * (8 + k * 4.5) + dir * (k * 3 - 1)
				boulder(rap, V3(q.X, Land.height(q.X, q.Y), q.Y), rng(5, 7), rng, Color3.fromRGB(96, 100, 94), M.Slate)
			end
		end
	end

	-- 벼랑 밑 턱(-19): 고사리와 이끼
	local ledge = folder(gorge, "턱")
	s = sStart + 15
	while s < sRapids - 10 do
		local side = if rng(0, 1) > 0.5 then 1 else -1
		local q = gorgePoint(s, side * rng(11, 18))
		if q.Y < -17 then
			fern(ledge, q, rng, rng(1.6, 2.6))
			if rng(0, 1) > 0.5 then
				local mo = deco(
					block(
						ledge,
						"Ikki",
						V3(rng(4, 7), 0.3, rng(3, 5)),
						CF(q + V3(rng(-2, 2), 0.05, rng(-2, 2))) * CFrame.Angles(0, rng(0, 3), 0),
						jitter(C.moss, rng, 0.08),
						M.LeafyGrass
					)
				)
				mo.CastShadow = false
			end
		end
		s += rng(40, 66)
	end

	-- 높은 출렁다리 (홍로성 서문 길 → 황구 쪽) 와 낮은 널다리 (협곡 바닥 길 건너기)
	local bridges = folder(gorge, "다리")
	local hA, hB = gorgePoint(sHigh, 39), gorgePoint(sHigh, -39)
	ropeBridge(bridges, hA + V3(0, 0.4, 0), hB + V3(0, 0.4, 0), 4.5, 4.2)
	do
		local p, dir, n = gorgeAt(sLow)
		local a = Vector2.new(p.X, p.Y) + n * 10
		local b = Vector2.new(p.X, p.Y) - n * 10
		local m = model(bridges, "널다리")
		local y = -18.4
		beam(m, "Neolpan", V3(a.X, y, a.Y), V3(b.X, y, b.Y), 3.6, 0.5, C.plankOld, M.WoodPlanks)
		for _, e in { a:Lerp(b, 0.3), a:Lerp(b, 0.7) } do
			for _, sgn in { -1, 1 } do
				local q = e + dir * sgn * 1.5
				beam(m, "Gidung", V3(q.X, -25, q.Y), V3(q.X, y - 0.2, q.Y), 0.7, 0.7, P.woodDark, M.Wood)
			end
		end
		local sideOff = V3(dir.X, 0, dir.Y) * 1.7
		beam(
			m,
			"Nangan",
			V3(a.X, y + 2.6, a.Y) + sideOff,
			V3(b.X, y + 2.6, b.Y) + sideOff,
			0.25,
			0.25,
			P.woodDark,
			M.Wood
		)
		for _, t in { 0.3, 0.7 } do
			local q = a:Lerp(b, t)
			beam(
				m,
				"Nangan",
				V3(q.X, y, q.Y) + sideOff,
				V3(q.X, y + 2.6, q.Y) + sideOff,
				0.25,
				0.25,
				P.woodDark,
				M.Wood
			)
		end
	end
	-- 서문 → 출렁다리 흙길, 다리 머리 비석
	local trail = folder(gorge, "길")
	local cityW = Vector2.new(CX - HALF - 10, 560)
	local bridgeE = Vector2.new(hA.X, hA.Z) + (Vector2.new(hA.X, hA.Z) - Vector2.new(hB.X, hB.Z)).Unit * 3
	local mid = Vector2.new((cityW.X + bridgeE.X) / 2, (cityW.Y + bridgeE.Y) / 2 + 8)
	pave(trail, cityW, mid, 5, C.dirt, M.Ground, { seg = 18, lift = 0.15, name = "Heukgil" })
	pave(trail, mid, bridgeE, 5, C.dirt, M.Ground, { seg = 18, lift = 0.15, name = "Heukgil" })
	local bridgeW = Vector2.new(hB.X, hB.Z) + (Vector2.new(hB.X, hB.Z) - Vector2.new(hA.X, hA.Z)).Unit * 3
	pave(
		trail,
		bridgeW,
		bridgeW + (bridgeW - bridgeE).Unit * 26,
		5,
		C.dirt,
		M.Ground,
		{ seg = 13, lift = 0.15, name = "Heukgil" }
	)
	local sideV = (bridgeE - Vector2.new(hB.X, hB.Z)).Unit
	local stelePos = bridgeE + Vector2.new(-sideV.Y, sideV.X) * 6 + sideV * 3
	Kit.stele(trail, V3(stelePos.X, gy(stelePos.X, stelePos.Y), stelePos.Y), "벽계협", V3(CX, 0, CZ))

	-- 벼랑 위 나무: 소나무와 활엽수 (물길에서 40~62 떨어진 위)
	local rim = folder(gorge, "벼랑 위")
	s = sStart + 10
	local k = 0
	while s < sRapids - 30 do
		k += 1
		local side = if k % 2 == 0 then 1 else -1
		local q = gorgePoint(s, side * rng(41, 60))
		if not nearRoad(q.X, q.Z, 7) and not blocked(q.X, q.Z, 5) and math.abs(q.X - (CX - HALF)) > 20 then
			local g = lowAt(q.X, q.Z, 1)
			if k % 2 == 0 then
				Build.broadleaf(rim, V3(q.X, g, q.Z), rng, { height = rng(10, 14), blobs = 6 })
			else
				Build.pine(rim, V3(q.X, g, q.Z), rng, { height = rng(12, 17), tiers = 4 })
			end
			if k % 3 == 0 then
				local r = gorgePoint(s + 6, side * rng(38, 46))
				Build.shrub(rim, V3(r.X, r.Y, r.Z), rng, { size = rng(2.5, 4), blobs = 2 })
			end
		end
		s += rng(78, 112)
	end
	return gorge
end

-- 무택 ----------------------------------------------------------------------------------------

local MARSH = Land.MARSH
local POND_Y = -22.4 -- 늪 물낯 (지형 물은 바다 높이 -24 아래에만 있어서, 늪 전체에 얕은 물판 한 장을 깐다: 패인 곳만 물로 보인다)

-- 갈대 포기 (가는 줄기 넷, 이삭 둘). Build.reeds 보다 부품이 적다
local function reedClump(parent: Instance, base: Vector3, rng, dry: boolean?)
	local m = model(parent, "갈대")
	for i = 1, 4 do
		local a, r = rng(0, math.pi * 2), rng(0, 1.3)
		local foot = base + V3(math.cos(a) * r, -0.4, math.sin(a) * r)
		local h = rng(3.5, 5.5)
		local dir = V3(rng(-0.22, 0.22), 1, rng(-0.22, 0.22)).Unit
		local stalk = deco(
			beam(
				m,
				"Julgi",
				foot,
				foot + dir * h,
				0.14,
				0.14,
				if dry then C.reedDry else Color3.fromRGB(122, 136, 78),
				M.Grass
			)
		)
		stalk.CastShadow = false
		if i <= 2 then
			local head = deco(
				beam(
					m,
					"Isak",
					foot + dir * (h - 0.2),
					foot + dir * (h + 1.0),
					0.32,
					0.32,
					Color3.fromRGB(176, 150, 112),
					M.Fabric
				)
			)
			head.CastShadow = false
		end
	end
	return m
end

-- 연잎: 물낯 위 납작한 원판 (몇 장은 꽃)
local function lilies(parent: Instance, c: Vector3, rng, n: number)
	local m = model(parent, "연잎")
	for i = 1, n do
		local a, r = rng(0, math.pi * 2), rng(0, 3.5)
		local p = V3(c.X + math.cos(a) * r, POND_Y + 0.08, c.Z + math.sin(a) * r)
		local d = rng(1.6, 3)
		local pad = deco(
			block(
				m,
				"Yeonip",
				V3(0.12, d, d),
				CF(p) * CFrame.Angles(0, rng(0, 3), rad(90)),
				jitter(C.lily, rng, 0.12),
				M.SmoothPlastic
			)
		)
		pad.Shape = Enum.PartType.Cylinder
		pad.CastShadow = false
		if i == 1 and rng(0, 1) > 0.4 then
			deco(ball(m, "Kkot", p + V3(0.3, 0.3, 0), 0.7, Color3.fromRGB(236, 176, 196), M.SmoothPlastic)).CastShadow =
				false
		end
	end
	return m
end

-- 무택 고탑: 기운 옛 목탑 (Build.pagoda 와 같은 모양을 가볍게: 처마 귀 쪼갬 1). 아래층은 늪에 묻히고 꼭대기는 부서졌다
local function sunkenPagoda(parent: Instance, ground: Vector3, rng)
	local m = model(parent, "무택 고탑")
	local floors, base = 4, 12.5
	local sink = 6.5
	local cf = CF(ground - V3(0, sink, 0))
	local plaster = Color3.fromRGB(176, 168, 146)
	local pillar = Color3.fromRGB(110, 62, 52)
	local tile = Color3.fromRGB(66, 74, 70)
	local y = 1.4
	for i = 1, floors do
		local s = base * (1 - 0.13 * (i - 1))
		local hgt = if i == 1 then 7.5 else 4.6
		local body = model(m, i .. "층")
		local fcf = cf * CF(0, y, 0)
		block(
			body,
			"Byeok",
			V3(s - 0.6, hgt, s - 0.6),
			fcf * CF(0, hgt / 2, 0),
			plaster:Lerp(C.moss, 0.12 * (floors - i) / floors),
			M.Plaster
		)
		for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
			cyl(
				body,
				"Gidung",
				fcf:PointToWorldSpace(V3(c[1] * s / 2, 0, c[2] * s / 2)),
				fcf:PointToWorldSpace(V3(c[1] * s / 2, hgt, c[2] * s / 2)),
				0.9,
				pillar,
				M.Wood
			)
		end
		block(
			body,
			"Changbang",
			V3(s + 0.9, 0.9, s + 0.9),
			fcf * CF(0, hgt - 0.45, 0),
			P.noerok:Lerp(plaster, 0.45),
			M.Wood
		)
		if i == 2 then
			block(body, "Mun", V3(2.4, 3.4, 0.3), fcf * CF(0, 1.9, -(s - 0.6) / 2 - 0.1), P.woodDark, M.Wood)
		end
		local eave = 3 - 0.2 * (i - 1)
		local spec = {
			ex = s / 2 + eave,
			ez = s / 2 + eave,
			eave = eave,
			bands = 2,
			kind = "hip",
			pitchLow = 16,
			pitchHigh = 34,
			lift = 1.1,
			flare = 0.4,
			segs = 1,
			t = 0.5,
			color = tile,
			ridgeColor = Color3.fromRGB(48, 54, 52),
		}
		local _, _, hh, pitches = Build.profile(spec)
		local under = hh[1] - 0.5 / math.cos(rad(pitches[1]))
		local eaveY = y + hgt + 0.05 - under
		if i < floors then
			local nextS = base * (1 - 0.13 * i)
			spec.stopInset = spec.ex - (nextS - 0.6) / 2 + 0.2
			Build.roof(body, cf * CF(0, eaveY, 0), spec)
			y = eaveY + hh[1] + 0.2
		else
			-- 꼭대기: 지붕 한쪽이 무너졌다 (+X 쪽 기와를 덜고), 상륜은 부러진 찰주만
			local r = Build.roof(body, cf * CF(0, eaveY, 0), spec)
			for _, d in r.model:GetChildren() do
				if d:IsA("BasePart") then
					local lp = cf:PointToObjectSpace(d.CFrame.Position)
					if lp.X > 1.5 and (d.Name == "Giwa" or d.Name == "Maru" or d.Name == "Mangwa") and lp.Z > -2 then
						d:Destroy()
					end
				end
			end
			local tip = cf:PointToWorldSpace(V3(0, eaveY + r.height, 0))
			cyl(
				body,
				"Chalju",
				tip,
				tip + (cf.UpVector + V3(0.25, 0, 0.1)).Unit * 3.2,
				0.32,
				Color3.fromRGB(130, 110, 70),
				M.Metal
			)
			-- 무너진 쪽 서까래 끝 (드러난 뼈대)
			for k = -1, 1 do
				beam(
					body,
					"Seokkarae",
					cf:PointToWorldSpace(V3(1.2, eaveY + r.height - 1.2, k * 1.6)),
					cf:PointToWorldSpace(V3(s / 2 + 1.6, eaveY + 0.6, k * 2.2)),
					0.35,
					0.35,
					P.woodDark,
					M.Wood
				)
			end
		end
	end
	-- 기울인다 (북동으로 8°)
	transformModel(m, CF(ground), CFrame.Angles(rad(-5.5), 0, rad(-5.8)))
	-- 늪에 묻힌 부품은 덜어 낸다
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			local top = d.CFrame.Position.Y
				+ 0.5
					* (math.abs(d.CFrame.UpVector.Y) * d.Size.Y + math.abs(d.CFrame.RightVector.Y) * d.Size.X + math.abs(
						d.CFrame.LookVector.Y
					) * d.Size.Z)
			if top < Land.height(d.CFrame.Position.X, d.CFrame.Position.Z) - 0.3 then
				d:Destroy()
			end
		end
	end
	-- 둘레에 떨어진 기와 조각, 쓰러진 기둥, 상륜 조각, 담쟁이
	local debris = model(parent, "고탑 잔해")
	for i = 1, 7 do
		local a = rng(0, math.pi * 2)
		local r = rng(9, 17)
		local x, z = ground.X + math.cos(a) * r, ground.Z + math.sin(a) * r
		tiltedPiece(
			debris,
			V3(x, Land.height(x, z) + 0.15, z),
			V3(rng(2, 4), 0.5, rng(1.5, 3)),
			rng,
			tile,
			M.ClayRoofTiles
		)
	end
	do
		local a = rng(0, math.pi * 2)
		local p = ground + V3(math.cos(a) * 11, 0, math.sin(a) * 11)
		local q = p + V3(math.cos(a + 1.2) * 7, 0, math.sin(a + 1.2) * 7)
		cyl(
			debris,
			"Gidung",
			V3(p.X, Land.height(p.X, p.Z) + 0.3, p.Z),
			V3(q.X, Land.height(q.X, q.Z) + 0.3, q.Z),
			0.9,
			pillar,
			M.Wood
		)
		local b = ground + V3(-13, 0, 6)
		ball(debris, "Boju", V3(b.X, Land.height(b.X, b.Z) + 0.3, b.Z), 1.1, Color3.fromRGB(130, 110, 70), M.Metal)
		cyl(
			debris,
			"Boryun",
			V3(b.X + 1.2, Land.height(b.X, b.Z) + 0.3, b.Z),
			V3(b.X + 1.6, Land.height(b.X, b.Z) + 0.3, b.Z + 0.3),
			1.6,
			Color3.fromRGB(130, 110, 70),
			M.Metal
		)
	end
	return m
end

-- 늪 짓기
local function buildMarsh(root: Instance, rng)
	local marsh = folder(root, "무택")
	local water = folder(marsh, "물")
	-- 물판: 늪 가운데 둥근 판 한 장. 가장자리(반지름 300)는 모두 물낯보다 높은 땅 밑이라 보이지 않는다 (둘레를 재 봤다)
	local pond = deco(
		block(
			water,
			"Neup",
			V3(0.2, 600, 600),
			CF(MARSH.x, POND_Y - 0.1, MARSH.z) * CFrame.Angles(0, 0, rad(90)),
			C.marshWater,
			M.Glass
		)
	)
	pond.Shape = Enum.PartType.Cylinder
	pond.Transparency = 0.35
	pond.Reflectance = 0.08
	pond.CastShadow = false
	-- 늪 들풀: 연잎(패인 물 위), 갈대(물가), 버드나무와 고사목(조금 높은 땅)
	local plants = folder(marsh, "풀")
	local nLily, nReed, nWillow, nDead = 0, 0, 0, 0
	for _ = 1, 900 do
		if nLily >= 10 and nReed >= 10 and nWillow >= 4 and nDead >= 6 then
			break
		end
		local a = rng(0, math.pi * 2)
		local r = MARSH.r * math.sqrt(rng(0, 1)) * 1.05
		local x, z = MARSH.x + math.cos(a) * r, MARSH.z + math.sin(a) * r
		if
			Land.blob(x, z, MARSH) > 0.5
			and not nearRoad(x, z, 9)
			and not blocked(x, z, 6)
			and (x - Land.TOWER.x) ^ 2 + (z - Land.TOWER.z) ^ 2 > 30 ^ 2
			and (x - Land.STARS.south.x) ^ 2 + (z - Land.STARS.south.z) ^ 2 > 40 ^ 2
			and Land.polyDist(x, z, Land.GORGE, 30) > 18
		then
			local h = Land.height(x, z)
			if h < POND_Y - 0.8 and nLily < 10 then
				lilies(plants, V3(x, h, z), rng, math.floor(rng(3, 5.99)))
				nLily += 1
			elseif h > POND_Y - 0.4 and h < POND_Y + 1.2 and nReed < 10 then
				reedClump(plants, V3(x, h, z), rng, nReed % 3 == 0)
				nReed += 1
			elseif h > POND_Y + 1.2 and nWillow < 4 and nReed > nWillow then
				Build.willow(plants, V3(x, lowAt(x, z, 1), z), rng, { height = rng(10, 13), strands = 12, blobs = 4 })
				nWillow += 1
			elseif h > POND_Y + 0.6 and nDead < 6 then
				deadTree(
					plants,
					V3(x, lowAt(x, z, 0.8), z),
					rng,
					{ color = C.deadWood, height = rng(7, 12), girth = 0.08, branches = 3 }
				)
				nDead += 1
			end
		end
	end
	-- 안개: 늪 위를 낮게 떠도는 큰 김 (보이지 않는 판에 파티클)
	for i = 1, 6 do
		local a = rad(i * 60 + 15)
		local x, z = MARSH.x + math.cos(a) * 150, MARSH.z + math.sin(a) * 150
		local fog = deco(block(water, "Angae", V3(70, 1, 70), CF(x, -21, z), C.foam, M.SmoothPlastic))
		fog.Transparency = 1
		smoke(
			fog,
			{
				rate = 1.4,
				size0 = 18,
				size1 = 34,
				life = 14,
				speed = 0.6,
				spread = 80,
				alpha = 0.86,
				color = Color3.fromRGB(222, 228, 226),
				accel = V3(0.3, 0.05, 0.2),
				drag = 0.2,
			}
		)
	end

	-- 둑길 위 널길 (Land.BENCHES.causeway → 남명대): 기둥 위 널판, 늪 쪽은 양쪽 난간
	local walk = folder(marsh, "널길")
	local cw = Land.BENCHES.causeway.pts
	local prevL, prevR = nil, nil
	for i = 2, #cw do
		local a, b = Vector2.new(cw[i - 1][1], cw[i - 1][2]), Vector2.new(cw[i][1], cw[i][2])
		local ya, yb = cw[i - 1][3], cw[i][3]
		local len = (b - a).Magnitude
		local n = math.max(1, math.ceil(len / 18))
		local dir = (b - a).Unit
		local side = Vector2.new(-dir.Y, dir.X)
		for k = 1, n do
			-- 마지막 끝 (남명대 단 바로 앞) 은 단에 닿게 짧게
			local t0, t1 = (k - 1) / n, k / n
			local p, q = a:Lerp(b, t0), a:Lerp(b, t1)
			local yp, yq = ya + (yb - ya) * t0 + 1.1, ya + (yb - ya) * t1 + 1.1
			if i == #cw and k == n then
				q = a:Lerp(b, 0.92)
			end
			beam(
				walk,
				"Neolpan",
				V3(p.X, yp, p.Y) - V3(dir.X, 0, dir.Y) * 0.2,
				V3(q.X, yq, q.Y) + V3(dir.X, 0, dir.Y) * 0.2,
				5,
				0.5,
				C.plankOld,
				M.WoodPlanks
			)
			for _, s in { -1, 1 } do
				local o = q + side * s * 2.6
				local g = Land.height(o.X, o.Y)
				local top = V3(o.X, yq + 2.7, o.Y)
				beam(
					walk,
					"Gidung",
					V3(o.X, math.min(g, yq) - 1.5, o.Y),
					top + V3(0, 0.2, 0),
					0.5,
					0.5,
					P.woodDark,
					M.Wood
				)
				local prev = if s < 0 then prevL else prevR
				if prev and i > 2 then
					local rail = beam(walk, "Nangan", prev, top, 0.28, 0.24, P.woodDark, M.Wood)
					rail.CastShadow = false
				end
				if s < 0 then
					prevL = top
				else
					prevR = top
				end
			end
		end
	end
	-- 둑길 어귀 (홍로성 남문 길 끝): 비석
	Kit.stele(walk, V3(cw[1][1] + 7, gy(cw[1][1] + 7, cw[1][2] - 4), cw[1][2] - 4), "무택", V3(CX, 0, CZ))

	-- 무택 고탑
	local tw = Land.TOWER
	sunkenPagoda(marsh, V3(tw.x, Land.height(tw.x, tw.z), tw.z), rng)
	return marsh
end

-- 남명대 둘레: 돌 단 가장자리 갓돌, 석등 둘, 붉은 깃발 (단 가운데 제단은 허브가 놓는다)
local function buildStarTerrace(root: Instance, rng)
	local f = folder(root, "남명대")
	local st = Land.STARS.south
	local wp = Sites.byId.wp_south
	local R = 29
	local n = 20
	local y = st.height
	for i = 0, n - 1 do
		local a0, a1 = (i / n) * math.pi * 2, ((i + 0.85) / n) * math.pi * 2
		local p = V3(st.x + math.cos(a0) * R, y, st.z + math.sin(a0) * R)
		local q = V3(st.x + math.cos(a1) * R, y, st.z + math.sin(a1) * R)
		local mid = (p + q) / 2
		-- 전송진 곁과 둑길 들어오는 동쪽은 비운다
		local dWp = math.sqrt((mid.X - wp.x) ^ 2 + (mid.Z - wp.z) ^ 2)
		local east = math.abs(((a0 + a1) / 2) - 0) < 0.35 or math.abs(((a0 + a1) / 2) - math.pi * 2) < 0.35
		if dWp > 13 and not east then
			local low = math.min(Land.height(p.X, p.Z), Land.height(q.X, q.Z), Land.height(mid.X * 1.0, mid.Z))
			local h = y + 0.9 - (low - 1.5)
			block(
				f,
				"Gapdol",
				V3(2.2, h, (q - p).Magnitude + 0.4),
				face(V3(mid.X, low - 1.5 + h / 2, mid.Z), V3(q.X, low - 1.5 + h / 2, q.Z)),
				P.granite:Lerp(C.moss, 0.15),
				M.Granite
			)
		end
	end
	-- 남쪽 석등 둘, 깃발 둘 (남방 주작의 붉은 빛)
	for _, deg in { 120, 240 } do
		local a = rad(deg)
		local g = V3(st.x + math.cos(a) * (R + 4), 0, st.z + math.sin(a) * (R + 4))
		Build.stoneLantern(f, V3(g.X, Land.height(g.X, g.Z), g.Z))
	end
	for _, deg in { 75, 285 } do
		local a = rad(deg)
		local g = V3(st.x + math.cos(a) * (R + 3), 0, st.z + math.sin(a) * (R + 3))
		Build.banner(f, V3(g.X, Land.height(g.X, g.Z), g.Z), V3(st.x, 0, st.z), Color3.fromRGB(176, 60, 46), 11)
	end
	return f
end

-- 백사포 ------------------------------------------------------------------------------------

-- 고깃배: 밑판, 두 마디로 좁아지는 뱃전, 고물판, 가로 널, 돛대(접은 돛). cf 는 배 밑 가운데, 이물이 -Z
local function boat(parent: Instance, cf: CFrame, rng, opts)
	opts = opts or {}
	local m = model(parent, "고깃배")
	local L, W = opts.len or rng(11, 14), opts.width or rng(3.6, 4.4)
	local wood = jitter(C.boat, rng, 0.08)
	block(m, "Mitpan", V3(W - 0.8, 0.5, L * 0.72), cf * CF(0, 0.25, L * 0.12), wood:Lerp(P.woodDark, 0.4), M.WoodPlanks)
	for _, s in { -1, 1 } do
		local stern = cf:PointToWorldSpace(V3(s * W / 2, 1.0, L / 2))
		local mid = cf:PointToWorldSpace(V3(s * W / 2, 1.0, -L * 0.18))
		local bow = cf:PointToWorldSpace(V3(0, 1.5, -L / 2))
		beam(m, "Baetjeon", stern, mid, 0.35, 1.7, wood, M.WoodPlanks)
		beam(m, "Baetjeon", mid, bow, 0.35, 1.7, wood, M.WoodPlanks)
	end
	block(m, "Gomul", V3(W, 1.6, 0.35), cf * CF(0, 1.0, L / 2), wood:Lerp(P.woodDark, 0.2), M.WoodPlanks)
	block(m, "Gamok", V3(W - 0.5, 0.3, 1.0), cf * CF(0, 1.4, L * 0.08), wood, M.WoodPlanks)
	if opts.mast ~= false then
		local foot = cf:PointToWorldSpace(V3(0, 0.5, -L * 0.12))
		cyl(m, "Dotdae", foot, foot + cf.UpVector * 9, 0.35, P.woodDark, M.Wood)
		cyl(
			m,
			"Dot",
			foot + cf.UpVector * 4.2 + cf.RightVector * 0.05,
			foot + cf.UpVector * 4.2 + cf.LookVector * -(L * 0.38),
			0.7,
			C.clothWhite:Lerp(C.dirt, 0.25),
			M.Fabric
		)
	end
	return m
end

-- 잔교: a(뭍) → b(바다), 널판 높이 y. 기둥은 모래·바다 밑까지
local function jetty(parent: Instance, a: Vector2, b: Vector2, y: number)
	local m = model(parent, "잔교")
	local len = (b - a).Magnitude
	local dir = (b - a).Unit
	local side = Vector2.new(-dir.Y, dir.X)
	local n = math.ceil(len / 12)
	for k = 1, n do
		local p, q = a:Lerp(b, (k - 1) / n), a:Lerp(b, k / n)
		beam(
			m,
			"Neolpan",
			V3(p.X, y, p.Y) - V3(dir.X, 0, dir.Y) * 0.2,
			V3(q.X, y, q.Y) + V3(dir.X, 0, dir.Y) * 0.2,
			4,
			0.5,
			C.plankOld,
			M.WoodPlanks
		)
		for _, s in { -1, 1 } do
			local o = q + side * s * 1.9
			beam(
				m,
				"Gidung",
				V3(o.X, Land.height(o.X, o.Y) - 1.2, o.Y),
				V3(o.X, y + 1.3, o.Y),
				0.6,
				0.6,
				P.woodDark,
				M.Wood
			)
		end
	end
	return m
end

-- 덕장: 생선 너는 장대 또는 그물 너는 장대
local function dryingRack(parent: Instance, cf: CFrame, rng, fish: boolean)
	local m = model(parent, "덕장")
	local w = 8
	for _, x in { -w / 2, w / 2 } do
		beam(
			m,
			"Gidung",
			cf:PointToWorldSpace(V3(x, -0.6, 0)),
			cf:PointToWorldSpace(V3(x, 4.4, 0)),
			0.4,
			0.4,
			P.wood,
			M.Wood
		)
	end
	beam(
		m,
		"Garodae",
		cf:PointToWorldSpace(V3(-w / 2 - 0.3, 4.1, 0)),
		cf:PointToWorldSpace(V3(w / 2 + 0.3, 4.1, 0)),
		0.25,
		0.25,
		P.wood,
		M.Wood
	)
	if fish then
		for i = 1, 5 do
			local x = -w / 2 + i * w / 6
			local f = block(
				m,
				"Saengseon",
				V3(0.55, rng(1.4, 1.9), 0.22),
				cf * CF(x, 3.1, 0) * CFrame.Angles(0, 0, rad(rng(-6, 6))),
				jitter(C.fish, rng, 0.1),
				M.SmoothPlastic
			)
			f.CastShadow = false
		end
	else
		local net = block(
			m,
			"Geumul",
			V3(w - 0.3, 3.2, 0.12),
			cf * CF(0, 2.5, 0.1) * CFrame.Angles(rad(5), 0, 0),
			C.net,
			M.Fabric
		)
		net.Transparency = 0.2
		net.CastShadow = false
	end
	return m
end

local function buildPort(root: Instance, rng)
	local port = folder(root, "백사포")
	local vein = Sites.byId["low@port"]
	local wp = Sites.byId.wp_port

	-- 해신당: 영맥 북쪽, 남쪽(영맥과 바다)을 본다. 곁에 솟대와 금줄 친 신목
	do
		local sx, sz = vein.x, vein.z - 17
		local m, look, top = smallShrine(
			port,
			sx,
			sz,
			V3(vein.x, 0, vein.z + 40),
			{ name = "해신당", footing = 12, raise = 0.6, stone = P.granite, stoneMat = M.Granite }
		)
		local front = look:PointToWorldSpace(V3(0, 0, -6.2))
		local g = gy(front.X, front.Z)
		for i = 1, 3 do
			local yy = top - i * (top - g) / 4
			block(m, "Gyedan", V3(4.4, 0.8, 1.2), look * CF(0, yy - 0.3, -6.4 - (i - 1) * 1.1), P.granite, M.Granite)
		end
		for _, s in { -1, 1 } do
			local q = look:PointToWorldSpace(V3(s * 7.5, 0, -5))
			Build.banner(
				m,
				V3(q.X, gy(q.X, q.Z), q.Z),
				V3(vein.x, 0, vein.z + 30),
				if s < 0 then C.clothWhite else P.samcheong,
				10
			)
		end
		-- 솟대 (긴 장대 끝의 나무 새)
		local pole = V3(vein.x + 14, 0, vein.z - 9)
		local pg = gy(pole.X, pole.Z)
		cyl(m, "Sotdae", V3(pole.X, pg - 0.8, pole.Z), V3(pole.X, pg + 13, pole.Z), 0.4, P.wood, M.Wood)
		block(
			m,
			"Sae",
			V3(0.45, 0.5, 1.6),
			CF(pole.X, pg + 13.3, pole.Z) * CFrame.Angles(0, rad(30), 0),
			P.woodDark,
			M.Wood
		)
		wedge(
			m,
			"Buri",
			V3(0.3, 0.3, 0.5),
			CF(pole.X, pg + 13.4, pole.Z) * CFrame.Angles(0, rad(30), 0) * CF(0, 0, -1),
			P.woodDark,
			M.Wood
		)
		-- 신목: 금줄 두른 큰 해송
		local tx, tz = sx - 14, sz + 4
		Build.pine(m, V3(tx, lowAt(tx, tz, 1), tz), rng, { height = 19, tiers = 5 })
		local rope = cyl(
			m,
			"Geumjul",
			V3(tx, gy(tx, tz) + 2.4, tz) - V3(0, 0.08, 0),
			V3(tx, gy(tx, tz) + 2.4, tz) + V3(0, 0.08, 0),
			2.0,
			Color3.fromRGB(214, 200, 160),
			M.Fabric
		)
		rope.CastShadow = false
	end

	-- 초가 여섯 채 (남향, 바다 쪽을 본다): 둔덕 위 길(Land.ROADS 16 끝)을 따라
	local houses = folder(port, "초가")
	local spots = {
		{ -528, 1532, 0 },
		{ -506, 1558, 8 },
		{ -534, 1576, -6 },
		{ -452, 1586, 4 },
		{ -425, 1590, -4 },
		{ -397, 1574, 10 },
	}
	for i, s in spots do
		local x, z = s[1], s[2]
		local look = face(V3(x, 0, z), V3(x + math.sin(rad(s[3])) * 10, 0, z + math.cos(rad(s[3])) * 10))
		local w, d = if i % 2 == 0 then 11 else 9, 6.5
		thatchAt(
			houses,
			x,
			z,
			look:PointToWorldSpace(V3(0, 0, -10)),
			w,
			d,
			{ bays = 2, thatch = jitter(C.thatch, rng, 0.06) }
		)
		-- 집마다 살림: 독, 통, 그물, 장작
		local yard = look:PointToWorldSpace(V3(w / 2 + 2.2, 0, -1))
		local g = gy(yard.X, yard.Z)
		if i % 3 == 1 then
			Build.jars(houses, CF(yard.X, g, yard.Z) * (look - look.Position) * CFrame.Angles(0, rad(90), 0), rng, 3)
		elseif i % 3 == 2 then
			for k = 0, 1 do
				local b = yard + look.RightVector * k * 1.8
				cyl(
					houses,
					"Tong",
					V3(b.X, gy(b.X, b.Z) - 0.2, b.Z),
					V3(b.X, gy(b.X, b.Z) + 1.9, b.Z),
					1.6,
					P.wood:Lerp(P.woodDark, k * 0.4),
					M.WoodPlanks
				)
			end
		else
			block(
				houses,
				"Jangjak",
				V3(3.2, 1.6, 1.4),
				CF(yard.X, g + 0.6, yard.Z) * (look - look.Position),
				P.wood,
				M.Wood
			)
		end
	end
	-- 마을 돌담 (해신당 마당) 과 싸리 울
	Build.stoneWall(
		houses,
		V3(-489, gy(-489, 1505), 1505),
		V3(-489, gy(-489, 1530), 1530),
		{ height = 2.6, width = 1.3 }
	)
	Build.stoneWall(
		houses,
		V3(-451, gy(-451, 1505), 1505),
		V3(-451, gy(-451, 1528), 1528),
		{ height = 2.6, width = 1.3 }
	)
	Build.stoneWall(
		houses,
		V3(-546, gy(-546, 1546), 1546),
		V3(-546, gy(-546, 1566), 1566),
		{ height = 2.4, width = 1.2 }
	)

	-- 덕장과 그물 (마을 아래 모래 비탈)
	local beach = folder(port, "갯가")
	for i, r in { { -486, 1612, 5, true }, { -462, 1618, -8, false }, { -510, 1622, 12, true } } do
		local look = face(V3(r[1], 0, r[2]), V3(r[1] + math.sin(rad(r[3])), 0, r[2] + math.cos(rad(r[3]))))
		dryingRack(
			beach,
			CF(r[1], gy(r[1], r[2]), r[2]) * (look - look.Position) * CFrame.Angles(0, math.pi / 2, 0),
			rng,
			r[4]
		)
		if i == 2 then
			block(
				beach,
				"Geumul",
				V3(4, 0.5, 3),
				CF(r[1] + 5, gy(r[1] + 5, r[2] + 2) + 0.2, r[2] + 2) * CFrame.Angles(0, 0.4, 0.05),
				C.net,
				M.Fabric
			)
		end
	end
	-- 잔교 둘과 배: 매어 둔 배 둘, 모래에 끌어올린 배 둘
	jetty(beach, Vector2.new(-532, 1662), Vector2.new(-532, 1724), -18.6)
	jetty(beach, Vector2.new(-492, 1690), Vector2.new(-488, 1746), -18.8)
	boat(beach, CF(-537, Land.SEA - 0.9, 1716) * CFrame.Angles(0, rad(176), 0), rng)
	boat(beach, CF(-482, Land.SEA - 0.9, 1742) * CFrame.Angles(0, rad(8), 0), rng)
	for _, b in { { -470, 1662, 160 }, { -512, 1684, 200 } } do
		local x, z = b[1], b[2]
		boat(
			beach,
			CF(x, gy(x, z) - 0.2, z) * CFrame.Angles(0, rad(b[3]), 0) * CFrame.Angles(0, 0, rad(6)),
			rng,
			{ mast = false }
		)
	end
	-- 통, 바구니
	for i = 1, 3 do
		local x, z = -520 + i * 4.5, 1652 + (i % 2) * 2
		cyl(
			beach,
			"Tong",
			V3(x, gy(x, z) - 0.2, z),
			V3(x, gy(x, z) + 1.8, z),
			1.5,
			P.wood:Lerp(P.woodDark, (i % 3) * 0.3),
			M.WoodPlanks
		)
	end

	-- 해송 (마을 뒤 둔덕) 과 덤불
	local trees = folder(port, "해송")
	for _, t in { { -556, 1508 }, { -505, 1490 }, { -412, 1508 }, { -566, 1546 } } do
		Build.pine(trees, V3(t[1], lowAt(t[1], t[2], 1), t[2]), rng, { height = rng(13, 18), tiers = 4 })
	end
	for _, t in { { -548, 1525 }, { -470, 1570 }, { -410, 1600 } } do
		Build.shrub(trees, V3(t[1], gy(t[1], t[2]), t[2]), rng, { size = rng(2.5, 4), blobs = 2 })
	end
	-- 마을 어귀 비석 (길 16 끝, 전송진 비켜서)
	Kit.stele(port, V3(-398, gy(-398, 1534), 1534), "백사포", V3(-300, 0, 1470))
	return port
end

-- 검총 ----------------------------------------------------------------------------------------

local function buildSwords(root: Instance, rng)
	local f = folder(root, "검총")
	local poi = Sites.byId.swords
	local cx, cz = poi.x, poi.z
	local rust = function()
		return C.rust:Lerp(C.rustDark, rng(0, 1)):Lerp(Color3.fromRGB(120, 116, 110), rng(0, 0.35))
	end
	-- 가운데 돌무지 무덤과 비석
	local mound = model(f, "돌무지")
	block(
		mound,
		"Heuk",
		V3(26, 1, 22),
		CF(cx, gy(cx, cz) - 0.35, cz) * CFrame.Angles(0, 0.3, 0),
		Color3.fromRGB(110, 96, 78),
		M.Ground
	)
	for i = 1, 7 do
		local a = rng(0, math.pi * 2)
		local r = if i == 1 then 0 else rng(2, 4.5)
		local s = if i == 1 then 6 else rng(2.5, 3.8)
		local x, z = cx + 6 + math.cos(a) * r, cz + 4 + math.sin(a) * r
		block(
			mound,
			"Dol",
			V3(s, s * 0.6, s * 0.85),
			CF(x, gy(x, z) + s * 0.18 + (if i == 1 then 0 else 1.6), z)
				* CFrame.Angles(rng(-0.3, 0.3), rng(0, 3), rng(-0.3, 0.3)),
			jitter(Color3.fromRGB(128, 124, 116), rng, 0.08),
			M.Slate
		)
	end
	Kit.stele(
		f,
		V3(cx - 3, gy(cx - 3, cz - 5), cz - 5),
		"검총",
		V3(Land.STARS.south.x, 0, Land.STARS.south.z),
		Color3.fromRGB(150, 144, 132)
	)
	-- 꽂힌 칼과 창 (둘레로 갈수록 드문드문, 비스듬히)
	local blades = folder(f, "칼")
	for i = 1, 26 do
		local a = rng(0, math.pi * 2)
		local r = 7 + 36 * math.sqrt(rng(0, 1))
		local x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
		local g = gy(x, z)
		local cf = CF(x, g, z)
			* CFrame.Angles(0, rng(0, math.pi * 2), 0)
			* CFrame.Angles(rad(rng(-24, 24)), 0, rad(rng(-18, 18)))
		if i % 3 == 0 then
			-- 창: 긴 자루와 날
			local len = rng(6, 9)
			local shaft = beam(
				blades,
				"Changjaru",
				cf.Position - cf.UpVector * 1,
				cf.Position + cf.UpVector * len,
				0.28,
				0.28,
				C.deadWood:Lerp(P.woodDark, 0.4),
				M.Wood
			)
			shaft.CastShadow = false
			if i % 2 == 0 then
				block(blades, "Changnal", V3(0.5, 1.4, 0.12), cf * CF(0, len + 0.6, 0), rust(), M.Metal)
			end
		elseif i % 5 == 1 then
			-- 부러진 칼 (날만)
			block(blades, "Buleojinkal", V3(0.5, rng(1.4, 2.4), 0.15), cf * CF(0, 0.6, 0), rust(), M.Metal)
		else
			local len = rng(3.2, 4.4)
			block(blades, "Kalnal", V3(0.55, len + 0.7, 0.15), cf * CF(0, len / 2 - 0.35, 0), rust(), M.Metal)
			block(blades, "Kodung", V3(1.8, 0.3, 0.4), cf * CF(0, len, 0), C.rustDark, M.Metal)
			block(blades, "Jaru", V3(0.32, 1.3, 0.32), cf * CF(0, len + 0.8, 0), Color3.fromRGB(70, 52, 40), M.Wood)
		end
	end
	-- 깨진 방패, 해진 깃발
	for i = 1, 6 do
		local a, r = rng(0, math.pi * 2), rng(8, 34)
		local x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
		local g = gy(x, z)
		local lean = if i % 2 == 0 then rad(rng(55, 75)) else rad(rng(4, 12))
		local d = rng(2.2, 3)
		local cfS = CF(x, g + (if i % 2 == 0 then d * 0.45 else 0.15), z)
			* CFrame.Angles(0, rng(0, 6), 0)
			* CFrame.Angles(0, 0, math.pi / 2 - lean)
		local sh =
			block(blades, "Bangpae", V3(0.3, d, d), cfS, Color3.fromRGB(108, 80, 58):Lerp(C.rustDark, 0.4), M.Wood)
		sh.Shape = Enum.PartType.Cylinder
	end
	for i = 1, 4 do
		local a = rad(i * 90 + rng(-20, 20))
		local r = rng(22, 34)
		local x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
		local g = gy(x, z)
		local top = V3(x + rng(-1.5, 1.5), g + rng(9, 12), z + rng(-1.5, 1.5))
		local pole = beam(blades, "Gitdae", V3(x, g - 0.8, z), top, 0.35, 0.35, C.deadWood, M.Wood)
		local look = face(top, top + V3(1, 0, 0.3))
		block(
			blades,
			"Hae_gi",
			V3(2.4, rng(2.6, 3.8), 0.08),
			look * CF(1.3, -2.0, 0) * CFrame.Angles(0, 0, rad(rng(-6, 6))),
			C.clothDark:Lerp(C.dirt, rng(0.2, 0.5)),
			M.Fabric
		)
		if i % 2 == 0 then
			block(
				blades,
				"Hae_gi",
				V3(1.2, 1.4, 0.08),
				look * CF(1.0, -4.6, 0) * CFrame.Angles(0, 0, rad(rng(8, 18))),
				C.clothDark:Lerp(C.dirt, 0.4),
				M.Fabric
			)
		end
		pole.CastShadow = true
	end
	-- 돌무덤 (작은 돌탑) 셋
	for i = 1, 3 do
		local a = rad(i * 120 + 30 + rng(-10, 10))
		local r = rng(40, 52)
		local x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
		local g = gy(x, z)
		local yy = g
		local cm = model(f, "돌탑")
		for k = 1, 3 do
			local s = 3.4 - k * 0.8
			block(
				cm,
				"Dol",
				V3(s, s * 0.55, s * 0.9),
				CF(x + rng(-0.2, 0.2), yy + s * 0.22, z + rng(-0.2, 0.2))
					* CFrame.Angles(rng(-0.15, 0.15), rng(0, 3), rng(-0.15, 0.15)),
				jitter(Color3.fromRGB(130, 126, 118), rng, 0.08),
				M.Slate
			)
			yy += s * 0.5
		end
	end
	-- 고사목과 바위, 마른 풀
	for i = 1, 2 do
		local a = rad(i * 160 + rng(-30, 30))
		local r = rng(46, 62)
		local x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
		deadTree(f, V3(x, lowAt(x, z, 0.8), z), rng, { color = C.deadWood, height = rng(8, 12), branches = 3 })
	end
	for i = 1, 3 do
		local a, r = rng(0, math.pi * 2), rng(14, 40)
		local x, z = cx + math.cos(a) * r, cz + math.sin(a) * r
		boulder(f, V3(x, lowAt(x, z, 1.5), z), rng(3, 5), rng, Color3.fromRGB(122, 118, 110), M.Slate)
	end
	-- 남명대 서쪽에서 오는 흙길
	pave(
		f,
		Vector2.new(-31, 1198),
		Vector2.new(-110, 1172),
		4.5,
		C.dirt,
		M.Ground,
		{ seg = 6, lift = 0.15, name = "Heukgil" }
	)
	pave(
		f,
		Vector2.new(-110, 1172),
		Vector2.new(cx + 26, cz + 14),
		4.5,
		C.dirt,
		M.Ground,
		{ seg = 26, lift = 0.15, name = "Heukgil" }
	)
	return f
end

-- 짓기 -------------------------------------------------------------------------------------

function Region.build(root: Instance, rng: (number, number) -> number)
	local south = folder(root, "남쪽")
	buildCity(south, rng)
	buildVolcano(south, rng)
	buildGorge(south, rng)
	buildMarsh(south, rng)
	buildStarTerrace(south, rng)
	buildPort(south, rng)
	buildSwords(south, rng)
	return south
end

return Region
