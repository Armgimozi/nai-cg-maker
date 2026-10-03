-- 백령(白嶺) 산맥과 서쪽 고원: 관운봉과 관운잔도, 삼첨봉·서령·소봉과 등줄기, 송풍령 고갯길, 백금굴, 운곡 마을, 낙조대.
-- World.luau 가 build(root, rng) 를 부른다. 모두 root 아래 "백령" 폴더 하나에 든다.
-- 과업 자리·영맥 둘레 7, 전송진 둘레 9 는 비워 두고(땅에 붙은 판만), 길(관운잔도·송풍령·돌길) 위에는 부품을 놓지 않는다.
-- 높이는 모두 Land.surface 로 잰다. 비탈에서는 축대(돌 바탕)를 깔거나 바닥을 땅에 묻는다.
-- CFrame.lookAt 은 Lune 에서 Z 가 뒤집혀서 쓰지 않는다 (Build.face).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")
local Land = require(Shared.Land)
local Build = require(script.Parent.WorldBuild)
local Kit = require(script.Parent.WorldKit)
local Sites = require(script.Parent.WorldSites)

local Region = {}

local P = Build.P
local block, beam, cyl, ball, wedge = Build.block, Build.beam, Build.cyl, Build.ball, Build.wedge
local deco, face = Build.deco, Build.face
local V3 = Vector3.new
local rad, sin, cos, sqrt, floor, min, max, abs =
	math.rad, math.sin, math.cos, math.sqrt, math.floor, math.min, math.max, math.abs
local PI = math.pi
local M = Enum.Material

-- 빛깔 -----------------------------------------------------------------------------------
local ROCK = Color3.fromRGB(124, 120, 114) -- 화강암 잿빛
local ROCK_DARK = Color3.fromRGB(94, 92, 90)
local ROCK_WARM = Color3.fromRGB(138, 128, 116)
local SNOW = Color3.fromRGB(236, 240, 246)
local ROPE = Color3.fromRGB(176, 150, 106)
local STRAW = Color3.fromRGB(176, 150, 98) -- 초가 이엉
local STRAW_DARK = Color3.fromRGB(140, 116, 76)
local NEOWA = Color3.fromRGB(102, 92, 82) -- 너와 (나무 너새)
local NEOWA_DARK = Color3.fromRGB(74, 66, 60)
local ORE = Color3.fromRGB(212, 218, 226) -- 백금 광석
local SOIL = Color3.fromRGB(116, 92, 66)
local DARK = Color3.fromRGB(18, 16, 16) -- 굴 안 어둠
local WALLSTONE = Color3.fromRGB(150, 142, 128) -- 축대·돌담 돌
local LIMESTONE = Color3.fromRGB(204, 198, 186) -- 종유석
local OAK = { P.leafDeep, P.leaf, P.leafLight }
local MAPLE = { Color3.fromRGB(150, 58, 42), P.maple, Color3.fromRGB(214, 122, 66) }
local GINKGO = { Color3.fromRGB(176, 150, 52), Color3.fromRGB(214, 184, 70), Color3.fromRGB(236, 208, 96) }
local BIRCH = { P.leaf, P.leafLight, P.leafYellow }
local AZALEA = Color3.fromRGB(222, 112, 150) -- 철쭉
local WILDFLOWERS = {
	Color3.fromRGB(236, 220, 120), -- 노란 들꽃
	Color3.fromRGB(196, 150, 220), -- 쑥부쟁이
	Color3.fromRGB(246, 244, 236), -- 구절초
	AZALEA,
}

local function jit(c: Color3, k: number, rng): Color3
	local f = 1 + rng(-k, k)
	return Color3.new(math.clamp(c.R * f, 0, 1), math.clamp(c.G * f, 0, 1), math.clamp(c.B * f, 0, 1))
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

-- 수평 방향 (face 와 같은 돌림): position 에서 target 을 보는 각
local function yawTo(position: Vector3, target: Vector3): number
	return math.atan2(-(target.X - position.X), -(target.Z - position.Z))
end

-- 땅 -------------------------------------------------------------------------------------
local surface = Land.surface
local function at(x: number, z: number, lift: number?): Vector3
	return V3(x, surface(x, z) + (lift or 0), z)
end
-- cf 의 자리를 땅 높이로 내린다 (돌림은 그대로)
local function onGround(c: CFrame): CFrame
	local p = c.Position
	return CFrame.new(p.X, surface(p.X, p.Z), p.Z) * (c - p)
end

-- 둘레 높이 (가운데 + 반지름 r 과 r/2 고리 여덟 방향): 가장 낮은 곳, 가장 높은 곳
local function span(x: number, z: number, r: number): (number, number)
	local low = surface(x, z)
	local high = low
	for i = 0, 7 do
		local a = i * PI / 4
		local c, s = cos(a), sin(a)
		for _, k in { 0.5, 1 } do
			local h = surface(x + c * r * k, z + s * r * k)
			low, high = min(low, h), max(high, h)
		end
	end
	return low, high
end

local function wet(x: number, z: number): boolean
	return Land.water(x, z, Land.height(x, z)) ~= nil
end

-- 땅 기울기 (높이 차 / 거리)
local function slope(x: number, z: number): number
	local h = surface(x, z)
	return max(
		abs(surface(x + 3, z) - h),
		abs(surface(x, z + 3) - h),
		abs(surface(x - 3, z) - h),
		abs(surface(x, z - 3) - h)
	) / 3
end

-- 땅 기울기에 맞춰 눕힌 판의 CFrame (가운데가 땅 위 lift)
local function slopeFrame(x: number, z: number, lift: number): CFrame
	local h = surface(x, z)
	local hx = (surface(x + 2, z) - surface(x - 2, z)) / 4
	local hz = (surface(x, z + 2) - surface(x, z - 2)) / 4
	local n = V3(-hx, 1, -hz).Unit
	local X = (V3(1, 0, 0) - n * n.X).Unit
	return CFrame.fromMatrix(V3(x, h, z) + n * lift, X, n)
end

-- 비워 둘 곳 ----------------------------------------------------------------------------------
-- 전송진 9 (허브의 15x15 바닥돌 귀가 10.6 까지 나와서 11), 과업 자리·영맥 7 (+1)
local KEEP = {}
for _, s in Sites.LIST do
	if s.kind ~= "poi" and not s.sky and s.x < -420 then
		table.insert(KEEP, { x = s.x, z = s.z, r = if s.kind == "wp" then 11 else max(8, s.radius or 0) })
	end
end
-- 낙조대 성대는 허브가 넓게 짓는다
table.insert(KEEP, { x = Land.STARS.west.x, z = Land.STARS.west.z, r = 22 })

local function kept(x: number, z: number, r: number): boolean
	for _, k in KEEP do
		local dx, dz, rr = x - k.x, z - k.z, k.r + r
		if dx * dx + dz * dz < rr * rr then
			return true
		end
	end
	return false
end

local TRAIL = Land.PEAK_TRAIL
local PASS = Land.BENCHES.pass
local ROADS = {}
for _, r in Land.ROADS do
	local p = Land.poly(r)
	if p.x0 < -380 then
		table.insert(ROADS, p)
	end
end
local function trailDist(x: number, z: number): number
	return (Land.spiralAt(x, z, TRAIL))
end
-- 길 위인가 (r: 놓을 것의 반지름)
local function nearPath(x: number, z: number, r: number): boolean
	if trailDist(x, z) < 6.5 + r then
		return true
	end
	if (Land.polyDist(x, z, PASS, 10 + r)) < 8 + r then
		return true
	end
	for _, p in ROADS do
		if (Land.polyDist(x, z, p, 7 + r)) < 5 + r then
			return true
		end
	end
	return false
end

-- 놓은 것의 자리 (나무끼리, 집과 나무가 겹치지 않게): 24 칸 격자
local CELL = 24
local OCC: { [number]: { { number } } } = {}
local function cellKey(ix: number, iz: number): number
	return (ix + 2000) * 4096 + (iz + 2000)
end
local function occupy(x: number, z: number, r: number)
	for ix = floor((x - r) / CELL), floor((x + r) / CELL) do
		for iz = floor((z - r) / CELL), floor((z + r) / CELL) do
			local k = cellKey(ix, iz)
			local list = OCC[k]
			if not list then
				list = {}
				OCC[k] = list
			end
			table.insert(list, { x, z, r })
		end
	end
end
local function occupied(x: number, z: number, r: number): boolean
	local list = OCC[cellKey(floor(x / CELL), floor(z / CELL))]
	if list then
		for _, o in list do
			local dx, dz, rr = x - o[1], z - o[2], o[3] + r
			if dx * dx + dz * dz < rr * rr then
				return true
			end
		end
	end
	return false
end

local function free(x: number, z: number, r: number): boolean
	return not kept(x, z, r) and not nearPath(x, z, r) and not occupied(x, z, r) and not wet(x, z)
end

-- 축대: 비탈에 평평한 바탕. 윗면 top, 밑은 가장 낮은 땅 아래로 묻는다. 방향은 cf 의 돌림
local function terrace(parent: Instance, cf: CFrame, sx: number, sz: number, top: number, low: number, color: Color3?)
	local h = top - low + 2
	local rot = cf - cf.Position
	block(
		parent,
		"Chukdae",
		V3(sx, h, sz),
		CFrame.new(cf.Position.X, top - h / 2, cf.Position.Z) * rot,
		color or WALLSTONE,
		M.Cobblestone
	)
	-- 갑석 (축대 윗단 테)
	return block(
		parent,
		"Gapseok",
		V3(sx + 0.4, 0.5, sz + 0.4),
		CFrame.new(cf.Position.X, top - 0.2, cf.Position.Z) * rot,
		P.graniteDark,
		M.Granite
	)
end

-- 돌담: a→b 를 7 마디로 나눠 땅을 따른다 (마디마다 부품 하나)
local function dryWall(parent: Instance, rng, a: Vector3, b: Vector3, h: number)
	local len = V3(b.X - a.X, 0, b.Z - a.Z).Magnitude
	local n = max(1, math.ceil(len / 7))
	for i = 0, n - 1 do
		local p0 = a:Lerp(b, i / n)
		local p1 = a:Lerp(b, (i + 1) / n)
		local g0, g1 = surface(p0.X, p0.Z), surface(p1.X, p1.Z)
		local gm = surface((p0.X + p1.X) / 2, (p0.Z + p1.Z) / 2)
		local low, high = min(g0, g1, gm), max(g0, g1, gm)
		local hh = high - low + h + 0.6
		local c = V3((p0.X + p1.X) / 2, high + h - hh / 2, (p0.Z + p1.Z) / 2)
		local look = face(c, V3(p1.X, c.Y, p1.Z))
		block(
			parent,
			"Doldam",
			V3(1.5, hh, len / n + 0.4),
			look * CFrame.Angles(0, 0, rng(-0.03, 0.03)),
			jit(WALLSTONE, 0.06, rng),
			M.Cobblestone
		)
	end
end

-- 나무와 돌 -----------------------------------------------------------------------------------

-- 전나무 (가벼운 것): 줄기 + 뿔 둘 (부품 9)
local function lightFir(parent: Instance, rng, base: Vector3, h: number, snow: boolean?)
	local m = model(parent, "전나무")
	local tw = h * 0.07
	block(m, "Trunk", V3(tw, h * 0.4 + 0.8, tw), CFrame.new(base + V3(0, h * 0.2 - 0.4, 0)), P.bark, M.Wood)
	local yaw = rng(0, 1.5)
	Build.pyramid(m, "Needles", base + V3(0, h * 0.14, 0), h * 0.52, h * 0.5, yaw, jit(P.pine, 0.06, rng), nil, true)
	Build.pyramid(
		m,
		"Needles",
		base + V3(0, h * 0.46, 0),
		h * 0.34,
		h * 0.54,
		yaw + 0.5,
		if snow then SNOW else jit(P.pineLight, 0.06, rng),
		nil,
		true
	)
	return m
end

-- 먼 비탈 전나무: 줄기 + 가는 뿔 하나 (부품 5)
local function fir5(parent: Instance, rng, base: Vector3, h: number)
	local m = model(parent, "전나무")
	local tw = h * 0.07
	block(m, "Trunk", V3(tw, h * 0.25 + 0.8, tw), CFrame.new(base + V3(0, h * 0.125 - 0.4, 0)), P.bark, M.Wood)
	Build.pyramid(
		m,
		"Needles",
		base + V3(0, h * 0.12, 0),
		h * 0.4,
		h * 0.88,
		rng(0, 1.5),
		jit(if rng(0, 1) > 0.5 then P.pine else P.pineLight, 0.07, rng),
		nil,
		true
	)
	return m
end

-- 바람에 누운 소나무: 줄기가 바람 쪽(wind, 수평 단위)으로 굽고 잎판이 바람 쪽으로 흐른다 (부품 11)
local function windPine(parent: Instance, rng, base: Vector3, h: number, wind: Vector3)
	local m = model(parent, "바람소나무")
	local tw = h * 0.1
	local side = V3(-wind.Z, 0, wind.X)
	local dirs = {
		(Vector3.yAxis + wind * 0.25 + side * rng(-0.1, 0.1)).Unit,
		(Vector3.yAxis + wind * 0.85 + side * rng(-0.2, 0.2)).Unit,
		(Vector3.yAxis * 0.45 + wind).Unit,
	}
	local p = base - V3(0, 0.8, 0)
	local pts = { p }
	for i, d in dirs do
		local len = h / 3 * (if i == 1 then 1.2 else 1)
		local q = p + d * len
		local w = tw * (1 - 0.22 * (i - 1))
		beam(m, "Trunk", p, q + d * (w * 0.3), w, w, if i == 1 then P.bark else P.barkPine, M.Wood)
		p = q
		table.insert(pts, p)
	end
	local function pad(c: Vector3, s: number)
		local cf = face(c, c + wind) * CFrame.Angles(0, rng(-0.2, 0.2), rng(-0.08, 0.08))
		deco(block(m, "Leaves", V3(s * 0.8, s * 0.22, s * 1.4), cf, jit(P.pine, 0.06, rng), M.LeafyGrass))
		deco(
			block(
				m,
				"Leaves",
				V3(s * 0.6, s * 0.2, s),
				cf * CFrame.new(0, s * 0.15, -s * 0.12),
				jit(P.pineLight, 0.06, rng),
				M.LeafyGrass
			)
		)
	end
	pad(p + wind * h * 0.12 + V3(0, 0.3, 0), h * 0.5)
	local b1 = pts[2]:Lerp(pts[3], 0.5)
	local t1 = b1 + wind * h * 0.34 + side * rng(-0.18, 0.18) * h + V3(0, h * 0.04, 0)
	beam(m, "Branch", b1, t1, tw * 0.45, tw * 0.45, P.barkPine, M.Wood)
	pad(t1 + V3(0, 0.25, 0), h * 0.36)
	local b2 = pts[3]:Lerp(pts[4], 0.35)
	local t2 = b2 + wind * h * 0.16 - side * rng(0.12, 0.3) * h + V3(0, h * 0.08, 0)
	beam(m, "Branch", b2, t2, tw * 0.38, tw * 0.38, P.barkPine, M.Wood)
	pad(t2 + V3(0, 0.25, 0), h * 0.3)
	return m
end

-- 길가 소나무 (가벼운 것): 굽은 붉은 줄기 둘, 가지 하나, 구름 잎판 셋 (부품 6)
local function lightPine(parent: Instance, rng, base: Vector3, h: number)
	local m = model(parent, "소나무")
	local tw = h * 0.085
	local lean = V3(rng(-0.35, 0.35), 0, rng(-0.35, 0.35))
	local mid = base + (Vector3.yAxis + lean).Unit * h * 0.55
	local top = mid + (Vector3.yAxis + lean * -0.6 + V3(rng(-0.2, 0.2), 0, rng(-0.2, 0.2))).Unit * h * 0.42
	beam(m, "Trunk", base - V3(0, 0.6, 0), mid + V3(0, tw * 0.3, 0), tw, tw, P.barkPine, M.Wood)
	beam(m, "Trunk", mid, top + V3(0, tw * 0.2, 0), tw * 0.7, tw * 0.7, P.barkPine, M.Wood)
	local a = rng(0, 2 * PI)
	local reach = h * 0.26
	local tip = mid + V3(cos(a) * reach, h * 0.08, sin(a) * reach)
	beam(m, "Branch", mid, tip, tw * 0.42, tw * 0.42, P.barkPine, M.Wood)
	local function pad(c: Vector3, s: number, color: Color3)
		local cf = CFrame.new(c) * CFrame.Angles(rng(-0.1, 0.1), rng(0, PI), rng(-0.1, 0.1))
		deco(block(m, "Leaves", V3(s, s * 0.26, s * 0.8), cf, jit(color, 0.06, rng), M.LeafyGrass))
	end
	pad(top + V3(0, 0.4, 0), h * 0.44, P.pineLight)
	pad(tip + V3(0, 0.3, 0), h * 0.34, P.pine)
	pad(mid:Lerp(top, 0.45) + V3(-cos(a), 0, -sin(a)) * h * 0.16, h * 0.3, P.pine)
	return m
end

-- 바위 벼랑(크래그): 비스듬히 박은 큰 돌 둘셋 + 깎인 머리. 눈 덮인 머리는 snowy
local function crag(parent: Instance, rng, x: number, z: number, s: number, snowy: boolean?)
	local low, high = span(x, z, s * 0.4)
	local m = model(parent, "바위벼랑")
	local yaw = rng(0, PI)
	local n = if s > 12 then 3 else 2
	-- 가파른 비탈에서는 기둥처럼 솟지 않게, 아래로만 묻는다
	local rise = min(high - low, s * 0.6)
	for i = 1, n do
		local k = if i == 1 then 1 else rng(0.45, 0.75)
		local w, d = s * rng(0.55, 0.8) * k, s * rng(0.45, 0.65) * k
		local hgt = s * rng(0.55, 0.95) * k + rise
		local ox, oz = 0, 0
		if i > 1 then
			local a = rng(0, 2 * PI)
			ox, oz = cos(a) * s * 0.34, sin(a) * s * 0.34
		end
		local g = surface(x + ox, z + oz)
		local bottom = min(g, low + rise) - 1.6
		local cf = CFrame.new(x + ox, bottom + hgt / 2, z + oz)
			* CFrame.Angles(rng(-0.16, 0.16), yaw + rng(-0.5, 0.5), rng(-0.16, 0.16))
		local col = jit(if i == 2 then ROCK_DARK elseif i == 3 then ROCK_WARM else ROCK, 0.06, rng)
		block(m, "Bawi", V3(w, hgt, d), cf, col, M.Slate)
		if i == 1 then
			-- 깎인 머리: 윗면에 기울인 쐐기
			local cap = cf
				* CFrame.new(0, hgt / 2 + d * 0.2, 0)
				* CFrame.Angles(0, if rng(0, 1) > 0.5 then 0 else PI, 0)
			wedge(m, "Meori", V3(w * 0.95, d * 0.4, d * 0.98), cap, col, M.Slate)
			if snowy then
				deco(
					block(
						m,
						"Nun",
						V3(w * 0.8, 0.45, d * 0.55),
						cf * CFrame.new(0, hgt / 2 + 0.1, d * 0.2),
						SNOW,
						M.Snow
					)
				)
			end
		end
	end
	return m
end

-- 바위 무더기 (Build.rocks 를 가운데 땅에 반쯤 묻는다)
local function boulder(parent: Instance, rng, x: number, z: number, s: number, color: Color3?)
	local g = surface(x, z) - s * 0.12
	return Build.rocks(
		parent,
		V3(x, g, z),
		s,
		rng,
		{ count = if s > 5 then 2 else 1, color = color or ROCK, moss = s > 3 }
	)
end

-- 비탈에 눈 판 (땅 기울기에 맞춰 눕힌다)
local function snowPatch(parent: Instance, rng, x: number, z: number, s: number)
	local cf = slopeFrame(x, z, 0.05) * CFrame.Angles(0, rng(0, PI), 0)
	return deco(block(parent, "Nun", V3(s, 0.7, s * rng(0.45, 0.75)), cf, SNOW, M.Snow))
end

-- 풀포기·들꽃: 땅에 붙은 작은 덩이 (부품 1~2)
local function tuft(parent: Instance, rng, x: number, z: number, flower: Color3?)
	local g = surface(x, z)
	local s = rng(1.2, 2.2)
	local cf = CFrame.new(x, g + s * 0.12, z) * CFrame.Angles(rng(-0.2, 0.2), rng(0, PI), rng(-0.2, 0.2))
	local p = deco(block(parent, "Pul", V3(s, s * 0.5, s * rng(0.7, 1)), cf, jit(P.leafLight, 0.1, rng), M.LeafyGrass))
	p.CastShadow = false
	if flower then
		local fcf = CFrame.new(x + rng(-0.3, 0.3), g + s * 0.38, z + rng(-0.3, 0.3)) * CFrame.Angles(0, rng(0, PI), 0)
		deco(block(parent, "Kkot", V3(s * 0.7, 0.35, s * 0.6), fcf, jit(flower, 0.06, rng), M.SmoothPlastic)).CastShadow =
			false
	end
end

-- 돌탑(케른): 납작한 돌을 줄여 가며 쌓는다
local function cairn(parent: Instance, rng, x: number, z: number, count: number?, size: number?)
	local m = model(parent, "돌탑")
	local low = span(x, z, 1.6)
	local y = low - 0.3
	local s = size or 3.2
	for _ = 1, floor(count or 5) do
		local t = s * rng(0.45, 0.62)
		local cf = CFrame.new(x + rng(-0.15, 0.15), y + t / 2, z + rng(-0.15, 0.15))
			* CFrame.Angles(rng(-0.06, 0.06), rng(0, PI), rng(-0.06, 0.06))
		block(m, "Dol", V3(s, t, s * rng(0.8, 1)), cf, jit(ROCK_WARM, 0.08, rng), M.Slate)
		y += t * 0.92
		s *= 0.84
	end
	return m
end

-- 초가·너와 지붕으로 바꾼다 (기와 지붕을 지은 뒤 빛깔·재질만, 망와와 양성은 뺀다)
local function reroof(house: Instance, kind: string)
	local roof = house:FindFirstChild("지붕")
	if not roof then
		return
	end
	for _, p in roof:GetChildren() do
		if p:IsA("BasePart") then
			if p.Name == "Mangwa" or p.Name == "Yangseong" then
				p:Destroy()
			elseif p.Name == "Giwa" then
				p.Color = if kind == "choga" then STRAW else NEOWA
				p.Material = if kind == "choga" then M.Grass else M.WoodPlanks
			elseif p.Name == "Maru" then
				p.Color = if kind == "choga" then STRAW_DARK else NEOWA_DARK
				p.Material = if kind == "choga" then M.Fabric else M.Wood
			elseif p.Name == "Hapgak" and kind == "neowa" then
				p.Color = P.woodDark
				p.Material = M.WoodPlanks
			end
		end
	end
end

-- 집 한 채: x, z 에서 toward 를 본다. 비탈이면 축대와 돌계단 (집터 모델 안에 같이 둔다).
-- 돌려주는 값: 집터 모델, 바닥 높이, cf
local function houseAt(parent: Instance, x: number, z: number, toward: Vector3, opts, roofKind: string?, name: string?)
	local bay = opts.bay or 5
	local W, D = opts.bays[1] * bay + 4.4, opts.bays[2] * bay + 4.4
	local r = sqrt(W * W + D * D) / 2
	local low, high = span(x, z, r)
	local look = face(V3(x, 0, z), toward)
	local rot = look - look.Position
	local base = CFrame.new(x, 0, z) * rot
	local site = model(parent, name or "집")
	local top
	if high - low > 1.2 then
		top = high + 0.2
		terrace(site, base, W + 3, D + 5, top, low)
		-- 축대 앞 돌계단 (계단 발치 땅까지)
		local foot = (base * CFrame.new(0, 0, -(D + 5) / 2 - 1.5)).Position
		local rise = top - surface(foot.X, foot.Z)
		if rise > 1.4 then
			local n = math.ceil(rise / 0.8)
			for i = 1, n do
				local y1 = top - i * (rise / n)
				local dz = (D + 5) / 2 + i * 1.1 - 0.5
				local h = y1 - (top - rise) + 1.5
				block(
					site,
					"Gyedan",
					V3(4.2, h, 1.2),
					base * CFrame.new(0, y1 - h / 2 + 0.01, -dz),
					WALLSTONE:Lerp(ROCK_DARK, 0.2),
					M.Cobblestone
				)
			end
		end
	else
		top = (low + high) / 2 + 0.3
	end
	local cf = CFrame.new(x, top, z) * rot
	local m = Build.house(site, cf, opts)
	if roofKind then
		reroof(m, roofKind)
	end
	-- 안에서 안 보이는 마루 바닥은 뺀다
	local floorPart = m:FindFirstChild("Floor")
	if floorPart and not opts.open then
		floorPart:Destroy()
	end
	occupy(x, z, r + 1)
	return site, top, cf
end

-- 장작더미: 통나무 쌓음 (부품 3)
local function woodpile(parent: Instance, cf: CFrame)
	local m = model(parent, "장작더미")
	block(m, "Jangjak", V3(5, 2.4, 1.8), cf * CFrame.new(0, 1.0, 0), Color3.fromRGB(138, 104, 70), M.Wood)
	block(m, "Jangjak", V3(4.2, 1.2, 1.7), cf * CFrame.new(0.2, 2.6, 0), Color3.fromRGB(124, 92, 62), M.Wood)
	block(
		m,
		"Deopgae",
		V3(5.6, 0.25, 2.4),
		cf * CFrame.new(0, 3.35, 0) * CFrame.Angles(rad(8), 0, 0),
		NEOWA,
		M.WoodPlanks
	)
	return m
end

-- 곶감·나물 말리는 덕: 기둥 둘, 가로대, 늘어진 줄 (부품 7)
local function dryingRack(parent: Instance, rng, cf: CFrame, color: Color3)
	local m = model(parent, "덕")
	local w = 6
	for _, s in { -1, 1 } do
		beam(
			m,
			"Gidung",
			(cf * CFrame.new(s * w / 2, -0.6, 0)).Position,
			(cf * CFrame.new(s * w / 2, 5.4, 0)).Position,
			0.4,
			0.4,
			P.woodDark,
			M.Wood
		)
	end
	beam(
		m,
		"Garodae",
		(cf * CFrame.new(-w / 2 - 0.3, 5, 0)).Position,
		(cf * CFrame.new(w / 2 + 0.3, 5, 0)).Position,
		0.3,
		0.3,
		P.wood,
		M.Wood
	)
	for i = 1, 4 do
		local x = -w / 2 + i * w / 5
		local len = rng(2.2, 3.2)
		deco(
			block(
				m,
				"Jul",
				V3(0.42, len, 0.42),
				cf * CFrame.new(x, 5 - len / 2 - 0.1, 0),
				jit(color, 0.08, rng),
				M.SmoothPlastic
			)
		).CastShadow =
			false
	end
	return m
end

-- 평상: 다리 둘에 널판 (부품 3)
local function bench(parent: Instance, cf: CFrame, w: number, d: number)
	local m = model(parent, "평상")
	block(m, "Panja", V3(w, 0.35, d), cf * CFrame.new(0, 1.5, 0), Color3.fromRGB(150, 112, 74), M.WoodPlanks)
	for _, s in { -1, 1 } do
		block(m, "Dari", V3(0.4, 1.8, d - 0.6), cf * CFrame.new(s * (w / 2 - 0.5), 0.55, 0), P.woodDark, M.Wood)
	end
	return m
end

-- 디딤돌 (땅에 붙은 판)
local function steppingStone(parent: Instance, rng, x: number, z: number, s: number?)
	local size = s or rng(1.6, 2.4)
	local cf = slopeFrame(x, z, 0.08) * CFrame.Angles(0, rng(0, PI), 0)
	local p = block(
		parent,
		"Didimdol",
		V3(size, 0.5, size * rng(0.7, 0.95)),
		cf,
		jit(Color3.fromRGB(160, 154, 144), 0.06, rng),
		M.Slate
	)
	p.CastShadow = false
	return p
end

-- 밧줄 (a 에서 b 까지)
local function rope(parent: Instance, a: Vector3, b: Vector3)
	local p = beam(parent, "Batjul", a, b, 0.16, 0.16, ROPE, M.Fabric)
	p.CastShadow = false
	return p
end

------------------------------------------------------------------------------------------
-- 관운잔도 (꼭대기와 산숲도 이 틀을 쓴다)
------------------------------------------------------------------------------------------
local PEAK = Land.PEAK
local TP = Land.spiralPoints(TRAIL, 1) -- 1도마다 { x, y, z }

-- k 도 자리의 길 가운데, 길에 수직인 바깥(봉우리 반대) 쪽 단위, 나아가는 쪽 단위
local function trailFrame(k: number): (Vector3, Vector3, Vector3)
	local i = math.clamp(floor(k), 0, #TP - 2)
	local f = k - i
	local a, b = TP[i + 1], TP[i + 2]
	local p = V3(a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f)
	local t = V3(b[1] - a[1], 0, b[3] - a[3]).Unit
	local o = V3(p.X - TRAIL.cx, 0, p.Z - TRAIL.cz)
	local n = V3(t.Z, 0, -t.X)
	if n:Dot(o) < 0 then
		n = -n
	end
	return p, n, t
end

-- 쉼터 축대: 길 바깥(낭떠러지 쪽)으로 내민 돌 바탕. 윗면이 길 높이. 돌려주는 값: 윗면 가운데 cf (앞 -Z 가 길을 본다)
local function trailTerrace(m: Instance, k: number, depth: number, len: number): CFrame
	local p, n = trailFrame(k)
	local c = p + n * (5.6 + depth / 2)
	local look = face(V3(c.X, 0, c.Z), V3(p.X, 0, p.Z))
	local low = span(c.X, c.Z, max(depth, len) / 2)
	local top = p.Y + 0.15
	local rot = look - look.Position
	local h = top - low + 3
	block(m, "Chukdae", V3(len, h, depth), CFrame.new(c.X, top - h / 2, c.Z) * rot, ROCK, M.Cobblestone)
	block(
		m,
		"Gapseok",
		V3(len + 0.4, 0.5, depth + 0.4),
		CFrame.new(c.X, top - 0.2, c.Z) * rot,
		P.graniteDark,
		M.Granite
	)
	occupy(c.X, c.Z, max(depth, len) / 2 + 1)
	return CFrame.new(c.X, top, c.Z) * rot
end

-- 축대 바깥 가장자리 돌난간 (뒤와 옆. 옆은 길 쪽 3 을 비운다)
local function parapet(m: Instance, cf: CFrame, len: number, depth: number)
	block(m, "Nangan", V3(len, 1.6, 0.8), cf * CFrame.new(0, 0.8, depth / 2 - 0.5), ROCK_DARK, M.Slate)
	for _, s in { -1, 1 } do
		block(m, "Nangan", V3(0.8, 1.6, depth - 3), cf * CFrame.new(s * (len / 2 - 0.4), 0.8, 1.5), ROCK_DARK, M.Slate)
	end
end

local function buildTrail(root: Instance, rng)
	local f = folder(root, "관운잔도")
	local n = TRAIL.n

	-- 들머리: 평지에서 길 첫머리(산자락 턱 위)까지 돌계단, 계단 밑에 일주문
	do
		local stair = model(f, "들머리 돌계단")
		local p0, _, t0 = trailFrame(0)
		local u = -t0 -- 계단은 길 반대쪽으로 내려간다
		local run, rise = 1.25, 0.75
		local look = face(V3(p0.X, 0, p0.Z), V3(p0.X, 0, p0.Z) + u) -- 앞이 아래쪽
		local rot = look - look.Position
		local right = rot.RightVector
		local y = p0.Y
		local s = 0.6
		local count = 0
		while count < 30 do
			local c = V3(p0.X, 0, p0.Z) + u * (s + run / 2)
			local g = surface(c.X, c.Z)
			local ytop = y - rise
			if ytop < g + 0.3 then
				break
			end
			local lowG = min(
				g,
				surface(c.X + right.X * 3.5, c.Z + right.Z * 3.5),
				surface(c.X - right.X * 3.5, c.Z - right.Z * 3.5)
			)
			local h = ytop - lowG + 1.2
			local color = if count % 2 == 0 then P.granite else P.graniteDark:Lerp(P.granite, 0.5)
			block(stair, "Gyedan", V3(7, h, run + 0.06), CFrame.new(c.X, ytop - h / 2, c.Z) * rot, color, M.Granite)
			y = ytop
			s += run
			count += 1
		end
		-- 계단 양옆 돌 난간 (기울인 갓돌)
		local a0 = V3(p0.X, p0.Y, p0.Z) + u * 0.6
		local a1 = V3(p0.X, y, p0.Z) + u * s
		for _, side in { -1, 1 } do
			local off = right * side * 4
			beam(stair, "Yeopdam", a0 + off + V3(0, 0.6, 0), a1 + off + V3(0, 0.6, 0), 1, 1.6, P.graniteDark, M.Granite)
		end
		-- 일주문: 계단 발치 앞
		local gate = model(f, "관운잔도 일주문")
		local gc = V3(p0.X, 0, p0.Z) + u * (s + 4.5)
		local gy = surface(gc.X, gc.Z)
		for _, sd in { -1, 1 } do
			local q = gc + right * sd * 6
			local g = surface(q.X, q.Z)
			if g < gy - 0.4 then
				block(
					gate,
					"Juchu",
					V3(3, gy - g + 1, 3),
					CFrame.new(q.X, (gy + g) / 2 - 0.5, q.Z) * rot,
					P.graniteDark,
					M.Granite
				)
			end
		end
		local ground = V3(gc.X, gy, gc.Z)
		local _, board = Build.iljumun(gate, ground, ground + u * 10, 12)
		Kit.engrave(board, "관운잔도", "Front,Back")
		-- 문 앞 판석 마당, 석등 둘
		block(
			gate,
			"Panseok",
			V3(14, 0.6, 10),
			CFrame.new(ground + u * 6 + V3(0, 0.05, 0)) * rot,
			P.granite:Lerp(ROCK, 0.4),
			M.Slate
		)
		for _, sd in { -1, 1 } do
			local q = gc + u * 7 + right * sd * 8.5
			Build.stoneLantern(f, at(q.X, q.Z))
		end
		occupy(gc.X, gc.Z, 10)
		local mid = (a0 + a1) / 2
		occupy(mid.X, mid.Z, s / 2 + 4)
	end

	-- 바깥(낭떠러지) 쪽 줄 난간: 말뚝 15 마다, 낭떠러지가 깊을 때만. 쉼터 앞은 돌난간이 대신한다
	local terraces = { { 100, 15, 14 }, { 206, 12, 12 } } -- { k, 깊이, 길이 }
	local function nearTerrace(k: number): boolean
		for _, t in terraces do
			if abs(k - t[1]) < 5 then
				return true
			end
		end
		return abs(k - 156) < 3 -- 널마루
	end
	local railing = model(f, "줄난간")
	local last: Vector3? = nil
	local acc = 0
	local prev = trailFrame(0)
	for k4 = 30, n * 4 do
		local k = k4 / 4
		local p, o = trailFrame(k)
		acc += (p - prev).Magnitude
		prev = p
		if acc >= 15 then
			acc = 0
			local q = p + o * 7.2
			local g = Land.height(q.X, q.Z)
			local drop = p.Y - Land.height(p.X + o.X * 16, p.Z + o.Z * 16)
			if drop > 7 and not nearTerrace(k) and not kept(q.X, q.Z, 1) and k < n - 2 then
				local topP = V3(q.X, g + 3.2, q.Z)
				beam(railing, "Malttuk", V3(q.X, g - 1.2, q.Z), topP + V3(0, 0.2, 0), 0.55, 0.55, P.woodDark, M.Wood)
				if last and (last - topP).Magnitude < 20 then
					rope(railing, last - V3(0, 0.3, 0), topP - V3(0, 0.3, 0))
				end
				last = topP
			else
				last = nil
			end
		end
	end

	-- 쉼터 1: 남서 굽이, 사모 정자
	do
		local m = model(f, "쉼터 정자")
		local t = terraces[1]
		local cf = trailTerrace(m, t[1], t[2], t[3])
		parapet(m, cf, t[3], t[2])
		Build.pavilion(m, cf * CFrame.new(0, 0, 1.3), { detail = 0, bands = 2, bay = 7, pillarH = 6.5, plinth = 1.2 })
		local p, o = trailFrame(t[1] + 4)
		local q = p - o * 7.4
		Build.stoneLantern(f, at(q.X, q.Z))
	end
	-- 쉼터 2: 북서 굽이, 너와 지붕 비가림 + 평상
	do
		local m = model(f, "비가림")
		local t = terraces[2]
		local cf = trailTerrace(m, t[1], t[2], t[3])
		parapet(m, cf, t[3], t[2])
		local hw, hd = 4.2, 3.2
		for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
			block(m, "Gidung", V3(0.8, 6.6, 0.8), cf * CFrame.new(c[1] * hw, 3.3, c[2] * hd + 1.2), P.wood, M.Wood)
		end
		for _, sz in { -1, 1 } do
			block(m, "Dori", V3(hw * 2 + 1.2, 0.7, 0.7), cf * CFrame.new(0, 6.6, sz * hd + 1.2), P.woodDark, M.Wood)
		end
		Build.roof(
			m,
			cf * CFrame.new(0, 6.95, 1.2),
			{ ex = hw + 2.2, ez = hd + 2, eave = 2, bands = 2, kind = "gable", pitchLow = 22, pitchHigh = 38, t = 0.5 }
		)
		reroof(m, "neowa")
		bench(m, cf * CFrame.new(0, 0, 2.2), 6.4, 3)
	end

	-- 잔도 널마루: 서쪽 벼랑 굽이에서 길 밖으로 내민 나무 마루 (버팀목으로 받친다)
	do
		local p, o = trailFrame(156)
		local c = p + o * 8.6
		local look = face(V3(c.X, 0, c.Z), V3(p.X, 0, p.Z))
		local cf = CFrame.new(c.X, p.Y - 0.05, c.Z) * (look - look.Position)
		local m = model(f, "널마루")
		for i = -3, 3 do
			block(
				m,
				"Neol",
				V3(1.35, 0.35, 6),
				cf * CFrame.new(i * 1.4, 0, 0),
				Color3.fromRGB(132, 98, 66):Lerp(P.woodDark, (i % 2) * 0.25),
				M.WoodPlanks
			)
		end
		for _, s in { -1, 1 } do
			local under = cf * CFrame.new(s * 4.2, -0.4, 2.6)
			local foot = cf * CFrame.new(s * 4.2, 0, -2.4)
			local g = Land.height(foot.Position.X, foot.Position.Z)
			beam(
				m,
				"Beotimmok",
				under.Position,
				V3(foot.Position.X, g - 0.8, foot.Position.Z),
				0.6,
				0.6,
				P.woodDark,
				M.Wood
			)
			beam(
				m,
				"Gidung",
				(cf * CFrame.new(s * 4.6, -0.2, 2.7)).Position,
				(cf * CFrame.new(s * 4.6, 3.4, 2.7)).Position,
				0.45,
				0.45,
				P.woodDark,
				M.Wood
			)
		end
		beam(
			m,
			"Nangan",
			(cf * CFrame.new(-4.6, 3.2, 2.7)).Position,
			(cf * CFrame.new(4.6, 3.2, 2.7)).Position,
			0.3,
			0.3,
			P.wood,
			M.Wood
		)
		beam(
			m,
			"Nangan",
			(cf * CFrame.new(-4.6, 1.6, 2.7)).Position,
			(cf * CFrame.new(4.6, 1.6, 2.7)).Position,
			0.25,
			0.25,
			P.wood,
			M.Wood
		)
		occupy(c.X, c.Z, 6)
	end

	-- 산 쪽(안쪽) 석등
	for _, k in { 52, 250 } do
		local p, o = trailFrame(k)
		local q = p - o * 7.4
		if not kept(q.X, q.Z, 2) then
			Build.stoneLantern(f, at(q.X, q.Z))
			occupy(q.X, q.Z, 2)
		end
	end
	-- 들머리 쪽 산 쪽 축대 (깎은 비탈을 돌로 받친다)
	local wall = model(f, "산쪽 축대")
	for k = 4, 40, 3.4 do
		local p, o = trailFrame(k)
		local q = p - o * 7.8
		local g = surface(q.X, q.Z)
		if g > p.Y + 1 then
			local look = face(V3(q.X, 0, q.Z), V3(q.X, 0, q.Z) + o)
			local h = g - p.Y + 1.8
			block(
				wall,
				"Seokchuk",
				V3(9.4, h, 2.2),
				CFrame.new(q.X, p.Y - 0.6 + h / 2, q.Z) * (look - look.Position),
				jit(WALLSTONE, 0.05, rng),
				M.Cobblestone
			)
		end
	end
end

------------------------------------------------------------------------------------------
-- 관운봉 꼭대기
------------------------------------------------------------------------------------------
local function buildSummit(root: Instance, rng)
	local f = folder(root, "관운봉 꼭대기")
	local cx, cz = PEAK.x, PEAK.z
	local center = V3(cx, 0, cz)
	local function polar(a: number, d: number): (number, number)
		return cx + cos(rad(a)) * d, cz + sin(rad(a)) * d
	end
	-- 관운정: 북서 벼랑 끝의 구름 보는 정자. 앞(계단)이 꼭대기 가운데를 본다
	do
		local px, pz = polar(222, 25)
		local look = face(V3(px, 0, pz), center)
		local rot = look - look.Position
		local low, high = span(px, pz, 9)
		local base = high + 0.6
		local m = model(f, "관운정")
		terrace(m, CFrame.new(px, 0, pz) * rot, 19, 19, base, low, ROCK)
		Build.pavilion(
			m,
			CFrame.new(px, base, pz) * rot,
			{ detail = 1, bands = 3, bay = 10, pillarH = 8, plinth = 1.8, name = "관운정" }
		)
		-- 바깥 벼랑 쪽 낮은 돌난간 (뒤와 옆)
		local cf = CFrame.new(px, base, pz) * rot
		for _, s in { -1, 1 } do
			block(m, "Nangan", V3(0.9, 1.8, 12), cf * CFrame.new(s * 9.1, 0.9, 3), ROCK_DARK, M.Slate)
		end
		block(m, "Nangan", V3(19, 1.8, 0.9), cf * CFrame.new(0, 0.9, 9.1), ROCK_DARK, M.Slate)
		-- 오르는 돌계단 (축대가 땅보다 높을 때)
		local front = (cf * CFrame.new(0, 0, -11)).Position
		local fy = surface(front.X, front.Z)
		local rise = base - fy
		if rise > 0.8 then
			local steps = math.ceil(rise / 0.75)
			for i = 1, steps do
				local y1 = base - i * rise / steps
				local h = y1 - fy + 1.2
				block(
					m,
					"Gyedan",
					V3(5, h, 1.1),
					cf * CFrame.new(0, y1 - base - h / 2, -9.6 - i * 1.05),
					P.granite,
					M.Granite
				)
			end
		end
		occupy(px, pz, 13)
	end
	-- 산신 돌감실: 서쪽, 가운데를 본다
	do
		local px, pz = polar(176, 30)
		local lf = face(V3(px, 0, pz), center)
		local rot = lf - lf.Position
		local look = CFrame.new(px, surface(px, pz), pz) * rot
		local m = model(f, "산신단")
		block(m, "Gidan", V3(7, 1.2, 5), look * CFrame.new(0, 0.2, 0), ROCK, M.Slate)
		for _, s in { -1, 1 } do
			block(m, "Yeopdol", V3(0.8, 4.2, 3.4), look * CFrame.new(s * 2.2, 2.9, 0.4), ROCK_WARM, M.Slate)
		end
		block(m, "Dwitdol", V3(5.2, 4.2, 0.8), look * CFrame.new(0, 2.9, 2.0), ROCK_WARM, M.Slate)
		block(m, "Gaebdol", V3(6.4, 0.8, 4.6), look * CFrame.new(0, 5.4, 0.3), ROCK_DARK, M.Slate)
		Build.pyramid(
			m,
			"Jibung",
			(look * CFrame.new(0, 5.8, 0.3)).Position,
			5.6,
			1.4,
			yawTo(V3(px, 0, pz), center),
			ROCK_DARK,
			M.Slate
		)
		-- 감실 안 작은 석상과 앞의 향로
		block(m, "Seoksang", V3(1.2, 1.8, 1), look * CFrame.new(0, 1.7, 0.9), Color3.fromRGB(170, 164, 152), M.Granite)
		ball(m, "Meori", (look * CFrame.new(0, 2.95, 0.9)).Position, 0.9, Color3.fromRGB(170, 164, 152), M.Granite)
		cyl(
			m,
			"Hyangno",
			(look * CFrame.new(0, 0.8, -1.5)).Position,
			(look * CFrame.new(0, 1.7, -1.5)).Position,
			1.1,
			Color3.fromRGB(90, 80, 60),
			M.Metal
		)
		occupy(px, pz, 5)
		-- 감실 양옆 깃대와 그 사이 오색 천 줄
		local colors = { P.plaster, P.samcheong, P.juhong, P.hwang, P.noerok }
		local poles = {}
		for i, off in { -5.5, 5.5 } do
			local g = look * CFrame.new(off, 0, 1)
			local foot = V3(g.Position.X, surface(g.Position.X, g.Position.Z), g.Position.Z)
			Build.banner(f, foot, foot - look.LookVector * 4, colors[i + 1], 12)
			table.insert(poles, foot + V3(0, 11.4, 0))
		end
		local a, b = poles[1], poles[2]
		rope(f, a, b)
		for i = 1, 5 do
			local p = a:Lerp(b, i / 6) - V3(0, 0.5 + 0.6 * sin(PI * i / 6), 0)
			deco(block(f, "Cheon", V3(0.9, 1.2, 0.08), CFrame.new(p) * rot, colors[i], M.Fabric)).CastShadow = false
		end
	end
	-- 이름 비석: 잔도가 올라오는 곳
	do
		local px, pz = polar(316, 31)
		local tx, tz = polar(326, 50)
		Kit.stele(f, at(px, pz, 0.6), "관운봉", V3(tx, 0, tz))
		occupy(px, pz, 3)
	end
	-- 큰 돌탑 (멀리서 보이는 꼭대기 표) 과 작은 돌탑
	do
		local px, pz = polar(272, 25)
		cairn(f, rng, px, pz, 8, 4.6)
		occupy(px, pz, 3)
	end
	for _, a in { 140, 100, 22 } do
		local px, pz = polar(a + rng(-5, 5), rng(31, 34))
		if not kept(px, pz, 2) and not occupied(px, pz, 2) then
			cairn(f, rng, px, pz, rng(4, 6))
		end
	end
	-- 석등: 관운정 앞
	do
		local px, pz = polar(222, 12)
		if not kept(px, pz, 2) then
			Build.stoneLantern(f, at(px, pz))
		end
	end
	-- 너럭바위 가장자리: 낮고 넓은 바위 (반쯤 묻는다)
	for i = 0, 11 do
		local a = i * 30 + rng(-9, 9)
		if abs(((a - 326 + 180) % 360) - 180) > 18 then
			local d = rng(39, 44)
			local px, pz = polar(a, d)
			if free(px, pz, 3) then
				local s = rng(5, 9)
				local g = surface(px, pz)
				local m = model(f, "바위")
				local cf = CFrame.new(px, g + s * 0.08, pz) * CFrame.Angles(rng(-0.2, 0.2), rng(0, PI), rng(-0.2, 0.2))
				block(m, "Bawi", V3(s, s * 0.5, s * 0.75), cf, jit(ROCK, 0.06, rng), M.Slate)
				deco(block(m, "Nun", V3(s * 0.7, 0.4, s * 0.5), cf * CFrame.new(0, s * 0.25 + 0.1, 0), SNOW, M.Snow))
				occupy(px, pz, s * 0.5)
			end
		end
	end
	for _ = 1, 6 do
		local px, pz = polar(rng(0, 360), rng(46, 70))
		if free(px, pz, 2) then
			snowPatch(f, rng, px, pz, rng(6, 12))
		end
	end
end

------------------------------------------------------------------------------------------
-- 산의 나무·바위·눈 (관운봉, 다른 봉우리, 등줄기)
------------------------------------------------------------------------------------------
local WIND = V3(1, 0, 0.15).Unit -- 서쪽 바다에서 부는 바람: 나무가 동쪽으로 눕는다

local function buildSlopes(root: Instance, rng)
	local f = folder(root, "산숲")
	-- 잔도 곁 나무: 길에서 12~30 떨어진 곳, 번갈아 (아래는 활엽·소나무 섞인 숲, 위로 갈수록 전나무, 꼭대기 밑은 바람 소나무)
	local side = 1
	local k = 4
	while k < 290 do
		local p, o = trailFrame(k)
		local placed = false
		for _ = 1, 3 do
			local off = rng(12, 30)
			local q = p + o * side * off
			if free(q.X, q.Z, 2.5) and slope(q.X, q.Z) < 2 then
				local g = surface(q.X, q.Z)
				local base = V3(q.X, g, q.Z)
				if g < 70 then
					local r = rng(0, 1)
					if r < 0.35 then
						Build.broadleaf(f, base, rng, { height = rng(10, 13), leaves = MAPLE, blobs = 5, branches = 2 })
					elseif r < 0.55 then
						Build.broadleaf(
							f,
							base,
							rng,
							{ height = rng(10, 12), leaves = BIRCH, bark = P.barkBirch, blobs = 5, branches = 2 }
						)
					else
						Build.fir(f, base, rng, { height = rng(14, 19), tiers = 3 })
					end
				elseif g < 360 then
					lightFir(f, rng, base, rng(11, 16) * (1 - (g - 70) / 900), g > 290)
				else
					windPine(f, rng, base, rng(6, 9), WIND)
				end
				occupy(q.X, q.Z, 4)
				placed = true
				break
			end
		end
		-- 길가 덤불·돌 (완만한 곳만)
		if rng(0, 1) < 0.5 then
			local q = p + o * -side * rng(8.5, 12)
			if free(q.X, q.Z, 1) and slope(q.X, q.Z) < 1.1 and p.Y < 470 then
				if rng(0, 1) < 0.5 then
					Build.shrub(
						f,
						at(q.X, q.Z),
						rng,
						{ size = rng(2.4, 3.6), blobs = 2, leaves = if p.Y > 300 then { P.pine, P.pineLight } else nil }
					)
				else
					boulder(f, rng, q.X, q.Z, rng(2, 4))
				end
				occupy(q.X, q.Z, 2)
			end
		end
		side = -side
		k += if placed then (if p.Y < 330 then 13 else 18) else 4
	end
	-- 관운봉 아래 비탈 곳곳: 전나무 무리
	for _ = 1, 9 do
		local a = rng(0, 2 * PI)
		local d = rng(200, 400)
		local cx, cz = PEAK.x + cos(a) * d, PEAK.z + sin(a) * d
		if cz > -820 and surface(cx, cz) < 260 then
			for _ = 1, 4 do
				local x, z = cx + rng(-16, 16), cz + rng(-16, 16)
				if free(x, z, 3) and slope(x, z) < 1.6 then
					fir5(f, rng, at(x, z), rng(12, 18))
					occupy(x, z, 3.5)
				end
			end
		end
	end
	-- 바위 벼랑: 관운봉 높은 비탈과 능선 (길에서 떨어진 곳)
	for _ = 1, 30 do
		local a = rng(0, 2 * PI)
		local d = rng(70, 330)
		local x, z = PEAK.x + cos(a) * d, PEAK.z + sin(a) * d
		if z > -820 and trailDist(x, z) > 24 and free(x, z, 6) then
			local g = surface(x, z)
			crag(f, rng, x, z, rng(10, 20) * (if g > 300 then 1.2 else 1), g > 330)
			occupy(x, z, 10)
		end
	end
	-- 눈 판: 바위 비탈(눈이 안 덮인 곳)
	local snowN = 0
	for _ = 1, 140 do
		if snowN >= 14 then
			break
		end
		local a = rng(0, 2 * PI)
		local d = rng(70, 260)
		local x, z = PEAK.x + cos(a) * d, PEAK.z + sin(a) * d
		local g = surface(x, z)
		if g > 250 and g < 420 and z > -820 and trailDist(x, z) > 9 then
			local s = Land.column(x, z).surface
			if s == "Rock" or s == "Slate" then
				snowPatch(f, rng, x, z, rng(9, 16))
				snowN += 1
			end
		end
	end

	-- 다른 봉우리: 삼첨봉, 서령, 소봉 (응봉은 북쪽 설원 담당)
	local peaks = folder(root, "봉우리")
	for _, pk in Land.PEAKS do
		local px, pz, ph, pr = pk[1], pk[2], pk[3], pk[4]
		if pz > -700 then
			local count = if ph > 200 then 6 else 4
			for _ = 1, count do
				local a = rng(0, 2 * PI)
				local d = rng(pr * 0.15, pr * 0.8)
				local x, z = px + cos(a) * d, pz + sin(a) * d
				if free(x, z, 5) and z < 580 then
					local g = surface(x, z)
					if g > 110 and rng(0, 1) < 0.6 then
						crag(peaks, rng, x, z, rng(10, 18), g > 300)
						occupy(x, z, 8)
					elseif slope(x, z) < 1.6 then
						for _ = 1, 3 do
							local tx, tz = x + rng(-10, 10), z + rng(-10, 10)
							if free(tx, tz, 2) then
								fir5(peaks, rng, at(tx, tz), rng(11, 16))
								occupy(tx, tz, 3)
							end
						end
					end
				end
			end
		end
	end
	-- 삼첨봉: 꼭대기 세 바위 봉 (이름 그대로 세 뿔)
	do
		local pk = Land.PEAKS[2]
		local m = model(peaks, "삼첨봉 세 뿔")
		for i = 0, 2 do
			local a = rad(i * 120 + 30)
			local x, z = pk[1] + cos(a) * 16, pk[2] + sin(a) * 16
			local low = span(x, z, 6)
			local hgt = ({ 46, 34, 38 })[i + 1]
			local yaw = rng(0, PI)
			local y = low - 3
			local w = 13
			for j = 1, 3 do
				local hh = hgt * ({ 0.5, 0.32, 0.25 })[j]
				local cf = CFrame.new(x + rng(-0.6, 0.6), y + hh / 2, z + rng(-0.6, 0.6))
					* CFrame.Angles(rng(-0.06, 0.06), yaw + j * 0.4, rng(-0.06, 0.06))
				block(
					m,
					"Bong",
					V3(w, hh + 1, w * 0.8),
					cf,
					jit(if j == 2 then ROCK_DARK else ROCK, 0.05, rng),
					M.Slate
				)
				y += hh
				w *= 0.66
			end
			Build.pyramid(m, "Kkokji", V3(x, y, z), w * 1.3, w * 1.4, yaw, SNOW, M.Snow)
			occupy(x, z, 8)
		end
	end
	-- 등줄기: 능선 따라 바위
	local pts = Land.SPINE.pts
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		if a[2] > -700 or b[2] > -700 then
			local t = rng(0.2, 0.8)
			local x = a[1] + (b[1] - a[1]) * t + rng(-20, 20)
			local z = a[2] + (b[2] - a[2]) * t + rng(-20, 20)
			if z > -700 and z < 580 and free(x, z, 5) then
				crag(peaks, rng, x, z, rng(9, 15), surface(x, z) > 300)
				occupy(x, z, 7)
			end
		end
	end
end

------------------------------------------------------------------------------------------
-- 송풍령 고갯길
------------------------------------------------------------------------------------------
-- 꺾은선을 따라 길이 s 자리: 길 가운데(높이는 꼭짓점 높이), 나아가는 쪽
local function passFrame(s: number): (Vector3, Vector3)
	local pts = PASS.pts
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local d = V3(b[1] - a[1], 0, b[2] - a[2])
		local len = d.Magnitude
		if s <= len or i == #pts - 1 then
			local t = math.clamp(s / len, 0, 1)
			return V3(a[1] + (b[1] - a[1]) * t, a[3] + (b[3] - a[3]) * t, a[2] + (b[2] - a[2]) * t), d.Unit
		end
		s -= len
	end
	local last = pts[#pts]
	return V3(last[1], last[3], last[2]), V3(-1, 0, 0)
end
local function passLength(): number
	local pts = PASS.pts
	local L = 0
	for i = 1, #pts - 1 do
		L += sqrt((pts[i + 1][1] - pts[i][1]) ^ 2 + (pts[i + 1][2] - pts[i][2]) ^ 2)
	end
	return L
end

local function buildPass(root: Instance, rng)
	local f = folder(root, "송풍령")
	local L = passLength()
	-- 솔숲 고갯길: 길 양옆 소나무 (둘씩 마주 서거나 번갈아)
	local s = 34
	local side = 1
	while s < L - 12 do
		local p, d = passFrame(s)
		local right = V3(-d.Z, 0, d.X)
		for _, sd in { side, -side } do
			if rng(0, 1) < (if sd == side then 1 else 0.45) then
				local off = rng(11.5, 16)
				local q = p + right * sd * off
				if free(q.X, q.Z, 2) and slope(q.X, q.Z) < 1.7 then
					local g = surface(q.X, q.Z)
					if g < 125 then
						lightPine(f, rng, V3(q.X, g, q.Z), rng(14, 19))
					else
						windPine(f, rng, V3(q.X, g, q.Z), rng(9, 12), WIND)
					end
					occupy(q.X, q.Z, 4)
				end
			end
		end
		if rng(0, 1) < 0.35 then
			local q = p + right * (if rng(0, 1) > 0.5 then 1 else -1) * rng(9, 12)
			if free(q.X, q.Z, 1) and slope(q.X, q.Z) < 1.1 then
				boulder(f, rng, q.X, q.Z, rng(2, 4.5))
				occupy(q.X, q.Z, 2)
			end
		end
		side = -side
		s += rng(28, 38)
	end

	-- 고개 마루(안장): 이름 비석, 서낭당(돌무더기 + 신목 + 오색 천)
	local sp, sd = passFrame(L * 0.79)
	local right = V3(-sd.Z, 0, sd.X)
	do
		local q = sp + right * 9.5
		Kit.stele(f, at(q.X, q.Z, 0.7), "송풍령", V3(sp.X, 0, sp.Z))
		occupy(q.X, q.Z, 3)
	end
	do
		local q = sp - right * 15 + sd * 6
		if not nearPath(q.X, q.Z, 3) then
			local g = surface(q.X, q.Z)
			local m = model(f, "서낭당")
			Build.broadleaf(m, V3(q.X, g, q.Z), rng, { height = 19, leaves = OAK, blobs = 7, name = "서낭나무" })
			-- 줄기에 두른 금줄과 오색 천
			local colors = { P.plaster, P.juhong, P.samcheong, P.hwang, P.noerok }
			for i = 1, 5 do
				local a = i * 2 * PI / 5
				local c = V3(q.X + cos(a) * 1.3, g + 3.2, q.Z + sin(a) * 1.3)
				deco(block(m, "Cheon", V3(0.7, 1.6, 0.08), face(c, c + V3(cos(a), 0, sin(a))), colors[i], M.Fabric)).CastShadow =
					false
			end
			deco(cyl(m, "Geumjul", V3(q.X, g + 4, q.Z), V3(q.X, g + 4.3, q.Z), 2.7, ROPE, M.Fabric)).CastShadow = false
			local c2 = q + sd * 5
			cairn(m, rng, c2.X, c2.Z, 6)
			for _ = 1, 3 do
				local a = rng(0, 2 * PI)
				local x, z = c2.X + cos(a) * rng(2.5, 3.6), c2.Z + sin(a) * rng(2.5, 3.6)
				local cf = CFrame.new(x, surface(x, z) + 0.2, z)
					* CFrame.Angles(rng(-0.3, 0.3), rng(0, PI), rng(-0.3, 0.3))
				block(m, "Dol", V3(rng(1, 1.8), rng(0.8, 1.3), rng(1, 1.6)), cf, jit(ROCK_WARM, 0.1, rng), M.Slate)
			end
			occupy(q.X, q.Z, 9)
		end
	end

	-- 주막(쉼터 집과 찻집): 안장 지나 고원 들머리, 가장 평평한 자리
	do
		local best, bx, bz = math.huge, 0, 0
		for s2 = L * 0.8, L * 0.98, 5 do
			local p, d = passFrame(s2)
			local r2 = V3(-d.Z, 0, d.X)
			for _, sgn in { 1, -1 } do
				for _, off in { 19, 23, 27 } do
					local q = p + r2 * off * sgn
					if not kept(q.X, q.Z, 12) and not nearPath(q.X, q.Z, 9) and not occupied(q.X, q.Z, 9) then
						local lo, hi = span(q.X, q.Z, 11)
						local score = (hi - lo) + abs(lo - p.Y) * 0.4
						if score < best then
							best, bx, bz = score, q.X, q.Z
						end
					end
				end
			end
		end
		-- 가장 가까운 길 쪽을 본다
		local road = passFrame(L * 0.9)
		local bestD = math.huge
		for s2 = L * 0.75, L, 4 do
			local p = passFrame(s2)
			local dd = (V3(p.X, 0, p.Z) - V3(bx, 0, bz)).Magnitude
			if dd < bestD then
				bestD, road = dd, p
			end
		end
		local site, _, cf = houseAt(
			f,
			bx,
			bz,
			V3(road.X, 0, road.Z),
			{ bays = { 3, 1 }, bay = 5, pillarH = 7.5, detail = 0, roof = "gable", bands = 2, plinth = 1.2 },
			"neowa",
			"주막"
		)
		-- 찻집 차양: 집 앞 기둥 넷에 천 지붕, 평상 둘, 화로와 주전자
		local fcf = onGround(cf * CFrame.new(0, 0, -9.5))
		local fy = fcf.Position.Y
		local stall = model(site, "찻집")
		for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
			local pp = (fcf * CFrame.new(c[1] * 6, 0, c[2] * 3.2)).Position
			local g = surface(pp.X, pp.Z)
			local hgt = if c[2] > 0 then 7.2 else 6.2
			beam(stall, "Gidung", V3(pp.X, g - 0.6, pp.Z), V3(pp.X, fy + hgt, pp.Z), 0.5, 0.5, P.woodDark, M.Wood)
		end
		block(
			stall,
			"Chayang",
			V3(13.4, 0.2, 7.6),
			fcf * CFrame.new(0, 6.85, 0) * CFrame.Angles(rad(-8), 0, 0),
			Color3.fromRGB(226, 214, 186),
			M.Fabric
		)
		bench(stall, onGround(fcf * CFrame.new(-3, 0, -0.4)), 5, 3.2)
		local b2 = onGround(fcf * CFrame.new(3.4, 0, 0.6))
		bench(stall, b2, 4.2, 3)
		local hw = b2 * CFrame.new(0, 1.85, 0)
		cyl(stall, "Hwaro", hw.Position, hw.Position + V3(0, 0.7, 0), 1.3, Color3.fromRGB(70, 60, 54), M.Metal)
		ball(stall, "Jujeonja", hw.Position + V3(0, 1.2, 0), 0.9, Color3.fromRGB(64, 84, 70), M.SmoothPlastic)
		local sign = block(stall, "Pyojit", V3(4.4, 1.4, 0.25), fcf * CFrame.new(0, 5.6, -3.4), P.meok, M.Wood)
		Kit.engrave(sign, "찻집", "Front,Back")
		local flagAt = (fcf * CFrame.new(7.8, 0, -3)).Position
		Build.banner(
			f,
			at(flagAt.X, flagAt.Z),
			(fcf * CFrame.new(7.8, 0, -8)).Position,
			Color3.fromRGB(226, 214, 186),
			10
		)
		occupy(fcf.Position.X, fcf.Position.Z, 8)
		woodpile(site, onGround(cf * CFrame.new(10.2, 0, 1.5) * CFrame.Angles(0, rad(90), 0)))
		Build.jars(site, onGround(cf * CFrame.new(-10.5, 0, 1) * CFrame.Angles(0, rad(90), 0)), rng, 4)
	end
end

------------------------------------------------------------------------------------------
-- 백금굴 (금 오행처): 소봉 앞 바위 언덕 동쪽 턱
------------------------------------------------------------------------------------------
local function buildMine(root: Instance, rng)
	local f = folder(root, "백금굴")
	local site = Land.MINE
	local knoll = Land.KNOLL
	-- 굴 어귀: 자리 남쪽, 언덕 동쪽의 깎인 바위 턱 (x = -480). 동쪽을 본다.
	-- 앞이 +X 라서 cf 의 +X(오른쪽)가 남쪽(+Z), -X 가 북쪽(자리 쪽)
	local gx, gz = -478.6, -139
	local gy = surface(gx + 1.5, gz)
	local look = face(V3(gx, 0, gz), V3(gx + 10, 0, gz))
	local rot = look - look.Position
	local cf = CFrame.new(gx, gy, gz) * rot
	local m = model(f, "굴 어귀")
	-- 어귀 둘레 바위 (굴이 바위에 뚫린 듯이)
	block(m, "Bawi", V3(15, 20, 6), cf * CFrame.new(0.5, 7, 4.2), ROCK, M.Slate)
	block(m, "Bawi", V3(4, 13, 6.5), cf * CFrame.new(-6.4, 4.6, 2.2) * CFrame.Angles(0, 0.18, 0.05), ROCK_DARK, M.Slate)
	block(m, "Bawi", V3(5, 16, 7), cf * CFrame.new(7.4, 6, 1.8) * CFrame.Angles(0, -0.25, -0.06), ROCK_WARM, M.Slate)
	block(m, "Eodum", V3(5.4, 7, 0.4), cf * CFrame.new(0, 3.4, 1.05), DARK, M.SmoothPlastic)
	-- 동발(갱목 틀): 기둥 둘, 버팀, 인방, 갓
	for _, s in { -1, 1 } do
		block(m, "Dongbal", V3(0.9, 7.6, 0.9), cf * CFrame.new(s * 3.2, 3.6, 0.3), P.woodDark, M.Wood)
		beam(
			m,
			"Beotim",
			(cf * CFrame.new(s * 3.2, 5.6, 0.3)).Position,
			(cf * CFrame.new(s * 2.0, 7.3, 0.3)).Position,
			0.5,
			0.5,
			P.woodDark,
			M.Wood
		)
	end
	block(m, "Inbang", V3(8, 1, 1.1), cf * CFrame.new(0, 7.7, 0.3), P.wood, M.Wood)
	block(m, "Gat", V3(9.4, 0.4, 3), cf * CFrame.new(0, 8.5, -0.4) * CFrame.Angles(rad(-12), 0, 0), NEOWA, M.WoodPlanks)
	local plaque = block(m, "Hyeonpan", V3(4.6, 1.3, 0.25), cf * CFrame.new(0, 9.5, 0.2), P.meok, M.Wood)
	Kit.engrave(plaque, "백금굴", "Front")
	-- 등잔: 인방에 매단 등
	local lampPos = (cf * CFrame.new(2.3, 6.2, -0.6)).Position
	deco(beam(m, "Kkeun", lampPos + V3(0, 1, 0), lampPos + V3(0, 0.4, 0), 0.08, 0.08, P.meok, M.Fabric))
	local lamp = block(m, "Deung", V3(0.8, 1, 0.8), CFrame.new(lampPos), Color3.fromRGB(255, 196, 120), M.Neon)
	Kit.light(lamp, Color3.fromRGB(255, 190, 120), 18, 1.6)
	-- 바위에 박힌 백금 광맥 (반짝이는 은빛)
	local veins = {
		{ -5.2, 9.5, 1, 0.6 },
		{ 4.8, 11, 1, -0.5 },
		{ -1.5, 13.5, 1.1, 0.3 },
		{ 6.6, 4, -1.6, 1.0 },
		{ -5.6, 3, -1.1, -0.9 },
	}
	for _, v in veins do
		local p = deco(
			block(
				m,
				"Gwangmaek",
				V3(rng(2.2, 3.4), 0.5, 0.5),
				cf * CFrame.new(v[1], v[2], v[3]) * CFrame.Angles(0, 0, v[4]),
				ORE,
				M.Foil
			)
		)
		p.Reflectance = 0.25
		local g = deco(
			block(
				m,
				"Banjjak",
				V3(0.35, 0.35, 0.2),
				cf * CFrame.new(v[1] + 0.4, v[2] + 0.2, v[3] - 0.3) * CFrame.Angles(0, 0, 0.785),
				Color3.fromRGB(240, 246, 255),
				M.Neon
			)
		)
		g.CastShadow = false
	end
	occupy(gx, gz, 9)

	-- 선로와 광차: 어귀에서 동남쪽으로 짧게
	local rail = model(f, "선로")
	local pts = { (cf * CFrame.new(0, 0, -1)).Position }
	for i = 1, 4 do
		table.insert(pts, (cf * CFrame.new(i * 0.9, 0, -1 - i * 3.6)).Position)
	end
	for i = 1, #pts do
		local p = pts[i]
		pts[i] = V3(p.X, surface(p.X, p.Z), p.Z)
	end
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local d = (b - a)
		local r = V3(-d.Z, 0, d.X).Unit
		for _, s in { -1, 1 } do
			beam(
				rail,
				"Rail",
				a + r * s * 1.1 + V3(0, 0.45, 0),
				b + r * s * 1.1 + V3(0, 0.45, 0),
				0.25,
				0.3,
				Color3.fromRGB(70, 66, 64),
				M.Metal
			)
		end
		local mid = a:Lerp(b, 0.5)
		beam(
			rail,
			"Chimmok",
			mid - r * 1.7 + V3(0, 0.15, 0),
			mid + r * 1.7 + V3(0, 0.15, 0),
			0.7,
			0.35,
			P.woodDark,
			M.Wood
		)
		beam(rail, "Chimmok", a - r * 1.7 + V3(0, 0.15, 0), a + r * 1.7 + V3(0, 0.15, 0), 0.7, 0.35, P.woodDark, M.Wood)
	end
	do
		local pos = pts[3] + V3(0, 0.45, 0)
		local c = model(f, "광차")
		local ccf = face(pos, pos + (pts[4] - pts[3]))
		block(c, "Tong", V3(2.8, 1.8, 3.6), ccf * CFrame.new(0, 1.85, 0), Color3.fromRGB(96, 74, 54), M.WoodPlanks)
		block(c, "Te", V3(3, 0.3, 3.8), ccf * CFrame.new(0, 2.85, 0), Color3.fromRGB(64, 60, 58), M.Metal)
		for _, sx in { -1, 1 } do
			for _, sz in { -1, 1 } do
				local h = (ccf * CFrame.new(sx * 1.15, 0.65, sz * 1.1)).Position
				cyl(
					c,
					"Bakwi",
					h - ccf.RightVector * 0.15,
					h + ccf.RightVector * 0.15,
					1.1,
					Color3.fromRGB(52, 50, 50),
					M.Metal
				)
			end
		end
		for _ = 1, 3 do
			local ocf = ccf
				* CFrame.new(rng(-0.7, 0.7), 3, rng(-0.9, 0.9))
				* CFrame.Angles(rng(0, 1), rng(0, 3), rng(0, 1))
			local p = deco(block(c, "Gwangseok", V3(rng(0.9, 1.3), rng(0.6, 1), rng(0.8, 1.2)), ocf, ORE, M.Foil))
			p.Reflectance = 0.2
		end
	end
	-- 선로 끝 광석 무더기
	local tail = pts[#pts]
	local tdir = (pts[#pts] - pts[#pts - 1]).Unit
	local heap = tail + tdir * 4
	local hm = model(f, "광석 무더기")
	for _ = 1, 6 do
		local x, z = heap.X + rng(-2.2, 2.2), heap.Z + rng(-2.2, 2.2)
		local g = surface(x, z)
		local s = rng(1, 2)
		local ocf = CFrame.new(x, g + s * 0.15, z) * CFrame.Angles(rng(0, 1), rng(0, 3), rng(0, 1))
		local shiny = rng(0, 1) > 0.45
		local p = block(
			hm,
			"Gwangseok",
			V3(s, s * 0.7, s),
			ocf,
			if shiny then ORE else jit(ROCK, 0.1, rng),
			if shiny then M.Foil else M.Slate
		)
		p.Reflectance = if shiny then 0.15 else 0
	end
	occupy(heap.X, heap.Z, 4)
	-- 연장 걸이: 곡괭이와 삽 (어귀 남쪽)
	do
		local rc = onGround(cf * CFrame.new(7.5, 0, -3.5) * CFrame.Angles(0, rad(20), 0))
		local r = model(f, "연장걸이")
		for _, s in { -1, 1 } do
			block(r, "Gidung", V3(0.4, 4.2, 0.4), rc * CFrame.new(s * 2.4, 1.6, 0), P.woodDark, M.Wood)
		end
		block(r, "Garodae", V3(5.4, 0.3, 0.3), rc * CFrame.new(0, 3.4, 0), P.wood, M.Wood)
		for i = -1, 1 do
			local hcf = rc * CFrame.new(i * 1.4, 1.9, -0.25) * CFrame.Angles(rad(8), 0, 0)
			block(r, "Jalu", V3(0.22, 3.4, 0.22), hcf, P.wood, M.Wood)
			if i == 0 then
				block(r, "Sap", V3(1, 1.3, 0.12), hcf * CFrame.new(0, -1.9, 0), Color3.fromRGB(80, 78, 76), M.Metal)
			else
				block(
					r,
					"Gokgwaengi",
					V3(2.4, 0.28, 0.28),
					hcf * CFrame.new(0, 1.6, 0) * CFrame.Angles(0, 0, rad(10)),
					Color3.fromRGB(80, 78, 76),
					M.Metal
				)
			end
		end
		occupy(rc.Position.X, rc.Position.Z, 3)
	end
	-- 언덕 꼭대기 도르래 틀 (멀리서 보이는 표)
	do
		local x, z = knoll.x + 6, knoll.z - 2
		local g = surface(x, z)
		local w = model(f, "도르래")
		for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
			beam(
				w,
				"Gidung",
				V3(x + c[1] * 3, g - 0.6, z + c[2] * 3),
				V3(x + c[1] * 1.2, g + 8.5, z + c[2] * 1.2),
				0.6,
				0.6,
				P.woodDark,
				M.Wood
			)
		end
		cyl(w, "Gul", V3(x - 1.8, g + 8, z), V3(x + 1.8, g + 8, z), 1.2, P.wood, M.Wood)
		block(w, "Gat", V3(4.4, 0.4, 4.4), CFrame.new(x, g + 9.1, z), NEOWA, M.WoodPlanks)
		rope(w, V3(x, g + 7.4, z - 0.6), V3(x, g + 1.4, z - 0.6))
		block(w, "Ttukkeong", V3(4.4, 0.5, 4.4), CFrame.new(x, g + 0.1, z), P.woodDark, M.WoodPlanks)
		occupy(x, z, 5)
	end
	-- 둘레 너덜 (자리 둘레는 비운다)
	for _ = 1, 8 do
		local a = rng(0, 2 * PI)
		local d = rng(14, 36)
		local x, z = site.x + cos(a) * d - 10, site.z + sin(a) * d
		if free(x, z, 2) and slope(x, z) < 1.3 then
			boulder(f, rng, x, z, rng(1.5, 3.5), ROCK_WARM)
			occupy(x, z, 2)
		end
	end
	-- 언덕 비탈 소나무
	for _ = 1, 5 do
		local a = rng(0, 2 * PI)
		local d = rng(16, 30)
		local x, z = knoll.x + cos(a) * d, knoll.z + sin(a) * d
		if free(x, z, 3) then
			lightPine(f, rng, at(x, z), rng(12, 16))
			occupy(x, z, 4)
		end
	end
end

------------------------------------------------------------------------------------------
-- 운곡 마을: 백령 기슭 구름골. 큰길(돌길)이 동쪽 문에서 서쪽 송풍령으로 지난다
------------------------------------------------------------------------------------------
local function buildVillage(root: Instance, rng)
	local f = folder(root, "운곡 마을")
	local V = Land.VILLAGE_W
	-- 동쪽 마을 문 (일주문 "운곡"): 돌길이 들어오는 곳
	do
		local gx, gz = -452, 22.2
		local g = surface(gx, gz)
		local toward = V3(gx + 10, 0, gz - 1.7)
		local gate = model(f, "운곡 일주문")
		local _, board = Build.iljumun(gate, V3(gx, g, gz), toward, 12)
		Kit.engrave(board, "운곡", "Front,Back")
		occupy(gx, gz, 9)
		-- 문 곁 장승 둘 (나무 기둥에 검은 갓)
		local look = face(V3(gx, 0, gz), toward)
		for _, s in { -1, 1 } do
			local q = look * CFrame.new(s * 9.5, 0, -2)
			local x, z = q.Position.X, q.Position.Z
			local gg = surface(x, z)
			local js = model(f, "장승")
			cyl(js, "Mom", V3(x, gg - 0.5, z), V3(x, gg + 6.5, z), 1.3, Color3.fromRGB(150, 116, 80), M.Wood)
			block(js, "Gat", V3(2, 1.2, 2), CFrame.new(x, gg + 7.1, z), P.meok, M.Wood)
			block(
				js,
				"Eolgul",
				V3(0.9, 1.2, 0.3),
				CFrame.new(x, gg + 5.4, z) * (look - look.Position) * CFrame.new(0, 0, -0.6),
				P.juhong,
				M.SmoothPlastic
			)
		end
	end
	-- 집 (앞이 큰길을 본다). { x, z, 칸, 지붕, 지붕감 }
	local houses = {
		{ -464, -4, { 2, 1 }, "gable", "neowa" },
		{ -527, -6, { 2, 1 }, "gable", "choga" },
		{ -468, 60, { 2, 1 }, "gable", "choga" },
		{ -505, 68, { 3, 2 }, "paljak", nil }, -- 촌장 댁 (기와)
		{ -545, 72, { 2, 1 }, "gable", "neowa" },
		{ -583, 72, { 2, 1 }, "gable", "choga" },
	}
	local yards = {}
	for _, h in houses do
		local x, z = h[1], h[2]
		local toward = V3(x, 0, if z < 30 then 40 else 25)
		local tile = h[5] == nil
		local opts = {
			bays = h[3],
			bay = if tile then 5 else 5.5,
			pillarH = if tile then 8 else 7,
			detail = 0,
			roof = h[4],
			bands = if tile then 2 else 1,
			plinth = 1.4,
		}
		local name = if tile then "촌장 댁" elseif h[5] == "choga" then "초가" else "너와집"
		local _, top, cf = houseAt(f, x, z, toward, opts, h[5], name)
		table.insert(yards, { cf = cf, top = top, w = h[3][1] * opts.bay, d = h[3][2] * opts.bay, tile = tile })
	end
	-- 마당 살림: 장독대, 장작, 덕, 돌담, 디딤돌
	for i, y in yards do
		local cf = y.cf
		local hw, hd = y.w / 2 + 2.2, y.d / 2 + 2.2
		if i % 2 == 1 or y.tile then
			Build.jars(
				f,
				onGround(cf * CFrame.new(hw + 3.4, 0, 0.5) * CFrame.Angles(0, rad(90), 0)),
				rng,
				if y.tile then 6 else 4
			)
		else
			woodpile(f, onGround(cf * CFrame.new(hw + 1.8, 0, 1.2) * CFrame.Angles(0, rad(90), 0)))
		end
		if i == 2 or i == 5 then
			dryingRack(
				f,
				rng,
				onGround(cf * CFrame.new(-hw - 3.4, 0, -2) * CFrame.Angles(0, rad(90), 0)),
				Color3.fromRGB(214, 118, 46)
			)
		end
		-- 돌담: 집 옆과 뒤 (앞 마당은 연다)
		local function w(lx: number, lz: number): Vector3
			return (cf * CFrame.new(lx, 0, lz)).Position
		end
		local bx, bz = hw + 6.5, hd + 3
		local front = -hd - 5
		local wallM = model(f, "돌담")
		dryWall(wallM, rng, w(-bx, front), w(-bx, bz), 2.4)
		dryWall(wallM, rng, w(-bx, bz), w(bx, bz), 2.4)
		dryWall(wallM, rng, w(bx, bz), w(bx, front), 2.4)
		if y.tile then
			-- 촌장 댁: 앞 담과 가운데 문 (문기둥 둘과 너와 지붕)
			dryWall(wallM, rng, w(-bx, front), w(-3, front), 2.4)
			dryWall(wallM, rng, w(3, front), w(bx, front), 2.4)
			for _, s in { -1, 1 } do
				local q = w(s * 3, front)
				local g = surface(q.X, q.Z)
				block(wallM, "Munjuk", V3(0.6, 5.4, 0.6), CFrame.new(q.X, g + 2.1, q.Z), P.woodDark, M.Wood)
			end
			local a, b = w(-3, front), w(3, front)
			local g = max(surface(a.X, a.Z), surface(b.X, b.Z))
			block(
				wallM,
				"Munjibung",
				V3(7.4, 0.5, 2),
				CFrame.new((a.X + b.X) / 2, g + 4.9, (a.Z + b.Z) / 2) * (cf - cf.Position),
				NEOWA_DARK,
				M.WoodPlanks
			)
		end
		-- 마당에서 큰길로 디딤돌
		for s = 1, 2 do
			local q = (cf * CFrame.new(rng(-0.4, 0.4), 0, -hd - 3 - s * 3)).Position
			steppingStone(f, rng, q.X, q.Z)
		end
	end
	-- 마을 마당: 당산나무(큰 느티)와 둘레 돌단, 우물, 평상
	do
		local tx, tz = -512, 46
		local g = surface(tx, tz)
		local seat = model(f, "당산나무")
		for k = 0, 5 do
			local a = k * PI / 3
			local p = V3(tx + cos(a) * 4.4, g + 0.6, tz + sin(a) * 4.4)
			block(seat, "Dol", V3(4.6, 1.4, 1.3), face(p, V3(tx, p.Y, tz)), jit(WALLSTONE, 0.05, rng), M.Cobblestone)
		end
		block(
			seat,
			"Heuk",
			V3(7.4, 0.8, 7.4),
			CFrame.new(tx, g + 0.2, tz) * CFrame.Angles(0, PI / 6, 0),
			SOIL,
			M.Ground
		)
		Build.broadleaf(seat, V3(tx, g + 0.6, tz), rng, { height = 24, leaves = OAK, blobs = 9, name = "느티나무" })
		occupy(tx, tz, 9)
		Build.well(f, at(-486, 46))
		occupy(-486, 46, 4)
		bench(f, onGround(CFrame.new(-497, 0, 54) * CFrame.Angles(0, rad(15), 0)), 5, 3.2)
	end
	-- 큰길 청사초롱과 깃발
	for _, p in { { -472, 14 }, { -530, 44 } } do
		if not kept(p[1], p[2], 2) then
			Build.chorong(f, at(p[1], p[2]), V3(p[1], 0, 28 + (p[1] + 500) * -0.17))
			occupy(p[1], p[2], 2)
		end
	end
	Build.banner(f, at(-461, 32), V3(-440, 0, 32), P.samcheong, 12)
	-- 계단밭: 마을 남서 비탈. 돌 축대 + 고랑
	for _, fd in { { -606, 98 }, { -626, 116 } } do
		local x, z = fd[1], fd[2]
		if free(x, z, 9) then
			local low, high = span(x, z, 9)
			local top = high + 0.3
			local look = face(V3(x, 0, z), V3(x + 10, 0, z))
			local rot = look - look.Position
			local h = top - low + 1.5
			local fm = model(f, "계단밭")
			block(fm, "Batchukdae", V3(16, h, 13), CFrame.new(x, top - h / 2 - 0.3, z) * rot, WALLSTONE, M.Cobblestone)
			block(fm, "Bat", V3(15.2, 0.4, 12.2), CFrame.new(x, top, z) * rot, SOIL, M.Ground)
			for r = -2, 2 do
				deco(
					block(
						fm,
						"Gorang",
						V3(14, 0.7, 1),
						CFrame.new(x, top + 0.45, z) * rot * CFrame.new(0, 0, r * 2.3),
						jit(P.leafLight, 0.08, rng),
						M.LeafyGrass
					)
				).CastShadow =
					false
			end
			occupy(x, z, 10)
		end
	end
	-- 석종굴: 영맥(mid@ungok) 뒤 서쪽 비탈에 뚫린 굴 어귀. 어둠 판은 비탈에 눕혀 굴이 산으로 드는 듯이,
	-- 위에는 처마처럼 내민 바위와 종유석 (영맥 둘레 7 은 비운다)
	do
		local vx, vz = -585, 30
		local cave = model(f, "석종굴")
		local back = V3(-1, 0, -0.12).Unit
		local mouth = V3(vx, 0, vz) + back * 11.5
		-- 비탈에 눕힌 어둠 (굴 속)
		local dcf = slopeFrame(mouth.X, mouth.Z, 0.3) * CFrame.Angles(0, yawTo(mouth, mouth - back), 0)
		block(cave, "Eodum", V3(8.5, 0.5, 9), dcf, DARK, M.SmoothPlastic)
		local g = surface(mouth.X, mouth.Z)
		local look = face(mouth, mouth - back)
		local rot = look - look.Position
		local function W(lx: number, ly: number, lz: number): CFrame
			return CFrame.new(mouth.X, g, mouth.Z) * rot * CFrame.new(lx, ly, lz)
		end
		-- 양옆 문설주 바위와 위 처마 바위 (앞으로 내민다)
		block(cave, "Bawi", V3(5, 13, 9), W(-6.6, 3.5, 1.5) * CFrame.Angles(0.1, 0.25, 0.08), ROCK, M.Slate)
		block(cave, "Bawi", V3(5.5, 12, 9), W(6.8, 3, 1.5) * CFrame.Angles(0.1, -0.3, -0.06), ROCK_DARK, M.Slate)
		local lip = W(0, 9.2, 1.4) * CFrame.Angles(-0.12, 0, 0.04)
		block(cave, "Cheoma", V3(17, 4, 8), lip, ROCK_WARM, M.Slate)
		block(cave, "Bawi", V3(20, 8, 9), W(0.5, 13.5, 5) * CFrame.Angles(0.15, 0.06, 0), ROCK, M.Slate)
		-- 종유석: 처마 바위 밑에 거꾸로 선 뿔
		for i = -3, 3 do
			local len = rng(1.6, 3.4) * (1 - abs(i) * 0.1)
			local tcf = lip * CFrame.new(i * 1.7 + rng(-0.3, 0.3), -2, -3.2 + rng(-0.4, 0.4))
			local p = Build.cornerWedge(
				cave,
				"Jongyuseok",
				V3(0.75, len, 0.75),
				tcf * CFrame.new(0, -len / 2, 0) * CFrame.Angles(PI, rng(0, PI), 0),
				LIMESTONE,
				M.Limestone
			)
			p.CastShadow = false
		end
		-- 석순 (굴 어귀 발치)
		for _, sx in { -3.8, 3.6 } do
			local q = (W(sx, 0, -1)).Position
			local gg = surface(q.X, q.Z)
			local len = rng(1.8, 3)
			Build.cornerWedge(
				cave,
				"Seoksun",
				V3(1, len, 1),
				CFrame.new(q.X, gg + len / 2 - 0.3, q.Z) * CFrame.Angles(0, rng(0, PI), 0),
				LIMESTONE:Lerp(ROCK, 0.2),
				M.Limestone
			)
		end
		local plaque = block(cave, "Pyoseok", V3(3.6, 1.5, 0.4), lip * CFrame.new(-4.5, 0.2, -4.1), P.meok, M.Wood)
		Kit.engrave(plaque, "석종굴", "Front")
		occupy(mouth.X, mouth.Z, 9)
	end
	-- 마을 둘레 나무: 은행, 단풍, 느티, 소나무
	local trees = {
		{ -440, 52, "ginkgo" },
		{ -486, 96, "pine" },
		{ -560, 102, "maple" },
		{ -604, -8, "pine" },
		{ -505, -32, "ginkgo" },
		{ -470, -38, "maple" },
		{ -566, -22, "oak" },
	}
	for _, t in trees do
		local x, z = t[1] + rng(-3, 3), t[2] + rng(-3, 3)
		if free(x, z, 3) then
			local base = at(x, z)
			if t[3] == "pine" then
				Build.pine(f, base, rng, { height = rng(14, 18), tiers = 4 })
			elseif t[3] == "maple" then
				Build.broadleaf(f, base, rng, { height = rng(10, 13), leaves = MAPLE, blobs = 6, branches = 2 })
			elseif t[3] == "ginkgo" then
				Build.broadleaf(f, base, rng, { height = rng(13, 16), leaves = GINKGO, blobs = 6, branches = 2 })
			else
				Build.broadleaf(f, base, rng, { height = rng(12, 15), leaves = OAK, blobs = 6, branches = 2 })
			end
			occupy(x, z, 5)
		end
	end
	-- 덤불과 들꽃
	for _ = 1, 16 do
		local a = rng(0, 2 * PI)
		local d = rng(20, 90)
		local x, z = V.x + cos(a) * d, V.z + sin(a) * d
		if free(x, z, 1.5) and slope(x, z) < 1 then
			if rng(0, 1) < 0.45 then
				Build.shrub(f, at(x, z), rng, { size = rng(2.2, 3.6), blobs = 2 })
			else
				tuft(f, rng, x, z, WILDFLOWERS[1 + floor(rng(0, 3.99))])
			end
			occupy(x, z, 1.5)
		end
	end
end

------------------------------------------------------------------------------------------
-- 낙조대: 서쪽 고원. 허브가 성대를 짓고, 여기서는 벼랑 끝 정자, 돌난간, 바람 소나무, 들꽃
------------------------------------------------------------------------------------------
local PLAT = { x = -1320, z = 20 }

-- 각도 a(도)에서 고원 가장자리(높이 141 아래로 꺾이는 곳)까지 거리
local function lipAt(a: number): number
	local c, s = cos(rad(a)), sin(rad(a))
	local d = 200
	while d < 320 do
		if surface(PLAT.x + c * d, PLAT.z + s * d) < 141 then
			return d - 2
		end
		d += 2
	end
	return d
end

local function buildPlateau(root: Instance, rng)
	local f = folder(root, "낙조대")
	local star = Land.STARS.west
	-- 낙조정: 서쪽 벼랑 끝. 앞(계단)이 고원 안쪽(동쪽), 뒤가 해 지는 바다
	local pa = 182
	local lip = lipAt(pa)
	local pd = lip - 10
	local px, pz = PLAT.x + cos(rad(pa)) * pd, PLAT.z + sin(rad(pa)) * pd
	do
		local look = face(V3(px, 0, pz), V3(px + 10, 0, pz))
		local rot = look - look.Position
		local low, high = span(px, pz, 9)
		local base = high + 0.3
		local m = model(f, "낙조정")
		terrace(m, CFrame.new(px, 0, pz) * rot, 16, 16, base, low, ROCK)
		Build.pavilion(
			m,
			CFrame.new(px, base, pz) * rot,
			{ detail = 0, bands = 2, bay = 9, pillarH = 7.5, plinth = 2, name = "낙조정" }
		)
		occupy(px, pz, 11)
		Build.stoneLantern(f, at(px + 12, pz - 7))
		Build.stoneLantern(f, at(px + 12, pz + 7))
	end
	-- 벼랑 끝 돌난간: 정자 양옆으로 가장자리를 따라
	do
		local m = model(f, "돌난간")
		local prev: Vector3? = nil
		for a = pa - 24, pa + 24, 3 do
			local d = lipAt(a) - 3
			local x, z = PLAT.x + cos(rad(a)) * d, PLAT.z + sin(rad(a)) * d
			if occupied(x, z, 0.5) then
				prev = nil
			else
				local g = surface(x, z)
				local p = V3(x, g, z)
				block(m, "Dolgidung", V3(1, 3.6, 1), CFrame.new(x, g + 0.7, z), P.granite, M.Granite)
				if prev and (prev - p).Magnitude < 16 then
					beam(
						m,
						"Dolnangan",
						prev + V3(0, 2.2, 0),
						p + V3(0, 2.2, 0),
						0.7,
						0.55,
						P.graniteDark:Lerp(P.granite, 0.4),
						M.Granite
					)
				end
				prev = p
			end
		end
	end
	-- 바람 소나무: 가장자리 따라 (바람이 바다에서 불어 동쪽으로 눕는다)
	local pines = 0
	for _ = 1, 14 do
		if pines >= 7 then
			break
		end
		local a = rng(130, 235)
		local d = lipAt(a) - rng(6, 22)
		local x, z = PLAT.x + cos(rad(a)) * d, PLAT.z + sin(rad(a)) * d
		if free(x, z, 3) then
			windPine(f, rng, at(x, z), rng(10, 15), WIND)
			occupy(x, z, 6)
			pines += 1
		end
	end
	-- 고원 곳곳 너럭바위와 철쭉 덤불
	for _ = 1, 10 do
		local a = rng(0, 2 * PI)
		local d = rng(40, 220)
		local x, z = PLAT.x + cos(a) * d, PLAT.z + sin(a) * d
		if free(x, z, 3) and surface(x, z) > 140 then
			if rng(0, 1) < 0.5 then
				boulder(f, rng, x, z, rng(2.5, 6))
			else
				Build.shrub(
					f,
					at(x, z),
					rng,
					{ size = rng(2.5, 4), blobs = 3, leaves = { P.leafDeep, P.leaf, AZALEA } }
				)
			end
			occupy(x, z, 3)
		end
	end
	-- 들꽃과 풀포기: 정자 둘레에 많이, 고원에 드문드문
	for _ = 1, 26 do
		local x, z
		if rng(0, 1) < 0.6 then
			x, z = px + rng(-30, 30), pz + rng(-36, 36)
		else
			x, z = PLAT.x + rng(-200, 160), PLAT.z + rng(-160, 160)
		end
		if free(x, z, 0.8) and surface(x, z) > 140 then
			tuft(f, rng, x, z, if rng(0, 1) < 0.65 then WILDFLOWERS[1 + floor(rng(0, 3.99))] else nil)
		end
	end
	-- 디딤돌 길: 성대 곁에서 낙조정까지
	do
		local m = model(f, "디딤돌 길")
		local a = V3(star.x - 26, 0, star.z + 14)
		local b = V3(px + 15, 0, pz)
		local len = (b - a).Magnitude
		local nsteps = floor(len / 13)
		for i = 0, nsteps do
			local q = a:Lerp(b, i / nsteps) + V3(0, 0, 6 * sin(i * 0.5))
			if not kept(q.X, q.Z, 1) and not occupied(q.X, q.Z, 1) then
				steppingStone(m, rng, q.X, q.Z, rng(2.2, 3))
			end
		end
	end
end

------------------------------------------------------------------------------------------

function Region.build(root: Instance, rng: (number, number) -> number)
	OCC = {}
	local top = folder(root, "백령")
	-- 사람이 다니는 곳부터 (자리를 먼저 차지한다)
	buildVillage(top, rng)
	buildMine(top, rng)
	buildTrail(top, rng)
	buildSummit(top, rng)
	buildPass(top, rng)
	buildPlateau(top, rng)
	buildSlopes(top, rng)
	return top
end

return Region
