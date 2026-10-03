-- 블록수선전 건물·자연 짓기 (프로토타입). World.luau 와 같은 Roblox 식 모듈: 전역 Instance, Vector3, CFrame, Color3, Enum 만 쓴다.
-- Lune 에서도 돈다 (CFrame.lookAt / CFrame.new(pos, target) 은 Lune 에서 Z 가 뒤집혀서 쓰지 않는다.
-- CFrame.fromMatrix 와 CFrame.Angles 는 Lune 과 엔진이 같은 값을 낸다: 엔진에서 GetComponents 로 맞춰 봤다).
--
-- 엔진에서 레이캐스트로 잰 모양 (크기 4 의 부품):
--   WedgePart       윗면 높이 = z (앞 -Z 가 낮고 뒤 +Z 가 높다), 비탈 법선 (0, .707, -.707)
--   CornerWedgePart 꼭짓점이 (+X, +Y, -Z) 모서리 위. 높이 = min(x, -z)
--   Cylinder        축이 로컬 X

local Build = {}

-- 색 ------------------------------------------------------------------------------------
-- 단청 오방색은 웹 색표(#62D957 같은)를 그대로 쓰면 Realistic 조명에서 형광처럼 뜬다. 채도를 30~40% 낮췄다.
local P = {
	giwa = Color3.fromRGB(70, 74, 80), -- 기와 (먹기와)
	giwaDark = Color3.fromRGB(50, 53, 58), -- 용마루·추녀마루
	mortar = Color3.fromRGB(228, 224, 212), -- 양성 (마루 흰 줄)
	seokganju = Color3.fromRGB(124, 50, 38), -- 석간주: 절·궁 기둥
	wood = Color3.fromRGB(128, 90, 60), -- 민가 기둥
	woodDark = Color3.fromRGB(78, 54, 38),
	noerok = Color3.fromRGB(62, 122, 100), -- 뇌록: 단청 바탕 (창방, 공포, 서까래)
	yangrok = Color3.fromRGB(96, 156, 82), -- 양록
	samcheong = Color3.fromRGB(88, 146, 186), -- 삼청
	gunjeong = Color3.fromRGB(42, 60, 118), -- 군청
	juhong = Color3.fromRGB(192, 66, 46), -- 주홍
	hwang = Color3.fromRGB(222, 176, 72), -- 황
	meok = Color3.fromRGB(36, 34, 34), -- 먹
	plaster = Color3.fromRGB(234, 228, 212), -- 회벽
	hanji = Color3.fromRGB(244, 238, 222), -- 창호지
	granite = Color3.fromRGB(158, 154, 146), -- 장대석
	graniteDark = Color3.fromRGB(120, 116, 110),
	soffit = Color3.fromRGB(58, 44, 36), -- 처마 밑 (어둡게)
	-- 나무 (LeafyGrass 재질은 색을 15% 쯤 어둡게 보이게 해서 밝게 잡았다: 엔진 썸네일로 확인)
	bark = Color3.fromRGB(92, 70, 54),
	barkPine = Color3.fromRGB(146, 82, 56), -- 적송 윗동
	barkBirch = Color3.fromRGB(214, 210, 200),
	leafDeep = Color3.fromRGB(58, 104, 60),
	leaf = Color3.fromRGB(84, 134, 70),
	leafLight = Color3.fromRGB(122, 164, 84),
	leafYellow = Color3.fromRGB(150, 160, 78),
	pine = Color3.fromRGB(52, 92, 64),
	pineLight = Color3.fromRGB(70, 112, 72),
	willow = Color3.fromRGB(128, 166, 82),
	blossom = Color3.fromRGB(242, 184, 204),
	blossomDeep = Color3.fromRGB(226, 148, 176),
	blossomWhite = Color3.fromRGB(250, 236, 240),
	bamboo = Color3.fromRGB(116, 150, 72),
	bambooOld = Color3.fromRGB(150, 160, 92),
	bambooLeaf = Color3.fromRGB(84, 132, 66),
	maple = Color3.fromRGB(196, 74, 48),
}
Build.P = P

local SMALL = 2 -- 가장 긴 변이 이보다 짧으면 그림자를 안 드리운다

-- 기본 부품 ------------------------------------------------------------------------------

-- position 에 서서 target 쪽(수평)을 보는 CFrame (World.luau 의 face 와 같다)
local function face(position: Vector3, target: Vector3): CFrame
	local dx, dz = target.X - position.X, target.Z - position.Z
	if dx * dx + dz * dz < 1e-6 then
		return CFrame.new(position)
	end
	return CFrame.new(position) * CFrame.Angles(0, math.atan2(-dx, -dz), 0)
end
Build.face = face

local function new(className: string, parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?): BasePart
	local p = Instance.new(className) :: BasePart
	p.Name = name
	p.Anchored = true
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	if math.max(size.X, size.Y, size.Z) < SMALL then
		p.CastShadow = false
	end
	p.Parent = parent
	return p
end

function Build.block(parent, name, size, cf, color, material)
	return new("Part", parent, name, size, cf, color, material)
end
local block = Build.block

function Build.wedge(parent, name, size, cf, color, material)
	return new("WedgePart", parent, name, size, cf, color, material)
end
local wedge = Build.wedge

function Build.cornerWedge(parent, name, size, cf, color, material)
	return new("CornerWedgePart", parent, name, size, cf, color, material)
end

-- 꾸밈 부품: 부딪히지도, 레이에 잡히지도 않는다 (잎, 작은 장식)
local function deco(p: BasePart): BasePart
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	return p
end
Build.deco = deco

-- a 에서 b 까지 각재. 단면 w(가로) × h(세로), 세로는 upHint 쪽
function Build.beam(parent, name, a: Vector3, b: Vector3, w: number, h: number, color, material, upHint: Vector3?)
	local d = b - a
	local len = d.Magnitude
	local Z = d / len
	local hint = upHint or Vector3.yAxis
	if math.abs(Z:Dot(hint)) > 0.98 then
		hint = if math.abs(Z.X) < 0.9 then Vector3.xAxis else Vector3.zAxis
	end
	local X = hint:Cross(Z).Unit
	local Y = Z:Cross(X)
	return block(parent, name, Vector3.new(w, h, len), CFrame.fromMatrix((a + b) / 2, X, Y), color, material)
end
local beam = Build.beam

-- a 에서 b 까지 둥근 기둥 (지름 d)
function Build.cyl(parent, name, a: Vector3, b: Vector3, d: number, color, material)
	local v = b - a
	local len = v.Magnitude
	local X = v / len
	local hint = if math.abs(X.Y) < 0.95 then Vector3.yAxis else Vector3.xAxis
	local Z = X:Cross(hint).Unit
	local Y = Z:Cross(X)
	local p = block(parent, name, Vector3.new(len, d, d), CFrame.fromMatrix((a + b) / 2, X, Y), color, material)
	p.Shape = Enum.PartType.Cylinder
	return p
end
local cyl = Build.cyl

function Build.ball(parent, name, center: Vector3, d: number, color, material)
	local p = block(parent, name, Vector3.new(d, d, d), CFrame.new(center), color, material)
	p.Shape = Enum.PartType.Ball
	return p
end
local ball = Build.ball

-- 직사각 판: 꼭짓점 p0 에서 변 e1, e2 (서로 직각). 윗면이 그 평면에 오고 두께는 up 반대쪽으로
function Build.slab(parent, name, p0: Vector3, e1: Vector3, e2: Vector3, t: number, up: Vector3, color, material)
	local l1, l2 = e1.Magnitude, e2.Magnitude
	if l1 < 0.02 or l2 < 0.02 then
		return nil
	end
	local X = e1 / l1
	local N = (e2 / l2):Cross(X)
	if N:Dot(up) < 0 then
		N = -N
	end
	local center = p0 + e1 / 2 + e2 / 2 - N * (t / 2)
	return block(parent, name, Vector3.new(l1, t, l2), CFrame.fromMatrix(center, X, N), color, material)
end
local slab = Build.slab

-- 직각삼각 판: 직각이 R, 두 다리 RA, RB. 쐐기 하나
function Build.rightTri(parent, name, R: Vector3, A: Vector3, B: Vector3, t: number, up: Vector3?, color, material)
	local la, lb = (A - R).Magnitude, (B - R).Magnitude
	if la < 0.02 or lb < 0.02 then
		return nil
	end
	local Y = (B - R) / lb
	local Z = (R - A) / la
	local X = Y:Cross(Z)
	local center = (A + B) / 2
	if up then
		center -= (if X:Dot(up) < 0 then -X else X) * (t / 2)
	end
	return wedge(parent, name, Vector3.new(t, lb, la), CFrame.fromMatrix(center, X, Y), color, material)
end
local rightTri = Build.rightTri

-- 아무 삼각 판: 가장 긴 변에 내린 수선으로 직각삼각 둘 (쐐기 둘)
function Build.tri(parent, name, a: Vector3, b: Vector3, c: Vector3, t: number, up: Vector3?, color, material)
	local ab, ac, bc = (b - a).Magnitude, (c - a).Magnitude, (c - b).Magnitude
	if ab >= ac and ab >= bc then
		a, c = c, a
	elseif ac >= ab and ac >= bc then
		a, b = b, a
	end
	local bc2 = c - b
	local k = (a - b):Dot(bc2) / bc2:Dot(bc2)
	local foot = b + bc2 * k
	local w1 = rightTri(parent, name, foot, b, a, t, up, color, material)
	local w2 = rightTri(parent, name, foot, c, a, t, up, color, material)
	return w1, w2
end
local tri = Build.tri

-- 지붕 ----------------------------------------------------------------------------------
--
-- 처마 윤곽(반너비 ex ≥ 반깊이 ez)에서 안쪽으로 띠(band)를 겹겹이 들인다. 띠마다 물매가 다르다 (처마 쪽이 눕고
-- 용마루 쪽이 선다 → 오목한 지붕 곡선). 띠 하나는 면마다 직사각 판 하나 + 끝의 직각삼각 쐐기 둘 (추녀선에서 옆 면과
-- 꼭 맞는다). 처마 띠(첫 띠)는 귀를 들어 올린다(앙곡)·내민다(안허리곡): 귀 쪽 lift 구간을 삼각으로 쪼갠다.
--
-- spec:
--   ex, ez       처마 윤곽 반너비·반깊이 (ex ≥ ez)
--   eave         처마 띠 수평 너비 (= 내민 처마 길이, 서까래가 그 밑에 든다)
--   bands        처마 띠 위로 띠 수 (기본 4)
--   pitches      띠마다 물매(도). 처마 띠부터. 없으면 pitchLow~pitchHigh
--   kind         "paljak"(팔작) | "hip"(우진각·모임) | "gable"(맞배)
--   nHip         팔작에서 추녀를 두는 띠 수 (처마 띠 포함, 기본 2)
--   gableOver    맞배·팔작 박공이 합각 밖으로 나오는 길이
--   t            지붕 두께
--   lift, flare  귀 들림 높이, 귀 내밈
--   liftLen      귀 들림 구간 (처마선 따라, 귀에서)
--   segs         귀 들림 구간 쪼갬 수
-- frame 은 처마 끝선(면 가운데) 높이, 건물 가운데. 앞이 -Z.
-- 돌려주는 값: { height = 용마루 높이, under = function(o) 그 들임에서 지붕 밑면 높이 }

local function profile(spec)
	local n = 1 + (spec.bands or 4)
	local widths, pitches = {}, {}
	local rest = (spec.ez - spec.eave) / (n - 1)
	for k = 1, n do
		widths[k] = if k == 1 then spec.eave else rest
		pitches[k] = if spec.pitches
			then spec.pitches[k]
			else (spec.pitchLow or 17) + ((spec.pitchHigh or 46) - (spec.pitchLow or 17)) * (k - 1) / (n - 1)
	end
	local o, h = { [0] = 0 }, { [0] = 0 }
	for k = 1, n do
		o[k] = o[k - 1] + widths[k]
		h[k] = h[k - 1] + widths[k] * math.tan(math.rad(pitches[k]))
	end
	return n, o, h, pitches
end
Build.profile = profile

function Build.roof(parent: Instance, frame: CFrame, spec)
	local ex, ez = spec.ex, spec.ez
	local t = spec.t or 0.6
	local kind = spec.kind or "paljak"
	local color = spec.color or P.giwa
	local mat = spec.material or Enum.Material.ClayRoofTiles
	local ridgeColor = spec.ridgeColor or P.giwaDark
	local n, o, h, pitches = profile(spec)
	local nHip = if kind == "hip" then n elseif kind == "gable" then 0 else math.clamp(spec.nHip or 2, 1, n - 1)
	local lift = if nHip > 0 then math.min(spec.lift or 1.4, h[1] * 1.15) else 0
	local flare = if nHip > 0 then spec.flare or 0.5 else 0
	local segs = spec.segs or 2
	local bo = spec.gableOver or 0.8
	local up = frame.UpVector
	local function W(v: Vector3): Vector3
		return frame:PointToWorldSpace(v)
	end
	local m = Instance.new("Model")
	m.Name = "지붕"
	m.Parent = parent

	-- 면: 바깥 법선 nrm, 처마선 방향 tg, 들임 o 에서 처마선 반길이 hl, 가운데에서 처마선까지 거리 dist
	local faces = {
		{ nrm = Vector3.new(0, 0, -1), tg = Vector3.new(1, 0, 0), long = true },
		{ nrm = Vector3.new(0, 0, 1), tg = Vector3.new(-1, 0, 0), long = true },
		{ nrm = Vector3.new(1, 0, 0), tg = Vector3.new(0, 0, 1), long = false },
		{ nrm = Vector3.new(-1, 0, 0), tg = Vector3.new(0, 0, -1), long = false },
	}
	local function hl(f, inset: number): number
		return (if f.long then ex else ez) - inset
	end
	local function dist(f, inset: number): number
		return (if f.long then ez else ex) - inset
	end
	local function pt(f, inset: number, x: number, y: number, out: number?): Vector3
		return f.nrm * (dist(f, inset) + (out or 0)) + f.tg * x + Vector3.new(0, y, 0)
	end
	local Gx = ex - o[nHip] -- 합각 자리 (팔작)
	local Lz = math.clamp(spec.liftLen or ez * 0.55, o[1] + 0.05, ez * 0.95)

	-- 띠 하나, 면 하나 (k 번째 띠). half: 이 띠 끝을 어디까지 (추녀면 삼각으로 귀까지, 아니면 박공까지)
	local function band(f, k: number)
		local oa, ob, ha, hb = o[k - 1], o[k], h[k - 1], h[k]
		local hipped = k <= nHip
		if not hipped and not f.long then
			return
		end
		local a = if hipped then hl(f, oa) elseif nHip == 0 then ex else Gx + bo
		local b = if hipped then hl(f, ob) elseif nHip == 0 then ex else Gx + bo
		local slope = (pt(f, ob, 0, hb) - pt(f, oa, 0, ha))
		if k == 1 and lift > 0 then
			-- 처마 띠: 가운데 판 + 귀 쪽 들림 삼각
			local c = hl(f, 0) - Lz
			slab(m, "Giwa", W(pt(f, oa, -c, ha)), frame:VectorToWorldSpace(f.tg * (2 * c)), frame:VectorToWorldSpace(slope), t, up, color, mat)
			local flT = flare -- 직각 귀: 처마선 따라 내미는 만큼 = 바깥으로 내미는 만큼
			for _, side in { 1, -1 } do
				local function inner(s: number): Vector3
					return pt(f, ob, side * (c + s * (b - c)), hb)
				end
				local function outer(s: number): Vector3
					local fs = s * s
					return pt(f, oa, side * (c + s * (Lz + flT)), ha + lift * fs, flare * fs)
				end
				for j = 0, segs - 1 do
					local s0, s1 = j / segs, (j + 1) / segs
					local i0, i1, o0, o1 = W(inner(s0)), W(inner(s1)), W(outer(s0)), W(outer(s1))
					tri(m, "Giwa", i0, i1, o1, t, up, color, mat)
					tri(m, "Giwa", i0, o1, o0, t, up, color, mat)
				end
			end
		else
			slab(m, "Giwa", W(pt(f, oa, -b, ha)), frame:VectorToWorldSpace(f.tg * (2 * b)), frame:VectorToWorldSpace(slope), t, up, color, mat)
			if a > b + 0.02 then
				for _, side in { 1, -1 } do
					rightTri(m, "Giwa", W(pt(f, oa, side * b, ha)), W(pt(f, oa, side * a, ha)), W(pt(f, ob, side * b, hb)), t, up, color, mat)
				end
			end
		end
	end
	-- stopInset: 그 들임까지만 짓는다 (탑의 아래층 처마처럼 위가 몸채에 묻힐 때)
	local last = n
	if spec.stopInset then
		for k = 1, n do
			if o[k] >= spec.stopInset then
				last = k
				break
			end
		end
	end
	for k = 1, last do
		for _, f in faces do
			band(f, k)
		end
	end
	if last < n then
		-- 추녀마루만 그 띠까지
		for _, sx in { 1, -1 } do
			for _, sz in { 1, -1 } do
				local prev = Vector3.new(sx * (ex + flare), lift, sz * (ez + flare))
				for k = 1, last do
					local cur = Vector3.new(sx * (ex - o[k]), h[k], sz * (ez - o[k]))
					beam(m, "Maru", W(prev + Vector3.new(0, 0.25, 0)), W(cur + Vector3.new(0, 0.25, 0)), 0.7, 0.7, ridgeColor, Enum.Material.Slate, up)
					prev = cur
				end
			end
		end
		return { height = h[last], model = m, pitches = pitches, o = o, h = h, Lz = Lz }
	end

	-- 합각 (팔작·맞배의 박공 밑 세모 벽): 띠마다 네모 + 세모
	if nHip < n then
		local gx = spec.gableX or (if nHip == 0 then ex - bo else Gx - 0.15)
		local kStart = math.max(nHip + 1, 2) -- 맞배는 처마 띠 밑(벽 밖)에 벽을 두지 않는다
		local base = h[kStart - 1] - t * 1.2 -- 지붕 속 막음(Sok) 위까지 내려 틈이 없게
		for _, sx in { 1, -1 } do
			for k = kStart, n do
				local za, zb = ez - o[k - 1], ez - o[k]
				local ya, yb = h[k - 1] - t * 0.8, h[k] - t * 0.8
				for _, sz in { 1, -1 } do
					if ya > base + 0.05 then
						block(m, "Hapgak", Vector3.new(0.4, ya - base, za - zb), frame * CFrame.new(sx * gx, (ya + base) / 2, sz * (za + zb) / 2), spec.gableColor or P.plaster, Enum.Material.Plaster)
					end
					rightTri(m, "Hapgak", W(Vector3.new(sx * gx, ya, sz * zb)), W(Vector3.new(sx * gx, ya, sz * za)), W(Vector3.new(sx * gx, yb, sz * zb)), 0.4, nil, spec.gableColor or P.plaster, Enum.Material.Plaster)
				end
			end
		end
	end

	-- 마루: 용마루, 추녀마루, 내림마루 (윗면 위에 얹는다)
	local ridgeW, ridgeH = spec.ridgeW or 1.1, spec.ridgeH or 1.1
	local function ridge(a: Vector3, b: Vector3, w: number, hgt: number)
		local p = beam(m, "Maru", W(a + Vector3.new(0, hgt * 0.3, 0)), W(b + Vector3.new(0, hgt * 0.3, 0)), w, hgt, ridgeColor, Enum.Material.Slate, up)
		return p
	end
	local topH = h[n]
	local ridgeHalf = if nHip == n then ex - ez else Gx + bo
	if ridgeHalf > 0.1 then
		ridge(Vector3.new(-ridgeHalf - 0.3, topH, 0), Vector3.new(ridgeHalf + 0.3, topH, 0), ridgeW, ridgeH)
		-- 양성: 용마루 밑 흰 줄 두 가닥
		for _, sz in { 1, -1 } do
			block(m, "Yangseong", Vector3.new(2 * ridgeHalf + 0.4, 0.25, 0.12), frame * CFrame.new(0, topH + 0.05, sz * (ridgeW / 2 + 0.02)), P.mortar, Enum.Material.Plaster)
		end
		-- 용마루 끝 망와: 살짝 들린 막새
		for _, sx in { 1, -1 } do
			block(m, "Mangwa", Vector3.new(0.5, ridgeH * 1.5, ridgeW * 1.15), frame * CFrame.new(sx * (ridgeHalf + 0.45), topH + ridgeH * 0.55, 0) * CFrame.Angles(0, 0, sx * math.rad(-18)), ridgeColor, Enum.Material.Slate)
		end
	else
		-- 모임지붕 꼭대기 절병통
		ball(m, "Jeolbyeong", W(Vector3.new(0, topH + 0.7, 0)), 1.6, ridgeColor, Enum.Material.Slate)
		cyl(m, "Jeolbyeong", W(Vector3.new(0, topH + 1.3, 0)), W(Vector3.new(0, topH + 2.4, 0)), 0.9, ridgeColor, Enum.Material.Slate)
	end
	-- 추녀마루: 귀마다 띠 꼭짓점을 따라 (처마 띠는 들린 귀까지)
	for _, sx in { 1, -1 } do
		for _, sz in { 1, -1 } do
			local prev = Vector3.new(sx * (ex + flare), lift, sz * (ez + flare))
			for k = 1, nHip do
				local cur = Vector3.new(sx * (ex - o[k]), h[k], sz * (ez - o[k]))
				if k == n and ex ~= ez then
					cur = Vector3.new(sx * (ex - ez), h[k], 0)
				end
				ridge(prev, cur, ridgeW * 0.75, ridgeH * 0.8)
				prev = cur
			end
			-- 귀 끝 망와: 추녀마루 끝에 바깥(대각선)을 보고 뒤로 젖힌 막새 판
			local tip = Vector3.new(sx * (ex + flare + 0.15), lift + 0.55, sz * (ez + flare + 0.15))
			local look = face(tip, tip + Vector3.new(sx, 0, sz))
			block(m, "Mangwa", Vector3.new(1.0, 1.1, 0.35), frame * look * CFrame.Angles(math.rad(-25), 0, 0), ridgeColor, Enum.Material.Slate)
		end
	end
	-- 내림마루: 팔작·맞배의 박공 따라
	if nHip < n then
		for _, sx in { 1, -1 } do
			local gx = sx * (if nHip == 0 then ex else Gx + bo)
			for _, sz in { 1, -1 } do
				for k = nHip + 1, n do
					ridge(Vector3.new(gx, h[k - 1], sz * (ez - o[k - 1])), Vector3.new(gx, h[k], sz * (ez - o[k])), ridgeW * 0.7, ridgeH * 0.7)
				end
			end
		end
	end

	-- 지붕 밑면 높이 (들임 inset 에서): 집 몸채가 처마 밑에 꼭 들어가게
	local function under(inset: number): number
		for k = 1, n do
			if inset <= o[k] + 1e-6 then
				local u = (inset - o[k - 1]) / (o[k] - o[k - 1])
				return h[k - 1] + (h[k] - h[k - 1]) * u - t / math.cos(math.rad(pitches[k]))
			end
		end
		return h[n]
	end
	return { height = topH, under = under, model = m, pitches = pitches, o = o, h = h, Lz = Lz }
end
local roof = Build.roof

-- 집 ------------------------------------------------------------------------------------
--
-- cf: 기단 밑 가운데 (땅), 앞(-Z)이 마당 쪽. opts:
--   bays = { 3, 2 }   칸 수 (정면, 측면)
--   bay = 5           칸 너비
--   pillarH = 8.5     기둥 높이
--   plinth = 1.6      기단 높이
--   eave = 4          처마 내밈
--   roof = "paljak" | "hip" | "gable"
--   style = "house" | "temple" | "palace"
--   detail = 0..2     2: 서까래·공포·단청띠, 1: 공포만, 0: 몸채와 지붕만
--   roofColor, wallColor
function Build.house(parent: Instance, cf: CFrame, opts)
	opts = opts or {}
	local bays = opts.bays or { 3, 2 }
	local bay = opts.bay or 5
	local pillarH = opts.pillarH or 8.5
	local plinth = opts.plinth or 1.6
	local eave = opts.eave or 4
	local style = opts.style or "house"
	local detail = if opts.detail == nil then 2 else opts.detail
	local fancy = style ~= "house"
	local W, D = bays[1] * bay, bays[2] * bay
	local pillarColor = opts.pillarColor or (if fancy then P.seokganju else P.wood)
	local beamColor = if fancy then P.noerok else P.wood
	local m = Instance.new("Model")
	m.Name = opts.name or (if style == "house" then "기와집" elseif style == "temple" then "법당" else "전각")
	m.Parent = parent

	-- 기단: 장대석 + 갑석, 앞 가운데 계단
	local pad = 2.2
	local floorY = plinth
	block(m, "Gidan", Vector3.new(W + 2 * pad, plinth - 0.1, D + 2 * pad), cf * CFrame.new(0, (plinth - 0.1) / 2 - 0.6, 0), P.granite, Enum.Material.Granite)
	block(m, "Gapseok", Vector3.new(W + 2 * pad + 0.3, 0.7, D + 2 * pad + 0.3), cf * CFrame.new(0, plinth - 0.35, 0), P.graniteDark, Enum.Material.Granite)
	if not opts.noSteps then
		local steps = math.max(1, math.floor(plinth / 0.6 + 0.5) - 1)
		local riser = plinth / (steps + 1)
		for i = 1, steps do
			local depth = 1.0 * (steps - i + 1)
			local y1 = i * riser
			block(m, "Step", Vector3.new(4.2, y1 + 0.6, depth), cf * CFrame.new(0, (y1 - 0.6) / 2, -(D / 2 + pad + 0.15) - depth / 2), P.granite, Enum.Material.Granite)
		end
	end
	-- 마루 바닥
	block(m, "Floor", Vector3.new(W - 0.4, 0.3, D - 0.4), cf * CFrame.new(0, floorY + 0.15, 0), P.woodDark, Enum.Material.WoodPlanks)

	-- 기둥: 둘레만 (안 기둥은 보이지 않는다)
	local pillarD = 1.15
	local top = floorY + pillarH
	local posts = {}
	for i = 0, bays[1] do
		for j = 0, bays[2] do
			if i == 0 or i == bays[1] or j == 0 or j == bays[2] then
				local x, z = -W / 2 + i * bay, -D / 2 + j * bay
				table.insert(posts, Vector3.new(x, 0, z))
				block(m, "Choseok", Vector3.new(1.7, 0.5, 1.7), cf * CFrame.new(x, floorY + 0.25, z), P.graniteDark, Enum.Material.Granite)
				cyl(m, "Gidung", cf:PointToWorldSpace(Vector3.new(x, floorY + 0.5, z)), cf:PointToWorldSpace(Vector3.new(x, top, z)), pillarD, pillarColor, Enum.Material.Wood)
			end
		end
	end

	-- 창방 (기둥머리를 두르는 보) + 단청 띠
	local beamH, beamW = 1.1, 0.8
	local ringY = top - beamH / 2
	for _, side in { { W, 0, -D / 2 }, { W, 0, D / 2 }, { D, -W / 2, 0 }, { D, W / 2, 0 } } do
		local alongX = side[3] ~= 0
		local size = if alongX then Vector3.new(side[1] + pillarD, beamH, beamW) else Vector3.new(beamW, beamH, side[1] + pillarD)
		block(m, "Changbang", size, cf * CFrame.new(side[2], ringY, side[3]), beamColor, Enum.Material.Wood)
		if fancy and detail >= 2 then
			-- 창방 밑 주홍 띠, 위 평방(군청)
			local band = if alongX then Vector3.new(side[1] + pillarD + 0.02, 0.22, beamW + 0.04) else Vector3.new(beamW + 0.04, 0.22, side[1] + pillarD + 0.02)
			block(m, "Dancheong", band, cf * CFrame.new(side[2], ringY - beamH / 2 + 0.11, side[3]), P.juhong, Enum.Material.SmoothPlastic)
			local pband = if alongX then Vector3.new(side[1] + pillarD + 0.4, 0.5, beamW + 0.3) else Vector3.new(beamW + 0.3, 0.5, side[1] + pillarD + 0.4)
			block(m, "Pyeongbang", pband, cf * CFrame.new(side[2], top + 0.25, side[3]), P.gunjeong, Enum.Material.Wood)
		end
	end
	local structTop = top + (if fancy and detail >= 2 then 0.5 else 0)

	-- 공포: 기둥머리 주두 + 첨차(벽 따라) + 살미(바깥으로)
	if fancy and detail >= 1 then
		for _, p in posts do
			local out = Vector3.new(if math.abs(p.X) > W / 2 - 0.01 then math.sign(p.X) else 0, 0, if math.abs(p.Z) > D / 2 - 0.01 then math.sign(p.Z) else 0)
			block(m, "Judu", Vector3.new(1.5, 0.7, 1.5), cf * CFrame.new(p.X, structTop + 0.35, p.Z), P.noerok, Enum.Material.Wood)
			local alongX = math.abs(p.Z) > D / 2 - 0.01
			local arm = if alongX then Vector3.new(3.4, 0.6, 0.7) else Vector3.new(0.7, 0.6, 3.4)
			block(m, "Cheomcha", arm, cf * CFrame.new(p.X, structTop + 0.95, p.Z), P.noerok, Enum.Material.Wood)
			if out.Magnitude > 0 then
				local o2 = out.Unit
				local a = Vector3.new(p.X, structTop + 0.95, p.Z) - o2 * 0.6
				local b = Vector3.new(p.X, structTop + 0.95, p.Z) + o2 * 2.1
				beam(m, "Salmi", cf:PointToWorldSpace(a), cf:PointToWorldSpace(b), 0.6, 0.6, P.yangrok, Enum.Material.Wood)
			end
		end
		-- 포벽: 공포 사이를 막는 벽 (단청 바탕색). 없으면 처마 밑으로 지붕 속이 보인다
		for _, side in { { W, 0, -D / 2 }, { W, 0, D / 2 }, { D, -W / 2, 0 }, { D, W / 2, 0 } } do
			local alongX = side[3] ~= 0
			local size = if alongX then Vector3.new(side[1], 1.3, 0.4) else Vector3.new(0.4, 1.3, side[1])
			block(m, "Pobyeok", size, cf * CFrame.new(side[2], structTop + 0.65, side[3]), P.noerok:Lerp(P.plaster, 0.3), Enum.Material.Plaster)
		end
		structTop += 1.3
	end

	-- 벽과 창호: 칸마다. 앞 가운데 칸은 문, 옆 칸은 창, 나머지는 회벽 (중방 한 줄)
	local wallTop = top - beamH
	local wallH = wallTop - (floorY + 0.3)
	local function bayPanels(axisLen: number, count: number, fixed: number, alongX: boolean, front: boolean)
		for i = 0, count - 1 do
			local c = -axisLen / 2 + (i + 0.5) * bay
			local w = bay - pillarD
			local function at(u: number, y: number, d: number): CFrame
				return if alongX then cf * CFrame.new(c + u, y, fixed + d) else cf * CFrame.new(fixed + d, y, c + u)
			end
			local function size(sx: number, sy: number, sz: number): Vector3
				return if alongX then Vector3.new(sx, sy, sz) else Vector3.new(sz, sy, sx)
			end
			local isDoor = front and (count <= 2 or (i > 0 and i < count - 1))
			if isDoor then
				-- 문 두 짝: 울거미(띠살 문의 테) + 창호지 + 살 두 줄
				local leaf = w / 2
				for _, s in { -1, 1 } do
					local u = s * leaf / 2
					block(m, "Mun", size(leaf + 0.04, wallH, 0.25), at(u, floorY + 0.3 + wallH / 2, 0), P.woodDark, Enum.Material.Wood)
					block(m, "Hanji", size(leaf - 0.55, wallH - 0.9, 0.27), at(u, floorY + 0.3 + wallH / 2 + 0.1, 0), P.hanji, Enum.Material.SmoothPlastic)
					if detail >= 1 then
						for _, du in { -0.3, 0.3 } do
							block(m, "Sal", size(0.1, wallH - 0.9, 0.3), at(u + du * (leaf - 0.55), floorY + 0.3 + wallH / 2 + 0.1, 0), P.woodDark, Enum.Material.Wood)
						end
						block(m, "Sal", size(leaf - 0.55, 0.1, 0.3), at(u, floorY + 0.3 + wallH * 0.62, 0), P.woodDark, Enum.Material.Wood)
					end
				end
			else
				block(m, "Byeok", size(w + 0.02, wallH, 0.5), at(0, floorY + 0.3 + wallH / 2, 0), opts.wallColor or P.plaster, Enum.Material.Plaster)
				block(m, "Jungbang", size(w + 0.04, 0.45, 0.6), at(0, floorY + 0.3 + wallH * 0.42, 0), beamColor, Enum.Material.Wood)
				if front or not alongX then
					-- 창: 벽 위쪽 가운데
					local ww = math.min(2.6, w * 0.55)
					block(m, "Chang", size(ww, 2.2, 0.56), at(0, floorY + 0.3 + wallH * 0.7, 0), P.woodDark, Enum.Material.Wood)
					block(m, "Hanji", size(ww - 0.4, 1.8, 0.58), at(0, floorY + 0.3 + wallH * 0.7, 0), P.hanji, Enum.Material.SmoothPlastic)
				end
			end
		end
	end
	if opts.open then
		-- 정자처럼 벽 없이: 난간만
		Build.railing(m, cf, W, D, floorY + 0.3, pillarD, opts.railColor or pillarColor)
	else
		bayPanels(W, bays[1], -D / 2, true, true)
		bayPanels(W, bays[1], D / 2, true, false)
		bayPanels(D, bays[2], -W / 2, false, false)
		bayPanels(D, bays[2], W / 2, false, false)
	end

	-- 지붕: 처마 끝 높이는 몸채 꼭대기에 맞춘다 (벽선 들임 = eave 에서 밑면이 몸채 위)
	local isGable = (opts.roof or "paljak") == "gable"
	local ex, ez = W / 2 + (if isGable then (opts.gableOver or 1.8) else eave), D / 2 + eave
	local spec = {
		ex = ex,
		ez = ez,
		eave = eave,
		bands = opts.bands or 4,
		kind = opts.roof or "paljak",
		nHip = opts.nHip or 2,
		pitchLow = opts.pitchLow or 17,
		pitchHigh = opts.pitchHigh or 46,
		lift = opts.lift or (if fancy then 1.6 else 1.1),
		flare = opts.flare or 0.6,
		color = opts.roofColor,
		segs = if detail >= 1 then 2 else 1,
		gableX = if isGable then W / 2 + 0.05 else nil,
		gableOver = if isGable then 0 else nil,
	}
	local _, o, h, pitches = profile(spec)
	local underAtWall = h[1] - (spec.t or 0.6) / math.cos(math.rad(pitches[1]))
	local raft = if detail >= 2 then 0.45 else 0
	local eaveY = structTop + raft + 0.05 - underAtWall
	local frame = cf * CFrame.new(0, eaveY, 0)
	local r = roof(m, frame, spec)
	-- 지붕 속 막음 (몸채 꼭대기와 지붕 밑 사이)
	local fillTop = eaveY + underAtWall
	if fillTop > structTop + 0.05 then
		block(m, "Sok", Vector3.new(W - 0.3, fillTop - structTop, D - 0.3), cf * CFrame.new(0, (fillTop + structTop) / 2, 0), P.soffit, Enum.Material.Wood)
	end
	-- 서까래: 처마 띠 밑, 벽선에서 처마 끝 너머까지
	if raft > 0 then
		local sp = opts.rafterSpacing or 1.3
		local slope = math.tan(math.rad(pitches[1]))
		local t = spec.t or 0.6
		local faceList = if spec.kind == "gable" then { { 0, -1, W }, { 0, 1, W } } else { { 0, -1, W }, { 0, 1, W }, { -1, 0, D }, { 1, 0, D } }
		for _, f in faceList do
			local nrm = Vector3.new(f[1], 0, f[2])
			local tg = Vector3.new(f[2], 0, -f[1])
			local halfFace = f[3] / 2
			local hlOuter = (if f[1] == 0 then ex else ez)
			local limit = if spec.kind == "gable" then halfFace - 0.7 else math.min(halfFace - 0.7, hlOuter - r.Lz - 0.3)
			local distWall = if f[1] == 0 then D / 2 else W / 2
			local count = math.floor(limit * 2 / sp)
			for i = 0, count do
				local x = -limit + i * (2 * limit / math.max(count, 1))
				local y0 = eaveY + h[1] - t / math.cos(math.rad(pitches[1])) - raft / 2 - 0.02
				local a = nrm * (distWall - 0.2) + tg * x + Vector3.new(0, y0, 0)
				local b = nrm * (distWall + eave + 0.25) + tg * x + Vector3.new(0, y0 - (eave + 0.45) * slope, 0)
				local p = cyl(m, "Seokkarae", cf:PointToWorldSpace(a), cf:PointToWorldSpace(b), raft, if fancy then P.noerok else P.wood, Enum.Material.Wood)
				p.CastShadow = false
			end
		end
	end
	return m, { roof = r, width = W, depth = D, eaveY = eaveY, top = eaveY + r.height }
end

-- 난간: 바닥 둘레 (앞 가운데는 비운다)
function Build.railing(parent: Instance, cf: CFrame, W: number, D: number, y: number, inset: number, color: Color3)
	local h = 2.2
	local gap = 4
	for _, side in { { -D / 2, true }, { D / 2, true }, { -W / 2, false }, { W / 2, false } } do
		local len = if side[2] then W else D
		local fixed = side[1]
		local function pos(u: number, yy: number): Vector3
			return if side[2] then cf:PointToWorldSpace(Vector3.new(u, yy, fixed)) else cf:PointToWorldSpace(Vector3.new(fixed, yy, u))
		end
		local segs = { { -len / 2 + inset / 2, len / 2 - inset / 2 } }
		if side[2] and fixed < 0 then
			segs = { { -len / 2 + inset / 2, -gap / 2 }, { gap / 2, len / 2 - inset / 2 } }
		end
		for _, s in segs do
			beam(parent, "Nangan", pos(s[1], y + h), pos(s[2], y + h), 0.35, 0.3, color, Enum.Material.Wood)
			beam(parent, "Nangan", pos(s[1], y + 0.6), pos(s[2], y + 0.6), 0.3, 0.25, color, Enum.Material.Wood)
			local n = math.max(1, math.floor((s[2] - s[1]) / 1.6))
			for i = 1, n - 1 do
				local u = s[1] + (s[2] - s[1]) * i / n
				beam(parent, "Dongja", pos(u, y + 0.6), pos(u, y + h), 0.22, 0.22, color, Enum.Material.Wood)
			end
		end
	end
end

-- 정자 (모정): 높은 마루, 벽 없이 난간, 사모(4)·육모(6)·팔모(8) 모임지붕은 polyRoof, 네모는 팔작
function Build.pavilion(parent: Instance, cf: CFrame, opts)
	opts = opts or {}
	opts.open = true
	opts.style = opts.style or "temple"
	opts.plinth = opts.plinth or 2.4
	opts.bays = opts.bays or { 1, 1 }
	opts.bay = opts.bay or 9
	opts.pillarH = opts.pillarH or 8
	opts.roof = opts.roof or "hip" -- 정사각 우진각 = 사모지붕 (꼭대기 절병통)
	opts.eave = opts.eave or 3.6
	opts.lift = opts.lift or 1.8
	opts.name = opts.name or "정자"
	return Build.house(parent, cf, opts)
end

-- 탑: 목탑처럼 층마다 몸채와 처마. floors 층, 아래층 칸 너비 base, 위로 갈수록 줄인다
function Build.pagoda(parent: Instance, cf: CFrame, opts)
	opts = opts or {}
	local floors = opts.floors or 5
	local base = opts.base or 12
	local m = Instance.new("Model")
	m.Name = opts.name or "목탑"
	m.Parent = parent
	local y = 0
	local plinth = 1.8
	block(m, "Gidan", Vector3.new(base + 6, plinth, base + 6), cf * CFrame.new(0, plinth / 2 - 0.4, 0), P.granite, Enum.Material.Granite)
	y = plinth - 0.4
	for i = 1, floors do
		local s = base * (1 - 0.13 * (i - 1))
		local hgt = if i == 1 then 7.5 else 4.6
		local body = Instance.new("Model")
		body.Name = i .. "층"
		body.Parent = m
		local floorCf = cf * CFrame.new(0, y, 0)
		-- 몸채: 기둥 네 귀 + 회벽 + 창방
		block(body, "Byeok", Vector3.new(s - 0.6, hgt, s - 0.6), floorCf * CFrame.new(0, hgt / 2, 0), P.plaster, Enum.Material.Plaster)
		for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
			cyl(body, "Gidung", floorCf:PointToWorldSpace(Vector3.new(c[1] * s / 2, 0, c[2] * s / 2)), floorCf:PointToWorldSpace(Vector3.new(c[1] * s / 2, hgt, c[2] * s / 2)), 0.9, P.seokganju, Enum.Material.Wood)
		end
		block(body, "Changbang", Vector3.new(s + 0.9, 0.9, s + 0.9), floorCf * CFrame.new(0, hgt - 0.45, 0), P.noerok, Enum.Material.Wood)
		if i == 1 then
			block(body, "Mun", Vector3.new(3, 5, 0.3), floorCf * CFrame.new(0, 2.5, -(s - 0.6) / 2 - 0.1), P.seokganju, Enum.Material.Wood)
		end
		local eave = 3 - 0.2 * (i - 1)
		local spec = { ex = s / 2 + eave, ez = s / 2 + eave, eave = eave, bands = 2, kind = "hip", pitchLow = 16, pitchHigh = 34, lift = 1.2, flare = 0.4, segs = 2, t = 0.5 }
		local _, o, hh, pitches = profile(spec)
		local under = hh[1] - 0.5 / math.cos(math.rad(pitches[1]))
		local eaveY = y + hgt + 0.05 - under
		local r = nil
		if i < floors then
			-- 위층 몸채가 지붕을 뚫고 올라가므로, 지붕은 위층 몸채 바깥만 덮으면 된다 (그 안쪽 띠는 짓지 않는다)
			local nextS = base * (1 - 0.13 * i)
			spec.stopInset = spec.ex - (nextS - 0.6) / 2 + 0.2
			r = roof(body, cf * CFrame.new(0, eaveY, 0), spec)
			y = eaveY + hh[1] + 0.2 -- 다음 층은 처마 띠 안쪽 높이에서
		else
			spec.bands = 3
			spec.pitchHigh = 44
			r = roof(body, cf * CFrame.new(0, eaveY, 0), spec)
			-- 상륜: 노반, 복발, 보륜 다섯, 보주
			local tip = eaveY + r.height + 0.8
			local ring = Vector3.new(0, tip, 0)
			block(m, "Noban", Vector3.new(1.8, 0.8, 1.8), cf * CFrame.new(0, tip + 0.4, 0), P.hwang, Enum.Material.Metal)
			for k = 1, 5 do
				cyl(m, "Boryun", cf:PointToWorldSpace(ring + Vector3.new(0, 0.8 + k * 0.9, 0)), cf:PointToWorldSpace(ring + Vector3.new(0, 1.1 + k * 0.9, 0)), 1.6 - k * 0.12, P.hwang, Enum.Material.Metal)
			end
			cyl(m, "Chalju", cf:PointToWorldSpace(ring), cf:PointToWorldSpace(ring + Vector3.new(0, 7, 0)), 0.3, P.hwang, Enum.Material.Metal)
			ball(m, "Boju", cf:PointToWorldSpace(ring + Vector3.new(0, 7.2, 0)), 0.9, P.hwang, Enum.Material.Metal)
		end
	end
	return m
end

-- 나무 -----------------------------------------------------------------------------------
--
-- 잎 덩이는 기울인 블록 여러 개 (공은 매끈한 장난감처럼 보여서). 덩이마다 잎색 셋 가운데 하나, 아래 덩이는 어둡게.
-- 잎은 LeafyGrass 재질 (부품에도 된다): 잎 무늬와 거친 반사가 SmoothPlastic 보다 훨씬 낫다.
-- 잎은 deco: 부딪히지 않고 레이에도 안 잡힌다 (영초가 나무 위에 돋지 않게, 카메라가 잎에 걸리지 않게).
-- rng(min, max) 는 World 의 makeRng.

local function blob(parent: Instance, center: Vector3, size: Vector3, rng, color: Color3)
	local cf = CFrame.new(center) * CFrame.Angles(rng(-0.35, 0.35), rng(0, math.pi), rng(-0.35, 0.35))
	return deco(block(parent, "Leaves", size, cf, color, Enum.Material.LeafyGrass))
end

local function jitter(color: Color3, rng, amount: number): Color3
	local k = 1 + rng(-amount, amount)
	return Color3.new(math.clamp(color.R * k, 0, 1), math.clamp(color.G * k, 0, 1), math.clamp(color.B * k, 0, 1))
end

-- 굽은 줄기: base 에서 위로 segs 마디, 마디마다 기울기를 바꾼다. 끝점과 방향을 돌려준다
local function trunk(parent: Instance, base: Vector3, height: number, w0: number, w1: number, lean: Vector3, segs: number, color: Color3, rng)
	local p = base - Vector3.new(0, 0.6, 0)
	local dir = (Vector3.yAxis + lean).Unit
	local points = { p }
	for i = 1, segs do
		local len = height / segs + (if i == 1 then 0.6 else 0)
		local q = p + dir * len
		local w = w0 + (w1 - w0) * (i - 1) / math.max(segs - 1, 1)
		beam(parent, "Trunk", p, q + dir * (w * 0.35), w, w, color, Enum.Material.Wood)
		p = q
		dir = (dir + Vector3.new(rng(-0.18, 0.18), 0, rng(-0.18, 0.18))).Unit
		table.insert(points, p)
	end
	return p, dir, points
end

-- 둥근 잎 덩어리: 타원체 겉에 고르게(피보나치) 작은 덩이 count 개 + 속 덩이 하나.
-- 위쪽 덩이는 밝은 잎, 아래는 어두운 잎 (햇빛 받는 쪽처럼). 실루엣이 둥글게 울퉁불퉁해진다
local function canopy(parent: Instance, center: Vector3, rx: number, ry: number, count: number, rng, palette, sizeK: number?)
	blob(parent, center, Vector3.new(rx * 1.35, ry * 1.15, rx * 1.35), rng, jitter(palette[1], rng, 0.04))
	for i = 1, count do
		local t = (i - 0.5) / count
		local y = 1 - t * 1.45
		local r = math.sqrt(math.max(0, 1 - y * y))
		local a = i * 2.39996 + rng(-0.3, 0.3)
		local p = center + Vector3.new(math.cos(a) * r * rx * 0.72, y * ry * 0.62, math.sin(a) * r * rx * 0.72)
		local s = rx * (sizeK or 0.78) * rng(0.8, 1.1)
		local shade = if y > 0.35 then palette[#palette] elseif y < -0.15 then palette[1] else palette[math.min(2, #palette)]
		blob(parent, p, Vector3.new(s, s * 0.78, s), rng, jitter(shade, rng, 0.06))
	end
end
Build.canopy = canopy

-- 활엽수 (느티·참나무 같은 둥근 나무). opts.height 대략 높이, opts.leaves 잎색 셋 (어두운→밝은)
function Build.broadleaf(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = opts.name or "나무"
	m.Parent = parent
	local height = opts.height or rng(10, 15)
	local tw = height * 0.11
	local bark = opts.bark or P.bark
	local lean = Vector3.new(rng(-0.12, 0.12), 0, rng(-0.12, 0.12))
	local top, _, pts = trunk(m, base, height * 0.55, tw, tw * 0.72, lean, 2, bark, rng)
	local palette = opts.leaves or { P.leafDeep, P.leaf, P.leafLight }
	local rx = height * 0.36
	local center = top + Vector3.new(0, height * 0.16, 0)
	-- 굵은 가지 셋: 줄기 위쪽에서 비스듬히 위로, 잎덩어리 속으로
	local a0 = rng(0, math.pi * 2)
	for i = 1, opts.branches or 3 do
		local a = a0 + i * (math.pi * 2 / 3) + rng(-0.4, 0.4)
		local from = pts[2]:Lerp(top, rng(0.2, 0.7))
		local to = center + Vector3.new(math.cos(a) * rx * 0.6, rng(-0.5, 0.8), math.sin(a) * rx * 0.6)
		beam(m, "Branch", from, to, tw * 0.42, tw * 0.42, bark, Enum.Material.Wood)
	end
	canopy(m, center, rx, height * 0.3, opts.blobs or 8, rng, palette)
	return m
end

-- 벚나무·매화: 둥근 나무 모양에 꽃색, 줄기는 검붉게, 조금 낮고 넓게
function Build.blossom(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	opts.name = opts.name or "벚나무"
	opts.bark = Color3.fromRGB(70, 50, 44)
	opts.leaves = { P.blossomDeep, P.blossom, P.blossomWhite }
	opts.height = opts.height or rng(8, 11)
	return Build.broadleaf(parent, base, rng, opts)
end

-- 소나무 (적송): 비스듬히 굽은 붉은 줄기, 위로 갈수록 짧아지는 가지 끝에 납작한 구름 잎판 (판 하나 = 납작 덩이 둘셋)
local function pad(parent: Instance, p: Vector3, s: number, rng)
	blob(parent, p, Vector3.new(s, s * 0.24, s * 0.82), rng, jitter(P.pine, rng, 0.06))
	blob(parent, p + Vector3.new(rng(-0.3, 0.3) * s, s * 0.14, rng(-0.3, 0.3) * s), Vector3.new(s * 0.72, s * 0.2, s * 0.6), rng, jitter(P.pineLight, rng, 0.06))
end
function Build.pine(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = opts.name or "소나무"
	m.Parent = parent
	local height = opts.height or rng(13, 19)
	local tw = height * 0.085
	local lean = Vector3.new(rng(-0.4, 0.4), 0, rng(-0.4, 0.4))
	local top, _, pts = trunk(m, base, height, tw, tw * 0.62, lean, 3, P.barkPine, rng)
	beam(m, "Bark", pts[1], pts[2], tw * 1.06, tw * 1.06, P.bark, Enum.Material.Wood)
	local tiers = opts.tiers or 5
	local a = rng(0, math.pi * 2)
	for i = 1, tiers do
		local t = 0.42 + 0.58 * (i - 1) / (tiers - 1)
		local u = math.clamp(t * 3, 0, 2.999)
		local seg = math.floor(u) + 1
		local from = pts[seg]:Lerp(pts[seg + 1], u - math.floor(u))
		a += 2.4 + rng(-0.4, 0.4)
		local reach = height * (0.34 - 0.22 * t) * rng(0.85, 1.15)
		local to = from + Vector3.new(math.cos(a) * reach, rng(-0.2, 0.9), math.sin(a) * reach)
		if i < tiers then
			beam(m, "Branch", from, to, tw * 0.42, tw * 0.42, P.barkPine, Enum.Material.Wood)
		else
			to = top
		end
		local s = height * (0.42 - 0.16 * t) * rng(0.9, 1.15)
		pad(m, to + Vector3.new(0, 0.35, 0), s, rng)
	end
	return m
end

-- 전나무 (산·설원): 사각뿔 넷을 겹친다 (뿔 하나 = 귀쐐기 넷)
-- center 는 밑면 가운데. 귀쐐기 꼭짓점(+X,+Y,-Z 모서리)이 뿔 가운데 위로 오게 사분면마다 하나
local function pyramid(parent: Instance, name: string, center: Vector3, size: number, height: number, yaw: number, color: Color3, material, isDeco: boolean?)
	local q = size / 2
	for k = 0, 3 do
		local a = yaw + k * math.pi / 2
		local cf = CFrame.new(center) * CFrame.Angles(0, a, 0) * CFrame.new(-q / 2, height / 2, q / 2)
		local p = Build.cornerWedge(parent, name, Vector3.new(q, height, q), cf, color, material or Enum.Material.LeafyGrass)
		if isDeco then
			deco(p)
		end
	end
end
Build.pyramid = pyramid

function Build.fir(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = opts.name or "전나무"
	m.Parent = parent
	local height = opts.height or rng(14, 22)
	local tw = height * 0.06
	beam(m, "Trunk", base - Vector3.new(0, 0.6, 0), base + Vector3.new(0, height * 0.5, 0), tw, tw, P.bark, Enum.Material.Wood)
	local tiers = opts.tiers or 4
	local yaw = rng(0, math.pi / 2)
	for i = 1, tiers do
		local t = (i - 1) / tiers
		local w = height * (0.52 - 0.36 * t)
		local h = height * 0.34
		local y = height * (0.16 + 0.68 * t)
		local color = if opts.snow and i == tiers then Color3.fromRGB(226, 232, 238) else jitter(if i % 2 == 0 then P.pine else P.pineLight, rng, 0.05)
		pyramid(m, "Needles", base + Vector3.new(0, y, 0), w, h, yaw + i * 0.4, color, nil, true)
	end
	return m
end

-- 버드나무: 둥근 머리 + 머리 가장자리에서 늘어진 가는 가지 (가는 판을 둘레 두 겹으로 드리운다)
function Build.willow(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = opts.name or "버드나무"
	m.Parent = parent
	local height = opts.height or rng(10, 13)
	local tw = height * 0.12
	local top = trunk(m, base, height * 0.62, tw, tw * 0.7, Vector3.new(rng(-0.2, 0.2), 0, rng(-0.2, 0.2)), 2, P.bark, rng)
	local rx = height * 0.34
	local center = top + Vector3.new(0, height * 0.1, 0)
	canopy(m, center, rx, height * 0.22, opts.blobs or 6, rng, { P.leaf, P.willow, P.leafYellow }, 0.7)
	local strands = opts.strands or 22
	for i = 1, strands do
		local a = (i / strands) * math.pi * 2 + rng(-0.12, 0.12)
		local ring = if i % 2 == 0 then 0.95 else 0.7
		local rr = rx * ring * rng(0.9, 1.05)
		local len = height * rng(0.55, 0.75) * (if ring < 0.8 then 0.8 else 1)
		local hang = center + Vector3.new(math.cos(a) * rr, -height * 0.05, math.sin(a) * rr)
		local p = hang - Vector3.new(0, len / 2, 0)
		-- 바깥으로 조금 벌어지게 (윗동이 안쪽)
		local cf = face(p, p + Vector3.new(math.cos(a), 0, math.sin(a))) * CFrame.Angles(math.rad(rng(-8, -2)), 0, 0)
		local strand = deco(block(m, "Strand", Vector3.new(rng(0.35, 0.65), len, 0.18), cf, jitter(P.willow, rng, 0.1), Enum.Material.LeafyGrass))
		strand.CastShadow = false
	end
	return m
end

-- 대숲: 가는 대 여럿 (둥근 기둥), 위쪽에 잎 판 몇 장
function Build.bamboo(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = opts.name or "대숲"
	m.Parent = parent
	local count = opts.count or 9
	local radius = opts.radius or 3
	for _ = 1, count do
		local a, r = rng(0, math.pi * 2), radius * math.sqrt(rng(0, 1))
		local foot = base + Vector3.new(math.cos(a) * r, -0.5, math.sin(a) * r)
		local height = rng(14, 22)
		local tilt = Vector3.new(rng(-0.08, 0.08), 1, rng(-0.08, 0.08)).Unit
		local tip = foot + tilt * height
		local d = rng(0.32, 0.5)
		cyl(m, "Dae", foot, tip, d, if rng(0, 1) > 0.7 then P.bambooOld else P.bamboo, Enum.Material.SmoothPlastic)
		-- 마디 두 개 (조금 굵은 고리)
		for _, f in { 0.3, 0.55 } do
			local c = foot:Lerp(tip, f)
			deco(cyl(m, "Madi", c - tilt * 0.06, c + tilt * 0.06, d * 1.18, P.bambooOld, Enum.Material.SmoothPlastic))
		end
		-- 잎: 위쪽 1/3 에 기울인 잎 판 2~3
		for _ = 1, 2 + math.floor(rng(0, 1.99)) do
			local c = foot:Lerp(tip, rng(0.68, 0.98))
			local la = rng(0, math.pi * 2)
			local out = Vector3.new(math.cos(la), 0, math.sin(la))
			local cf = face(c + out * 1.2, c + out * 3) * CFrame.Angles(math.rad(rng(15, 35)), 0, math.rad(rng(-20, 20)))
			deco(block(m, "Ip", Vector3.new(rng(1.4, 2.2), 0.15, rng(2.6, 3.6)), cf, jitter(P.bambooLeaf, rng, 0.08), Enum.Material.LeafyGrass)).CastShadow = false
		end
	end
	return m
end

-- 덤불: 낮은 덩이 둘셋
function Build.shrub(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "덤불"
	m.Parent = parent
	local s = opts.size or rng(2.5, 4.5)
	local colors = opts.leaves or { P.leafDeep, P.leaf, P.leafLight }
	for i = 1, opts.blobs or 3 do
		local a = rng(0, math.pi * 2)
		local r = s * 0.35 * (i - 1)
		local ss = s * rng(0.7, 1)
		blob(m, base + Vector3.new(math.cos(a) * r, ss * 0.28, math.sin(a) * r), Vector3.new(ss, ss * 0.65, ss), rng, jitter(colors[1 + (i - 1) % #colors], rng, 0.07))
	end
	if opts.flowers then
		for _ = 1, 5 do
			local a, r = rng(0, math.pi * 2), rng(0, s * 0.5)
			local p = base + Vector3.new(math.cos(a) * r, s * 0.55 + rng(0, 0.3), math.sin(a) * r)
			deco(block(m, "Kkot", Vector3.new(0.45, 0.3, 0.45), CFrame.new(p) * CFrame.Angles(0, rng(0, 3), 0), opts.flowers, Enum.Material.SmoothPlastic))
		end
	end
	return m
end

-- 갈대: 물가에 가는 줄기 여럿과 이삭
function Build.reeds(parent: Instance, base: Vector3, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "갈대"
	m.Parent = parent
	for _ = 1, opts.count or 8 do
		local a, r = rng(0, math.pi * 2), rng(0, opts.radius or 1.6)
		local foot = base + Vector3.new(math.cos(a) * r, -0.3, math.sin(a) * r)
		local h = rng(3, 5)
		local dir = Vector3.new(rng(-0.25, 0.25), 1, rng(-0.25, 0.25)).Unit
		deco(beam(m, "Julgi", foot, foot + dir * h, 0.12, 0.12, Color3.fromRGB(136, 140, 86), Enum.Material.Grass))
		deco(beam(m, "Isak", foot + dir * (h - 0.2), foot + dir * (h + 0.9), 0.3, 0.3, Color3.fromRGB(196, 178, 132), Enum.Material.Fabric))
	end
	return m
end

-- 바위 무더기: 큰 돌 하나 + 작은 돌 몇, 모두 세 축으로 돌려 반쯤 묻는다. 큰 돌 윗면에 이끼 판
function Build.rocks(parent: Instance, base: Vector3, size: number, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "바위"
	m.Parent = parent
	local color = opts.color or Color3.fromRGB(122, 118, 112)
	local mat = opts.material or Enum.Material.Slate
	local main = block(m, "Rock", Vector3.new(size, size * rng(0.55, 0.8), size * rng(0.7, 1)), CFrame.new(base + Vector3.new(0, size * 0.18, 0)) * CFrame.Angles(rng(-0.25, 0.25), rng(0, math.pi), rng(-0.25, 0.25)), jitter(color, rng, 0.06), mat)
	-- 모서리를 깎은 듯이: 큰 돌 위에 기울인 쐐기
	block(m, "Rock", Vector3.new(size * 0.8, size * 0.5, size * 0.7), main.CFrame * CFrame.new(size * 0.1, size * 0.28, 0) * CFrame.Angles(rng(-0.5, 0.5), rng(0, 1), rng(0.3, 0.6)), jitter(color, rng, 0.08), mat)
	for _ = 1, opts.count or 3 do
		local a = rng(0, math.pi * 2)
		local s = size * rng(0.25, 0.5)
		local p = base + Vector3.new(math.cos(a) * size * 0.6, s * 0.15, math.sin(a) * size * 0.6)
		block(m, "Rock", Vector3.new(s, s * rng(0.5, 0.8), s * rng(0.7, 1.1)), CFrame.new(p) * CFrame.Angles(rng(-0.5, 0.5), rng(0, 6), rng(-0.5, 0.5)), jitter(color, rng, 0.1), mat)
	end
	if opts.moss ~= false then
		local top = main.CFrame * CFrame.new(0, main.Size.Y / 2 + 0.05, 0)
		deco(block(m, "Moss", Vector3.new(main.Size.X * 0.7, 0.25, main.Size.Z * 0.6), top * CFrame.Angles(0, rng(0, 1), 0), jitter(Color3.fromRGB(84, 112, 62), rng, 0.06), Enum.Material.LeafyGrass))
	end
	return m
end

-- 마을 살림 ---------------------------------------------------------------------------------

-- 돌담 (기와 얹은): a 에서 b 까지
function Build.stoneWall(parent: Instance, a: Vector3, b: Vector3, opts)
	opts = opts or {}
	local h = opts.height or 3.4
	local w = opts.width or 1.6
	local m = Instance.new("Model")
	m.Name = "돌담"
	m.Parent = parent
	local lookCf = face((a + b) / 2, b)
	local len = (b - a).Magnitude
	block(m, "Dam", Vector3.new(w, h, len), lookCf * CFrame.new(0, h / 2 - 0.3, 0), Color3.fromRGB(150, 140, 124), Enum.Material.Cobblestone)
	-- 맞배 기와 갓: 쐐기 둘 (길이 방향이 Z 라서 옆으로 눕힌다)
	local capW = w / 2 + 0.45
	for _, s in { 1, -1 } do
		wedge(m, "Gat", Vector3.new(len + 0.4, 0.7, capW), lookCf * CFrame.new(s * capW / 2, h - 0.3 + 0.35, 0) * CFrame.Angles(0, s * math.rad(90), 0), P.giwa, Enum.Material.ClayRoofTiles)
	end
	block(m, "Maru", Vector3.new(0.5, 0.35, len + 0.5), lookCf * CFrame.new(0, h + 0.55, 0), P.giwaDark, Enum.Material.Slate)
	return m
end

-- 싸리 울타리: 말뚝과 가로대 둘
function Build.fence(parent: Instance, points: { Vector3 }, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "울타리"
	m.Parent = parent
	local color = opts.color or Color3.fromRGB(150, 120, 84)
	for i = 1, #points - 1 do
		local a, b = points[i], points[i + 1]
		local n = math.max(1, math.floor((b - a).Magnitude / 2.5))
		for k = 0, n do
			if k < n or i == #points - 1 then
				local p = a:Lerp(b, k / n)
				beam(m, "Malttuk", p - Vector3.new(0, 0.5, 0), p + Vector3.new(0, 3.2, 0), 0.32, 0.32, color, Enum.Material.Wood)
			end
		end
		for _, y in { 1.1, 2.5 } do
			beam(m, "Garodae", a + Vector3.new(0, y, 0), b + Vector3.new(0, y, 0), 0.18, 0.22, color, Enum.Material.Wood)
		end
	end
	return m
end

-- 우물: 돌 테 + 물 + 두레박 틀 (맞배 지붕)
function Build.well(parent: Instance, ground: Vector3, opts)
	local m = Instance.new("Model")
	m.Name = "우물"
	m.Parent = parent
	local r = 2.2
	for k = 0, 9 do
		local a = k * math.pi * 2 / 10
		local p = ground + Vector3.new(math.cos(a) * r, 0.9, math.sin(a) * r)
		block(m, "Dol", Vector3.new(1.5, 1.8, 1.0), face(p, ground + Vector3.new(0, 0.9, 0)) * CFrame.Angles(0, 0, 0), P.granite:Lerp(P.graniteDark, (k % 3) / 3), Enum.Material.Granite)
	end
	local water = block(m, "Mul", Vector3.new(0.2, 3.2, 3.2), CFrame.new(ground + Vector3.new(0, 0.6, 0)) * CFrame.Angles(0, 0, math.rad(90)), Color3.fromRGB(34, 70, 84), Enum.Material.Glass)
	water.Shape = Enum.PartType.Cylinder
	water.Transparency = 0.2
	for _, s in { 1, -1 } do
		beam(m, "Gidung", ground + Vector3.new(s * 2.6, 0, 0), ground + Vector3.new(s * 2.6, 6, 0), 0.5, 0.5, P.woodDark, Enum.Material.Wood)
	end
	cyl(m, "Gulim", ground + Vector3.new(-2.6, 4.8, 0), ground + Vector3.new(2.6, 4.8, 0), 0.5, P.wood, Enum.Material.Wood)
	beam(m, "Jul", ground + Vector3.new(0.4, 4.8, 0), ground + Vector3.new(0.4, 2.4, 0), 0.08, 0.08, Color3.fromRGB(190, 170, 130), Enum.Material.Fabric)
	cyl(m, "Durebak", ground + Vector3.new(0.4, 1.9, 0), ground + Vector3.new(0.4, 2.5, 0), 0.8, P.woodDark, Enum.Material.Wood)
	for _, s in { 1, -1 } do
		wedge(m, "Jibung", Vector3.new(6.4, 1, 1.8), CFrame.new(ground + Vector3.new(0, 6.5, s * 0.9)) * CFrame.Angles(0, if s > 0 then math.pi else 0, 0), P.giwa, Enum.Material.ClayRoofTiles)
	end
	return m
end

-- 수레: 짐칸, 바퀴 둘, 끌채 둘 (끌채 끝이 땅에 닿게 기운다)
function Build.cart(parent: Instance, cf: CFrame)
	local m = Instance.new("Model")
	m.Name = "수레"
	m.Parent = parent
	local R = 1.7
	block(m, "Jimkan", Vector3.new(3.6, 0.4, 5), cf * CFrame.new(0, R + 0.2, 0), P.wood, Enum.Material.WoodPlanks)
	for _, s in { 1, -1 } do
		block(m, "Yeop", Vector3.new(0.2, 1, 5), cf * CFrame.new(s * 1.7, R + 0.9, 0), P.woodDark, Enum.Material.WoodPlanks)
		local hub = cf:PointToWorldSpace(Vector3.new(s * 2.1, R, 0.4))
		cyl(m, "Bakwi", hub - cf.RightVector * 0.15, hub + cf.RightVector * 0.15, R * 2, P.woodDark, Enum.Material.Wood)
		cyl(m, "Tong", hub - cf.RightVector * 0.3, hub + cf.RightVector * 0.3, 0.7, P.meok, Enum.Material.Metal)
		beam(m, "Kkeulchae", cf:PointToWorldSpace(Vector3.new(s * 1.2, R + 0.05, -2)), cf:PointToWorldSpace(Vector3.new(s * 1.0, 0.25, -6.5)), 0.3, 0.3, P.wood, Enum.Material.Wood)
	end
	cyl(m, "Gulttae", cf:PointToWorldSpace(Vector3.new(-2.1, R, 0.4)), cf:PointToWorldSpace(Vector3.new(2.1, R, 0.4)), 0.35, P.meok, Enum.Material.Metal)
	return m
end

-- 장독대: 돌 단 위 옹기 (공 + 목 + 뚜껑)
function Build.jars(parent: Instance, cf: CFrame, rng, count: number?)
	local m = Instance.new("Model")
	m.Name = "장독대"
	m.Parent = parent
	local n = count or 6
	local cols = math.ceil(n / 2)
	block(m, "Dan", Vector3.new(cols * 2.6 + 0.8, 0.8, 6), cf * CFrame.new(0, 0.2, 0), P.granite, Enum.Material.Cobblestone)
	for i = 0, n - 1 do
		local row, col = i % 2, i // 2
		local d = rng(1.8, 2.5) * (if row == 1 then 0.85 else 1)
		local p = cf:PointToWorldSpace(Vector3.new(-cols * 1.3 + 1.3 + col * 2.6, 0.6 + d / 2 - 0.15, row * 2.6 - 1.3))
		local jar = ball(m, "Ongi", p, d, jitter(Color3.fromRGB(86, 54, 36), rng, 0.08), Enum.Material.SmoothPlastic)
		jar.Reflectance = 0.06
		cyl(m, "Mok", p + Vector3.new(0, d * 0.38, 0), p + Vector3.new(0, d * 0.5, 0), d * 0.6, jar.Color, Enum.Material.SmoothPlastic)
		cyl(m, "Ttukkeong", p + Vector3.new(0, d * 0.5, 0), p + Vector3.new(0, d * 0.56, 0), d * 0.68, Color3.fromRGB(66, 44, 32), Enum.Material.SmoothPlastic)
	end
	return m
end

-- 깃발: 장대 + 늘어진 기 (두 폭)
function Build.banner(parent: Instance, ground: Vector3, toward: Vector3, color: Color3, height: number?)
	local m = Instance.new("Model")
	m.Name = "깃발"
	m.Parent = parent
	local h = height or 10
	local look = face(ground, toward)
	cyl(m, "Jangdae", ground - Vector3.new(0, 0.6, 0), ground + Vector3.new(0, h, 0), 0.35, P.woodDark, Enum.Material.Wood)
	ball(m, "Kkokji", ground + Vector3.new(0, h + 0.25, 0), 0.6, P.hwang, Enum.Material.Metal)
	beam(m, "Gaji", (look * CFrame.new(0, h - 0.4, 0)).Position, (look * CFrame.new(2.8, h - 0.4, 0)).Position, 0.18, 0.18, P.woodDark, Enum.Material.Wood)
	block(m, "Gi", Vector3.new(2.5, 5.2, 0.08), look * CFrame.new(1.45, h - 3.1, 0), color, Enum.Material.Fabric)
	block(m, "Dan", Vector3.new(2.5, 0.35, 0.1), look * CFrame.new(1.45, h - 5.6, 0), P.hwang, Enum.Material.Fabric)
	return m
end

-- 청사초롱: 기둥에 팔을 내고 붉은 위·푸른 아래 등을 매단다
function Build.chorong(parent: Instance, ground: Vector3, toward: Vector3)
	local m = Instance.new("Model")
	m.Name = "청사초롱"
	m.Parent = parent
	local look = face(ground, toward)
	beam(m, "Gidung", ground - Vector3.new(0, 0.5, 0), ground + Vector3.new(0, 8, 0), 0.6, 0.6, P.woodDark, Enum.Material.Wood)
	beam(m, "Pal", (look * CFrame.new(0, 7.6, 0)).Position, (look * CFrame.new(0, 7.6, -2.6)).Position, 0.3, 0.3, P.woodDark, Enum.Material.Wood)
	local c = (look * CFrame.new(0, 5.6, -2.3)).Position
	deco(beam(m, "Kkeun", c + Vector3.new(0, 2, 0), c + Vector3.new(0, 1.05, 0), 0.06, 0.06, P.meok, Enum.Material.Fabric))
	cyl(m, "Ttukkeong", c + Vector3.new(0, 0.85, 0), c + Vector3.new(0, 1.05, 0), 1.4, P.meok, Enum.Material.Metal)
	local red = cyl(m, "Wit", c, c + Vector3.new(0, 0.85, 0), 1.25, Color3.fromRGB(214, 70, 58), Enum.Material.Neon)
	cyl(m, "Arae", c - Vector3.new(0, 0.85, 0), c, 1.25, Color3.fromRGB(62, 92, 170), Enum.Material.Neon)
	cyl(m, "Badak", c - Vector3.new(0, 1.05, 0), c - Vector3.new(0, 0.85, 0), 1.4, P.meok, Enum.Material.Metal)
	deco(beam(m, "Sul", c - Vector3.new(0, 1.05, 0), c - Vector3.new(0, 2.1, 0), 0.25, 0.25, P.juhong, Enum.Material.Fabric))
	local l = Instance.new("PointLight")
	l.Color = Color3.fromRGB(255, 176, 130)
	l.Range = 18
	l.Brightness = 1.6
	l.Shadows = false
	l.Parent = red
	return m
end

-- 석등: 하대석, 간주석, 화사석(불빛), 옥개석(사모 지붕), 보주
function Build.stoneLantern(parent: Instance, ground: Vector3)
	local m = Instance.new("Model")
	m.Name = "석등"
	m.Parent = parent
	local g = P.granite
	block(m, "Hadae", Vector3.new(2.6, 0.9, 2.6), CFrame.new(ground + Vector3.new(0, 0.3, 0)) * CFrame.Angles(0, math.rad(45), 0), g, Enum.Material.Granite)
	cyl(m, "Ganju", ground + Vector3.new(0, 0.7, 0), ground + Vector3.new(0, 4, 0), 0.9, g, Enum.Material.Granite)
	block(m, "Sangdae", Vector3.new(2.2, 0.5, 2.2), CFrame.new(ground + Vector3.new(0, 4.2, 0)), g, Enum.Material.Granite)
	local fire = block(m, "Bul", Vector3.new(1.1, 1.3, 1.1), CFrame.new(ground + Vector3.new(0, 5.1, 0)), Color3.fromRGB(255, 196, 120), Enum.Material.Neon)
	for _, c in { { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } } do
		block(m, "Hwasa", Vector3.new(0.45, 1.4, 0.45), CFrame.new(ground + Vector3.new(c[1] * 0.75, 5.15, c[2] * 0.75)), g, Enum.Material.Granite)
	end
	pyramid(m, "Okgae", ground + Vector3.new(0, 5.8, 0), 3.2, 1.1, 0, P.graniteDark, Enum.Material.Granite)
	ball(m, "Boju", ground + Vector3.new(0, 7, 0), 0.7, g, Enum.Material.Granite)
	local l = Instance.new("PointLight")
	l.Color = Color3.fromRGB(255, 190, 120)
	l.Range = 16
	l.Brightness = 1.4
	l.Parent = fire
	return m
end

-- 성벽: a→b, 몸 + 여장(타구) + 여장 갓. 밖(앞)이 face 의 -X 쪽이 되도록 outward 를 준다
function Build.cityWall(parent: Instance, a: Vector3, b: Vector3, opts)
	opts = opts or {}
	local H = opts.height or 14
	local T = opts.thick or 5
	local color = opts.color or Color3.fromRGB(176, 168, 150)
	local mat = opts.material or Enum.Material.Cobblestone
	local m = Instance.new("Model")
	m.Name = "성벽"
	m.Parent = parent
	local len = (b - a).Magnitude
	local cf = face((a + b) / 2, b) -- 길이 방향이 -Z(앞), 바깥이 +X
	-- 밑이 조금 넓은 몸 (두 단)
	block(m, "Mom", Vector3.new(T + 1, H * 0.45, len), cf * CFrame.new(0, H * 0.225 - 1, 0), color, mat)
	block(m, "Mom", Vector3.new(T, H * 0.55 + 1, len), cf * CFrame.new(0, H * 0.45 + (H * 0.55 + 1) / 2 - 1, 0), color, mat)
	-- 여장: 바깥 가장자리 타구 (사이를 비운다), 안쪽 낮은 벽
	local top = H
	local merlonW, gap = opts.merlon or 3.2, opts.gap or 1.2
	local count = math.floor(len / (merlonW + gap))
	local start = -len / 2 + (len - count * (merlonW + gap) + gap) / 2
	for i = 0, count - 1 do
		local z = start + i * (merlonW + gap) + merlonW / 2
		block(m, "Tagu", Vector3.new(1, 2.6, merlonW), cf * CFrame.new(T / 2 - 0.5, top + 1.3, z), opts.parapet or Color3.fromRGB(96, 96, 100), Enum.Material.Brick)
		block(m, "Gat", Vector3.new(1.4, 0.35, merlonW + 0.2), cf * CFrame.new(T / 2 - 0.5, top + 2.75, z), P.giwaDark, Enum.Material.Slate)
	end
	block(m, "Naeyeojang", Vector3.new(0.6, 1.1, len), cf * CFrame.new(-T / 2 + 0.3, top + 0.55, 0), opts.parapet or Color3.fromRGB(96, 96, 100), Enum.Material.Brick)
	return m
end

-- 홍예문: 성벽 가운데 둥근 문길. 문길 둘레는 쐐기돌(홍예석), 그 바깥 네모까지는 삼각으로 메운다. 위에 문루(누각)
-- cf: 문 가운데 땅, 앞(-Z)이 성 밖. 문길은 Z 방향, 벽 몸은 X 방향.
function Build.gatehouse(parent: Instance, cf: CFrame, opts)
	opts = opts or {}
	local H = opts.height or 14
	local T = opts.thick or 6
	local span = opts.span or 20
	local r = opts.radius or 4.2
	local ring = 1.1
	local R = r + ring
	local spring = opts.spring or 5
	local color = opts.color or Color3.fromRGB(176, 168, 150)
	local stone = Color3.fromRGB(198, 192, 178)
	local mat = opts.material or Enum.Material.Cobblestone
	local m = Instance.new("Model")
	m.Name = opts.name or "성문"
	m.Parent = parent
	local function W(v: Vector3): Vector3
		return cf:PointToWorldSpace(v)
	end
	local side = span / 2 - R
	for _, s in { 1, -1 } do
		block(m, "Mom", Vector3.new(side, H, T), cf * CFrame.new(s * (R + side / 2), H / 2, 0), color, mat)
		-- 문설주 (홍예 밑 곧은 돌)
		block(m, "Muncheol", Vector3.new(ring, spring, T + 0.3), cf * CFrame.new(s * (r + ring / 2), spring / 2, 0), stone, Enum.Material.Granite)
	end
	block(m, "Inbang", Vector3.new(2 * R, H - (spring + R), T), cf * CFrame.new(0, (H + spring + R) / 2, 0), color, mat)
	local n = opts.voussoirs or 9
	for i = 0, n - 1 do
		local a0, a1 = math.pi * i / n, math.pi * (i + 1) / n
		local am = (a0 + a1) / 2
		local c = Vector3.new(math.cos(am) * (r + ring / 2), spring + math.sin(am) * (r + ring / 2), 0)
		local wv = 2 * R * math.sin((a1 - a0) / 2)
		-- 홀짝으로 내민 깊이를 달리해 겹친 면이 같은 평면에 오지 않게
		block(m, "Hongye", Vector3.new(ring, wv, T + (if i % 2 == 0 then 0.3 else 0.38)), cf * CFrame.new(c) * CFrame.Angles(0, 0, am), stone, Enum.Material.Granite)
		local function arc(a: number): Vector3
			return Vector3.new(math.cos(a) * R, spring + math.sin(a) * R, 0)
		end
		local function rim(a: number): Vector3
			local x, y = math.cos(a), math.sin(a)
			local k = math.min(if math.abs(x) > 1e-6 then R / math.abs(x) else math.huge, if y > 1e-6 then R / y else math.huge)
			return Vector3.new(x * k, spring + y * k, 0)
		end
		local p0, p1, q0, q1 = arc(a0), arc(a1), rim(a0), rim(a1)
		local poly = { p0, p1, q1 }
		local cx = if math.abs(q0.X) > math.abs(q1.X) then q0.X else q1.X
		local cy = math.max(q0.Y, q1.Y)
		if math.abs(q0.X - q1.X) > 1e-3 and math.abs(q0.Y - q1.Y) > 1e-3 then
			table.insert(poly, Vector3.new(cx, cy, 0))
		end
		table.insert(poly, q0)
		for j = 2, #poly - 1 do
			local a, b, c2 = poly[1], poly[j], poly[j + 1]
			if (b - a):Cross(c2 - a).Magnitude > 0.01 then
				tri(m, "Meum", W(a), W(b), W(c2), T, nil, color, mat)
			end
		end
	end
	local loft = nil
	if opts.loft ~= false then
		loft = Build.house(m, cf * CFrame.new(0, H, 0), {
			bays = { 3, 2 },
			bay = 5,
			pillarH = 7,
			plinth = 0.6,
			style = "palace",
			open = true,
			eave = 3.8,
			detail = opts.detail or 2,
			name = "문루",
			railColor = P.seokganju,
			noSteps = true,
		})
	end
	return m, loft
end

-- 일주문: 기둥 한 줄(둘)에 공포와 팔작지붕을 얹은 마을 어귀 문. 현판(board)을 돌려준다 (World 의 engrave 로 새긴다).
-- ground: 땅 가운데, toward: 문 앞이 볼 곳
function Build.iljumun(parent: Instance, ground: Vector3, toward: Vector3, width: number?)
	local w = width or 12
	local m = Instance.new("Model")
	m.Name = "일주문"
	m.Parent = parent
	local look = face(ground, toward)
	local H = 9.5
	for _, s in { -1, 1 } do
		local foot = look * CFrame.new(s * w / 2, 0, 0)
		block(m, "Choseok", Vector3.new(2.4, 1.2, 2.4), foot * CFrame.new(0, 0, 0), P.granite, Enum.Material.Granite)
		cyl(m, "Gidung", (foot * CFrame.new(0, 0.6, 0)).Position, (foot * CFrame.new(0, H, 0)).Position, 1.5, P.seokganju, Enum.Material.Wood)
		-- 기둥 앞뒤 버팀 (보조 기둥 없이 쓰러지지 않아 보이게 짧은 받침)
		for _, f in { -1, 1 } do
			beam(m, "Beotim", (foot * CFrame.new(0, 2.2, 0)).Position, (foot * CFrame.new(0, 0.2, f * 1.6)).Position, 0.45, 0.45, P.seokganju, Enum.Material.Wood)
		end
	end
	-- 창방·평방 (단청: 뇌록 바탕, 주홍·군청 띠)
	block(m, "Changbang", Vector3.new(w + 2.4, 1.1, 0.9), look * CFrame.new(0, H - 0.55, 0), P.noerok, Enum.Material.Wood)
	block(m, "Dancheong", Vector3.new(w + 2.42, 0.2, 0.94), look * CFrame.new(0, H - 1.0, 0), P.juhong, Enum.Material.SmoothPlastic)
	block(m, "Pyeongbang", Vector3.new(w + 3, 0.5, 1.3), look * CFrame.new(0, H + 0.25, 0), P.gunjeong, Enum.Material.Wood)
	-- 공포: 기둥 사이에 촘촘히 (다포)
	local n = math.max(3, math.floor(w / 2.2))
	for i = 0, n do
		local x = -w / 2 - 0.6 + (w + 1.2) * i / n
		block(m, "Judu", Vector3.new(0.9, 0.55, 0.9), look * CFrame.new(x, H + 0.78, 0), P.noerok, Enum.Material.Wood)
		block(m, "Cheomcha", Vector3.new(1.6, 0.45, 0.5), look * CFrame.new(x, H + 1.28, 0), P.yangrok, Enum.Material.Wood)
		block(m, "Salmi", Vector3.new(0.45, 0.45, 3.2), look * CFrame.new(x, H + 1.28, 0), P.noerok, Enum.Material.Wood)
	end
	block(m, "Pobyeok", Vector3.new(w + 1.6, 1.1, 0.3), look * CFrame.new(0, H + 1.05, 0), P.noerok:Lerp(P.plaster, 0.3), Enum.Material.Plaster)
	-- 현판: 창방 아래 가운데
	local board = block(m, "Hyeonpan", Vector3.new(math.min(w - 3, 6), 1.8, 0.3), look * CFrame.new(0, H - 2.1, -0.6), P.meok, Enum.Material.Wood)
	block(m, "Te", Vector3.new(board.Size.X + 0.5, 2.3, 0.25), look * CFrame.new(0, H - 2.1, -0.5), P.hwang, Enum.Material.Wood)
	-- 지붕: 앞뒤로 얕은 팔작
	local top = H + 1.55
	local spec = { ex = w / 2 + 3.2, ez = 3.6, eave = 2.4, bands = 3, kind = "paljak", nHip = 2, pitchLow = 18, pitchHigh = 44, lift = 1.2, flare = 0.5, t = 0.5, segs = 2 }
	local _, _, h, pitches = profile(spec)
	local under = h[1] - 0.5 / math.cos(math.rad(pitches[1]))
	roof(m, look * CFrame.new(0, top + 0.1 - under, 0), spec)
	return m, board
end

-- 폭포: 벼랑 끝(lip, 물이 넘는 가운데)에서 dir(수평, 물 흐르는 쪽)으로 떨어진다. width 폭, height 낙차.
-- 물줄기 판(유리) 두 겹 + 넘어가는 굽은 판 + 파티클 셋(물줄기, 물보라, 안개). 텍스처는 엔진 내장(rbxasset://)이라 올릴 것 없음
function Build.waterfall(parent: Instance, lip: Vector3, dir: Vector3, width: number, height: number)
	local m = Instance.new("Model")
	m.Name = "폭포"
	m.Parent = parent
	local look = face(lip, lip + dir) -- -Z 가 물 흐르는 쪽
	local water = Color3.fromRGB(186, 222, 238)
	local function sheet(name: string, size: Vector3, cf: CFrame, transparency: number)
		local p = deco(block(m, name, size, cf, water, Enum.Material.Glass))
		p.Transparency = transparency
		p.CastShadow = false
		return p
	end
	-- 넘어가는 굽은 판: 수평에서 수직으로 네 마디 (가장자리를 축으로 꺾는다)
	local cf = look * CFrame.new(0, 0.1, 0.6)
	local seg = 0.9
	for _ = 1, 4 do
		cf = cf * CFrame.new(0, 0, -seg / 2) -- 앞 마디 끝을 축으로
		local piece = cf * CFrame.Angles(math.rad(-22), 0, 0) -- 마디마다 22도씩 더 꺾여 네 마디면 거의 수직
		sheet("Neomeo", Vector3.new(width, 0.35, seg + 0.05), piece * CFrame.new(0, 0, -seg / 2), 0.3)
		cf = piece * CFrame.new(0, 0, -seg / 2)
	end
	local front = cf.Position
	local fallTop = front
	sheet("Mulgil", Vector3.new(width * 0.98, height, 0.35), CFrame.new(fallTop - Vector3.new(0, height / 2, 0)) * (look - look.Position), 0.35)
	sheet("Mulgil2", Vector3.new(width * 0.9, height, 0.25), CFrame.new(fallTop - Vector3.new(0, height / 2, 0) + look.LookVector * 0.35) * (look - look.Position), 0.6)
	-- 물줄기 파티클: 위 가장자리에서 아래로 (Squash 로 세로로 늘인 긴 방울)
	local emitTop = deco(block(m, "Emit", Vector3.new(width, 0.2, 0.2), CFrame.new(fallTop + look.LookVector * 0.5) * (look - look.Position), water))
	emitTop.Transparency = 1
	local streak = Instance.new("ParticleEmitter")
	streak.Name = "Mulbal"
	streak.Texture = "rbxasset://textures/particles/smoke_main.dds"
	streak.EmissionDirection = Enum.NormalId.Bottom
	streak.Shape = Enum.ParticleEmitterShape.Box
	streak.Rate = width * 6
	streak.Lifetime = NumberRange.new(math.sqrt(2 * height / 40) * 0.9, math.sqrt(2 * height / 40))
	streak.Speed = NumberRange.new(4, 7)
	streak.Acceleration = Vector3.new(0, -40, 0)
	streak.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.6), NumberSequenceKeypoint.new(1, 3.2) })
	streak.Squash = NumberSequence.new(1.2)
	streak.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.5), NumberSequenceKeypoint.new(0.8, 0.7), NumberSequenceKeypoint.new(1, 1) })
	streak.Color = ColorSequence.new(Color3.fromRGB(235, 246, 255))
	streak.LightEmission = 0.25
	streak.Orientation = Enum.ParticleOrientation.VelocityParallel
	streak.Parent = emitTop
	-- 물보라와 안개: 아래 못
	local base = fallTop - Vector3.new(0, height, 0) + look.LookVector * 1.2
	local foamPart = deco(block(m, "Mulbora", Vector3.new(width, 0.4, 3), CFrame.new(base) * (look - look.Position), water))
	foamPart.Transparency = 1
	local foam = Instance.new("ParticleEmitter")
	foam.Name = "Mulbora"
	foam.Texture = "rbxasset://textures/particles/smoke_main.dds"
	foam.EmissionDirection = Enum.NormalId.Top
	foam.Shape = Enum.ParticleEmitterShape.Box
	foam.Rate = width * 3
	foam.Lifetime = NumberRange.new(1.2, 2.2)
	foam.Speed = NumberRange.new(3, 7)
	foam.SpreadAngle = Vector2.new(50, 50)
	foam.Acceleration = Vector3.new(0, -6, 0)
	foam.Drag = 1.5
	foam.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2.5), NumberSequenceKeypoint.new(1, 7) })
	foam.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 1) })
	foam.Color = ColorSequence.new(Color3.fromRGB(245, 250, 255))
	foam.Parent = foamPart
	local mist = Instance.new("ParticleEmitter")
	mist.Name = "Angae"
	mist.Texture = "rbxasset://textures/particles/smoke_main.dds"
	mist.Rate = 4
	mist.Lifetime = NumberRange.new(4, 6)
	mist.Speed = NumberRange.new(1, 2.5)
	mist.SpreadAngle = Vector2.new(180, 40)
	mist.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 10), NumberSequenceKeypoint.new(1, 22) })
	mist.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.82), NumberSequenceKeypoint.new(1, 1) })
	mist.Color = ColorSequence.new(Color3.fromRGB(240, 246, 252))
	mist.Parent = foamPart
	return m
end

-- 벼랑 면: a→b 선(벼랑 위 가장자리)을 따라 기울인 바위 판을 겹쳐 세운다. top/bottom 은 그 자리 높이 함수 (x, z) -> y
-- out: 벼랑 바깥(낮은 쪽) 수평 방향
function Build.cliffFace(parent: Instance, a: Vector3, b: Vector3, out: Vector3, top: (number, number) -> number, bottom: (number, number) -> number, rng, opts)
	opts = opts or {}
	local m = Instance.new("Model")
	m.Name = "벼랑"
	m.Parent = parent
	local color = opts.color or Color3.fromRGB(108, 104, 100)
	local mat = opts.material or Enum.Material.Slate
	local len = (b - a).Magnitude
	local n = math.max(1, math.floor(len / (opts.spacing or 4.5)))
	for i = 0, n do
		local p = a:Lerp(b, i / n)
		local yTop, yBot = top(p.X, p.Z), bottom(p.X, p.Z)
		local h = (yTop - yBot) * rng(0.75, 1.05)
		local w = rng(4, 7)
		local d = rng(2.5, 4.5)
		local c = Vector3.new(p.X, yBot + h / 2 - 0.5, p.Z) + out * rng(-0.6, 0.4)
		local cf = face(c, c + out) * CFrame.Angles(math.rad(rng(-14, -4)), 0, math.rad(rng(-6, 6)))
		block(m, "Bawi", Vector3.new(w, h, d), cf, jitter(color, rng, 0.08), mat)
	end
	return m
end

return Build
