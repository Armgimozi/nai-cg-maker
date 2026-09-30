-- 아시아(2) 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.

return function(K)
	local V, rgb, Mat, PI, TAU = K.V, K.rgb, K.Mat, K.PI, K.TAU
	local ALONG_Z, CORNERS = K.ALONG_Z, K.CORNERS
	local LEAF, WATER, DARK, TILE, ROCK, WOOD, SAND, CLOUD, BLACK, WHITE =
		K.LEAF, K.WATER, K.DARK, K.TILE, K.ROCK, K.WOOD, K.SAND, K.CLOUD, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam, facing, roof, gable, plant =
		K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam, K.facing, K.roof, K.gable, K.plant

	local B = {}

	-- 기와지붕(K.roof)을 다른 재질로 씌움
	local function roofWith(c, material, x, y, z, w, d, h, color)
		local keep = c.M
		c.M = material
		roof(c, x, y, z, w, d, h, color)
		c.M = keep
	end

	-- 삼각형 판: 밑변 a-b(꼭짓점 p 가 그 위쪽) 를 잇는 두께 t 의 판(직각 쐐기 두 개, p 에서 내린 수선으로 나눔).
	-- p 의 수선 발이 a-b 사이에 와야 함. 쐐기 상자의 빈 모서리도 p 높이 아래·안쪽에 머묾.
	-- out = 1 이면 inside 반대쪽(바깥)으로, -1 이면 inside 쪽으로 두께를 줌(면이 정확히 삼각형 평면에 오도록)
	local function tri(
		c,
		a: Vector3,
		b: Vector3,
		p: Vector3,
		t: number,
		color: Color3,
		material,
		inside: Vector3,
		out: number
	)
		local along = (b - a).Unit
		local foot = a + along * (p - a):Dot(along)
		local h = (p - foot).Magnitude
		local up = (p - foot).Unit
		local normal = (b - a):Cross(p - a).Unit
		if normal:Dot(inside - a) > 0 then
			normal = -normal
		end
		local shift = normal * (out * t / 2)
		local da, db = (foot - a):Dot(along), (b - foot):Dot(along)
		if da > 0.02 then
			local center = foot + up * (h / 2) - along * (da / 2) + shift
			wedge(c, CFrame.lookAt(center, center - along, up), V(t, h, da), color, material)
		end
		if db > 0.02 then
			local center = foot + up * (h / 2) + along * (db / 2) + shift
			wedge(c, CFrame.lookAt(center, center + along, up), V(t, h, db), color, material)
		end
	end

	-- 삼각뿔/사각뿔 봉우리: 바위 면(안쪽 두께) + 면마다 꼭대기에서 snow[i] 비율까지 덮는 눈 면(바깥 두께).
	-- ring[i] → ring[i + 1] 이 i 번째 면의 밑변. 꼭대기의 수선 발이 각 밑변 안에 오도록 둘 것
	local function peak(c, apex: Vector3, ring: { Vector3 }, rock: Color3, snowColor: Color3, snow: { number }?)
		local center = V(apex.X, ring[1].Y, apex.Z)
		for i, a in ring do
			local b = ring[i % #ring + 1]
			tri(c, a, b, apex, 0.3, rock, Mat.Rock, center, -1)
		end
		if snow then
			for i, a in ring do
				local b = ring[i % #ring + 1]
				local f = snow[i]
				if f > 0 then
					tri(c, apex + (a - apex) * f, apex + (b - apex) * f, apex, 0.12, snowColor, Mat.Snow, center, 1)
				end
			end
		end
	end

	-- 돌하르방: 둥근 잔디 + 제주 검은 돌담 + 유채꽃 + 귤나무, 가운데에 벙거지 모자·왕방울 눈·큰 코·배 위에 얹은 두 손의 현무암 석상
	function B.dolhareubang(c)
		local stone = mix(c.P, WHITE, 0.22)
		local pale = mix(c.P, WHITE, 0.34)
		local basalt = mix(c.P, BLACK, 0.3)
		col(c, 0, 0, 0, 0.3, 9.8, c.S, Mat.Grass)
		for _, a in { -0.95, 0, 0.95 } do
			local px, pz = 3.9 * math.sin(a), 3.9 * math.cos(a)
			block(c, CFrame.new(px, 0.75, pz) * facing(px, pz), V(3, 0.9, 0.7), basalt)
		end
		for _, f in
			{ { -2.9, -2.4, 0.8 }, { -3.6, -1.3, 0.7 }, { -2.2, -3.3, 0.7 }, { -3.4, 0.1, 0.6 }, { -1.3, -3.9, 0.6 } }
		do
			ball(c, f[1], 0.3 + f[3] * 0.4, f[2], f[3], rgb(250, 214, 48), Mat.Grass)
		end
		plant(c, 3, 0.3, -2.3, 1.2, 2, LEAF)
		for _, d in
			{ V(-0.5, 0.3, -0.8), V(0.45, 0.5, -0.75), V(0.9, -0.1, -0.4), V(-0.1, 0.95, -0.3), V(-0.85, -0.2, -0.5) }
		do
			local p = V(3, 2.1, -2.3) + d.Unit
			ball(c, p.X, p.Y, p.Z, 0.42, c.A)
		end
		-- 석상
		col(c, 0, 0.3, 0, 0.7, 3.8, basalt)
		col(c, 0, 1, 0, 5.2, 3.1, stone)
		cyl(c, CFrame.new(-0.25, 4.5, -1.35), 2.1, 0.75, stone)
		cyl(c, CFrame.new(0.25, 3.45, -1.35), 2.1, 0.75, stone)
		beam(c, V(-1.45, 5.9, 0), V(-1.25, 4.5, -1.05), 0.6, stone)
		beam(c, V(1.45, 5.9, 0), V(1.3, 3.45, -1.05), 0.6, stone)
		ball(c, 0, 7.5, -0.1, 3.5, stone)
		for _, sx in { -1, 1 } do
			box(c, sx * 1.66, 6.4, 0, 0.25, 1.5, 0.55, stone)
			ball(c, sx * 0.72, 7.9, -1.4, 1.15, pale)
			ball(c, sx * 0.72, 7.9, -1.93, 0.36, DARK)
		end
		wedge(c, CFrame.new(0, 6.95, -1.95), V(1.05, 1.7, 0.75), pale)
		box(c, 0, 5.87, -1.58, 1.2, 0.18, 0.1, DARK)
		col(c, 0, 8.7, 0, 0.35, 3.9, stone)
		col(c, 0, 9.05, 0, 0.8, 3.1, stone)
		ball(c, 0, 9.8, 0, 3.1, stone)
	end

	-- 다보탑: 사방 돌계단의 기단 + 네 귀 돌기둥과 가운데 기둥 + 네모 옥개석 + 네모 난간 + 대나무 마디 기둥의 팔각 난간
	--   + 연꽃 받침 + 팔각 지붕돌 + 상륜(노반·복발·보륜·보주)
	function B.dabotap(c)
		local stone = c.P
		local joint = mix(c.P, BLACK, 0.15)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.S, SAND, 0.45), Mat.Sand)
		box(c, 0, 0.25, 0, 6, 1.5, 6, stone)
		box(c, 0, 1.75, 0, 6.3, 0.25, 6.3, joint)
		for i = 0, 3 do
			wedge(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 1.125, -3.8), V(1.5, 1.75, 1.6), stone)
		end
		local y = 2
		for _, s in CORNERS do
			box(c, s[1] * 1.9, y, s[2] * 1.9, 0.55, 2.5, 0.55, stone)
		end
		box(c, 0, y, 0, 1.2, 2.5, 1.2, stone)
		y += 2.5
		box(c, 0, y, 0, 4.7, 0.3, 4.7, joint)
		box(c, 0, y + 0.3, 0, 5.4, 0.45, 5.4, stone)
		y += 0.75
		box(c, 0, y, 0, 2.4, 1.5, 2.4, stone)
		for i = 0, 3 do
			block(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, y + 0.45, -2.3), V(4.7, 0.9, 0.16), stone)
		end
		y += 1.5
		col(c, 0, y, 0, 0.3, 3.4, joint)
		y += 0.3
		col(c, 0, y, 0, 1.4, 1.5, stone)
		for i = 0, 7 do
			local a = i * PI / 4 + PI / 8
			col(c, 1.3 * math.cos(a), y, 1.3 * math.sin(a), 1.4, 0.24, stone)
		end
		y += 1.4
		col(c, 0, y, 0, 0.3, 3, joint)
		col(c, 0, y + 0.3, 0, 0.45, 2, stone)
		y += 0.75
		col(c, 0, y, 0, 0.35, 3.9, stone)
		y += 0.35
		col(c, 0, y, 0, 0.45, 1.1, stone)
		ball(c, 0, y + 0.8, 0, 1, stone)
		col(c, 0, y + 1.2, 0, 2.3, 0.2, stone)
		for k, d in { 0.95, 0.8, 0.65 } do
			col(c, 0, y + 1.3 + k * 0.45, 0, 0.14, d, stone)
		end
		ball(c, 0, y + 3.6, 0, 0.45, c.A, Mat.Metal)
	end

	-- 경복궁 근정전: 박석 마당 + 품계석 + 돌난간 두른 2단 월대와 가운데 계단 + 붉은 기둥 늘어선 전각
	--   + 초록 단청 띠 + 들린 추녀의 겹처마 기와지붕 두 겹
	function B.gyeongbokgung(c)
		local granite = rgb(208, 202, 190)
		local rail = rgb(238, 234, 224)
		local wall = mix(c.P, BLACK, 0.3)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(granite, SAND, 0.35), Mat.Sand)
		for _, sx in { -1, 1 } do
			for _, z in { -4.3, -3.3 } do
				box(c, sx * 1.4, 0.2, z, 0.35, 0.45, 0.25, granite, Mat.Granite)
			end
		end
		box(c, 0, 0.2, 1.2, 9.2, 0.8, 6.8, granite, Mat.Granite)
		box(c, 0, 1, 1.45, 7.6, 0.8, 5.5, granite, Mat.Granite)
		wedge(c, CFrame.new(0, 0.6, -2.65), V(1.6, 0.8, 0.9), granite, Mat.Granite)
		wedge(c, CFrame.new(0, 1.4, -1.75), V(1.4, 0.8, 0.9), granite, Mat.Granite)
		for _, sx in { -1, 1 } do
			box(c, sx * 2.7, 1, -2.14, 3.8, 0.3, 0.12, rail, Mat.Marble)
			box(c, sx * 2.3, 1.8, -1.19, 3, 0.3, 0.12, rail, Mat.Marble)
			box(c, sx * 3.74, 1.8, 1.45, 0.12, 0.3, 5.5, rail, Mat.Marble)
		end
		local y = 1.8
		box(c, 0, y, 1.8, 6, 2, 3.4, wall)
		for k = 0, 5 do
			col(c, -2.75 + k * 1.1, y, 0.02, 2, 0.32, c.P)
		end
		box(c, 0, y + 1.65, 1.8, 6.3, 0.4, 3.7, c.S)
		roofWith(c, Mat.Slate, 0, y + 2.05, 1.8, 8.2, 5.6, 0.9, TILE)
		box(c, 0, 4.5, 1.8, 4.8, 1.3, 2.6, wall)
		box(c, 0, 5.75, 1.8, 5, 0.35, 2.8, c.S)
		roofWith(c, Mat.Slate, 0, 6.1, 1.8, 7.2, 4.6, 1.3, TILE)
	end

	-- 초콜릿 힐: 흙 단면이 보이는 들판 위에 고르게 솟은 갈색 둥근 언덕들(일부는 풀빛) + 전망대 언덕 + 덤불
	function B.chocolatehills(c)
		local base = 1
		box(c, 0, 0, 0, 9.8, base - 0.15, 9.8, mix(c.P, BLACK, 0.3), Mat.Ground)
		box(c, 0, base - 0.15, 0, 9.8, 0.15, 9.8, mix(c.S, LEAF, 0.35), Mat.Grass)
		-- { x, z, 지름 }: 공 중심 = 지름 / 2 (바닥 판이 아래쪽을 가림)
		local hills = {
			{ -3.7, -3.6, 2.2 },
			{ -1.3, -3.9, 2 },
			{ 1.2, -3.5, 2.3 },
			{ 3.7, -3.8, 2.1 },
			{ -3.9, -1.2, 2 },
			{ -1.8, -1.6, 1.9 },
			{ 2.5, -1.3, 2.3 },
			{ 4, 0.9, 1.9 },
			{ -3.5, 1.3, 2.3 },
			{ 1.8, 1.5, 2.1 },
			{ -3.8, 3.8, 2.1 },
			{ -1.3, 3.4, 2.3 },
			{ 1.1, 3.9, 2 },
			{ 3.6, 3.6, 2.3 },
			{ 0.4, -1.9, 1.7 },
		}
		for k, h in hills do
			local color = if k % 5 == 2 then mix(c.P, c.S, 0.55) else mix(c.P, BLACK, (k % 3) * 0.06)
			ball(c, h[1], h[3] / 2, h[2], h[3], color)
		end
		ball(c, -0.4, 1.5, 0.6, 3, c.P)
		box(c, -0.4, 2.85, 0.6, 1, 0.5, 1, c.A, Mat.Concrete)
		gable(c, -0.4, 3.35, 0.6, 1.2, 1.2, 0.5, rgb(190, 60, 50))
		for _, t in { { -2.6, -2.8, 0.7 }, { 3.1, -2.5, 0.6 }, { -2.2, 2.3, 0.8 }, { 2.9, 2.6, 0.7 } } do
			ball(c, t[1], base + t[3] / 2 - 0.1, t[2], t[3], LEAF, Mat.Grass)
		end
	end

	-- 금각사: 거울 연못 + 소나무 섬 + 뒤쪽 숲 + 돌 기단 위 3층 누각
	--   (1층 흰 벽·나무 기둥, 2·3층 금박, 얇게 뻗은 너와 처마, 꼭대기 금 봉황) + 물에 비친 금빛 + 낚시 정자
	function B.kinkakuji(c)
		local pond = mix(WATER, c.A, 0.5)
		local shingle = rgb(72, 54, 42)
		local wood = rgb(125, 90, 60)
		local plaster = rgb(242, 238, 228)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, pond, Mat.Glass, 0.1)
		box(c, 0, 0, 3.8, 9.8, 0.5, 2.2, c.S, Mat.Grass)
		ball(c, -3.7, 1.6, 3.9, 2.2, c.S, Mat.Grass)
		ball(c, 3.7, 1.8, 3.8, 2.4, mix(c.S, BLACK, 0.15), Mat.Grass)
		col(c, -3.4, 0, -3.1, 0.35, 1.9, ROCK, Mat.Slate)
		ball(c, -3.4, 1, -3.1, 1.2, LEAF, Mat.Grass)
		col(c, 3.5, 0, -3.6, 0.3, 1.4, ROCK, Mat.Slate)
		ball(c, 3.5, 0.8, -3.6, 0.9, LEAF, Mat.Grass)
		box(c, 0, 0.2, -2.6, 4.8, 0.03, 2.2, c.P, Mat.Glass, 0.55)
		-- 누각(s 배 크기)
		local s, z = 1.18, 1
		local function part(x, y, w, h, d, color, material)
			box(c, x * s, y * s, z, w * s, h * s, d * s, color, material)
		end
		part(0, 0, 5, 0.45, 4.2, ROCK, Mat.Slate)
		part(0, 0.45, 4.4, 1.6, 3.6, plaster, Mat.Plaster)
		for _, x in { -2.1, -0.7, 0.7, 2.1 } do
			box(c, x * s, 0.45 * s, z - 1.85 * s, 0.22 * s, 1.6 * s, 0.14, wood, Mat.Wood)
		end
		part(0, 2.05, 5.4, 0.2, 4.6, shingle, Mat.Wood)
		part(0, 2.25, 4.8, 0.15, 4, shingle, Mat.Wood)
		part(0, 2.4, 4.1, 1.5, 3.3, c.P)
		part(0, 2.4, 4.5, 0.35, 3.7, c.P)
		part(0, 3.9, 5.2, 0.2, 4.4, shingle, Mat.Wood)
		part(0, 4.1, 4.4, 0.15, 3.6, shingle, Mat.Wood)
		part(0, 4.25, 2.6, 1.35, 2.4, c.P)
		roofWith(c, Mat.Wood, 0, 5.6 * s, z, 3.9 * s, 3.6 * s, 1.1 * s, shingle)
		local top = (5.6 + 0.3) * s + 1.1 * s
		box(c, 0, top, z, 0.24, 0.6, 0.24, c.P)
		wedge(c, CFrame.new(0, top + 0.7, z), V(1.1, 0.5, 0.6), c.P)
		box(c, -3.6, 0.2, 0.4, 1.3, 0.9, 1.3, wood, Mat.Wood)
		box(c, -3.6, 1.1, 0.4, 1.7, 0.2, 1.7, shingle, Mat.Wood)
	end

	-- 천단 기년전: 3단 원형 흰 대리석 기단(사방 계단) + 붉은 원통 몸체 + 단청 띠 + 파란 원뿔 지붕 세 겹 + 금빛 보주
	function B.templeofheaven(c)
		local marble = c.A
		local railColor = mix(c.A, rgb(150, 150, 150), 0.3)
		local band = rgb(40, 130, 110)
		local gold = rgb(235, 190, 70)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, rgb(165, 160, 155), Mat.Concrete)
		local y = 0.2
		for _, d in { 9.4, 7.8, 6.2 } do
			col(c, 0, y, 0, 0.55, d, marble)
			col(c, 0, y + 0.55, 0, 0.18, d - 0.15, railColor)
			y += 0.73
		end
		local rise = y - 0.2
		for i = 0, 3 do
			wedge(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 0.2 + rise / 2, -3.9), V(1.2, rise, 1.6), marble)
		end
		local function tier(bodyD: number, bodyH: number, discs: { { number } })
			col(c, 0, y, 0, bodyH, bodyD, c.S)
			y += bodyH
			col(c, 0, y, 0, 0.25, bodyD + 0.2, band)
			y += 0.25
			for _, disc in discs do
				col(c, 0, y, 0, disc[2], disc[1], c.P)
				y += disc[2]
			end
		end
		tier(4.4, 1.5, { { 6, 0.28 }, { 5.1, 0.3 }, { 4.1, 0.3 }, { 3.2, 0.25 } })
		tier(3.3, 0.85, { { 4.8, 0.28 }, { 4, 0.3 }, { 3.1, 0.3 }, { 2.3, 0.25 } })
		tier(2.3, 0.7, { { 3.6, 0.28 }, { 2.9, 0.32 }, { 2.1, 0.32 }, { 1.4, 0.3 }, { 0.7, 0.25 } })
		col(c, 0, y, 0, 0.5, 0.3, gold, Mat.Metal)
		ball(c, 0, y + 0.75, 0, 0.6, gold, Mat.Metal)
	end

	-- 포탈라궁: 마르포리 언덕(흰 지그재그 계단) + 층층이 흰 궁전(창 줄) + 가운데 우뚝한 붉은 궁전
	--   + 지붕 아래 검붉은 펜바 띠 + 금빛 지붕 세 채와 승리 깃발 + 앞쪽 성벽
	function B.potala(c)
		local white, red, gold = c.P, c.S, c.A
		local frieze = rgb(92, 34, 30)
		local hill = rgb(140, 118, 92)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, rgb(150, 140, 110), Mat.Ground)
		wedge(c, CFrame.new(0, 1.15, -2.6), V(9.8, 1.8, 2.2), hill, Mat.Rock)
		box(c, 0, 0.25, 1.2, 9.4, 3.2, 5.4, white)
		box(c, 0, 3.2, 1.2, 9.5, 0.25, 5.5, frieze)
		for _, wy in { 2.2, 2.75 } do
			for _, x in { -3.2, 0, 3.2 } do
				box(c, x, wy, -1.52, 2.4, 0.26, 0.06, DARK)
			end
		end
		for _, sx in { -1, 1 } do
			box(c, sx * 3.1, 3.45, 1.3, 2.8, 2.45, 4.4, white)
			box(c, sx * 3.1, 5.9, 1.3, 2.9, 0.4, 4.5, frieze)
			box(c, sx * 3.1, 4.6, -0.92, 2, 0.28, 0.06, DARK)
			beam(c, V(sx * 4.3, 0.55, -3.5), V(sx * 1.9, 1.3, -2.8), 0.25, white)
			beam(c, V(sx * 1.9, 1.35, -2.75), V(sx * 4.1, 2, -1.75), 0.25, white)
			col(c, sx * 1.55, 8.65, -0.4, 0.8, 0.24, gold, Mat.Metal)
			ball(c, sx * 4.4, 0.65, -4.3, 0.8, LEAF, Mat.Grass)
		end
		box(c, 0, 3.45, 1.2, 3.8, 1.35, 4.6, white)
		box(c, 0, 4.8, 1.3, 3.4, 3.4, 4, red)
		box(c, 0, 8.2, 1.3, 3.5, 0.45, 4.1, frieze)
		for _, wy in { 5.6, 6.5, 7.4 } do
			box(c, 0, wy, -0.72, 2.6, 0.3, 0.06, DARK)
		end
		-- 금빛 지붕 세 채(작은 붉은 누각 위)
		for _, g in { { -1.05, 0.8, 1.9 }, { 0.1, 1.1, 1.3 }, { 1.15, 0.8, 2 } } do
			box(c, g[1], 8.65, g[3], g[2] - 0.2, 0.35, g[2] - 0.2, frieze)
			gable(c, g[1], 9, g[3], g[2] + 0.1, g[2] + 0.1, 0.55, gold)
		end
		box(c, 0, 0.25, -4.5, 8.4, 0.7, 0.35, white)
	end

	-- 하롱베이: 에메랄드 바다 + 물가가 파여 들어간 석회암 섬들(비틀린 바위 두 덩이 + 초록 숲 덮개) + 붉은 돛 정크선
	function B.halong(c)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		local lime = mix(mix(ROCK, c.P, 0.45), SAND, 0.15)
		local lime2 = mix(lime, WHITE, 0.12)
		local wet = mix(lime, BLACK, 0.35)
		local jungle = mix(LEAF, c.P, 0.2)
		local function karst(x: number, z: number, h: number, w: number, d: number, twist: number)
			local cf = CFrame.new(x, 0, z) * CFrame.Angles(0, twist, 0)
			col(c, x, 0.3, z, 0.45, math.min(w, d) * 0.8, wet)
			local body = h - 0.75
			block(
				c,
				cf * CFrame.new(0, 0.75 + body * 0.42, 0) * CFrame.Angles(0.04, 0, -0.03),
				V(w, body * 0.84, d),
				lime
			)
			block(
				c,
				cf * CFrame.new(w * 0.05, 0.75 + body * 0.4, -d * 0.04) * CFrame.Angles(0, PI / 4, 0.05),
				V(w * 0.8, body * 0.8, d * 0.8),
				lime2
			)
			local top = math.max(w, d) * 1.02
			ball(c, x, h - top * 0.28, z, top, jungle, Mat.Grass)
		end
		karst(-3.1, 2.9, 4.8, 2.8, 2.4, 0.3)
		karst(-0.2, 3.4, 3.6, 2.4, 1.8, -0.4)
		karst(2.7, 2.6, 5.6, 2.5, 2.4, 0.6)
		karst(3.7, -0.5, 3.2, 1.9, 2.1, -0.2)
		karst(-3.5, -0.6, 3, 2, 1.8, 0.8)
		karst(0.5, 0.7, 2.4, 1.9, 1.7, 0.2)
		karst(-1.9, -3, 1.8, 1.5, 1.3, -0.5)
		-- 정크선(왼쪽으로 항해): 선체 + 높은 고물 + 세 돛대의 붉은 돛
		local bx, bz = 1.7, -3.4
		box(c, bx, 0.3, bz, 2.8, 0.4, 0.9, WOOD, Mat.Wood)
		box(c, bx + 1.05, 0.7, bz, 0.7, 0.4, 0.9, WOOD, Mat.Wood)
		for _, s in { { -0.9, 0.75, 1.3 }, { 0.05, 1, 2 }, { 0.95, 0.7, 1.2 } } do
			col(c, bx + s[1], 0.7, bz, s[3] + 0.4, 0.08, DARK)
			block(
				c,
				CFrame.new(bx + s[1] + 0.05, 1.05 + s[3] / 2, bz - 0.08) * CFrame.Angles(0, 0.3, 0),
				V(s[2], s[3], 0.06),
				c.A,
				Mat.Fabric
			)
		end
	end

	-- 장가계: 짙은 숲 골짜기에서 솟은 가느다란 사암 기둥들(두 덩이를 비틀어 쌓음 + 풀 덮인 꼭대기 + 소나무)
	--   + 기둥 사이를 떠도는 구름 + 천하제일교(두 기둥을 잇는 돌다리)
	function B.zhangjiajie(c)
		box(c, 0, 0, 0, 9.8, 0.4, 9.8, mix(c.S, BLACK, 0.25), Mat.Grass)
		local low = mix(c.P, BLACK, 0.08)
		local high = mix(c.P, rgb(210, 190, 160), 0.35)
		local pine = mix(LEAF, c.S, 0.3)
		local function pillar(x: number, z: number, h: number, w: number, twist: number)
			local bottom = h * 0.55
			block(c, CFrame.new(x, 0.4 + bottom / 2, z) * CFrame.Angles(0, twist, 0), V(w, bottom, w * 0.9), low)
			local upper = h - bottom
			local cf = CFrame.new(x + w * 0.05, 0.4 + bottom + upper / 2 - 0.05, z - w * 0.05)
				* CFrame.Angles(0, twist + 0.4, 0)
			block(c, cf, V(w * 0.8, upper, w * 0.75), high)
			local top = cf * V(0, upper / 2 + w * 0.25, 0)
			ball(c, top.X, top.Y, top.Z, w * 1.15, pine, Mat.Grass)
			local side = cf * V(-w * 0.42, upper * 0.1, -w * 0.3)
			ball(c, side.X, side.Y, side.Z, w * 0.7, pine, Mat.Grass)
		end
		pillar(-2.6, 2.4, 17, 1.8, 0.2)
		pillar(0.4, 3.4, 14, 1.6, -0.3)
		pillar(3, 2, 15.5, 1.7, 0.5)
		pillar(-3.6, -0.9, 11, 1.5, -0.1)
		pillar(-0.8, 0.1, 12.5, 1.5, 0.7)
		pillar(2, -1, 9.5, 1.4, 0.1)
		pillar(3.7, -3.4, 7, 1.3, -0.4)
		pillar(-1.8, -3.3, 6.5, 1.3, 0.3)
		beam(c, V(-2, 12.2, 2.6), V(-0.1, 12.2, 3.2), 0.6, high)
		-- 기둥 사이를 떠도는 구름
		for _, cl in { { -1, 7.4, 2.2, 2.6 }, { 2.6, 5.6, 0.6, 2.2 }, { -2.4, 3.6, -1.6, 2.4 }, { 1.2, 3, -2.6, 2 } } do
			ball(c, cl[1], cl[2], cl[3], cl[4], c.A, Mat.SmoothPlastic, 0.3)
		end
		for _, t in { { 0.6, -3.6, 1.4 }, { -4, 3.9, 1.3 }, { 4.1, 0.7, 1.2 } } do
			ball(c, t[1], 0.4 + t[3] * 0.35, t[2], t[3], LEAF, Mat.Grass)
		end
	end

	-- 보로부두르: 밀림 잔디 + 네모 기단 5층(사방 계단) + 원형 단 3층에 둘러앉은 종 모양 스투파들 + 꼭대기 큰 스투파
	function B.borobudur(c)
		local stone = c.P
		local dark = mix(c.P, BLACK, 0.18)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, c.S, Mat.Grass)
		local y = 0.2
		for i, w in { 8.8, 7.8, 6.8, 5.8, 4.8 } do
			box(c, 0, y, 0, w, 0.5, w, if i % 2 == 1 then stone else dark)
			y += 0.5
		end
		for i = 0, 3 do
			local cf = CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 1.45, -3.68)
			wedge(c, cf, V(0.9, 2.5, 2.5), mix(stone, WHITE, 0.2))
		end
		-- 원형 단 + 스투파 고리: { 단 지름, 고리 반지름, 스투파 수, 스투파 지름 }
		for _, ring in { { 4.4, 1.97, 12, 0.5 }, { 3.5, 1.52, 9, 0.46 }, { 2.6, 1.07, 6, 0.42 } } do
			col(c, 0, y, 0, 0.3, ring[1], stone)
			y += 0.3
			for k = 0, ring[3] - 1 do
				local a = k / ring[3] * TAU + ring[2]
				ball(c, ring[2] * math.cos(a), y + ring[4] * 0.35, ring[2] * math.sin(a), ring[4], stone)
			end
		end
		ball(c, 0, y + 0.6, 0, 1.5, stone)
		box(c, 0, y + 1.25, 0, 0.45, 0.35, 0.45, stone)
		col(c, 0, y + 1.6, 0, 0.8, 0.22, stone)
	end

	-- 에베레스트: 빙하 바닥 + 눈 덮인 사각뿔 주봉(앞으로 뻗은 능선) + 뒤 오른쪽 로체 + 앞 왼쪽 눕체
	--   + 정상에서 옆으로 흩날리는 눈보라 깃 + 베이스캠프 텐트 + 오색 타르초(룽다)
	function B.everest(c)
		local snow, rock = c.P, c.S
		local g = 0.35
		box(c, 0, 0, 0, 9.8, g, 9.8, mix(c.S, WHITE, 0.7), Mat.Glacier)
		peak(
			c,
			V(-0.2, 9.6, 1),
			{ V(-4.7, g, -0.4), V(0.4, g, -4.4), V(4.6, g, 0.3), V(-0.4, g, 4.7) },
			rock,
			snow,
			{ 0.68, 0.6, 0.72, 0.6 }
		)
		local lhotse = { V(1.4, g, 0.4), V(4.8, g, 1.1), V(3.8, g, 4.8) }
		peak(c, V(3.2, 7.6, 2.8), lhotse, mix(rock, WHITE, 0.1), snow, { 0.55, 0.62, 0 })
		local nuptse = { V(-4.8, g, -1.1), V(-2.4, g, -4.8), V(-0.4, g, -1.4) }
		peak(c, V(-2.8, 6.4, -2.4), nuptse, mix(rock, WHITE, 0.18), snow, { 0.5, 0.55, 0 })
		ball(c, 0.55, 9.25, 1, 1.6, CLOUD, Mat.SmoothPlastic, 0.3)
		gable(c, 2.9, g, -4.1, 1.1, 0.9, 0.65, c.A)
		col(c, 1.1, g, -4.3, 1.9, 0.1, WOOD, Mat.Wood)
		local flags = { rgb(40, 90, 220), rgb(220, 40, 40), rgb(40, 170, 70), rgb(250, 210, 40) }
		for k, color in flags do
			local t = k / 5
			local p = V(1.1 + 3.5 * t, 2.2 - 1.4 * t, -4.3 + 1.1 * t)
			block(
				c,
				CFrame.new(p.X, p.Y - 0.2, p.Z) * CFrame.Angles(0, -0.3, 0),
				V(0.35, 0.35, 0.04),
				color,
				Mat.Fabric
			)
		end
	end

	-- 마우솔로스 영묘: 계단 기단 + 높은 대리석 받침(부조 띠·코니스) + 이오니아식 열주로 두른 안채
	--   + 24단 계단식 피라미드 지붕(6단으로 줄임) + 꼭대기 청동 4두 전차
	function B.mausoleum(c)
		local marble, stone, gold = c.P, c.S, c.A
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(stone, WHITE, 0.3))
		box(c, 0, 0.25, 0, 7.6, 0.5, 6.4, stone)
		box(c, 0, 0.75, 0, 7, 4.2, 5.8, marble)
		box(c, 0, 3.8, 0, 7.06, 0.6, 5.86, stone)
		box(c, 0, 4.95, 0, 7.3, 0.35, 6.1, stone)
		box(c, 0, 0.75, -2.92, 1, 1.6, 0.06, DARK)
		local y = 5.3
		box(c, 0, y, 0, 4.6, 2.2, 3.4, mix(marble, stone, 0.35))
		for _, x in { -3, -1.5, 0, 1.5, 3 } do
			for _, sz in { -1, 1 } do
				col(c, x, y, sz * 2.4, 2.2, 0.42, marble)
			end
		end
		for _, sx in { -1, 1 } do
			for _, z in { -0.8, 0.8 } do
				col(c, sx * 3, y, z, 2.2, 0.42, marble)
			end
		end
		y += 2.2
		box(c, 0, y, 0, 6.8, 0.5, 5.6, marble)
		y += 0.5
		for k = 0, 5 do
			box(c, 0, y, 0, 6.4 - k * 0.8, 0.45, 5.2 - k * 0.7, marble)
			y += 0.45
		end
		box(c, 0, y, 0, 1.6, 0.5, 1.4, stone)
		y += 0.5
		box(c, 0, y, -0.2, 1.2, 0.35, 0.6, mix(gold, BLACK, 0.35), Mat.Metal)
		box(c, 0, y + 0.35, -0.2, 1.3, 0.4, 0.85, gold, Mat.Metal)
		for k = 0, 3 do
			local cf = CFrame.new(-0.48 + k * 0.32, y + 0.95, -0.62) * CFrame.Angles(0.5, 0, 0)
			block(c, cf, V(0.2, 0.55, 0.25), gold, Mat.Metal)
		end
		box(c, 0, y + 0.2, 0.45, 0.8, 0.5, 0.45, gold, Mat.Metal)
		col(c, 0, y + 0.7, 0.45, 0.6, 0.3, gold, Mat.Metal)
		ball(c, 0, y + 1.45, 0.45, 0.3, gold, Mat.Metal)
	end

	-- 트로이 목마: 모래밭 + 뒤쪽 트로이 성벽(탑·성가퀴·성문) + 바퀴 달린 받침 위의 거대한 나무 말
	--   (통나무 몸통, 굵은 네 다리, 치켜든 목과 머리, 갈기, 꼬리, 옆구리 비밀 문). 앞 왼쪽을 보며 옆모습이 보이게 비스듬히 섬
	function B.trojanhorse(c)
		local wood, dark = c.P, c.S
		local stone = rgb(205, 188, 150)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, SAND, Mat.Sand)
		box(c, 0, 0.2, 4.3, 9.8, 3.4, 1.2, stone, Mat.Sandstone)
		for _, sx in { -1, 1 } do
			box(c, sx * 4.1, 0.2, 4.1, 1.6, 4.8, 1.6, stone, Mat.Sandstone)
		end
		for _, x in { -2.6, -1.3, 0, 1.3, 2.6 } do
			box(c, x, 3.6, 3.9, 0.6, 0.5, 0.4, stone, Mat.Sandstone)
		end
		box(c, 0, 0.2, 3.68, 1.6, 2.2, 0.1, DARK)
		-- 말(로컬 좌표: 머리가 -X)
		c.origin = CFrame.new(0.2, 0, -0.9) * CFrame.Angles(0, -0.45, 0)
		box(c, 0, 0.75, 0, 6.2, 0.4, 2.4, dark)
		for _, s in CORNERS do
			cyl(c, CFrame.new(s[1] * 2.3, 0.75, s[2] * 1.35) * ALONG_Z, 0.3, 1.5, dark)
			box(c, s[1] * 1.9, 1.15, s[2] * 0.65, 0.6, 2.6, 0.6, wood)
		end
		cyl(c, CFrame.new(0, 4.6, 0), 5.4, 2.6, wood)
		ball(c, -2.5, 4.75, 0, 2.5, wood)
		ball(c, 2.5, 4.7, 0, 2.5, wood)
		beam(c, V(-2.5, 5.2, 0), V(-3.4, 8, 0), 1.3, wood)
		block(c, CFrame.new(-3.9, 8.1, 0) * CFrame.Angles(0, 0, 0.45), V(2, 1, 1), wood)
		beam(c, V(-1.8, 5.45, 0), V(-2.7, 8.25, 0), 0.4, dark)
		beam(c, V(2.9, 5.3, 0), V(3.5, 2.6, 0), 0.45, dark)
		for _, sz in { -1, 1 } do
			box(c, -3.1, 8.8, sz * 0.3, 0.25, 0.7, 0.2, wood)
			box(c, -4.1, 8.05, sz * 0.51, 0.25, 0.25, 0.05, DARK)
			box(c, 0, 3.95, sz * 1.17, 4.6, 0.08, 0.06, dark)
		end
		box(c, 0.2, 4.3, -1.31, 1.2, 0.9, 0.05, dark)
		c.origin = CFrame.new()
	end

	-- 용궁: 모래 바닥 + 자개빛 기단 위 붉은 2층 전각(청록 기와, 빛나는 문) + 꼭대기 여의주
	--   + 전각을 휘감아 오르는 황금 용(머리·턱·뿔·물고 있는 여의주) + 산호 + 다시마 + 물방울
	function B.yonggung(c)
		local gold = rgb(240, 190, 60)
		local nacre = mix(WHITE, c.P, 0.15)
		col(c, 0, 0, 0, 0.4, 9.8, mix(SAND, c.S, 0.3), Mat.Sand)
		box(c, 0, 0.4, 0.8, 6.4, 0.7, 5.4, nacre, Mat.Marble)
		box(c, 0, 1.1, 0.9, 5, 2, 3.8, c.P)
		box(c, 0, 1.1, -1.02, 1.3, 1.5, 0.1, c.A, Mat.Neon)
		roof(c, 0, 3.1, 0.9, 7, 5.4, 1.2, c.S)
		box(c, 0, 4.1, 0.9, 3.2, 1.6, 2.6, c.P)
		roof(c, 0, 5.7, 0.9, 5, 3.8, 1.1, c.S)
		ball(c, 0, 7.3, 0.9, 0.7, c.A, Mat.Neon)
		-- 황금 용(꼬리 → 목): 굽이치며 전각 뒤를 돌아 오른쪽 앞에서 머리를 들고 정면을 봄
		local path = {
			V(-3.6, 0.9, -3.4),
			V(-4.3, 2.6, -0.8),
			V(-3.9, 5.2, 2.2),
			V(-1.2, 8.2, 3.6),
			V(1.8, 9.2, 2.4),
			V(3.6, 7, 0.4),
			V(3.2, 8.4, -2),
		}
		for k = 1, #path - 1 do
			local t = 0.4 + k * 0.08
			beam(c, path[k], path[k + 1], t, gold, Mat.Metal)
			if k > 1 then
				ball(c, path[k].X, path[k].Y, path[k].Z, t * 1.15, gold, Mat.Metal)
			end
		end
		local head = CFrame.lookAt(path[#path], V(1.4, 7.4, -4.4))
		block(c, head * CFrame.new(0, 0.1, -0.6), V(1.3, 0.9, 1.8), gold, Mat.Metal)
		block(c, head * CFrame.new(0, -0.5, -0.9) * CFrame.Angles(-0.4, 0, 0), V(1, 0.3, 1.4), gold, Mat.Metal)
		for _, sx in { -1, 1 } do
			local root = (head * CFrame.new(sx * 0.35, 0.5, 0)).Position
			beam(c, root, (head * CFrame.new(sx * 0.75, 1.5, 0.8)).Position, 0.18, CLOUD)
		end
		local pearl = (head * CFrame.new(0, -0.25, -1.85)).Position
		ball(c, pearl.X, pearl.Y, pearl.Z, 0.75, c.A, Mat.Neon)
		-- 산호, 다시마, 물고기, 물방울
		ball(c, 3.9, 0.7, -3.4, 1.2, rgb(255, 120, 150))
		ball(c, 4, 0.6, 3.5, 0.9, rgb(170, 110, 230))
		for _, k in { { -2.4, -3.9, 2.4, 0.15 }, { 4.3, 1.4, 2.8, 0.1 } } do
			local cf = CFrame.new(k[1], 0.4 + k[3] / 2, k[2]) * CFrame.Angles(k[4], 0, k[4])
			block(c, cf, V(0.25, k[3], 0.5), rgb(60, 150, 80))
		end
		ball(c, -1.6, 3.8, -3.2, 0.7, rgb(255, 150, 60))
		wedge(c, CFrame.new(-1.05, 3.8, -3.2) * CFrame.Angles(0, PI / 2, 0), V(0.1, 0.6, 0.5), rgb(255, 150, 60))
		ball(c, -1.6, 9.4, 1.6, 0.5, c.A, Mat.Glass, 0.5)
	end

	return B
end
