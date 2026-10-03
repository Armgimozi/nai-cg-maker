-- 북쪽 땅: 명경호와 경심정, 비류대와 비류폭, 백랑설원과 북진대, 설하 빙하와 빙경담, 응봉.
-- World.luau 가 build(root, rng) 를 부른다. root 밑에 "북쪽" 폴더 하나를 짓고 모두 그 안에 넣는다.
-- 과업 자리·전송진·영맥·영초 범위는 World(허브)가 놓는다. 여기서는 Sites 의 자리를 읽어 그 둘레를 비워 두고 꾸민다.
-- 땅 모양은 Shared.Land 가 정한다. 모든 물건은 Land.surface 에 맞춰 앉히고, 비탈이면 낮은 쪽에 박거나 축대를 받친다.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")
local Land = require(Shared.Land)
local Build = require(script.Parent.WorldBuild)
local Kit = require(script.Parent.WorldKit)
local Sites = require(script.Parent.WorldSites)

local P = Build.P
local block, wedge, beam, cyl = Build.block, Build.wedge, Build.beam, Build.cyl
local deco, face = Build.deco, Build.face
local huge, sqrt, cos, sin, rad, floor, min, max, abs =
	math.huge, math.sqrt, math.cos, math.sin, math.rad, math.floor, math.min, math.max, math.abs
local TAU = math.pi * 2
local M = Enum.Material

local Region = {}

-- 빛깔 ------------------------------------------------------------------------------------

local NC = {
	snow = Color3.fromRGB(236, 240, 246),
	snowShade = Color3.fromRGB(206, 216, 228),
	ice = Color3.fromRGB(178, 214, 234),
	iceDeep = Color3.fromRGB(120, 172, 208),
	crevasse = Color3.fromRGB(40, 78, 116),
	frostRock = Color3.fromRGB(104, 110, 120),
	rock = Color3.fromRGB(122, 118, 112),
	darkRock = Color3.fromRGB(84, 86, 90),
	wetRock = Color3.fromRGB(62, 66, 70),
	pebble = Color3.fromRGB(178, 172, 160),
	water = Color3.fromRGB(186, 222, 238),
	foam = Color3.fromRGB(240, 248, 252),
	navy = Color3.fromRGB(46, 52, 96), -- 현무 깃발 (검푸른)
	ink = Color3.fromRGB(30, 32, 40),
	straw = Color3.fromRGB(176, 150, 98),
	net = Color3.fromRGB(70, 60, 48),
	azalea = Color3.fromRGB(222, 112, 150), -- 진달래
	iris = Color3.fromRGB(110, 96, 180), -- 붓꽃
	wildY = Color3.fromRGB(232, 200, 90), -- 들꽃 (노랑)
	wildW = Color3.fromRGB(242, 240, 230),
}
local BIRCH_LEAVES = { Color3.fromRGB(96, 138, 70), Color3.fromRGB(130, 168, 84), Color3.fromRGB(168, 190, 96) }
local MAPLE_LEAVES = { Color3.fromRGB(150, 54, 40), P.maple, Color3.fromRGB(222, 120, 60) }
local FROST_LEAVES = { Color3.fromRGB(110, 128, 120), Color3.fromRGB(160, 176, 178), Color3.fromRGB(214, 222, 228) }
local FERN_LEAVES = { Color3.fromRGB(46, 88, 52), Color3.fromRGB(62, 108, 60), Color3.fromRGB(84, 128, 66) }
local FIR_GREEN = { Color3.fromRGB(44, 80, 58), Color3.fromRGB(54, 94, 66), Color3.fromRGB(66, 108, 72) }

-- 땅 -------------------------------------------------------------------------------------

local function surf(x: number, z: number): number
	return Land.surface(x, z)
end

-- 가운데와 둘레 여덟 곳 땅 높이의 낮은 값과 높은 값
local function span(x: number, z: number, r: number): (number, number)
	local lo, hi = huge, -huge
	for i = 0, 8 do
		local px, pz = x, z
		if i > 0 then
			local a = i * math.pi / 4
			px, pz = x + cos(a) * r, z + sin(a) * r
		end
		local h = surf(px, pz)
		if h < lo then
			lo = h
		end
		if h > hi then
			hi = h
		end
	end
	return lo, hi
end

-- 네모 자리(가운데 cf, 크기 sx × sz) 안 25 곳의 낮은·높은 땅
local function rectSpan(cf: CFrame, sx: number, sz: number): (number, number)
	local lo, hi = huge, -huge
	for i = -2, 2 do
		for j = -2, 2 do
			local p = cf:PointToWorldSpace(Vector3.new(i * sx / 4, 0, j * sz / 4))
			local h = surf(p.X, p.Z)
			lo, hi = min(lo, h), max(hi, h)
		end
	end
	return lo, hi
end

local function rot(cf: CFrame): CFrame
	return cf - cf.Position
end

-- 이 기둥의 물 높이와 땅 높이 (물이 없으면 nil)
local function waterAt(x: number, z: number): (number?, number)
	local h = Land.height(x, z)
	return Land.water(x, z, h), h
end

-- 땅 기울기 (가장 가파른 쪽 높이차 / 거리)
local function slope(x: number, z: number): number
	local d = 2
	local hx = surf(x + d, z) - surf(x - d, z)
	local hz = surf(x, z + d) - surf(x, z - d)
	return sqrt(hx * hx + hz * hz) / (2 * d)
end

-- 비움 자리 ---------------------------------------------------------------------------------
-- 전송진(9 + 표석), 과업 자리·영맥(7 + 받침), 비급 자리. 이 안에는 아무것도 두지 않는다.

local function inArea(x: number, z: number): boolean
	return x > -980 and x < 480 and z > -1960 and z < -330
end

local CLEAR: { { number } } = {}
local function initClear()
	table.clear(CLEAR)
	for _, s in Sites.WAYPOINTS do
		if not s.sky and inArea(s.x, s.z) then
			table.insert(CLEAR, { s.x, s.z, 12 })
		end
	end
	for _, s in Sites.TASK do
		if inArea(s.x, s.z) then
			-- 성대는 허브가 짓는 단이 넓다 (단 + 비석)
			table.insert(CLEAR, { s.x, s.z, if string.find(s.id, "^star_") then 17 else 10 })
		end
	end
	for _, s in Sites.VEINS do
		if not s.sky and not s.volcano and inArea(s.x, s.z) then
			table.insert(CLEAR, { s.x, s.z, (s.radius or 7) + 3 })
		end
	end
	for _, m in Sites.MANUALS do
		if not m.sky and inArea(m[1], m[2]) then
			table.insert(CLEAR, { m[1], m[2], 4 })
		end
	end
end

local function clearOf(x: number, z: number, r: number): boolean
	for _, c in CLEAR do
		local dx, dz = x - c[1], z - c[2]
		local rr = c[3] + r
		if dx * dx + dz * dz < rr * rr then
			return false
		end
	end
	return true
end

-- 길 (돌길과 깎은 길): 나무와 바위는 길 위에 두지 않는다
local ROADS = {}
for _, road in Land.ROADS do
	table.insert(ROADS, Land.poly(road))
end
for _, bench in Land.BENCHES do
	table.insert(ROADS, bench)
end
local function nearRoad(x: number, z: number, w: number): boolean
	for _, p in ROADS do
		if Land.polyDist(x, z, p, w) < w then
			return true
		end
	end
	return false
end

-- 놓은 자리 (겹치지 않게): 칸마다 { x, z, r }
local CELL = 16
local taken: { [number]: { { number } } } = {}
local function cellKey(i: number, j: number): number
	return i * 65536 + j
end
local function reserve(x: number, z: number, r: number)
	local k = cellKey(floor(x / CELL), floor(z / CELL))
	local list = taken[k]
	if not list then
		list = {}
		taken[k] = list
	end
	table.insert(list, { x, z, r })
end
local function isFree(x: number, z: number, r: number): boolean
	local i0, j0 = floor(x / CELL), floor(z / CELL)
	for i = i0 - 2, i0 + 2 do
		for j = j0 - 2, j0 + 2 do
			local list = taken[cellKey(i, j)]
			if list then
				for _, q in list do
					local dx, dz = x - q[1], z - q[2]
					local rr = r + q[3]
					if dx * dx + dz * dz < rr * rr then
						return false
					end
				end
			end
		end
	end
	return true
end
-- 큰 네모 자리를 원 여럿으로 잡아 둔다
local function reserveRect(cf: CFrame, sx: number, sz: number)
	local step = 10
	local nx, nz = max(1, math.ceil(sx / step)), max(1, math.ceil(sz / step))
	local r = sqrt((sx / nx) ^ 2 + (sz / nz) ^ 2) / 2
	for i = 0, nx - 1 do
		for j = 0, nz - 1 do
			local p = cf:PointToWorldSpace(Vector3.new(-sx / 2 + (i + 0.5) * sx / nx, 0, -sz / 2 + (j + 0.5) * sz / nz))
			reserve(p.X, p.Z, r)
		end
	end
end
-- a→b 선을 따라 자리를 잡는다 (다리, 길)
local function reserveLine(a: Vector3, b: Vector3, r: number)
	local n = max(1, math.ceil((b - a).Magnitude / r))
	for k = 0, n do
		local p = a:Lerp(b, k / n)
		reserve(p.X, p.Z, r)
	end
end

-- 둘레 안에서 조건(ok)을 지나는 자리 n 곳 (서로 spacing 떨어지게)
type Spot = { x: number, z: number, h: number }
local function scatter(
	rng,
	cx: number,
	cz: number,
	radius: number,
	n: number,
	spacing: number,
	ok: (number, number, number) -> boolean,
	tries: number?
): { Spot }
	local out = {}
	for _ = 1, tries or n * 10 do
		if #out >= n then
			break
		end
		local a, r = rng(0, TAU), radius * sqrt(rng(0, 1))
		local x, z = cx + cos(a) * r, cz + sin(a) * r
		if isFree(x, z, spacing) and clearOf(x, z, spacing) then
			local h = surf(x, z)
			if ok(x, z, h) then
				reserve(x, z, spacing)
				table.insert(out, { x = x, z = z, h = h })
			end
		end
	end
	return out
end

-- 마른 땅인가 (물이 없고 길이 아니다)
local function dry(x: number, z: number, roadW: number?): boolean
	if waterAt(x, z) ~= nil then
		return false
	end
	return not nearRoad(x, z, roadW or 6)
end

-- 나무·풀 ---------------------------------------------------------------------------------

local function jitter(color: Color3, rng, amount: number): Color3
	local k = 1 + rng(-amount, amount)
	return Color3.new(math.clamp(color.R * k, 0, 1), math.clamp(color.G * k, 0, 1), math.clamp(color.B * k, 0, 1))
end

-- 비탈에서도 뿌리가 땅에 박히게: 둘레 가장 낮은 땅
local function foot(x: number, z: number, r: number?): Vector3
	local lo = span(x, z, r or 1.2)
	return Vector3.new(x, lo + 0.15, z)
end

-- 전나무: 사각뿔 층을 겹친다. snow (0~1) 가 클수록 위층부터 눈을 인다
local function fir(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "전나무"
	m.Parent = parent
	local height = opts.height or rng(14, 22)
	local snow = opts.snow or 0
	local tw = height * 0.065
	beam(m, "Trunk", base - Vector3.new(0, 0.8, 0), base + Vector3.new(0, height * 0.5, 0), tw, tw, P.bark, M.Wood)
	local tiers = opts.tiers or (if height > 15 then 4 else 3)
	local yaw = rng(0, math.pi / 2)
	local lean = Vector3.new(rng(-0.03, 0.03), 0, rng(-0.03, 0.03)) * height
	for i = 1, tiers do
		local t = (i - 1) / tiers
		local w = height * (0.54 - 0.36 * t) * rng(0.9, 1.08)
		local h = height * 0.36
		local y = height * (0.13 + 0.68 * t)
		local green = jitter(FIR_GREEN[1 + i % 3], rng, 0.05)
		local color, mat = green, M.LeafyGrass
		if snow > 0 then
			-- 위층은 눈을 이고, 아래층은 서리만 (층마다 번갈아 희게)
			local s = snow * (if i == tiers then 1 elseif (tiers - i) % 2 == 1 then 0.35 else 0.8)
			if s > 0.6 then
				color, mat = NC.snow:Lerp(green, 0.12), M.Snow
			else
				color = green:Lerp(NC.snowShade, s)
			end
		end
		Build.pyramid(m, "Needles", base + lean * t + Vector3.new(0, y, 0), w, h, yaw + i * 0.45, color, mat, true)
	end
	return m
end

local function pine(parent: Instance, x: number, z: number, rng, opts)
	return Build.pine(parent, foot(x, z, 1.5), rng, opts)
end
local function birch(parent: Instance, x: number, z: number, rng, opts)
	opts = opts or {}
	opts.name = "자작나무"
	opts.bark = P.barkBirch
	opts.leaves = BIRCH_LEAVES
	opts.height = opts.height or rng(11, 15)
	opts.blobs = opts.blobs or 6
	return Build.broadleaf(parent, foot(x, z, 1.2), rng, opts)
end
local function maple(parent: Instance, x: number, z: number, rng, opts)
	opts = opts or {}
	opts.name = "단풍나무"
	opts.leaves = MAPLE_LEAVES
	opts.height = opts.height or rng(9, 12)
	opts.blobs = opts.blobs or 6
	return Build.broadleaf(parent, foot(x, z, 1.2), rng, opts)
end
local function shrub(parent: Instance, x: number, z: number, rng, opts)
	return Build.shrub(parent, foot(x, z, 1) - Vector3.new(0, 0.3, 0), rng, opts)
end

-- 꽃 무더기: 낮은 잎 덩이 하나에 꽃 송이 셋 (덤불보다 싸다)
local function flowers(parent: Instance, x: number, z: number, rng, color: Color3)
	local m = Kit.model(parent, "꽃")
	local g = span(x, z, 1.2)
	local s = rng(2.2, 3.2)
	deco(block(m, "Ip", Vector3.new(s, s * 0.32, s * 0.85), CFrame.new(x, g + s * 0.1, z) * CFrame.Angles(rng(-0.1, 0.1), rng(0, TAU), rng(-0.1, 0.1)), jitter(P.leaf, rng, 0.08), M.LeafyGrass))
	for _ = 1, 3 do
		local a, r = rng(0, TAU), rng(0, s * 0.35)
		local f = deco(block(m, "Kkot", Vector3.new(0.55, 0.35, 0.55), CFrame.new(x + cos(a) * r, g + s * 0.27 + rng(0, 0.15), z + sin(a) * r) * CFrame.Angles(0, rng(0, 3), 0), jitter(color, rng, 0.08), M.SmoothPlastic))
		f.CastShadow = false
	end
	return m
end

-- 바위 무더기 (비탈이면 낮은 쪽에 반쯤 묻는다). snow 면 이끼 대신 눈을 얹는다
local function rocks(parent: Instance, x: number, z: number, size: number, rng, opts)
	opts = opts or {}
	local lo = span(x, z, size * 0.4)
	local m = Build.rocks(parent, Vector3.new(x, lo - size * 0.08, z), size, rng, {
		color = opts.color or NC.rock,
		material = opts.material or M.Slate,
		count = opts.count,
		moss = if opts.snow then false else opts.moss,
	})
	if opts.snow then
		local main = m:FindFirstChild("Rock") :: BasePart?
		if main then
			block(
				m,
				"Nun",
				Vector3.new(main.Size.X * 0.84, 0.5, main.Size.Z * 0.8),
				main.CFrame * CFrame.new(0, main.Size.Y / 2 + 0.1, 0) * CFrame.Angles(0, rng(-0.3, 0.3), 0),
				NC.snow,
				M.Snow
			)
		end
	end
	if opts.wet then
		for _, p in m:GetChildren() do
			if p:IsA("BasePart") and p.Name == "Rock" then
				p.Reflectance = 0.08
			end
		end
	end
	return m
end

-- 땅을 따라 기운 판 (조약돌 물가, 디딤돌): 네 귀 높이의 평균 평면에 윗면을 맞춘다
local function groundSlab(
	parent: Instance,
	name: string,
	x: number,
	z: number,
	len: number,
	wid: number,
	yaw: number,
	t: number,
	color: Color3,
	material: Enum.Material,
	lift: number?
)
	local dir = Vector3.new(sin(yaw), 0, cos(yaw))
	local side = Vector3.new(dir.Z, 0, -dir.X)
	local function h(p: Vector3): number
		return surf(p.X, p.Z)
	end
	local c = Vector3.new(x, 0, z)
	local hf, hb = h(c + dir * len / 2), h(c - dir * len / 2)
	local hl, hr = h(c + side * wid / 2), h(c - side * wid / 2)
	local y = (hf + hb + hl + hr) / 4 + (lift or 0.12)
	local Z = (dir * len + Vector3.new(0, hf - hb, 0)).Unit
	local X = (side * wid + Vector3.new(0, hl - hr, 0)).Unit
	local Y = Z:Cross(X).Unit
	if Y.Y < 0 then
		Y = -Y
	end
	X = Y:Cross(Z).Unit
	return block(parent, name, Vector3.new(wid, t, len), CFrame.fromMatrix(Vector3.new(x, y - t / 2, z), X, Y), color, material)
end

-- 축대: 비탈 위에 평평한 돌 단. 윗면 = 가장 높은 땅 + lift. 윗면 높이를 돌려준다
local function terrace(parent: Instance, cf: CFrame, sx: number, sz: number, lift: number?, color: Color3?): number
	local lo, hi = rectSpan(cf, sx, sz)
	local top = hi + (lift or 0.4)
	local depth = top - lo + 2
	block(
		parent,
		"Chukdae",
		Vector3.new(sx, depth, sz),
		CFrame.new(cf.X, top - depth / 2, cf.Z) * rot(cf),
		color or Color3.fromRGB(150, 142, 128),
		M.Cobblestone
	)
	-- 갑석: 윗가장자리 장대석 띠
	block(parent, "Gapseok", Vector3.new(sx + 0.4, 0.5, sz + 0.4), CFrame.new(cf.X, top - 0.25, cf.Z) * rot(cf), P.granite, M.Granite)
	return top
end

-- 명경호 ---------------------------------------------------------------------------------

local LAKE = Land.LAKE
local ISLET = Land.ISLET

-- 그 방향(도, 0 = 동쪽 +x, 90 = 남쪽 +z) 물가 반지름: 섬 너머에서 땅이 수면(-1) 위로 올라오는 곳
local shoreCache: { [number]: number } = {}
local function shoreR(deg: number): number
	local key = floor(deg + 0.5) % 360
	local cached = shoreCache[key]
	if cached then
		return cached
	end
	local a = rad(key)
	local c, s = cos(a), sin(a)
	local found = 260
	for r = 125, 262, 1 do
		if Land.height(LAKE.x + c * r, LAKE.z + s * r) > -1 then
			found = r
			break
		end
	end
	shoreCache[key] = found
	return found
end
-- 물가에서 off 만큼 뭍(+) 또는 물(-) 쪽 자리
local function lakeXZ(deg: number, off: number): (number, number)
	local r = shoreR(deg) + off
	local a = rad(deg)
	return LAKE.x + cos(a) * r, LAKE.z + sin(a) * r
end

-- 경심정: 섬 가운데는 영맥(허브). 정자는 북서쪽(비류폭 쪽) 물 위 돌 단에, 구곡교는 남쪽 물가에서
local PAVILION_DIR = Vector3.new(-222, 0, -112).Unit -- 섬에서 폭포 쪽
local BRIDGE_PTS = {
	Vector3.new(-46, 0, -521),
	Vector3.new(-54, 0, -530),
	Vector3.new(-38, 0, -546),
	Vector3.new(-54, 0, -562),
	Vector3.new(-38, 0, -578),
	Vector3.new(-46, 0, -587),
}
local DECK = 1.5 -- 다리 마루 윗면 (수면 -1)

local function buildBridge(F: Instance, rng)
	local m = Kit.model(F, "구곡교")
	local railColor = P.seokganju
	local pts = BRIDGE_PTS
	local width = 3.4
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local d = (b - a)
		local len = d.Magnitude
		local dir = d / len
		local side = Vector3.new(-dir.Z, 0, dir.X)
		local mid = (a + b) / 2
		local look = face(Vector3.new(mid.X, DECK - 0.25, mid.Z), Vector3.new(b.X, DECK - 0.25, b.Z))
		-- 마루: 이음매에서 겹치도록 너비만큼 길게
		block(m, "Maru", Vector3.new(width, 0.5, len + width * 0.9), look, P.woodDark, M.WoodPlanks)
		for _, s in { 1, -1 } do
			block(m, "Yeonggwi", Vector3.new(0.35, 0.6, len), look * CFrame.new(s * (width / 2 + 0.1), -0.25, 0), P.wood, M.Wood)
		end
		-- 난간: 이음매 가까이는 비워 둔다 (돌아 나가는 자리)
		local inset = 2.2
		local ra, rb = a + dir * inset, b - dir * inset
		local n = max(2, math.ceil((rb - ra).Magnitude / 4.2))
		for _, s in { 1, -1 } do
			local off = side * s * (width / 2 - 0.15)
			local pa, pb = ra + off, rb + off
			beam(m, "Nangan", Vector3.new(pa.X, DECK + 2.4, pa.Z), Vector3.new(pb.X, DECK + 2.4, pb.Z), 0.32, 0.28, railColor, M.Wood)
			beam(m, "Nangan", Vector3.new(pa.X, DECK + 0.9, pa.Z), Vector3.new(pb.X, DECK + 0.9, pb.Z), 0.24, 0.22, railColor, M.Wood)
			for k = 0, n do
				local p = pa:Lerp(pb, k / n)
				local thick = if k == 0 or k == n then 0.46 else 0.34
				beam(m, "Dongja", Vector3.new(p.X, DECK - 0.1, p.Z), Vector3.new(p.X, DECK + 2.75, p.Z), thick, thick, railColor, M.Wood)
			end
		end
		-- 다리 발: 이음매와 긴 마루 가운데에 기둥 둘과 멍에
		local feet = {}
		if i < #pts - 1 then
			table.insert(feet, b)
		end
		if len > 16 then
			table.insert(feet, mid)
		end
		for _, p in feet do
			local bottom = Land.height(p.X, p.Z) - 1
			for _, s in { 1, -1 } do
				local q = p + side * s * 1.3
				beam(m, "Gidung", Vector3.new(q.X, bottom, q.Z), Vector3.new(q.X, DECK - 0.5, q.Z), 0.55, 0.55, P.woodDark, M.Wood)
			end
			local e1, e2 = p + side * 2, p - side * 2
			beam(m, "Meongye", Vector3.new(e1.X, DECK - 0.75, e1.Z), Vector3.new(e2.X, DECK - 0.75, e2.Z), 0.5, 0.5, P.wood, M.Wood)
		end
		reserveLine(a, b, 4)
	end
	-- 두 끝: 돌 받침과 디딤돌
	for idx, p in { pts[1], pts[#pts] } do
		local h = Land.height(p.X, p.Z)
		local nextP = if idx == 1 then pts[2] else pts[#pts - 1]
		local look = face(Vector3.new(p.X, 0, p.Z), Vector3.new(nextP.X, 0, nextP.Z))
		local bottom = min(h, DECK) - 2.5
		block(
			m,
			"Batchim",
			Vector3.new(width + 1.6, DECK - 0.4 - bottom, 3),
			CFrame.new(p.X, (DECK - 0.4 + bottom) / 2, p.Z) * rot(look),
			P.granite,
			M.Granite
		)
		-- 뭍 쪽으로 계단 (땅이 마루보다 높거나 낮으면)
		local away = -look.LookVector
		for k = 1, 3 do
			local q = Vector3.new(p.X, 0, p.Z) + away * (1.5 + k * 1.4)
			local g = surf(q.X, q.Z)
			if k > 1 and abs(g - DECK) < 0.6 then
				break
			end
			local stepTop = DECK + (g - DECK) * (k / 3)
			block(
				m,
				"Didim",
				Vector3.new(width + 0.6, stepTop - g + 1.2, 1.5),
				CFrame.new(q.X, (stepTop + g - 1.2) / 2, q.Z) * rot(look),
				P.granite,
				M.Granite
			)
		end
	end
	-- 물가 들머리 청사초롱 둘
	local a, b = pts[1], pts[2]
	local dir = (b - a).Unit
	local side = Vector3.new(-dir.Z, 0, dir.X)
	for _, s in { 1, -1 } do
		local p = a - dir * 4 + side * s * 3.4
		Build.chorong(m, Vector3.new(p.X, surf(p.X, p.Z), p.Z), a - dir * 4)
	end
	return m
end

local function buildIslet(F: Instance, rng)
	local m = Kit.model(F, "경심정 섬")
	local cx, cz = ISLET.x, ISLET.z
	local top = surf(cx, cz) -- 2.5
	local toBridgeDir = (BRIDGE_PTS[#BRIDGE_PTS] - Vector3.new(cx, 0, cz)).Unit
	-- 호안: 섬 둘레 장대석 띠 (다리 들머리와 정자 쪽은 비운다)
	local n = 16
	for k = 0, n - 1 do
		local a = (k + 0.5) / n * TAU
		local dir = Vector3.new(cos(a), 0, sin(a))
		if dir:Dot(toBridgeDir) < 0.93 and dir:Dot(PAVILION_DIR) < 0.9 then
			local r = 19.2
			local p = Vector3.new(cx, 0, cz) + dir * r
			local g = surf(p.X, p.Z)
			local look = face(p, p + Vector3.new(-dir.Z, 0, dir.X))
			local len = TAU * r / n + 0.4
			block(
				m,
				"Hoan",
				Vector3.new(1.3, top + 0.35 - (g - 1.6), len),
				CFrame.new(p.X, (top + 0.35 + g - 1.6) / 2, p.Z) * rot(look),
				P.granite:Lerp(P.graniteDark, (k % 3) / 4),
				M.Granite
			)
		end
	end
	-- 물가 바위와 갈대 (호안 바깥)
	for k = 0, 6 do
		local a = k / 7 * TAU + rng(-0.2, 0.2)
		local dir = Vector3.new(cos(a), 0, sin(a))
		if dir:Dot(toBridgeDir) < 0.85 and dir:Dot(PAVILION_DIR) < 0.75 then
			local p = Vector3.new(cx, 0, cz) + dir * rng(21.5, 24)
			if k % 3 == 0 then
				Build.reeds(m, Vector3.new(p.X, Land.height(p.X, p.Z), p.Z), rng, { count = 6, radius = 1.8 })
			else
				rocks(m, p.X, p.Z, rng(2.2, 3.8), rng, { count = 1, wet = true })
			end
		end
	end
	-- 물 위로 기운 소나무 (동쪽 물가)
	local pd = Vector3.new(0.9, 0, -0.42).Unit
	local pp = Vector3.new(cx, 0, cz) + pd * 18.4
	Build.pine(m, Vector3.new(pp.X, top - 0.2, pp.Z), rng, { height = 15, tiers = 5 })
	-- 정자 돌 단: 물 위에 장대석으로 쌓는다
	local pc = Vector3.new(cx, 0, cz) + PAVILION_DIR * 27.5
	local platTop = top + 0.8
	local look = face(Vector3.new(pc.X, platTop, pc.Z), Vector3.new(cx, platTop, cz)) -- 앞이 섬 가운데
	local S = 18
	local bottom = Land.height(pc.X, pc.Z) - 3
	block(
		m,
		"Seokdan",
		Vector3.new(S, platTop - 0.5 - bottom, S),
		CFrame.new(pc.X, (platTop - 0.5 + bottom) / 2, pc.Z) * rot(look),
		Color3.fromRGB(150, 146, 136),
		M.Granite
	)
	block(m, "Gapseok", Vector3.new(S + 0.6, 0.55, S + 0.6), look * CFrame.new(0, -0.27, 0), P.graniteDark, M.Granite)
	-- 물 닿는 곳 띠 (젖은 돌)
	block(m, "Multti", Vector3.new(S + 0.12, 1.1, S + 0.12), CFrame.new(pc.X, -1.2, pc.Z) * rot(look), Color3.fromRGB(96, 98, 92), M.Granite)
	-- 섬에서 오르는 디딤돌
	for k = 0, 1 do
		local q = (look * CFrame.new(0, 0, -S / 2 - 0.8 - k * 1.3)).Position
		local g = surf(q.X, q.Z)
		local y = platTop - 0.45 * (k + 1)
		block(m, "Didim", Vector3.new(5, y - g + 1, 1.3), CFrame.new(q.X, (y + g - 1) / 2, q.Z) * rot(look), P.granite, M.Granite)
	end
	-- 정자: 사모지붕 정자 (2칸 × 2칸)
	local pav, info = Build.pavilion(m, look, { bays = { 2, 2 }, bay = 5.2, pillarH = 7.6, plinth = 1.7, eave = 3.8, name = "경심정", detail = 2, bands = 3 })
	-- 현판: 앞 처마 밑 창방에
	local D = info.depth
	local boardY = 1.7 + 7.6 - 1.1 - 0.95
	local board = block(pav, "Hyeonpan", Vector3.new(4.4, 1.5, 0.25), look * CFrame.new(0, boardY, -D / 2 - 0.62), P.meok, M.Wood)
	block(pav, "Te", Vector3.new(4.9, 1.95, 0.2), look * CFrame.new(0, boardY, -D / 2 - 0.5), P.hwang, M.Wood)
	Kit.engrave(board, "경심정", "Front", false, "gold")
	-- 돌 단 앞 귀에 석등 둘
	for _, s in { 1, -1 } do
		local q = (look * CFrame.new(s * (S / 2 - 1.6), 0, -S / 2 + 1.6)).Position
		Build.stoneLantern(m, Vector3.new(q.X, platTop, q.Z))
	end
	reserve(cx, cz, 24)
	reserveRect(look, S + 2, S + 2)
	return m
end

-- 수 오행처 물가 바위: 자리(허브 받침) 둘레에 바위를 반달로 두르고, 호수 쪽으로 너럭바위 층계를 내린다
local function buildWaterSite(F: Instance, rng)
	local site = Sites.byId.el_water
	local m = Kit.model(F, "물가 바위")
	local sx, sz = site.x, site.z
	local toLake = Vector3.new(LAKE.x - sx, 0, LAKE.z - sz).Unit
	local toHome = Vector3.new(-sx, 0, -sz).Unit -- 허브 비석이 서는 쪽
	local center = Vector3.new(sx, 0, sz)
	local lakeA = math.atan2(toLake.Z, toLake.X)
	-- 반달 바위: 뭍 쪽 (호수와 비석 쪽은 비운다)
	local count = 9
	for k = 0, count - 1 do
		local a = lakeA + rad(70) + k * rad(220 / (count - 1))
		local dir = Vector3.new(cos(a), 0, sin(a))
		if dir:Dot(toHome) < 0.82 then
			local r = 13.6 + rng(-0.4, 1.2)
			local p = center + dir * r
			local size = if k % 3 == 1 then rng(5.5, 7) else rng(3, 4.6)
			rocks(m, p.X, p.Z, size, rng, { count = if size > 5 then 2 else 1, color = Color3.fromRGB(128, 124, 116) })
		end
	end
	-- 선 바위 둘 (오행처 표지: 물빛 이끼)
	for _, s in { -1, 1 } do
		local a = lakeA + s * rad(58)
		local p = center + Vector3.new(cos(a), 0, sin(a)) * 13.5
		local lo = span(p.X, p.Z, 1.5)
		local h = rng(7, 9)
		block(
			m,
			"Seonbawi",
			Vector3.new(2.6, h, 2.2),
			CFrame.new(p.X, lo + h / 2 - 1, p.Z) * CFrame.Angles(rng(-0.06, 0.06), rng(0, 3), rng(-0.08, 0.08)),
			Color3.fromRGB(112, 116, 118),
			M.Slate
		)
		block(m, "Ikki", Vector3.new(2.8, 0.4, 2.4), CFrame.new(p.X, lo + h - 1.1, p.Z) * CFrame.Angles(0, rng(0, 3), 0), Color3.fromRGB(80, 120, 110), M.LeafyGrass)
	end
	-- 자리 둘레 박석: 받침(허브) 밖 호수 쪽에 땅에 붙은 넓적한 돌 판 (비움 자리 안이라 낮게)
	local side = Vector3.new(-toLake.Z, 0, toLake.X)
	local lakeYaw = math.atan2(toLake.X, toLake.Z)
	for k = -1, 1 do
		local p = center + toLake * 10 + side * k * 4.6
		groundSlab(m, "Bakseok", p.X, p.Z, rng(4.2, 5), rng(4, 4.6), lakeYaw + rng(-0.2, 0.2), 0.6, Color3.fromRGB(158, 152, 142), M.Slate, 0.22)
	end
	-- 너럭바위 층계: 박석 끝에서 물가까지 (양옆에 받친 돌)
	local d = 13.6
	local steps = 0
	while d < 26 and steps < 6 do
		local p = center + toLake * d + side * rng(-1, 1)
		local g = surf(p.X, p.Z)
		local w = rng(11, 13) - steps * 0.8
		if steps % 2 == 0 then
			local q = p + side * (if steps % 4 == 0 then 1 else -1) * (w / 2 + 1.2)
			rocks(m, q.X, q.Z, rng(2.4, 3.4), rng, { count = 0, moss = false, color = Color3.fromRGB(128, 124, 116) })
		end
		local depth = rng(3.6, 4.6)
		local yaw = math.atan2(toLake.X, toLake.Z) + rng(-0.15, 0.15)
		local look = CFrame.new(p.X, 0, p.Z) * CFrame.Angles(0, yaw, 0)
		-- 윗면은 그 자리 높은 쪽 땅에 맞추고 아래로 깊게 묻는다
		local _, hi = rectSpan(look, w, depth)
		local topY = max(hi + 0.25, -0.6)
		block(
			m,
			"Neoreok",
			Vector3.new(w, topY - g + 2.5, depth),
			CFrame.new(p.X, (topY + g - 2.5) / 2, p.Z) * rot(look) * CFrame.Angles(0, 0, rng(-0.03, 0.03)),
			Color3.fromRGB(150, 144, 134):Lerp(NC.wetRock, steps / 8),
			M.Slate
		)
		d += depth * 0.92
		steps += 1
		if g < -1.5 then
			break
		end
	end
	-- 물에 반쯤 잠긴 큰 바위 (물가 바위)
	local wp = center + toLake * (d + 3) + side * 5
	rocks(m, wp.X, wp.Z, 7, rng, { count = 2, wet = true, color = Color3.fromRGB(106, 104, 100) })
	local wp2 = center + toLake * (d + 1) - side * 7
	rocks(m, wp2.X, wp2.Z, 4.2, rng, { count = 1, wet = true })
	-- 물 위로 기운 소나무와 갈대
	local tp = center + toLake * 9 - side * 15
	Build.pine(m, foot(tp.X, tp.Z, 1.5), rng, { height = 17 })
	local rp = center + toLake * (d + 1) + side * 12
	Build.reeds(m, Vector3.new(rp.X, Land.height(rp.X, rp.Z), rp.Z), rng, { count = 7 })
	reserve(sx, sz, 16)
	local far = center + toLake * 18
	reserve(far.X, far.Z, 9)
	return m
end

-- 고깃배 (나룻배): cf 는 수면 가운데, 앞(-Z)이 이물
local function boat(parent: Instance, cf: CFrame)
	local m = Kit.model(parent, "나룻배")
	local hull = Color3.fromRGB(112, 82, 56)
	local L = 9
	block(m, "Bada", Vector3.new(2.6, 0.35, L), cf * CFrame.new(0, -0.45, 0), hull, M.WoodPlanks)
	for _, s in { 1, -1 } do
		block(m, "Panja", Vector3.new(0.3, 1.2, L), cf * CFrame.new(s * 1.45, 0.05, 0) * CFrame.Angles(0, 0, s * rad(-12)), hull, M.WoodPlanks)
	end
	-- 이물과 고물: 밑이 들린 쐐기 (뒤집어 놓는다)
	wedge(m, "Imul", Vector3.new(3.2, 1.3, 2.4), cf * CFrame.new(0, 0.05, -L / 2 - 1.1) * CFrame.Angles(0, 0, math.pi), hull, M.WoodPlanks)
	wedge(m, "Gomul", Vector3.new(3.2, 1.3, 1.6), cf * CFrame.new(0, 0.05, L / 2 + 0.7) * CFrame.Angles(0, math.pi, math.pi), hull, M.WoodPlanks)
	for _, z in { -2, 1.8 } do
		block(m, "Gamut", Vector3.new(2.9, 0.25, 0.8), cf * CFrame.new(0, 0.3, z), P.woodDark, M.Wood)
	end
	-- 노와 삿대, 그물 뭉치
	beam(m, "No", (cf * CFrame.new(1.2, 0.6, 2.5)).Position, (cf * CFrame.new(2.6, -0.6, 6.5)).Position, 0.22, 0.22, P.wood, M.Wood)
	beam(m, "Satdae", (cf * CFrame.new(-0.8, 0.35, -3)).Position, (cf * CFrame.new(-0.9, 0.55, 4.5)).Position, 0.18, 0.18, P.woodDark, M.Wood)
	block(m, "Geumul", Vector3.new(1.6, 0.4, 1.4), cf * CFrame.new(0.2, 0.25, 0.2), NC.net, M.Fabric)
	return m
end

-- 덕장: 고기 말리는 시렁 (A자 틀 둘 + 가로대 + 매단 고기)
local function dryingRack(parent: Instance, cf: CFrame, rng)
	local m = Kit.model(parent, "덕장")
	local L = 7
	for _, s in { -1, 1 } do
		for _, f in { -1, 1 } do
			beam(m, "Gaji", (cf * CFrame.new(s * L / 2, -0.4, f * 1.4)).Position, (cf * CFrame.new(s * L / 2, 4.2, 0)).Position, 0.3, 0.3, P.wood, M.Wood)
		end
	end
	beam(m, "Garodae", (cf * CFrame.new(-L / 2 - 0.3, 4, 0)).Position, (cf * CFrame.new(L / 2 + 0.3, 4, 0)).Position, 0.25, 0.25, P.woodDark, M.Wood)
	for k = 1, 6 do
		local x = -L / 2 + k * L / 7
		local fish = block(
			m,
			"Gogi",
			Vector3.new(0.45, 1.6, 0.2),
			cf * CFrame.new(x, 3.05, 0) * CFrame.Angles(0, rng(-0.4, 0.4), rng(-0.08, 0.08)),
			Color3.fromRGB(150, 128, 92):Lerp(Color3.fromRGB(110, 96, 80), rng(0, 1)),
			M.SmoothPlastic
		)
		deco(fish)
	end
	-- 그물 한 폭
	local net = block(m, "Geumul", Vector3.new(L * 0.6, 2.2, 0.08), cf * CFrame.new(-0.8, 2.7, 0.35), NC.net, M.Fabric)
	net.Transparency = 0.35
	deco(net)
	return m
end

-- 어부의 집: 남쪽 물가 평평한 언덕. 마당, 울타리, 장독대, 덕장, 수레, 물가 나루와 배
local HOME = Vector3.new(4, 0, -495)
local function buildHomestead(F: Instance, rng)
	local m = Kit.model(F, "어부의 집")
	local look0 = face(HOME, HOME + Vector3.new(-0.15, 0, -1)) -- 앞이 호수(북)
	local yardCf = look0 * CFrame.new(0, 0, -3)
	local top = terrace(m, look0 * CFrame.new(0, 0, 1.5), 22, 16, 0.3)
	local houseCf = CFrame.new(HOME.X, top, HOME.Z) * rot(look0) * CFrame.new(0, 0, 3.5)
	local _, info = Build.house(m, houseCf, { bays = { 3, 2 }, bay = 4.4, pillarH = 7, plinth = 1.3, eave = 3.2, detail = 0, roof = "gable", bands = 3, name = "어부의 집" })
	-- 마당 둘레 싸리 울타리 (앞은 열고, 옆과 뒤)
	local W, Dp = 26, 30
	local function yp(x: number, z: number): Vector3
		local p = (yardCf * CFrame.new(x, 0, z)).Position
		return Vector3.new(p.X, surf(p.X, p.Z), p.Z)
	end
	Build.fence(m, { yp(-W / 2 + 6, -Dp / 2), yp(-W / 2, -Dp / 2), yp(-W / 2, Dp / 2 - 6) })
	Build.fence(m, { yp(W / 2 - 6, -Dp / 2), yp(W / 2, -Dp / 2), yp(W / 2, -Dp / 2 + 10) })
	-- 마당: 다진 흙 판과 평상
	groundSlab(m, "Madang", (yardCf * CFrame.new(0, 0, -8)).Position.X, (yardCf * CFrame.new(0, 0, -8)).Position.Z, 14, 18, math.atan2(look0.LookVector.X, look0.LookVector.Z), 0.5, Color3.fromRGB(150, 126, 96), M.Ground, 0.12)
	local pp = (yardCf * CFrame.new(5, 0, -8)).Position
	local pg = surf(pp.X, pp.Z)
	local pcf = CFrame.new(pp.X, pg, pp.Z) * rot(look0) * CFrame.Angles(0, 0.1, 0)
	block(m, "Pyeongsang", Vector3.new(5, 0.35, 3.6), pcf * CFrame.new(0, 1.6, 0), P.wood, M.WoodPlanks)
	for _, sx in { -1, 1 } do
		for _, sz in { -1, 1 } do
			block(m, "Dari", Vector3.new(0.35, 1.6, 0.35), pcf * CFrame.new(sx * 2.2, 0.75, sz * 1.5), P.woodDark, M.Wood)
		end
	end
	-- 장독대 (집 옆 뒤꼍)
	local jp = (houseCf * CFrame.new(info.width / 2 + 5.2, 0, 2)).Position
	Build.jars(m, CFrame.new(jp.X, surf(jp.X, jp.Z), jp.Z) * rot(look0) * CFrame.Angles(0, math.pi / 2, 0), rng, 6)
	-- 덕장 (마당 서쪽)
	local dp = (yardCf * CFrame.new(-8, 0, -9)).Position
	dryingRack(m, CFrame.new(dp.X, surf(dp.X, dp.Z), dp.Z) * rot(look0) * CFrame.Angles(0, 0.3, 0), rng)
	-- 수레 (마당 동쪽)
	local cp = (yardCf * CFrame.new(9, 0, -6)).Position
	Build.cart(m, CFrame.new(cp.X, surf(cp.X, cp.Z), cp.Z) * rot(look0) * CFrame.Angles(0, 2.4, 0))
	-- 감나무 한 그루 (뒤꼍)
	local tp = (houseCf * CFrame.new(-info.width / 2 - 4, 0, 9)).Position
	Build.broadleaf(m, foot(tp.X, tp.Z), rng, { height = 12, name = "감나무", leaves = { P.leafDeep, P.leaf, Color3.fromRGB(170, 150, 70) } })
	-- 나루: 물가에서 북쪽으로 내민 널 마루
	local d0 = Vector3.new(16, 0, -531)
	local d1 = Vector3.new(14, 0, -553)
	local dlook = face(d0, d1)
	local dlen = (d1 - d0).Magnitude
	local dy = 0.55
	for _, s in { -1.15, 0, 1.15 } do
		block(
			m,
			"Neol",
			Vector3.new(1.05, 0.3, dlen),
			CFrame.new((d0 + d1) / 2 + Vector3.new(0, dy, 0)) * rot(dlook) * CFrame.new(s, 0, 0),
			Color3.fromRGB(120, 90, 62):Lerp(P.woodDark, abs(s) / 3),
			M.WoodPlanks
		)
	end
	for k = 0, 3 do
		local p = d0:Lerp(d1, (k + 0.3) / 3.4)
		local bottom = Land.height(p.X, p.Z) - 1.2
		for _, s in { -1, 1 } do
			local q = (CFrame.new(p) * rot(dlook) * CFrame.new(s * 1.6, 0, 0)).Position
			cyl(m, "Malttuk", Vector3.new(q.X, bottom, q.Z), Vector3.new(q.X, dy + (if k == 3 then 1.6 else 0.1), q.Z), 0.6, P.woodDark, M.Wood)
		end
		local e = CFrame.new(p) * rot(dlook)
		block(m, "Meongye", Vector3.new(3.8, 0.4, 0.5), e * CFrame.new(0, dy - 0.35, 0), P.wood, M.Wood)
	end
	-- 물가 디딤돌 (뭍에서 나루로)
	local gp = d0 - dlook.LookVector * 1.8
	local gg = surf(gp.X, gp.Z)
	block(m, "Didim", Vector3.new(4, max(0.6, dy + 0.15 - gg + 0.8), 2), CFrame.new(gp.X, (dy + 0.15 + gg - 0.8) / 2, gp.Z) * rot(dlook), P.granite, M.Granite)
	-- 매어 둔 배
	local bp = d1:Lerp(d0, 0.35) + dlook.RightVector * 3.4
	boat(m, CFrame.new(bp.X, -1, bp.Z) * rot(dlook) * CFrame.Angles(0, rng(-0.12, 0.12), 0))
	-- 매는 줄
	local post = (CFrame.new(d1:Lerp(d0, 0.12)) * rot(dlook) * CFrame.new(1.6, dy + 1.4, 0)).Position
	deco(beam(m, "Jul", post, Vector3.new(bp.X - 0.6, 0.2, bp.Z - 3.6), 0.1, 0.1, Color3.fromRGB(190, 170, 130), M.Fabric))
	reserveRect(look0, 30, 34)
	reserveLine(d0, d1, 5)
	return m
end

-- 비류대 길 징검돌 (벽계)
local function buildSteppingStones(F: Instance, rng)
	local m = Kit.model(F, "징검돌")
	local b = Sites.BRIDGES[2]
	local a0 = Vector3.new(b[1], 0, b[2])
	local a1 = Vector3.new(b[3], 0, b[4])
	local dir = (a1 - a0).Unit
	local side = Vector3.new(-dir.Z, 0, dir.X)
	local len = (a1 - a0).Magnitude
	local k = 0
	local d = 2
	while d < len - 1 do
		local p = a0 + dir * d + side * (if k % 2 == 0 then 0.5 else -0.5)
		local w, h = waterAt(p.X, p.Z)
		if w then
			local topY = b[5] + rng(-0.1, 0.15)
			local s = rng(2.6, 3.2)
			block(
				m,
				"Jinggeom",
				Vector3.new(s, topY - h + 1, s * rng(0.85, 1)),
				CFrame.new(p.X, (topY + h - 1) / 2, p.Z) * CFrame.Angles(0, rng(0, TAU), 0),
				Color3.fromRGB(150, 146, 138):Lerp(NC.wetRock, rng(0, 0.4)),
				M.Granite
			)
			k += 1
		end
		d += 3.3
	end
	-- 물가에 갈대와 바위
	for _, s in { -1, 1 } do
		for _, e in { 0, 1 } do
			local base = if e == 0 then a0 + dir * 4 else a1 - dir * 4
			local p = base + side * s * 6
			if waterAt(p.X, p.Z) then
				Build.reeds(m, Vector3.new(p.X, Land.height(p.X, p.Z), p.Z), rng, { count = 5 })
			else
				rocks(m, p.X, p.Z, rng(2, 3), rng, { count = 1 })
			end
		end
	end
	reserveLine(a0, a1, 4)
	return m
end

-- 호숫가: 사람이 드나드는 남쪽·동쪽 물가는 촘촘히, 북쪽은 성기게 (서쪽 벼랑은 폭포 쪽에서).
-- 나무는 두셋씩 덩이로 모으고, 그 발치와 물가 띠를 낮은 덤불 덩이로 메운다 (부품이 적고 땅을 넓게 덮는다)
local function buildLakeShore(F: Instance, rng)
	local m = Kit.folder(F, "호숫가")
	local function okAt(x: number, z: number, r: number): boolean
		return isFree(x, z, r) and clearOf(x, z, r + 2) and not nearRoad(x, z, 6)
	end
	local function plant(kind: string, deg: number, off: number)
		local x, z = lakeXZ(deg, off)
		if not okAt(x, z, if kind == "reeds" or kind == "flowers" then 2.5 else 4.5) then
			return
		end
		reserve(x, z, if kind == "reeds" or kind == "flowers" then 2.5 else 5)
		if kind == "willow" then
			Build.willow(m, foot(x, z, 1.5), rng, { strands = 10, blobs = 4, height = rng(11, 14) })
		elseif kind == "pine" then
			pine(m, x, z, rng, { height = rng(15, 20), tiers = 4 })
		elseif kind == "maple" then
			maple(m, x, z, rng, { blobs = 5, height = rng(10, 13) })
		elseif kind == "birch" then
			birch(m, x, z, rng, { blobs = 4, branches = 2 })
		elseif kind == "reeds" then
			Build.reeds(m, Vector3.new(x, Land.height(x, z), z), rng, { count = 5, radius = 1.8 })
		elseif kind == "flowers" then
			flowers(m, x, z, rng, if rng(0, 1) < 0.5 then NC.azalea else NC.wildY)
		end
	end
	-- 나무 덩이: { 각도, 물가에서 거리, 종류 }
	local clumps = {
		-- 남쪽: 다리 들머리 양옆과 강어귀 (도착하는 곳)
		{ 72, 3, "willow" },
		{ 76, 13, "maple" },
		{ 66, 18, "pine" },
		{ 99, 2.5, "willow" },
		{ 104, 12, "birch" },
		{ 110, 20, "pine" },
		-- 남서 얕은 물가
		{ 122, 2.5, "willow" },
		{ 130, 14, "maple" },
		{ 143, 3, "willow" },
		{ 147, 16, "pine" },
		-- 동쪽 둑: 소나무 숲 덩이
		{ 8, 14, "pine" },
		{ 14, 24, "pine" },
		{ 18, 3, "willow" },
		{ 26, 18, "birch" },
		-- 북동
		{ 306, 16, "birch" },
		{ 312, 24, "pine" },
		{ 338, 20, "pine" },
		{ 344, 12, "birch" },
		-- 북서 (벼랑 아래 물가)
		{ 214, 3, "willow" },
		{ 228, 10, "birch" },
	}
	for _, c in clumps do
		plant(c[3], c[1] + rng(-1.5, 1.5), c[2] + rng(-1.5, 1.5))
	end
	-- 갈대: 얕은 물 (물가에서 2~5 안쪽)
	for _, deg in { 94, 108, 117, 128, 138, 150, 212, 224, 236, 304, 331, 22 } do
		plant("reeds", deg + rng(-1.5, 1.5), -rng(2, 4.5))
	end
	-- 꽃 무더기: 남쪽 물가 둑
	for k = 0, 6 do
		plant("flowers", 62 + k * 13 + rng(-3, 3), rng(6, 16))
	end
	-- 덤불 덩이: 물가 띠를 따라 (남·동은 촘촘히)
	for deg = 0, 359, 7 do
		local south = deg < 160
		if (south or deg % 14 == 0) and not (deg > 156 and deg < 208) then
			local x, z = lakeXZ(deg + rng(-2, 2), rng(4, 12))
			if okAt(x, z, 3) and dry(x, z, 6) then
				reserve(x, z, 3)
				shrub(m, x, z, rng, { size = rng(3.8, 6), blobs = 2, leaves = if rng(0, 1) < 0.4 then FERN_LEAVES else nil })
			end
		end
	end
	-- 조약돌 물가 둘: 물가 띠를 따라 기운 판 + 흩은 돌
	for _, beach in { { 114, 126 }, { 318, 330 } } do
		for deg = beach[1], beach[2], 3 do
			local x, z = lakeXZ(deg, rng(-0.5, 1.5))
			if clearOf(x, z, 3) then
				local a = rad(deg)
				local yaw = math.atan2(-sin(a), cos(a)) + math.pi / 2 -- 물가를 따라 눕힌다
				groundSlab(m, "Jogyak", x, z, rng(5.5, 7.5), rng(3.4, 4.6), yaw + rng(-0.2, 0.2), 0.7, NC.pebble:Lerp(Color3.fromRGB(150, 146, 140), rng(0, 0.6)), M.Pebble, 0.18)
			end
		end
		for k = 0, 2 do
			local px, pz = lakeXZ(beach[1] + (beach[2] - beach[1]) * (k + 0.5) / 3, rng(-1.5, 0.5))
			local s = rng(0.9, 1.6)
			block(m, "Dol", Vector3.new(s, s * 0.6, s * 0.8), CFrame.new(px, Land.height(px, pz) + s * 0.15, pz) * CFrame.Angles(rng(-0.3, 0.3), rng(0, 6), rng(-0.3, 0.3)), NC.pebble:Lerp(NC.darkRock, rng(0, 0.6)), M.Slate)
		end
	end
	-- 물가 바위: 남·동쪽은 촘촘히, 북쪽은 큰 바위 몇
	local function rockAt(deg: number, off: number, size: number)
		local x, z = lakeXZ(deg, off)
		if isFree(x, z, size * 0.6) and clearOf(x, z, size * 0.6) and not nearRoad(x, z, 5) then
			reserve(x, z, size * 0.6)
			rocks(m, x, z, size, rng, { count = if size > 4 then 2 else 0, wet = true, moss = size > 4 })
		end
	end
	for deg = 2, 152, 11 do
		rockAt(deg + rng(-4, 4), rng(-2, 3), if rng(0, 1) < 0.3 then rng(4.5, 7) else rng(1.8, 3.4))
	end
	for deg = 210, 352, 24 do
		rockAt(deg + rng(-6, 6), rng(-1, 5), rng(5, 9))
	end
	return m
end

-- 북쪽 둑: 호수에서 설원 벼랑으로 오르는 비탈 숲 덩이 (아래 자작·소나무 → 위 눈 인 전나무)
local function buildNorthBank(F: Instance, rng)
	local m = Kit.folder(F, "북쪽 비탈숲")
	local function ok(x: number, z: number, h: number): boolean
		return z < -872 and z > -1000 and h > 2 and dry(x, z, 7)
	end
	for _, g in { { -160, -925, 36, 4 }, { 40, -912, 32, 4 }, { -70, -950, 26, 2 }, { 120, -960, 26, 2 } } do
		local spots = scatter(rng, g[1], g[2], g[3], g[4], 6.5, ok, 200)
		for _, s in spots do
			if s.h < 26 then
				if rng(0, 1) < 0.5 then
					birch(m, s.x, s.z, rng, { blobs = 4, branches = 2 })
				else
					pine(m, s.x, s.z, rng, { height = rng(15, 19), tiers = 4 })
				end
			elseif s.h < 58 then
				fir(m, foot(s.x, s.z), rng, { height = rng(15, 21), snow = 0.3 })
			else
				fir(m, foot(s.x, s.z), rng, { height = rng(13, 20), snow = 0.9 })
			end
		end
		-- 숲 발치 덤불
		local under = scatter(rng, g[1], g[2], g[3] + 8, 3, 4, ok, 60)
		for _, s in under do
			shrub(m, s.x, s.z, rng, { leaves = if s.h > 50 then FROST_LEAVES else FERN_LEAVES, size = rng(3.5, 5.5), blobs = 2 })
		end
	end
	local small = scatter(rng, -60, -930, 190, 6, 8, ok, 200)
	for _, s in small do
		rocks(m, s.x, s.z, rng(4, 8), rng, { count = 1, snow = s.h > 55 })
	end
	return m
end

-- 비류폭 ---------------------------------------------------------------------------------
-- 비류천(수면 110)이 비류대 동쪽 벼랑 끝(x ≈ -280)에서 명경호로 떨어진다. 벼랑은 77° 쯤 기운 면이라
-- 물줄기는 수직 판 하나가 아니라 벼랑 면을 2~3 떨어져 따라 내려가는 꺾인 판 여러 장으로 짓는다.

local FALLS = Land.FALLS
local FALL_Z = -720
local FALL_DIR = Vector3.new(1, 0, 0.12).Unit -- 물이 떨어지는 쪽 (동)
local FALL_SIDE = Vector3.new(-FALL_DIR.Z, 0, FALL_DIR.X)

-- 벼랑: z 줄에서 땅 높이가 y 가 되는 x (서쪽이 높다)
local function cliffX(z: number, y: number): number
	local lo, hi = -335, -240
	for _ = 1, 22 do
		local mid = (lo + hi) / 2
		if Land.height(mid, z) > y then
			lo = mid
		else
			hi = mid
		end
	end
	return (lo + hi) / 2
end

local function particle(parent: BasePart, name: string, props)
	local e = Instance.new("ParticleEmitter")
	e.Name = name
	e.Texture = "rbxasset://textures/particles/smoke_main.dds"
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

local function emitterPart(parent: Instance, name: string, size: Vector3, cf: CFrame): BasePart
	local p = deco(block(parent, name, size, cf, NC.water, M.SmoothPlastic))
	p.Transparency = 1
	p.CastShadow = false
	return p
end

-- 벼랑 소나무: 벼랑 틈에서 바깥으로 비스듬히 자란다 (줄기 두 마디 + 납작한 잎판 셋)
local function cliffPine(parent: Instance, base: Vector3, out: Vector3, rng)
	local m = Kit.model(parent, "벼랑 소나무")
	local h = rng(8, 12)
	local side = Vector3.new(-out.Z, 0, out.X)
	local mid = base + out * h * 0.28 + Vector3.new(0, h * 0.35, 0)
	local tip = mid + out * h * 0.3 + side * rng(-1.5, 1.5) + Vector3.new(0, h * 0.45, 0)
	beam(m, "Trunk", base - out * 1.2, mid, 0.95, 0.95, P.barkPine, M.Wood)
	beam(m, "Trunk", mid, tip, 0.7, 0.7, P.barkPine, M.Wood)
	for k, p in { tip, mid + out * 2.2 + side * 2.4 + Vector3.new(0, 1.2, 0), tip + out * 1.6 - side * 2.6 - Vector3.new(0, 2.2, 0) } do
		local s = (if k == 1 then 5.5 else 4.2) * rng(0.85, 1.15)
		deco(block(m, "Leaves", Vector3.new(s, s * 0.26, s * 0.8), CFrame.new(p + Vector3.new(0, 0.3, 0)) * CFrame.Angles(rng(-0.12, 0.12), rng(0, TAU), rng(-0.12, 0.12)), jitter(if k == 1 then P.pineLight else P.pine, rng, 0.06), M.LeafyGrass))
	end
	return m
end

local function buildFalls(F: Instance, rng)
	local m = Kit.model(F, "비류폭")
	-- 물줄기 꺾은선: 높이마다 (그 폭 안에서 벼랑이 가장 나온 곳 + 띄움)
	local levels = { 110, 92, 70, 46, 22, -1.2 }
	local widths = { 15.5, 18, 22, 26, 30, 34 }
	local pts = {}
	for k, y in levels do
		local w = widths[k]
		local xMax = -huge
		for u = -0.5, 0.5, 0.25 do
			local z = FALL_Z + FALL_SIDE.Z * w * u
			xMax = max(xMax, cliffX(z, y))
		end
		local gap = if k == 1 then 0.4 else 1.4 + k * 0.45
		local x = if k == 1 then -280.2 else xMax + gap
		pts[k] = Vector3.new(x, y, FALL_Z + FALL_SIDE.Z * 0)
	end
	local function sheet(name: string, a: Vector3, b: Vector3, w: number, t: number, transparency: number, color: Color3, up: Vector3?)
		local p = deco(beam(m, name, a, b, w, t, color, M.Glass, up or FALL_DIR))
		p.Transparency = transparency
		p.CastShadow = false
		return p
	end
	for k = 1, #pts - 1 do
		local a, b = pts[k], pts[k + 1]
		local along = (b - a).Unit
		local w = (widths[k] + widths[k + 1]) / 2
		local a2, b2 = a - along * 0.6, b + along * 0.6
		sheet("Mulgil", a2, b2, w, 0.45, 0.28, NC.water)
		sheet("Mulgil2", a2 - FALL_DIR * 0.7, b2 - FALL_DIR * 0.7, w * 0.92, 0.3, 0.55, Color3.fromRGB(160, 206, 230))
		-- 흰 물살 줄: 판 앞에 가는 띠 몇 가닥
		for j = 1, 3 do
			local u = (j - 2) * 0.3 + rng(-0.08, 0.08)
			local off = FALL_SIDE * (w * u) + FALL_DIR * 0.35
			local s = sheet("Mulsal", a2 + off, b2 + off, rng(0.8, 1.6), 0.15, 0.2, NC.foam)
			s.Material = M.SmoothPlastic
		end
	end
	-- 넘어가는 자리: 수면(110)에서 첫 판으로 굽는 판
	local lip = pts[1]
	sheet("Neomeo", lip - FALL_DIR * 3 + Vector3.new(0, 0.05, 0), lip + Vector3.new(0, -0.2, 0), widths[1], 0.5, 0.3, NC.water, Vector3.yAxis)
	-- 곁 물줄기 둘 (벼랑 틈에서 새어 나와 가늘게 떨어진다)
	for _, s in { -1, 1 } do
		local z = FALL_Z + s * rng(19, 24)
		local yTop = rng(62, 80)
		local prev = nil
		for _, y in { yTop, (yTop + 20) / 2, -1.2 } do
			local x = cliffX(z, y) + 1.2
			local p = Vector3.new(x, y, z)
			if prev then
				sheet("Gyeot", prev, p, rng(2.5, 3.6), 0.3, 0.35, NC.water)
			end
			prev = p
		end
	end
	-- 물방울 줄기 (벼랑 따라 비스듬히), 물보라, 안개
	local top, bottom = pts[1], pts[#pts]
	local fallDir = (bottom - top).Unit
	local fallLen = (bottom - top).Magnitude
	-- 내뿜는 판: 앞(-Z)이 물 떨어지는 쪽을 보게 (Z = -fallDir)
	local Zv = -fallDir
	local Yv = Zv:Cross(FALL_SIDE).Unit
	local ep = emitterPart(m, "Emit", Vector3.new(widths[1], 0.2, 0.2), CFrame.fromMatrix(top + FALL_DIR * 0.8, FALL_SIDE, Yv))
	particle(ep, "Mulbal", {
		EmissionDirection = Enum.NormalId.Front,
		Shape = Enum.ParticleEmitterShape.Box,
		Rate = 70,
		Lifetime = NumberRange.new(fallLen / 46, fallLen / 40),
		Speed = NumberRange.new(40, 46),
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.8), NumberSequenceKeypoint.new(1, 4.5) }),
		Squash = NumberSequence.new(1.3),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.45), NumberSequenceKeypoint.new(0.85, 0.7), NumberSequenceKeypoint.new(1, 1) }),
		Color = ColorSequence.new(Color3.fromRGB(235, 246, 255)),
		LightEmission = 0.25,
		Orientation = Enum.ParticleOrientation.VelocityParallel,
	})
	local base = Vector3.new(bottom.X + 3, -0.6, bottom.Z)
	local fp = emitterPart(m, "Mulbora", Vector3.new(4, 0.4, widths[#widths]), CFrame.new(base))
	particle(fp, "Mulbora", {
		EmissionDirection = Enum.NormalId.Top,
		Shape = Enum.ParticleEmitterShape.Box,
		Rate = 70,
		Lifetime = NumberRange.new(1.4, 2.6),
		Speed = NumberRange.new(5, 11),
		SpreadAngle = Vector2.new(55, 55),
		Acceleration = Vector3.new(0, -7, 0),
		Drag = 1.5,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 3), NumberSequenceKeypoint.new(1, 9) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 1) }),
		Color = ColorSequence.new(Color3.fromRGB(245, 250, 255)),
	})
	particle(fp, "Angae", {
		Rate = 7,
		Lifetime = NumberRange.new(5, 8),
		Speed = NumberRange.new(2, 4),
		SpreadAngle = Vector2.new(180, 30),
		Acceleration = Vector3.new(1.5, 0.6, 0),
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 14), NumberSequenceKeypoint.new(1, 34) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.8), NumberSequenceKeypoint.new(1, 1) }),
		Color = ColorSequence.new(Color3.fromRGB(240, 246, 252)),
	})
	-- 물거품 판 (떨어지는 자리 수면)
	for k = 0, 2 do
		local c = base + FALL_DIR * (k * 6 + 2) + FALL_SIDE * rng(-3, 3)
		local disc = Kit.disc(m, "Geopum", Vector3.new(c.X, -0.85, c.Z), 9 - k * 2.2, 0.2, NC.foam, M.SmoothPlastic)
		disc.Transparency = 0.25 + k * 0.2
		disc.CanCollide = false
		disc.CanQuery = false
		disc.CastShadow = false
	end
	-- 젖은 바위: 떨어지는 자리 양옆과 앞 물속
	for k = 0, 7 do
		local s = if k % 2 == 0 then 1 else -1
		local p = base + FALL_SIDE * s * rng(14, 22) + FALL_DIR * rng(-4, 10)
		local x = min(p.X, cliffX(p.Z, 2) + 6)
		rocks(m, x, p.Z, rng(4, 8), rng, { count = 2, wet = true, color = NC.wetRock, moss = k % 3 == 0 })
	end
	for _ = 1, 3 do
		local p = base + FALL_DIR * rng(12, 22) + FALL_SIDE * rng(-12, 12)
		rocks(m, p.X, p.Z, rng(2.5, 4), rng, { count = 1, wet = true, color = NC.wetRock, moss = false })
	end
	-- 벼랑 바위 결: 폭포 양옆 벼랑 면에 기둥 바위 (벼랑 면 기울기를 따라 키와 깊이를 달리해 엇갈린다)
	for k = 0, 15 do
		local s = if k % 2 == 0 then 1 else -1
		local z = FALL_Z + s * (19 + (k // 2) * 5.5 + rng(-1.5, 1.5))
		local yBot = rng(-2, 40)
		local yTop = min(104, yBot + rng(24, 60))
		local out = rng(0.2, 1.4)
		local aTop = Vector3.new(cliffX(z, yTop) + out, yTop, z)
		local aBot = Vector3.new(cliffX(z, yBot) + out, yBot, z)
		local slab = beam(m, "Byeorang", aBot, aTop, rng(3.5, 6), rng(2, 3.5), NC.rock:Lerp(NC.darkRock, rng(0, 0.45)), M.Slate, FALL_DIR)
		slab.CFrame *= CFrame.Angles(0, 0, rng(-0.06, 0.06))
	end
	-- 벼랑 틈 소나무: 벼랑 면에서 바깥으로 비스듬히 (폭포 둘레는 비운다)
	for _, z in { -628, -652, -676, -696, -748, -770, -796, -822 } do
		local y = rng(36, 96)
		local zz = z + rng(-4, 4)
		local base = Vector3.new(cliffX(zz, y) - 0.4, y, zz)
		cliffPine(m, base, Vector3.new(1, 0, rng(-0.3, 0.3)).Unit, rng)
	end
	-- 벼랑 위 가장자리 덤불 (위에서 보면 벼랑 끝이 부드럽다)
	for z = -600, -850, -21 do
		if abs(z - FALL_Z) > 20 then
			local zz = z + rng(-5, 5)
			local x = cliffX(zz, 107) - rng(2, 4)
			if surf(x, zz) > 104 and isFree(x, zz, 3) then
				reserve(x, zz, 3)
				shrub(m, x, zz, rng, { size = rng(3.5, 5.5), blobs = 2, leaves = FERN_LEAVES })
			end
		end
	end
	reserve(-262, FALL_Z, 30)
	return m
end

-- 비류대 ---------------------------------------------------------------------------------

local TABLE = Land.TABLE
-- 비류천 물길 위 자리 (x 에서)
local function streamZ(x: number): number
	local pts = Land.STREAM.pts
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		if x >= a[1] and x <= b[1] then
			local t = (x - a[1]) / (b[1] - a[1])
			return a[2] + (b[2] - a[2]) * t
		end
	end
	return pts[#pts][2]
end
local function onTable(x: number, z: number, h: number): boolean
	return h > 104 and Land.blob(x, z, TABLE) > 0.6
end

-- 깎은 오름길에 돌계단: 길 꺾은선을 따라 일정한 간격으로 디딤 판을 놓는다
local function benchSteps(parent: Instance, bench, every: number, width: number)
	local m = Kit.model(parent, "돌계단")
	local pts = bench.pts
	local count = 0
	for i = 1, #pts - 1 do
		local a = Vector3.new(pts[i][1], pts[i][3], pts[i][2])
		local b = Vector3.new(pts[i + 1][1], pts[i + 1][3], pts[i + 1][2])
		local flatLen = Vector3.new(b.X - a.X, 0, b.Z - a.Z).Magnitude
		local n = floor(flatLen / every)
		local look = face(Vector3.new(a.X, 0, a.Z), Vector3.new(b.X, 0, b.Z))
		local rise = (b.Y - a.Y) / n
		for k = 0, n - 1 do
			-- 디딤 판 하나: 아래쪽 끝이 길보다 rise 만큼 높고, 위쪽 끝이 길과 같다
			local c = a:Lerp(b, (k + 0.5) / n)
			local topY = a.Y + rise * (k + 1) + 0.05
			local t = rise + 1.2
			block(
				m,
				"Gyedan",
				Vector3.new(width * (1 + ((k + i) % 3 - 1) * 0.04), t, flatLen / n + 0.1),
				CFrame.new(c.X, topY - t / 2, c.Z) * rot(look),
				P.granite:Lerp(P.graniteDark, ((k * 7 + i) % 5) / 8),
				M.Granite
			)
			count += 1
		end
		reserveLine(Vector3.new(a.X, 0, a.Z), Vector3.new(b.X, 0, b.Z), 7)
	end
	return m, count
end

local function buildTable(F: Instance, rng)
	local m = Kit.folder(F, "비류대")
	-- 오름길 돌계단 (깎은 길 전체), 들머리 비석과 석등
	local bench = Land.BENCHES.table
	benchSteps(m, bench, 3.4, 8)
	local p0 = bench.pts[1]
	local start = Vector3.new(p0[1], 0, p0[2])
	local first = Vector3.new(bench.pts[2][1], 0, bench.pts[2][2])
	local bdir = (first - start).Unit
	local bside = Vector3.new(-bdir.Z, 0, bdir.X)
	local sp = start - bdir * 5 + bside * 7
	Kit.stele(m, Vector3.new(sp.X, surf(sp.X, sp.Z) - 0.4, sp.Z), "비류대", start - bdir * 20)
	for _, s in { 1, -1 } do
		local lp = start - bdir * 2 + bside * s * 6.2
		Build.stoneLantern(m, Vector3.new(lp.X, span(lp.X, lp.Z, 1.4) - 0.2, lp.Z))
	end
	-- 벼랑 끝 정자: 폭포 남쪽, 호수를 내려다본다
	local pc = Vector3.new(-303, 0, -757)
	local look = face(pc, pc + Vector3.new(-1, 0, 0.25)) -- 앞(계단)이 대지 안쪽(서)
	local top = terrace(m, CFrame.new(pc) * rot(look), 15, 15, 0.2, Color3.fromRGB(140, 136, 126))
	local pav = Build.pavilion(m, CFrame.new(pc.X, top, pc.Z) * rot(look), { bays = { 1, 1 }, bay = 8.5, pillarH = 7.8, plinth = 1.4, roof = "paljak", detail = 1, bands = 3, name = "비류대 정자" })
	pav:SetAttribute("Place", "비류대")
	reserve(pc.X, pc.Z, 13)
	-- 폭포 머리: 남쪽 물가 비석, 물길 가운데 갈라 바위
	local stp = Vector3.new(-292, 0, -741)
	Kit.stele(m, Vector3.new(stp.X, span(stp.X, stp.Z, 1.5) - 0.3, stp.Z), "비류폭", Vector3.new(-330, 0, -760))
	reserve(stp.X, stp.Z, 4)
	for _, q in { { -287, -717, 3.2 }, { -293, -724, 2.4 }, { -298, -715, 2 } } do
		rocks(m, q[1], q[2], q[3], rng, { count = 1, wet = true, color = NC.wetRock, moss = false })
	end
	-- 돌다리: 물길을 건너는 장대석 세 장 (가운데 돌 기둥)
	local bx = -322
	local bz = streamZ(bx)
	local nA = Vector3.new(bx + 2.2, 0, bz - 12)
	local nB = Vector3.new(bx - 2.2, 0, bz + 12)
	local blook = face(nA, nB)
	local yA, yB = surf(nA.X, nA.Z), surf(nB.X, nB.Z)
	local deckY = max(yA, yB, 110.6) + 0.5
	for _, s in { -1.35, 0, 1.35 } do
		local a = (CFrame.new(nA) * rot(blook) * CFrame.new(s, 0, 0)).Position
		local b = (CFrame.new(nB) * rot(blook) * CFrame.new(s, 0, 0)).Position
		beam(m, "Dolpan", Vector3.new(a.X, deckY - 0.4, a.Z), Vector3.new(b.X, deckY - 0.4, b.Z), 1.3, 0.8, P.granite:Lerp(P.graniteDark, abs(s) / 3), M.Granite)
	end
	local mid = (nA + nB) / 2
	block(m, "Gyogak", Vector3.new(5, deckY - 0.8 - 102, 2.2), CFrame.new(mid.X, (deckY - 0.8 + 102) / 2, mid.Z) * rot(blook), P.graniteDark, M.Granite)
	for _, e in { nA, nB } do
		local g = surf(e.X, e.Z)
		block(m, "Batchim", Vector3.new(5, deckY - 0.8 - g + 1.5, 3), CFrame.new(e.X, (deckY - 0.8 + g - 1.5) / 2, e.Z) * rot(blook), P.graniteDark, M.Granite)
	end
	reserveLine(nA, nB, 5)
	-- 물가 갈대·붓꽃·바위 (비류천을 따라)
	for x = -590, -340, 36 do
		local z = streamZ(x)
		local s = if (x // 36) % 2 == 0 then 1 else -1
		local off = rng(7, 10)
		local px, pz = x + rng(-6, 6), z + s * off
		if isFree(px, pz, 3) then
			reserve(px, pz, 3)
			local w = waterAt(px, pz)
			if w then
				Build.reeds(m, Vector3.new(px, Land.height(px, pz), pz), rng, { count = 5 })
			elseif rng(0, 1) < 0.5 then
				flowers(m, px, pz, rng, NC.iris)
			else
				rocks(m, px, pz, rng(2, 3.5), rng, { count = 0, moss = false })
			end
		end
	end
	-- 대지 위: 숲 덩이 (벼랑 가 소나무, 안쪽 섞인 숲), 바위 언덕, 꽃밭. 가운데 풀밭은 영초 자리로 비워 둔다
	local function ok(x: number, z: number, h: number): boolean
		return onTable(x, z, h) and abs(z - streamZ(x)) > 13 and not nearRoad(x, z, 8)
	end
	local groves = {
		{ -318, -782, 18, { "pine", "pine" } }, -- 정자 뒤 벼랑 가
		{ -300, -694, 16, { "pine", "pine", "maple" } }, -- 폭포 북쪽 벼랑 가
		{ -470, -716, 20, { "pine", "maple", "pine", "birch" } },
		{ -430, -858, 20, { "pine", "maple" } },
		{ -560, -770, 16, { "pine", "birch" } },
	}
	for _, g in groves do
		local spots = scatter(rng, g[1], g[2], g[3], #g[4], 7, ok, 120)
		for i, sp in spots do
			local kind = g[4][i]
			if kind == "maple" then
				maple(m, sp.x, sp.z, rng, { blobs = 5 })
			elseif kind == "birch" then
				birch(m, sp.x, sp.z, rng, { blobs = 5 })
			else
				pine(m, sp.x, sp.z, rng, { height = rng(14, 20), tiers = 4 })
			end
		end
		-- 숲 덩이 발치에 바위나 덤불 하나
		local rp = scatter(rng, g[1], g[2], g[3] + 6, 1, 4, ok, 30)
		for _, sp in rp do
			if #g[4] > 2 then
				rocks(m, sp.x, sp.z, rng(3.5, 6), rng, { count = 1 })
			else
				shrub(m, sp.x, sp.z, rng, { size = rng(2.4, 3.4), blobs = 2, leaves = FERN_LEAVES })
			end
		end
	end
	-- 바위 언덕 둘 (큰 바위 셋씩)
	for _, c in { { -390, -690 }, { -520, -850 } } do
		local spots = scatter(rng, c[1], c[2], 10, 3, 4, ok, 40)
		for i, sp in spots do
			rocks(m, sp.x, sp.z, if i == 1 then rng(9, 12) else rng(4, 6), rng, { count = if i == 1 then 3 else 1 })
		end
	end
	-- 꽃밭: 진달래·들꽃 덤불을 몇 곳에 모아서
	for _, c in { { -360, -740, NC.azalea }, { -430, -790, NC.wildY }, { -500, -700, NC.wildW } } do
		local spots = scatter(rng, c[1], c[2], 12, 4, 3.5, ok, 40)
		for _, sp in spots do
			flowers(m, sp.x, sp.z, rng, c[3])
		end
	end
	return m
end

-- 백랑설원 --------------------------------------------------------------------------------

local SNOW = Land.SNOW
local GLACIER = Land.GLACIER
local TARN = Land.TARN
local function onSnow(x: number, z: number, h: number): boolean
	return h > 64 and Land.blob(x, z, SNOW) > 0.5 and Land.polyDist(x, z, GLACIER, 160) > 95 and Land.shoreDist(x, z) < -40
end

-- 얼음 낀 바위: 눈 인 바위 + 한쪽에 반투명 얼음 껍질
local function iceRock(parent: Instance, x: number, z: number, size: number, rng)
	local m = rocks(parent, x, z, size, rng, { count = 1, snow = true, color = NC.frostRock })
	local main = m:FindFirstChild("Rock") :: BasePart?
	if main and rng(0, 1) < 0.6 then
		local shell = block(
			m,
			"Eoreum",
			main.Size * Vector3.new(0.7, 0.9, 1.08),
			main.CFrame * CFrame.new(main.Size.X * 0.25, -0.1, 0) * CFrame.Angles(0, 0, rng(-0.1, 0.1)),
			NC.ice,
			M.Glacier
		)
		shell.Transparency = 0.35
		shell.Reflectance = 0.1
	end
	return m
end

-- 눈 인 전나무 숲 덩이
local function firGrove(parent: Instance, rng, cx: number, cz: number, r: number, n: number, ok, snow: number?)
	local spots = scatter(rng, cx, cz, r, n, 5.5, ok, n * 30)
	for i, s in spots do
		local tall = 1 - sqrt((s.x - cx) ^ 2 + (s.z - cz) ^ 2) / r -- 가운데가 크다
		local hgt = 11 + 12 * tall + rng(-2, 2)
		fir(parent, foot(s.x, s.z, 1.4), rng, {
			height = hgt,
			snow = snow or 0.9,
			tiers = if hgt > 18 then 4 elseif hgt > 13.5 then 3 else 2,
		})
	end
	return spots
end

-- 무너진 돌 망루: 아래 몸만 남고 위는 무너졌다. 문 자리, 쓰러진 들보, 무너진 돌, 눈
local function ruinTower(parent: Instance, rng, x: number, z: number, faceTo: Vector3)
	local m = Kit.model(parent, "망루 옛터")
	local S, T = 9, 1.6
	local look0 = face(Vector3.new(x, 0, z), Vector3.new(faceTo.X, 0, faceTo.Z))
	local lo, hi = rectSpan(look0, S + 2, S + 2)
	local base = hi
	local cf = CFrame.new(x, base, z) * rot(look0)
	local stone = Color3.fromRGB(132, 128, 120)
	local plinthH = base - lo + 1.6
	block(m, "Gidan", Vector3.new(S + 2, plinthH, S + 2), cf * CFrame.new(0, -plinthH / 2 + 0.6, 0), Color3.fromRGB(116, 112, 106), M.Cobblestone)
	local function wall(name: string, size: Vector3, at: CFrame, snowCap: boolean)
		block(m, name, size, at, stone:Lerp(Color3.fromRGB(100, 98, 94), rng(0, 0.5)), M.Cobblestone)
		if snowCap then
			block(m, "Nun", Vector3.new(size.X + 0.2, 0.45, size.Z + 0.2), at * CFrame.new(0, size.Y / 2 + 0.2, 0), NC.snow, M.Snow)
		end
	end
	-- 앞 벽: 문 자리 (양쪽 벽 + 문 위 돌)
	local hF = rng(9, 11)
	local door = 3
	local side = (S - door) / 2
	for _, s in { -1, 1 } do
		local h = hF + (if s > 0 then 2.5 else 0)
		wall("Byeok", Vector3.new(side, h, T), cf * CFrame.new(s * (door / 2 + side / 2), h / 2 + 0.6, -S / 2 + T / 2), true)
	end
	wall("Inbang", Vector3.new(door + 0.4, 1.4, T + 0.1), cf * CFrame.new(0, 0.6 + 5.6, -S / 2 + T / 2), false)
	-- 뒤 벽 (높게 남은 쪽): 계단처럼 무너진 위
	local hB = rng(14, 17)
	wall("Byeok", Vector3.new(S * 0.6, hB, T), cf * CFrame.new(-S * 0.2, hB / 2 + 0.6, S / 2 - T / 2), true)
	wall("Byeok", Vector3.new(S * 0.4, hB - 5, T), cf * CFrame.new(S * 0.3, (hB - 5) / 2 + 0.6, S / 2 - T / 2), true)
	-- 옆 벽 둘: 하나는 높고 하나는 낮게
	local hL, hR = rng(12, 15), rng(6, 8)
	wall("Byeok", Vector3.new(T, hL, S - 2 * T), cf * CFrame.new(-S / 2 + T / 2, hL / 2 + 0.6, 0), true)
	wall("Byeok", Vector3.new(T, hR, S - 2 * T), cf * CFrame.new(S / 2 - T / 2, hR / 2 + 0.6, 0), true)
	-- 활 쏘던 틈 (어두운 홈)
	block(m, "Teum", Vector3.new(T + 0.08, 2.2, 0.5), cf * CFrame.new(-S / 2 + T / 2, hL - 3, 0), NC.ink, M.Slate)
	block(m, "Teum", Vector3.new(0.6, 2.2, T + 0.08), cf * CFrame.new(-S * 0.2, hB - 4, S / 2 - T / 2), NC.ink, M.Slate)
	-- 쓰러진 들보: 높은 벽 위에서 땅으로
	local a = (cf * CFrame.new(-S / 2 + 1, hL - 1, -1)).Position
	local bpos = (cf * CFrame.new(S / 2 + 5, 0, -3)).Position
	beam(m, "Deulbo", a, Vector3.new(bpos.X, surf(bpos.X, bpos.Z) + 0.3, bpos.Z), 0.9, 0.9, Color3.fromRGB(70, 56, 46), M.Wood)
	-- 무너진 돌 (낮은 벽 쪽)
	for k = 1, 5 do
		local q = (cf * CFrame.new(S / 2 + rng(1, 4), 0, rng(-S / 2, S / 2))).Position
		local g = surf(q.X, q.Z)
		local s = rng(1.2, 2.4)
		block(m, "Dol", Vector3.new(s * 1.3, s * 0.8, s), CFrame.new(q.X, g + s * 0.2, q.Z) * CFrame.Angles(rng(-0.4, 0.4), rng(0, 6), rng(-0.4, 0.4)), stone, M.Cobblestone)
		if k == 1 then
			local q2 = (cf * CFrame.new(rng(-3, 3), 0, -S / 2 - rng(2, 3))).Position
			block(m, "Dol", Vector3.new(2, 1.2, 1.6), CFrame.new(q2.X, surf(q2.X, q2.Z) + 0.3, q2.Z) * CFrame.Angles(0.2, rng(0, 6), 0.1), stone, M.Cobblestone)
		end
	end
	-- 바람받이 쪽 눈 더미 (쐐기)
	wedge(m, "Nundeomi", Vector3.new(S + 1, 2.2, 4), cf * CFrame.new(0, 0.5, S / 2 + 2) * CFrame.Angles(0, math.pi, 0), NC.snow, M.Snow)
	reserve(x, z, 12)
	return m
end

-- 길 따라 선 표석: 눈 인 돌기둥 + 매어 둔 검푸른 천 조각
local function pathMarker(parent: Instance, rng, p: Vector3, toward: Vector3)
	local m = Kit.model(parent, "표석")
	local lo = span(p.X, p.Z, 1)
	local h = rng(4.2, 5.6)
	local look = face(Vector3.new(p.X, lo, p.Z), Vector3.new(toward.X, lo, toward.Z)) * CFrame.Angles(rng(-0.05, 0.05), 0, rng(-0.06, 0.06))
	block(m, "Badak", Vector3.new(2.4, 1.2, 2), look * CFrame.Angles(0, 0.4, 0), NC.frostRock, M.Slate)
	block(m, "Pyoseok", Vector3.new(1.3, h, 0.9), look * CFrame.new(0, h / 2 + 0.2, 0), Color3.fromRGB(128, 126, 122), M.Slate)
	block(m, "Nun", Vector3.new(1.5, 0.45, 1.1), look * CFrame.new(0, h + 0.4, 0), NC.snow, M.Snow)
	deco(block(m, "Cheon", Vector3.new(0.12, 1.6, 0.5), look * CFrame.new(0.72, h - 0.9, 0.2) * CFrame.Angles(0.15, 0, 0.1), NC.navy, M.Fabric))
	return m
end

-- 꺾은선을 따라 every 마다 { 자리, 방향 }
local function polyPoints(poly, every: number): { { Vector3 } }
	local out = {}
	local pts = poly.pts
	local carry = 0
	for i = 1, #pts - 1 do
		local a = Vector3.new(pts[i][1], 0, pts[i][2])
		local b = Vector3.new(pts[i + 1][1], 0, pts[i + 1][2])
		local len = (b - a).Magnitude
		local dir = (b - a) / len
		local d = carry
		while d < len do
			table.insert(out, { a + dir * d, dir })
			d += every
		end
		carry = d - len
	end
	return out
end

local function buildSnowfield(F: Instance, rng)
	local m = Kit.folder(F, "백랑설원")
	-- 오름길: 들머리 비석, 길 따라 표석 (좌우 번갈아)
	local ramp = Land.BENCHES.snow
	local r0 = Vector3.new(ramp.pts[1][1], 0, ramp.pts[1][2])
	local r1 = Vector3.new(ramp.pts[2][1], 0, ramp.pts[2][2])
	local rdir = (r1 - r0).Unit
	local rside = Vector3.new(-rdir.Z, 0, rdir.X)
	local sp = r0 + rside * 8 - rdir * 2
	Kit.stele(m, Vector3.new(sp.X, span(sp.X, sp.Z, 1.5) - 0.4, sp.Z), "백랑설원", r0 - rdir * 30)
	reserve(sp.X, sp.Z, 4)
	local markers = polyPoints(ramp, 34)
	for _, q in polyPoints(Land.poly(Land.ROADS[2]), 34) do
		table.insert(markers, q)
	end
	for k, q in markers do
		if k > 1 then
			local s = if k % 2 == 0 then 1 else -1
			local side = Vector3.new(-q[2].Z, 0, q[2].X)
			local p = q[1] + side * s * 7.5
			if clearOf(p.X, p.Z, 2) and isFree(p.X, p.Z, 1.5) then
				pathMarker(m, rng, p, q[1])
				reserve(p.X, p.Z, 2)
			end
		end
	end
	-- 무너진 망루 둘: 남쪽 벼랑 끝(명경호를 내려다봄)과 북쪽 바닷가 벼랑 끝
	ruinTower(m, rng, -168, -1016, Vector3.new(-60, 0, -700))
	ruinTower(m, rng, 118, -1722, Vector3.new(118, 0, -1900))
	-- 전나무 숲 덩이 (바람을 막는 둔덕 뒤에)
	local groves = {
		{ -150, -1062, 30, 5 }, -- 남쪽 망루 뒤
		{ 118, -1012, 26, 4 }, -- 오름길 위 동쪽
		{ -110, -1330, 32, 5 },
		{ 220, -1420, 30, 4 },
		{ 150, -1690, 22, 3 }, -- 북쪽 망루 곁
		{ -330, -1150, 24, 3 }, -- 빙하 가
	}
	for _, g in groves do
		firGrove(m, rng, g[1], g[2], g[3], g[4], function(x, z, h)
			return onSnow(x, z, h) and dry(x, z, 8) and slope(x, z) < 0.9
		end)
	end
	-- 홀로 선 전나무와 얼어붙은 덤불, 얼음 낀 바위
	local singles = scatter(rng, -40, -1360, 420, 4, 60, function(x, z, h)
		return onSnow(x, z, h) and dry(x, z, 8)
	end, 300)
	for _, s in singles do
		fir(m, foot(s.x, s.z), rng, { height = rng(9, 15), snow = 1, tiers = 3 })
		local a = rng(0, TAU)
		local bx, bz = s.x + cos(a) * 4, s.z + sin(a) * 4
		Build.shrub(m, foot(bx, bz) - Vector3.new(0, 0.4, 0), rng, { leaves = FROST_LEAVES, size = rng(2, 3), blobs = 2 })
	end
	local stones = scatter(rng, -40, -1360, 440, 10, 30, function(x, z, h)
		return onSnow(x, z, h) and dry(x, z, 6)
	end, 400)
	for i, s in stones do
		iceRock(m, s.x, s.z, if i % 3 == 0 then rng(6, 10) else rng(2.5, 5), rng)
	end
	return m
end

-- 북진대: 허브가 단을 짓는 설원 위 둥근 터 (지름 52). 돌기둥, 찢긴 깃발, 바람막이 돌담, 오르는 돌계단
local function tornBanner(parent: Instance, rng, ground: Vector3, wind: Vector3, color: Color3)
	local m = Kit.model(parent, "깃발")
	local h = rng(10.5, 12.5)
	cyl(m, "Jangdae", ground - Vector3.new(0, 0.8, 0), ground + Vector3.new(0, h, 0), 0.4, P.woodDark, M.Wood)
	Build.ball(m, "Kkokji", ground + Vector3.new(0, h + 0.3, 0), 0.7, P.hwang, M.Metal)
	local look = face(ground, ground + wind)
	for k = 0, 2 do
		local len = rng(3, 5.6) - k * 0.4
		local y = h - 0.9 - k * 1.25
		local strip = block(
			m,
			"Gi",
			Vector3.new(0.08, 1.15, len),
			look * CFrame.new(0, y, -len / 2 - 0.2) * CFrame.Angles(rad(rng(-12, -3)), 0, rad(rng(-10, 10))),
			color:Lerp(NC.ink, k * 0.15),
			M.Fabric
		)
		deco(strip)
	end
	return m
end

-- 홍살문: 신성한 터 어귀의 붉은 살 문 (기둥 둘, 가로대 둘, 위로 솟은 살, 가운데 태극 판)
local function hongsalmun(parent: Instance, ground: Vector3, along: Vector3, width: number)
	local m = Kit.model(parent, "홍살문")
	local red = P.juhong:Lerp(P.seokganju, 0.55)
	local look = face(ground, ground + along)
	local H = 10.5
	for _, s in { -1, 1 } do
		local foot0 = (look * CFrame.new(s * width / 2, 0, 0)).Position
		local g = surf(foot0.X, foot0.Z)
		block(m, "Choseok", Vector3.new(1.8, 1.4, 1.8), CFrame.new(foot0.X, g + 0.2, foot0.Z) * rot(look), NC.frostRock, M.Granite)
		cyl(m, "Gidung", Vector3.new(foot0.X, g + 0.8, foot0.Z), Vector3.new(foot0.X, ground.Y + H + 0.8, foot0.Z), 0.95, red, M.Wood)
	end
	for _, y in { H - 1.6, H - 0.2 } do
		block(m, "Garodae", Vector3.new(width + 0.8, 0.55, 0.55), look * CFrame.new(0, y, 0), red, M.Wood)
	end
	block(m, "Nun", Vector3.new(width + 0.9, 0.3, 0.75), look * CFrame.new(0, H + 0.2, 0), NC.snow, M.Snow)
	-- 살: 가로대 사이와 위로 솟는다
	local n = 9
	for k = 1, n do
		local x = -width / 2 + k * width / (n + 1)
		local tall = if k == (n + 1) / 2 then 0 else 1.9
		if tall > 0 then
			block(m, "Sal", Vector3.new(0.22, 3.4, 0.22), look * CFrame.new(x, H - 0.6 + 1.2, 0), red, M.Wood)
		end
	end
	-- 가운데 태극 판과 삼지창
	local disc = Kit.disc(m, "Taegeuk", Vector3.zero, 0.95, 0.2, P.gunjeong, M.SmoothPlastic)
	disc.CFrame = look * CFrame.new(0, H + 1.4, 0) * CFrame.Angles(0, math.pi / 2, 0)
	block(m, "Samjichang", Vector3.new(0.25, 2.4, 0.25), look * CFrame.new(0, H + 2.4, 0), red, M.Wood)
	return m
end

local function buildStar(F: Instance, rng)
	local m = Kit.model(F, "북진대 터")
	local st = Land.STARS.north
	local c = Vector3.new(st.x, st.height, st.z)
	local wind = Vector3.new(0.45, 0, 0.9).Unit -- 북서 빙하에서 불어오는 바람
	-- 돌기둥 여덟 (둘은 부러졌다)
	for k = 0, 7 do
		local a = rad(22.5 + k * 45)
		local p = c + Vector3.new(cos(a), 0, sin(a)) * 21.5
		if clearOf(p.X, p.Z, 1.5) then
			local broken = k == 2 or k == 5
			local h = if broken then rng(3.5, 5) else rng(8.5, 10)
			local g = span(p.X, p.Z, 1.2)
			local look = face(p, c)
			block(m, "Gidan", Vector3.new(2.8, 1, 2.8), CFrame.new(p.X, g + 0.2, p.Z) * rot(look), NC.frostRock, M.Slate)
			block(m, "Dolgidung", Vector3.new(1.7, h, 1.7), CFrame.new(p.X, g + 0.7 + h / 2, p.Z) * rot(look) * CFrame.Angles(rng(-0.03, 0.03), 0, rng(-0.03, 0.03)), Color3.fromRGB(140, 140, 138), M.Granite)
			if broken then
				-- 부러진 윗동이 곁에 누웠다
				local q = p + Vector3.new(cos(a + 1.2), 0, sin(a + 1.2)) * 3.5
				block(m, "Dolgidung", Vector3.new(1.6, 1.6, rng(4, 5)), CFrame.new(q.X, surf(q.X, q.Z) + 0.5, q.Z) * CFrame.Angles(0, a + 0.8, 0.1), Color3.fromRGB(136, 136, 134), M.Granite)
			else
				block(m, "Nun", Vector3.new(2, 0.5, 2), CFrame.new(p.X, g + 0.7 + h + 0.25, p.Z) * rot(look), NC.snow, M.Snow)
			end
		end
	end
	-- 찢긴 깃발 넷
	for k = 0, 3 do
		local a = rad(k * 90 + rng(-6, 6))
		local p = c + Vector3.new(cos(a), 0, sin(a)) * 26
		if clearOf(p.X, p.Z, 1) then
			tornBanner(m, rng, Vector3.new(p.X, span(p.X, p.Z, 0.8), p.Z), wind, if k % 2 == 0 then NC.navy else Color3.fromRGB(28, 30, 36))
		end
	end
	-- 바람막이 돌담: 북쪽 반원 (군데군데 무너졌다)
	for k = 0, 7 do
		local a0 = rad(196 + k * 19)
		local a1 = a0 + rad(16)
		if k ~= 3 then
			local r = 30.5
			local p0 = c + Vector3.new(cos(a0), 0, sin(a0)) * r
			local p1 = c + Vector3.new(cos(a1), 0, sin(a1)) * r
			local mid = (p0 + p1) / 2
			local g = span(mid.X, mid.Z, 3)
			local h = if k == 6 then 1.4 else rng(2.4, 3.2)
			local look = face(mid, p1)
			local len = (p1 - p0).Magnitude
			block(m, "Dam", Vector3.new(1.8, h + 1, len), CFrame.new(mid.X, g + (h - 1) / 2, mid.Z) * rot(look), Color3.fromRGB(124, 122, 118), M.Cobblestone)
			block(m, "Nun", Vector3.new(2.1, 0.45, len + 0.2), CFrame.new(mid.X, g + h + 0.2, mid.Z) * rot(look), NC.snow, M.Snow)
		end
	end
	-- 돌계단: 오름길이 닿는 남남동 가장자리
	local roadEnd = Vector3.new(Land.ROADS[2][2][1], 0, Land.ROADS[2][2][2])
	local rdir = (Vector3.new(c.X, 0, c.Z) - roadEnd).Unit
	for k = 0, 3 do
		local q = roadEnd + rdir * (k * 1.6 - 2)
		local g = surf(q.X, q.Z)
		local topY = min(c.Y + 0.2, g + 0.5 + k * 0.15)
		local look = face(q, q + rdir)
		block(m, "Gyedan", Vector3.new(8, topY - g + 1.5, 1.7), CFrame.new(q.X, (topY + g - 1.5) / 2, q.Z) * rot(look), P.granite:Lerp(NC.frostRock, 0.3), M.Granite)
	end
	for _, s in { -1, 1 } do
		local q = roadEnd + Vector3.new(-rdir.Z, 0, rdir.X) * s * 5.2 + rdir * 1
		pathMarker(m, rng, q, q + rdir)
	end
	-- 오름길 위 홍살문 (전송진과 떨어지게 길 바깥쪽에)
	local gp = roadEnd - rdir * 10
	hongsalmun(m, Vector3.new(gp.X, surf(gp.X, gp.Z), gp.Z), rdir, 9)
	reserve(gp.X, gp.Z, 6)
	reserve(c.X, c.Z, 34)
	return m
end

-- 설하 빙하 ------------------------------------------------------------------------------

-- 빙하 꺾은선 위 자리 (0~1 길이 비율): 자리, 흐름 방향
local function glacierFrame(s: number): (Vector3, Vector3)
	local pts = GLACIER.pts
	local total = 0
	local lens = {}
	for i = 1, #pts - 1 do
		local l = sqrt((pts[i + 1][1] - pts[i][1]) ^ 2 + (pts[i + 1][2] - pts[i][2]) ^ 2)
		lens[i] = l
		total += l
	end
	local want = s * total
	for i = 1, #pts - 1 do
		if want <= lens[i] or i == #pts - 1 then
			local t = math.clamp(want / lens[i], 0, 1)
			local a, b = pts[i], pts[i + 1]
			local p = Vector3.new(a[1] + (b[1] - a[1]) * t, 0, a[2] + (b[2] - a[2]) * t)
			local dir = Vector3.new(b[1] - a[1], 0, b[2] - a[2]).Unit
			return p, dir
		end
		want -= lens[i]
	end
	return Vector3.zero, Vector3.zAxis
end

local function onGlacier(x: number, z: number): boolean
	local d = Land.polyDist(x, z, GLACIER, 100)
	return d < 58 and surf(x, z) > 40 and Land.shoreDist(x, z) < -30
end

local function buildGlacier(F: Instance, rng)
	local m = Kit.folder(F, "설하")
	local iceColor = NC.ice
	-- 크레바스 띠: 흐름에 가로로 갈라진 틈 (검푸른 틈 + 양옆 얼음 턱)
	for _, s0 in { 0.1, 0.21, 0.34, 0.5, 0.63, 0.77 } do
		local p, dir = glacierFrame(s0)
		local side = Vector3.new(-dir.Z, 0, dir.X)
		local count = floor(rng(3, 5.99))
		for k = 1, count do
			local c = p + dir * ((k - count / 2) * rng(7, 10)) + side * rng(-26, 26)
			local farTarn = (c - Vector3.new(TARN.x, 0, TARN.z)).Magnitude > 70
			if onGlacier(c.X, c.Z) and clearOf(c.X, c.Z, 6) and farTarn then
				local len = rng(16, 30)
				local wid = rng(1.2, 2.2)
				local yaw = math.atan2(side.X, side.Z) + rng(-0.25, 0.25)
				local crack = groundSlab(m, "Teum", c.X, c.Z, len, wid, yaw, 0.4, NC.crevasse, M.Glass, 0.1)
				crack.Reflectance = 0.05
				local cdir = Vector3.new(sin(yaw), 0, cos(yaw))
				local cside = Vector3.new(cdir.Z, 0, -cdir.X)
				for _, e in { 1, -1 } do
					local q = c + cside * e * (wid / 2 + 0.45)
					local lip = groundSlab(m, "Teok", q.X, q.Z, len * rng(0.75, 0.95), 0.9, yaw, 1.1, iceColor:Lerp(NC.snow, 0.3), M.Glacier, 0.45)
					lip.Transparency = 0.1
				end
				reserve(c.X, c.Z, len / 2)
			end
		end
	end
	-- 세락: 가파른 머리 쪽(응봉 아래)과 가장자리에 솟은 얼음 덩이
	local function serac(x: number, z: number, size: number)
		local g = span(x, z, size * 0.4)
		local h = size * rng(1.1, 1.8)
		local p = block(
			m,
			"Serak",
			Vector3.new(size, h, size * rng(0.6, 0.9)),
			CFrame.new(x, g + h * 0.32, z) * CFrame.Angles(rng(-0.25, 0.25), rng(0, TAU), rng(-0.25, 0.25)),
			iceColor:Lerp(NC.iceDeep, rng(0, 0.5)),
			M.Glacier
		)
		p.Transparency = 0.12
		p.Reflectance = 0.06
		return p
	end
	for k = 1, 22 do
		local s0 = if k <= 12 then rng(0.02, 0.16) else rng(0.2, 0.85)
		local p, dir = glacierFrame(s0)
		local side = Vector3.new(-dir.Z, 0, dir.X)
		local lateral = if k <= 12 then rng(-45, 45) else (if k % 2 == 0 then 1 else -1) * rng(36, 52)
		local c = p + side * lateral + dir * rng(-8, 8)
		if onGlacier(c.X, c.Z) and clearOf(c.X, c.Z, 6) and isFree(c.X, c.Z, 3) then
			serac(c.X, c.Z, rng(3.5, 8))
			if k % 3 == 0 then
				serac(c.X + rng(-4, 4), c.Z + rng(-4, 4), rng(2.5, 4))
			end
			reserve(c.X, c.Z, 4)
		end
	end
	-- 바다에 닿는 얼음 벼랑: 빙하 끝 둘레에 얼음 기둥 (바닷물에서 빙하 겉까지)
	local mouth = Kit.model(m, "얼음 벼랑")
	for x = -372, -226, 7 do
		local zEdge = nil
		for z = -1690, -1800, -1.5 do
			if Land.height(x, z) < 6 then
				zEdge = z
				break
			end
		end
		local d = Land.polyDist(x, -1735, GLACIER, 200)
		if zEdge and d < 72 then
			local topY = Land.height(x, zEdge + 9) + rng(2, 9) * (1 - d / 90)
			local bottom = Land.SEA - 4
			local p = block(
				mouth,
				"Eoreumbyeok",
				Vector3.new(rng(6, 9), topY - bottom, rng(5, 8)),
				CFrame.new(x, (topY + bottom) / 2, zEdge + 1.5) * CFrame.Angles(rng(-0.12, 0.04), rng(-0.2, 0.2), rng(-0.06, 0.06)),
				iceColor:Lerp(NC.iceDeep, rng(0.1, 0.6)),
				M.Glacier
			)
			p.Transparency = 0.08
		end
	end
	-- 떨어져 나간 얼음 덩이 (바다 위)
	for k = 1, 6 do
		local x = rng(-380, -220)
		local z = rng(-1800, -1770) - k * 3
		local s = rng(3, 8)
		local berg = block(mouth, "Bingsan", Vector3.new(s * 1.4, s, s * 1.1), CFrame.new(x, Land.SEA + s * 0.2, z) * CFrame.Angles(rng(-0.3, 0.3), rng(0, TAU), rng(-0.3, 0.3)), iceColor:Lerp(NC.snow, rng(0, 0.4)), M.Glacier)
		berg.Transparency = 0.1
	end
	-- 빙하 끝 전망: 비석
	local poi = Sites.byId.glacier_mouth
	if poi then
		local q = Vector3.new(poi.x + 14, 0, poi.z + 6)
		Kit.stele(m, Vector3.new(q.X, span(q.X, q.Z, 1.5) - 0.4, q.Z), "설하", Vector3.new(poi.x, 0, poi.z - 100))
		reserve(q.X, q.Z, 4)
	end
	return m
end

-- 빙경담: 빙하 위 얼어붙은 못. 가운데 상품 영맥(허브). 높은 가에 서리 사당, 둘레에 얼음 등
local function iceLantern(parent: Instance, p: Vector3)
	local m = Kit.model(parent, "얼음 등")
	local g = span(p.X, p.Z, 1)
	block(m, "Badak", Vector3.new(1.8, 1.2, 1.8), CFrame.new(p.X, g + 0.2, p.Z) * CFrame.Angles(0, rad(45), 0), NC.frostRock, M.Slate)
	local post = block(m, "Eoreum", Vector3.new(0.9, 3, 0.9), CFrame.new(p.X, g + 2.2, p.Z), NC.ice, M.Glacier)
	post.Transparency = 0.3
	local lamp = block(m, "Bul", Vector3.new(1.1, 1.2, 1.1), CFrame.new(p.X, g + 4.3, p.Z) * CFrame.Angles(0, rad(45), 0), Color3.fromRGB(170, 220, 255), M.Neon)
	lamp.Transparency = 0.15
	Kit.light(lamp, Color3.fromRGB(150, 205, 255), 14, 1.3)
	block(m, "Gat", Vector3.new(1.6, 0.4, 1.6), CFrame.new(p.X, g + 5.1, p.Z) * CFrame.Angles(0, rad(45), 0), NC.snow, M.Snow)
	return m
end

local function buildTarn(F: Instance, rng)
	local m = Kit.folder(F, "빙경담")
	local c = Vector3.new(TARN.x, 0, TARN.z)
	-- 얼음 등 여섯 (못 가장자리)
	for k = 0, 5 do
		local a = rad(k * 60 + 15)
		local p = c + Vector3.new(cos(a), 0, sin(a)) * 31
		if clearOf(p.X, p.Z, 1) then
			iceLantern(m, p)
		end
	end
	-- 서리 사당: 못가에서 가장 평평한 곳 (남쪽 높은 가 쪽에서 고른다), 못을 내려다본다. 지붕에 눈
	local bestA, bestSpan = rad(102), huge
	for deg = 40, 170, 10 do
		local a = rad(deg)
		local q = c + Vector3.new(cos(a), 0, sin(a)) * 46
		local lo, hi = rectSpan(face(q, c), 13, 12)
		if hi - lo < bestSpan then
			bestA, bestSpan = a, hi - lo
		end
	end
	local sp = c + Vector3.new(cos(bestA), 0, sin(bestA)) * 46
	local look = face(sp, c)
	-- 비탈에 반쯤 묻은 돌 단 (윗면은 높은 쪽과 낮은 쪽 가운데보다 조금 위)
	local lo, hi = rectSpan(CFrame.new(sp) * rot(look), 13, 12)
	local top = lo + (hi - lo) * 0.65 + 0.4
	block(m, "Chukdae", Vector3.new(13, top - lo + 2, 12), CFrame.new(sp.X, (top + lo - 2) / 2, sp.Z) * rot(look), NC.frostRock, M.Cobblestone)
	block(m, "Gapseok", Vector3.new(13.4, 0.5, 12.4), CFrame.new(sp.X, top - 0.25, sp.Z) * rot(look), P.granite, M.Granite)
	local shrine = Build.house(m, CFrame.new(sp.X, top, sp.Z) * rot(look), {
		bays = { 1, 1 },
		bay = 7,
		pillarH = 6.8,
		plinth = 1.2,
		eave = 3,
		style = "temple",
		detail = 1,
		roof = "gable",
		bands = 3,
		roofColor = Color3.fromRGB(214, 220, 230),
		name = "서리 사당",
	})
	shrine:SetAttribute("Place", "빙경담")
	-- 사당 앞 비석과 얼음 등 둘
	local fp = (CFrame.new(sp.X, top, sp.Z) * rot(look) * CFrame.new(5.5, 0, -10)).Position
	Kit.stele(m, Vector3.new(fp.X, span(fp.X, fp.Z, 1.4) - 0.4, fp.Z), "빙경담", c)
	for _, s in { -1, 1 } do
		local q = (CFrame.new(sp.X, top, sp.Z) * rot(look) * CFrame.new(s * 4.2, 0, -8.5)).Position
		iceLantern(m, q)
	end
	reserve(sp.X, sp.Z, 12)
	-- 못가 얼음 바위
	for k = 0, 6 do
		local a = rad(k * 51 + rng(-10, 10))
		local r = rng(36, 46)
		local p = c + Vector3.new(cos(a), 0, sin(a)) * r
		if isFree(p.X, p.Z, 4) and clearOf(p.X, p.Z, 3) then
			reserve(p.X, p.Z, 4)
			iceRock(m, p.X, p.Z, rng(3, 6), rng)
		end
	end
	return m
end

-- 응봉: 매 부리처럼 솟은 바위 머리, 아래 비탈에 전나무
local function buildPeak(F: Instance, rng)
	local m = Kit.folder(F, "응봉")
	local pk = Land.PEAKS[1]
	local cx, cz = pk[1], pk[2]
	local top = surf(cx, cz)
	local crown = Kit.model(m, "바위 머리")
	for k = 0, 6 do
		local a = rad(k * 51 + rng(-12, 12))
		local r = if k == 0 then 0 else rng(5, 12)
		local x, z = cx + cos(a) * r, cz + sin(a) * r
		local g = span(x, z, 2.5)
		local h = if k == 0 then 26 else rng(9, 20)
		local w = rng(4, 7)
		local p = block(
			crown,
			"Bawi",
			Vector3.new(w, h, w * rng(0.6, 0.9)),
			CFrame.new(x, g + h / 2 - 2, z) * CFrame.Angles(rng(-0.14, 0.14), rng(0, TAU), rng(-0.14, 0.14)),
			NC.darkRock:Lerp(NC.frostRock, rng(0, 0.5)),
			M.Slate
		)
		if k % 2 == 0 then
			block(crown, "Nun", Vector3.new(p.Size.X * 0.9, 0.6, p.Size.Z * 0.9), p.CFrame * CFrame.new(0, h / 2 + 0.2, 0), NC.snow, M.Snow)
		end
	end
	-- 매 부리: 북쪽으로 기울어 내민 큰 바위 판
	local beakBase = Vector3.new(cx - 3, top + 14, cz - 4)
	beam(crown, "Buri", beakBase, beakBase + Vector3.new(-2, 9, -13), 5, 3.4, NC.darkRock, M.Slate)
	-- 아래 비탈 전나무 (동쪽과 남쪽)
	for _, g in { { -660, -905, 36, 4 }, { -700, -820, 30, 3 }, { -820, -1060, 30, 2 } } do
		firGrove(m, rng, g[1], g[2], g[3], g[4], function(x, z, h)
			return h > 110 and h < 280 and slope(x, z) < 1.1 and not onGlacier(x, z)
		end, 0.6)
	end
	return m
end

-- 짓기 ------------------------------------------------------------------------------------

function Region.build(root: Instance, rng: (number, number) -> number)
	initClear()
	table.clear(taken)
	local F = Kit.folder(root, "북쪽")
	local lake = Kit.folder(F, "명경호")
	buildIslet(lake, rng)
	buildBridge(lake, rng)
	buildWaterSite(lake, rng)
	buildHomestead(lake, rng)
	buildSteppingStones(lake, rng)
	buildLakeShore(lake, rng)
	buildNorthBank(lake, rng)
	buildFalls(F, rng)
	buildTable(F, rng)
	buildStar(F, rng)
	buildTarn(F, rng)
	buildSnowfield(F, rng)
	buildGlacier(F, rng)
	buildPeak(F, rng)
	return F
end

return Region
