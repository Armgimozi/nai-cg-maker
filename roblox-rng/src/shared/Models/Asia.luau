-- 아시아 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 숭례문(gate) · 만리장성(wall) · 페트라(facade) · 바벨탑(spiral) 은 원래 그 명소를 위해 만든 모양을 그대로 씀.

return function(K)
	local B = {}

	local V, rgb, Mat, PI, TAU = K.V, K.rgb, K.Mat, K.PI, K.TAU
	local ALONG_Z, CORNERS = K.ALONG_Z, K.CORNERS
	local GRASS, LEAF, WATER, DARK, TILE = K.GRASS, K.LEAF, K.WATER, K.DARK, K.TILE
	local ROCK, WOOD, SAND, CLOUD, BLACK, WHITE = K.ROCK, K.WOOD, K.SAND, K.CLOUD, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local roof, gable, plant, clockFace = K.roof, K.gable, K.plant, K.clockFace

	-- 정면(-Z)에서 삼각형이 보이는 박공(용마루가 Z 방향). 바닥 y, 폭 w(X), 깊이 d(Z), 높이 h
	local function frontGable(c, x, y, z, w, d, h, color, material)
		wedge(c, CFrame.new(x - w / 4, y + h / 2, z) * CFrame.Angles(0, PI / 2, 0), V(d, h, w / 2), color, material)
		wedge(c, CFrame.new(x + w / 4, y + h / 2, z) * CFrame.Angles(0, -PI / 2, 0), V(d, h, w / 2), color, material)
	end

	-- 홍콩 시계탑: 붉은 벽돌 + 화강암 띠 탑신, 세 면 시계, 팔각 등롱 + 작은 돔 + 긴 피뢰침
	B.clocktower = function(c)
		local brick = rgb(178, 86, 60)
		local granite = mix(c.P, WHITE, 0.35)
		box(c, 0, 0, 0, 7.4, 0.3, 7.4, mix(c.P, WHITE, 0.55))
		box(c, 0, 0.3, 0, 4.4, 0.8, 4.4, granite)
		box(c, 0, 1.1, 0, 3.6, 10.2, 3.6, brick)
		for _, y in { 3.8, 6.6, 9.4 } do
			box(c, 0, y, 0, 3.8, 0.3, 3.8, granite)
		end
		box(c, 0, 1.1, -1.83, 1.2, 2.2, 0.1, DARK)
		box(c, 0, 4.6, -1.83, 0.5, 1.4, 0.1, DARK)
		box(c, 0, 7.4, -1.83, 0.5, 1.4, 0.1, DARK)
		box(c, 0, 11.3, 0, 4.3, 0.35, 4.3, granite)
		box(c, 0, 11.65, 0, 4, 3.1, 4, brick)
		for _, i in { 0, 1, 3 } do
			clockFace(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 13.2, -2), 2.6)
		end
		box(c, 0, 14.75, 0, 4.5, 0.4, 4.5, granite)
		-- 팔각 등롱(사각 두 개를 45도 엇갈림) + 아치 창
		box(c, 0, 15.15, 0, 2.8, 2, 2.8, brick)
		block(c, CFrame.new(0, 16.15, 0) * CFrame.Angles(0, PI / 4, 0), V(2.8, 2, 2.8), brick)
		for i = 0, 3 do
			block(c, CFrame.Angles(0, i * PI / 2, 0) * CFrame.new(0, 16.1, -1.42), V(0.6, 1.2, 0.1), DARK)
		end
		col(c, 0, 17.15, 0, 0.3, 3.4, granite)
		col(c, 0, 17.45, 0, 0.7, 2.2, brick)
		ball(c, 0, 18.15, 0, 2.2, c.S)
		col(c, 0, 19.1, 0, 0.5, 0.5, granite)
		col(c, 0, 19.6, 0, 2.3, 0.14, c.S, Mat.Metal)
	end

	-- 첨성대: 잔디 + 네모 2단 기단 + 아래가 불룩한 병 모양 돌 원통(돌 켜) + 남쪽 네모 창 + 꼭대기 井 자 정자석 2단
	B.cheomseongdae = function(c)
		col(c, 0, 0, 0, 0.2, 9.6, GRASS, Mat.Grass)
		local stone = mix(c.S, WHITE, 0.15)
		box(c, 0, 0.2, 0, 5.6, 0.45, 5.6, stone)
		box(c, 0, 0.65, 0, 5, 0.45, 5, stone)
		local y = 1.1
		local courses = 11
		local courseH = 0.85
		for k = 0, courses - 1 do
			local t = (k + 0.5) / courses
			local d = 2.7 + 2.1 * (1 - t) ^ 2.2
			col(c, 0, y, 0, courseH, d, if k % 2 == 0 then c.P else mix(c.P, c.S, 0.3))
			y += courseH
		end
		box(c, 0, 4.5, -1.6, 1.1, 1.1, 0.4, DARK)
		for layer = 0, 1 do
			local ly = y + layer * 0.76
			for _, s in { -1, 1 } do
				box(c, 0, ly, s * 1, 3.1, 0.38, 0.4, c.P)
				box(c, s * 1, ly + 0.38, 0, 0.4, 0.38, 3.1, c.P)
			end
		end
		ball(c, -3.4, 0.6, -3.2, 1.1, LEAF, Mat.Grass)
		ball(c, 3.5, 0.65, 3.1, 1.2, LEAF, Mat.Grass)
		ball(c, 3.6, 0.5, -2.9, 0.9, LEAF, Mat.Grass)
	end

	-- 성산일출봉: 바다 위로 솟은 왕관 모양 분화구(가파른 주름 절벽 + 둘레 봉우리 + 안쪽 풀밭)
	--   + 뒤쪽 육지로 이어지는 풀밭 능선 + 떠오르는 해
	B.seongsan = function(c)
		local sea = mix(WATER, c.S, 0.35)
		local tuff = rgb(128, 104, 78)
		local green = c.P
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, sea, Mat.Glass, 0.1)
		box(c, 1.6, 0, 4.2, 6.6, 0.6, 1.6, GRASS, Mat.Grass)
		local cx, cz = -0.4, -0.6
		col(c, cx, 0, cz, 0.9, 8.6, mix(tuff, ROCK, 0.4))
		col(c, cx, 0.9, cz, 1.7, 8, tuff)
		col(c, cx, 2.6, cz, 1.5, 7.5, green, Mat.Grass)
		col(c, cx, 4.1, cz, 0.12, 6.4, mix(green, GRASS, 0.5), Mat.Grass)
		-- 절벽 주름
		for i = 0, 7 do
			local cf = CFrame.new(cx, 0, cz) * CFrame.Angles(0, (i + 0.5) / 8 * TAU, 0)
			block(c, cf * CFrame.new(0, 2.5, -3.95) * CFrame.Angles(0.12, 0, 0), V(0.8, 3.4, 0.6), mix(tuff, BLACK, 0.12))
		end
		-- 둘레 봉우리(왕관)
		local n = 14
		for i = 0, n - 1 do
			local h = if i % 2 == 0 then 1.7 else 1.1
			local cf = CFrame.new(cx, 0, cz)
				* CFrame.Angles(0, i / n * TAU, 0)
				* CFrame.new(0, 4.1 + h / 2 - 0.2, -3.35)
				* CFrame.Angles(-0.2, 0, 0)
			local rocky = i % 3 == 0
			block(c, cf, V(1.55, h, 0.8), if rocky then tuff else green, if rocky then nil else Mat.Grass)
		end
		-- 육지에서 분화구로 오르는 능선
		wedge(c, CFrame.new(1.9, 0.6 + 1.5, 3.1) * CFrame.Angles(0, PI, 0), V(2.2, 3, 3), GRASS, Mat.Grass)
		ball(c, 4, 0.9, 4.2, 1, LEAF, Mat.Grass)
		ball(c, -1.4, 0.9, 4.3, 0.9, LEAF, Mat.Grass)
		-- 떠오르는 해
		cyl(c, CFrame.new(3.3, 7.4, 3.6) * ALONG_Z, 0.2, 2.4, c.A, Mat.Neon)
		cyl(c, CFrame.new(3.3, 7.4, 3.75) * ALONG_Z, 0.1, 3.4, c.A, Mat.Neon, 0.6)
	end

	-- 하와마할: 분홍 사암의 얇은 5층 정면. 위로 갈수록 좁아지는 피라미드 윤곽 + 층마다 크림색 띠
	--   + 튀어나온 창 기둥(자로카) 줄 + 기둥마다 작은 돔 + 꼭대기 정자
	B.hawamahal = function(c)
		local wall = c.S
		local bay = c.P
		local trim = c.A
		local front = -0.8
		box(c, 0, 0, -2.6, 9.8, 0.15, 3.6, rgb(205, 190, 165))
		-- 층 덩어리: { 폭, 바닥, 꼭대기, 깊이 }
		local levels = {
			{ 9.6, 0, 2.6, 3.2 },
			{ 9.6, 2.6, 4.8, 2.8 },
			{ 7.8, 4.8, 7, 2.4 },
			{ 5.8, 7, 9, 2 },
			{ 3.6, 9, 10.8, 1.6 },
		}
		for _, l in levels do
			box(c, 0, l[2], front + l[4] / 2, l[1], l[3] - l[2], l[4], wall)
		end
		box(c, 0, 0.15, front - 0.03, 1.4, 1.9, 0.08, DARK)
		-- 창 기둥: { x, 꼭대기 }
		local bays = {
			{ 0, 10.8 },
			{ -1.2, 10.8 },
			{ 1.2, 10.8 },
			{ -2.4, 9 },
			{ 2.4, 9 },
			{ -3.5, 7 },
			{ 3.5, 7 },
			{ -4.4, 4.8 },
			{ 4.4, 4.8 },
		}
		for _, b in bays do
			local x, top = b[1], b[2]
			block(c, CFrame.new(x, (2.6 + top) / 2, front) * CFrame.Angles(0, PI / 4, 0), V(0.85, top - 2.6, 0.85), bay)
			ball(c, x, top + 0.05, front - 0.15, 0.8, bay)
		end
		-- 층 띠(돌출 처마) + 층 가운데 가는 띠
		for k = 2, 5 do
			local l = levels[k]
			box(c, 0, l[2] - 0.09, front - 0.35, levels[k - 1][1] + 0.1, 0.18, 0.75, trim)
			box(c, 0, (l[2] + l[3]) / 2, front - 0.3, l[1], 0.1, 0.72, trim)
		end
		box(c, 0, 10.72, front - 0.35, 3.7, 0.16, 0.75, trim)
		col(c, 0, 10.8, -0.1, 0.8, 1.4, bay)
		ball(c, 0, 11.6, -0.1, 1.3, bay)
		col(c, 0, 12.15, -0.1, 0.5, 0.15, trim)
	end

	-- 히메지성: 잔디 + 비스듬한 돌 기단 + 흰 회벽 5층 천수각(층마다 회색 기와 처마 + 박공)
	--   + 앞쪽 치도리하후(삼각 박공)·가라하후(둥근 박공) + 금빛 샤치호코 + 뒤쪽 작은 천수 2
	B.himeji = function(c)
		local stone = mix(ROCK, WHITE, 0.25)
		local roofC = c.S
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, GRASS, Mat.Grass)
		box(c, 0, 0.25, 0.3, 8, 1.2, 7, stone, Mat.Slate)
		box(c, 0, 1.45, 0.3, 7.2, 1.2, 6.2, stone, Mat.Slate)
		-- 작은 천수(뒤 양쪽)
		for _, sx in { -1, 1 } do
			box(c, sx * 2.6, 2.65, 2.4, 1.8, 1.5, 1.6, c.P)
			box(c, sx * 2.6, 4.15, 2.4, 2.5, 0.2, 2.3, roofC)
			gable(c, sx * 2.6, 4.35, 2.4, 2.2, 2, 0.7, roofC)
		end
		-- { 몸체 폭, 깊이, 높이, 지붕 높이 }
		local tiers = {
			{ 6.2, 4.6, 1.9, 0.9 },
			{ 5.2, 3.9, 1.5, 0.8 },
			{ 4.3, 3.3, 1.4, 0.75 },
			{ 3.4, 2.7, 1.3, 0.7 },
			{ 2.6, 2.1, 1.2, 1.1 },
		}
		local y = 2.65
		local z = 0
		local top = 0
		local lastW = 0
		for k, t in tiers do
			local w, d, h, rh = t[1], t[2], t[3], t[4]
			box(c, 0, y, z, w, h, d, c.P)
			if k <= 3 then
				box(c, 0, y + h * 0.4, z - d / 2 - 0.03, w * 0.6, 0.28, 0.06, DARK)
			end
			local ey = y + h
			box(c, 0, ey, z, w + 1.1, 0.22, d + 1.1, roofC)
			gable(c, 0, ey + 0.22, z, w + 0.7, d + 0.7, rh, roofC)
			if k == 2 or k == 4 then
				frontGable(c, 0, ey + 0.22, z - d / 2 - 0.1, w * 0.5, 1.2, rh * 1.35, roofC)
			elseif k == 1 then
				cyl(c, CFrame.new(0, ey + 0.25, z - d / 2 - 0.35), 2, 0.9, roofC)
			end
			top = ey + 0.22 + rh
			lastW = w + 0.7
			y = ey + 0.22 + rh * 0.55
		end
		for _, sx in { -1, 1 } do
			block(c, CFrame.new(sx * (lastW / 2 - 0.25), top + 0.1, z) * CFrame.Angles(0, 0, sx * 0.3), V(0.22, 0.6, 0.3), c.A, Mat.Metal)
		end
	end

	-- 파묵칼레: 흰 석회 언덕(뒤) + 앞으로 계단처럼 내려오는 반원 석회붕 + 옥빛 물웅덩이 + 언덕 위 히에라폴리스 기둥
	B.pamukkale = function(c)
		local white = c.P
		local pool = c.S
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(white, SAND, 0.3), Mat.Salt)
		box(c, 0, 0.2, -4.4, 9.8, 0.1, 1, GRASS, Mat.Grass)
		box(c, 0, 0.2, 3.5, 9.8, 5.2, 2.8, white)
		-- 석회붕 줄: { z, 윗면, 지름, x 목록 }
		local rows = {
			{ 2, 4.9, 2.8, { -3.4, -0.5, 2.5 } },
			{ 0.2, 3.5, 2.6, { -2.3, 0.6, 3.5 } },
			{ -1.6, 2.2, 2.5, { -3.6, -0.7, 2.2 } },
			{ -3.2, 1, 2.2, { -2.2, 0.6, 3.5 } },
		}
		for _, row in rows do
			local z, top, d = row[1], row[2], row[3]
			for _, x in row[4] do
				col(c, x, 0.2, z, top - 0.2, d, white)
				col(c, x, top - 0.02, z, 0.1, d - 0.4, pool, Mat.Glass, 0.05)
			end
		end
		-- 언덕 위 유적 + 나무
		for _, x in { -3.6, -2.6, -1.6 } do
			col(c, x, 5.4, 3.4, 1.6, 0.35, mix(white, SAND, 0.45))
		end
		box(c, -2.6, 7, 3.4, 2.6, 0.3, 0.5, mix(white, SAND, 0.45))
		plant(c, 2.4, 5.4, 3.6, 1, 1.3, LEAF)
		plant(c, 3.8, 5.4, 3.2, 0.8, 1.1, LEAF)
	end

	-- 후지산: 숲 + 앞쪽 호수 + 아래가 넓게 퍼진 대칭 원뿔(얇은 원통 켜) + 흰 눈 모자 + 흘러내린 눈 줄기
	--   + 벚꽃 나무 + 붉은 5층탑(추레이토)
	B.fuji = function(c)
		local forest = mix(LEAF, c.P, 0.25)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, forest, Mat.Grass)
		box(c, 0, 0.25, -4.25, 9.8, 0.05, 1.3, WATER, Mat.Glass, 0.1)
		local cx, cz = 0, 0.6
		local n = 12
		local layer = 0.45
		local y = 0.25
		local radius = {}
		for k = 0, n - 1 do
			local t = k / (n - 1)
			local d = 1.9 + 6.5 * (1 - t) ^ 1.5
			radius[k] = d / 2
			local snowy = k >= 7
			col(c, cx, y, cz, layer, d, if snowy then c.S else c.P, if snowy then Mat.Snow else nil)
			y += layer
		end
		-- 눈 줄기: 눈선에서 비탈을 따라 흘러내림
		for i = 0, 5 do
			local a = (i + 0.5) / 6 * TAU
			local dir = V(math.sin(a), 0, -math.cos(a))
			local k1, k2 = 7, if i % 2 == 0 then 3 else 4
			local p1 = V(cx, 0.25 + (k1 + 0.5) * layer, cz) + dir * (radius[k1] + 0.05)
			local p2 = V(cx, 0.25 + (k2 + 0.5) * layer, cz) + dir * (radius[k2] + 0.05)
			beam(c, p1, p2, 0.4, c.S, Mat.Snow)
		end
		-- 벚꽃
		plant(c, -4, 0.25, -2.9, 0.9, 1.4, c.A)
		plant(c, -3, 0.25, -3.5, 0.7, 1.1, c.A)
		plant(c, 2.6, 0.25, -3.6, 0.7, 1.1, c.A)
		-- 추레이토 탑
		local red = rgb(200, 60, 50)
		local px, pz = 3.9, -2.9
		local py = 0.25
		for k = 0, 2 do
			local w = 0.9 - k * 0.15
			box(c, px, py, pz, w, 0.6, w, red)
			box(c, px, py + 0.6, pz, w + 0.6, 0.14, w + 0.6, TILE)
			py += 0.74
		end
		col(c, px, py, pz, 0.7, 0.12, c.A, Mat.Metal)
	end

	-- 석굴암: 안이 보이게 앞을 연 둥근 돌방(돌판 벽 + 안으로 기운 궁륭 2단) + 연꽃 대좌 위 흰 본존불
	--   + 뒤벽의 둥근 광배 + 앞쪽 팔각 돌기둥 2개
	B.seokguram = function(c)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, GRASS, Mat.Grass)
		col(c, 0, 0.25, 0.9, 0.3, 8.2, c.S)
		box(c, 0, 0.25, -3.4, 3.8, 0.3, 2.6, c.S)
		local center = CFrame.new(0, 0, 0.9)
		local shells = {
			-- { 반지름, 바닥, 높이, 기울기, 개수, 각도 범위 }
			{ 3.7, 0.55, 2.9, 0, 7, 105 },
			{ 3.35, 3.45, 1.45, 0.4, 7, 105 },
			{ 2.55, 4.9, 1.2, 0.8, 5, 80 },
		}
		for k, s in shells do
			local r, y0, h, tilt, count, range = s[1], s[2], s[3], s[4], s[5], s[6]
			local step = 2 * range / (count - 1)
			local w = 2 * r * math.sin(math.rad(step / 2)) + 0.18
			for i = 0, count - 1 do
				local a = math.rad(-range + i * step)
				local cf = center * CFrame.Angles(0, a, 0) * CFrame.new(0, y0 + h / 2, r) * CFrame.Angles(-tilt, 0, 0)
				block(c, cf, V(w, h, 0.5), if (i + k) % 2 == 0 then c.P else mix(c.P, c.S, 0.25))
			end
		end
		-- 본존불
		local bz = 1.3
		col(c, 0, 0.55, bz, 0.45, 3, c.S)
		col(c, 0, 1, bz, 0.7, 1.7, c.P)
		col(c, 0, 1.7, bz, 0.45, 3.1, c.P)
		box(c, 0, 2.15, bz - 0.2, 2.9, 0.8, 1.9, c.P)
		box(c, 0, 2.95, bz + 0.15, 1.8, 1.9, 1.1, c.P)
		cyl(c, CFrame.new(0, 4.6, bz + 0.15), 2.1, 0.8, c.P)
		beam(c, V(-1, 4.5, bz), V(-0.5, 3.1, bz - 0.8), 0.45, c.P)
		beam(c, V(1, 4.5, bz), V(1.1, 3, bz - 0.9), 0.45, c.P)
		ball(c, 0, 5.55, bz + 0.1, 1.3, c.P)
		ball(c, 0, 6.2, bz + 0.15, 0.65, c.P)
		cyl(c, CFrame.new(0, 5.7, 3.6) * ALONG_Z, 0.15, 2.6, c.A, Mat.Neon)
		for _, sx in { -1, 1 } do
			col(c, sx * 1.7, 0.55, -2.9, 3.4, 0.6, c.P)
		end
	end

	-- 아야 소피아: 분홍빛 본당 + 네모 받침 + 창문 띠 위의 납작한 큰 돔 + 앞뒤로 내려앉은 반구 돔
	--   + 버팀벽 + 모서리의 가는 첨탑 4개(연필 모양 지붕)
	B.hagiasophia = function(c)
		local dome = c.S
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.P, WHITE, 0.55))
		box(c, 0, 0.25, 0.2, 6.8, 3.2, 6.4, c.P)
		box(c, 0, 0.25, -3.5, 5.4, 2.4, 1.2, mix(c.P, WHITE, 0.1))
		box(c, 0, 3.45, 0.2, 5.6, 1.5, 5.6, c.P)
		for _, s in CORNERS do
			box(c, s[1] * 2.75, 3.45, 0.2 + s[2] * 1.7, 0.9, 2.2, 1.3, mix(c.P, BLACK, 0.08))
		end
		col(c, 0, 4.95, 0.2, 0.6, 5.4, mix(c.P, BLACK, 0.35))
		ball(c, 0, 4.6, 0.2, 5.4, dome)
		ball(c, 0, 3.45, -2.5, 3.6, dome)
		ball(c, 0, 3.45, 2.9, 3.6, dome)
		col(c, 0, 7.2, 0.2, 0.7, 0.14, c.A, Mat.Metal)
		ball(c, 0, 8, 0.2, 0.35, c.A, Mat.Neon)
		for _, s in CORNERS do
			local x, z = s[1] * 4.3, s[2] * 4.3
			col(c, x, 0.25, z, 9.15, 0.55, c.P)
			col(c, x, 7, z, 0.25, 0.9, mix(c.P, WHITE, 0.3))
			col(c, x, 9.4, z, 0.7, 0.5, dome)
			col(c, x, 10.1, z, 1, 0.26, dome)
		end
	end

	-- 카파도키아: 모래빛 골짜기 + 검은 모자를 쓴 요정 굴뚝 바위들(동굴 창) + 하늘에 뜬 열기구 3개
	B.cappadocia = function(c)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.S, SAND, 0.35), Mat.Sand)
		local capColor = mix(c.S, DARK, 0.45)
		local function chimney(x, z, h, d, cave)
			col(c, x, 0.3, z, h * 0.45, d, c.P)
			col(c, x, 0.3 + h * 0.45, z, h * 0.33, d * 0.7, c.P)
			col(c, x, 0.3 + h * 0.78, z, h * 0.22, d * 0.45, mix(c.P, c.S, 0.4))
			ball(c, x, 0.3 + h + d * 0.08, z, d * 0.62, capColor)
			if cave then
				box(c, x, 0.3 + h * 0.2, z - d / 2, 0.4, 0.55, 0.2, DARK)
			end
		end
		chimney(-3.2, 2.4, 6.5, 2.2, true)
		chimney(-0.4, 3.2, 8, 2.4, false)
		chimney(2.6, 2.5, 7, 2.2, true)
		chimney(3.6, -1.2, 5, 1.9, false)
		chimney(-3.4, -1.6, 4.4, 1.8, true)
		chimney(0.5, 0, 5.4, 2, true)
		local function balloon(x, y, z, d, color, stripe)
			ball(c, x, y, z, d, color)
			col(c, x, y - 0.15, z, 0.35, d + 0.04, stripe)
			col(c, x, y - d * 0.62, z, d * 0.3, d * 0.42, color)
			box(c, x, y - d * 0.5 - 0.9, z, 0.45, 0.4, 0.45, WOOD, Mat.Wood)
		end
		balloon(-2.6, 13.5, -1.2, 2.2, c.A, rgb(255, 205, 70))
		balloon(2.4, 15.8, 0.8, 2, rgb(255, 205, 70), c.A)
		balloon(0.3, 11, -3, 1.6, rgb(70, 140, 230), WHITE)
	end

	-- 자금성(태화전): 돌 포장 광장 + 흰 대리석 3단 기단과 가운데 계단 + 붉은 기둥 전각
	--   + 금빛 기와의 겹처마 지붕(아래 처마 + 위 지붕) + 치문 장식 + 청동 향로
	B.forbiddencity = function(c)
		local marble = c.A
		local red = c.P
		local gold = c.S
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, rgb(172, 166, 158))
		box(c, 0, 0.2, 0.6, 9.2, 0.55, 7.6, marble)
		box(c, 0, 0.75, 0.7, 8.4, 0.55, 6.8, marble)
		box(c, 0, 1.3, 0.8, 7.6, 0.55, 6, marble)
		wedge(c, CFrame.new(0, 0.2 + 0.825, -3.55), V(1.6, 1.65, 1.8), mix(marble, WHITE, 0.3))
		box(c, 0, 1.85, 1.1, 6.4, 2.2, 3.4, mix(red, BLACK, 0.3))
		for k = 0, 5 do
			col(c, -2.75 + k * 1.1, 1.85, -0.85, 2.2, 0.36, red)
		end
		roof(c, 0, 4.05, 0.9, 8.2, 5.4, 0.9, gold)
		box(c, 0, 5, 0.9, 5.2, 1, 2.9, red)
		roof(c, 0, 6, 0.9, 7.4, 4.6, 1.6, gold)
		for _, sx in { -1, 1 } do
			box(c, sx * 3.35, 7.7, 0.9, 0.35, 0.7, 0.45, mix(gold, BLACK, 0.25))
			col(c, sx * 3.2, 1.85, -1.8, 0.55, 0.5, rgb(70, 80, 70), Mat.Metal)
		end
	end

	-- 진시황 병마용: 흙 구덩이(뒤·옆 둑 + 칸막이 흙벽 3줄) + 칸마다 앞을 보고 줄지어 선 흙빛 병사 4x4
	B.terracotta = function(c)
		local earth = mix(c.S, SAND, 0.25)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(earth, BLACK, 0.12))
		box(c, 0, 0.3, 4.5, 9.8, 1.5, 0.8, earth)
		for _, sx in { -1, 1 } do
			box(c, sx * 4.6, 0.3, 0, 0.6, 1.5, 9.8, earth)
		end
		for _, x in { -2.2, 0, 2.2 } do
			box(c, x, 0.3, 0.3, 0.5, 1.2, 7.8, earth)
		end
		local xs = { -3.3, -1.1, 1.1, 3.3 }
		local zs = { -3.1, -1.4, 0.3, 2 }
		for i, x in xs do
			for j, z in zs do
				local shade = if (i + j) % 2 == 0 then c.P else mix(c.P, c.A, 0.35)
				box(c, x, 0.3, z, 0.8, 1.55, 0.55, shade)
				ball(c, x, 2.1, z, 0.55, shade)
			end
		end
	end

	-- 아르테미스 신전: 3단 기단 + 앞쪽 두 줄·옆 한 줄의 가늘고 높은 이오니아식 기둥 숲
	--   + 금빛 기둥머리 띠 + 엔타블러처와 금빛 프리즈 + 정면 박공 + 금빛 아크로테리아
	B.artemis = function(c)
		local marble = c.P
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.S, GRASS, 0.3), Mat.Grass)
		box(c, 0, 0.2, 0.2, 9.4, 0.4, 9.4, c.S)
		box(c, 0, 0.6, 0.2, 8.8, 0.4, 8.8, mix(c.S, marble, 0.5))
		box(c, 0, 1, 0.2, 8.2, 0.4, 8.2, marble)
		box(c, 0, 1.4, 1, 4.6, 6, 5.6, mix(c.S, marble, 0.3))
		box(c, 0, 1.4, -1.82, 1.4, 3.2, 0.1, DARK)
		for k = 0, 7 do
			local x = -3.5 + k
			col(c, x, 1.4, -3.5, 6, 0.5, marble)
			col(c, x, 1.4, -2.4, 6, 0.5, marble)
		end
		for _, sx in { -1, 1 } do
			for _, z in { -1.2, 0.3, 1.8, 3.3 } do
				col(c, sx * 3.5, 1.4, z, 6, 0.5, marble)
			end
		end
		box(c, 0, 7.4, 0.2, 7.9, 0.25, 8, c.A)
		box(c, 0, 7.65, 0.2, 8.2, 0.8, 8.2, marble)
		box(c, 0, 7.9, -3.93, 7.8, 0.28, 0.06, c.A)
		frontGable(c, 0, 8.45, 0.2, 8.2, 8.2, 1.7, marble)
		ball(c, 0, 10.2, -3.8, 0.5, c.A, Mat.Metal)
		ball(c, -3.9, 8.7, -3.8, 0.45, c.A, Mat.Metal)
		ball(c, 3.9, 8.7, -3.8, 0.45, c.A, Mat.Metal)
	end

	-- 황룡사 9층 목탑: 돌 기단 + 위로 갈수록 좁아지는 9층 붉은 목조 몸체(초록 단청 공포 + 넓은 기와 처마)
	--   + 금빛 상륜부
	B.hwangnyongsa = function(c)
		local stone = rgb(190, 185, 175)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(SAND, GRASS, 0.3), Mat.Grass)
		box(c, 0, 0.2, 0, 7.6, 0.5, 7.6, stone)
		box(c, 0, 0.7, 0, 6.6, 0.35, 6.6, stone)
		wedge(c, CFrame.new(0, 0.2 + 0.425, -4.3), V(1.6, 0.85, 1), stone)
		local y = 1.05
		for k = 0, 8 do
			local t = k / 8
			local w = 4.6 - 2.2 * t
			local h = 1.35 - 0.3 * t
			box(c, 0, y, 0, w, h, w, c.P)
			box(c, 0, y + h - 0.28, 0, w + 0.3, 0.28, w + 0.3, c.S)
			local rw = w + 2 - 0.6 * t
			box(c, 0, y + h, 0, rw, 0.32, rw, TILE)
			y += h + 0.32
		end
		col(c, 0, y, 0, 0.5, 1.2, TILE)
		col(c, 0, y + 0.5, 0, 3.6, 0.2, c.A, Mat.Metal)
		for k = 0, 2 do
			col(c, 0, y + 1.1 + k * 0.6, 0, 0.12, 0.8 - k * 0.12, c.A, Mat.Metal)
		end
		ball(c, 0, y + 4.2, 0, 0.45, c.A, Mat.Neon)
	end

	-- 샹그릴라: 푸른 골짜기 + 뒤쪽의 눈 덮인 뾰족 봉우리 3개(가운데 카라칼) + 흰 벽과 금빛 지붕의 라마 사원
	--   (본전 + 누각 + 양쪽 곁채) + 빛나는 창 + 개울 + 꽃나무 + 떠다니는 빛 구슬
	B.shangrila = function(c)
		local rock = rgb(112, 120, 138)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, rgb(110, 185, 90), Mat.Grass)
		box(c, 0, 0.3, -4.3, 9.8, 0.05, 0.7, WATER, Mat.Glass, 0.1)
		local function peak(x, z, w, h, d)
			frontGable(c, x, 0.3, z, w, d, h, rock, Mat.Slate)
			local sh = h * 0.38
			local sw = w * sh / h
			frontGable(c, x, 0.3 + h + 0.12 - sh, z, sw, d + 0.2, sh, CLOUD, Mat.Snow)
		end
		peak(-2.4, 3.2, 5, 7.5, 2.4)
		peak(3.2, 3, 3.4, 6.2, 2.2)
		peak(0.6, 3.9, 7, 12.5, 2)
		local stone = mix(c.P, SAND, 0.35)
		box(c, 0, 0.3, -0.6, 7.2, 0.9, 4.4, stone)
		wedge(c, CFrame.new(0, 0.75, -3.3), V(1.4, 0.9, 1), stone)
		box(c, 0, 1.2, -0.2, 3.8, 2.2, 2.6, c.P)
		box(c, 0, 2.1, -1.53, 2.8, 0.5, 0.06, c.A, Mat.Neon)
		roof(c, 0, 3.4, -0.2, 4.8, 3.6, 1, c.S)
		box(c, 0, 4.3, -0.2, 2, 1.3, 1.6, c.P)
		gable(c, 0, 5.6, -0.2, 2.6, 2.2, 0.8, c.S)
		col(c, 0, 6.3, -0.2, 0.6, 0.2, c.S, Mat.Metal)
		ball(c, 0, 7.05, -0.2, 0.5, c.A, Mat.Neon)
		for _, sx in { -1, 1 } do
			box(c, sx * 2.9, 1.2, -0.8, 1.4, 1.5, 2, c.P)
			box(c, sx * 2.9, 1.8, -1.82, 0.7, 0.4, 0.06, c.A, Mat.Neon)
			gable(c, sx * 2.9, 2.7, -0.8, 1.7, 2.3, 0.6, c.S)
		end
		plant(c, -4.1, 0.3, -3.3, 1, 1.3, rgb(255, 170, 200))
		plant(c, 4.1, 0.3, -3.1, 1.1, 1.4, LEAF)
		ball(c, -3.6, 8.5, 1.4, 0.7, c.A, Mat.Neon, 0.3)
		ball(c, 3.9, 10, 0.6, 0.6, c.A, Mat.Neon, 0.3)
	end

	return B
end
