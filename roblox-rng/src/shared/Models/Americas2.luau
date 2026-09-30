-- 아메리카(2) 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 마추픽추(terraces) 는 원래 그 명소를 위해 만든 모양을 그대로 씀.

return function(K)
	local B = {}

	local V, rgb, Mat, PI, TAU = K.V, K.rgb, K.Mat, K.PI, K.TAU
	local UPRIGHT, ALONG_Z = K.UPRIGHT, K.ALONG_Z
	local GRASS, LEAF, WATER, DARK, TILE = K.GRASS, K.LEAF, K.WATER, K.DARK, K.TILE
	local ROCK, WOOD, SAND, CLOUD, BLACK, WHITE = K.ROCK, K.WOOD, K.SAND, K.CLOUD, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local archCorner, gable, plant = K.archCorner, K.gable, K.plant

	-- a 에서 b 까지 이어지는 원기둥(지름 d). a → b 는 수직이 아니어야 함
	local function rod(c, a, b, d, color, material, transparency)
		local mid = (a + b) / 2
		return cyl(
			c,
			CFrame.lookAt(mid, b) * CFrame.Angles(0, PI / 2, 0),
			(b - a).Magnitude,
			d,
			color,
			material,
			transparency
		)
	end

	-- 정면(-Z)에서 삼각형으로 보이는 봉우리(쐐기 두 개): 바닥 y, 꼭짓점에서 -X 쪽 폭 wl, +X 쪽 폭 wr, 깊이 d, 높이 h
	local function peak(c, x, y, z, wl, wr, d, h, color, material)
		wedge(c, CFrame.new(x - wl / 2, y + h / 2, z) * CFrame.Angles(0, PI / 2, 0), V(d, h, wl), color, material)
		wedge(c, CFrame.new(x + wr / 2, y + h / 2, z) * CFrame.Angles(0, -PI / 2, 0), V(d, h, wr), color, material)
	end

	-- 침엽수(원기둥 두 단)
	local function pine(c, x, y, z, h, d, color)
		col(c, x, y, z, h * 0.5, d, color, Mat.Grass)
		col(c, x, y + h * 0.45, z, h * 0.55, d * 0.55, color, Mat.Grass)
	end

	-- 꺾은선(점 목록 xs, ys)에서 x 위치의 높이
	local function along(xs, ys, x)
		for k = 1, #xs - 1 do
			if x >= xs[k] and x <= xs[k + 1] then
				local t = (x - xs[k]) / (xs[k + 1] - xs[k])
				return ys[k] + (ys[k + 1] - ys[k]) * t
			end
		end
		return ys[#ys]
	end

	-- 워싱턴 기념탑: 내셔널 몰 잔디(십자 산책로 + 앞쪽 반사 연못) + 둔덕 위 광장 + 둘레의 성조기
	--   + 아주 가늘고 높은 흰 대리석 오벨리스크(아래 1/4 은 색이 살짝 다름) + 피라미드 꼭대기 + 전망 창
	B.washingtonmonument = function(c)
		local path = rgb(226, 218, 200)
		local lower = mix(c.P, rgb(214, 196, 168), 0.45)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, GRASS, Mat.Grass)
		box(c, 0, 0.3, 0, 9.8, 0.04, 0.7, path, Mat.Concrete)
		box(c, 0, 0.3, 0, 0.7, 0.04, 9.8, path, Mat.Concrete)
		box(c, 0, 0.3, -3.95, 3.2, 0.16, 1.7, mix(c.P, ROCK, 0.3))
		box(c, 0, 0.3, -3.95, 2.8, 0.2, 1.3, WATER, Mat.Glass, 0.1)
		col(c, 0, 0.3, 0, 0.5, 6, mix(GRASS, LEAF, 0.2), Mat.Grass)
		col(c, 0, 0.8, 0, 0.15, 3.6, path, Mat.Concrete)
		local flags = { rgb(205, 50, 60), rgb(45, 65, 140) }
		for i = 0, 7 do
			local a = (i + 0.5) / 8 * TAU
			local x, z = 2.45 * math.cos(a), 2.45 * math.sin(a)
			col(c, x, 0.8, z, 1.8, 0.08, WHITE, Mat.Metal)
			box(c, x + 0.24, 2.05, z, 0.46, 0.3, 0.05, flags[i % 2 + 1], Mat.Fabric)
		end
		local y = 0.95
		for k, t in { { 2.1, 5 }, { 2, 4.6 }, { 1.88, 4.4 }, { 1.76, 4.4 } } do
			box(c, 0, y, 0, t[1], t[2], t[1], if k == 1 then lower else c.P)
			y += t[2]
		end
		for _, x in { -0.4, 0.4 } do
			box(c, x, y - 1.2, -0.89, 0.22, 0.4, 0.04, DARK)
		end
		for _, t in { { 1.45, 0.55 }, { 1.08, 0.55 }, { 0.7, 0.5 }, { 0.32, 0.45 } } do
			box(c, 0, y, 0, t[1], t[2], t[1], c.P)
			y += t[2]
		end
		ball(c, 0, y, 0, 0.2, c.A, Mat.Metal)
	end

	-- 브루클린 다리: 강 + 뒤쪽 맨해튼 빌딩 + 비스듬히 놓인 다리(아치 면과 케이블 옆모습이 함께 보이게)
	--   + 양 끝 석조 앵커리지 + 상판이 뚫고 지나가는 뾰족 고딕 아치 두 개짜리 화강암 탑 2개(코니스)
	--   + 탑 꼭대기에서 늘어진 주 케이블 + 탑에서 부챗살처럼 내려오는 사선 케이블(거미줄)
	B.brooklynbridge = function(c)
		local stone = c.P
		local steel = c.S
		local deckY, deckTop = 2.6, 3
		local tx, archTop, top = 2.2, 7.2, 8.8
		local ax = 3.9
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, WATER, Mat.Glass, 0.1)
		for _, b in { { -3.9, 3.9, 1.6, 5.2 }, { -2.3, 4.2, 1.2, 3.6 }, { -4.1, 2.2, 1.2, 2.8 } } do
			box(c, b[1], 0.25, b[2], b[3], b[4], b[3], mix(steel, WHITE, 0.35), Mat.Concrete)
		end
		local rot = CFrame.Angles(0, -0.5, 0)
		c.origin = rot
		for _, sx in { -1, 1 } do
			box(c, sx * ax, 0.25, 0, 1.1, 2.9, 2.6, mix(stone, ROCK, 0.3))
		end
		box(c, 0, deckY, 0, 2 * ax, deckTop - deckY, 2.4, steel)
		for _, sx in { -1, 1 } do
			local x = sx * tx
			box(c, x, 0.25, 0, 1.2, deckY - 0.25, 3.6, stone)
			for _, z in { -1.58, 0, 1.58 } do
				box(c, x, deckY, z, 1, archTop - deckY, if z == 0 then 0.5 else 0.45, stone)
			end
			box(c, x, archTop, 0, 1, 1.4, 3.6, stone)
			box(c, x, archTop + 1.4, 0, 1.2, 0.35, 3.8, mix(stone, WHITE, 0.2))
			-- 뾰족 아치: 길이 방향이 X 인 개구부라 좌표계를 90도 돌려 archCorner 를 씀
			c.origin = rot * CFrame.new(x, 0, 0) * CFrame.Angles(0, PI / 2, 0)
			for _, w in { { -1.35, -0.25 }, { 0.25, 1.35 } } do
				archCorner(c, w[1], archTop, 0, 0.55, 1, stone, -1)
				archCorner(c, w[2], archTop, 0, 0.55, 1, stone, 1)
			end
			c.origin = rot
		end
		local xs = { -tx, -tx / 2, 0, tx / 2, tx }
		local ys = {}
		for k, x in xs do
			ys[k] = deckTop + 0.35 + (top - deckTop - 0.35) * (x / tx) ^ 2
		end
		for _, z in { -1.1, 1.1 } do
			for k = 1, 4 do
				rod(c, V(xs[k], ys[k], z), V(xs[k + 1], ys[k + 1], z), 0.18, steel)
			end
			for _, sx in { -1, 1 } do
				rod(c, V(sx * tx, top, z), V(sx * ax, 3.15, z), 0.18, steel)
				beam(c, V(sx * (tx - 0.3), top - 0.5, z), V(sx * 0.7, deckTop, z), 0.07, steel)
			end
		end
		c.origin = CFrame.new()
	end

	-- 금문교: 바다 + 뒤쪽 마린 헤드랜즈 언덕 + 양 끝 앵커리지 + 주황 상판
	--   + 다리 두 개가 위로 갈수록 가늘어지는 아르데코 탑(가로보 3단) + 크게 늘어진 주 케이블 + 수직 멜대
	B.goldengate = function(c)
		local red = c.P
		local concrete = rgb(205, 200, 190)
		local deckY, deckTop = 2.6, 3.1
		local tx, top = 2.7, 11.9
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, WATER, Mat.Glass, 0.1)
		col(c, 3.5, 0.25, 3.5, 1.1, 2.8, mix(GRASS, SAND, 0.35), Mat.Grass)
		col(c, 3.7, 1.35, 3.7, 0.9, 1.6, mix(GRASS, SAND, 0.2), Mat.Grass)
		for _, sx in { -1, 1 } do
			box(c, sx * 4.5, 0.25, 0, 0.8, 3.1, 2.6, concrete)
		end
		box(c, 0, deckY, 0, 9.8, deckTop - deckY, 2.2, red)
		for _, sx in { -1, 1 } do
			local x = sx * tx
			box(c, x, 0.25, 0, 1.4, 0.9, 2.8, concrete)
			for _, sz in { -1, 1 } do
				box(c, x, 1.15, sz, 0.72, 5.4, 0.62, red)
				box(c, x, 6.55, sz, 0.56, top + 0.25 - 6.55, 0.5, red)
			end
			for _, s in { { 5.6, 0.5 }, { 8.5, 0.45 }, { 11.2, 0.7 } } do
				box(c, x, s[1], 0, 0.42, s[2], 1.6, red)
			end
		end
		local xs = { -tx, -tx / 2, 0, tx / 2, tx }
		local ys = {}
		for k, x in xs do
			ys[k] = deckTop + 0.35 + (top - deckTop - 0.35) * (x / tx) ^ 2
		end
		for _, z in { -1, 1 } do
			for k = 1, 4 do
				rod(c, V(xs[k], ys[k], z), V(xs[k + 1], ys[k + 1], z), 0.2, red)
			end
			for _, sx in { -1, 1 } do
				rod(c, V(sx * tx, top, z), V(sx * 4.5, 3.35, z), 0.2, red)
			end
			for _, x in { -2, -0.8, 0.8, 2 } do
				local y = along(xs, ys, x)
				box(c, x, deckTop, z, 0.06, y - deckTop, 0.06, red)
			end
		end
	end

	-- 피통스: 바다 + 뒤쪽 섬 해안 + 숲에 덮인 둥근 원뿔 봉우리 둘(왼쪽 넓은 그로 피통, 오른쪽 가파른 프티 피통, 드러난 바위 벽)
	--   + 두 봉우리 사이 모래 해변(야자수, 오두막) + 앞바다의 돛단배
	B.pitons = function(c)
		local green = c.P
		local dark = mix(c.P, BLACK, 0.3)
		local lush = mix(c.P, LEAF, 0.5)
		local rock = mix(ROCK, c.P, 0.25)
		local crag = mix(c.P, ROCK, 0.5)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		box(c, 0, 0.3, 3.7, 9.8, 0.5, 2.4, dark, Mat.Grass)
		-- 봉우리: 얇게 쌓아 올린 원기둥 원뿔(조금씩 기울어짐) + 둥근 꼭대기 + 비탈의 숲 덩어리
		local function piton(x, z, base, top, height, layers, lean)
			local step = height / layers
			for k = 0, layers - 1 do
				local d = base + (top - base) * k / (layers - 1)
				local t = k / (layers - 1)
				local color = if t < 0.5 then mix(dark, green, t * 2) else mix(green, crag, (t - 0.5) * 2)
				col(c, x + lean * k, 0.3 + k * step, z, step + 0.02, d, color, Mat.Grass)
			end
			ball(c, x + lean * layers, 0.3 + height, z, top * 1.05, crag, Mat.Grass)
		end
		piton(-2.1, 1.4, 5.6, 1.3, 6.8, 6, 0.03)
		piton(2.6, -0.1, 4.4, 0.9, 7.2, 7, -0.04)
		for _, p in
			{
				{ -4.1, 1.6, 0.4, 1.4 },
				{ -1.1, 2.6, -0.8, 1.4 },
				{ -2.7, 4.2, -0.2, 1.2 },
				{ 1.4, 2.2, -0.6, 1.2 },
				{ 3.6, 3.4, -0.5, 1 },
				{ 2.3, 5, -0.4, 0.9 },
			}
		do
			ball(c, p[1], p[2], p[3], p[4], lush, Mat.Grass)
		end
		block(c, CFrame.new(-2, 3.6, -0.6) * CFrame.Angles(0.4, 0.15, 0), V(1.2, 2.4, 0.4), rock)
		block(c, CFrame.new(2.9, 4.4, -1.1) * CFrame.Angles(0.3, -0.5, 0), V(0.7, 2.4, 0.3), rock)
		box(c, 0.3, 0.3, -1.7, 2.4, 0.12, 1.3, SAND, Mat.Sand)
		plant(c, -0.3, 0.42, -1.5, 1.3, 0.8, LEAF)
		plant(c, 0.9, 0.42, -1.9, 1.1, 0.7, LEAF)
		box(c, 0.4, 0.42, -1.2, 0.6, 0.4, 0.5, WHITE)
		local boat = CFrame.new(0.8, 0.3, -3.5) * CFrame.Angles(0, 0.6, 0)
		block(c, boat * CFrame.new(0, 0.12, 0), V(0.5, 0.25, 1.5), WHITE)
		wedge(c, boat * CFrame.new(0, 0.25 + 0.9, 0.05), V(0.05, 1.8, 1.1), c.A)
	end

	-- 올드 페이스풀: 풀밭 + 흰 규화물(간헐천 둔덕) + 주황 미생물 물길 + 위로 갈수록 넓어지는 흰 물기둥
	--   + 꼭대기에서 부채꼴로 떨어지는 물보라 + 바람에 밀려 나는 수증기 구름
	--   + 앞쪽 나무 관람 데크와 관광객 + 로지폴 소나무 + 작은 온천 웅덩이
	B.oldfaithful = function(c)
		local sinter = c.P
		local steam = c.S
		local meadow = mix(GRASS, SAND, 0.45)
		local pineColor = rgb(40, 90, 55)
		local foam = mix(steam, c.A, 0.25)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, meadow, Mat.Grass)
		local vx, vz = 0, 0.6
		col(c, vx, 0.3, vz, 0.35, 6.6, mix(sinter, WHITE, 0.45), Mat.Rock)
		col(c, vx + 0.2, 0.65, vz, 0.35, 4.2, mix(sinter, WHITE, 0.25), Mat.Rock)
		col(c, vx, 1, vz, 0.35, 2.2, sinter, Mat.Rock)
		block(
			c,
			CFrame.new(-1.7, 0.33, -2.2) * CFrame.Angles(0, 0.5, 0),
			V(0.55, 0.1, 2.4),
			rgb(215, 130, 55),
			Mat.Ground
		)
		block(c, CFrame.new(1.9, 0.33, -2) * CFrame.Angles(0, -0.6, 0), V(0.45, 0.1, 2), rgb(200, 150, 70), Mat.Ground)
		-- 물기둥(위로 갈수록 넓고 옅어짐) + 밑의 물보라 + 떨어지는 물방울 + 바람에 밀려 나는 수증기
		col(c, vx, 1.35, vz, 0.8, 3.2, steam, Mat.Glass, 0.45)
		local y = 1.35
		for _, p in { { 2.4, 1.3, 0.05 }, { 3, 1.8, 0.12 }, { 2.6, 2.3, 0.2 }, { 1.4, 2.6, 0.35 } } do
			col(c, vx, y, vz, p[1], p[2], steam, Mat.Glass, p[3])
			y += p[1]
		end
		for i = 0, 5 do
			local a = i / 6 * TAU + 0.4
			local r = 1.5 + (i % 2) * 0.5
			ball(c, vx + r * math.cos(a), 4.6 + (i % 3) * 1.3, vz + r * math.sin(a), 0.45, foam, Mat.Glass, 0.2)
		end
		for _, p in
			{ { 0.3, 11.4, 3.3, 0.25 }, { 1.2, 13.6, 3.8, 0.35 }, { 2.1, 16, 3.6, 0.5 }, { 2.9, 18.3, 2.8, 0.65 } }
		do
			ball(c, vx + p[1], p[2], vz + 0.2, p[3], CLOUD, Mat.SmoothPlastic, p[4])
		end
		for _, a in { -0.62, 0, 0.62 } do
			block(c, CFrame.Angles(0, a, 0) * CFrame.new(0, 0.42, -4.1), V(2.6, 0.12, 0.6), WOOD, Mat.WoodPlanks)
		end
		for k, x in { -1.1, -0.2, 0.9 } do
			local shirt = ({ rgb(210, 60, 60), rgb(60, 110, 200), rgb(240, 190, 60) })[k]
			col(c, x, 0.48, -4.2, 0.55, 0.28, shirt)
			ball(c, x, 1.15, -4.2, 0.24, rgb(235, 200, 170))
		end
		for _, p in { { -3.8, 3.4, 3.6 }, { -2.3, 4.1, 3 }, { 3.9, 3.4, 3.2 }, { -4, 0.2, 2.4 } } do
			pine(c, p[1], 0.3, p[2], p[3], 1.1, pineColor)
		end
		col(c, 3.3, 0.3, -0.6, 0.06, 1.8, rgb(225, 150, 60), Mat.Ground)
		col(c, 3.3, 0.3, -0.6, 0.1, 1.3, c.A, Mat.Glass, 0.05)
	end

	-- 모레인 호수: 짙은 숲 바닥 + 청록 호수 + 앞의 바위 더미 + 빨간 카누
	--   + 뒤쪽 너덜 비탈과 산벽 + 들쭉날쭉한 텐 피크(앞줄 회색 바위, 뒷줄 눈 봉우리) + 호숫가 침엽수
	B.morainelake = function(c)
		local rock = c.S
		local snow = c.A
		local forest = rgb(38, 92, 60)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(rock, LEAF, 0.45), Mat.Grass)
		box(c, 0.2, 0.3, -1.2, 7.2, 0.1, 5.4, c.P, Mat.Glass, 0.05)
		wedge(c, CFrame.new(0, 0.3 + 1.5, 2.3), V(9.8, 3, 1.6), mix(rock, WHITE, 0.15), Mat.Slate)
		box(c, 0, 0.3, 4, 9.8, 3.4, 1.8, rock, Mat.Slate)
		box(c, 1, 2.2, 3.08, 2.6, 0.8, 0.1, snow, Mat.Snow)
		for _, p in { { 2.9, 1.3, 1.4, 6.2 }, { 0.4, 1.3, 1.2, 6.8 }, { -2.3, 1.4, 1.3, 6 }, { -4.2, 0.7, 0.7, 5 } } do
			peak(c, p[1], 3.4, 4.4, p[2], p[3], 0.9, p[4], snow, Mat.Snow)
		end
		for _, p in { { 3.9, 1, 1, 3.6 }, { 1.7, 1.2, 1.2, 4.6 }, { -0.8, 1.3, 1.3, 4 }, { -3.4, 1.5, 1.3, 4.8 } } do
			peak(c, p[1], 3, 3.5, p[2], p[3], 0.8, p[4], rock, Mat.Slate)
		end
		for _, p in { { -3.4, -3.9, 1.3, 0.3 }, { -2.3, -4.1, 1, -0.4 }, { -4, -3.1, 0.9, 0.7 } } do
			block(
				c,
				CFrame.new(p[1], 0.3 + p[3] * 0.4, p[2]) * CFrame.Angles(0.2, p[4], 0.15),
				V(p[3], p[3] * 0.8, p[3]),
				ROCK,
				Mat.Slate
			)
		end
		local canoe = rgb(205, 45, 40)
		block(c, CFrame.new(1.4, 0.45, -2) * CFrame.Angles(0, 0.4, 0), V(0.32, 0.14, 1.3), canoe)
		block(c, CFrame.new(-0.6, 0.45, -2.8) * CFrame.Angles(0, -0.3, 0), V(0.32, 0.14, 1.3), canoe)
		for _, p in { { 4.3, -2.6 }, { 4.3, -0.6 }, { 4.4, 1.2 }, { -4.2, -2.8 }, { -4.3, -0.9 }, { -4.2, 0.9 } } do
			pine(c, p[1], 0.3, p[2], 2.4, 0.95, forest)
		end
	end

	-- 파나마 운하: 밀림 땅 + 계단처럼 한 단씩 높아지는 갑문 3칸(물 높이가 다른 두 줄 수로, 콘크리트 벽) + 갑문 문짝
	--   + 가운데 칸의 컨테이너선(선수, 색색의 컨테이너, 흰 선교) + 벽 위 전기 기관차(뮬)와 견인줄 + 관제탑 + 예인선
	B.panamacanal = function(c)
		local concrete = c.P
		local water = c.S
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(GRASS, LEAF, 0.4), Mat.Grass)
		local sections = { { -4.9, -2.4, 1 }, { -2.4, 2.4, 1.9 }, { 2.4, 4.9, 2.8 } }
		for _, s in sections do
			local cx, w, level = (s[1] + s[2]) / 2, s[2] - s[1], s[3]
			box(c, cx, 0.3, 0, w, level - 0.3, 5.6, water, Mat.Glass, 0.1)
			for _, z in { -3.2, 0, 3.2 } do
				box(c, cx, 0.3, z, w, level - 0.1, 0.8, concrete)
			end
		end
		local steel = rgb(70, 75, 85)
		for k, gx in { -2.4, 2.4 } do
			for _, z in { -1.6, 1.6 } do
				box(c, gx, 0.3, z, 0.25, sections[k + 1][3] - 0.05, 2.4, steel, Mat.Metal)
			end
		end
		-- 컨테이너선(앞 수로, 가운데 칸)
		local sz = -1.6
		local hull = rgb(45, 55, 75)
		box(c, 0.2, 1.3, sz, 3.4, 1.3, 1.7, hull, Mat.Metal)
		block(c, CFrame.new(-1.5, 1.95, sz) * CFrame.Angles(0, PI / 4, 0), V(1.2, 1.3, 1.2), hull, Mat.Metal)
		local boxes = {
			{ -1, 1.2, c.A },
			{ -0.15, 0.9, rgb(50, 110, 190) },
			{ 0.7, 1.2, rgb(190, 60, 50) },
		}
		for _, b in boxes do
			box(c, b[1], 2.6, sz, 0.8, b[2], 1.5, b[3], Mat.Metal)
		end
		box(c, 1.6, 2.6, sz, 0.6, 1.7, 1.6, WHITE)
		box(c, 1.75, 4.3, sz, 0.3, 0.45, 0.35, rgb(190, 60, 50))
		-- 유람선(뒤 수로, 가운데 칸)
		box(c, 0.3, 1.4, 1.6, 2.8, 0.9, 1.3, WHITE)
		box(c, 0.5, 2.3, 1.6, 2, 0.55, 1, mix(WHITE, WATER, 0.2))
		-- 뮬(전기 기관차)과 견인줄
		local silver = rgb(200, 205, 210)
		for _, z in { -3.2, 0 } do
			box(c, -1.6, 2.1, z, 0.7, 0.45, 0.5, silver, Mat.Metal)
			beam(c, V(-1.6, 2.45, z), V(-1.3, 2.5, sz + (if z < sz then -0.8 else 0.8)), 0.05, DARK)
		end
		-- 관제탑(가운데 벽, 높은 칸)
		box(c, 3.6, 3, 0, 1.2, 1.1, 1.2, WHITE)
		gable(c, 3.6, 4.1, 0, 1.4, 1.4, 0.55, rgb(175, 75, 55))
		-- 예인선(뒤 수로, 낮은 칸)
		box(c, -3.7, 0.8, 1.6, 1.4, 0.4, 0.8, rgb(200, 70, 50))
		box(c, -3.5, 1.2, 1.6, 0.6, 0.45, 0.6, WHITE)
		for _, p in { { -3.6, 4.4 }, { -1.2, 4.3 }, { 1.4, 4.4 }, { 3.8, 4.3 }, { -3, -4.3 }, { 2.6, -4.3 } } do
			ball(c, p[1], 0.9, p[2], 1.2, LEAF, Mat.Grass)
		end
	end

	-- 페리토 모레노 빙하: 우윳빛 청록 호수 + 뒤쪽 설산에서 흘러내려 호수에 닿는 거대한 빙하
	--   (높이·앞뒤가 들쭉날쭉한 푸른 얼음 절벽 + 꼭대기의 뾰족한 세락 + 뒤로 솟는 빙원) + 양옆 눈 덮인 바위산
	--   + 떠다니는 빙산 + 앞쪽 전망 반도(숲, 나무 데크) + 유람선
	B.peritomoreno = function(c)
		local ice = c.P
		local blue = c.S
		local deep = mix(blue, rgb(40, 90, 170), 0.35)
		local lake = rgb(105, 170, 190)
		local rockColor = rgb(120, 114, 108)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, lake, Mat.Glass, 0.1)
		box(c, 0, 0.3, 2.6, 8.2, 2.4, 4.8, ice, Mat.Ice)
		wedge(c, CFrame.new(0, 2.7 + 1.5, 3.6), V(8.2, 3, 2.8), ice, Mat.Ice)
		-- 얼음 절벽: { x, 폭, 높이, 앞면 z, 색 }
		local faces = {
			{ -3.3, 1.6, 2.5, -0.5, ice },
			{ -1.7, 1.7, 3, -0.9, mix(ice, blue, 0.3) },
			{ 0, 1.8, 2.6, -0.6, ice },
			{ 1.7, 1.7, 3.1, -1, mix(ice, blue, 0.4) },
			{ 3.3, 1.6, 2.4, -0.4, mix(ice, blue, 0.15) },
		}
		for _, f in faces do
			box(c, f[1], 0.3, (f[4] + 1) / 2, f[2], f[3], 1 - f[4], f[5], Mat.Ice)
		end
		for k, f in faces do
			local h = 0.8 + (k % 3) * 0.25
			local cf = CFrame.new(f[1] + (k % 2 - 0.5) * 0.4, 0.3 + f[3] + h / 2 - 0.3, f[4] + 0.35)
				* CFrame.Angles(0.15 * (k % 3 - 1), k * 0.7, 0.3 * ((k % 2) * 2 - 1))
			block(c, cf, V(0.7, h, 0.6), mix(ice, WHITE, 0.4), Mat.Ice)
		end
		for _, p in { { -2.6, 0.5 }, { 0.9, 0.7 }, { 2.6, 1.4 } } do
			block(c, CFrame.new(p[1], 2.8, p[2]) * CFrame.Angles(0, 0.6, 0.35), V(0.6, 0.8, 0.6), WHITE, Mat.Ice)
		end
		block(c, CFrame.new(-1.7, 1.6, -0.93) * CFrame.Angles(0, 0, 0.3), V(0.25, 2.2, 0.06), deep, Mat.Ice)
		block(c, CFrame.new(1.8, 1.8, -1.03) * CFrame.Angles(0, 0, -0.25), V(0.3, 2.4, 0.06), deep, Mat.Ice)
		for _, z in { 1.5, 2.2 } do
			box(c, 0, 2.7, z, 7.4, 0.04, 0.16, deep, Mat.Ice)
		end
		-- 양옆 바위산(눈 모자) + 뒤쪽 설산
		for _, sx in { -1, 1 } do
			local x = sx * 4.1
			local wl, wr = if sx > 0 then 1.6 else 0.8, if sx > 0 then 0.8 else 1.6
			local h, snow, lift = 5.4, 0.5, 0.12
			peak(c, x, 0.3, 2.8, wl, wr, 3, h, rockColor, Mat.Slate)
			local sh = h * snow + lift
			peak(c, x, 0.3 + h * (1 - snow), 2.75, wl * sh / h, wr * sh / h, 3.2, sh, WHITE, Mat.Snow)
		end
		peak(c, -1.4, 4.5, 4.55, 1.6, 1.5, 0.8, 3.2, mix(ice, WHITE, 0.5), Mat.Snow)
		peak(c, 1.5, 4.5, 4.55, 1.3, 1.6, 0.8, 2.6, mix(ice, WHITE, 0.5), Mat.Snow)
		for _, p in { { -1.6, -2.3, 0.9, 0.3 }, { 1, -2.1, 0.7, -0.5 }, { -3.4, -3.3, 0.6, 0.8 } } do
			block(
				c,
				CFrame.new(p[1], 0.4, p[2]) * CFrame.Angles(0.15, p[4], 0.1),
				V(p[3], 0.45, p[3] * 0.8),
				mix(ice, blue, 0.2),
				Mat.Ice
			)
		end
		box(c, 3.7, 0.3, -3.7, 2.4, 0.5, 2.4, rgb(70, 120, 70), Mat.Grass)
		ball(c, 4.2, 1.3, -3, 1.1, LEAF, Mat.Grass)
		ball(c, 3.1, 1.2, -4.3, 0.9, LEAF, Mat.Grass)
		box(c, 2.8, 0.8, -3.4, 0.35, 0.1, 1.6, WOOD, Mat.WoodPlanks)
		box(c, 2.2, 0.8, -2.7, 1.4, 0.1, 0.45, WOOD, Mat.WoodPlanks)
		box(c, -1.4, 0.3, -3.9, 1.6, 0.35, 0.6, WHITE)
		box(c, -1.2, 0.65, -3.9, 0.8, 0.3, 0.45, rgb(60, 90, 140))
	end

	-- 우유니 소금사막: 흰 소금 평원(앞쪽 육각형 소금 결정 무늬) + 뒤쪽 하늘을 비추는 물 거울(비친 구름, 분홍 노을)
	--   + 거대 선인장이 선 잉카와시 섬 + 지붕 짐칸 달린 지프 + 원뿔형 소금 더미
	B.uyuni = function(c)
		local salt = c.P
		local ridge = mix(salt, ROCK, 0.3)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, salt, Mat.Salt)
		box(c, 0, 0.3, 2.6, 9.8, 0.04, 4.6, c.S, Mat.Glass, 0.1)
		box(c, 0, 0.3, 4.4, 9.8, 0.05, 0.9, c.A, Mat.Glass, 0.2)
		-- 거울에 비친 구름
		for _, p in { { -1.5, 3.1, 2.2 }, { 1, 1.5, 1.6 }, { -3.8, 1.4, 1.2 } } do
			cyl(c, CFrame.new(p[1], 0.34, p[2]) * UPRIGHT, 0.04, p[3], CLOUD, Mat.SmoothPlastic, 0.1)
		end
		local r = 1.25
		local function hexagon(cx, cz, skip)
			for k = 0, 5 do
				if not skip[k] then
					local a1, a2 = k * PI / 3, (k + 1) * PI / 3
					local p1 = V(cx + r * math.cos(a1), 0.34, cz + r * math.sin(a1))
					local p2 = V(cx + r * math.cos(a2), 0.34, cz + r * math.sin(a2))
					block(c, CFrame.lookAt((p1 + p2) / 2, p2), V(0.16, 0.08, r + 0.14), ridge, Mat.Salt)
				end
			end
		end
		local h = r * math.sqrt(3)
		hexagon(-0.6, -2.4, {})
		hexagon(-0.6 + h * math.cos(PI / 6), -2.4 + h * math.sin(PI / 6), { [3] = true })
		-- 잉카와시 섬 + 선인장
		local ix, iz = 3, 3
		col(c, ix, 0.3, iz, 0.8, 3.6, rgb(150, 120, 95), Mat.Rock)
		col(c, ix + 0.2, 1.1, iz + 0.2, 0.7, 2.6, rgb(135, 108, 88), Mat.Rock)
		col(c, ix + 0.1, 1.8, iz + 0.3, 0.5, 1.5, rgb(125, 100, 82), Mat.Rock)
		local cactus = rgb(80, 130, 70)
		for _, p in { { 2, 2.3, 3.2, 1 }, { 3.3, 2.2, 4, -1 }, { 3.9, 3.7, 2.8, 1 } } do
			local x, z, ht, side = p[1], p[2], p[3], p[4]
			local base = 1.1
			col(c, x, base, z, ht, 0.45, cactus, Mat.Grass)
			box(c, x + side * 0.3, base + ht * 0.45, z, 0.5, 0.26, 0.26, cactus, Mat.Grass)
			col(c, x + side * 0.52, base + ht * 0.45, z, ht * 0.35, 0.32, cactus, Mat.Grass)
		end
		-- 지프(지붕 짐칸)
		local jeep = CFrame.new(-2.2, 0.3, 0.2) * CFrame.Angles(0, 0.35, 0)
		block(c, jeep * CFrame.new(0, 0.17, 0), V(2.2, 0.34, 1), DARK)
		block(c, jeep * CFrame.new(0, 0.65, 0), V(2.5, 0.65, 1.1), WHITE)
		block(c, jeep * CFrame.new(0.2, 1.26, 0), V(1.7, 0.57, 1.04), mix(c.S, DARK, 0.4), Mat.Glass)
		block(c, jeep * CFrame.new(0.2, 1.65, 0), V(1.75, 0.2, 1.1), rgb(230, 140, 60))
		for _, p in { { -3.8, -1.8 }, { -3.2, -3.2 } } do
			col(c, p[1], 0.3, p[2], 0.35, 0.85, WHITE, Mat.Salt)
			col(c, p[1], 0.65, p[2], 0.3, 0.45, WHITE, Mat.Salt)
		end
	end

	-- 그랜드 캐니언: 캐니언 바닥 + 굽이치는 콜로라도 강 + 뒤쪽 북쪽 가장자리의 층층이 물러나는 붉은 절벽(지층 색 띠)
	--   + 가운데 솟은 층층 뷰트(신전 바위) 둘 + 앞쪽 남쪽 가장자리(소나무, 데저트 뷰 망루)
	B.grandcanyon = function(c)
		local red = c.P
		local tan = c.S
		local schist = rgb(98, 78, 82)
		local supai = mix(red, tan, 0.45)
		local cream = rgb(236, 214, 170)
		local kaibab = rgb(214, 196, 160)
		local rim = rgb(60, 105, 65)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(schist, tan, 0.35), Mat.Slate)
		for _, s in { { -3, -1.4, 0.25 }, { 0.2, -1.9, -0.12 }, { 3.2, -1.5, 0.3 } } do
			block(c, CFrame.new(s[1], 0.33, s[2]) * CFrame.Angles(0, s[3], 0), V(3.4, 0.06, 0.7), c.A, Mat.Glass, 0.05)
		end
		-- 북쪽 가장자리: { 높이, 앞면 z, 색 }
		local y = 0.3
		for _, l in
			{ { 1.3, 1.2, schist }, { 1.8, 1.9, red }, { 1.4, 2.5, supai }, { 1.1, 3.1, cream }, { 0.6, 3.4, kaibab } }
		do
			box(c, 0, y, (l[2] + 4.9) / 2, 9.8, l[1], 4.9 - l[2], l[3], c.M)
			y += l[1]
		end
		for _, x in { -3.4, -0.6, 2.6 } do
			ball(c, x, y + 0.35, 4.3, 0.8, rim, Mat.Grass)
		end
		-- 층층 뷰트: { x, z, 가로, 세로, 층 높이들 }
		local function butte(x, z, w, d, heights)
			local colors = { schist, red, supai, cream, kaibab }
			local yy = 0.3
			for k, hgt in heights do
				local s = 1 - (k - 1) * 0.16
				box(c, x, yy, z, w * s, hgt, d * s, colors[k], c.M)
				yy += hgt
			end
		end
		butte(-2.4, 0.2, 2.8, 2.4, { 1.1, 1.6, 1.2, 0.9, 0.4 })
		butte(1.9, 0, 2.2, 1.9, { 1, 1.4, 1, 0.6 })
		butte(4.1, 0.5, 1.6, 2.4, { 1.3, 1.8, 1.4 })
		-- 남쪽 가장자리(앞 왼쪽) + 망루
		box(c, 3, 0.3, -4.1, 3.8, 0.9, 1.6, red, c.M)
		box(c, 3.2, 1.2, -4.3, 3.4, 0.35, 1.2, kaibab, c.M)
		pine(c, 1.8, 1.55, -4.3, 1.1, 0.6, rim)
		col(c, 4, 1.55, -4.2, 1.6, 0.8, rgb(170, 130, 100), Mat.Cobblestone)
		col(c, 4, 3.15, -4.2, 0.2, 0.95, rgb(150, 110, 85), Mat.Cobblestone)
	end

	-- 갈라파고스 제도: 바다 + 검은 용암 섬(초록 덤불) + 뒤쪽 붉은 응회암 분화구 + 바다에서 솟은 비스듬한 피너클 바위
	--   + 섬 앞쪽의 커다란 코끼리거북(둥근 등딱지, 긴 목) + 모래 해변의 바다사자 + 푸른발부비새 + 오푼티아 선인장 나무
	B.galapagos = function(c)
		local lava = mix(ROCK, BLACK, 0.45)
		local tuff = rgb(165, 105, 70)
		local shell = c.A
		local skin = rgb(115, 108, 95)
		local g = 0.65
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		box(c, -1, 0.3, 1.2, 7.8, 0.35, 7.4, lava, Mat.Basalt)
		box(c, -0.8, 0.3, -3.3, 5.8, 0.25, 2, SAND, Mat.Sand)
		-- 응회암 분화구
		col(c, -2.8, g, 3, 0.8, 3.8, tuff, Mat.Sandstone)
		col(c, -2.8, g + 0.8, 3, 0.7, 2.9, mix(tuff, BLACK, 0.1), Mat.Sandstone)
		col(c, -2.8, g + 1.5, 3, 0.45, 2, tuff, Mat.Sandstone)
		col(c, -2.8, g + 1.95, 3, 0.05, 1.3, DARK)
		-- 피너클 바위
		local pinnacle = mix(lava, tuff, 0.25)
		col(c, 3.6, 0.3, 1.8, 0.5, 2.2, lava, Mat.Basalt)
		local lean = CFrame.new(3.6, 0.3, 1.8) * CFrame.Angles(0.06, 0.3, 0.14)
		block(c, lean * CFrame.new(0, 1.9, 0), V(1.4, 3.8, 1.1), pinnacle, Mat.Basalt)
		block(c, lean * CFrame.new(0.1, 4.6, 0) * CFrame.Angles(0, 0, 0.08), V(0.95, 2, 0.8), pinnacle, Mat.Basalt)
		block(c, lean * CFrame.new(0.2, 5.8, 0) * CFrame.Angles(0, 0, PI / 4), V(0.62, 0.62, 0.6), pinnacle, Mat.Basalt)
		for _, p in { { -0.6, 2.8, 1.2 }, { 1.5, 3.8, 1 }, { -4.1, 0.2, 1.1 }, { 1.9, 0.6, 0.8 } } do
			ball(c, p[1], g + p[3] * 0.3, p[2], p[3], c.P, Mat.Grass)
		end
		-- 오푼티아 선인장 나무(줄기 + 납작한 잎)
		local ox, oz = 0.4, 1.4
		col(c, ox, g, oz, 1.9, 0.35, rgb(150, 120, 90), Mat.Wood)
		for _, pd in { { -0.4, 2.7, 0.3 }, { 0.35, 3, -0.4 }, { 0, 3.4, 0.9 }, { 0.3, 2.4, 1.8 } } do
			block(
				c,
				CFrame.new(ox + pd[1], pd[2], oz) * CFrame.Angles(0, pd[3], pd[1] * 0.8),
				V(0.7, 0.9, 0.15),
				mix(c.P, LEAF, 0.4),
				Mat.Grass
			)
		end
		-- 코끼리거북
		local tx, tz = -1.3, -1.1
		for _, s in K.CORNERS do
			col(c, tx + s[1] * 0.85, g, tz + s[2] * 0.7, 0.8, 0.55, skin)
		end
		col(c, tx, g + 0.6, tz, 0.4, 2.9, mix(shell, BLACK, 0.3))
		ball(c, tx, g + 0.85, tz, 2.7, shell)
		col(c, tx, g + 1.3, tz, 0.08, 2.6, mix(shell, BLACK, 0.35))
		beam(c, V(tx, g + 1, tz - 1.1), V(tx, g + 1.95, tz - 2.1), 0.5, skin)
		ball(c, tx, g + 2.1, tz - 2.2, 0.75, skin)
		-- 바다사자
		local seal = rgb(120, 100, 85)
		beam(c, V(0.6, 0.75, -3.4), V(1.8, 0.72, -3.8), 0.5, seal)
		beam(c, V(0.7, 0.8, -3.4), V(0.45, 1.25, -3.25), 0.36, seal)
		-- 푸른발부비새
		local bx, bz = 2.3, -1.9
		box(c, bx, g, bz, 0.45, 0.12, 0.3, rgb(50, 170, 235))
		ball(c, bx, g + 0.4, bz, 0.55, WHITE)
		block(c, CFrame.new(bx, g + 0.45, bz + 0.12) * CFrame.Angles(0.3, 0, 0), V(0.5, 0.35, 0.45), rgb(120, 95, 70))
		ball(c, bx, g + 0.8, bz - 0.05, 0.34, WHITE)
		block(c, CFrame.new(bx, g + 0.78, bz - 0.3), V(0.09, 0.09, 0.28), rgb(60, 110, 150))
	end

	-- 테오티우아칸: 메마른 풀밭 + 죽은 자의 길 + 길가 제단들 + 오른쪽의 거대한 5단 태양의 피라미드(길 쪽 계단)
	--   + 길 끝의 달의 피라미드(앞쪽 부속 기단과 계단)
	B.teotihuacan = function(c)
		local stone = c.P
		local shade = c.S
		local path = mix(stone, WHITE, 0.3)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(stone, GRASS, 0.45), Mat.Grass)
		box(c, -2.2, 0.25, -1.9, 1.4, 0.06, 6, path, Mat.Concrete)
		box(c, -2.2, 0.25, 1.1, 3, 0.06, 1.2, path, Mat.Concrete)
		-- 태양의 피라미드
		local sx, sz = 2.2, -0.6
		local y = 0.25
		for _, t in { { 5.2, 1.5 }, { 4.3, 1.5 }, { 3.4, 1.3 }, { 2.5, 1.2 }, { 1.7, 0.9 } } do
			box(c, sx, y, sz, t[1], t[2], t[1], stone)
			y += t[2]
		end
		box(c, sx, y, sz, 1.1, 0.25, 1.1, shade)
		local run = 2.9 - 0.85
		wedge(
			c,
			CFrame.new(sx - 0.85 - run / 2, 0.25 + (y - 0.25) / 2, sz) * CFrame.Angles(0, PI / 2, 0),
			V(1.3, y - 0.25, run),
			mix(stone, WHITE, 0.3)
		)
		box(c, sx - 3.1, 0.25, sz, 0.6, 0.7, 2.2, stone)
		-- 달의 피라미드
		local mx, mz = -2.2, 3.3
		y = 0.25
		for _, t in { { 3.2, 1.1 }, { 2.6, 1 }, { 2, 0.9 }, { 1.4, 0.8 } } do
			box(c, mx, y, mz, t[1], t[2], t[1], stone)
			y += t[2]
		end
		box(c, mx, 0.25, 1.4, 2.2, 1.4, 0.9, shade)
		wedge(c, CFrame.new(mx, 0.25 + (y - 0.25) / 2, 1.55), V(0.9, y - 0.25, 2.1), mix(stone, WHITE, 0.15))
		-- 길가 제단
		for _, p in { { -4.1, -3.6 }, { -4.1, -1.4 }, { -4.1, 0.8 }, { -0.6, -4.1 } } do
			box(c, p[1], 0.25, p[2], 1.4, 0.6, 1.4, shade)
			box(c, p[1], 0.85, p[2], 0.9, 0.4, 0.9, stone)
		end
		plant(c, -4.2, 0.25, 3.8, 0.9, 1, mix(LEAF, SAND, 0.3))
		plant(c, 4.2, 0.25, 3.9, 1, 1.1, mix(LEAF, SAND, 0.3))
	end

	-- 나스카 라인: 뒤로 완만하게 올라가는 사막 고원 + 그 위에 밝은 선으로 그린 거대한 벌새(긴 부리, 펼친 날개, 부채꼴 꼬리)
	--   + 곧게 뻗은 직선과 사다리꼴 + 앞쪽 고속도로와 철골 전망탑 + 그림을 보러 선회하는 경비행기 + 뒤쪽 갈색 언덕
	B.nazca = function(c)
		local desert = c.P
		local lineColor = mix(c.A, WHITE, 0.3)
		local rise = 2
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Sand)
		wedge(c, CFrame.new(0, 0.3 + rise / 2, 0), V(9.8, rise, 9.8), desert, Mat.Sand)
		local tilt = math.atan2(rise, 9.8)
		local plane = CFrame.new(0, 0.3 + rise / 2, 0) * CFrame.Angles(-tilt, 0, 0)
		local function line(x1, z1, x2, z2, w, color)
			local a, b = V(x1, 0.02, z1), V(x2, 0.02, z2)
			block(
				c,
				plane * CFrame.lookAt((a + b) / 2, b),
				V(w, 0.1, (b - a).Magnitude + w),
				color or lineColor,
				Mat.Sand
			)
		end
		-- 직선, 사다리꼴, 고속도로
		line(-4.5, -3.8, -2.9, 4.6, 0.14)
		line(4.6, -1.2, 3.2, 4.6, 0.14)
		block(
			c,
			plane * CFrame.new(-3.6, 0.01, -1.6) * CFrame.Angles(0, 0.2, 0),
			V(0.9, 0.08, 2.6),
			mix(lineColor, desert, 0.35),
			Mat.Sand
		)
		line(-4.7, -4.35, 4.7, -4.35, 0.5, TILE)
		-- 벌새: 부리, 머리, 몸통, 날개 깃 3줄씩, 꼬리 3줄
		line(0.1, 1.9, 0.55, 4.5, 0.22)
		cyl(c, plane * CFrame.new(0, 0.02, 1.5) * UPRIGHT, 0.1, 1.1, lineColor, Mat.Sand)
		line(0, 1.2, 0, -1.4, 0.8)
		for _, sx in { -1, 1 } do
			for _, tip in { { 3.6, 1.6 }, { 3.5, 0.5 }, { 3.1, -0.5 } } do
				line(sx * 0.3, 0.4, sx * tip[1], tip[2], 0.3)
			end
		end
		for _, tx in { -0.8, 0, 0.8 } do
			line(0, -1.4, tx, if tx == 0 then -3.8 else -3.5, 0.26)
		end
		-- 전망탑
		local foot = plane * V(-3.9, 0, -3.6)
		local towerTop = foot.Y + 2.3
		for _, s in K.CORNERS do
			beam(
				c,
				V(foot.X + s[1] * 0.45, foot.Y, foot.Z + s[2] * 0.45),
				V(foot.X + s[1] * 0.3, towerTop, foot.Z + s[2] * 0.3),
				0.1,
				rgb(90, 90, 95),
				Mat.Metal
			)
		end
		box(c, foot.X, towerTop, foot.Z, 1, 0.12, 1, rgb(90, 90, 95), Mat.Metal)
		-- 경비행기
		local flight = CFrame.new(1, 6.4, -1.8) * CFrame.Angles(0, 0.6, 0) * CFrame.Angles(0, 0, 0.35)
		cyl(c, flight * ALONG_Z, 2.6, 0.5, WHITE)
		block(c, flight * CFrame.new(0, 0.28, -0.2), V(3.8, 0.08, 0.6), WHITE)
		block(c, flight * CFrame.new(0, 0.5, 1.1), V(0.08, 0.7, 0.5), rgb(200, 50, 50))
		block(c, flight * CFrame.new(0, 0.12, 1.15), V(1.4, 0.06, 0.4), WHITE)
		block(c, flight * CFrame.new(0, 0, -1.33), V(0.9, 0.12, 0.05), DARK)
		-- 뒤쪽 언덕
		local back = 0.3 + rise * 0.93
		peak(c, -2.9, back - 0.2, 3.9, 2, 1.9, 1.8, 1.6, mix(c.S, desert, 0.4), Mat.Sand)
		peak(c, 2.9, back - 0.2, 3.9, 1.9, 2, 1.8, 1.3, mix(c.S, desert, 0.4), Mat.Sand)
	end

	-- 테노치티틀란: 텍스코코 호수 + 섬 도시 + 사방으로 뻗은 둑길 + 신성 구역 광장
	--   + 쌍둥이 신전을 얹은 템플로 마요르(4단, 두 줄 계단, 붉은 우이칠로포치틀리·파란 틀랄록 신당)
	--   + 원형 에에카틀 신전 + 흰 집들과 운하 + 호수 위 치남파(떠 있는 밭)와 카누
	B.tenochtitlan = function(c)
		local stone = c.P
		local lake = c.S
		local white = rgb(240, 235, 225)
		local blue = rgb(60, 110, 200)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, lake, Mat.Glass, 0.1)
		box(c, 0, 0.3, 0.3, 6.6, 0.35, 6.4, mix(stone, SAND, 0.3))
		box(c, 0, 0.65, 0.6, 4.4, 0.08, 4.4, mix(stone, WHITE, 0.45))
		box(c, 0, 0.3, -3.9, 0.7, 0.22, 2, stone)
		box(c, 0, 0.3, 4.2, 0.7, 0.22, 1.4, stone)
		box(c, -4.1, 0.3, 0.6, 1.6, 0.22, 0.7, stone)
		box(c, 4.1, 0.3, 1.2, 1.6, 0.22, 0.7, stone)
		local tz = 1.4
		local y = 0.73
		for _, w in { 3.4, 2.9, 2.4, 1.9 } do
			box(c, 0, y, tz, w, 0.9, w, stone)
			y += 0.9
		end
		for _, sx in { -1, 1 } do
			wedge(
				c,
				CFrame.new(sx * 0.45, 0.73 + (y - 0.73) / 2, tz - 1.45),
				V(0.75, y - 0.73, 1.1),
				mix(stone, WHITE, 0.2)
			)
			local color = if sx > 0 then c.A else blue
			box(c, sx * 0.5, y, tz + 0.25, 0.8, 0.8, 0.9, white)
			box(c, sx * 0.5, y + 0.8, tz + 0.25, 0.9, 0.6, 1, color)
			box(c, sx * 0.5, y, tz - 0.22, 0.3, 0.5, 0.05, DARK)
		end
		col(c, -1.6, 0.73, -1.1, 0.4, 1.3, stone)
		col(c, -1.6, 1.13, -1.1, 0.6, 0.8, white)
		col(c, -1.6, 1.73, -1.1, 0.35, 0.95, c.A)
		for _, p in { { -2.7, -2.2 }, { 2.7, -2.1 }, { -2.8, 3 }, { 2.8, 3 }, { 2.8, 0.6 } } do
			box(c, p[1], 0.65, p[2], 0.9, 0.5, 0.9, white)
		end
		box(c, -2.75, 0.65, 0.5, 0.5, 0.03, 4, lake, Mat.Glass, 0.1)
		for _, p in { { -4.1, -3.3 }, { 4.1, -3.3 }, { -4, 3.6 } } do
			box(c, p[1], 0.3, p[2], 1.2, 0.15, 1.6, GRASS, Mat.Grass)
		end
		plant(c, -4.1, 0.45, -3.3, 1, 0.8, LEAF)
		plant(c, 4.1, 0.45, -3.3, 1.1, 0.8, LEAF)
		box(c, 2, 0.3, -3.8, 0.28, 0.14, 1, WOOD, Mat.Wood)
		box(c, -2.4, 0.3, 4.1, 1, 0.14, 0.28, WOOD, Mat.Wood)
	end

	-- 젊음의 샘: 둥근 밀림 빈터 + 대리석 계단 기단 + 빛나는 청록 샘물 + 3단 대리석 분수(물 커튼) + 황금 성배와 물줄기
	--   + 하늘로 솟는 빛 기둥 + 둘레의 부서진 고대 기둥(쓰러진 것 하나, 덩굴) + 야자수 + 떠다니는 금빛 반딧불
	B.fountainofyouth = function(c)
		local marble = c.P
		local water = c.S
		local gold = c.A
		local vine = rgb(70, 150, 80)
		col(c, 0, 0, 0, 0.3, 9.8, mix(GRASS, LEAF, 0.4), Mat.Grass)
		col(c, 0, 0.3, 0, 0.3, 7.6, mix(marble, ROCK, 0.15))
		col(c, 0, 0.6, 0, 0.7, 6.4, marble)
		col(c, 0, 1.3, 0, 0.04, 5.6, water, Mat.Neon, 0.2)
		col(c, 0, 1.3, 0, 1.6, 1.2, marble)
		col(c, 0, 2.9, 0, 0.35, 3.4, marble)
		col(c, 0, 3.25, 0, 0.04, 3, water, Mat.Neon, 0.2)
		col(c, 0, 1.34, 0, 1.56, 3.3, water, Mat.Glass, 0.6)
		col(c, 0, 3.25, 0, 1.3, 0.8, marble)
		col(c, 0, 4.55, 0, 0.3, 2.2, marble)
		col(c, 0, 4.85, 0, 0.04, 1.9, water, Mat.Neon, 0.2)
		col(c, 0, 3.29, 0, 1.26, 2.1, water, Mat.Glass, 0.6)
		col(c, 0, 4.85, 0, 0.8, 0.35, gold, Mat.Metal)
		col(c, 0, 5.65, 0, 0.6, 1, gold, Mat.Metal)
		col(c, 0, 6.25, 0, 1.2, 0.3, water, Mat.Neon, 0.2)
		ball(c, 0, 7.6, 0, 0.9, water, Mat.Neon, 0.3)
		col(c, 0, 6.2, 0, 9, 1.4, gold, Mat.Neon, 0.8)
		local heights = { 4.2, 2.4, 3.6, 1.6, 4.2, 3 }
		for i = 0, 5 do
			local a = i / 6 * TAU + PI / 6
			local x, z = 4.1 * math.cos(a), 4.1 * math.sin(a)
			local h = heights[i + 1]
			col(c, x, 0.3, z, h, 0.6, marble)
			if h > 4 then
				box(c, x, 0.3 + h, z, 0.85, 0.3, 0.85, marble)
			elseif i % 2 == 0 then
				ball(c, x, 0.3 + h, z, 0.75, vine, Mat.Grass)
			end
		end
		cyl(c, CFrame.new(-2.4, 0.58, -4) * CFrame.Angles(0, 0.3, 0), 2, 0.55, marble)
		plant(c, -2.5, 0.3, 3.9, 3.6, 1.8, LEAF)
		plant(c, 2.6, 0.3, 3.7, 3, 1.6, LEAF)
		for _, p in { { -1.8, 5.2, -1.2 }, { 2, 6.4, -0.6 }, { -1.2, 8.3, 1.5 }, { 1.4, 9.4, 1 } } do
			ball(c, p[1], p[2], p[3], 0.3, gold, Mat.Neon)
		end
	end

	return B
end
