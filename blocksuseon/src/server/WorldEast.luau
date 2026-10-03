-- 동쪽 땅: 만년목, 태고림, 무명사 옛터, 조양대, 청음죽림·청음암, 백초원·마령채·팔방석진, 망선대·운제, 청허경.
-- World.luau 가 build(root, rng) 를 부른다. root 밑에 폴더 "동쪽" 하나를 만들고 모두 그 안에 넣는다.
--
-- 땅 높이는 Land.surface (떠 있는 섬 위면 섬 윗면). 비탈에 놓는 것은 둘레에서 가장 낮은 곳에 맞추고(나무),
-- 집은 기단 밑을 장대석으로 메운다. 과업 자리·영맥(7)·전송진(9)·비급 자리(3.5) 둘레는 비워 둔다:
-- 자리는 짓는 때에 WorldSites 에서 읽는다 (가운데 담당이 전송진을 옮겨도 따라간다).
-- 길(Land.ROADS, 깎은 길 BENCHES, 여기서 낸 숲길) 위에는 나무를 심지 않는다.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:FindFirstChild("Shared") or ReplicatedStorage:WaitForChild("Shared")

local Land = require(Shared.Land)
local Build = require(script.Parent.WorldBuild)
local Kit = require(script.Parent.WorldKit)
local Sites = require(script.Parent.WorldSites)

local Region = {}

local P = Build.P
local block, wedge, beam, cyl, ball, deco, face =
	Build.block, Build.wedge, Build.beam, Build.cyl, Build.ball, Build.deco, Build.face
local V3 = Vector3.new
local CF = CFrame.new
local ANG = CFrame.Angles
local sin, cos, sqrt, floor, max, min, abs, pi, rad, atan2 =
	math.sin, math.cos, math.sqrt, math.floor, math.max, math.min, math.abs, math.pi, math.rad, math.atan2
local MAT = Enum.Material
local TAU = pi * 2

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- 빛깔 (단청은 Build.P 를 쓰고, 여기 것은 숲·초원·하늘섬 살림)
local C = {
	barkOld = rgb(84, 70, 58), -- 만년목 껍질
	moss = rgb(92, 120, 62),
	mossHang = rgb(150, 166, 112),
	straw = rgb(198, 174, 116), -- 금줄
	hanji = rgb(246, 242, 230),
	earth = rgb(118, 96, 70), -- 숲길 흙
	felt = rgb(232, 222, 200), -- 천막 펠트
	feltRoof = rgb(214, 202, 178),
	doorRed = rgb(186, 82, 50),
	cloud = rgb(246, 248, 255),
	marble = rgb(236, 236, 230), -- 운제·청허경 흰 돌
	jade = rgb(222, 232, 224),
	gold = rgb(208, 170, 92),
	glazed = rgb(62, 100, 126), -- 청기와
	glazedDark = rgb(44, 72, 92),
	ivory = rgb(240, 234, 220),
	rune = rgb(150, 220, 255),
	lichen = rgb(170, 176, 112),
	lichenOrange = rgb(196, 140, 72),
	bronze = rgb(92, 82, 58),
	water = rgb(150, 200, 226),
}
-- 오방색 (천 조각, 깃발: 채도를 낮춘 것)
local OBANG = { rgb(64, 96, 168), rgb(192, 70, 52), rgb(222, 184, 80), rgb(240, 238, 230), rgb(48, 46, 46) }
local GRASS = { rgb(150, 162, 86), rgb(178, 172, 106), rgb(124, 148, 74), rgb(198, 186, 130), rgb(140, 150, 70) }
local FLOWERS = { rgb(246, 244, 236), rgb(236, 206, 84), rgb(170, 128, 206), rgb(226, 112, 92), rgb(120, 150, 222) }

local R: (number, number) -> number = Kit.makeRng(1) -- build() 가 넘겨받은 rng 로 바꾼다

local function surf(x: number, z: number): number
	return Land.surface(x, z)
end

-- 둘레(반지름 r, 두 겹 여덟 군데)에서 가장 낮은 곳, 높은 곳
local function span(x: number, z: number, r: number): (number, number)
	local h0 = surf(x, z)
	local lo, hi = h0, h0
	if r > 0 then
		for k = 0, 7 do
			local a = k * pi / 4
			for _, f in { 0.5, 1 } do
				local h = surf(x + cos(a) * r * f, z + sin(a) * r * f)
				lo, hi = min(lo, h), max(hi, h)
			end
		end
	end
	return lo, hi
end
local function lowAt(x: number, z: number, r: number): number
	return (span(x, z, r))
end

-- 돌린 네모 바닥(가운데 x, z, 방향 yaw, 반너비 hx, 반깊이 hz)의 가장 낮은 곳, 높은 곳
local function rectSpan(x: number, z: number, yaw: number, hx: number, hz: number): (number, number)
	local lo, hi = math.huge, -math.huge
	local c, s = cos(yaw), sin(yaw)
	for i = -2, 2 do
		for j = -2, 2 do
			local u, v = hx * i / 2, hz * j / 2
			local h = surf(x + u * c + v * s, z - u * s + v * c)
			lo, hi = min(lo, h), max(hi, h)
		end
	end
	return lo, hi
end

local function yawTo(x: number, z: number, tx: number, tz: number): number
	return atan2(-(tx - x), -(tz - z))
end

-- 모델 통째로 옮기기 (Lune 에는 PivotTo 가 없다): from 에 있던 것을 to 로
local function moveModel(m: Instance, from: CFrame, to: CFrame)
	local k = to * from:Inverse()
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			d.CFrame = k * d.CFrame
		end
	end
end

local function partCount(m: Instance): number
	local n = 0
	for _, d in m:GetDescendants() do
		if d:IsA("BasePart") then
			n += 1
		end
	end
	return n
end

-- 비워 둘 자리와 차지한 자리 ------------------------------------------------------------------

local CLEAR: { { number } } = {}
local TAKEN: { [number]: { { number } } } = {}
local CELL = 32
local ROADS = {}
for _, road in Land.ROADS do
	table.insert(ROADS, Land.poly(road))
end
local PATHS = {} -- 여기서 낸 길 (Land.poly)

local function resetZones()
	CLEAR = {}
	TAKEN = {}
	PATHS = {}
	for _, s in Sites.WAYPOINTS do
		table.insert(CLEAR, { s.x, s.z, 9.5 })
	end
	for _, s in Sites.TASK do
		table.insert(CLEAR, { s.x, s.z, (s.radius or 7) + 0.5 })
	end
	for _, s in Sites.VEINS do
		table.insert(CLEAR, { s.x, s.z, (if s.radius then s.radius + 1 else 7) + 0.5 })
	end
	for _, q in Sites.MANUALS do
		table.insert(CLEAR, { q[1], q[2], 3.5 })
	end
end

local function take(x: number, z: number, r: number)
	local e = { x, z, r }
	for i = floor((x - r) / CELL), floor((x + r) / CELL) do
		for j = floor((z - r) / CELL), floor((z + r) / CELL) do
			local key = i * 65536 + j
			local list = TAKEN[key]
			if not list then
				list = {}
				TAKEN[key] = list
			end
			table.insert(list, e)
		end
	end
end

local function clashes(x: number, z: number, r: number): boolean
	for i = floor((x - r) / CELL), floor((x + r) / CELL) do
		for j = floor((z - r) / CELL), floor((z + r) / CELL) do
			local list = TAKEN[i * 65536 + j]
			if list then
				for _, e in list do
					local dx, dz, rr = x - e[1], z - e[2], r + e[3]
					if dx * dx + dz * dz < rr * rr then
						return true
					end
				end
			end
		end
	end
	return false
end

local function inClear(x: number, z: number, r: number): boolean
	for _, c in CLEAR do
		local dx, dz, rr = x - c[1], z - c[2], r + c[3]
		if dx * dx + dz * dz < rr * rr then
			return true
		end
	end
	return false
end

local function nearPath(x: number, z: number, w: number): boolean
	for _, p in ROADS do
		if Land.polyDist(x, z, p, w + 1) < w then
			return true
		end
	end
	for _, b in Land.BENCHES do
		if Land.polyDist(x, z, b, w + 1) < w then
			return true
		end
	end
	for _, p in PATHS do
		if Land.polyDist(x, z, p, w + 1) < w then
			return true
		end
	end
	return false
end

-- 이 자리에 반지름 r 짜리를 놓아도 되는가
type FreeOpts = { path: number?, sky: boolean?, shore: number? }
local function free(x: number, z: number, r: number, opts: FreeOpts?): boolean
	local o: FreeOpts = opts or {}
	if inClear(x, z, r) or clashes(x, z, r) then
		return false
	end
	if o.path ~= 0 and nearPath(x, z, r + (o.path or 5)) then
		return false
	end
	if o.sky then
		for k = 0, 7 do
			local a = k * pi / 4
			if not Land.island(x + cos(a) * (r + 4), z + sin(a) * (r + 4)) then
				return false
			end
		end
		return Land.island(x, z) ~= nil
	end
	if Land.island(x, z) then
		return false -- 하늘섬 밑 바다
	end
	local h = Land.height(x, z)
	if Land.water(x, z, h) or h < Land.SEA + 3 then
		return false
	end
	return Land.shoreDist(x, z) < -(o.shore or 18)
end

-- 기단 놓기: 집 cf (기단 밑 가운데) 를 돌려준다. 비탈이면 높은 쪽을 조금 묻고 낮은 쪽은 장대석으로 받친다
local function siteCf(
	parent: Instance,
	x: number,
	z: number,
	tx: number,
	tz: number,
	hx: number,
	hz: number,
	sink: number?
): CFrame
	local yaw = yawTo(x, z, tx, tz)
	local lo, hi = rectSpan(x, z, yaw, hx, hz)
	local y = max(lo + 0.5, hi - (sink or 1.1))
	if y - 0.6 > lo + 0.15 then
		local depth = y - lo + 1.2
		block(
			parent,
			"Badchim",
			V3(hx * 2 - 0.4, depth, hz * 2 - 0.4),
			CF(x, y - 0.55 - depth / 2, z) * ANG(0, yaw, 0),
			P.graniteDark,
			MAT.Granite
		)
	end
	return CF(x, y, z) * ANG(0, yaw, 0)
end

-- 작은 꾸밈 ---------------------------------------------------------------------------------

local function decoBlock(
	parent: Instance,
	name: string,
	size: Vector3,
	cf: CFrame,
	color: Color3,
	material: Enum.Material?
)
	local p = deco(block(parent, name, size, cf, color, material))
	p.CastShadow = false
	return p
end

-- 돌등 (작은 석등 다섯 조각). 길 따라 세운다
local function smallLantern(parent: Instance, ground: Vector3, stone: Color3?, glow: Color3?)
	local m = Kit.model(parent, "돌등")
	local s = stone or P.granite
	block(m, "Hadae", V3(1.9, 1.0, 1.9), CF(ground), s, MAT.Granite)
	block(m, "Ganju", V3(0.8, 2.6, 0.8), CF(ground + V3(0, 1.8, 0)), s, MAT.Granite)
	local fire = block(m, "Bul", V3(1.25, 1.1, 1.25), CF(ground + V3(0, 3.65, 0)), glow or rgb(255, 204, 140), MAT.Neon)
	block(m, "Okgae", V3(2.3, 0.55, 2.3), CF(ground + V3(0, 4.45, 0)) * ANG(0, rad(45), 0), P.graniteDark, MAT.Granite)
	ball(m, "Boju", ground + V3(0, 4.95, 0), 0.7, s, MAT.Granite)
	Kit.light(fire, glow or rgb(255, 190, 120), 14, 1.1)
	return m
end

-- 쌓은 돌탑 (돌 n 개, 위로 갈수록 작게)
local function stoneStack(parent: Instance, x: number, z: number, n: number, size: number, color: Color3?)
	local m = Kit.model(parent, "돌탑")
	local y = lowAt(x, z, size * 0.4) - 0.2
	local s = size
	for _ = 1, n do
		local h = s * R(0.42, 0.55)
		block(
			m,
			"Dol",
			V3(s, h, s * R(0.8, 1)),
			CF(x + R(-0.12, 0.12) * s, y + h / 2, z + R(-0.12, 0.12) * s)
				* ANG(R(-0.08, 0.08), R(0, TAU), R(-0.08, 0.08)),
			(color or P.granite):Lerp(P.graniteDark, R(0, 0.6)),
			MAT.Slate
		)
		y += h * 0.92
		s *= R(0.72, 0.84)
		if s < 0.9 then
			break
		end
	end
	return m, y
end

-- 오색 천을 단 장대 (돌무더기·석진 곁)
local function prayerPole(parent: Instance, x: number, z: number, h: number)
	local m = Kit.model(parent, "오색 장대")
	local g = surf(x, z)
	cyl(m, "Jangdae", V3(x, g - 0.8, z), V3(x, g + h, z), 0.35, P.woodDark, MAT.Wood)
	ball(m, "Kkokji", V3(x, g + h + 0.2, z), 0.55, P.hwang, MAT.Metal)
	for k = 1, 5 do
		local a = rad(k * 72 + R(-15, 15))
		local y = g + h - 0.6 - k * 0.15
		local out = V3(cos(a), 0, sin(a))
		local top = V3(x, y, z) + out * 0.3
		local cf = face(top, top + out) * CF(0, -1.1, -0.55) * ANG(rad(R(8, 18)), 0, 0)
		decoBlock(m, "Cheon", V3(0.7, 2.4, 0.05), cf, OBANG[k], MAT.Fabric)
	end
	return m
end

-- 풀포기 (가는 잎 넷): 초원의 키 큰 풀
local function tuft(parent: Instance, x: number, z: number, s: number, colorIdx: number?)
	local m = Kit.model(parent, "풀포기")
	local g = surf(x, z)
	local col = GRASS[colorIdx or (1 + floor(R(0, #GRASS - 0.01)))]
	for _ = 1, 4 do
		local a = R(0, TAU)
		local h = s * R(0.7, 1.1)
		local foot = V3(x + cos(a) * 0.35, g - 0.35, z + sin(a) * 0.35)
		local lean = R(0.25, 0.6)
		local dir = V3(cos(a) * lean, 1, sin(a) * lean).Unit
		local p =
			deco(beam(m, "Pul", foot, foot + dir * h, R(0.5, 0.9), 0.14, col:Lerp(GRASS[4], R(0, 0.3)), MAT.Grass))
		p.CastShadow = false
	end
	return m
end

-- 들꽃 무더기: 낮은 덤불 하나에 꽃 다섯
local function flowers(parent: Instance, x: number, z: number)
	local col = FLOWERS[1 + floor(R(0, #FLOWERS - 0.01))]
	return Build.shrub(parent, V3(x, surf(x, z) - 0.25, z), R, {
		size = R(1.8, 2.6),
		blobs = 1,
		leaves = { rgb(108, 140, 70), rgb(122, 150, 76) },
		flowers = col,
	})
end

-- 버섯 무더기 (glow 면 옥빛으로 은은히)
local function mushrooms(parent: Instance, x: number, z: number, glow: boolean?)
	local m = Kit.model(parent, "버섯")
	for _ = 1, 3 do
		local px, pz = x + R(-1.2, 1.2), z + R(-1.2, 1.2)
		local g = surf(px, pz)
		local h = R(0.6, 1.3)
		local d = R(0.9, 1.6)
		cyl(m, "Julgi", V3(px, g - 0.3, pz), V3(px, g + h, pz), d * 0.28, rgb(232, 224, 204), MAT.SmoothPlastic)
		local cap = cyl(
			m,
			"Gat",
			V3(px, g + h - 0.05, pz),
			V3(px, g + h + d * 0.28, pz),
			d,
			if glow then rgb(120, 220, 210) else (if R(0, 1) > 0.5 then rgb(176, 72, 52) else rgb(160, 122, 84)),
			if glow then MAT.Neon else MAT.SmoothPlastic
		)
		if glow then
			cap.Transparency = 0.15
		end
	end
	return m
end

-- 나무 ------------------------------------------------------------------------------------

local LEAVES = {
	{ P.leafDeep, P.leaf, P.leafLight },
	{ rgb(48, 90, 54), P.leafDeep, P.leaf },
	{ P.leafDeep, rgb(98, 142, 68), P.leafYellow },
	{ rgb(54, 98, 62), rgb(76, 126, 74), rgb(110, 156, 92) },
}
local function leaves(): { Color3 }
	return LEAVES[1 + floor(R(0, #LEAVES - 0.01))]
end

-- 큰 활엽수. roots 면 줄기 밑에 판뿌리 몇 개
local function bigTree(parent: Instance, x: number, z: number, h: number, opts: { [string]: any }?)
	local o = opts or {}
	local tw = h * 0.11
	local base = V3(x, lowAt(x, z, tw * 0.8) - 0.15, z)
	local bark = o.bark or (if R(0, 1) > 0.5 then P.bark else rgb(80, 66, 54))
	local m = Build.broadleaf(parent, base, R, {
		height = h,
		blobs = o.blobs or 6,
		branches = o.branches or 2,
		leaves = o.leaves or leaves(),
		bark = bark,
		name = o.name,
	})
	for _ = 1, o.roots or 0 do
		local a = R(0, TAU)
		local reach = tw * R(1.8, 2.6)
		local ex, ez = x + cos(a) * reach, z + sin(a) * reach
		local top = base + V3(cos(a) * tw * 0.25, tw * R(0.8, 1.2), sin(a) * tw * 0.25)
		beam(m, "Root", top, V3(ex, surf(ex, ez) - 0.6, ez), tw * 0.42, tw * 0.36, bark, MAT.Wood)
	end
	take(x, z, tw + 1.5)
	return m
end

local function pineTree(parent: Instance, x: number, z: number, h: number, tiers: number?)
	local base = V3(x, lowAt(x, z, 1.2) - 0.15, z)
	local m = Build.pine(parent, base, R, { height = h, tiers = tiers or 4 })
	take(x, z, h * 0.085 + 1.5)
	return m
end

-- 먼 숲 나무: 줄기 하나에 잎 덩이 셋 (숲 속 깊은 곳, 멀리서 숲의 덩어리를 만든다)
local function farTree(parent: Instance, x: number, z: number, h: number)
	local m = Kit.model(parent, "나무")
	local tw = h * 0.08
	local base = V3(x, lowAt(x, z, tw) - 0.2, z)
	local top = base + V3(R(-1.5, 1.5), h * 0.6, R(-1.5, 1.5))
	beam(m, "Trunk", base - V3(0, 0.6, 0), top + V3(0, tw, 0), tw, tw, P.bark, MAT.Wood)
	Build.canopy(m, top + V3(0, h * 0.14, 0), h * 0.34, h * 0.24, 2, R, leaves(), 0.95)
	take(x, z, tw + 2)
	return m
end

-- 쓰러진 고목: 이끼 낀 통나무, 뿌리 판
local function fallenLog(parent: Instance, x: number, z: number, len: number)
	local m = Kit.model(parent, "쓰러진 나무")
	local a = R(0, TAU)
	local d = R(2.2, 3.2)
	local ax, az = x - cos(a) * len / 2, z - sin(a) * len / 2
	local bx, bz = x + cos(a) * len / 2, z + sin(a) * len / 2
	local pa = V3(ax, lowAt(ax, az, d / 2) + d * 0.32, az)
	local pb = V3(bx, lowAt(bx, bz, d / 2) + d * 0.32, bz)
	cyl(m, "Tong", pa, pb, d, rgb(96, 78, 60), MAT.Wood)
	local mid = (pa + pb) / 2
	decoBlock(
		m,
		"Ikki",
		V3(d * 0.7, 0.3, len * 0.6),
		face(mid + V3(0, d * 0.45, 0), pb + V3(0, d * 0.45, 0)),
		C.moss,
		MAT.LeafyGrass
	)
	-- 뿌리 판 (뽑힌 밑동)
	local u = (pb - pa).Unit
	cyl(
		m,
		"Ppuri",
		pa - u * 0.4 + V3(0, d * 0.5, 0),
		pa - u * 1.1 + V3(0, d * 0.5, 0),
		d * 2.2,
		rgb(88, 70, 54),
		MAT.Ground
	)
	take(x, z, len / 2 + 1)
	return m
end

-- 만년목 ---------------------------------------------------------------------------------
--
-- 목 오행처(el_wood) 자리 바로 북쪽에 선 큰 나무 (높이 90, 잎 너비 120 남짓). 자리(7)는 밑동 앞 빈터로 남긴다.
-- 굵은 몸통을 판뿌리 일곱이 받치고(밑동이 넓게 퍼진다) 비튼 줄기 셋이 감아 오른다. 낮게 갈라진 큰 가지 여섯이
-- 옆으로 멀리 뻗어 우산처럼 넓고 납작한 잎 구름(가운데·가지 끝·그 사이 아랫단)을 받친다. 잎 밑에 늘어진 이끼.
-- 밑동에는 금줄(새끼줄에 한지·오색 천), 돌 제단과 제물, 절하는 돌, 돌탑 둘. 둘레에 선돌 고리 (남쪽 길 쪽은 연다).

local function ancientTree(root: Instance)
	local f = Kit.folder(root, "만년목")
	local site = Sites.byId.el_wood
	local sx, sz = site.x, site.z
	local tx, tz = sx + 2, sz - 30
	local y0 = lowAt(tx, tz, 10)
	local m = Kit.model(f, "만년목")
	local bark = C.barkOld
	local barkLight = rgb(104, 88, 72)
	local foot = V3(tx, y0, tz)

	-- 몸통: 낮게 갈라지는 굵은 기둥
	local fork = V3(tx + 1, y0 + 34, tz - 1)
	cyl(m, "Trunk", foot - V3(0, 3, 0), fork + V3(0, 5, 0), 15, bark, MAT.Wood)
	-- 판뿌리: 밑동을 둘러 받치는 굵은 기둥 (땅에 묻히고 위에서 몸통에 스민다)
	local a0 = R(0, TAU)
	for k = 0, 6 do
		local a = a0 + k * TAU / 7 + R(-0.15, 0.15)
		local fr = R(11, 13)
		local fx, fz = tx + cos(a) * fr, tz + sin(a) * fr
		local top = V3(tx + cos(a) * 4, y0 + R(14, 22), tz + sin(a) * 4)
		cyl(
			m,
			"Panppuri",
			V3(fx, surf(fx, fz) - 2.2, fz),
			top,
			R(6.5, 8),
			if k % 2 == 0 then bark else barkLight,
			MAT.Wood
		)
	end
	-- 비틀린 줄기 셋: 몸통 겉을 감아 오른다
	for k = 0, 2 do
		local a = a0 + 0.45 + k * TAU / 3
		local b = a + rad(75)
		cyl(
			m,
			"Kkoim",
			V3(tx + cos(a) * 7.6, y0 + 3, tz + sin(a) * 7.6),
			V3(tx + cos(b) * 5.8, y0 + 34, tz + sin(b) * 5.8),
			4.4,
			barkLight,
			MAT.Wood
		)
	end
	-- 이끼 (몸통 겉에 붙은 판)
	for _ = 1, 5 do
		local a = R(0, TAU)
		local y = y0 + R(10, 32)
		local p = V3(tx + cos(a) * 7.7, y, tz + sin(a) * 7.7)
		decoBlock(m, "Ikki", V3(R(3, 5), R(3, 6), 0.6), face(p, p + V3(cos(a), 0, sin(a))), C.moss, MAT.LeafyGrass)
	end

	-- 큰 가지 여섯: 옆으로 멀리, 두 마디로 꺾여 오른다. 무릎에서 잔가지
	local tips = {}
	local b0 = R(0, TAU)
	for k = 1, 6 do
		local a = b0 + k * TAU / 6 + R(-0.2, 0.2)
		local reach = R(36, 44)
		local start = fork + V3(cos(a) * 3, -5, sin(a) * 3)
		local knee = fork + V3(cos(a) * reach * 0.42, R(8, 12), sin(a) * reach * 0.42)
		local tip = fork + V3(cos(a) * reach, R(15, 21), sin(a) * reach)
		cyl(m, "Gaji", start, knee, 6.2, bark, MAT.Wood)
		cyl(m, "Gaji", knee, tip, 4.2, bark, MAT.Wood)
		local sideA = a + (if k % 2 == 0 then 0.8 else -0.8)
		cyl(m, "Janggaji", knee, knee + V3(cos(sideA) * 15, R(5, 9), sin(sideA) * 15), 2.4, bark, MAT.Wood)
		table.insert(tips, tip)
	end
	cyl(m, "Udeumji", fork, fork + V3(R(-2, 2), 24, R(-2, 2)), 6, bark, MAT.Wood)

	-- 잎 구름: 가운데 넓은 덩이, 가지 끝 여섯, 그 사이 아랫단 여섯 (처진 잎)
	local leaf = { rgb(48, 90, 54), rgb(68, 116, 64), rgb(106, 154, 82) }
	local canopy = Kit.model(m, "잎")
	Build.canopy(canopy, fork + V3(0, 31, 0), 27, 10, 12, R, leaf, 0.66)
	for _, tip in tips do
		Build.canopy(canopy, tip + V3(0, 3, 0), 17, 8, 9, R, leaf, 0.7)
	end
	for k = 1, 6 do
		local a = b0 + (k + 0.5) * TAU / 6
		Build.canopy(
			canopy,
			fork + V3(cos(a) * 36, R(8, 12), sin(a) * 36),
			13,
			6,
			4,
			R,
			{ rgb(44, 84, 50), rgb(62, 108, 60), rgb(90, 138, 74) },
			0.75
		)
	end
	-- 영기: 잎 사이로 옥빛 티끌
	Kit.motes(canopy:GetChildren()[1] :: BasePart, rgb(176, 255, 190), 8)

	-- 늘어진 이끼: 아랫단 잎 덩이 밑에서 드리운다
	local lows = {}
	for _, p in canopy:GetChildren() do
		if p:IsA("BasePart") then
			table.insert(lows, p)
		end
	end
	table.sort(lows, function(a: BasePart, b: BasePart)
		return a.CFrame.Position.Y < b.CFrame.Position.Y
	end)
	for i = 1, 30 do
		local p = lows[1 + (i - 1) % min(#lows, 24)]
		local pos = p.CFrame.Position
		local bottom = pos.Y - p.Size.Y * 0.3
		local len = R(6, 16)
		local q = V3(pos.X + R(-0.3, 0.3) * p.Size.X, bottom - len / 2, pos.Z + R(-0.3, 0.3) * p.Size.Z)
		local a = R(0, TAU)
		decoBlock(
			m,
			"Mosa",
			V3(R(0.35, 0.7), len, 0.18),
			face(q, q + V3(cos(a), 0, sin(a))) * ANG(rad(R(-5, 5)), 0, 0),
			C.mossHang,
			MAT.LeafyGrass
		)
	end

	-- 뿌리: 판뿌리 사이로 땅 위를 기어 나가 묻힌다 (자리 쪽으로는 짧게)
	for k = 0, 7 do
		local a = a0 + TAU / 14 + k * TAU / 8 + R(-0.12, 0.12)
		local reach = R(22, 30)
		local ex, ez = tx + cos(a) * reach, tz + sin(a) * reach
		while (ex - sx) ^ 2 + (ez - sz) ^ 2 < 10 ^ 2 and reach > 14 do
			reach -= 1
			ex, ez = tx + cos(a) * reach, tz + sin(a) * reach
		end
		local start = V3(tx + cos(a) * 7, y0 + R(3, 4.5), tz + sin(a) * 7)
		local kx, kz = tx + cos(a) * reach * 0.6, tz + sin(a) * reach * 0.6
		local knee = V3(kx, surf(kx, kz) + 1.0, kz)
		cyl(m, "Ppuri", start, knee, 3.8, bark, MAT.Wood)
		cyl(m, "Ppuri", knee, V3(ex, surf(ex, ez) - 1.2, ez), 2.4, bark, MAT.Wood)
	end

	-- 금줄: 밑동 둘레 판뿌리 위로 (한지 조각과 오색 천을 끼운다)
	local ropeR, ropeY = 11.6, y0 + 8
	local n = 14
	for k = 0, n - 1 do
		local a1, a2 = k * TAU / n, (k + 1) * TAU / n
		local p1 = V3(tx + cos(a1) * ropeR, ropeY + 0.3 * sin(k * 1.7), tz + sin(a1) * ropeR)
		local p2 = V3(tx + cos(a2) * ropeR, ropeY + 0.3 * sin((k + 1) * 1.7), tz + sin(a2) * ropeR)
		local rope = beam(m, "Geumjul", p1, p2, 0.45, 0.45, C.straw, MAT.Fabric)
		rope.CastShadow = false
		local mid = (p1 + p2) / 2
		local out = V3(cos((a1 + a2) / 2), 0, sin((a1 + a2) / 2))
		local col = if k % 3 == 0 then OBANG[1 + (k // 3) % 5] else C.hanji
		decoBlock(
			m,
			"Jongi",
			V3(0.8, 1.7, 0.06),
			face(mid + out * 0.3 - V3(0, 1.05, 0), mid + out * 2),
			col,
			MAT.Fabric
		)
	end
	-- 돌 제단과 제물 (자리를 바라본다)
	local dir = (V3(sx, 0, sz) - V3(tx, 0, tz)).Unit
	local ap = V3(tx, 0, tz) + dir * 19
	local ag = lowAt(ap.X, ap.Z, 2.8)
	local acf = face(V3(ap.X, ag, ap.Z), V3(sx, ag, sz)) * ANG(0, pi, 0) -- 앞(-Z)이 나무 쪽: 절하는 사람은 자리 쪽에 선다
	block(m, "Jedan", V3(5.4, 0.6, 2.6), acf * CF(0, 2.1, 0), P.granite, MAT.Granite)
	for _, s in { -1, 1 } do
		block(m, "Dari", V3(0.9, 2.3, 2.0), acf * CF(s * 1.9, 0.75, 0), P.graniteDark, MAT.Granite)
	end
	for _, s in { -1, 1 } do
		local bowl = (acf * CF(s * 1.5, 2.6, 0.2)).Position
		cyl(m, "Gureut", bowl - V3(0, 0.2, 0), bowl + V3(0, 0.25, 0), 1.0, rgb(214, 206, 188), MAT.SmoothPlastic)
		ball(
			m,
			"Gwail",
			bowl + V3(0, 0.5, 0),
			0.7,
			if s > 0 then rgb(196, 74, 52) else rgb(222, 170, 70),
			MAT.SmoothPlastic
		)
	end
	local censer = (acf * CF(0, 2.4, 0)).Position
	local hyang = cyl(m, "Hyangno", censer, censer + V3(0, 0.8, 0), 1.1, C.bronze, MAT.Metal)
	local smoke = Instance.new("ParticleEmitter")
	smoke.Name = "Yeon"
	smoke.Texture = "rbxasset://textures/particles/smoke_main.dds"
	smoke.Rate = 2
	smoke.Lifetime = NumberRange.new(4, 6)
	smoke.Speed = NumberRange.new(0.6, 1.2)
	smoke.SpreadAngle = Vector2.new(8, 8)
	smoke.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 1.6) })
	smoke.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.55), NumberSequenceKeypoint.new(1, 1) })
	smoke.Color = ColorSequence.new(rgb(230, 230, 236))
	smoke.EmissionDirection = Enum.NormalId.Right
	smoke.Parent = hyang
	Kit.light(hyang, rgb(170, 255, 180), 26, 1.1)
	-- 절하는 돌 (낮은 판)
	block(m, "Baeryeseok", V3(4.4, 0.5, 2.4), acf * CF(0, 0, 3.1), P.granite, MAT.Granite)
	-- 돌탑 둘
	for _, s in { -1, 1 } do
		local p = (acf * CF(s * 5.6, 0, 0.5)).Position
		stoneStack(f, p.X, p.Z, 5, 2.2)
	end

	-- 선돌 고리: 나무 둘레 반지름 46, 남쪽(자리·길 쪽)은 연다
	local ring = Kit.model(f, "선돌 고리")
	local openA = atan2(dir.Z, dir.X)
	for k = 0, 19 do
		local a = k * TAU / 20
		local da = abs((a - openA + pi) % TAU - pi)
		if da > rad(24) then
			local rr = 46 + R(-1.5, 1.5)
			local x, z = tx + cos(a) * rr, tz + sin(a) * rr
			if not nearPath(x, z, 6) and not inClear(x, z, 2) then
				local hgt = R(3.6, 6.2)
				local g = lowAt(x, z, 1.2)
				local s = block(
					ring,
					"Seondol",
					V3(R(1.8, 2.6), hgt, R(1.2, 1.7)),
					face(V3(x, g + hgt / 2 - 0.9, z), V3(tx, g, tz)) * ANG(rad(R(-6, 6)), 0, rad(R(-6, 6))),
					P.granite:Lerp(P.graniteDark, R(0.2, 0.8)),
					MAT.Slate
				)
				if k % 3 == 0 then
					decoBlock(
						ring,
						"Ikki",
						V3(s.Size.X * 0.8, 0.3, s.Size.Z * 1.05),
						s.CFrame * CF(0, s.Size.Y / 2, 0),
						C.moss,
						MAT.LeafyGrass
					)
				end
			end
		end
	end
	-- 비석: 길에서 들어오는 어귀
	local sp = V3(sx, 0, sz) + dir * 9 + V3(-dir.Z, 0, dir.X) * 12
	Kit.stele(f, V3(sp.X, lowAt(sp.X, sp.Z, 2), sp.Z), "만년목", V3(sx, 0, sz) + dir * 40)
	take(tx, tz, 50)
	take(sx, sz, 12)
	return f
end

-- 태고림 ---------------------------------------------------------------------------------
--
-- 동쪽 큰길(Land.ROADS 4)과 무명사 옛터로 드는 숲길 두 줄기를 따라 큰 고목을 촘촘히 심는다 (길가 첫 줄은 큰 활엽수와
-- 소나무, 둘째 줄은 먼 숲 나무). 숲 속 깊은 곳은 먼 숲 나무만 드문드문. 길가에는 덤불, 이끼 바위, 쓰러진 고목, 버섯.
-- 숲길 어귀에 장승 한 쌍과 길 현판.

local TEMPLE_PATH = {
	{ 770, -95 },
	{ 803, -134 },
	{ 846, -176 },
	{ 896, -203 },
	{ 948, -232 },
	{ 996, -255 },
	{ 1030, -261 },
	{ 1050, -258 },
}
local FOREST_ROAD = { { 600, -123 }, { 800, -90 }, { 1055, 0 } } -- Land.ROADS 4 의 숲 구간

local function forestMask(x: number, z: number): number
	return Land.blob(x, z, Land.FOREST)
end

-- 꺾은선 pts 를 따라 step 마다 양쪽에 place(x, z, side) 를 부른다
local function alongPath(
	pts: { { number } },
	step: number,
	near: number,
	far: number,
	chance: number,
	place: (number, number, number) -> ()
)
	local carry = R(0, step)
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local dx, dz = b[1] - a[1], b[2] - a[2]
		local len = sqrt(dx * dx + dz * dz)
		local ux, uz = dx / len, dz / len
		local t = carry
		while t < len do
			local px, pz = a[1] + ux * t, a[2] + uz * t
			for _, side in { -1, 1 } do
				if R(0, 1) < chance then
					local off = R(near, far)
					place(px - uz * off * side + R(-2, 2), pz + ux * off * side + R(-2, 2), side)
				end
			end
			t += step * R(0.8, 1.2)
		end
		carry = t - len
	end
end

-- 흙길: 납작한 흙 판을 길 따라 겹쳐 깐다 (비탈을 따라 기운다)
local function dirtPath(parent: Instance, pts: { { number } }, every: number, width: number)
	local m = Kit.model(parent, "숲길")
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local dx, dz = b[1] - a[1], b[2] - a[2]
		local len = sqrt(dx * dx + dz * dz)
		local ux, uz = dx / len, dz / len
		local n = math.max(1, floor(len / every + 0.5))
		for k = 0, n - 1 do
			local t0, t1 = len * k / n, len * (k + 1) / n + 0.8
			local x0, z0 = a[1] + ux * t0, a[2] + uz * t0
			local x1, z1 = a[1] + ux * t1, a[2] + uz * t1
			-- 가로 기울기만큼 조금 더 묻는다
			local cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
			local tilt =
				abs(surf(cx - uz * width / 2, cz + ux * width / 2) - surf(cx + uz * width / 2, cz - ux * width / 2))
			local sink = 0.12 + tilt * 0.5
			local pa = V3(x0, surf(x0, z0) - sink, z0)
			local pb = V3(x1, surf(x1, z1) - sink, z1)
			local p = beam(
				m,
				"Heukgil",
				pa,
				pb,
				width * R(0.85, 1.05),
				0.4,
				C.earth:Lerp(rgb(96, 82, 62), R(0, 1)),
				MAT.Ground
			)
			p.CastShadow = false
		end
	end
	return m
end

-- 장승: 나무 몸에 글을 세로로 새기고, 머리에 눈·입, 갓을 씌운다
local function jangseung(parent: Instance, x: number, z: number, toward: Vector3, text: string, female: boolean)
	local m = Kit.model(parent, "장승")
	local g = lowAt(x, z, 0.8)
	local look = face(V3(x, g, z), toward)
	local body = block(m, "Mom", V3(1.5, 6.6, 1.3), look * CF(0, 2.6, 0), rgb(150, 118, 82), MAT.Wood)
	Kit.engrave(body, text, "Front", true, "ink")
	local head = block(m, "Meori", V3(2.1, 2.4, 1.8), look * CF(0, 7.0, 0), rgb(160, 126, 88), MAT.Wood)
	for _, s in { -1, 1 } do
		block(m, "Nun", V3(0.55, 0.4, 0.2), head.CFrame * CF(s * 0.5, 0.35, -0.9), P.meok, MAT.SmoothPlastic)
	end
	block(
		m,
		"Ip",
		V3(1.2, 0.3, 0.2),
		head.CFrame * CF(0, -0.55, -0.9),
		if female then P.juhong else P.meok,
		MAT.SmoothPlastic
	)
	if female then
		block(m, "Gat", V3(2.2, 0.6, 2.0), look * CF(0, 8.5, 0), rgb(70, 60, 50), MAT.Wood)
	else
		cyl(m, "Gat", (look * CF(0, 8.3, 0)).Position, (look * CF(0, 8.55, 0)).Position, 3.4, P.meok, MAT.SmoothPlastic)
		cyl(m, "Gat", (look * CF(0, 8.5, 0)).Position, (look * CF(0, 9.9, 0)).Position, 1.5, P.meok, MAT.SmoothPlastic)
	end
	return m
end

local function forest(root: Instance)
	local f = Kit.folder(root, "태고림")
	table.insert(PATHS, Land.poly(TEMPLE_PATH))
	dirtPath(f, TEMPLE_PATH, 8.5, 3.8)

	-- 숲길 어귀: 장승 한 쌍 + 길 현판
	local p0, p1 = TEMPLE_PATH[1], TEMPLE_PATH[2]
	local ux, uz = p1[1] - p0[1], p1[2] - p0[2]
	local l = sqrt(ux * ux + uz * uz)
	ux, uz = ux / l, uz / l
	local gx, gz = p0[1] + ux * 12, p0[2] + uz * 12
	local toward = V3(p0[1] - ux * 10, 0, p0[2] - uz * 10)
	jangseung(f, gx - uz * 4.2, gz + ux * 4.2, toward, "태고림", false)
	jangseung(f, gx + uz * 4.2, gz - ux * 4.2, toward, "무명사", true)
	take(gx, gz, 7)
	local sgx, sgz = p0[1] + ux * 4 + uz * 6.5, p0[2] + uz * 4 - ux * 6.5
	Kit.signboard(f, V3(sgx, lowAt(sgx, sgz, 2), sgz), "무명사 옛터", V3(p0[1] - 30, 0, p0[2] + 10))
	take(sgx, sgz, 3)

	local trees = Kit.folder(f, "나무")
	local under = Kit.folder(f, "덤불")
	local function inForest(x: number, z: number, t: number): boolean
		return forestMask(x, z) > t
	end
	-- 길가 첫 줄
	local function nearRow(x: number, z: number)
		if not inForest(x, z, 0.3) then
			return
		end
		local roll = R(0, 1)
		if roll < 0.68 then
			local h = R(26, 36)
			if free(x, z, h * 0.11 + 1, { path = 5 }) then
				bigTree(trees, x, z, h, { roots = if R(0, 1) < 0.35 then 2 else 0, branches = if h > 31 then 3 else 2 })
			end
		elseif roll < 0.88 then
			local h = R(22, 30)
			if free(x, z, 3, { path = 5 }) then
				pineTree(trees, x, z, h)
			end
		else
			local h = R(12, 16)
			if free(x, z, 2.5, { path = 4 }) then
				bigTree(trees, x, z, h, { blobs = 5, leaves = LEAVES[3] })
			end
		end
	end
	local function farRow(x: number, z: number)
		if not inForest(x, z, 0.35) then
			return
		end
		local h = R(30, 40)
		if free(x, z, 4.5, { path = 8 }) then
			if R(0, 1) < 0.7 then
				farTree(trees, x, z, h)
			else
				bigTree(trees, x, z, h * 0.85, { blobs = 5 })
			end
		end
	end
	alongPath(TEMPLE_PATH, 30, 10, 17, 0.9, nearRow)
	alongPath(FOREST_ROAD, 30, 11, 18, 0.85, nearRow)
	alongPath(TEMPLE_PATH, 44, 24, 40, 0.75, farRow)
	alongPath(FOREST_ROAD, 46, 25, 42, 0.7, farRow)

	-- 숲 속 깊은 곳: 먼 숲 나무 드문드문
	local deep = 0
	for _ = 1, 500 do
		if deep >= 34 then
			break
		end
		local a, r = R(0, TAU), 560 * sqrt(R(0, 1))
		local x, z = Land.FOREST.x + cos(a) * r, Land.FOREST.z + sin(a) * r
		if inForest(x, z, 0.6) and free(x, z, 22, { path = 30 }) then
			farTree(trees, x, z, R(30, 42))
			deep += 1
		end
	end

	-- 길가 덤불·바위·고목·버섯
	local function undergrowth(x: number, z: number)
		if not inForest(x, z, 0.3) or not free(x, z, 2, { path = 2.5 }) then
			return
		end
		local roll = R(0, 1)
		if roll < 0.66 then
			Build.shrub(
				under,
				V3(x, surf(x, z) - 0.3, z),
				R,
				{ size = R(3, 5), leaves = { P.leafDeep, P.leaf, rgb(76, 120, 66) } }
			)
			take(x, z, 2)
		elseif roll < 0.82 then
			if free(x, z, 4, { path = 3 }) then
				Build.rocks(
					under,
					V3(x, lowAt(x, z, 2) - 0.6, z),
					R(3.5, 6),
					R,
					{ count = 2, color = rgb(116, 116, 106) }
				)
				take(x, z, 4)
			end
		elseif roll < 0.92 then
			if free(x, z, 8, { path = 3 }) then
				fallenLog(under, x, z, R(12, 17))
			end
		else
			mushrooms(under, x, z, R(0, 1) < 0.5)
			take(x, z, 2)
		end
	end
	alongPath(TEMPLE_PATH, 15, 5.5, 9.5, 0.6, undergrowth)
	alongPath(FOREST_ROAD, 18, 6.5, 10, 0.5, undergrowth)
	return f
end

-- 무명사 옛터 -----------------------------------------------------------------------------
--
-- 남북으로 놓인 절터. 남쪽 문터(기둥 밑동)로 들어와 마당 가운데 영맥(mid@temple, 비워 둔다), 그 뒤 기운 삼층 목탑
-- (위층 지붕은 무너져 없다), 맨 뒤 금당 터(장대석 기단과 주춧돌, 무너진 지붕 한 덩이). 동서 요사 터, 쓰러진 석등,
-- 허물어진 돌담, 기단을 덮은 덤불. 숲길이 남서쪽에서 들어온다.

local function ruinBase(
	parent: Instance,
	x: number,
	z: number,
	w: number,
	d: number,
	cols: number,
	rows: number,
	keep: number
)
	local m = Kit.model(parent, "건물 터")
	local cf = siteCf(m, x, z, x, z + 10, w / 2, d / 2, 0.9)
	block(m, "Gidan", V3(w, 1.3, d), cf * CF(0, 0.05, 0), P.granite:Lerp(P.graniteDark, 0.3), MAT.Granite)
	for i = 0, cols - 1 do
		for j = 0, rows - 1 do
			if (i == 0 or i == cols - 1 or j == 0 or j == rows - 1) and R(0, 1) < keep then
				local px = -w / 2 + 2.4 + (w - 4.8) * i / math.max(cols - 1, 1)
				local pz = -d / 2 + 2.4 + (d - 4.8) * j / math.max(rows - 1, 1)
				block(
					m,
					"Juchu",
					V3(1.8, 0.6, 1.8),
					cf * CF(px, 0.95, pz) * ANG(0, R(-0.2, 0.2), 0),
					P.graniteDark,
					MAT.Granite
				)
			end
		end
	end
	return m, cf
end

local function temple(root: Instance)
	local f = Kit.folder(root, "무명사 옛터")
	local vein = Sites.byId["mid@temple"]
	local vx, vz = vein.x, vein.z

	-- 기운 삼층탑 (사층으로 짓고 맨 위층과 상륜을 덜어 낸다: 위층 지붕이 뚫린 채 남는다)
	local px, pz = vx, vz - 24
	local pg = lowAt(px, pz, 8)
	local pcf = face(V3(px, pg - 0.5, pz), V3(px, pg, pz + 10))
	local pagoda = Build.pagoda(f, pcf, { floors = 4, base = 10, name = "기운 탑" })
	for _, c in pagoda:GetChildren() do
		if c.Name == "4층" or c.Name == "Noban" or c.Name == "Boryun" or c.Name == "Chalju" or c.Name == "Boju" then
			c:Destroy()
		end
	end
	-- 삼층 지붕 한쪽 귀가 떨어져 나갔다
	local third = pagoda:FindFirstChild("3층")
	local rubble = {}
	if third then
		for _, d in third:GetDescendants() do
			if d:IsA("BasePart") and (d.Name == "Giwa" or d.Name == "Maru") then
				local lp = pcf:PointToObjectSpace(d.CFrame.Position)
				if lp.X > 1.5 and lp.Z > -1 then
					table.insert(rubble, d.Size)
					d:Destroy()
				end
			end
		end
	end
	moveModel(pagoda, pcf, pcf * ANG(rad(-2.5), 0, rad(-4)))
	-- 떨어진 기와 조각
	for i = 1, math.min(#rubble, 6) do
		local a, r = R(-0.6, 1.2), R(8, 13)
		local x, z = px + cos(a) * r, pz + sin(a) * r
		local s = rubble[i]
		block(
			f,
			"Giwa",
			V3(math.min(s.X, 4), 0.6, math.min(s.Z, 3)),
			CF(x, surf(x, z) + 0.05, z) * ANG(R(-0.4, 0.4), R(0, TAU), R(-0.4, 0.4)),
			P.giwa,
			MAT.ClayRoofTiles
		)
	end
	take(px, pz, 12)

	-- 금당 터 (탑 뒤)
	local hx, hz = vx, vz - 52
	local hall, hcf = ruinBase(f, hx, hz, 26, 15, 5, 3, 0.75)
	-- 남은 기둥 밑동 둘과 쓰러진 기둥 하나
	for _, q in { { -9.2, -5.1, 3.2 }, { 4.6, -5.1, 1.6 } } do
		local b = hcf * CF(q[1], 1.2, q[2])
		cyl(
			hall,
			"Gidung",
			b.Position,
			(b * CF(0, q[3], 0)).Position,
			1.15,
			P.seokganju:Lerp(P.woodDark, 0.4),
			MAT.Wood
		)
	end
	cyl(
		hall,
		"Gidung",
		(hcf * CF(-3, 1.3, 1)).Position,
		(hcf * CF(6.5, 1.3, 4.5)).Position,
		1.15,
		P.seokganju:Lerp(P.woodDark, 0.5),
		MAT.Wood
	)
	-- 무너진 지붕 한 덩이: 기와 판 셋이 서로 기대고, 용마루 토막과 서까래가 삐져나온다
	local rc = hcf * CF(7, 1.2, 1.5)
	block(hall, "Giwa", V3(9, 0.7, 6), rc * CF(0, 1.4, -1.6) * ANG(rad(28), rad(8), 0), P.giwa, MAT.ClayRoofTiles)
	block(hall, "Giwa", V3(8, 0.7, 5.5), rc * CF(0.5, 1.2, 2.2) * ANG(rad(-32), rad(-6), 0), P.giwa, MAT.ClayRoofTiles)
	block(
		hall,
		"Giwa",
		V3(6, 0.7, 4),
		rc * CF(-5, 0.6, 0.5) * ANG(rad(12), rad(30), rad(14)),
		P.giwa:Lerp(P.giwaDark, 0.5),
		MAT.ClayRoofTiles
	)
	beam(
		hall,
		"Maru",
		(rc * CF(-4, 2.6, 0.2)).Position,
		(rc * CF(4, 3.0, 0.4)).Position,
		1.1,
		1.1,
		P.giwaDark,
		MAT.Slate
	)
	for _, s in { -1.5, 1.5 } do
		beam(
			hall,
			"Seokkarae",
			(rc * CF(s, 0.4, -4)).Position,
			(rc * CF(s * 1.4, 3.2, 1)).Position,
			0.45,
			0.45,
			P.woodDark,
			MAT.Wood
		)
	end
	take(hx, hz, 16)

	-- 동서 요사 터
	local wing, wcf = ruinBase(f, vx + 30, vz - 4, 11, 16, 2, 4, 0.7)
	beam(wing, "Bo", (wcf * CF(-2, 1.0, -4)).Position, (wcf * CF(3, 2.2, 5)).Position, 0.8, 0.9, P.woodDark, MAT.Wood)
	take(vx + 30, vz - 4, 10)
	local wing2, wcf2 = ruinBase(f, vx - 30, vz - 4, 11, 16, 2, 4, 0.6)
	cyl(
		wing2,
		"Gidung",
		(wcf2 * CF(-3.1, 1.2, -5.6)).Position,
		(wcf2 * CF(-3.1, 6.0, -5.6)).Position,
		1.1,
		P.woodDark,
		MAT.Wood
	)
	take(vx - 30, vz - 4, 10)

	-- 남쪽 문터: 기둥 밑동 둘, 떨어진 창방
	local gx, gz = vx, vz + 38
	for _, s in { -1, 1 } do
		local x = gx + s * 6
		local g = lowAt(x, gz, 1.4)
		block(f, "Choseok", V3(2.4, 1.0, 2.4), CF(x, g + 0.1, gz), P.granite, MAT.Granite)
		cyl(
			f,
			"Gidung",
			V3(x, g + 0.5, gz),
			V3(x, g + (if s < 0 then 4.5 else 2.4), gz),
			1.5,
			P.seokganju:Lerp(P.woodDark, 0.35),
			MAT.Wood
		)
	end
	beam(
		f,
		"Changbang",
		V3(gx - 1, lowAt(gx - 1, gz + 3, 1) + 0.4, gz + 3),
		V3(gx + 8, lowAt(gx + 8, gz + 1, 1) + 0.5, gz + 1),
		0.9,
		1.0,
		P.noerok:Lerp(P.woodDark, 0.5),
		MAT.Wood
	)
	take(gx, gz, 8)
	-- 비석 (문터 곁, 조금 기울었다)
	local sg = lowAt(gx - 11, gz - 2, 2)
	local stele = Kit.stele(f, V3(gx - 11, sg, gz - 2), "무명사", V3(gx - 40, 0, gz + 20))
	local sbase = CF(gx - 11, sg, gz - 2)
	moveModel(stele, sbase, sbase * ANG(rad(5), 0, rad(-4)))
	take(gx - 11, gz - 2, 3)

	-- 석등: 탑 앞에 하나 서 있고, 하나는 쓰러졌고, 하나는 몸돌만 남았다
	Build.stoneLantern(f, V3(vx, surf(vx, vz - 12), vz - 12))
	local lx, lz = vx + 9, vz - 13
	local fallen = Build.stoneLantern(f, V3(lx, surf(lx, lz), lz))
	local lb = CF(lx, surf(lx, lz), lz)
	moveModel(fallen, lb, lb * CF(0, 1.0, 0) * ANG(0, rad(30), rad(84)) * CF(0, -0.2, 0))
	local bx, bz = vx - 9, vz - 13
	local bg = surf(bx, bz)
	block(f, "Hadae", V3(2.6, 0.9, 2.6), CF(bx, bg + 0.3, bz) * ANG(0, rad(45), 0), P.granite, MAT.Granite)
	cyl(f, "Ganju", V3(bx, bg + 0.7, bz), V3(bx, bg + 2.6, bz), 0.9, P.granite, MAT.Granite)
	block(
		f,
		"Okgae",
		V3(2.4, 0.9, 2.4),
		CF(bx + 2.2, bg + 0.3, bz + 1.4) * ANG(rad(16), rad(20), rad(-10)),
		P.graniteDark,
		MAT.Granite
	)
	take(vx, vz - 12.5, 11)

	-- 허물어진 돌담 (서쪽과 북동쪽에 토막)
	for _, seg in { { -40, -30, -40, -12 }, { -40, 4, -38, 16 }, { 26, -46, 40, -40 } } do
		local ax, az, bx2, bz2 = vx + seg[1], vz + seg[2], vx + seg[3], vz + seg[4]
		local ya = lowAt(ax, az, 1) - 0.4
		local yb = lowAt(bx2, bz2, 1) - 0.4
		local wall = Build.stoneWall(f, V3(ax, min(ya, yb), az), V3(bx2, min(ya, yb), bz2), { height = R(2.2, 3.2) })
		for _, p in wall:GetChildren() do
			if p.Name == "Gat" and R(0, 1) < 0.5 then
				p:Destroy() -- 기와 갓 한쪽이 떨어졌다
			end
		end
	end

	-- 덤불이 기단을 덮는다
	local plants = Kit.folder(f, "덤불")
	for _ = 1, 16 do
		local a, r = R(0, TAU), R(10, 44)
		local x, z = vx + cos(a) * r, vz + sin(a) * r
		if not inClear(x, z, 1.5) and not nearPath(x, z, 2) then
			Build.shrub(
				plants,
				V3(x, surf(x, z) - 0.2, z),
				R,
				{ size = R(2.5, 4.5), leaves = { P.leafDeep, P.leaf, P.leafYellow } }
			)
		end
	end
	-- 금당 터에서 자란 어린 나무
	bigTree(plants, hx - 2, hz + 3, 13, { blobs = 5, leaves = LEAVES[3] })
	mushrooms(plants, px + 9, pz - 7, true)
	-- 둘레 고목 (빈터를 둘러싼다)
	for k = 0, 5 do
		local a = rad(k * 60 + 15 + R(-12, 12))
		local x, z = vx + cos(a) * R(54, 64), vz + sin(a) * R(54, 64)
		if free(x, z, 4, { path = 5 }) then
			bigTree(f, x, z, R(30, 38), { roots = 2, branches = 3 })
		end
	end
	take(vx, vz, 42)
	return f
end

-- 조양대 ---------------------------------------------------------------------------------
--
-- 언덕 꼭대기 가운데는 성대(가운데 담당), 서쪽에 전송진. 동쪽 가장자리에 해 뜨는 바다를 보는 정자.
-- 언덕길(Land.HILL_TRAIL) 들머리에 홍살문, 길 바깥 가장자리에 돌등, 꼭대기 어귀에 돌계단과 석등 한 쌍. 솔숲.

-- 나선 길을 every 스터드마다 (모든 점도 함께 돌려준다)
local function trailSamples(sp, every: number): ({ { number } }, { { number } })
	local pts = Land.spiralPoints(sp, 1)
	local out = {}
	local acc = 0
	for i = 2, #pts do
		local a, b = pts[i - 1], pts[i]
		acc += sqrt((b[1] - a[1]) ^ 2 + (b[3] - a[3]) ^ 2)
		if acc >= every then
			acc = 0
			table.insert(out, b)
		end
	end
	return out, pts
end

local function eastHill(root: Instance)
	local f = Kit.folder(root, "조양대")
	local hill = Land.EAST_HILL
	local cx, cz = hill.x, hill.z
	local sp = Land.HILL_TRAIL

	-- 홍살문: 길 들머리, 길을 가로질러 선다
	local _, all = trailSamples(sp, 1000)
	local s0 = all[6]
	local s1 = all[9]
	local tx, tz = s1[1] - s0[1], s1[3] - s0[3]
	local tl = sqrt(tx * tx + tz * tz)
	tx, tz = tx / tl, tz / tl
	do
		local m = Kit.model(f, "홍살문")
		local gx, gz = s0[1], s0[3]
		local top = -math.huge
		local feet = {}
		for _, s in { -1, 1 } do
			local x, z = gx - tz * s * 5.5, gz + tx * s * 5.5
			local g = lowAt(x, z, 0.8)
			table.insert(feet, V3(x, g, z))
			top = max(top, surf(x, z))
		end
		for _, p in feet do
			cyl(m, "Gidung", p - V3(0, 0.8, 0), V3(p.X, top + 10.5, p.Z), 0.9, P.juhong, MAT.Wood)
			block(m, "Choseok", V3(1.6, 1.0, 1.6), CF(p), P.granite, MAT.Granite)
		end
		local a, b = V3(feet[1].X, top + 8.8, feet[1].Z), V3(feet[2].X, top + 8.8, feet[2].Z)
		beam(m, "Garodae", a + (a - b).Unit * 0.6, b + (b - a).Unit * 0.6, 0.6, 0.6, P.juhong, MAT.Wood)
		beam(m, "Garodae", a + V3(0, 1.5, 0), b + V3(0, 1.5, 0), 0.5, 0.5, P.juhong, MAT.Wood)
		-- 살 (붉은 화살대 줄): 가로대 사이 한 판
		local mid = (a + b) / 2 + V3(0, 0.75, 0)
		block(m, "Sal", V3((b - a).Magnitude - 0.8, 1.2, 0.12), face(mid, mid + V3(tx, 0, tz)), P.juhong, MAT.Wood)
		local tg = cyl(
			m,
			"Taegeuk",
			mid + V3(0, 1.6, 0) - V3(tx, 0, tz) * 0.15,
			mid + V3(0, 1.6, 0) + V3(tx, 0, tz) * 0.15,
			1.6,
			P.gunjeong,
			MAT.SmoothPlastic
		)
		tg.CastShadow = false
		take(gx, gz, 7)
	end

	-- 돌등: 길 바깥 가장자리 (언덕 바깥 쪽)
	local samples = trailSamples(sp, 34)
	for i, s in samples do
		if i < #samples then
			local dx, dz = s[1] - cx, s[3] - cz
			local d = sqrt(dx * dx + dz * dz)
			local x, z = s[1] + dx / d * 6.5, s[3] + dz / d * 6.5
			if not inClear(x, z, 1.5) then
				smallLantern(f, V3(x, lowAt(x, z, 1), z))
				take(x, z, 1.5)
			end
		end
	end

	-- 꼭대기 어귀: 길 끝에서 마루로 오르는 돌계단과 석등 한 쌍
	local last = all[#all]
	local ex, ez = last[1], last[3]
	local ix, iz = cx - ex, cz - ez
	local il = sqrt(ix * ix + iz * iz)
	ix, iz = ix / il, iz / il
	local y1 = surf(ex + ix * 7, ez + iz * 7)
	for k = 0, 3 do
		local x, z = ex + ix * (k * 1.8 + 1), ez + iz * (k * 1.8 + 1)
		local g = surf(x, z)
		local topY = min(y1, max(g, last[2] + (k + 1) * (y1 - last[2]) / 4))
		local depth = topY - (lowAt(x, z, 3) - 1)
		block(
			f,
			"Dolgyedan",
			V3(7.5, depth, 1.9),
			face(V3(x, topY - depth / 2, z), V3(x + ix, topY - depth / 2, z + iz)),
			P.granite,
			MAT.Granite
		)
	end
	for _, s in { -1, 1 } do
		local x, z = ex + ix * 8 - iz * s * 5.5, ez + iz * 8 + ix * s * 5.5
		if not inClear(x, z, 1.5) then
			Build.stoneLantern(f, V3(x, lowAt(x, z, 1.3), z))
			take(x, z, 2)
		end
	end
	take(ex + ix * 4, ez + iz * 4, 5)

	-- 해맞이 정자: 꼭대기 동쪽 가장자리, 앞(계단)은 성대 쪽, 뒤로 해 뜨는 바다
	local star = Sites.byId.star_east
	local qx, qz = star.x + 23, star.z - 6
	local cf = siteCf(f, qx, qz, star.x, star.z, 7.5, 9, 1.0)
	local pav = Build.pavilion(f, cf, { detail = 0, bands = 3, bay = 10, name = "해맞이 정자" })
	local board = block(pav, "Hyeonpan", V3(4.6, 1.5, 0.25), cf * CF(0, 2.4 + 8 - 0.7, -5 - 0.75), P.meok, MAT.Wood)
	block(pav, "Te", V3(5.1, 1.95, 0.2), cf * CF(0, 2.4 + 8 - 0.7, -5 - 0.62), P.hwang, MAT.Wood)
	Kit.engrave(board, "조양대", "Front")
	take(qx, qz, 10)

	-- 솔숲: 꼭대기 가장자리와 비탈
	local pines = 0
	for _ = 1, 200 do
		if pines >= 9 then
			break
		end
		local a, r = R(0, TAU), R(30, 120)
		local x, z = cx + cos(a) * r, cz + sin(a) * r
		if free(x, z, 3.5, { path = 6 }) then
			if r < 40 then
				-- 꼭대기 가장자리: 동쪽(바다 쪽) 시야는 비운다
				if cos(a) < 0.3 then
					pineTree(f, x, z, R(16, 22))
					pines += 1
				end
			else
				pineTree(f, x, z, R(18, 26))
				pines += 1
			end
		end
	end
	for _ = 1, 10 do
		local a, r = R(0, TAU), R(34, 110)
		local x, z = cx + cos(a) * r, cz + sin(a) * r
		if free(x, z, 2, { path = 3 }) then
			Build.shrub(f, V3(x, surf(x, z) - 0.3, z), R, { size = R(2.5, 4) })
			take(x, z, 2)
		end
	end
	for _ = 1, 4 do
		local a, r = R(0, TAU), R(40, 120)
		local x, z = cx + cos(a) * r, cz + sin(a) * r
		if free(x, z, 4, { path = 4 }) then
			Build.rocks(f, V3(x, lowAt(x, z, 2) - 0.5, z), R(4, 7), R, { count = 2 })
			take(x, z, 4)
		end
	end
	return f
end

-- 청음죽림·청음암 --------------------------------------------------------------------------
--
-- 청음암: 영맥(mid@hermit)을 마당 가운데 두고 북쪽에 법당, 동쪽에 종각, 서쪽에 작은 못과 돌 정원.
-- 남서쪽으로 길(Land.ROADS 7)이 들어오는 어귀에 사립문과 현판. 둘레는 대숲 (길가와 암자 둘레가 빽빽하다).

-- 가벼운 대숲 덤불: 대 n 그루와 위쪽 잎 덩이 둘
local function bambooClump(parent: Instance, x: number, z: number, n: number, radius: number)
	local m = Kit.model(parent, "대숲")
	local g = lowAt(x, z, radius)
	local tops = {}
	for _ = 1, n do
		local a, r = R(0, TAU), radius * sqrt(R(0, 1))
		local fx, fz = x + cos(a) * r, z + sin(a) * r
		local foot = V3(fx, min(g, surf(fx, fz)) - 0.5, fz)
		local h = R(16, 25)
		local tilt = V3(R(-0.07, 0.07), 1, R(-0.07, 0.07)).Unit
		local tip = foot + tilt * h
		cyl(m, "Dae", foot, tip, R(0.38, 0.55), if R(0, 1) > 0.75 then P.bambooOld else P.bamboo, MAT.SmoothPlastic)
		table.insert(tops, tip)
	end
	local c = V3(0, 0, 0)
	for _, t in tops do
		c += t
	end
	c /= #tops
	for i = 1, 2 do
		local s = radius * 2 + R(3, 5)
		local p = c + V3(R(-1.5, 1.5), -2.5 - (i - 1) * 3.5, R(-1.5, 1.5))
		decoBlock(
			m,
			"Ip",
			V3(s, R(2.2, 3.2), s * R(0.75, 1)),
			CF(p) * ANG(R(-0.3, 0.3), R(0, pi), R(-0.3, 0.3)),
			if i == 1 then P.bambooLeaf else P.bambooLeaf:Lerp(P.leafLight, 0.3),
			MAT.LeafyGrass
		)
	end
	take(x, z, radius + 1)
	return m
end

local function hermitage(root: Instance)
	local f = Kit.folder(root, "청음암")
	local vein = Sites.byId["mid@hermit"]
	local vx, vz = vein.x, vein.z

	-- 법당 (북쪽, 마당을 본다)
	local hx, hz = vx, vz - 22
	local hcf = siteCf(f, hx, hz, vx, vz, 9.8, 9.5, 1.0)
	local hall = Build.house(
		f,
		hcf,
		{ bays = { 3, 2 }, bay = 5, style = "temple", detail = 0, bands = 3, pillarH = 8, name = "청음암 법당" }
	)
	local board = block(hall, "Hyeonpan", V3(4.2, 1.4, 0.25), hcf * CF(0, 1.6 + 8 - 0.5, -5 - 0.75), P.meok, MAT.Wood)
	block(hall, "Te", V3(4.7, 1.85, 0.2), hcf * CF(0, 1.6 + 8 - 0.5, -5 - 0.62), P.hwang, MAT.Wood)
	Kit.engrave(board, "청음암", "Front")
	take(hx, hz, 12)

	-- 종각 (동쪽): 범종과 당목
	local bx, bz = vx + 25, vz + 6
	local bcf = siteCf(f, bx, bz, vx, vz, 6.5, 6.5, 1.0)
	local belfry = Build.pavilion(f, bcf, { detail = 0, bands = 2, bay = 7, pillarH = 8.5, name = "종각" })
	local hang = bcf * CF(0, 2.4 + 8.5 - 1.1, 0)
	local bellTop = hang.Position - V3(0, 0.6, 0)
	cyl(belfry, "Gori", hang.Position + V3(0, 0.4, 0), bellTop, 0.35, C.bronze, MAT.Metal)
	ball(belfry, "Yongnyu", bellTop - V3(0, 0.3, 0), 1.6, C.bronze, MAT.Metal)
	cyl(belfry, "Beomjong", bellTop - V3(0, 0.5, 0), bellTop - V3(0, 4.4, 0), 3.0, C.bronze, MAT.Metal)
	cyl(belfry, "Ip", bellTop - V3(0, 4.2, 0), bellTop - V3(0, 4.6, 0), 3.3, C.bronze:Lerp(P.meok, 0.3), MAT.Metal)
	local log0 = (bcf * CF(-2.2, 2.4 + 5.6, 0.9)).Position
	local log1 = (bcf * CF(-2.2, 2.4 + 5.6, -2.9)).Position
	cyl(belfry, "Dangmok", log0, log1, 0.75, P.wood, MAT.Wood)
	for _, p in { log0:Lerp(log1, 0.2), log0:Lerp(log1, 0.8) } do
		deco(beam(belfry, "Jul", p, p + V3(0, 2.0, 0), 0.08, 0.08, C.straw, MAT.Fabric))
	end
	take(bx, bz, 8)

	-- 돌 정원과 작은 못 (서쪽)
	local gx, gz = vx - 23, vz - 2
	local gy = lowAt(gx, gz, 6)
	local pond = Kit.disc(f, "Mot", V3(gx, gy + 0.05, gz), 4.6, 0.3, rgb(54, 96, 104), MAT.Glass)
	pond.Transparency = 0.15
	Kit.disc(f, "Motgajang", V3(gx, gy - 0.12, gz), 5.4, 0.3, P.granite, MAT.Pebble)
	for k = 0, 3 do
		local a = rad(k * 70 + 30)
		local x, z = gx + cos(a) * 6.8, gz + sin(a) * 6.8
		Build.rocks(f, V3(x, surf(x, z) - 0.6, z), R(1.8, 3.2), R, { count = 1, moss = k % 2 == 0 })
	end
	smallLantern(f, V3(gx + 2, surf(gx + 2, gz - 8), gz - 8))
	Build.broadleaf(f, V3(gx - 5, lowAt(gx - 5, gz - 9, 1) - 0.1, gz - 9), R, {
		height = 11,
		blobs = 6,
		name = "단풍나무",
		leaves = { rgb(160, 54, 40), P.maple, rgb(220, 120, 60) },
		bark = rgb(84, 62, 52),
	})
	for k = 1, 4 do
		local x, z = gx + 6 + k * 2.6, gz + 3 - k * 0.6
		block(
			f,
			"Didimdol",
			V3(1.8, 0.4, 1.5),
			CF(x, surf(x, z) - 0.05, z) * ANG(0, R(0, 1), 0),
			P.granite,
			MAT.Granite
		)
	end
	take(gx, gz, 11)

	-- 사립문과 현판: 길이 마당으로 드는 어귀
	local road = Land.ROADS[7]
	local ax, az = road[#road - 1][1], road[#road - 1][2]
	local dx, dz = vx - ax, vz - az
	local dl = sqrt(dx * dx + dz * dz)
	dx, dz = dx / dl, dz / dl
	local ex, ez = vx - dx * 30, vz - dz * 30
	do
		local m = Kit.model(f, "사립문")
		local top = -math.huge
		local feet = {}
		for _, s in { -1, 1 } do
			local x, z = ex - dz * s * 4, ez + dx * s * 4
			local g = lowAt(x, z, 0.6)
			table.insert(feet, V3(x, g, z))
			top = max(top, surf(x, z))
		end
		for _, p in feet do
			cyl(m, "Gidung", p - V3(0, 0.8, 0), V3(p.X, top + 7.2, p.Z), 0.7, P.wood, MAT.Wood)
		end
		local across = V3(-dz, 0, dx)
		beam(
			m,
			"Inbang",
			V3(feet[1].X, top + 6.8, feet[1].Z) - across * 0.8,
			V3(feet[2].X, top + 6.8, feet[2].Z) + across * 0.8,
			0.6,
			0.7,
			P.wood,
			MAT.Wood
		)
		-- 맞배 이엉 지붕 (작은 갓): 쐐기 둘, 높은 쪽이 가운데
		local mid = V3(ex, top + 7.55, ez)
		for _, s in { -1, 1 } do
			local along = V3(dx, 0, dz) * s
			local c = mid + along * 0.8
			wedge(m, "Ieong", V3(10, 0.9, 1.6), face(c, c + along), C.straw:Lerp(P.woodDark, 0.25), MAT.Grass)
		end
		take(ex, ez, 5)
	end
	local sx, sz = ex - dz * 7.5 - dx * 2, ez + dx * 7.5 - dz * 2
	Kit.signboard(f, V3(sx, lowAt(sx, sz, 2), sz), "청음암", V3(ax, 0, az))
	take(sx, sz, 3)
	-- 암자 마당 가: 덤불 몇
	for _ = 1, 6 do
		local a, r = R(0, TAU), R(12, 30)
		local x, z = vx + cos(a) * r, vz + sin(a) * r
		if free(x, z, 2, { path = 2 }) then
			Build.shrub(
				f,
				V3(x, surf(x, z) - 0.25, z),
				R,
				{ size = R(2, 3.2), flowers = if R(0, 1) < 0.5 then FLOWERS[3] else nil }
			)
			take(x, z, 2)
		end
	end
	take(vx, vz, 14)
	return f
end

local function bambooGrove(root: Instance)
	local f = Kit.folder(root, "청음죽림")
	local B = Land.BAMBOO
	local function mask(x: number, z: number): number
		return Land.blob(x, z, B)
	end
	-- 길가 대숲 (청음암으로 드는 길 양쪽)
	local road = Land.ROADS[7]
	alongPath({ road[2], road[3] }, 12, 6.5, 11, 0.95, function(x, z)
		if mask(x, z) > 0.3 and free(x, z, 4, { path = 3 }) then
			bambooClump(f, x, z, 7, 3.2)
		end
	end)
	-- 홍로성 쪽 들머리는 덜
	alongPath({ road[1], road[2] }, 18, 7, 12, 0.8, function(x, z)
		if mask(x, z) > 0.4 and free(x, z, 4, { path = 3 }) then
			bambooClump(f, x, z, 6, 3)
		end
	end)
	-- 손으로 지은 대숲 (Build.bamboo, 마디와 잎): 암자 어귀
	local vein = Sites.byId["mid@hermit"]
	for _, o in { { -36, -16 }, { -14, -40 }, { 40, -26 } } do
		local x, z = vein.x + o[1], vein.z + o[2]
		if free(x, z, 4, { path = 3 }) then
			Build.bamboo(f, V3(x, lowAt(x, z, 3), z), R, { count = 7, radius = 3.5 })
			take(x, z, 4.5)
		end
	end
	-- 암자 둘레 고리 (마당 뒤쪽이 빽빽하다)
	local placed = 0
	for k = 0, 40 do
		if placed >= 14 then
			break
		end
		local a = k * 2.39996
		local r = 44 + (k % 5) * 9 + R(-3, 3)
		local x, z = vein.x + cos(a) * r, vein.z + sin(a) * r
		if mask(x, z) > 0.35 and free(x, z, 4, { path = 4 }) then
			bambooClump(f, x, z, 7, 3.4)
			placed += 1
		end
	end
	-- 대숲 먼 곳 (드문드문)
	local far = 0
	for _ = 1, 300 do
		if far >= 8 then
			break
		end
		local a, r = R(0, TAU), 200 * sqrt(R(0, 1))
		local x, z = B.x + cos(a) * r, B.z + sin(a) * r
		if mask(x, z) > 0.55 and free(x, z, 30, { path = 12 }) then
			bambooClump(f, x, z, 6, 4)
			far += 1
		end
	end
	return f
end

-- 백초원·마령채·팔방석진 -------------------------------------------------------------------

-- 둥근 펠트 천막: 둥근 벽(원기둥) + 쐐기 여덟 장 고깔 지붕 + 지붕창 테 + 붉은 문
local function tent(parent: Instance, x: number, z: number, r: number, toward: Vector3, band: Color3, roof: Color3?)
	local m = Kit.model(parent, "천막")
	local g = lowAt(x, z, r)
	local base = V3(x, g, z)
	local hw = r * 0.6
	local hr = r * 0.5
	cyl(m, "Byeok", base - V3(0, 0.6, 0), base + V3(0, hw, 0), 2 * r, C.felt, MAT.Fabric)
	cyl(m, "Ddi", base + V3(0, hw * 0.6, 0), base + V3(0, hw * 0.6 + 0.55, 0), 2 * r + 0.14, band, MAT.Fabric)
	local n = 8
	local L = r + 0.6
	for k = 0, n - 1 do
		local a = k * TAU / n
		local out = V3(cos(a), 0, sin(a))
		local c = base + out * ((r + 0.4 - 0.2) / 2) + V3(0, hw - 0.12 + hr / 2, 0)
		wedge(m, "Jibung", V3(0.8 * (r + 0.4), hr, L), face(c, c + out), roof or C.feltRoof, MAT.Fabric)
	end
	local apex = base + V3(0, hw + hr - 0.1, 0)
	cyl(m, "Toono", apex - V3(0, 0.3, 0), apex + V3(0, 0.45, 0), r * 0.36, P.woodDark, MAT.Wood)
	local dir = (V3(toward.X, 0, toward.Z) - V3(x, 0, z)).Unit
	local door = base + dir * (r - 0.05) + V3(0, 1.75, 0)
	block(m, "Mun", V3(2.3, 3.5, 0.5), face(door, door + dir), C.doorRed, MAT.Wood)
	take(x, z, r + 1.5)
	return m
end

local function camp(root: Instance)
	local f = Kit.folder(root, "마령채")
	local vein = Sites.byId["low@camp"]
	local wp = Sites.byId.wp_camp
	-- 목책 고리: 영맥과 전송진이 둘 다 넉넉히 들어오게 두 자리 가운데쯤에 둔다
	local ox, oz = (vein.x + wp.x) / 2 + 2, (vein.z + wp.z) / 2 + 2
	local ringR = 47
	local roadPoly = ROADS[3]
	-- 길이 고리를 지나는 곳 (문)
	local gates = {}
	do
		local dists = {}
		for k = 0, 359 do
			local a = rad(k)
			dists[k] = Land.polyDist(ox + cos(a) * ringR, oz + sin(a) * ringR, roadPoly, 80)
		end
		for k = 0, 359 do
			local d = dists[k]
			if d < 6 and d <= dists[(k + 359) % 360] and d <= dists[(k + 1) % 360] then
				table.insert(gates, rad(k))
			end
		end
	end
	local gap = rad(7.5)
	local function nearGate(a: number): boolean
		for _, g in gates do
			if abs((a - g + pi) % TAU - pi) < gap then
				return true
			end
		end
		return false
	end
	-- 울타리: 문 사이를 이어 둘레를 돈다
	local fence = Kit.folder(f, "목책")
	local run = {}
	local function flush()
		if #run >= 2 then
			Build.fence(fence, run, { color = rgb(130, 100, 70) })
		end
		run = {}
	end
	local startA = (gates[1] or 0) + gap
	for k = 0, 72 do
		local a = startA + rad(k * 5)
		if nearGate(a) then
			flush()
		else
			local x, z = ox + cos(a) * ringR, oz + sin(a) * ringR
			table.insert(run, V3(x, surf(x, z) - 0.1, z))
		end
	end
	flush()
	-- 문: 통나무 기둥 둘, 가로 들보에 현판, 바깥 양쪽 깃발
	for i, ga in gates do
		local m = Kit.model(f, "채문")
		local cxg, czg = ox + cos(ga) * ringR, oz + sin(ga) * ringR
		local tgx, tgz = -sin(ga), cos(ga)
		local out = V3(cos(ga), 0, sin(ga))
		local top = -math.huge
		local feet = {}
		for _, s in { -1, 1 } do
			local x, z = cxg + tgx * s * 6, czg + tgz * s * 6
			table.insert(feet, V3(x, lowAt(x, z, 0.8), z))
			top = max(top, surf(x, z))
		end
		for _, p in feet do
			cyl(m, "Gidung", p - V3(0, 1, 0), V3(p.X, top + 9.5, p.Z), 1.3, rgb(112, 84, 60), MAT.Wood)
			ball(m, "Kkokji", V3(p.X, top + 9.8, p.Z), 1.1, rgb(112, 84, 60), MAT.Wood)
		end
		local a, b = V3(feet[1].X, top + 8.3, feet[1].Z), V3(feet[2].X, top + 8.3, feet[2].Z)
		cyl(m, "Deulbo", a + (a - b).Unit * 0.8, b + (b - a).Unit * 0.8, 1.0, rgb(112, 84, 60), MAT.Wood)
		if i == 1 then
			local mid = (a + b) / 2 - V3(0, 1.5, 0)
			local board = block(m, "Hyeonpan", V3(5.4, 1.6, 0.3), face(mid, mid + out), P.woodDark, MAT.Wood)
			Kit.engrave(board, "마령채", "Front,Back")
			for _, p in { a:Lerp(b, 0.3), a:Lerp(b, 0.7) } do
				deco(beam(m, "Jul", p, p - V3(0, 0.75, 0), 0.08, 0.08, C.straw, MAT.Fabric))
			end
		end
		for j, p in feet do
			local bp = p + out * 2.2 + V3(tgx, 0, tgz) * (if j == 1 then -1.5 else 1.5)
			Build.banner(m, V3(bp.X, lowAt(bp.X, bp.Z, 0.5), bp.Z), bp + out * 5, OBANG[1 + (i + j) % 5], 11)
		end
		take(cxg, czg, 8)
	end

	-- 천막: 모닥불을 둘러 남쪽에 넷, 길 북쪽에 우두머리 천막과 하나
	local fireX, fireZ = ox + 4, oz + 15
	for _ = 1, 12 do
		if free(fireX, fireZ, 6, { path = 7 }) then
			break
		end
		fireZ += 2
	end
	local function tryTent(a: number, r: number, size: number, band: Color3, roof: Color3?)
		for t = 0, 8 do
			local aa = a + rad(t * 9 * (if t % 2 == 0 then 1 else -1))
			local x, z = fireX + cos(aa) * r, fireZ + sin(aa) * r
			if free(x, z, size + 2, { path = 4 }) and (x - ox) ^ 2 + (z - oz) ^ 2 < (ringR - size - 4) ^ 2 then
				tent(f, x, z, size, V3(fireX, 0, fireZ), band, roof)
				return true
			end
		end
		return false
	end
	take(fireX, fireZ, 6)
	tryTent(rad(10), 19, 5.8, OBANG[1])
	tryTent(rad(60), 20, 6.2, OBANG[2])
	tryTent(rad(115), 19, 5.6, OBANG[3], rgb(196, 182, 156))
	tryTent(rad(170), 20, 6.0, OBANG[1])
	-- 길 북쪽 (영맥 둘레는 비운다)
	for _, q in { { 18, -18, 7.5, OBANG[2] }, { -24, -2, 5.6, OBANG[3] } } do
		local x, z = ox + q[1], oz + q[2]
		for t = 0, 10 do
			local xx, zz = x + (t % 3 - 1) * 4, z - (t // 3) * 4
			if free(xx, zz, q[3] + 2, { path = 4 }) and (xx - ox) ^ 2 + (zz - oz) ^ 2 < (ringR - q[3] - 4) ^ 2 then
				tent(f, xx, zz, q[3], V3(ox, 0, oz), q[4], if q[3] > 7 then rgb(170, 140, 104) else nil)
				break
			end
		end
	end

	-- 모닥불: 돌 테, 장작, 불, 솥을 건 삼발이
	do
		local m = Kit.model(f, "모닥불")
		local g = lowAt(fireX, fireZ, 2.5)
		for k = 0, 6 do
			local a = k * TAU / 7
			block(
				m,
				"Dol",
				V3(1.2, 0.8, 1.0),
				CF(fireX + cos(a) * 2.2, g + 0.15, fireZ + sin(a) * 2.2) * ANG(R(-0.2, 0.2), a, R(-0.2, 0.2)),
				P.graniteDark,
				MAT.Slate
			)
		end
		for k = 0, 1 do
			local a = k * pi / 2 + 0.4
			cyl(
				m,
				"Jangjak",
				V3(fireX - cos(a) * 1.6, g + 0.3, fireZ - sin(a) * 1.6),
				V3(fireX + cos(a) * 1.6, g + 0.3, fireZ + sin(a) * 1.6),
				0.5,
				P.woodDark,
				MAT.Wood
			)
		end
		local fire = block(m, "Bul", V3(1.2, 0.6, 1.2), CF(fireX, g + 0.5, fireZ), rgb(255, 150, 70), MAT.Neon)
		fire.CanCollide = false
		local flame = Instance.new("Fire")
		flame.Size = 4
		flame.Heat = 7
		flame.Color = rgb(255, 140, 60)
		flame.SecondaryColor = rgb(255, 210, 120)
		flame.Parent = fire
		Kit.light(fire, rgb(255, 160, 90), 22, 2)
		local apex = V3(fireX, g + 5.2, fireZ)
		for k = 0, 2 do
			local a = k * TAU / 3 + 0.3
			beam(
				m,
				"Sambal",
				V3(fireX + cos(a) * 2.6, g - 0.3, fireZ + sin(a) * 2.6),
				apex,
				0.3,
				0.3,
				P.woodDark,
				MAT.Wood
			)
		end
		deco(beam(m, "Jul", apex, apex - V3(0, 2.1, 0), 0.1, 0.1, P.meok, MAT.Metal))
		ball(m, "Sot", apex - V3(0, 2.6, 0), 1.6, P.meok, MAT.Metal)
	end

	-- 말 매는 가로대 둘, 구유, 건초 더미: 서쪽 문 안쪽
	local wa = gates[1] or rad(170)
	for _, ga in gates do
		if cos(ga) < cos(wa) then
			wa = ga
		end
	end
	local function inside(a: number, r: number): (number, number)
		return ox + cos(a) * r, oz + sin(a) * r
	end
	for k, da in { rad(-24), rad(24) } do
		local x, z = inside(wa + da, ringR - 10)
		if free(x, z, 4, { path = 3 }) then
			local m = Kit.model(f, "말뚝")
			local tg = V3(-sin(wa + da), 0, cos(wa + da))
			local inw = -V3(cos(wa + da), 0, sin(wa + da))
			local pa, pb = V3(x, 0, z) - tg * 3.5, V3(x, 0, z) + tg * 3.5
			pa = V3(pa.X, lowAt(pa.X, pa.Z, 0.5), pa.Z)
			pb = V3(pb.X, lowAt(pb.X, pb.Z, 0.5), pb.Z)
			cyl(m, "Malttuk", pa - V3(0, 0.8, 0), pa + V3(0, 3.6, 0), 0.6, P.wood, MAT.Wood)
			cyl(m, "Malttuk", pb - V3(0, 0.8, 0), pb + V3(0, 3.6, 0), 0.6, P.wood, MAT.Wood)
			cyl(m, "Garodae", pa + V3(0, 3.0, 0), pb + V3(0, 3.0, 0), 0.4, P.wood, MAT.Wood)
			local q = V3(x, 0, z) + inw * 2.6
			local qg = lowAt(q.X, q.Z, 1.5)
			if k == 1 then
				block(
					m,
					"Guyu",
					V3(5, 1.1, 1.4),
					face(V3(q.X, qg + 0.3, q.Z), V3(q.X, qg + 0.3, q.Z) + inw),
					P.woodDark,
					MAT.WoodPlanks
				)
			else
				cyl(
					m,
					"Geoncho",
					V3(q.X, qg + 1.0, q.Z) - tg * 1.4,
					V3(q.X, qg + 1.0, q.Z) + tg * 1.4,
					2.6,
					rgb(206, 184, 112),
					MAT.Grass
				)
			end
			take(x, z, 4.5)
		end
	end
	-- 수레 둘과 장독: 동쪽 문 안쪽
	local ea = gates[2] or rad(330)
	for _, ga in gates do
		if cos(ga) > cos(ea) then
			ea = ga
		end
	end
	for k, da in { rad(-22), rad(20) } do
		local x, z = inside(ea + da, ringR - 11)
		if free(x, z, 5, { path = 3 }) then
			Build.cart(f, CF(x, lowAt(x, z, 2.5), z) * ANG(0, R(0, TAU), 0))
			take(x, z, 5)
		end
		if k == 2 then
			local jx, jz = inside(ea + da + rad(14), ringR - 9)
			if free(jx, jz, 4, { path = 3 }) then
				Build.jars(f, CF(jx, lowAt(jx, jz, 2.5) - 0.1, jz) * ANG(0, R(0, TAU), 0), R, 4)
				take(jx, jz, 4)
			end
		end
	end
	-- 가죽 너는 시렁
	do
		local x, z = ox - 10, oz + 30
		for _ = 0, 8 do
			if free(x, z, 4, { path = 3 }) then
				break
			end
			x += 3
		end
		if free(x, z, 4, { path = 3 }) then
			local m = Kit.model(f, "시렁")
			local pa = V3(x - 3, lowAt(x - 3, z, 0.5), z)
			local pb = V3(x + 3, lowAt(x + 3, z, 0.5), z)
			cyl(m, "Gidung", pa - V3(0, 0.8, 0), pa + V3(0, 4.6, 0), 0.45, P.wood, MAT.Wood)
			cyl(m, "Gidung", pb - V3(0, 0.8, 0), pb + V3(0, 4.6, 0), 0.45, P.wood, MAT.Wood)
			cyl(m, "Jangdae", pa + V3(0, 4.3, 0), pb + V3(0, 4.3, 0), 0.35, P.wood, MAT.Wood)
			local mid = (pa + pb) / 2
			decoBlock(
				m,
				"Gajuk",
				V3(2.4, 2.8, 0.1),
				CF(mid.X - 1.3, max(pa.Y, pb.Y) + 2.85, mid.Z),
				rgb(166, 120, 80),
				MAT.Fabric
			)
			decoBlock(
				m,
				"Gajuk",
				V3(2.0, 2.4, 0.1),
				CF(mid.X + 1.4, max(pa.Y, pb.Y) + 3.05, mid.Z),
				rgb(200, 176, 140),
				MAT.Fabric
			)
			take(x, z, 4)
		end
	end
	take(ox, oz, ringR + 2)
	return f, ox, oz, ringR
end

local function standingStones(root: Instance)
	local f = Kit.folder(root, "팔방석진")
	local poi = Sites.byId.stones
	local cx, cz = poi.x, poi.z
	local g = surf(cx, cz)
	-- 가운데 너럭바위 (탁자식 고인돌)
	for _, s in { -1, 1 } do
		block(
			f,
			"Goindol",
			V3(1.4, 2.6, 4.2),
			CF(cx + s * 2.6, g + 0.8, cz) * ANG(0, 0, rad(s * 3)),
			P.graniteDark,
			MAT.Slate
		)
	end
	local top = block(
		f,
		"Deopgae",
		V3(9, 1.4, 6.4),
		CF(cx, g + 2.75, cz) * ANG(rad(2), rad(12), rad(-1.5)),
		P.granite:Lerp(P.graniteDark, 0.4),
		MAT.Slate
	)
	decoBlock(f, "Ikki", V3(4.2, 0.2, 2.6), top.CFrame * CF(-1.6, 0.75, 0.9), C.lichen, MAT.LeafyGrass)
	-- 선돌 여덟: 팔방
	for k = 0, 7 do
		local a = rad(k * 45 - 90)
		local x, z = cx + cos(a) * 22, cz + sin(a) * 22
		local gg = lowAt(x, z, 1.5)
		local hgt = R(10, 13.5)
		local s = block(
			f,
			"Seondol",
			V3(R(3.0, 3.8), hgt, R(1.8, 2.4)),
			face(V3(x, gg + hgt / 2 - 1.2, z), V3(cx, gg, cz)) * ANG(rad(R(-3, 3)), 0, rad(R(-4, 4))),
			rgb(132, 132, 126):Lerp(rgb(104, 104, 100), R(0, 1)),
			MAT.Slate
		)
		decoBlock(
			f,
			"Ikki",
			V3(s.Size.X * 0.6, s.Size.Y * R(0.25, 0.4), 0.1),
			s.CFrame * CF(R(-0.4, 0.4), -s.Size.Y * R(0.05, 0.3), -s.Size.Z / 2 - 0.02),
			if k % 3 == 0 then C.lichenOrange else C.lichen,
			MAT.LeafyGrass
		)
		-- 선돌 밑 빛나는 표 (진의 눈)
		local mark = block(
			f,
			"Nun",
			V3(1.2, 0.08, 1.2),
			CF(cx + cos(a) * 18.5, g + 0.06, cz + sin(a) * 18.5) * ANG(0, a + pi / 4, 0),
			C.rune,
			MAT.Neon
		)
		mark.Transparency = 0.45
		mark.CanCollide = false
		mark.CastShadow = false
	end
	-- 희미한 진 고리
	local n = 20
	for k = 0, n - 1 do
		local a = (k + 0.5) * TAU / n
		local x, z = cx + cos(a) * 14, cz + sin(a) * 14
		local seg = block(
			f,
			"Jingori",
			V3(0.45, 0.06, 2 * 14 * sin(pi / n) + 0.1),
			face(V3(x, g + 0.05, z), V3(x - sin(a), g, z + cos(a))),
			C.rune,
			MAT.Neon
		)
		seg.Transparency = 0.55
		seg.CanCollide = false
		seg.CastShadow = false
		if k == 0 then
			Kit.light(seg, C.rune, 20, 0.5)
		end
	end
	-- 비석과 둘레 돌 몇
	Kit.stele(f, V3(cx + 30, lowAt(cx + 30, cz + 12, 2), cz + 12), "팔방석진", V3(cx + 80, 0, cz + 40))
	for k = 0, 3 do
		local a = rad(k * 90 + 30 + R(-15, 15))
		local x, z = cx + cos(a) * R(28, 34), cz + sin(a) * R(28, 34)
		Build.rocks(f, V3(x, lowAt(x, z, 1.5) - 0.5, z), R(2, 3.5), R, { count = 1, moss = false })
	end
	prayerPole(f, cx - 27, cz - 10, 9)
	take(cx, cz, 40)
	return f
end

local function steppe(root: Instance, campX: number, campZ: number, campR: number)
	local f = Kit.folder(root, "백초원")
	local S = Land.STEPPE
	local function inSteppe(x: number, z: number): boolean
		return Land.blob(x, z, S) > 0.55 and Land.blob(x, z, Land.FOREST) < 0.2
	end
	-- 풀 무더기: 큰 덤불 하나에 풀포기 둘 (길과 마령채, 석진 둘레에 많이)
	local anchors = {
		{ campX, campZ, campR + 30 },
		{ 420, -1040, 60 },
		{ 760, -880, 90 },
		{ 900, -1000, 90 },
		{ 560, -1180, 120 },
		{ 820, -1250, 120 },
	}
	local patches = 0
	for _ = 1, 400 do
		if patches >= 18 then
			break
		end
		local an = anchors[1 + floor(R(0, #anchors - 0.01))]
		local a, r = R(0, TAU), R(an[3] * 0.4, an[3])
		local x, z = an[1] + cos(a) * r, an[2] + sin(a) * r
		if inSteppe(x, z) and free(x, z, 5, { path = 3 }) then
			Build.shrub(
				f,
				V3(x, surf(x, z) - 0.35, z),
				R,
				{ size = R(2.6, 4), blobs = 2, leaves = { GRASS[3], GRASS[1], GRASS[5] } }
			)
			for _ = 1, 2 do
				tuft(f, x + R(-3.5, 3.5), z + R(-3.5, 3.5), R(3, 5))
			end
			if R(0, 1) < 0.55 then
				flowers(f, x + R(-5, 5), z + R(-5, 5))
			end
			take(x, z, 5)
			patches += 1
		end
	end
	-- 들꽃 밭 (따로 몇 군데)
	local beds = 0
	for _ = 1, 80 do
		if beds >= 10 then
			break
		end
		local an = anchors[1 + floor(R(0, #anchors - 0.01))]
		local a, r = R(0, TAU), R(10, an[3])
		local x, z = an[1] + cos(a) * r, an[2] + sin(a) * r
		if inSteppe(x, z) and free(x, z, 3, { path = 2 }) then
			flowers(f, x, z)
			flowers(f, x + R(-3, 3), z + R(-3, 3))
			take(x, z, 3)
			beds += 1
		end
	end
	-- 외딴 나무: 둔덕 위 몇 그루
	local trees = 0
	for _ = 1, 300 do
		if trees >= 5 then
			break
		end
		local a, r = R(0, TAU), R(150, 560)
		local x, z = S.x + cos(a) * r, S.z + sin(a) * r
		local h0 = surf(x, z)
		local _, hi = span(x, z, 30)
		if inSteppe(x, z) and h0 > hi - 2.5 and free(x, z, 40, { path = 10 }) then
			bigTree(f, x, z, R(14, 19), { leaves = LEAVES[3], blobs = 6, name = "외딴 나무" })
			take(x, z, 40)
			trees += 1
		end
	end
	-- 돌무더기와 오색 장대: 높은 둔덕 위
	local cairns = 0
	for _ = 1, 300 do
		if cairns >= 3 then
			break
		end
		local a, r = R(0, TAU), R(100, 520)
		local x, z = S.x + cos(a) * r, S.z + sin(a) * r
		local h0 = surf(x, z)
		local _, hi = span(x, z, 40)
		if inSteppe(x, z) and h0 > hi - 1.5 and free(x, z, 60, { path = 6 }) then
			local m = stoneStack(f, x, z, 6, 3.6)
			m.Name = "돌무더기"
			prayerPole(f, x + 3.2, z + 1.5, 8)
			take(x, z, 60)
			cairns += 1
		end
	end
	return f
end

-- 망선대·운제 ----------------------------------------------------------------------------
--
-- 곶 바위길(Land.CAPE_TRAIL) 바깥 가장자리에 말뚝과 밧줄 난간, 들머리에 비석. 꼭대기 북서쪽에 망루 정자 (청허경을 본다).
-- 운제: 가운데 (1233, -1233), 반지름 45, 63 계단. i 번째 계단은 135° + 14.06°·i, 윗면 높이 116 + 4·i.
-- 계단 판은 길이 12.5 (호 간격 11.0 보다 길어 앞뒤가 겹친다), 너비 7, 두께 1.2. 밑에 구름 덩이.

local STAIR =
	{ x = 1233, z = -1233, r = 45, n = 63, a0 = 135, da = 14.06, y0 = 116, dy = 4, len = 12.5, width = 7, thick = 1.2 }
Region.STAIR = STAIR

local function stairStep(i: number): (Vector3, Vector3)
	local a = rad(STAIR.a0 + STAIR.da * i)
	local p = V3(STAIR.x + cos(a) * STAIR.r, STAIR.y0 + STAIR.dy * i, STAIR.z + sin(a) * STAIR.r)
	local t = V3(-sin(a), 0, cos(a))
	return p, t
end
Region.stairStep = stairStep

local function cloudStair(root: Instance)
	local f = Kit.folder(root, "운제")
	for i = 0, STAIR.n - 1 do
		local p, t = stairStep(i)
		local out = V3(t.Z, 0, -t.X) -- 바깥 (가운데 반대쪽)
		local center = p - V3(0, STAIR.thick / 2, 0)
		local step =
			block(f, "Gyedan", V3(STAIR.width, STAIR.thick, STAIR.len), face(center, center + t), C.marble, MAT.Marble)
		step:SetAttribute("Step", i)
		if i % 7 == 3 then
			local inlay =
				block(f, "Mun", V3(0.5, 0.06, STAIR.len - 3), face(p + V3(0, 0.02, 0), p + t), C.rune, MAT.Neon)
			inlay.Transparency = 0.45
			inlay.CanCollide = false
			inlay.CastShadow = false
		end
		-- 구름 덩이: 계단 밑에 하나, 셋째마다 하나 더 (부딪히지 않는다)
		if i > 0 and i < STAIR.n - 1 then
			local puff = ball(
				f,
				"Gureum",
				p - V3(0, 3.2, 0) + out * R(-0.5, 1.5) + t * R(-1.5, 1.5),
				R(6.5, 8),
				C.cloud,
				MAT.SmoothPlastic
			)
			deco(puff)
			puff.Transparency = 0.3
			puff.CastShadow = false
			if i % 4 == 1 then
				Kit.light(puff, rgb(210, 228, 255), 12, 0.7)
			end
			if i % 3 == 0 then
				local p2 = ball(
					f,
					"Gureum",
					p - V3(0, 2.4, 0) + out * R(2.5, 4) - t * R(3, 5),
					R(4.5, 6),
					C.cloud,
					MAT.SmoothPlastic
				)
				deco(p2)
				p2.Transparency = 0.35
				p2.CastShadow = false
			end
		end
	end
	-- 첫 계단 어귀: 구름 새긴 돌기둥 둘과 비석
	local p0, t0 = stairStep(0)
	local out0 = V3(t0.Z, 0, -t0.X)
	for _, s in { -1, 1 } do
		local q = p0 - t0 * 7.5 + out0 * s * 4.4
		local g = lowAt(q.X, q.Z, 0.8)
		local hgt = (p0.Y - g) + 5.5 + 0.6
		block(f, "Dolgidung", V3(1.3, hgt, 1.3), CF(q.X, g - 0.6 + hgt / 2, q.Z), C.marble, MAT.Marble)
		ball(f, "Gureumdol", V3(q.X, p0.Y + 5.4, q.Z), 1.9, C.cloud, MAT.Marble)
	end
	local sq = p0 - t0 * 9 + out0 * 8
	Kit.stele(f, V3(sq.X, lowAt(sq.X, sq.Z, 2), sq.Z), "운제", p0 - t0 * 30)
	take(p0.X - t0.X * 6, p0.Z - t0.Z * 6, 6)
	return f
end

local function cape(root: Instance)
	local f = Kit.folder(root, "망선대")
	local cpe = Land.CAPE
	local sp = Land.CAPE_TRAIL
	-- 난간: 길 바깥 가장자리, 높은 쪽 2/3 에 말뚝과 밧줄
	local samples, all = trailSamples(sp, 9)
	local prev = nil
	for i, s in samples do
		if i > #samples * 0.3 and i < #samples then
			local dx, dz = s[1] - cpe.x, s[3] - cpe.z
			local d = sqrt(dx * dx + dz * dz)
			local x, z = s[1] + dx / d * 5.2, s[3] + dz / d * 5.2
			local post = V3(x, surf(x, z), z)
			cyl(f, "Malttuk", post - V3(0, 1.0, 0), post + V3(0, 3.2, 0), 0.55, rgb(120, 92, 66), MAT.Wood)
			if prev then
				local rope =
					beam(f, "Batjul", prev + V3(0, 2.7, 0), post + V3(0, 2.7, 0), 0.22, 0.22, C.straw, MAT.Fabric)
				rope.CastShadow = false
			end
			prev = post
		end
	end
	-- 들머리 비석
	local s0 = all[1]
	Kit.stele(f, V3(s0[1] - 7, lowAt(s0[1] - 7, s0[3] + 6, 2), s0[3] + 6), "망선대", V3(s0[1] - 60, 0, s0[3] + 40))
	take(s0[1] - 7, s0[3] + 6, 3)

	-- 망루 정자: 꼭대기 북서쪽 가장자리, 청허경 쪽(북동)을 본다
	local sky = Land.SKY
	local qx, qz = cpe.x - 9, cpe.z - 11
	local cf = siteCf(f, qx, qz, sky.x, sky.z, 7.5, 7.5, 1.0)
	local pav = Build.pavilion(f, cf, { detail = 0, bands = 2, bay = 9, name = "망루" })
	local board = block(pav, "Hyeonpan", V3(4.4, 1.5, 0.25), cf * CF(0, 2.4 + 8 - 0.7, -4.5 - 0.75), P.meok, MAT.Wood)
	block(pav, "Te", V3(4.9, 1.95, 0.2), cf * CF(0, 2.4 + 8 - 0.7, -4.5 - 0.62), P.hwang, MAT.Wood)
	Kit.engrave(board, "망선대", "Front")
	take(qx, qz, 9.5)

	-- 바람에 누운 소나무, 바위, 덤불
	local placed = 0
	for _ = 1, 200 do
		if placed >= 3 then
			break
		end
		local a, r = R(0, TAU), R(30, 110)
		local x, z = cpe.x + cos(a) * r, cpe.z + sin(a) * r
		if free(x, z, 4, { path = 6, shore = 8 }) then
			pineTree(f, x, z, R(14, 20), 4)
			placed += 1
		end
	end
	for _ = 1, 40 do
		local a, r = R(0, TAU), R(30, 115)
		local x, z = cpe.x + cos(a) * r, cpe.z + sin(a) * r
		if free(x, z, 3, { path = 4, shore = 6 }) then
			if R(0, 1) < 0.45 then
				Build.rocks(
					f,
					V3(x, lowAt(x, z, 2) - 0.5, z),
					R(3.5, 6.5),
					R,
					{ count = 2, color = rgb(104, 108, 114) }
				)
				take(x, z, 4)
			else
				Build.shrub(
					f,
					V3(x, surf(x, z) - 0.3, z),
					R,
					{ size = R(2, 3.4), leaves = { P.pine, P.leafDeep, P.leaf } }
				)
				take(x, z, 2.5)
			end
		end
	end
	return f
end

-- 청허경 ---------------------------------------------------------------------------------
--
-- 운제가 닿는 남서쪽 가장자리에 흰 돌 단과 우화문, 문 뒤로 비탈을 오르는 돌계단. 흰 돌길이 가운데 마당(전송진·극품 영맥,
-- 비워 둔다)으로 이어지고, 마당 북동쪽 높은 기단 위에 청기와 전각. 서쪽 가장자리에 땅을 굽어보는 정자.
-- 가장자리 세 곳에서 폭포가 허공으로 쏟아지고, 섬 밑에는 큰 구름. 벚나무, 흰 꽃나무, 소나무, 꽃 덤불.

local function islandTopAt(x: number, z: number): number?
	local _, top = Land.island(x, z)
	return top
end

local function rimRadius(a: number): number
	local S = Land.SKY
	local last = 0
	for r = 100, 220, 1 do
		if Land.island(S.x + cos(a) * r, S.z + sin(a) * r) then
			last = r
		end
	end
	return last
end

local function skyIsland(root: Instance)
	local f = Kit.folder(root, "청허경")
	local S = Land.SKY
	local O = V3(S.x, 0, S.z)
	local pTop = stairStep(STAIR.n - 1)
	local A = V3(pTop.X, 0, pTop.Z) -- 운제 끝
	local inward = (O - A).Unit
	local side = V3(-inward.Z, 0, inward.X)

	-- 흰 돌 단 (운제 마지막 계단에 잇닿는다) 과 우화문
	local land = Kit.model(f, "우화문 단")
	local padC = A + inward * 6.5
	local padTop = pTop.Y
	local padLo = math.huge
	for _, q in { { 0, 0 }, { 8, 6 }, { -8, 6 }, { 8, -6 }, { -8, -6 } } do
		local x, z = padC.X + side.X * q[1] + inward.X * q[2], padC.Z + side.Z * q[1] + inward.Z * q[2]
		padLo = min(padLo, islandTopAt(x, z) or (padTop - 6))
	end
	local depth = padTop - padLo + 3
	local pad = block(
		land,
		"Dan",
		V3(18, depth, 13),
		face(padC + V3(0, padTop - depth / 2, 0), padC + inward + V3(0, padTop - depth / 2, 0)),
		C.marble,
		MAT.Marble
	)
	block(land, "Gapseok", V3(18.6, 0.5, 13.6), pad.CFrame * CF(0, depth / 2 - 0.2, 0), C.jade, MAT.Marble)
	-- 단 앞 가장자리 난간 기둥 (운제 쪽은 연다)
	for _, s in { -1, 1 } do
		for k = 0, 1 do
			local q = padC + side * s * (7.8 - k * 2.6) - inward * 6.2
			cyl(land, "Nangan", V3(q.X, padTop, q.Z), V3(q.X, padTop + 2.6, q.Z), 0.7, C.marble, MAT.Marble)
			ball(land, "Boju", V3(q.X, padTop + 2.9, q.Z), 0.8, C.gold, MAT.Metal)
		end
	end
	local gateGround = padC + inward * 1 + V3(0, padTop, 0)
	local gate, gboard = Build.iljumun(f, gateGround, gateGround - inward * 10, 14)
	gate.Name = "우화문"
	Kit.engrave(gboard, "우화문", "Front,Back")
	for _, d in gate:GetDescendants() do
		if d:IsA("BasePart") then
			if d.Name == "Gidung" or d.Name == "Beotim" then
				d.Color = C.ivory
			elseif d.Name == "Dancheong" or d.Name == "Te" then
				d.Color = C.gold
			elseif d.Name == "Giwa" then
				d.Color = C.glazed
			elseif d.Name == "Maru" or d.Name == "Mangwa" then
				d.Color = C.glazedDark
			end
		end
	end
	-- 문 양옆 금빛 꼭지 돌기둥
	for _, s in { -1, 1 } do
		local q = gateGround + side * s * 10.5
		cyl(land, "Pyojeok", q - V3(0, 0.4, 0), q + V3(0, 7, 0), 1.4, C.marble, MAT.Marble)
		ball(land, "Boju", q + V3(0, 7.6, 0), 1.6, C.gold, MAT.Metal)
	end
	take(padC.X, padC.Z, 11)

	-- 문 뒤 돌계단: 섬 비탈을 따라 오른다 (계단마다 밑이 땅에 묻히게 길게)
	local stair = Kit.model(f, "돌계단")
	local y = padTop
	local d = 7
	local stepsEnd = padC
	for _ = 1, 24 do
		local q = padC + inward * d
		local g = islandTopAt(q.X, q.Z)
		if not g or g <= y + 0.4 then
			break
		end
		y += 1
		local lo = min(
			islandTopAt(q.X + side.X * 5, q.Z + side.Z * 5) or g,
			islandTopAt(q.X - side.X * 5, q.Z - side.Z * 5) or g,
			g
		)
		local hgt = math.max(y - lo + 1.5, 1)
		block(
			stair,
			"Dolgyedan",
			V3(11, hgt, 2.2),
			face(V3(q.X, y - hgt / 2, q.Z), V3(q.X, y - hgt / 2, q.Z) + inward),
			C.marble,
			MAT.Marble
		)
		stepsEnd = q
		d += 1.9
	end
	take(padC.X + inward.X * 14, padC.Z + inward.Z * 14, 8)

	-- 흰 돌길: 계단 끝에서 가운데 마당으로
	local wp = Sites.byId.wp_sky
	local veinS = Sites.byId["top@sky"]
	local plaza = V3((wp.x + veinS.x) / 2, 0, (wp.z + veinS.z) / 2)
	local toPlaza = plaza - V3(stepsEnd.X, 0, stepsEnd.Z)
	local len = toPlaza.Magnitude - 13
	local dirP = toPlaza.Unit
	local nPath = floor(len / 6)
	local path = Kit.model(f, "흰 돌길")
	for k = 0, nPath - 1 do
		local q = stepsEnd + dirP * (k * 6 + 1)
		local q2 = q + dirP * 6.2
		local ya, yb = islandTopAt(q.X, q.Z), islandTopAt(q2.X, q2.Z)
		if ya and yb then
			beam(
				path,
				"Dolgil",
				V3(q.X, ya - 0.2, q.Z),
				V3(q2.X, yb - 0.2, q2.Z),
				5.2,
				0.6,
				C.marble:Lerp(C.jade, R(0, 1)),
				MAT.Marble
			)
		end
	end
	table.insert(PATHS, Land.poly({ { stepsEnd.X, stepsEnd.Z }, { plaza.X - dirP.X * 12, plaza.Z - dirP.Z * 12 } }))
	-- 길가 옥등 (쌍으로 셋)
	for k = 1, 3 do
		local q = stepsEnd + dirP * (len * k / 3.4)
		for _, s in { -1, 1 } do
			local lq = q + V3(-dirP.Z, 0, dirP.X) * s * 5.2
			local g = islandTopAt(lq.X, lq.Z)
			if g and not inClear(lq.X, lq.Z, 1.5) then
				smallLantern(f, V3(lq.X, g - 0.1, lq.Z), C.jade, rgb(200, 230, 255))
				take(lq.X, lq.Z, 1.5)
			end
		end
	end

	-- 청기와 전각: 마당 북동쪽, 마당을 본다
	local hx, hz = plaza.X + dirP.X * 44, plaza.Z + dirP.Z * 44
	local hcf = siteCf(f, hx, hz, plaza.X, plaza.Z, 15, 12, 1.4)
	local hall, info = Build.house(f, hcf, {
		bays = { 5, 3 },
		bay = 5.2,
		style = "palace",
		detail = 0,
		bands = 3,
		plinth = 2.6,
		pillarH = 9.5,
		roofColor = C.glazed,
		name = "청허경 전각",
	})
	for _, dd in hall:GetDescendants() do
		if dd:IsA("BasePart") then
			if dd.Name == "Gidung" then
				dd.Color = C.ivory
			elseif dd.Name == "Changbang" then
				dd.Color = C.gold
			elseif dd.Name == "Maru" or dd.Name == "Mangwa" then
				dd.Color = C.glazedDark
			elseif dd.Name == "Gidan" or dd.Name == "Gapseok" or dd.Name == "Step" then
				dd.Color = C.marble
				dd.Material = MAT.Marble
			end
		end
	end
	local board = block(
		hall,
		"Hyeonpan",
		V3(5.6, 1.7, 0.25),
		hcf * CF(0, 2.6 + 9.5 - 0.6, -info.depth / 2 - 0.75),
		P.meok,
		MAT.Wood
	)
	block(hall, "Te", V3(6.2, 2.2, 0.2), hcf * CF(0, 2.6 + 9.5 - 0.6, -info.depth / 2 - 0.62), C.gold, MAT.Metal)
	Kit.engrave(board, "청허경", "Front")
	take(hx, hz, 20)
	-- 전각 앞 석등 한 쌍
	for _, s in { -1, 1 } do
		local q = V3(hx, 0, hz) - dirP * 17 + V3(-dirP.Z, 0, dirP.X) * s * 9
		local g = islandTopAt(q.X, q.Z)
		if g and not inClear(q.X, q.Z, 2) then
			local lan = Build.stoneLantern(f, V3(q.X, g - 0.1, q.Z))
			for _, p in lan:GetDescendants() do
				if p:IsA("BasePart") and p.Material == MAT.Granite then
					p.Color = C.marble
					p.Material = MAT.Marble
				end
			end
			take(q.X, q.Z, 2)
		end
	end

	-- 서쪽 가장자리 정자: 땅(망선대 쪽)을 굽어본다
	local pa = rad(195)
	local pr = rimRadius(pa) - 20
	local px, pz = S.x + cos(pa) * pr, S.z + sin(pa) * pr
	local pcf = siteCf(f, px, pz, S.x, S.z, 7.5, 7.5, 1.2)
	local pav = Build.pavilion(f, pcf, { detail = 0, bands = 3, bay = 9, roofColor = C.glazed, name = "운해정" })
	for _, dd in pav:GetDescendants() do
		if dd:IsA("BasePart") then
			if dd.Name == "Gidung" or dd.Name == "Nangan" or dd.Name == "Dongja" then
				dd.Color = C.ivory
			elseif dd.Name == "Jeolbyeong" then
				dd.Color = C.gold
				dd.Material = MAT.Metal
			elseif dd.Name == "Maru" or dd.Name == "Mangwa" then
				dd.Color = C.glazedDark
			end
		end
	end
	take(px, pz, 10)

	-- 폭포 셋: 가장자리에서 허공으로 (샘에서 가는 물길이 이어진다)
	for _, deg in { 100, 172, 55 } do
		local a = rad(deg)
		local rr = rimRadius(a) - 0.6
		local out = V3(cos(a), 0, sin(a))
		local lipX, lipZ = S.x + cos(a) * rr, S.z + sin(a) * rr
		local lipY = islandTopAt(lipX, lipZ) or (S.top - 20)
		Build.waterfall(f, V3(lipX, lipY - 0.2, lipZ), out, 6, 95)
		-- 물길 (안쪽 샘 → 가장자리)
		local stream = Kit.model(f, "물길")
		local prevQ = V3(lipX, lipY - 0.15, lipZ)
		for k = 1, 3 do
			local q = V3(S.x + cos(a) * (rr - k * 8), 0, S.z + sin(a) * (rr - k * 8))
			local qy = islandTopAt(q.X, q.Z)
			if not qy then
				break
			end
			q = V3(q.X, qy - 0.15, q.Z)
			local w = beam(stream, "Mul", prevQ, q, 5.2 - k * 0.6, 0.3, C.water, MAT.Glass)
			w.Transparency = 0.25
			deco(w)
			prevQ = q
		end
		local spring = Kit.disc(stream, "Saem", prevQ + V3(0, 0.05, 0), 3.4, 0.3, C.water, MAT.Glass)
		spring.Transparency = 0.2
		deco(spring)
		for k = 0, 1 do
			local q = prevQ + V3(-out.Z, 0, out.X) * (if k == 0 then 4.2 else -4.2)
			Build.rocks(
				stream,
				V3(q.X, (islandTopAt(q.X, q.Z) or prevQ.Y) - 0.4, q.Z),
				R(1.8, 2.8),
				R,
				{ count = 1, color = rgb(150, 156, 160) }
			)
		end
		take(S.x + cos(a) * (rr - 12), S.z + sin(a) * (rr - 12), 14)
	end

	-- 섬 밑 구름 (크고 흰 덩이, 부딪히지 않는다)
	local clouds = Kit.model(f, "구름")
	for k = 0, 13 do
		local a = k * 2.39996 + R(-0.3, 0.3)
		local r = if k < 6 then R(20, 95) else R(120, 185)
		local x, z = S.x + cos(a) * r, S.z + sin(a) * r
		local size = if k < 6 then R(44, 66) else R(30, 48)
		local bottom = Land.island(x, z)
		local yc
		if bottom then
			yc = bottom - size * 0.28
		else
			yc = S.top - 50 - size / 2 - R(0, 40)
		end
		local c = ball(clouds, "Gureum", V3(x, yc, z), size, C.cloud, MAT.SmoothPlastic)
		deco(c)
		c.Transparency = if k < 6 then 0.25 else 0.4
		c.CastShadow = false
	end

	-- 꽃나무와 소나무, 꽃 덤불
	local trees = Kit.folder(f, "나무")
	local placed = 0
	for _ = 1, 400 do
		if placed >= 9 then
			break
		end
		local a, r = R(0, TAU), R(20, 140)
		local x, z = S.x + cos(a) * r, S.z + sin(a) * r
		if free(x, z, 4.5, { sky = true, path = 4 }) then
			local g = islandTopAt(x, z) or 0
			local lo = g
			for k = 0, 3 do
				local aa = k * pi / 2
				lo = min(lo, islandTopAt(x + cos(aa) * 1.5, z + sin(aa) * 1.5) or g)
			end
			local base = V3(x, lo - 0.15, z)
			local roll = placed % 3
			if roll == 0 then
				Build.blossom(trees, base, R, { height = R(9, 12) })
			elseif roll == 1 then
				Build.broadleaf(trees, base, R, {
					height = R(9, 12),
					name = "흰 꽃나무",
					bark = rgb(96, 84, 80),
					leaves = { P.blossomWhite:Lerp(P.blossom, 0.3), P.blossomWhite, rgb(255, 250, 246) },
				})
			else
				Build.pine(trees, base, R, { height = R(14, 19), tiers = 4 })
			end
			take(x, z, 6)
			placed += 1
		end
	end
	local shrubs = 0
	for _ = 1, 60 do
		if shrubs >= 6 then
			break
		end
		local a, r = R(0, TAU), R(15, 130)
		local x, z = S.x + cos(a) * r, S.z + sin(a) * r
		if free(x, z, 2, { sky = true, path = 2 }) then
			local g = islandTopAt(x, z) or 0
			Build.shrub(
				trees,
				V3(x, g - 0.3, z),
				R,
				{ size = R(2.4, 3.6), flowers = if R(0, 1) < 0.5 then P.blossomWhite else rgb(236, 206, 120) }
			)
			take(x, z, 2.5)
			shrubs += 1
		end
	end
	return f
end

-- 짓기 ------------------------------------------------------------------------------------

function Region.build(root: Instance, rng: (number, number) -> number)
	R = rng
	resetZones()
	local f = Kit.folder(root, "동쪽")
	ancientTree(f)
	temple(f)
	hermitage(f)
	eastHill(f)
	cloudStair(f)
	cape(f)
	skyIsland(f)
	local _, ox, oz, ringR = camp(f)
	standingStones(f)
	forest(f)
	bambooGrove(f)
	steppe(f, ox, oz, ringR)
	return f
end

Region.partCount = partCount

return Region
