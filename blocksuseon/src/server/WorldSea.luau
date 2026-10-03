-- 환해(環海)와 천애(天涯): 옥반을 두른 바다. 바다 끝(천애)에서 물이 운해로 쏟아지고,
-- 바다에는 섬 셋(월아도, 연파군도, 경도)이 있으며, 큰 땅 바닷가에는 바위·유목·난파선·바위기둥을 드문드문 둔다.
-- World.luau 가 build(root, rng) 를 부른다. 모두 "바다" 폴더 하나 안에 짓는다.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")
local Land = require(Shared.Land)
local Build = require(script.Parent.WorldBuild)
local Kit = require(script.Parent.WorldKit)
local Sites = require(script.Parent.WorldSites)

local P = Build.P
local block, beam, cyl, ball, deco = Build.block, Build.beam, Build.cyl, Build.ball, Build.deco
local face = Kit.face
local rad, sin, cos, sqrt, max, min, floor = math.rad, math.sin, math.cos, math.sqrt, math.max, math.min, math.floor

local Sea = {}

-- 색 ------------------------------------------------------------------------------------
local COL = {
	lipWater = Color3.fromRGB(58, 128, 148), -- 턱을 넘는 물 (바닷물 빛)
	lipFoam = Color3.fromRGB(176, 214, 224), -- 턱 끝에서 부서지는 물
	fall = Color3.fromRGB(188, 222, 236), -- 쏟아지는 물줄기
	basalt = Color3.fromRGB(54, 50, 50), -- 천애 벼랑 (지형 Basalt 와 같은 빛)
	basaltLight = Color3.fromRGB(74, 70, 68),
	cloud = Color3.fromRGB(246, 247, 250),
	cloudShade = Color3.fromRGB(226, 230, 238),
	wetRock = Color3.fromRGB(86, 82, 78),
	rock = Color3.fromRGB(122, 116, 108),
	seaweed = Color3.fromRGB(58, 70, 40),
	barnacle = Color3.fromRGB(196, 190, 176),
	drift = Color3.fromRGB(170, 158, 138), -- 바랜 유목
	driftDark = Color3.fromRGB(122, 108, 90),
	hull = Color3.fromRGB(106, 80, 58),
	hullDark = Color3.fromRGB(70, 52, 40),
	bronze = Color3.fromRGB(168, 126, 70),
	patina = Color3.fromRGB(92, 140, 118),
	guano = Color3.fromRGB(226, 224, 214),
	kelp = Color3.fromRGB(78, 74, 36),
	mist = Color3.fromRGB(236, 240, 244),
	beachGrass = Color3.fromRGB(150, 156, 92),
}

-- 작은 도구 ---------------------------------------------------------------------------------

local function folder(parent: Instance, name: string): Folder
	return Kit.folder(parent, name)
end

local function model(parent: Instance, name: string): Model
	local m = Instance.new("Model")
	m.Name = name
	m.Parent = parent
	return m
end

-- 그림자를 안 드리우고 부딪히지도 않는 꾸밈 (물, 구름, 안개)
local function soft(p: BasePart, transparency: number?): BasePart
	deco(p)
	p.CastShadow = false
	if transparency then
		p.Transparency = transparency
	end
	return p
end

local function surface(x: number, z: number): number
	return Land.surface(x, z)
end

-- 가운데와 둘레 두 겹(반지름 radius 와 그 절반쯤, 열두 방향)의 땅 높이 가운데 가장 낮은 곳과 높은 곳.
-- 네모난 기단이면 radius 를 반대각선으로 준다
local function span(x: number, z: number, radius: number): (number, number)
	local low = surface(x, z)
	local high = low
	for i = 1, 12 do
		local a = i * math.pi / 6
		for _, k in { 0.55, 1 } do
			local h = surface(x + cos(a) * radius * k, z + sin(a) * radius * k)
			low, high = min(low, h), max(high, h)
		end
	end
	return low, high
end

local function emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.Texture = "rbxasset://textures/particles/smoke_main.dds"
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

-- 납작한 공 (구름, 안개): 부품 크기대로 늘어난 타원체
local function ellipsoid(
	parent: Instance,
	name: string,
	center: Vector3,
	size: Vector3,
	orient: CFrame,
	color: Color3,
	transparency: number
): BasePart
	local p =
		block(parent, name, size, CFrame.new(center) * (orient - orient.Position), color, Enum.Material.SmoothPlastic)
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = p
	return soft(p, transparency)
end

local function jitter(color: Color3, rng, amount: number): Color3
	local k = 1 + rng(-amount, amount)
	return Color3.new(math.clamp(color.R * k, 0, 1), math.clamp(color.G * k, 0, 1), math.clamp(color.B * k, 0, 1))
end

-- 천애 -------------------------------------------------------------------------------------
--
-- 지형은 반지름 Land.EDGE(2240) 까지 있다 (4 칸 가운데가 그 안이면 칸이 다 차서 실제 끝은 2238~2243 계단).
-- 바다 밑은 끝에서 -32 턱으로 솟고 물은 -24. 그 너머로:
--   턱 물판 (물속 2235 에서 나와 2252 까지 비스듬히 내려간다) → 물줄기 판 (2252, -31 → 2261, -166)
--   그 뒤(안쪽)에는 벼랑 (현무암, -29 에서 운해 밑 -192 까지), 앞(바깥)에는 운해 (-170 둘레의 흰 구름).

local RIM = {
	count = 150, -- 물판 수 (2.4도마다)
	width = 96,
	lip = { 2235, -24.4, 2252.5, -31.5 }, -- { 안쪽 r, y, 바깥 r, y }: 물속에서 나와 휘어 내려간다
	fall = { 2252.5, -31.5, 2261, -166 },
	cliffCount = 60,
	cloudY = -170,
}
Sea.RIM = RIM

local function ringPoint(theta: number, r: number, y: number): Vector3
	return Vector3.new(cos(theta) * r, y, sin(theta) * r)
end

-- 물줄기 판 위 높이 y 에서의 반지름 (판이 바깥으로 조금 기운다)
local function fallR(y: number): number
	local F = RIM.fall
	return F[1] + (y - F[2]) / (F[4] - F[2]) * (F[3] - F[1])
end

local function buildRim(parent: Instance, rng)
	local sheets = folder(parent, "물턱")
	local B, F = RIM.lip, RIM.fall
	local step = math.pi * 2 / RIM.count
	for i = 0, RIM.count - 1 do
		local theta = (i + 0.5) * step
		local out = Vector3.new(cos(theta), 0, sin(theta))
		local along = Vector3.new(-sin(theta), 0, cos(theta))
		local w = RIM.width
		local b = soft(
			beam(
				sheets,
				"Neomeo",
				ringPoint(theta, B[1], B[2]),
				ringPoint(theta, B[3], B[4]),
				w,
				0.5,
				COL.lipWater:Lerp(COL.lipFoam, 0.55),
				Enum.Material.Glass
			),
			0.22
		)
		local f = soft(
			beam(
				sheets,
				"Mulgil",
				ringPoint(theta, F[1], F[2]),
				ringPoint(theta, F[3], F[4]),
				w,
				0.6,
				COL.fall,
				Enum.Material.Glass,
				out
			),
			0.4
		)
		-- 흰 물살 한 가닥 (판 셋에 둘): 판 앞에 가는 띠 (길이와 자리를 달리해 물줄기에 결을 낸다)
		if i % 3 ~= 2 then
			local y0 = F[2] - rng(0, 1) ^ 2 * 40
			local y1 = max(F[4] + 2, y0 - rng(45, 135))
			local u = rng(-w * 0.45, w * 0.45)
			local pa = ringPoint(theta, fallR(y0) + 0.55, y0) + along * u
			local pb = ringPoint(theta, fallR(y1) + 0.55, y1) + along * u
			soft(
				beam(sheets, "Mulsal", pa, pb, rng(2.5, 7), 0.3, COL.cloud, Enum.Material.SmoothPlastic, out),
				rng(0.3, 0.55)
			)
		end
		if i % 3 == 0 then
			-- 턱에서 피어오르는 물보라: 바닷가에서도 세상 끝이 흰 띠로 보이게
			emitter(b, {
				Name = "Mulbora",
				EmissionDirection = Enum.NormalId.Top,
				Rate = 4,
				Lifetime = NumberRange.new(3, 5),
				Speed = NumberRange.new(3, 7),
				SpreadAngle = Vector2.new(30, 30),
				Acceleration = Vector3.new(0, -1.5, 0),
				Drag = 1,
				Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 5), NumberSequenceKeypoint.new(1, 16) }),
				Transparency = NumberSequence.new({
					NumberSequenceKeypoint.new(0, 1),
					NumberSequenceKeypoint.new(0.15, 0.6),
					NumberSequenceKeypoint.new(1, 1),
				}),
				Color = ColorSequence.new(Color3.fromRGB(240, 248, 252)),
				LightEmission = 0.1,
				RotSpeed = NumberRange.new(-10, 10),
			})
			-- 물줄기 따라 떨어지는 물방울 줄 (판 앞면에서)
			emitter(f, {
				Name = "Mulbal",
				EmissionDirection = Enum.NormalId.Back, -- 판의 +Z = 아래쪽
				Rate = 6,
				Lifetime = NumberRange.new(1.6, 2.6),
				Speed = NumberRange.new(12, 20),
				Acceleration = Vector3.new(0, -30, 0),
				Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2), NumberSequenceKeypoint.new(1, 4) }),
				Squash = NumberSequence.new(1.3),
				Transparency = NumberSequence.new({
					NumberSequenceKeypoint.new(0, 0.6),
					NumberSequenceKeypoint.new(1, 1),
				}),
				Color = ColorSequence.new(Color3.fromRGB(236, 246, 255)),
				LightEmission = 0.2,
				Orientation = Enum.ParticleOrientation.VelocityParallel,
			})
		end
	end

	-- 벼랑: 물줄기 뒤의 검은 바위 (판마다 조금씩 기울이고 두께를 달리해 결이 보이게)
	local cliff = folder(parent, "벼랑")
	local n = RIM.cliffCount
	for i = 0, n - 1 do
		local theta = (i + rng(0.35, 0.65)) * math.pi * 2 / n
		local r = 2240.6 + rng(-0.8, 0.6)
		local chord = 2 * r * sin(math.pi / n) + 8
		local top = -29 - rng(0, 2)
		local bottom = -194
		local h = top - bottom
		local c = ringPoint(theta, r, (top + bottom) / 2)
		local cf = face(c, Vector3.zero) * CFrame.Angles(rad(rng(-2.5, 1.5)), 0, rad(rng(-2, 2)))
		block(
			cliff,
			"Byeorang",
			Vector3.new(chord, h, rng(6, 8)),
			cf,
			jitter(if i % 2 == 0 then COL.basalt else COL.basaltLight, rng, 0.08),
			Enum.Material.Basalt
		)
	end

	-- 운해: 물줄기가 떨어지는 곳의 구름 둔덕 + 바깥 구름 무리 + 아주 넓은 바닥 구름.
	-- 구름 덩이는 납작한 타원체 (SpecialMesh Sphere: 부품 크기대로 늘어난 공). 반투명으로 겹쳐 부드럽게 보인다
	local clouds = folder(parent, "운해")
	local Y = RIM.cloudY
	local near = 100
	for i = 0, near - 1 do
		local theta = (i + rng(0.1, 0.9)) * math.pi * 2 / near
		local c = ringPoint(theta, 2274 + rng(-2, 10), Y + rng(-3, 2))
		local size = Vector3.new(rng(150, 200), rng(30, 46), rng(55, 82))
		local p = ellipsoid(clouds, "Gureum", c, size, face(c, Vector3.zero), COL.cloud, rng(0.1, 0.25))
		if i % 3 == 1 then
			-- 물줄기가 구름에 부딪혀 피어오르는 물안개
			emitter(p, {
				Name = "Angae",
				EmissionDirection = Enum.NormalId.Top,
				Rate = 1.6,
				Lifetime = NumberRange.new(6, 10),
				Speed = NumberRange.new(1.5, 4),
				SpreadAngle = Vector2.new(40, 40),
				Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 18), NumberSequenceKeypoint.new(1, 42) }),
				Transparency = NumberSequence.new({
					NumberSequenceKeypoint.new(0, 1),
					NumberSequenceKeypoint.new(0.2, 0.78),
					NumberSequenceKeypoint.new(1, 1),
				}),
				Color = ColorSequence.new(Color3.fromRGB(244, 248, 252)),
				RotSpeed = NumberRange.new(-8, 8),
			})
		end
	end
	for i = 0, 49 do
		local theta = (i + rng(0, 1)) * math.pi * 2 / 50
		local c = ringPoint(theta, 2325 + rng(0, 50), Y - 4 + rng(-3, 3))
		local size = Vector3.new(rng(240, 340), rng(26, 40), rng(90, 130))
		ellipsoid(clouds, "Gureum", c, size, face(c, Vector3.zero), COL.cloudShade, rng(0.12, 0.3))
	end
	for _ = 1, 50 do
		local theta = rng(0, math.pi * 2)
		local r = 2400 + 700 * rng(0, 1) ^ 1.3
		local c = ringPoint(theta, r, Y - 6 + rng(-4, 5))
		local size = Vector3.new(rng(220, 420), rng(20, 40), rng(150, 280))
		ellipsoid(
			clouds,
			"Gureum",
			c,
			size,
			face(c, Vector3.zero) * CFrame.Angles(0, rng(-0.6, 0.6), 0),
			COL.cloud,
			rng(0.2, 0.45)
		)
	end
	-- 바닥 구름: 2048 판 (엔진 부품 한 변 최대). 옥반 밑(가운데)은 비운다
	for gx = -2, 2 do
		for gz = -2, 2 do
			if gx ~= 0 or gz ~= 0 then
				local c = Vector3.new(gx * 2048, Y - 8, gz * 2048)
				soft(
					block(
						clouds,
						"Unhae",
						Vector3.new(2048, 4, 2048),
						CFrame.new(c),
						COL.cloudShade,
						Enum.Material.SmoothPlastic
					),
					0.08
				)
			end
		end
	end
end

-- 자리 비우기: 과업 자리·전송진·영맥 둘레에는 아무것도 두지 않는다 (허브가 놓는 것들) ------------
local CLEAR = {}
for _, s in Sites.TASK do
	table.insert(CLEAR, { s.x, s.z, s.radius or 7 })
end
for _, s in Sites.WAYPOINTS do
	table.insert(CLEAR, { s.x, s.z, 9 })
end
for _, s in Sites.VEINS do
	table.insert(CLEAR, { s.x, s.z, s.radius or 7 })
end
local function isClear(x: number, z: number, r: number): boolean
	for _, c in CLEAR do
		local dx, dz = x - c[1], z - c[2]
		local lim = c[3] + r
		if dx * dx + dz * dz < lim * lim then
			return false
		end
	end
	return true
end

-- 바닷가 자연 ----------------------------------------------------------------------------------

local BARK_DARK = Color3.fromRGB(70, 60, 54) -- 곰솔(해송) 밑동: 검은 껍질
local BARK = Color3.fromRGB(102, 74, 56)

-- 잎판: 바람 부는 쪽으로 길쭉한 납작 덩이 둘
local function leafPad(m: Instance, center: Vector3, s: number, wind: Vector3, rng)
	local cf = face(center, center + wind) * CFrame.Angles(rad(rng(-6, 6)), rng(-0.5, 0.5), rad(rng(-6, 6)))
	deco(
		block(m, "Leaves", Vector3.new(s * 0.78, s * 0.24, s), cf, jitter(P.pine, rng, 0.06), Enum.Material.LeafyGrass)
	)
	deco(
		block(
			m,
			"Leaves",
			Vector3.new(s * 0.55, s * 0.2, s * 0.7),
			cf * CFrame.new(rng(-0.15, 0.15) * s, s * 0.14, -s * 0.12),
			jitter(P.pineLight, rng, 0.06),
			Enum.Material.LeafyGrass
		)
	)
end

-- 바닷바람에 누운 해송: 줄기가 wind 쪽으로 위로 갈수록 더 눕고, 가지와 잎판이 바람 아래쪽으로 몰린다
local function windPine(parent: Instance, base: Vector3, rng, wind: Vector3, height: number?): Model
	local m = model(parent, "해송")
	local hgt = height or rng(9, 14)
	local tw = hgt * 0.095
	local p = base - Vector3.new(0, 0.8, 0)
	local pts = { p }
	for k = 1, 3 do
		local lean = 0.15 + 0.3 * k
		local dir = (Vector3.yAxis + wind * lean + Vector3.new(rng(-0.1, 0.1), 0, rng(-0.1, 0.1))).Unit
		local len = hgt / 3 * (if k == 1 then 1.15 else 0.95)
		local q = p + dir * len
		local w = tw * (1 - 0.2 * (k - 1))
		beam(m, "Trunk", p, q + dir * (w * 0.3), w, w, if k == 1 then BARK_DARK else BARK, Enum.Material.Wood)
		p = q
		table.insert(pts, p)
	end
	local wa = math.atan2(wind.Z, wind.X)
	local pads = 4
	for i = 1, pads do
		local t = 0.5 + 0.5 * (i - 1) / (pads - 1) -- 줄기 위쪽 절반
		local u = t * 3
		local seg = min(floor(u) + 1, 3)
		local from = pts[seg]:Lerp(pts[seg + 1], u - (seg - 1))
		local to
		if i < pads then
			local a = wa + (if i % 2 == 0 then 1 else -1) * rng(0.5, 1.3)
			local reach = hgt * (0.36 - 0.14 * t) * rng(0.85, 1.15)
			to = from + Vector3.new(cos(a) * reach, rng(-0.4, 0.5), sin(a) * reach)
			beam(m, "Branch", from, to, tw * 0.42, tw * 0.42, BARK, Enum.Material.Wood)
		else
			to = p + wind * hgt * 0.06
		end
		leafPad(m, to + Vector3.new(0, 0.3, 0), hgt * (0.5 - 0.16 * t) * rng(0.9, 1.15), wind, rng)
	end
	return m
end

-- 갯바위: 큰 돌 + 모서리 돌 + 작은 돌 몇. 물에 잠기는 바위는 수면 언저리에 검푸른 물때 띠, 새 바위는 흰 똥
local function seaRock(parent: Instance, x: number, z: number, size: number, rng, opts): (Model, BasePart)
	opts = opts or {}
	local m = model(parent, opts.name or "갯바위")
	local low = span(x, z, size * 0.62) -- 비탈에서도 뜨지 않게 가장 낮은 곳에 앉힌다
	local g = min(low, surface(x, z))
	local color = opts.color or COL.wetRock
	local hgt = size * rng(0.55, 0.8) + max(0, surface(x, z) - g)
	local sink = min(size * 0.16, 1.8)
	local yaw = rng(0, math.pi)
	local cf = CFrame.new(x, g + hgt / 2 - sink, z)
		* CFrame.Angles(0, yaw, 0)
		* CFrame.Angles(rng(-0.2, 0.2), 0, rng(-0.2, 0.2))
	local main =
		block(m, "Rock", Vector3.new(size, hgt, size * rng(0.7, 1)), cf, jitter(color, rng, 0.06), Enum.Material.Slate)
	if size >= 4.5 then
		block(
			m,
			"Rock",
			Vector3.new(size * 0.75, hgt * 0.6, size * 0.65),
			cf * CFrame.new(size * 0.12, hgt * 0.38, 0) * CFrame.Angles(rng(-0.4, 0.4), rng(0, 1), rng(0.25, 0.5)),
			jitter(color:Lerp(COL.rock, 0.35), rng, 0.08),
			Enum.Material.Slate
		)
	end
	for _ = 1, opts.count or 2 do
		local a = rng(0, math.pi * 2)
		local s = size * rng(0.22, 0.42)
		local px, pz = x + cos(a) * size * 0.66, z + sin(a) * size * 0.66
		block(
			m,
			"Rock",
			Vector3.new(s, s * rng(0.5, 0.8), s * rng(0.7, 1.1)),
			CFrame.new(px, surface(px, pz) + s * 0.2, pz) * CFrame.Angles(rng(-0.5, 0.5), rng(0, 6), rng(-0.5, 0.5)),
			jitter(color, rng, 0.1),
			Enum.Material.Slate
		)
	end
	if g < Land.SEA + 0.5 and g + hgt - sink > Land.SEA + 0.8 then
		soft(
			block(
				m,
				"Multtae",
				Vector3.new(size * 1.04, 0.9, main.Size.Z * 1.05),
				CFrame.new(x, Land.SEA + 0.15, z) * CFrame.Angles(0, yaw, 0),
				COL.seaweed,
				Enum.Material.Slate
			)
		)
	end
	if opts.guano then
		deco(
			block(
				m,
				"Saeddong",
				Vector3.new(size * 0.62, 0.2, main.Size.Z * 0.55),
				main.CFrame * CFrame.new(0, hgt / 2 + 0.05, 0),
				COL.guano,
				Enum.Material.Slate
			)
		)
	end
	return m, main
end

-- 유목: 파도에 바랜 통나무, 뿌리 둘, 부러진 가지 하나
local function driftwood(parent: Instance, x: number, z: number, rng): Model
	local m = model(parent, "유목")
	local yaw = rng(0, math.pi * 2)
	local len = rng(7, 15)
	local d = rng(0.9, 1.7)
	local dx, dz = cos(yaw) * len / 2, sin(yaw) * len / 2
	local a = Vector3.new(x - dx, surface(x - dx, z - dz) + d * 0.3, z - dz)
	local b = Vector3.new(x + dx, surface(x + dx, z + dz) + d * 0.22, z + dz)
	cyl(m, "Tongnamu", a, b, d, jitter(COL.drift, rng, 0.06), Enum.Material.Wood)
	for _ = 1, 2 do
		local ra = yaw + math.pi + rng(-1.1, 1.1)
		beam(
			m,
			"Ppuri",
			a,
			a + Vector3.new(cos(ra), rng(0, 0.5), sin(ra)) * rng(1.4, 2.8),
			d * 0.36,
			d * 0.36,
			jitter(COL.driftDark, rng, 0.08),
			Enum.Material.Wood
		)
	end
	local c = a:Lerp(b, rng(0.45, 0.75))
	local sa = yaw + (if rng(0, 1) > 0.5 then 1 else -1) * rng(0.6, 1)
	beam(
		m,
		"Gaji",
		c,
		c + Vector3.new(cos(sa) * 2.2, rng(0.3, 1.2), sin(sa) * 2.2),
		d * 0.3,
		d * 0.3,
		COL.drift,
		Enum.Material.Wood
	)
	return m
end

-- 갯풀 한 포기
local function grassTuft(parent: Instance, x: number, z: number, rng, color: Color3?): Model
	local m = model(parent, "갯풀")
	local g = surface(x, z)
	for _ = 1, 3 do
		local a = rng(0, math.pi * 2)
		local foot = Vector3.new(x + cos(a) * 0.3, g - 0.2, z + sin(a) * 0.3)
		local tip = foot + Vector3.new(cos(a) * rng(0.6, 1.4), rng(1.4, 2.6), sin(a) * rng(0.6, 1.4))
		soft(
			beam(
				m,
				"Pul",
				foot,
				tip,
				rng(0.5, 0.9),
				0.08,
				jitter(color or COL.beachGrass, rng, 0.1),
				Enum.Material.Grass
			)
		)
	end
	return m
end

-- 말(해초) 무리: 바닥에서 수면까지 줄기, 수면에 뜬 잎
local function kelp(parent: Instance, x: number, z: number, rng): Model
	local m = model(parent, "말무리")
	for _ = 1, 2 do
		local px, pz = x + rng(-3.5, 3.5), z + rng(-3.5, 3.5)
		local floorY = Land.height(px, pz)
		if floorY < Land.SEA - 1.5 then
			local top = Vector3.new(px + rng(-1, 1), Land.SEA - 0.4, pz + rng(-1, 1))
			soft(beam(m, "Julgi", Vector3.new(px, floorY - 0.3, pz), top, 0.35, 0.12, COL.kelp, Enum.Material.Grass))
			soft(
				block(
					m,
					"Ip",
					Vector3.new(rng(0.8, 1.3), 0.12, rng(3, 5)),
					CFrame.new(top.X, Land.SEA + 0.05, top.Z) * CFrame.Angles(0, rng(0, 6.2), 0),
					jitter(COL.kelp, rng, 0.1),
					Enum.Material.Grass
				)
			)
		end
	end
	return m
end

-- 바위에 앉은 갈매기
local function gull(parent: Instance, pos: Vector3, yaw: number): Model
	local m = model(parent, "갈매기")
	local cf = CFrame.new(pos) * CFrame.Angles(0, yaw, 0)
	deco(block(m, "Mom", Vector3.new(0.5, 0.48, 1.2), cf * CFrame.new(0, 0.38, 0), Color3.fromRGB(242, 242, 238)))
	deco(
		block(m, "Nalgae", Vector3.new(0.62, 0.18, 0.95), cf * CFrame.new(0, 0.6, 0.15), Color3.fromRGB(150, 156, 164))
	)
	deco(
		block(m, "Meori", Vector3.new(0.36, 0.36, 0.4), cf * CFrame.new(0, 0.74, -0.62), Color3.fromRGB(246, 246, 244))
	)
	return m
end

-- 바위기둥: 바다 밑에서 솟은 켜켜이 쌓인 바위. 위로 갈수록 가늘고 켜마다 빛이 다르다. 꼭대기 자리를 돌려준다
local STRATA = { Color3.fromRGB(118, 110, 100), Color3.fromRGB(96, 90, 84), Color3.fromRGB(136, 126, 112) }
local function seaStack(parent: Instance, x: number, z: number, height: number, rng, opts): (Model, Vector3)
	opts = opts or {}
	local m = model(parent, opts.name or "바위기둥")
	local floorY = Land.height(x, z)
	local r0 = opts.radius or rng(6, 10)
	local y = floorY - 3
	local top = Land.SEA + height
	local tiers = 3 + floor(height / 16)
	local th = (top - y) / tiers
	local cx, cz = x, z
	local last: CFrame = CFrame.new(x, top, z)
	local lastH = 0
	local firstYaw, firstSize = 0, Vector3.one
	for k = 1, tiers do
		local r = r0 * (1 - 0.34 * (k - 1) / tiers) * rng(0.88, 1.08)
		local h = th * rng(1.0, 1.18)
		local yaw = rng(0, math.pi)
		local cf = CFrame.new(cx, y + h / 2, cz)
			* CFrame.Angles(0, yaw, 0)
			* CFrame.Angles(rng(-0.05, 0.05), 0, rng(-0.05, 0.05))
		local size = Vector3.new(r * 2, h, r * rng(1.5, 1.9))
		block(m, "Bawi", size, cf, jitter(STRATA[1 + (k % #STRATA)], rng, 0.05), Enum.Material.Slate)
		if k == 1 then
			firstYaw, firstSize = yaw, size
		end
		last, lastH = cf, h
		y += th
		cx += rng(-0.7, 0.7)
		cz += rng(-0.7, 0.7)
	end
	soft(
		block(
			m,
			"Multtae",
			Vector3.new(firstSize.X * 1.04, 1.3, firstSize.Z * 1.05),
			CFrame.new(x, Land.SEA + 0.25, z) * CFrame.Angles(0, firstYaw, 0),
			COL.seaweed,
			Enum.Material.Slate
		)
	)
	local crown = (last * CFrame.new(0, lastH / 2, 0)).Position
	if opts.guano ~= false then
		deco(
			block(
				m,
				"Saeddong",
				Vector3.new(r0 * 0.9, 0.25, r0 * 0.8),
				last * CFrame.new(0, lastH / 2 + 0.05, 0),
				COL.guano,
				Enum.Material.Slate
			)
		)
	end
	return m, crown
end

-- 거룻배: cf 는 배 밑 가운데 (앞 -Z 가 이물). 판 둘씩 고물 귀에서 이물 끝으로 모인다
local function boat(parent: Instance, cf: CFrame, rng, name: string?): Model
	local m = model(parent, name or "거룻배")
	local L, Wd, H = 11, 3.8, 1.6
	local wood, dark = jitter(COL.hull, rng, 0.06), COL.hullDark
	local planks = Enum.Material.WoodPlanks
	local function W(v: Vector3): Vector3
		return cf:PointToWorldSpace(v)
	end
	block(m, "Badak", Vector3.new(Wd * 0.62, 0.35, L * 0.72), cf * CFrame.new(0, 0.18, 0.9), wood, planks)
	local bow = Vector3.new(0, H * 0.95, -L / 2)
	for _, s in { -1, 1 } do
		beam(
			m,
			"Pan",
			W(Vector3.new(s * Wd * 0.36, 0.55, L / 2)),
			W(Vector3.new(0, 0.7, -L / 2 + 0.3)),
			0.3,
			0.9,
			wood,
			planks
		)
		beam(
			m,
			"Pan",
			W(Vector3.new(s * Wd * 0.48, 1.35, L / 2)),
			W(bow + Vector3.new(0, 0, 0.2)),
			0.3,
			0.9,
			wood,
			planks
		)
	end
	block(m, "Gomul", Vector3.new(Wd * 1.0, H, 0.35), cf * CFrame.new(0, H * 0.55, L / 2), dark, planks)
	beam(
		m,
		"Imul",
		W(Vector3.new(0, 0.2, -L / 2 + 0.4)),
		W(bow + Vector3.new(0, 0.5, -0.2)),
		0.45,
		0.45,
		dark,
		Enum.Material.Wood
	)
	block(m, "Gamok", Vector3.new(Wd * 0.85, 0.25, 0.8), cf * CFrame.new(0, 1.2, 1.2), dark, planks)
	block(m, "Gamok", Vector3.new(Wd * 0.6, 0.25, 0.8), cf * CFrame.new(0, 1.25, -2.2), dark, planks)
	local o0 = W(Vector3.new(Wd * 0.3, 1.5, 2.8))
	local o1 = W(Vector3.new(Wd * 0.75 + 2.6, 0.05, -2.2))
	beam(m, "No", o0, o1, 0.22, 0.22, COL.drift, Enum.Material.Wood)
	local look = face(o0, o1)
	block(
		m,
		"Nonal",
		Vector3.new(0.7, 0.12, 2),
		CFrame.new(o1 + Vector3.new(0, 0.1, 0)) * (look - look.Position),
		COL.drift,
		Enum.Material.Wood
	)
	return m
end

-- 땅 위에 비스듬히 누운 배: 이물·고물 땅 높이로 기울이고 한쪽으로 눕힌다
local function beachedBoat(parent: Instance, x: number, z: number, toward: Vector3, rng, name: string?): Model
	local look = face(Vector3.new(x, 0, z), toward)
	local bowP = look * CFrame.new(0, 0, -5.5)
	local sternP = look * CFrame.new(0, 0, 5.5)
	local gb, gs = surface(bowP.X, bowP.Z), surface(sternP.X, sternP.Z)
	local pitch = math.atan2(gb - gs, 11)
	local y = min(surface(x, z), (gb + gs) / 2) - 0.25
	local roll = rad(rng(10, 18)) * (if rng(0, 1) > 0.5 then 1 else -1)
	return boat(parent, CFrame.new(x, y, z) * (look - look.Position) * CFrame.Angles(pitch, 0, roll), rng, name)
end

-- 난파선: 반쯤 묻힌 용골과 갈비뼈처럼 선 늑골
local function wreck(parent: Instance, x: number, z: number, yaw: number, rng): Model
	local m = model(parent, "난파선")
	local L = rng(24, 30)
	local dir = Vector3.new(cos(yaw), 0, sin(yaw))
	local side = Vector3.new(-sin(yaw), 0, cos(yaw))
	local ax, az = x - dir.X * L / 2, z - dir.Z * L / 2
	local bx, bz = x + dir.X * L / 2, z + dir.Z * L / 2
	local a = Vector3.new(ax, surface(ax, az) - 0.2, az)
	local b = Vector3.new(bx, surface(bx, bz) + 0.7, bz)
	beam(m, "Yonggol", a, b, 1.3, 1.2, COL.hullDark, Enum.Material.Wood)
	local ribs = 7
	for k = 1, ribs do
		local t = (k - 0.5) / ribs
		local c = a:Lerp(b, t)
		local bulge = 1 - (2 * t - 1) ^ 2 * 0.55
		local hgt = 7.5 * bulge * rng(0.7, 1.05)
		for _, s in { -1, 1 } do
			if rng(0, 1) > 0.18 then -- 몇 개는 부러져 없다
				local half = 3.6 * bulge
				local p1 = c + side * s * half + Vector3.new(0, hgt * 0.38, 0)
				beam(m, "Neukgol", c + side * s * 0.3, p1, 0.6, 0.7, COL.hull, Enum.Material.Wood)
				if rng(0, 1) > 0.3 then
					local p2 = c + side * s * (half * rng(0.8, 1.05)) + Vector3.new(0, hgt, 0)
					beam(m, "Neukgol", p1, p2, 0.55, 0.62, COL.hull, Enum.Material.Wood)
				end
			end
		end
	end
	-- 한쪽 아래에 남은 바깥 판 둘
	for k = 1, 2 do
		local s = if k == 1 then 1 else -1
		local t0, t1 = rng(0.1, 0.35), rng(0.6, 0.9)
		local p0 = a:Lerp(b, t0) + side * s * 3.2 * 0.8 + Vector3.new(0, 1.6, 0)
		local p1 = a:Lerp(b, t1) + side * s * 3.2 * 0.85 + Vector3.new(0, 1.9, 0)
		beam(m, "Pan", p0, p1, 0.3, 1.1, COL.hullDark, Enum.Material.WoodPlanks)
	end
	-- 부러진 돛대: 곁 모래에 누워
	local mx, mz = x + side.X * 7, z + side.Z * 7
	local m0 = Vector3.new(mx - dir.X * 6, surface(mx - dir.X * 6, mz - dir.Z * 6) + 0.4, mz - dir.Z * 6)
	local m1 = Vector3.new(mx + dir.X * 5, surface(mx + dir.X * 5, mz + dir.Z * 5) + 0.4, mz + dir.Z * 5)
	cyl(m, "Dotdae", m0, m1, 0.9, COL.driftDark, Enum.Material.Wood)
	return m
end

-- 돌계단: a 에서 b 까지 땅을 따라 디딤돌 (디딤마다 높은 쪽에 윗면, 낮은 쪽 땅까지 몸을 내린다)
local function stairs(parent: Instance, a: Vector3, b: Vector3, width: number, rng, tread: number?): Model
	local m = model(parent, "돌계단")
	local d = Vector3.new(b.X - a.X, 0, b.Z - a.Z)
	local len = d.Magnitude
	local dir = d / len
	local side = Vector3.new(-dir.Z, 0, dir.X)
	local step = tread or 2.2
	local n = math.max(1, math.ceil(len / step))
	for k = 0, n - 1 do
		local t = (k + 0.5) / n
		local px, pz = a.X + d.X * t, a.Z + d.Z * t
		local hi, lo = -math.huge, math.huge
		for _, f in { -0.5, 0.5 } do
			for _, w in { -0.45, 0, 0.45 } do
				local qx, qz = px + dir.X * f * step + side.X * w * width, pz + dir.Z * f * step + side.Z * w * width
				local g = surface(qx, qz)
				hi, lo = max(hi, g), min(lo, g)
			end
		end
		local top = hi + 0.3
		local bottom = lo - 0.8
		local c = Vector3.new(px, (top + bottom) / 2, pz)
		block(
			m,
			"Didim",
			Vector3.new(width * rng(0.92, 1.05), top - bottom, step * 1.04),
			face(c, c + dir) * CFrame.Angles(0, rng(-0.04, 0.04), 0),
			jitter(P.granite, rng, 0.07),
			Enum.Material.Slate
		)
	end
	return m
end

-- 사방 둘레 몇 곳 높이를 보고 바닥이 평평한지
local function flatness(x: number, z: number, r: number): number
	local lo, hi = span(x, z, r)
	return hi - lo
end

-- 섬 이름 비석: 근처(반지름 7)에서 가장 평평한 곳을 골라 받침이 뜨지 않게 세운다
local function steleAt(parent: Instance, x: number, z: number, text: string, toward: Vector3): (Model, number, number)
	local bx, bz, best = x, z, math.huge
	for i = 0, 12 do
		local px, pz = x, z
		if i > 0 then
			local a = i * math.pi / 6
			local r = if i % 2 == 0 then 6 else 3.5
			px, pz = x + cos(a) * r, z + sin(a) * r
		end
		local f = flatness(px, pz, 2.8)
		if f < best then
			bx, bz, best = px, pz, f
		end
	end
	local low = span(bx, bz, 2.8)
	return Kit.stele(parent, Vector3.new(bx, low + 0.75, bz), text, toward), bx, bz
end

-- 섬 꾸밈 자리 고르기: 네모 안에서 높이가 맞고, avoid({x, z, r}) 와 이미 고른 자리에서 gap 만큼 떨어진 곳
local function pickSpots(
	rng,
	cx: number,
	cz: number,
	half: number,
	count: number,
	minH: number,
	maxH: number,
	avoid,
	gap: number,
	inside: ((number, number) -> boolean)?
): { Vector3 }
	local out = {}
	for _ = 1, count * 40 do
		if #out >= count then
			break
		end
		local x, z = cx + rng(-half, half), cz + rng(-half, half)
		local h = surface(x, z)
		local ok = h >= minH and h <= maxH and isClear(x, z, 3) and (inside == nil or inside(x, z))
		if ok then
			for _, a in avoid do
				if (x - a[1]) ^ 2 + (z - a[2]) ^ 2 < a[3] * a[3] then
					ok = false
					break
				end
			end
		end
		if ok then
			for _, o in out do
				if (x - o.X) ^ 2 + (z - o.Z) ^ 2 < gap * gap then
					ok = false
					break
				end
			end
		end
		if ok then
			table.insert(out, Vector3.new(x, h, z))
		end
	end
	return out
end

-- 섬마다 바람: 바다 끝에서 옥반 가운데로 분다 (해송이 가운데 쪽으로 눕는다)
local function inwardWind(x: number, z: number): Vector3
	return Vector3.new(-x, 0, -z).Unit
end

local COAST_LEAVES = { P.leafDeep, P.pine, P.leaf }

-- 섬 자연 한 벌: 해송, 덤불, 갯풀, 물가 바위, 말무리
local function islandNature(parent: Instance, rng, cx: number, cz: number, half: number, avoid, counts)
	local wind = inwardWind(cx, cz)
	local inside = counts.inside
	-- 풀과 나무는 너무 가파르지 않은 곳에만
	local function plantable(x: number, z: number): boolean
		return (inside == nil or inside(x, z)) and flatness(x, z, 2.5) < 2.4
	end
	for _, p in
		pickSpots(rng, cx, cz, half, counts.pines or 0, counts.pineMin or 8, counts.pineMax or 60, avoid, 13, plantable)
	do
		windPine(parent, p, rng, wind, rng(8, 13))
		table.insert(avoid, { p.X, p.Z, 5 })
	end
	for _, p in pickSpots(rng, cx, cz, half, counts.shrubs or 0, 0, 60, avoid, 6, plantable) do
		Build.shrub(parent, p - Vector3.new(0, 0.3, 0), rng, { leaves = COAST_LEAVES, size = rng(2.4, 4) })
	end
	for _, p in pickSpots(rng, cx, cz, half, counts.grass or 0, -19, 60, avoid, 5, plantable) do
		grassTuft(parent, p.X, p.Z, rng)
	end
	for _, p in pickSpots(rng, cx, cz, half, counts.rocks or 0, -27, -18, avoid, 14, inside) do
		seaRock(parent, p.X, p.Z, rng(3.5, 8), rng, { guano = rng(0, 1) > 0.6 })
	end
	for _, p in pickSpots(rng, cx, cz, half, counts.kelp or 0, -40, -26, avoid, 16, inside) do
		kelp(parent, p.X, p.Z, rng)
	end
end

-- 월아도 ----------------------------------------------------------------------------------------
--
-- 초승달 섬: 안쪽 만이 북동(육지 쪽)으로 열렸다. 서쪽 팔 높은 곳에 옛 관측대(두 단 돌 대 위의 부서진 혼천의),
-- 남쪽 팔에 병 모양 돌탑(옛 별탑), 그 사이에 무너진 정자 터, 안쪽 만에 부서진 잔교와 섬 이름 비석.

-- 고리 하나 (가운데 center, 고리 면을 U·V 가 편다). missing[k] 인 마디는 부러져 없다
local function ringArc(
	m: Instance,
	name: string,
	center: Vector3,
	U: Vector3,
	V: Vector3,
	radius: number,
	segs: number,
	missing,
	color: Color3,
	mat: Enum.Material,
	w: number
)
	local N = U:Cross(V).Unit
	for k = 0, segs - 1 do
		if not missing[k] then
			local a0, a1 = k * math.pi * 2 / segs, (k + 1) * math.pi * 2 / segs
			local p0 = center + (U * cos(a0) + V * sin(a0)) * radius
			local p1 = center + (U * cos(a1) + V * sin(a1)) * radius
			local mid, half = (p0 + p1) / 2, (p1 - p0) * 0.53
			beam(m, name, mid - half, mid + half, w, w * 0.8, color, mat, N)
		end
	end
end

-- 혼천의: 돌 받침, 구리 십자와 네 기둥, 지평환·자오환·적도환, 북쪽 하늘을 겨누던 망통. 오래되어 부서지고 녹슬었다
local function armillary(parent: Instance, g: Vector3, rng): Model
	local m = model(parent, "혼천의")
	block(
		m,
		"Daeseok",
		Vector3.new(5, 1.2, 5),
		CFrame.new(g + Vector3.new(0, 0.6, 0)) * CFrame.Angles(0, rad(45), 0),
		P.graniteDark,
		Enum.Material.Granite
	)
	local cy = g.Y + 1.45
	local R = 5.4
	local c = Vector3.new(g.X, cy, g.Z)
	for _, a in { 0, math.pi / 2 } do
		local d = Vector3.new(cos(a), 0, sin(a)) * R
		beam(m, "Sipja", c - d, c + d, 0.7, 0.5, COL.bronze, Enum.Material.Metal)
	end
	local C = Vector3.new(g.X, g.Y + 7.4, g.Z)
	for k = 0, 3 do
		local a = k * math.pi / 2
		local foot = Vector3.new(g.X + cos(a) * R, cy, g.Z + sin(a) * R)
		local rusty = k == 2
		cyl(
			m,
			"Gidung",
			foot,
			Vector3.new(foot.X, C.Y, foot.Z),
			0.5,
			if rusty then COL.patina else COL.bronze,
			if rusty then Enum.Material.CorrodedMetal else Enum.Material.Metal
		)
	end
	local X, Y, Z = Vector3.xAxis, Vector3.yAxis, Vector3.zAxis
	ringArc(m, "Jipyeonghwan", C, X, Z, R + 0.1, 16, { [6] = true }, COL.bronze, Enum.Material.Metal, 0.55)
	ringArc(
		m,
		"Jaohwan",
		C,
		Z,
		Y,
		R - 0.35,
		16,
		{ [3] = true, [4] = true, [5] = true },
		COL.bronze,
		Enum.Material.Metal,
		0.45
	)
	-- 적도환: 본디 위도만큼 기울었던 고리가 내려앉아 더 누웠다
	local tilt = rad(64)
	ringArc(
		m,
		"Jeokdohwan",
		C - Vector3.new(0.3, 1.1, 0),
		X,
		(Y * cos(tilt) + Z * sin(tilt)).Unit,
		R - 0.8,
		14,
		{ [9] = true, [10] = true },
		COL.patina,
		Enum.Material.CorrodedMetal,
		0.4
	)
	-- 망통: 북쪽(-z) 하늘을 겨누던 관, 비틀렸다
	local axis = Vector3.new(0.14, sin(rad(32)), -cos(rad(32))).Unit
	cyl(m, "Mangtong", C - axis * 5.2, C + axis * 5.2, 0.85, COL.bronze, Enum.Material.Metal)
	cyl(m, "Mangtong", C + axis * 4.6, C + axis * 5.4, 1.2, COL.patina, Enum.Material.CorrodedMetal)
	-- 떨어진 고리 토막
	beam(
		m,
		"Jogak",
		g + Vector3.new(3.4, 0.28, 2.9),
		g + Vector3.new(5.3, 0.3, 0.9),
		0.5,
		0.4,
		COL.patina,
		Enum.Material.CorrodedMetal
	)
	return m
end

-- 앞(-Z)에서 cf 쪽으로 오르는 장대석 계단 (Build.house 와 같은 꼴: 깊이가 줄어드는 돌을 겹친다)
local function frontSteps(m: Instance, cf: CFrame, frontZ: number, fromY: number, toY: number, width: number)
	local rise = toY - fromY
	if rise < 0.4 then
		return
	end
	local n = max(1, math.ceil(rise / 0.75) - 1)
	for i = 1, n do
		local top = fromY + rise * i / (n + 1)
		local depth = 1.0 * (n - i + 1)
		local bottom = fromY - 0.6
		block(
			m,
			"Step",
			Vector3.new(width, top - bottom, depth),
			cf * CFrame.new(0, (top + bottom) / 2, frontZ - depth / 2),
			P.granite,
			Enum.Material.Granite
		)
	end
end

-- 옛 관측대: 두 단 돌 대. 첫 단 갑석 한 토막이 빠져 굴렀고, 네 귀 돌기둥 가운데 하나는 부러져 누웠다
local function terrace(parent: Instance, x: number, z: number, toward: Vector3, rng): (Model, Vector3)
	local m = model(parent, "옛 관측대")
	local S1, S2 = 28, 16
	local low, high = span(x, z, S1 * 0.72)
	local look = face(Vector3.new(x, 0, z), toward)
	local top1 = high + 1.0
	local bot = low - 1.2
	block(
		m,
		"Gidan",
		Vector3.new(S1, top1 - bot, S1),
		look * CFrame.new(0, (top1 + bot) / 2, 0),
		jitter(P.granite, rng, 0.04),
		Enum.Material.Granite
	)
	for side = 0, 3 do
		local yaw = side * math.pi / 2
		local edge = look * CFrame.Angles(0, yaw, 0) * CFrame.new(0, top1 + 0.3, -(S1 / 2 - 0.7))
		if side == 2 then
			block(
				m,
				"Gapseok",
				Vector3.new(S1 * 0.42, 0.6, 1.4),
				edge * CFrame.new(-S1 * 0.29, 0, 0),
				P.graniteDark,
				Enum.Material.Granite
			)
			block(
				m,
				"Gapseok",
				Vector3.new(S1 * 0.38, 0.6, 1.4),
				edge * CFrame.new(S1 * 0.31, 0, 0),
				P.graniteDark,
				Enum.Material.Granite
			)
			local fall = edge * CFrame.new(S1 * 0.02, 0, -2.8)
			local fx, fz = fall.X, fall.Z
			block(
				m,
				"Gapseok",
				Vector3.new(S1 * 0.18, 0.6, 1.4),
				CFrame.new(fx, surface(fx, fz) + 0.25, fz)
					* CFrame.Angles(0, yaw + rng(-0.6, 0.6), 0)
					* CFrame.Angles(rng(-0.15, 0.15), 0, rng(0.15, 0.3)),
				P.graniteDark,
				Enum.Material.Granite
			)
		else
			block(m, "Gapseok", Vector3.new(S1 + 0.4, 0.6, 1.4), edge, P.graniteDark, Enum.Material.Granite)
		end
	end
	-- 둘째 단 (조금 뒤로)
	local top2 = top1 + 1.9
	local back = 1.5
	block(
		m,
		"Gidan",
		Vector3.new(S2, top2 - top1 + 0.6, S2),
		look * CFrame.new(0, (top2 + top1 - 0.6) / 2, back),
		jitter(P.granite, rng, 0.04),
		Enum.Material.Granite
	)
	block(
		m,
		"Gapseok",
		Vector3.new(S2 + 0.5, 0.5, S2 + 0.5),
		look * CFrame.new(0, top2 - 0.15, back),
		P.graniteDark,
		Enum.Material.Granite
	)
	-- 계단: 앞 가장자리 땅에서 첫 단, 첫 단에서 둘째 단
	local fg = math.huge
	for _, u in { -3, 0, 3 } do
		local p = look * CFrame.new(u, 0, -S1 / 2 - 1.5)
		fg = min(fg, surface(p.X, p.Z))
	end
	frontSteps(m, look, -S1 / 2, fg, top1 + 0.6, 6)
	frontSteps(m, look, back - S2 / 2, top1 + 0.6, top2 + 0.1, 5)
	-- 네 귀 돌기둥 (망주석처럼 둥근 머리). 셋째는 부러져 첫 단 위에 누웠다
	for k, c in { { 1, 1 }, { -1, 1 }, { 1, -1 }, { -1, -1 } } do
		local p = look * CFrame.new(c[1] * (S1 / 2 - 1.8), top1 + 0.6, c[2] * (S1 / 2 - 1.8))
		if k == 3 then
			block(
				m,
				"Seokju",
				Vector3.new(1.3, 1.4, 1.3),
				p * CFrame.new(0, 0.7, 0) * CFrame.Angles(0, 0, rad(4)),
				P.granite,
				Enum.Material.Granite
			)
			local q = p * CFrame.new(-2.6, 0.55, 2.2) * CFrame.Angles(0, rad(rng(20, 50)), rad(90))
			block(m, "Seokju", Vector3.new(4.4, 1.1, 1.1), q, P.granite, Enum.Material.Granite)
		else
			local h = rng(4.2, 5.6)
			block(m, "Seokju", Vector3.new(1.3, h, 1.3), p * CFrame.new(0, h / 2, 0), P.granite, Enum.Material.Granite)
			ball(m, "Meori", p.Position + Vector3.new(0, h + 0.55, 0), 1.5, P.granite, Enum.Material.Granite)
		end
	end
	return m, (look * CFrame.new(0, top2 + 0.1, back)).Position
end

-- 옛 별탑: 위로 갈수록 좁아지는 둥근 돌 켜 열둘, 가운데쯤 네모 창, 꼭대기 정(井)자 돌 (한 개는 떨어졌다)
local function starTower(parent: Instance, x: number, z: number, windowToward: Vector3, rng): Model
	local m = model(parent, "옛 별탑")
	local low, high = span(x, z, 9.6)
	local base = high + 0.9
	local yaw = rad(12)
	block(
		m,
		"Gidan",
		Vector3.new(13.5, base - (low - 1), 13.5),
		CFrame.new(x, (base + low - 1) / 2, z) * CFrame.Angles(0, yaw, 0),
		P.graniteDark,
		Enum.Material.Granite
	)
	block(
		m,
		"Gidan",
		Vector3.new(11.4, 0.9, 11.4),
		CFrame.new(x, base + 0.45, z) * CFrame.Angles(0, yaw, 0),
		P.granite,
		Enum.Material.Granite
	)
	local R = { 5.25, 5.19, 5.06, 4.88, 4.65, 4.4, 4.12, 3.85, 3.6, 3.38, 3.2, 3.08 }
	local course = 1.8
	local y0 = base + 0.9
	local y = y0
	-- 오래되어 살짝 기울었다
	local lean = Vector3.new(rng(-0.025, 0.025), 0, rng(-0.025, 0.025))
	local function axisAt(yy: number): Vector3
		return Vector3.new(x, yy, z) + lean * (yy - y0)
	end
	for k, r in R do
		local shade = if k % 2 == 0 then P.granite else P.granite:Lerp(P.graniteDark, 0.35)
		cyl(
			m,
			"Dan",
			axisAt(y),
			axisAt(y + course) + Vector3.new(0, 0.02, 0),
			r * 2,
			jitter(shade, rng, 0.03),
			Enum.Material.Granite
		)
		y += course
	end
	-- 창
	local wy = y0 + course * 5.5
	local wr = R[6]
	local wd = Vector3.new(windowToward.X - x, 0, windowToward.Z - z).Unit
	local wc = axisAt(wy) + wd * (wr - 0.35)
	block(m, "Chang", Vector3.new(2.6, 2.6, 1.0), face(wc, wc + wd), P.meok, Enum.Material.Slate)
	block(
		m,
		"Inbang",
		Vector3.new(3.6, 0.5, 1.1),
		face(wc, wc + wd) * CFrame.new(0, 1.3, 0.05),
		P.graniteDark,
		Enum.Material.Granite
	)
	-- 정자석: 아래 켜 둘(동서로), 위 켜 하나(남북으로, 하나는 떨어졌다)
	local topC = axisAt(y)
	for _, s in { -1, 1 } do
		block(
			m,
			"Jeongjaseok",
			Vector3.new(7.6, 0.9, 1.0),
			CFrame.new(topC + Vector3.new(0, 0.45, s * 2.3)),
			P.granite,
			Enum.Material.Granite
		)
	end
	block(
		m,
		"Jeongjaseok",
		Vector3.new(1.0, 0.9, 7.6),
		CFrame.new(topC + Vector3.new(-2.3, 1.35, 0)) * CFrame.Angles(rad(rng(-3, 3)), 0, 0),
		P.granite,
		Enum.Material.Granite
	)
	local fx, fz = x + 7.8, z + 2.8
	block(
		m,
		"Jeongjaseok",
		Vector3.new(7.6, 0.9, 1.0),
		CFrame.new(fx, surface(fx, fz) + 0.3, fz) * CFrame.Angles(0, rng(0, 3), 0) * CFrame.Angles(0, 0, rng(0.1, 0.22)),
		P.granite,
		Enum.Material.Granite
	)
	for _ = 1, 3 do
		local a = rng(0, math.pi * 2)
		local sx, sz = x + cos(a) * rng(8, 11), z + sin(a) * rng(8, 11)
		local s = rng(0.9, 1.6)
		block(
			m,
			"Dol",
			Vector3.new(s * 1.5, s, s),
			CFrame.new(sx, surface(sx, sz) + s * 0.3, sz) * CFrame.Angles(rng(-0.3, 0.3), rng(0, 3), rng(-0.3, 0.3)),
			P.granite:Lerp(P.graniteDark, rng(0, 1)),
			Enum.Material.Granite
		)
	end
	return m
end

-- 무너진 정자 터: 기단, 초석 넷, 부러진 기둥 셋과 쓰러진 기둥 하나, 내려앉은 지붕 토막, 흩어진 기와
local function pavilionRuin(parent: Instance, x: number, z: number, toward: Vector3, rng): Model
	local m = model(parent, "무너진 정자")
	local low, high = span(x, z, 8.9)
	local look = face(Vector3.new(x, 0, z), toward)
	local top = high + 0.9
	block(
		m,
		"Gidan",
		Vector3.new(12.5, top - (low - 1), 12.5),
		look * CFrame.new(0, (top + low - 1) / 2, 0),
		jitter(P.granite, rng, 0.05),
		Enum.Material.Granite
	)
	local heights = { 5.2, 2.1, 0.9, 3.6 }
	for k, c in { { 1, 1 }, { -1, 1 }, { 1, -1 }, { -1, -1 } } do
		local p = look * CFrame.new(c[1] * 4.3, top, c[2] * 4.3)
		block(
			m,
			"Choseok",
			Vector3.new(1.8, 0.5, 1.8),
			p * CFrame.new(0, 0.25, 0),
			P.graniteDark,
			Enum.Material.Granite
		)
		if k ~= 3 then
			local h = heights[k]
			cyl(
				m,
				"Gidung",
				(p * CFrame.new(0, 0.5, 0)).Position,
				(p * CFrame.new(rng(-0.15, 0.15), 0.5 + h, rng(-0.15, 0.15))).Position,
				1.1,
				P.seokganju:Lerp(P.woodDark, 0.45),
				Enum.Material.Wood
			)
		end
	end
	-- 쓰러진 기둥: 기단 모서리에서 땅으로
	local a = (look * CFrame.new(4.3, top + 0.5, -4.3)).Position
	local bxz = look * CFrame.new(9.5, 0, -8.5)
	cyl(
		m,
		"Gidung",
		a,
		Vector3.new(bxz.X, surface(bxz.X, bxz.Z) + 0.5, bxz.Z),
		1.1,
		P.seokganju:Lerp(P.woodDark, 0.5),
		Enum.Material.Wood
	)
	-- 내려앉은 지붕 토막: 기와 판 둘이 기단 뒤 가장자리에 걸쳐 땅으로 비스듬히
	local roofCf = look * CFrame.new(-1.5, top + 1.3, 6.6) * CFrame.Angles(rad(-28), rad(rng(-8, 8)), rad(rng(-6, 6)))
	block(m, "Giwa", Vector3.new(8.5, 0.6, 5.2), roofCf, P.giwa, Enum.Material.ClayRoofTiles)
	block(
		m,
		"Giwa",
		Vector3.new(6, 0.55, 3.4),
		roofCf * CFrame.new(1.2, 0.35, -3.6) * CFrame.Angles(rad(14), 0, 0),
		P.giwa,
		Enum.Material.ClayRoofTiles
	)
	beam(
		m,
		"Maru",
		(roofCf * CFrame.new(-4.2, 0.6, 2.4)).Position,
		(roofCf * CFrame.new(4.0, 0.55, 2.5)).Position,
		0.9,
		0.8,
		P.giwaDark,
		Enum.Material.Slate
	)
	for _ = 1, 5 do
		local ang = rng(0, math.pi * 2)
		local tx, tz = x + cos(ang) * rng(7.5, 11), z + sin(ang) * rng(7.5, 11)
		block(
			m,
			"Giwa",
			Vector3.new(1.3, 0.3, 1.0),
			CFrame.new(tx, surface(tx, tz) + 0.1, tz) * CFrame.Angles(rng(-0.3, 0.3), rng(0, 3), rng(-0.3, 0.3)),
			P.giwa,
			Enum.Material.ClayRoofTiles
		)
	end
	return m
end

-- 부서진 잔교: 물가에서 바다 쪽으로 말뚝 다섯 쌍, 판 넷 (셋째 칸은 무너져 물에 비스듬히)
local function jetty(parent: Instance, shore: Vector3, sea: Vector3, rng): Model
	local m = model(parent, "옛 잔교")
	local d = Vector3.new(sea.X - shore.X, 0, sea.Z - shore.Z)
	local len = d.Magnitude
	local dir = d / len
	local side = Vector3.new(-dir.Z, 0, dir.X)
	local deckY = max(surface(shore.X, shore.Z) + 0.4, Land.SEA + 1.4)
	local spans = 4
	for k = 0, spans do
		local p = shore + dir * (len * k / spans)
		for _, s in { -1, 1 } do
			local q = p + side * s * 1.9
			local fy = Land.height(q.X, q.Z)
			local topY = deckY - 0.1 + (if k == spans and s == 1 then -1.4 else rng(-0.2, 0.4))
			cyl(
				m,
				"Malttuk",
				Vector3.new(q.X, fy - 1, q.Z),
				Vector3.new(q.X + rng(-0.25, 0.25), topY, q.Z + rng(-0.25, 0.25)),
				0.85,
				COL.hullDark,
				Enum.Material.Wood
			)
		end
		if k < spans then
			local a = Vector3.new(p.X, deckY + 0.1, p.Z)
			local bq = shore + dir * (len * (k + 1) / spans)
			local b = Vector3.new(bq.X, deckY + 0.1, bq.Z)
			if k == 2 then
				beam(
					m,
					"Pan",
					a + dir * 0.6,
					Vector3.new(b.X, Land.SEA - 1.2, b.Z) - dir * 0.8 + side * 0.8,
					4,
					0.4,
					COL.hull,
					Enum.Material.WoodPlanks
				)
			else
				beam(m, "Pan", a, b, 4.2, 0.4, jitter(COL.hull, rng, 0.06), Enum.Material.WoodPlanks)
			end
		end
	end
	return m
end

local function buildCrescent(parent: Instance, rng)
	local c = Land.ISLES.crescent
	local avoid = {}
	-- 서쪽 팔: 옛 관측대와 혼천의. 앞(계단)은 북쪽 모래톱(백사포 쪽)을 본다
	local terraceAt = Vector3.new(-401, 0, 1903)
	local _, terraceTop = terrace(parent, terraceAt.X, terraceAt.Z, Vector3.new(-395, 0, 1780), rng)
	armillary(parent, terraceTop, rng)
	table.insert(avoid, { terraceAt.X, terraceAt.Z, 26 })
	-- 남쪽 팔: 옛 별탑 (창은 안쪽 만 쪽)
	local towerAt = Vector3.new(-346, 0, 1999)
	starTower(parent, towerAt.X, towerAt.Z, Vector3.new(-290, 0, 1960), rng)
	table.insert(avoid, { towerAt.X, towerAt.Z, 14 })
	-- 그 사이: 무너진 정자 터
	local ruinAt = Vector3.new(-382, 0, 1955)
	pavilionRuin(parent, ruinAt.X, ruinAt.Z, Vector3.new(-300, 0, 1935), rng)
	table.insert(avoid, { ruinAt.X, ruinAt.Z, 13 })
	-- 북쪽 모래톱(뭍과 이어진 얕은 모래): 섬 이름 비석과 관측대로 오르는 돌계단
	local _, sx, sz = steleAt(parent, -346, 1801, "월아도", Vector3.new(-346, 0, 1700))
	table.insert(avoid, { sx, sz, 5 })
	local north = {
		Vector3.new(-354, 0, 1808),
		Vector3.new(-363, 0, 1820),
		Vector3.new(-371, 0, 1834),
		Vector3.new(-379, 0, 1850),
		Vector3.new(-392, 0, 1866),
		Vector3.new(-400, 0, 1880),
	}
	-- 안쪽 만: 부서진 잔교와 별탑으로 오르는 벼랑 계단
	jetty(parent, Vector3.new(-292, 0, 1967), Vector3.new(-286, 0, 1930), rng)
	table.insert(avoid, { -289, 1950, 12 })
	local bay = {
		Vector3.new(-296, 0, 1975),
		Vector3.new(-318, 0, 1988),
		Vector3.new(-334, 0, 1994),
	}
	-- 별탑에서 정자 터를 지나 관측대 뒤로
	local ridge = {
		Vector3.new(-354, 0, 1988),
		Vector3.new(-368, 0, 1968),
		Vector3.new(-378, 0, 1946),
		Vector3.new(-392, 0, 1925),
	}
	for _, line in { north, bay, ridge } do
		for i = 1, #line - 1 do
			stairs(parent, line[i], line[i + 1], 3, rng, 3)
		end
		for _, p in line do
			table.insert(avoid, { p.X, p.Z, 5 })
		end
	end
	local function onIsland(x: number, z: number): boolean
		local dc = sqrt((x - c.x) ^ 2 + (z - c.z) ^ 2)
		local dcut = sqrt((x - c.cut.x) ^ 2 + (z - c.cut.z) ^ 2)
		return dc < c.r + 14 and dcut > c.cut.r - 14
	end
	-- 해송 숲 둘 (서쪽 팔 북쪽 끝, 남쪽 팔 동쪽 끝)과 섬 전체의 덤불·갯풀
	local wind = inwardWind(c.x, c.z)
	for _, grove in { { -380, 1846, 22, 4 }, { -268, 2008, 20, 3 }, { -430, 1960, 14, 2 } } do
		local function inGrove(x: number, z: number): boolean
			return onIsland(x, z) and flatness(x, z, 2.5) < 2.6
		end
		for _, p in pickSpots(rng, grove[1], grove[2], grove[3], grove[4], 2, 60, avoid, 9, inGrove) do
			windPine(parent, p, rng, wind, rng(11, 16))
			table.insert(avoid, { p.X, p.Z, 5 })
		end
	end
	islandNature(
		parent,
		rng,
		c.x,
		c.z,
		128,
		avoid,
		{ pines = 0, shrubs = 9, grass = 14, rocks = 7, kelp = 3, inside = onIsland }
	)
	-- 갈매기 몇: 물가 바위 위
	for _, rock in parent:GetChildren() do
		if rock.Name == "갯바위" and rng(0, 1) > 0.6 then
			local main = rock:FindFirstChild("Rock") :: BasePart?
			if main then
				gull(rock, (main.CFrame * CFrame.new(0, main.Size.Y / 2 - 0.05, 0)).Position, rng(0, 6.2))
			end
		end
	end
end

-- 연파군도 --------------------------------------------------------------------------------------
--
-- 동쪽 바닷가 앞 작은 섬 다섯. 가장 큰 섬(모래톱으로 이어졌다) 꼭대기에 외딴 정자와 석등, 서쪽 모래톱에서 돌계단.
-- 가장 높은 바위섬은 벼랑 바위로 깎아지르고 꼭대기에 해송 한 그루. 섬 사이 물 위에 낮게 깔린 물안개.

local function mistBank(parent: Instance, x: number, z: number, rng, withEmitter: boolean)
	local c = Vector3.new(x, Land.SEA + rng(1.5, 6), z)
	local size = Vector3.new(rng(60, 130), rng(6, 12), rng(40, 80))
	local p = ellipsoid(parent, "Mulangae", c, size, CFrame.Angles(0, rng(0, math.pi), 0), COL.mist, rng(0.62, 0.8))
	if withEmitter then
		emitter(p, {
			Name = "Angae",
			Rate = 0.9,
			Lifetime = NumberRange.new(10, 16),
			Speed = NumberRange.new(0.4, 1.4),
			SpreadAngle = Vector2.new(180, 20),
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 20), NumberSequenceKeypoint.new(1, 48) }),
			Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1),
				NumberSequenceKeypoint.new(0.3, 0.84),
				NumberSequenceKeypoint.new(1, 1),
			}),
			Color = ColorSequence.new(Color3.fromRGB(238, 242, 246)),
			RotSpeed = NumberRange.new(-4, 4),
		})
	end
	return p
end

-- 벼랑 바위 판: 가파른 비탈에서 물속부터 솟아 가운데(toward) 쪽으로 조금 기댄 큰 바위 판 (섬을 깎아지른 바위섬처럼)
local function crag(parent: Instance, x: number, z: number, toward: Vector3, rng, k: number): BasePart
	local g = surface(x, z)
	local bottom = min(g, Land.SEA) - 6
	local topY = g + rng(4, 11)
	local cc = Vector3.new(x, (topY + bottom) / 2, z)
	return block(
		parent,
		"Byeorang",
		Vector3.new(rng(9, 14), topY - bottom, rng(5, 8)),
		face(cc, Vector3.new(toward.X, cc.Y, toward.Z)) * CFrame.Angles(rad(rng(-9, -4)), 0, rad(rng(-5, 5))),
		jitter(STRATA[1 + k % #STRATA], rng, 0.05),
		Enum.Material.Slate
	)
end

-- 섬 둘레 count 곳에 벼랑 바위 판. from~to(라디안) 사이 방향만, 높이가 lo~hi 인 비탈에
local function cragRing(
	parent: Instance,
	cx: number,
	cz: number,
	radius: number,
	count: number,
	rng,
	from: number,
	to: number
)
	for k = 0, count - 1 do
		local a = from + (to - from) * (k + rng(0.25, 0.75)) / count
		-- 비탈에서 땅이 바다 높이 위 4~20 인 곳을 찾는다
		for rr = radius * 0.5, radius * 1.3, 2 do
			local x, z = cx + cos(a) * rr, cz + sin(a) * rr
			local g = surface(x, z)
			if g < Land.SEA + 12 then
				crag(parent, x, z, Vector3.new(cx, 0, cz), rng, k)
				break
			end
		end
	end
end

-- 돌탑 (작은 돌을 포개 쌓은 탑)
local function cairn(parent: Instance, x: number, z: number, rng): Model
	local m = model(parent, "돌탑")
	local y = surface(x, z) - 0.3
	local s = 2.6
	for _ = 1, 5 do
		local h = s * 0.55
		block(
			m,
			"Dol",
			Vector3.new(s, h, s * rng(0.8, 1)),
			CFrame.new(x + rng(-0.15, 0.15), y + h / 2, z + rng(-0.15, 0.15))
				* CFrame.Angles(rng(-0.06, 0.06), rng(0, 3), rng(-0.06, 0.06)),
			jitter(P.granite, rng, 0.1),
			Enum.Material.Slate
		)
		y += h * 0.92
		s *= 0.78
	end
	return m
end

local function buildMist(parent: Instance, rng)
	local isles = Land.ISLES.mist
	local wind = inwardWind(1960, 380)
	local avoid = {}
	-- 외딴 정자: 가장 큰 섬 꼭대기, 앞(-Z)이 서쪽 육지를 본다
	local px, pz = 1921, 265
	local low, high = span(px, pz, 9.5)
	local m = model(parent, "외딴 정자")
	if high - low > 0.5 then
		block(
			m,
			"Footing",
			Vector3.new(13.6, high - low + 1, 13.6),
			CFrame.new(px, (high + low) / 2 - 0.9, pz),
			P.graniteDark,
			Enum.Material.Granite
		)
	end
	local cf = face(Vector3.new(px, high, pz), Vector3.new(px - 10, high, pz))
	Build.pavilion(m, cf, { bay = 8, detail = 1, name = "연파정" })
	table.insert(avoid, { px, pz, 13 })
	-- 석등 둘: 정자 앞 양옆
	for _, s in { 1 } do
		local l = cf * CFrame.new(s * 7.5, 0, -7.2)
		Build.stoneLantern(parent, Vector3.new(l.X, surface(l.X, l.Z), l.Z))
		table.insert(avoid, { l.X, l.Z, 3 })
	end
	-- 돌계단: 서쪽 모래톱에서 정자 앞 계단까지
	local stepFoot = cf * CFrame.new(0, 0, -10.4)
	stairs(parent, Vector3.new(1864, 0, 262), Vector3.new(stepFoot.X, 0, stepFoot.Z), 3.2, rng)
	for x = 1864, stepFoot.X, 8 do
		table.insert(avoid, { x, 263, 4.5 })
	end
	local _, sx, sz = steleAt(parent, 1858, 252, "연파군도", Vector3.new(1800, 0, 252))
	table.insert(avoid, { sx, sz, 5 })

	-- 높은 바위섬: 벼랑 바위 판 여섯 (가운데 쪽으로 조금 기댄다), 꼭대기에 해송
	local hx, hz = isles[4][1], isles[4][2]
	for k = 0, 5 do
		local a = k * math.pi / 3 + rng(-0.3, 0.3)
		local rr = 19 + rng(-2, 2)
		crag(parent, hx + cos(a) * rr, hz + sin(a) * rr, Vector3.new(hx, 0, hz), rng, k)
	end
	-- 다른 섬 비탈에도 벼랑 바위 (큰 섬은 계단이 오르는 서쪽을 비운다)
	cragRing(parent, isles[1][1], isles[1][2], isles[1][3], 5, rng, rad(-110), rad(130))
	cragRing(parent, isles[2][1], isles[2][2], isles[2][3], 3, rng, 0, math.pi * 2)
	cragRing(parent, isles[3][1], isles[3][2], isles[3][3], 2, rng, rad(40), rad(220))
	windPine(parent, Vector3.new(hx + 2, surface(hx + 2, hz), hz), rng, wind, 11)
	Build.shrub(parent, Vector3.new(hx - 4, surface(hx - 4, hz + 3), hz + 3), rng, { leaves = COAST_LEAVES, size = 3 })
	table.insert(avoid, { hx, hz, 26 })

	-- 작은 섬들
	for i = 2, #isles do
		local isle = isles[i]
		if i ~= 4 then
			local ix, iz, ir = isle[1], isle[2], isle[3]
			if i == 2 then
				cairn(parent, ix - 3, iz + 2, rng)
				table.insert(avoid, { ix - 3, iz + 2, 4 })
			end
			local function near(x: number, z: number): boolean
				return (x - ix) ^ 2 + (z - iz) ^ 2 < (ir + 16) ^ 2
			end
			islandNature(parent, rng, ix, iz, ir + 14, avoid, {
				pines = if ir > 28 then 1 else 0,
				pineMin = 4,
				shrubs = 2,
				grass = 2,
				rocks = 2,
				kelp = 1,
				inside = near,
			})
		end
	end
	local bx, bz, br = isles[1][1], isles[1][2], isles[1][3]
	local function onBig(x: number, z: number): boolean
		return (x - bx) ^ 2 + (z - bz) ^ 2 < (br + 12) ^ 2
	end
	islandNature(
		parent,
		rng,
		bx,
		bz,
		br + 10,
		avoid,
		{ pines = 3, pineMin = 10, shrubs = 4, grass = 4, rocks = 4, kelp = 1, inside = onBig }
	)

	-- 물속에서 솟은 바위기둥 둘
	for _, s in { { 2088, 300, 30 }, { 1928, 488, 20 }, { 2090, 455, 16 } } do
		if Land.height(s[1], s[2]) < Land.SEA - 3 then
			local stack, crown = seaStack(parent, s[1], s[2], s[3], rng, { radius = rng(5, 7) })
			if s[3] > 25 then
				windPine(stack, crown, rng, wind, 8)
			end
		end
	end

	-- 물안개
	local mists = 0
	for _ = 1, 200 do
		if mists >= 12 then
			break
		end
		local x, z = rng(1850, 2100), rng(150, 580)
		local wet = true
		for _, o in { { 0, 0 }, { 40, 0 }, { -40, 0 }, { 0, 30 }, { 0, -30 } } do
			if Land.height(x + o[1], z + o[2]) > Land.SEA - 0.5 then
				wet = false
			end
		end
		if wet then
			mistBank(parent, x, z, rng, mists % 4 == 0)
			mists += 1
		end
	end
end

-- 경도 ----------------------------------------------------------------------------------------
--
-- 고래 등처럼 긴 바위섬 (북동 끝이 머리, 남서 끝이 꼬리). 머리 쪽 등성이에 봉화탑(등대처럼 밤새 불을 켠다),
-- 등줄기를 따라 따개비 낀 바위 등뼈, 머리 곁에 물을 뿜는 숨구멍, 꼬리 쪽 새 바위와 물 위로 솟은 꼬리지느러미 바위.

-- 봉화탑: 둥근 돌탑 네 켜 (켜마다 띠), 문과 창, 꼭대기 돌기둥 넷에 사모 돌지붕, 가운데 쇠 화로에 불
local function beaconTower(parent: Instance, x: number, z: number, toward: Vector3, rng): Model
	local m = model(parent, "봉화탑")
	local low, high = span(x, z, 9.6)
	local look = face(Vector3.new(x, 0, z), toward)
	local y = high + 0.6
	block(
		m,
		"Gidan",
		Vector3.new(13.5, y - (low - 1.2), 13.5),
		look * CFrame.new(0, (y + low - 1.2) / 2, 0),
		P.graniteDark,
		Enum.Material.Granite
	)
	local stone = Color3.fromRGB(176, 170, 158)
	local ds = { 9.6, 8.5, 7.5, 6.6 }
	local hs = { 6.5, 6, 5.5, 5 }
	local c = Vector3.new(x, 0, z)
	for k, d in ds do
		local h = hs[k]
		cyl(
			m,
			"Mom",
			Vector3.new(x, y - 0.05, z),
			Vector3.new(x, y + h, z),
			d,
			jitter(stone, rng, 0.04),
			Enum.Material.Granite
		)
		cyl(
			m,
			"Ddi",
			Vector3.new(x, y + h - 0.5, z),
			Vector3.new(x, y + h + 0.1, z),
			d + 0.8,
			P.graniteDark,
			Enum.Material.Granite
		)
		if k == 1 then
			local door = look * CFrame.new(0, y + 1.9, -d / 2 + 0.3)
			block(m, "Mun", Vector3.new(2.4, 3.8, 1.0), door, P.woodDark, Enum.Material.Wood)
			block(
				m,
				"Inbang",
				Vector3.new(3.2, 0.5, 1.1),
				door * CFrame.new(0, 2.15, -0.05),
				P.graniteDark,
				Enum.Material.Granite
			)
		elseif k == 2 or k == 3 then
			local side = if k == 2 then 1 else -1
			local win = look * CFrame.Angles(0, side * rad(70), 0) * CFrame.new(0, y + h * 0.55, -d / 2 + 0.25)
			block(m, "Chang", Vector3.new(0.9, 1.8, 0.8), win, P.meok, Enum.Material.Slate)
		end
		y += h
	end
	local deck = y + 0.1
	cyl(m, "Maru", Vector3.new(x, deck - 0.6, z), Vector3.new(x, deck, z), 8.4, P.graniteDark, Enum.Material.Granite)
	for _, q in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
		local p = look * CFrame.new(q[1] * 2.5, deck + 2.1, q[2] * 2.5)
		block(m, "Gidung", Vector3.new(0.8, 4.2, 0.8), p, stone, Enum.Material.Granite)
	end
	local yaw = math.atan2(-(toward.X - x), -(toward.Z - z))
	block(
		m,
		"Cheoma",
		Vector3.new(8.4, 0.5, 8.4),
		CFrame.new(x, deck + 4.35, z) * CFrame.Angles(0, yaw, 0),
		P.giwaDark,
		Enum.Material.Slate
	)
	Build.pyramid(m, "Jibung", Vector3.new(x, deck + 4.55, z), 7.6, 2.8, yaw, P.giwaDark, Enum.Material.Slate)
	ball(m, "Boju", Vector3.new(x, deck + 7.65, z), 1.1, P.graniteDark, Enum.Material.Granite)
	cyl(m, "Hwaro", Vector3.new(x, deck, z), Vector3.new(x, deck + 1.3, z), 2.6, P.meok, Enum.Material.Metal)
	local ember = block(
		m,
		"Bul",
		Vector3.new(1.8, 0.4, 1.8),
		CFrame.new(x, deck + 1.4, z) * CFrame.Angles(0, rad(45), 0),
		Color3.fromRGB(255, 140, 60),
		Enum.Material.Neon
	)
	ember.CastShadow = false
	local fire = Instance.new("Fire")
	fire.Size = 5
	fire.Heat = 7
	fire.Color = Color3.fromRGB(255, 150, 60)
	fire.SecondaryColor = Color3.fromRGB(255, 220, 120)
	fire.Parent = ember
	local l = Instance.new("PointLight")
	l.Color = Color3.fromRGB(255, 180, 110)
	l.Range = 48
	l.Brightness = 2.2
	l.Shadows = false
	l.Parent = ember
	local _ = c
	return m
end

local function buildWhale(parent: Instance, rng)
	local w = Land.ISLES.whale
	local a = rad(w.angle)
	local U = Vector3.new(cos(a), 0, sin(a)) -- 머리(북동) 쪽
	local V = Vector3.new(-sin(a), 0, cos(a))
	local O = Vector3.new(w.x, 0, w.z)
	local function P2(u: number, v: number): Vector3
		local p = O + U * u + V * v
		return Vector3.new(p.X, surface(p.X, p.Z), p.Z)
	end
	local avoid = {}
	local wind = inwardWind(w.x, w.z)
	-- 봉화탑: 머리 쪽 등성이, 문은 육지(동남)를 본다
	local t = P2(80, 0)
	beaconTower(parent, t.X, t.Z, Vector3.new(0, 0, 0), rng)
	table.insert(avoid, { t.X, t.Z, 13 })
	-- 비석: 탑 아래 육지 쪽
	local s = P2(60, 22)
	local _, sx, sz = steleAt(parent, s.X, s.Z, "경도", Vector3.new(0, 0, 0))
	table.insert(avoid, { sx, sz, 5 })
	-- 등뼈 바위: 등줄기를 따라 낮고 긴 바위 (따개비 낀 곳이 희끗하다)
	for u = -112, 112, 22 do
		if math.abs(u - 80) > 18 and math.abs(u - 38) > 10 then
			local v = rng(-4, 4)
			local p = P2(u, v)
			local len = rng(12, 18)
			local ahead, behind = P2(u + len / 2, v), P2(u - len / 2, v)
			local pitch = math.atan2(ahead.Y - behind.Y, len)
			local thick = rng(3, 4.6)
			local cfp = face(p, p + U) * CFrame.Angles(pitch, 0, rad(rng(-6, 6)))
			local spine = model(parent, "등뼈바위")
			local slab = block(
				spine,
				"Deungppyeo",
				Vector3.new(rng(6, 10), thick, len),
				cfp * CFrame.new(0, thick * 0.12, 0),
				jitter(Color3.fromRGB(86, 90, 96), rng, 0.06),
				Enum.Material.Slate
			)
			if rng(0, 1) > 0.5 then
				deco(
					block(
						spine,
						"Ttagaebi",
						Vector3.new(slab.Size.X * 0.5, 0.25, len * 0.35),
						slab.CFrame * CFrame.new(rng(-1, 1), thick / 2 + 0.05, rng(-2, 2)),
						COL.barnacle,
						Enum.Material.Slate
					)
				)
			end
			table.insert(avoid, { p.X, p.Z, 7 })
		end
	end
	-- 숨구멍: 머리 곁 (북서쪽 비탈), 돌 고리와 검은 구멍, 물을 높이 뿜는다
	local h = P2(38, -16)
	local hole = model(parent, "숨구멍")
	for k = 0, 5 do
		local ang = k * math.pi / 3 + rng(-0.2, 0.2)
		local sx, sz = h.X + cos(ang) * 2.6, h.Z + sin(ang) * 2.6
		local sz2 = rng(1.4, 2.2)
		block(
			hole,
			"Dol",
			Vector3.new(sz2 * 1.4, sz2, sz2),
			CFrame.new(sx, surface(sx, sz) + sz2 * 0.25, sz) * CFrame.Angles(rng(-0.3, 0.3), ang, rng(-0.3, 0.3)),
			jitter(Color3.fromRGB(84, 86, 90), rng, 0.08),
			Enum.Material.Slate
		)
	end
	local pit = block(
		hole,
		"Gumeong",
		Vector3.new(0.4, 3.2, 3.2),
		CFrame.new(h.X, h.Y + 0.05, h.Z) * CFrame.Angles(0, 0, rad(90)),
		Color3.fromRGB(20, 26, 30),
		Enum.Material.Slate
	)
	pit.Shape = Enum.PartType.Cylinder
	deco(pit)
	local spout = soft(block(hole, "Mulgi", Vector3.new(1.6, 0.4, 1.6), CFrame.new(h.X, h.Y + 0.4, h.Z), COL.mist), 1)
	emitter(spout, {
		Name = "Mulgi",
		EmissionDirection = Enum.NormalId.Top,
		Rate = 14,
		Lifetime = NumberRange.new(1.4, 2),
		Speed = NumberRange.new(22, 30),
		SpreadAngle = Vector2.new(7, 7),
		Acceleration = Vector3.new(0, -24, 0),
		Drag = 0.6,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.6), NumberSequenceKeypoint.new(1, 7) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 1) }),
		Color = ColorSequence.new(Color3.fromRGB(240, 248, 252)),
	})
	table.insert(avoid, { h.X, h.Z, 6 })
	-- 꼬리: 새 바위 셋과 갈매기, 물 위로 솟은 꼬리지느러미 바위
	for _, q in { { -128, 14 }, { -140, -12 }, { -118, -22 } } do
		local p = P2(q[1], q[2])
		local birdRock, main = seaRock(
			parent,
			p.X,
			p.Z,
			rng(6, 9),
			rng,
			{ guano = true, name = "새바위", color = Color3.fromRGB(96, 94, 92) }
		)
		for _ = 1, 2 do
			local top = main.CFrame * CFrame.new(rng(-1.2, 1.2), main.Size.Y / 2 - 0.05, rng(-1.2, 1.2))
			gull(birdRock, top.Position, rng(0, 6.2))
		end
		table.insert(avoid, { p.X, p.Z, 9 })
	end
	local tail = O + U * -194
	local fin = model(parent, "꼬리바위")
	local tailCf = face(Vector3.new(tail.X, Land.SEA + 1.2, tail.Z), Vector3.new(tail.X, 0, tail.Z) - U)
	block(
		fin,
		"Kkori",
		Vector3.new(5, 3.6 + (Land.SEA - Land.height(tail.X, tail.Z)), 14),
		tailCf
			* CFrame.new(0, 1.2 - (3.6 + (Land.SEA - Land.height(tail.X, tail.Z))) / 2 + 0.6, -2)
			* CFrame.Angles(rad(8), 0, 0),
		Color3.fromRGB(82, 86, 92),
		Enum.Material.Slate
	)
	for _, sgn in { -1, 1 } do
		block(
			fin,
			"Jineureomi",
			Vector3.new(17, 2.6, 9),
			tailCf * CFrame.new(sgn * 8.5, 3.2, -9) * CFrame.Angles(rad(-10), sgn * rad(18), sgn * rad(26)),
			Color3.fromRGB(78, 82, 88),
			Enum.Material.Slate
		)
	end
	soft(
		block(
			fin,
			"Multtae",
			Vector3.new(6, 0.9, 15),
			CFrame.new(tail.X, Land.SEA + 0.15, tail.Z) * (tailCf - tailCf.Position),
			COL.seaweed,
			Enum.Material.Slate
		)
	)
	local function onWhale(x: number, z: number): boolean
		local dx, dz = x - w.x, z - w.z
		local u, v = dx * cos(a) + dz * sin(a), -dx * sin(a) + dz * cos(a)
		return (u / w.a) ^ 2 + (v / w.b) ^ 2 < 1.35 * 1.35
	end
	-- 옆구리 벼랑 바위: 긴 두 비탈에 셋씩
	for _, sgn in { -1, 1 } do
		for k = 0, 2 do
			local u = -80 + k * 70 + rng(-12, 12)
			for vv = w.b * 0.5, w.b * 1.3, 2 do
				local p = O + U * u + V * (sgn * vv)
				if surface(p.X, p.Z) < Land.SEA + 12 then
					crag(parent, p.X, p.Z, O + U * u, rng, k)
					break
				end
			end
		end
	end
	islandNature(
		parent,
		rng,
		w.x,
		w.z,
		170,
		avoid,
		{ pines = 6, pineMin = 14, shrubs = 6, grass = 6, rocks = 6, kelp = 5, inside = onWhale }
	)
end

-- 큰 땅 바닷가 ------------------------------------------------------------------------------------
--
-- 바닷가 선을 따라 60~100 스터드마다 한 자리: 물가 바위, 유목과 갯풀, 뭍에 끌어 올린 거룻배, 물 위 말무리.
-- 모래밭은 바닷가 선에서 바다 쪽으로 넓게(물가는 선 바깥 약 146) 내려가고, 벼랑 바닷가는 좁다(약 58).
-- 다른 담당이 꾸미는 바닷가(포구, 곶, 벼랑, 빙하 끝, 늪 하구)와 연파군도 앞은 비운다.

local SKIP = {
	{ -440, 1575, 330 }, -- 백사포
	{ 1180, -1180, 340 }, -- 망선대 곶
	{ -1320, 20, 500 }, -- 낙조대 벼랑
	{ -300, -1730, 210 }, -- 설하 빙하 끝
	{ 130, 1270, 450 }, -- 무택 하구
	{ 1960, 380, 250 }, -- 연파군도
	{ -1420, -1270, 230 }, -- 경도 앞
}
Sea.SKIP = SKIP

local function skipped(x: number, z: number, margin: number?): boolean
	for _, s in SKIP do
		local r = s[3] + (margin or 0)
		if (x - s[1]) ^ 2 + (z - s[2]) ^ 2 < r * r then
			return true
		end
	end
	return false
end

-- 방향 theta 의 바닷가 반지름과 물가(처음 물에 잠기는 곳) 반지름
local function waterline(theta: number): (number, number?)
	local dx, dz = cos(theta), sin(theta)
	local R = Land.shoreR(dx * 1000, dz * 1000)
	for r = R - 40, R + 260, 3 do
		if Land.height(dx * r, dz * r) < Land.SEA then
			return R, r
		end
	end
	return R, nil
end
Sea.waterline = waterline

-- 따로 정한 큰 볼거리: 난파선 (모래밭), 바위기둥 무리 (주로 벼랑 바닷가 앞바다). 각도(도)
local WRECKS = { 38, 63, 300 }
local STACKS = { 128, 152, 203, 247, 279, 291, 27 }

local function buildCoast(parent: Instance, rng)
	-- 고른 간격으로 한 바퀴
	local theta = rng(0, 0.05)
	while theta < math.pi * 2 do
		local R, wl = waterline(theta)
		local dx, dz = cos(theta), sin(theta)
		local tangent = Vector3.new(-dz, 0, dx)
		if wl and not skipped(dx * wl, dz * wl) then
			local sandy = wl - R > 100
			local function along(r: number, t: number): (number, number)
				return dx * r + tangent.X * t, dz * r + tangent.Z * t
			end
			local roll = rng(0, 1)
			if sandy then
				if roll < 0.42 then
					local x, z = along(wl + rng(-6, 5), rng(-12, 12))
					if isClear(x, z, 8) then
						seaRock(parent, x, z, rng(3, 7), rng, { count = 1, guano = rng(0, 1) > 0.8 })
						if rng(0, 1) > 0.65 then
							local x2, z2 = along(wl + rng(-10, 8), rng(-18, 18))
							seaRock(parent, x2, z2, rng(2, 3.5), rng, { count = 0 })
						end
					end
				elseif roll < 0.74 then
					local x, z = along(wl - rng(14, 40), rng(-12, 12))
					if isClear(x, z, 9) then
						driftwood(parent, x, z, rng)
						if rng(0, 1) > 0.4 then
							local gx, gz = along(wl - rng(45, 95), rng(-15, 15))
							grassTuft(parent, gx, gz, rng)
						end
					end
				elseif roll < 0.81 then
					local x, z = along(wl - rng(8, 18), rng(-10, 10))
					if isClear(x, z, 9) then
						local toward = Vector3.new(x, 0, z)
							+ tangent * (if rng(0, 1) > 0.5 then 10 else -10)
							- Vector3.new(dx, 0, dz) * 6
						beachedBoat(parent, x, z, toward, rng)
					end
				else
					local x, z = along(wl + rng(10, 24), rng(-10, 10))
					kelp(parent, x, z, rng)
					local x2, z2 = along(wl + rng(-3, 4), rng(-10, 10))
					seaRock(parent, x2, z2, rng(2.5, 4.5), rng, { count = 0 })
				end
			else
				-- 벼랑 바닷가: 벼랑 밑 큰 바위
				local x, z = along(wl - rng(3, 10), rng(-10, 10))
				if isClear(x, z, 12) then
					seaRock(parent, x, z, rng(6, 12), rng, { count = 1, color = COL.wetRock:Lerp(COL.rock, 0.2) })
					if roll < 0.6 then
						local x2, z2 = along(wl + rng(-2, 8), rng(-20, 20))
						seaRock(parent, x2, z2, rng(4, 7), rng, { count = 0 })
					elseif roll < 0.85 then
						local x2, z2 = along(wl + rng(10, 24), rng(-14, 14))
						kelp(parent, x2, z2, rng)
					end
				end
			end
		end
		theta += rng(90, 125) / R
	end

	-- 난파선
	for _, deg in WRECKS do
		local th = rad(deg)
		local _, wl = waterline(th)
		if wl then
			local x, z = cos(th) * (wl - 12), sin(th) * (wl - 12)
			if not skipped(x, z) and isClear(x, z, 20) then
				wreck(parent, x, z, th + math.pi / 2 + rng(-0.5, 0.5), rng)
			end
		end
	end
	-- 바위기둥 무리: 큰 기둥 하나와 작은 기둥 한둘, 큰 기둥 꼭대기에 가끔 해송
	for _, deg in STACKS do
		local th = rad(deg)
		local _, wl = waterline(th)
		if wl then
			local r = wl + rng(70, 130)
			local x, z = cos(th) * r, sin(th) * r
			if not skipped(x, z, -60) and Land.height(x, z) < Land.SEA - 3 then
				local height = rng(22, 40)
				local stack, crown = seaStack(parent, x, z, height, rng, { radius = rng(7, 10) })
				if rng(0, 1) > 0.65 then
					windPine(stack, crown, rng, inwardWind(x, z), rng(7, 10))
				end
				local tangent = Vector3.new(-sin(th), 0, cos(th))
				for k = 1, if rng(0, 1) > 0.75 then 2 else 1 do
					local off = tangent * rng(14, 26) * (if k == 1 then 1 else -1)
						+ Vector3.new(cos(th), 0, sin(th)) * rng(-10, 14)
					local sx, sz = x + off.X, z + off.Z
					if Land.height(sx, sz) < Land.SEA - 3 then
						seaStack(parent, sx, sz, rng(6, 16), rng, { radius = rng(3.5, 6) })
					end
				end
			end
		end
	end
end

-- 짓기 ---------------------------------------------------------------------------------------

function Sea.build(root: Instance, rng: (number, number) -> number)
	local top = folder(root, "바다")
	buildRim(folder(top, "천애"), rng)
	buildCrescent(folder(top, "월아도"), rng)
	buildMist(folder(top, "연파군도"), rng)
	buildWhale(folder(top, "경도"), rng)
	buildCoast(folder(top, "바닷가"), rng)
	return top
end

return Sea
