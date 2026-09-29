-- 아메리카 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 버킹엄 분수(fountain) · 자유의 여신상(statue) · 치첸이트사(steps) 는 원래 그 명소를 위해 만든 모양을 그대로 씀.

return function(K)
	local B = {}

	local V, rgb, Mat, PI = K.V, K.rgb, K.Mat, K.PI
	local ALONG_Z = K.ALONG_Z
	local GRASS, LEAF, WATER, DARK = K.GRASS, K.LEAF, K.WATER, K.DARK
	local ROCK, WOOD, SAND, CLOUD, BLACK, WHITE = K.ROCK, K.WOOD, K.SAND, K.CLOUD, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local facing, gable, plant = K.facing, K.gable, K.plant

	-- a 에서 b 까지 이어지는 판: 가로 w(진행 방향의 오른쪽), 두께 t. a → b 는 수직이 아니어야 함
	local function slab(c, a, b, w, t, color, material, transparency)
		local mid = (a + b) / 2
		return block(c, CFrame.lookAt(mid, b), V(w, t, (b - a).Magnitude), color, material, transparency)
	end

	-- 원호 위의 판 조각들: 중심 (cx, cz), 반지름 r, 각 a0 → a1(0 = +Z, 시계 반대 = +X 쪽), n 토막.
	--   each(cf, chord, dir): cf = 원호 위 한 토막의 중심(y = 0, LookVector = 안쪽), chord = 토막 길이, dir = 바깥 방향
	local function around(cx, cz, r, a0, a1, n, each)
		for i = 0, n - 1 do
			local p1 = a0 + (a1 - a0) * i / n
			local p2 = a0 + (a1 - a0) * (i + 1) / n
			local pm = (p1 + p2) / 2
			local dir = V(math.sin(pm), 0, math.cos(pm))
			local chord = 2 * r * math.sin(math.abs(p2 - p1) / 2)
			each(CFrame.new(cx + dir.X * r, 0, cz + dir.Z * r) * facing(-dir.X, -dir.Z), chord, dir, i)
		end
	end

	-- 게이트웨이 아치: 잔디 공원 + 뒤쪽 미시시피강(증기선) + 연못 두 개 + 땅에서 솟아 꼭대기로 가늘어지는 은빛 현수선 아치
	B.gatewayarch = function(c)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, GRASS, Mat.Grass)
		box(c, 0, 0, 4.2, 9.8, 0.26, 1.4, WATER, Mat.Glass, 0.1)
		box(c, 0, 0.2, 3.35, 9.8, 0.14, 0.3, mix(c.S, WHITE, 0.45), Mat.Concrete)
		box(c, 0, 0.2, -2.6, 1.3, 0.04, 4.6, mix(c.S, WHITE, 0.65), Mat.Concrete)
		block(c, CFrame.new(-2.7, 0.22, -2.7) * CFrame.Angles(0, 0.45, 0), V(1.1, 0.05, 2.6), WATER, Mat.Glass)
		block(c, CFrame.new(2.7, 0.22, -2.7) * CFrame.Angles(0, -0.45, 0), V(1.1, 0.05, 2.6), WATER, Mat.Glass)
		-- 현수선 y = foot + A(cosh k - cosh(kx/L)) 를 호 길이로 고르게 나눠 토막을 이음(발은 굵고 꼭대기는 가늚)
		local L, H, k, foot = 4.1, 11.5, 3, 0.3
		local A = (H - foot) / (math.cosh(k) - 1)
		local function point(x)
			return V(x, foot + A * (math.cosh(k) - math.cosh(k * x / L)), 0)
		end
		local samples, lengths = {}, { 0 }
		for i = 0, 300 do
			samples[i + 1] = point(-L + 2 * L * i / 300)
			if i > 0 then
				lengths[i + 1] = lengths[i] + (samples[i + 1] - samples[i]).Magnitude
			end
		end
		local total = lengths[#lengths]
		local n = 17
		local points = {}
		local j = 1
		for s = 0, n do
			local target = total * s / n
			while j < #lengths - 1 and lengths[j + 1] < target do
				j += 1
			end
			local t = math.clamp((target - lengths[j]) / (lengths[j + 1] - lengths[j]), 0, 1)
			points[s + 1] = samples[j] + (samples[j + 1] - samples[j]) * t
		end
		for s = 1, n do
			local a, b = points[s], points[s + 1]
			local u = math.abs((s - 0.5) / n * 2 - 1)
			local t = 0.42 + 0.55 * u
			block(c, CFrame.lookAt((a + b) / 2, b), V(t * 0.9, t, (b - a).Magnitude + 0.12), c.P, Mat.Metal)
		end
		for _, sx in { -1, 1 } do
			box(c, sx * L, 0.2, 0, 1.4, 0.12, 1.2, mix(c.S, WHITE, 0.5), Mat.Concrete)
			plant(c, sx * 4.2, 0.2, -4.1, 1.1, 1.3, LEAF)
			plant(c, sx * 4.2, 0.2, 2.3, 1.1, 1.3, LEAF)
		end
		-- 미시시피 증기선
		box(c, 2.4, 0.26, 4.2, 1.8, 0.3, 0.7, WHITE)
		box(c, 2.3, 0.56, 4.2, 1.2, 0.35, 0.55, mix(WHITE, c.A, 0.4))
		box(c, 3.35, 0.26, 4.2, 0.3, 0.5, 0.75, rgb(190, 50, 40))
	end

	-- 빵산: 과나바라만 바다 + 숲으로 덮인 우르카 언덕 + 넓은 밑동 위로 뒤로 살짝 기울어 솟은 둥근 화강암 봉우리
	--   + 두 구간 케이블카(노란 객차) + 해변 + 요트
	B.sugarloaf = function(c)
		local granite = c.P
		local forest = c.S
		local light = mix(c.P, WHITE, 0.12)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, WATER, Mat.Glass, 0.1)
		col(c, 1.3, 0, 1.5, 0.5, 7, forest, Mat.Grass)
		col(c, -3, 0, -2.4, 0.45, 3.8, forest, Mat.Grass)
		box(c, -3.9, 0.25, -4.25, 1.6, 0.1, 1, SAND, Mat.Sand)
		-- 봉우리: 촘촘히 겹친 공(아래는 넓고 위로 좁아지며 뒤로 기움) = 매끈한 돔
		for i = 0, 6 do
			local d = 6.2 - i * 0.47
			ball(c, 1.1 + i * 0.1, d / 2 + i * 1.02, 1.3 + i * 0.13, d, if i % 2 == 0 then granite else light)
		end
		-- 기슭 숲(왼쪽 어깨와 앞 기슭)
		for _, t in
			{
				{ -1.2, 1.2, 0.2, 2.2 },
				{ -0.9, 2.6, 1.8, 2 },
				{ 0.2, 1.1, -1.4, 2 },
				{ 2.6, 1, -1.3, 1.8 },
				{ 3.9, 1.3, 0.6, 2 },
				{ -0.2, 3.9, 2.6, 1.6 },
			}
		do
			ball(c, t[1], t[2], t[3], t[4], forest, Mat.Grass)
		end
		-- 우르카 언덕
		col(c, -3, 0.45, -2.4, 1.1, 3.4, mix(granite, forest, 0.3))
		ball(c, -3, 1.65, -2.4, 3.2, forest, Mat.Grass)
		-- 케이블카: 해변 역 → 우르카 → 빵산 꼭대기
		local base, mid, top = V(-4.1, 0.9, -4.3), V(-3, 3.7, -2.4), V(1.9, 10.6, 2.6)
		box(c, -4.1, 0.35, -4.3, 0.8, 0.6, 0.6, WHITE)
		box(c, -3, 3.2, -2.4, 1, 0.5, 0.8, WHITE)
		box(c, 1.9, 9.8, 2.6, 1.1, 0.6, 0.9, WHITE)
		beam(c, base, mid, 0.07, DARK)
		beam(c, mid, top, 0.07, DARK)
		for _, t in { { base, mid, 0.5 }, { mid, top, 0.45 } } do
			local p = t[1] + (t[2] - t[1]) * t[3]
			box(c, p.X, p.Y - 0.35, p.Z, 0.08, 0.35, 0.08, DARK)
			box(c, p.X, p.Y - 0.85, p.Z, 0.6, 0.5, 0.6, c.A)
		end
		-- 요트
		box(c, 3.4, 0.25, -3.6, 0.3, 0.2, 1, WHITE)
		wedge(c, CFrame.new(3.4, 1.05, -3.6), V(0.06, 1.4, 0.9), WHITE)
	end

	-- 백악관(남쪽 정면): 잔디 + 분수 + 흰 본관(창문 두 줄, 코니스, 난간) + 가운데 반원형 포티코(기둥 6, 트루먼 발코니) + 성조기
	B.whitehouse = function(c)
		local white = c.P
		local shade = mix(c.P, ROCK, 0.18)
		local window = rgb(60, 70, 85)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, c.S, Mat.Grass)
		box(c, 0, 0.2, -3, 1.2, 0.03, 3.6, mix(SAND, WHITE, 0.4), Mat.Concrete)
		col(c, 0, 0.2, -3.7, 0.3, 1.9, shade)
		col(c, 0, 0.3, -3.7, 0.22, 1.6, WATER, Mat.Glass)
		col(c, 0, 0.5, -3.7, 0.9, 0.2, c.A, Mat.Neon, 0.3)
		-- 본관
		box(c, 0, 0.2, 1.6, 8.8, 1.2, 3.8, shade)
		box(c, 0, 1.4, 1.6, 8.6, 2.6, 3.6, white)
		box(c, 0, 4, 1.6, 8.9, 0.4, 3.9, white)
		box(c, 0, 4.4, 1.6, 8.6, 0.4, 3.6, mix(white, ROCK, 0.08))
		box(c, 0, 4.4, 2, 7.2, 0.7, 2.4, rgb(150, 150, 150))
		for _, x in { -3.7, -2.75, 2.75, 3.7 } do
			box(c, x, 2, -0.23, 0.5, 0.9, 0.1, window)
			box(c, x, 3.2, -0.23, 0.5, 0.6, 0.1, window)
			box(c, x, 0.55, -0.23, 0.45, 0.55, 0.1, window)
		end
		-- 반원형 포티코
		local pz = -0.2
		col(c, 0, 0.2, pz, 1.2, 4.2, shade)
		box(c, 0, 0.2, pz - 2.1, 0.8, 0.9, 0.12, window)
		col(c, 0, 1.4, pz, 2.6, 2.9, mix(white, ROCK, 0.12))
		for k = 0, 5 do
			local angle = math.rad(-75 + k * 30)
			col(c, 1.8 * math.sin(angle), 1.4, pz - 1.8 * math.cos(angle), 2.6, 0.32, white)
		end
		col(c, 0, 2.6, pz, 0.12, 3.9, white)
		col(c, 0, 4, pz, 0.45, 4.2, white)
		col(c, 0, 4.45, pz, 0.35, 4, mix(white, ROCK, 0.08))
		-- 성조기
		col(c, 0, 5.1, 2, 2.1, 0.08, ROCK, Mat.Metal)
		box(c, 0.5, 6.5, 2, 0.9, 0.55, 0.05, rgb(200, 40, 50))
		box(c, 0.25, 6.77, 1.99, 0.4, 0.28, 0.05, rgb(40, 60, 140))
		plant(c, -3.9, 0.2, -3.6, 1.2, 1.8, LEAF)
		plant(c, 3.9, 0.2, -3.6, 1.2, 1.8, LEAF)
	end

	-- 나이아가라 폭포: 아래 강 + 윗단 강이 말굽 모양으로 휘어 쏟아지는 캐나다 폭포(물안개) + 숲이 있는 고트섬
	--   + 곧게 떨어지는 미국 폭포(바위 더미) + 캐나다 쪽 기슭과 스카이론 타워 + 폭포로 다가가는 유람선
	B.niagara = function(c)
		local deep = mix(c.P, rgb(20, 70, 130), 0.35)
		local foam = mix(c.A, c.P, 0.08)
		local cliff = mix(ROCK, rgb(150, 125, 95), 0.35)
		local top, front = 4.2, 0.2
		local hx, R = 1.3, 2
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, deep, Mat.Glass, 0.1)
		-- 말굽: 원호를 따라 떨어지는 물(뒤로 조금 누워 빛을 받음) + 폭포로 흘러드는 윗단 물
		around(hx, front, R, math.rad(-100), math.rad(100), 6, function(cf, chord, _dir, i)
			local white = if i == 2 or i == 3 then WHITE else foam
			block(
				c,
				cf * CFrame.new(0, (0.3 + top) / 2, 0.15) * CFrame.Angles(0.12, 0, 0),
				V(chord + 0.14, top - 0.2, 0.25),
				white
			)
			block(c, cf * CFrame.new(0, top - 0.2, 0.75), V(chord * (R + 1.5) / R + 0.1, 0.4, 1.4), c.P)
		end)
		box(c, 1.6, 0.3, 3.6, 4.2, top - 0.65, 2.6, cliff)
		box(c, 1.6, top - 0.35, 3.6, 4.2, 0.35, 2.6, c.P)
		-- 고트섬(말굽 왼쪽)
		box(c, -1.4, 0.3, 2.55, 1.9, 4, 4.7, cliff)
		box(c, -1.4, 4.3, 2.55, 1.9, 0.25, 4.7, c.S, Mat.Grass)
		ball(c, -1.5, 5, 1.2, 1.4, LEAF, Mat.Grass)
		ball(c, -1.3, 5.1, 3.2, 1.6, LEAF, Mat.Grass)
		-- 캐나다 쪽 기슭(말굽 오른쪽) + 스카이론 타워
		box(c, 4.3, 0.3, 2.55, 1.2, 4, 4.7, cliff)
		box(c, 4.3, 4.3, 2.55, 1.2, 0.25, 4.7, c.S, Mat.Grass)
		box(c, 4.3, 0.3, -2.4, 1.2, 1.6, 5, cliff)
		box(c, 4.3, 1.9, -2.4, 1.2, 0.2, 5, c.S, Mat.Grass)
		col(c, 4.2, 4.55, 4, 6.4, 0.45, rgb(225, 225, 215), Mat.Concrete)
		col(c, 4.2, 10.4, 4, 0.9, 1.5, rgb(225, 225, 215), Mat.Concrete)
		col(c, 4.2, 11.3, 4, 0.9, 0.15, DARK)
		-- 미국 폭포 + 바위 더미
		box(c, -3.65, 0.3, 2.55, 2.5, 3.2, 4.7, cliff)
		box(c, -3.65, 3.5, 2.55, 2.5, 0.3, 4.7, c.P)
		block(c, CFrame.new(-3.65, 2.05, 0.05) * CFrame.Angles(0.18, 0, 0), V(2.5, 3.5, 0.25), WHITE)
		for _, t in { { -4.3, -0.5, 1.2 }, { -3.5, -0.6, 1 }, { -2.8, -0.45, 1.2 } } do
			ball(c, t[1], t[3] / 2 + 0.1, t[2], t[3], ROCK)
		end
		-- 물안개 + 유람선
		ball(c, hx, 1.6, -0.6, 2.6, CLOUD, Mat.SmoothPlastic, 0.65)
		ball(c, hx + 0.3, 4.4, 0.2, 2, CLOUD, Mat.SmoothPlastic, 0.7)
		box(c, 0.2, 0.3, -2.9, 0.7, 0.3, 1.5, WHITE)
		box(c, 0.2, 0.6, -2.8, 0.55, 0.35, 0.9, rgb(40, 90, 200))
	end

	-- 무지개산(비니쿤카): 갈색 고원 + 높이마다 색이 바뀌는 지층 띠를 두른 봉우리 셋(층마다 살짝 바깥으로 나온 박공.
	--   가운데 큰 봉우리는 정면에서 뾰족한 삼각형) + 오솔길 + 알파카
	B.rainbowmountain = function(c)
		local bands = {
			rgb(150, 65, 70),
			c.P,
			rgb(225, 150, 70),
			c.S,
			c.A,
			rgb(175, 130, 190),
			mix(c.P, WHITE, 0.25),
		}
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(rgb(170, 145, 95), GRASS, 0.25), Mat.Grass)
		local t = 1.15
		-- 봉우리: { x, z, 방향(yaw), 꼭대기 높이, 능선 길이, 기울기(반폭/높이) }
		for _, peak in
			{
				{ -2, 2.1, PI / 2 - 0.3, 5.4, 3.6, 0.45 },
				{ 1.8, 2, PI / 2 + 0.35, 6, 3.6, 0.42 },
				{ 0.2, 0, PI / 2 + 0.1, 8.6, 4.4, 0.37 },
			}
		do
			local cf = CFrame.new(peak[1], 0, peak[2]) * CFrame.Angles(0, peak[3], 0)
			local apex, len, s = peak[4], peak[5], peak[6]
			for k, color in bands do
				local y = 0.2 + (k - 1) * t
				local h = apex - y
				if h < 0.9 then
					break
				end
				local d = 2 * (s * h + 0.05 * (k - 1))
				local w = len + (k - 1) * 0.1
				wedge(c, cf * CFrame.new(0, y + h / 2, -d / 4), V(w, h, d / 2), color)
				wedge(c, cf * CFrame.new(0, y + h / 2, d / 4) * CFrame.Angles(0, PI, 0), V(w, h, d / 2), color)
			end
		end
		slab(c, V(-4.6, 0.22, -4.7), V(0.8, 0.22, -4.3), 0.5, 0.04, mix(SAND, WHITE, 0.2), Mat.Sand)
		-- 알파카(옆모습, +X 쪽을 봄)
		local wool = rgb(245, 238, 225)
		local ax, az = 2.9, -4.1
		box(c, ax, 0.2, az, 0.9, 0.6, 0.3, wool)
		box(c, ax, 0.8, az, 1.05, 0.55, 0.5, wool)
		box(c, ax + 0.5, 1.25, az, 0.25, 0.85, 0.28, wool)
		box(c, ax + 0.62, 2, az, 0.5, 0.3, 0.28, wool)
		box(c, ax, 1.35, az, 0.55, 0.06, 0.52, rgb(220, 50, 80))
	end

	-- 아레날 화산: 잔디 + 호수 + 아래는 숲, 위는 맨 바위인 매끈한 원뿔(층층 원기둥) + 붉은 용암 줄기 + 화구의 빛 + 연기
	B.arenal = function(c)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.S, BLACK, 0.15), Mat.Grass)
		block(c, CFrame.new(-2.9, 0.27, -3.3) * CFrame.Angles(0, 0.4, 0), V(3.2, 0.06, 1.8), WATER, Mat.Glass, 0.1)
		local n = 12
		local height = 12.2
		local h = height / n
		local radii = {}
		for k = 0, n - 1 do
			local d = 1.4 + 7.9 * (1 - k / n) ^ 1.35
			radii[k + 1] = d / 2
			local color
			if k <= 1 then
				color = c.S
			elseif k == 2 then
				color = mix(c.S, c.P, 0.5)
			else
				color = if k % 2 == 0 then c.P else mix(c.P, WHITE, 0.08)
			end
			col(c, 0, 0.25 + k * h, 0, h, d, color, if k <= 2 then Mat.Grass else nil)
		end
		local peak = 0.25 + height
		col(c, 0, peak, 0, 0.1, 1.1, c.A, Mat.Neon)
		-- 용암 줄기: 층 모서리를 따라 내려옴
		local function corner(k, angle)
			local r = radii[k] + 0.02
			return V(math.sin(angle) * r, 0.25 + k * h, -math.cos(angle) * r)
		end
		for _, flow in { { 0.35, { 12, 10, 8, 6 } }, { -0.5, { 12, 10, 9 } } } do
			local angle, ks = flow[1], flow[2]
			for i = 1, #ks - 1 do
				beam(c, corner(ks[i], angle), corner(ks[i + 1], angle), 0.3, c.A, Mat.Neon)
			end
		end
		-- 연기
		ball(c, 0.2, peak + 1.2, 0.2, 1.6, rgb(150, 145, 140), Mat.SmoothPlastic, 0.3)
		ball(c, 0.8, peak + 2.6, 0.6, 2.2, rgb(170, 165, 160), Mat.SmoothPlastic, 0.35)
		ball(c, 1.8, peak + 4.3, 1.1, 2.8, rgb(190, 185, 180), Mat.SmoothPlastic, 0.4)
		-- 기슭 숲
		for i = 0, 6 do
			local angle = i / 7 * 2 * PI + 0.3
			ball(
				c,
				math.sin(angle) * 4.1,
				0.95,
				math.cos(angle) * 4.1,
				1.7,
				if i % 2 == 0 then LEAF else c.S,
				Mat.Grass
			)
		end
	end

	-- 티칼 1호 신전(거대한 재규어 신전): 밀림 + 광장 + 가파르고 좁은 9단 피라미드 + 정면 한 줄 계단
	--   + 꼭대기 신전(입구) + 높이 솟은 지붕 볏(루프 콤) + 기단을 가리는 밀림 수관
	B.tikal = function(c)
		local weathered = mix(c.P, DARK, 0.28)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.S, BLACK, 0.2), Mat.Grass)
		box(c, 0, 0.25, 0.2, 7.6, 0.3, 7.4, mix(c.P, WHITE, 0.1))
		local y, z0, n, h = 0.55, 0.8, 9, 1.12
		for i = 0, n - 1 do
			local t = i / (n - 1)
			box(c, 0, y, z0, 6.4 - 3.2 * t, h, 5.8 - 2.8 * t, if i % 2 == 0 then c.P else mix(c.P, DARK, 0.14))
			y += h
		end
		wedge(c, CFrame.new(0, 0.55 + (y - 0.55) / 2, -1.9), V(1.5, y - 0.55, 2.4), mix(c.P, WHITE, 0.15))
		box(c, 0, y, 1, 2.8, 2, 2.2, c.P)
		box(c, 0, y, -0.12, 0.8, 1.3, 0.1, DARK)
		box(c, 0, y + 2, 1, 3, 0.3, 2.4, weathered)
		box(c, 0, y + 2.3, 1.4, 2.4, 2.6, 0.9, weathered)
		box(c, 0, y + 4.9, 1.4, 1.6, 0.9, 0.8, weathered)
		for _, t in
			{
				{ -3.6, -3.4, 2.6 },
				{ 3.6, -3.5, 2.6 },
				{ -3.6, 0.6, 2.8 },
				{ 3.6, 0.2, 2.8 },
				{ -3.3, 3.5, 3 },
				{ 3.4, 3.4, 3 },
				{ -1.6, -4.1, 1.6 },
				{ 1.7, -4.1, 1.6 },
			}
		do
			ball(c, t[1], t[3] / 2 + 0.35, t[2], t[3], if t[3] > 2.7 then LEAF else c.S, Mat.Grass)
		end
	end

	-- 이과수 폭포: 흙빛 강 + 뒤쪽을 넓게 감싸는 밀림 절벽(2단) + 절벽 틈마다 두 단으로 쏟아지는 흰 폭포 여러 줄기
	--   + 폭포 사이 수풀 + 물안개 + 폭포 쪽으로 뻗은 관람 데크
	B.iguazu = function(c)
		local deep = mix(c.P, rgb(120, 90, 55), 0.4)
		local foam = mix(c.P, WHITE, 0.85)
		local ledge = mix(c.S, c.A, 0.2)
		local top, mid = 5, 2.6
		local R = 5.5
		local falls = { [0] = true, [1] = true, [3] = true, [5] = true, [6] = true }
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, deep, Mat.Glass, 0.1)
		around(0, -2.2, R, math.rad(-40), math.rad(40), 7, function(cf, chord, _dir, i)
			local height = if falls[i] then top else top + 0.9
			block(
				c,
				cf * CFrame.new(0, (0.3 + height) / 2, 0.5),
				V(chord * (R + 1) / R + 0.1, height - 0.3, 1),
				c.S,
				Mat.Grass
			)
			block(c, cf * CFrame.new(0, (0.3 + mid) / 2, -0.55), V(chord + 0.1, mid - 0.3, 1.1), ledge)
			if falls[i] then
				block(c, cf * CFrame.new(0, top + 0.05, 0.45), V(chord * 0.7, 0.14, 1.1), c.P)
				local upper = cf * CFrame.new(0, (mid + top + 0.12) / 2, -0.12) * CFrame.Angles(0.15, 0, 0)
				block(c, upper, V(chord * 0.7, top + 0.12 - mid, 0.16), foam)
				local lower = cf * CFrame.new(0, (0.3 + mid + 0.05) / 2, -1.2) * CFrame.Angles(0.15, 0, 0)
				block(c, lower, V(chord * 0.85, mid - 0.25, 0.16), foam)
			else
				local p = (cf * CFrame.new(0, height + 0.3, 0.4)).Position
				ball(c, p.X, p.Y, p.Z, 1.5, LEAF, Mat.Grass)
			end
		end)
		for _, t in { { -4.1, 0.2, 1.6 }, { 4.1, 0.1, 1.6 }, { -4.1, 2.2, 1.6 }, { 4.1, 2.2, 1.6 } } do
			ball(c, t[1], t[3] / 2 + 0.3, t[2], t[3], if t[2] > 1 then c.S else LEAF, Mat.Grass)
		end
		ball(c, 0, 1.3, 1.5, 2.4, CLOUD, Mat.SmoothPlastic, 0.7)
		ball(c, -2.3, 1.1, 1, 2, CLOUD, Mat.SmoothPlastic, 0.7)
		box(c, 1.3, 0.9, -1.9, 0.5, 0.12, 5.8, rgb(150, 150, 150), Mat.Metal)
		box(c, 1.52, 1.02, -1.9, 0.05, 0.3, 5.8, rgb(210, 210, 210), Mat.Metal)
	end

	-- 아마존 열대우림: 굽이치는 흙탕 강 + 빽빽한 밀림(여러 높이의 나무) + 우뚝 솟은 케이폭 나무 + 금강앵무 + 큰가시연잎 + 카누
	B.amazon = function(c)
		local ground = mix(c.P, BLACK, 0.35)
		local river = mix(c.S, rgb(175, 125, 70), 0.45)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, ground, Mat.Grass)
		local path = {
			V(-4.5, 0.3, 4.2),
			V(-2.2, 0.3, 2.4),
			V(0.2, 0.3, 1.2),
			V(1, 0.3, -1.3),
			V(3, 0.3, -2.8),
			V(4.4, 0.3, -3.4),
		}
		for i = 1, #path - 1 do
			local a, b = path[i], path[i + 1]
			local dir = (b - a).Unit
			local a2 = if i > 1 then a - dir * 0.5 else a
			local b2 = if i < #path - 1 then b + dir * 0.5 else b
			slab(c, a2 + V(0, 0.03, 0), b2 + V(0, 0.03, 0), 1.5, 0.06, river, Mat.Glass, 0.05)
		end
		for _, p in { { -1.4, 2 }, { 0.8, -0.3 }, { 2.4, -2.4 } } do
			col(c, p[1], 0.36, p[2], 0.06, 0.8, rgb(90, 160, 70), Mat.Grass)
		end
		block(c, CFrame.new(-0.5, 0.42, 1.6) * CFrame.Angles(0, 0.6, 0), V(0.3, 0.18, 1.3), WOOD, Mat.Wood)
		-- 밀림: { x, z, 줄기 높이, 잎 지름, 색 }
		local greens = { c.P, LEAF, mix(c.P, rgb(200, 200, 60), 0.3), mix(c.P, BLACK, 0.2) }
		for k, t in
			{
				{ -3.6, 0.8, 1.6, 2.6 },
				{ -1.6, -0.9, 2.2, 2.6 },
				{ -3.8, -2.6, 1.4, 2.2 },
				{ -1.8, -3.8, 1.2, 2 },
				{ 0.2, -3.9, 1.6, 1.8 },
				{ 2.4, 1.2, 1.8, 2.8 },
				{ 3.8, -0.4, 1.3, 2 },
				{ -0.6, 3.9, 1.4, 1.9 },
				{ 3.8, 3.8, 1.6, 2.2 },
			}
		do
			plant(c, t[1], 0.3, t[2], t[3], t[4], greens[(k - 1) % #greens + 1])
		end
		-- 케이폭: 판뿌리 + 긴 줄기 + 우산 모양 수관
		local kx, kz = 1.4, 2.5
		col(c, kx, 0.3, kz, 8.2, 0.6, WOOD, Mat.Wood)
		beam(c, V(kx - 0.9, 0.35, kz), V(kx, 2, kz), 0.3, WOOD, Mat.Wood)
		beam(c, V(kx + 0.8, 0.35, kz - 0.5), V(kx, 2, kz), 0.3, WOOD, Mat.Wood)
		col(c, kx, 8.4, kz, 0.9, 4.6, c.P, Mat.Grass)
		ball(c, kx - 0.8, 9.4, kz + 0.2, 2.2, LEAF, Mat.Grass)
		ball(c, kx + 0.9, 9.3, kz - 0.3, 2, mix(c.P, BLACK, 0.1), Mat.Grass)
		-- 금강앵무 두 마리
		for _, m in { { -1.2, 4.6, -1.6, 0.4 }, { 3.2, 6.5, 1.4, -0.5 } } do
			local p = V(m[1], m[2], m[3])
			ball(c, p.X, p.Y, p.Z, 0.45, c.A)
			beam(c, p + V(0, -0.1, 0.1), p + V(0.1, -0.7, 0.35), 0.12, c.A)
			block(c, CFrame.new(p) * CFrame.Angles(0, m[4], 0), V(1, 0.06, 0.3), rgb(40, 110, 220))
		end
	end

	-- 앙헬 폭포: 밀림 + 붉은 사암 테푸이(평평한 초록 꼭대기, 깎아지른 절벽, 가운데 움푹한 협곡) + 꼭대기 가장자리에서
	--   떨어지는 가느다란 긴 물줄기(아래로 갈수록 퍼짐) + 물보라 + 흘러나가는 강 + 절벽 허리의 구름 + 기슭 밀림 비탈
	B.angelfalls = function(c)
		local jungle = mix(c.S, BLACK, 0.25)
		local rock = c.P
		local light = mix(c.P, WHITE, 0.1)
		local cleft = mix(c.P, BLACK, 0.35)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, jungle, Mat.Grass)
		box(c, 0, 0.3, 3.2, 9.8, 16, 3.4, rock)
		box(c, -3.3, 0.3, 1.1, 3.2, 14.6, 1.6, light)
		box(c, 3.25, 0.3, 1, 3.3, 15.4, 1.8, light)
		box(c, -4.1, 7, 0.2, 1.6, 7.9, 0.4, rock)
		box(c, 4.1, 5, 0.05, 1.6, 10.7, 0.3, rock)
		box(c, -0.1, 0.3, 1.46, 3.2, 16, 0.1, cleft)
		box(c, 0, 16.3, 3.2, 9.6, 0.35, 3.2, c.S, Mat.Grass)
		box(c, -3.3, 14.9, 1.1, 3, 0.3, 1.4, c.S, Mat.Grass)
		box(c, 3.25, 15.7, 1, 3.1, 0.3, 1.6, c.S, Mat.Grass)
		ball(c, 2.6, 16.8, 3, 1.3, LEAF, Mat.Grass)
		-- 물줄기: 꼭대기 물길 → 가는 물줄기(빛남) → 아래로 퍼지는 물보라
		box(c, -0.1, 16.3, 2.3, 0.7, 0.42, 1.8, WATER)
		box(c, -0.1, 7.6, 1.15, 0.5, 9.1, 0.2, c.A, Mat.Neon, 0.1)
		box(c, -0.1, 3.4, 1.05, 0.8, 4.3, 0.25, c.A, Mat.Neon, 0.35)
		box(c, -0.1, 0.3, 0.95, 1.3, 3.2, 0.3, c.A, Mat.SmoothPlastic, 0.4)
		ball(c, -0.1, 1.3, 0.5, 2.4, CLOUD, Mat.SmoothPlastic, 0.55)
		ball(c, 0.9, 1, 0.1, 1.8, CLOUD, Mat.SmoothPlastic, 0.6)
		slab(c, V(-0.1, 0.33, 0.2), V(0.9, 0.33, -4.9), 1.1, 0.06, WATER, Mat.Glass, 0.05)
		-- 기슭 밀림 비탈 + 수관
		wedge(c, CFrame.new(-3.3, 1.45, -0.35), V(3.2, 2.3, 1.3), jungle, Mat.Grass)
		wedge(c, CFrame.new(3.25, 1.45, -0.45), V(3.3, 2.3, 1.3), jungle, Mat.Grass)
		for _, t in
			{
				{ -4, -2.6, 2 },
				{ -2.2, -3.4, 1.8 },
				{ -3.2, -4.1, 1.6 },
				{ 2.5, -3.1, 2 },
				{ 4, -1.8, 1.8 },
				{ 3.6, -4, 1.7 },
			}
		do
			ball(c, t[1], t[3] / 2 + 0.4, t[2], t[3], if t[3] >= 1.8 then LEAF else c.S, Mat.Grass)
		end
		-- 구름
		ball(c, -3.9, 10.2, -0.2, 2, CLOUD, Mat.SmoothPlastic, 0.4)
		ball(c, -2.7, 10.5, -0.5, 1.5, CLOUD, Mat.SmoothPlastic, 0.4)
		ball(c, 3.8, 8.4, -0.5, 2.2, CLOUD, Mat.SmoothPlastic, 0.4)
		ball(c, 2.7, 8.1, -0.7, 1.4, CLOUD, Mat.SmoothPlastic, 0.4)
	end

	-- 그레이트 블루홀: 청록 석호 + 모래 여울 + 둥근 산호초 테두리 + 바깥에서 안쪽으로 짙어지는 동그란 구멍 + 산호 덩이 + 다이빙 보트 + 야자수 모래톱
	B.bluehole = function(c)
		local lagoon = mix(c.S, rgb(40, 150, 200), 0.3)
		local flats = mix(c.S, WHITE, 0.45)
		local rim = mix(c.A, c.S, 0.25)
		box(c, 0, 0, 0, 9.8, 0.9, 9.8, mix(c.A, ROCK, 0.35), Mat.Sand)
		box(c, 0, 0.9, 0, 9.8, 0.4, 9.8, lagoon, Mat.Glass, 0.05)
		col(c, -3.3, 0.9, 3.4, 0.42, 2.6, flats, Mat.Sand)
		col(c, 3.6, 0.9, -1, 0.42, 2.2, flats, Mat.Sand)
		local cz = 0.3
		col(c, 0, 0.9, cz, 0.44, 7.6, rim, Mat.Sand)
		col(c, 0, 0.9, cz, 0.46, 6.6, mix(c.S, c.P, 0.45))
		col(c, 0, 0.9, cz, 0.48, 5.6, mix(c.S, c.P, 0.75))
		col(c, 0, 0.9, cz, 0.5, 4.2, c.P)
		col(c, 0, 0.9, cz, 0.52, 2.6, mix(c.P, BLACK, 0.35))
		for i = 0, 9 do
			local angle = i / 10 * 2 * PI + 0.2
			local color = if i % 3 == 0
				then rgb(200, 150, 100)
				elseif i % 3 == 1 then rgb(170, 120, 150)
				else rgb(220, 200, 120)
			ball(c, math.sin(angle) * 3.55, 1.3, cz + math.cos(angle) * 3.55, 0.5, color)
		end
		-- 다이빙 보트
		local boat = CFrame.new(3.4, 1.45, -3.3) * CFrame.Angles(0, 0.6, 0)
		block(c, boat, V(0.6, 0.3, 1.6), WHITE)
		block(c, boat * CFrame.new(0, 0.3, 0.2), V(0.5, 0.35, 0.6), rgb(40, 90, 180))
		-- 야자수 모래톱
		local px, pz = -3.5, -3.4
		col(c, px, 0.9, pz, 0.5, 1.8, SAND, Mat.Sand)
		beam(c, V(px, 1.4, pz), V(px + 0.4, 3.1, pz - 0.1), 0.18, WOOD, Mat.Wood)
		for k = 0, 3 do
			local rot = CFrame.new(px + 0.4, 3.05, pz - 0.1) * CFrame.Angles(0, k * PI / 2 + 0.4, 0)
			block(
				c,
				rot * CFrame.new(0, -0.15, -0.55) * CFrame.Angles(-0.35, 0, 0),
				V(0.35, 0.06, 1.2),
				LEAF,
				Mat.Grass
			)
		end
	end

	-- 올멕 거대 두상: 잔디 + 흙바닥 + 현무암 두상(정면에서 둥근 투구 + 이마 띠와 가운데 장식, 귀 덮개와 귀걸이,
	--   부은 볼, 무거운 눈꺼풀과 아몬드 눈, 넓적한 코, 두툼한 입술) + 밀림
	B.olmechead = function(c)
		local stone = c.P
		local helmet = mix(c.P, BLACK, 0.1)
		local deep = mix(c.P, BLACK, 0.5)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, c.S, Mat.Grass)
		box(c, 0, 0.25, 0.4, 7.8, 0.3, 7, mix(c.A, ROCK, 0.35), Mat.Ground)
		-- 얼굴 덩어리: 턱 + 볼 + 이마
		box(c, 0, 0.55, 0.7, 5.8, 3.4, 5, stone)
		ball(c, -1.8, 2.85, -0.55, 3.2, stone)
		ball(c, 1.8, 2.85, -0.55, 3.2, stone)
		box(c, 0, 3.9, 0.7, 6, 2.4, 5.2, stone)
		-- 투구: 정면에서 둥근 돔 + 이마 띠 + 장식 + 귀 덮개와 귀걸이
		cyl(c, CFrame.new(0, 6, 0.8) * ALONG_Z, 5.4, 6.8, helmet)
		box(c, 0, 5.8, -2.3, 6.5, 0.8, 0.4, helmet)
		box(c, 0, 5.7, -2.62, 1.2, 1.1, 0.3, mix(helmet, WHITE, 0.08))
		ball(c, 0, 7, -2.1, 1.1, helmet)
		for _, sx in { -1, 1 } do
			box(c, sx * 3.1, 1.6, 0.9, 0.6, 4.9, 3, helmet)
			cyl(c, CFrame.new(sx * 3.5, 3.1, 0.3), 0.35, 1.4, helmet)
			col(c, sx * 3.1, 1, 0.9, 0.7, 0.9, helmet)
			-- 아몬드 눈(눈꺼풀 + 어두운 눈)
			block(c, CFrame.new(sx * 1.35, 4.95, -2.13) * CFrame.Angles(0, 0, sx * 0.14), V(1.5, 0.45, 0.1), deep)
			block(c, CFrame.new(sx * 1.35, 5.25, -2.25) * CFrame.Angles(0, 0, sx * 0.14), V(1.7, 0.3, 0.3), stone)
		end
		-- 코 + 입술
		wedge(c, CFrame.new(0, 4, -2.45), V(1.7, 2, 0.9), stone)
		ball(c, -0.72, 3.3, -2.35, 0.95, stone)
		ball(c, 0.72, 3.3, -2.35, 0.95, stone)
		cyl(c, CFrame.new(0, 2.45, -2.1), 2.4, 0.75, stone)
		cyl(c, CFrame.new(0, 1.8, -2.05), 2.1, 0.75, stone)
		box(c, 0, 2.05, -2.45, 1.9, 0.12, 0.1, deep)
		plant(c, -4, 0.25, 3.8, 2.2, 1.8, LEAF)
		plant(c, 4, 0.25, 3.6, 1.8, 1.6, c.S)
		ball(c, -4.1, 0.8, -3.9, 1.4, LEAF, Mat.Grass)
		ball(c, 4.2, 0.7, -4, 1.2, c.S, Mat.Grass)
	end

	-- 엘도라도: 밀림 + 앞쪽 둥근 호수(과타비타)에 뜬 황금 뗏목과 황금 왕 + 뒤쪽 황금 도시
	--   (성벽과 문, 가운데 계단 피라미드 신전과 빛나는 태양 원반, 양쪽 황금 탑, 황금 집들) + 밀림 나무
	B.eldorado = function(c)
		local gold, deep, glow = c.P, c.S, c.A
		local jungle = rgb(50, 120, 60)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(jungle, BLACK, 0.2), Mat.Grass)
		col(c, 0, 0.25, -3.1, 0.06, 3.4, WATER, Mat.Glass, 0.1)
		box(c, 0, 0.31, -3.1, 1.3, 0.14, 0.8, gold)
		col(c, 0, 0.45, -3.1, 0.7, 0.36, glow, Mat.Neon)
		ball(c, 0, 1.3, -3.1, 0.36, glow, Mat.Neon)
		ball(c, 0.9, 0.35, -2.4, 0.25, glow, Mat.Neon)
		-- 성벽 + 문
		box(c, -2.7, 0.25, -0.9, 3.8, 1, 0.4, deep)
		box(c, 2.7, 0.25, -0.9, 3.8, 1, 0.4, deep)
		box(c, -0.6, 0.25, -0.9, 0.5, 1.8, 0.6, gold)
		box(c, 0.6, 0.25, -0.9, 0.5, 1.8, 0.6, gold)
		box(c, 0, 2.05, -0.9, 1.8, 0.35, 0.7, gold)
		-- 계단 피라미드 신전 + 태양 원반
		local y = 0.25
		for _, w in { 4.8, 3.9, 3, 2.2 } do
			box(c, 0, y, 2.4, w, 1.1, w, if w == 3.9 or w == 2.2 then deep else gold)
			y += 1.1
		end
		wedge(c, CFrame.new(0, 0.25 + (y - 0.25) / 2, 0.55), V(1, y - 0.25, 1.3), glow)
		box(c, 0, y, 2.4, 1.5, 1.2, 1.5, gold)
		box(c, 0, y + 1.2, 2.4, 1.8, 0.3, 1.8, deep)
		cyl(c, CFrame.new(0, y + 2.8, 2.6) * ALONG_Z, 0.2, 2.4, glow, Mat.Neon)
		cyl(c, CFrame.new(0, y + 2.8, 2.7) * ALONG_Z, 0.15, 3, gold)
		-- 양쪽 황금 탑
		for _, sx in { -1, 1 } do
			col(c, sx * 3.6, 0.25, 2.6, 4.6, 1.3, gold)
			ball(c, sx * 3.6, 5, 2.6, 1.5, gold)
			col(c, sx * 3.6, 5.6, 2.6, 1, 0.14, glow)
			ball(c, sx * 3.6, 6.7, 2.6, 0.35, glow, Mat.Neon)
			box(c, sx * 2.4, 0.25, 0.5, 1.3, 1, 1.1, gold)
			gable(c, sx * 2.4, 1.25, 0.5, 1.4, 1.2, 0.6, deep)
			box(c, sx * 3.9, 0.25, 4.3, 1.2, 1.4, 1, deep)
		end
		plant(c, -4.1, 0.25, -1.8, 1.4, 1.5, jungle)
		plant(c, 4.1, 0.25, -2.2, 1.2, 1.4, LEAF)
		ball(c, -3.9, 0.9, -4, 1.4, LEAF, Mat.Grass)
		ball(c, 3.9, 0.8, -4.1, 1.3, jungle, Mat.Grass)
	end

	return B
end
