-- 유럽(2) 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 개선문(arch) · 빅벤(clocktower) · 에펠탑(lattice) · 콜로세움(ring) · 스톤헨지(stones) · 아틀란티스(island) · 세계수(tree)
-- 는 원래 그 명소를 위해 만든 모양을 그대로 씀.

return function(K)
	local B = {}

	local V, rgb, Mat, PI = K.V, K.rgb, K.Mat, K.PI
	local ALONG_Z, CORNERS = K.ALONG_Z, K.CORNERS
	local GRASS, LEAF, WATER, DARK, ROCK, WOOD, SAND, BLACK, WHITE =
		K.GRASS, K.LEAF, K.WATER, K.DARK, K.ROCK, K.WOOD, K.SAND, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local archCorner, gable, stepped = K.archCorner, K.gable, K.stepped

	-- 정면(-Z)에서 삼각형이 보이는 박공(용마루가 Z 방향). 바닥 y, 폭 w(X), 깊이 d(Z), 높이 h
	local function frontGable(c, x, y, z, w, d, h, color, material)
		wedge(c, CFrame.new(x - w / 4, y + h / 2, z) * CFrame.Angles(0, PI / 2, 0), V(d, h, w / 2), color, material)
		wedge(c, CFrame.new(x + w / 4, y + h / 2, z) * CFrame.Angles(0, -PI / 2, 0), V(d, h, w / 2), color, material)
	end

	-- 원뿔 지붕: 지름이 줄어드는 원기둥 steps 단. 꼭대기 높이를 돌려줌
	local function cone(c, x, y, z, d, h, steps, color, material)
		local stepH = h / steps
		for i = 0, steps - 1 do
			col(c, x, y + i * stepH, z, stepH, d * (1 - i / steps), color, material)
		end
		return y + h
	end

	-- 타워 브리지: 템스강 + 강 속 교각 위의 고딕 석탑 2개(네 귀퉁이 작은 탑 + 뾰족 지붕 + 고딕 창)
	--   + 탑 위쪽을 잇는 파란 윗 보도 2줄(흰 띠) + 반쯤 들어 올린 도개교 상판 2장 + 기슭으로 내려가는 파란 현수 사슬
	B.towerbridge = function(c)
		local slate = rgb(78, 84, 96)
		local deck = 2.2
		local pier, towerTop = 1, 7.6
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(WATER, rgb(70, 110, 120), 0.4), Mat.Glass, 0.1)
		for _, sx in { -1, 1 } do
			local x = sx * 2.6
			-- 기슭 교대 + 옆 경간 도로
			box(c, sx * 4.6, 0, 0, 0.8, deck, 3.2, c.P)
			box(c, sx * 3.9, deck - 0.35, 0, 1.2, 0.35, 2.2, c.S)
			-- 교각 + 탑신 + 고딕 창
			box(c, x, 0, 0, 2.5, pier, 3.2, mix(c.P, ROCK, 0.35))
			box(c, x, pier, 0, 1.8, towerTop - pier, 2.4, c.P)
			box(c, x, 3.4, -1.22, 0.55, 2.6, 0.06, DARK)
			-- 네 귀퉁이 작은 탑 + 뾰족 모자
			for _, s in CORNERS do
				local tx, tz = x + s[1] * 0.85, s[2] * 1.15
				col(c, tx, pier, tz, towerTop - pier + 0.8, 0.58, c.P)
				col(c, tx, towerTop + 0.8, tz, 1, 0.34, slate)
			end
			-- 가운데 뾰족 지붕
			stepped(c, x, 0, towerTop, 1.6, 2.4, 3, slate)
			-- 현수 사슬(탑 위쪽 → 기슭)
			for _, sz in { -1, 1 } do
				beam(c, V(sx * 3.5, 6.6, sz * 0.9), V(sx * 4.75, deck + 0.1, sz * 0.9), 0.26, c.S)
			end
			-- 도개교 상판(탑 안쪽 면을 축으로 들어 올림)
			local angle = math.rad(40)
			local L = 1.7
			local cf = CFrame.new(sx * (1.7 - math.cos(angle) * L / 2), deck - 0.17 + math.sin(angle) * L / 2, 0)
			block(c, cf * CFrame.Angles(0, 0, -sx * angle), V(L, 0.34, 2.2), c.S)
		end
		-- 윗 보도(앞뒤 2줄) + 흰 띠
		for _, sz in { -1, 1 } do
			box(c, 0, 5.8, sz * 0.8, 3.6, 1.1, 0.5, c.S)
			box(c, 0, 6.2, sz * 1.06, 3.6, 0.3, 0.04, mix(c.S, WHITE, 0.55))
		end
		-- 가운데 탑 꼭지(금)
		for _, sx in { -1, 1 } do
			col(c, sx * 2.6, towerTop + 2.4, 0, 0.8, 0.14, c.A, Mat.Metal)
		end
	end

	-- 프라하 천문시계: 구시청사 탑(짙은 돌, 난간 + 뾰족 지붕 + 네 귀퉁이 작은 탑) 앞면 아래에 튀어나온 시계 집
	--   + 파란 천문 시계판(금테, 아래쪽 검은 땅, 위로 치우친 황도 고리, 금 바늘) + 아래 달력판 + 사도 창 + 양옆 인형
	--   + 양옆의 박공 집들
	B.pragueclock = function(c)
		local light = mix(c.P, WHITE, 0.3)
		local roofC = mix(c.P, BLACK, 0.4)
		local tileRed = rgb(170, 72, 52)
		local gold = c.A
		local tx, tz = 0.6, 1.4
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, rgb(176, 166, 150), Mat.Cobblestone)
		-- 양옆 집(정면 박공)
		box(c, -3.4, 0.3, 1.4, 3, 5.4, 5, rgb(236, 214, 180))
		frontGable(c, -3.4, 5.7, 1.4, 3, 5, 1.8, tileRed)
		box(c, 3.9, 0.3, 1.8, 2, 4.6, 4.6, rgb(222, 190, 150))
		frontGable(c, 3.9, 4.9, 1.8, 2, 4.6, 1.4, tileRed)
		-- 탑
		box(c, tx, 0.3, tz, 3.4, 13.2, 3.4, c.P)
		box(c, tx, 9, tz, 3.6, 0.3, 3.6, light)
		box(c, tx, 10.2, tz - 1.72, 0.6, 1.8, 0.06, DARK)
		box(c, tx, 13.5, tz, 4, 0.5, 4, light)
		local top = stepped(c, tx, tz, 14, 2.8, 3.6, 3, roofC)
		col(c, tx, top, tz, 0.9, 0.14, gold, Mat.Metal)
		ball(c, tx, top + 1, tz, 0.35, gold, Mat.Metal)
		for _, s in CORNERS do
			local x, z = tx + s[1] * 1.75, tz + s[2] * 1.75
			col(c, x, 13.5, z, 1.8, 0.6, c.P)
			col(c, x, 15.3, z, 1.3, 0.3, roofC)
		end
		-- 시계 집(탑 앞면에 튀어나옴) + 경사 지붕
		local front = tz - 1.7 - 0.9
		box(c, tx, 0.3, front + 0.45, 3, 8.6, 0.9, light)
		wedge(c, CFrame.new(tx, 8.9 + 0.7, front + 0.45), V(3.2, 1.4, 0.9), roofC)
		-- 천문 시계판
		local ay = 5.7
		cyl(c, CFrame.new(tx, ay, front - 0.05) * ALONG_Z, 0.1, 2.7, gold, Mat.Metal)
		cyl(c, CFrame.new(tx, ay, front - 0.12) * ALONG_Z, 0.1, 2.3, c.S)
		cyl(c, CFrame.new(tx, ay - 0.55, front - 0.18) * ALONG_Z, 0.06, 1.1, DARK)
		cyl(c, CFrame.new(tx, ay + 0.25, front - 0.22) * ALONG_Z, 0.05, 1.5, gold, Mat.Metal)
		cyl(c, CFrame.new(tx, ay + 0.25, front - 0.26) * ALONG_Z, 0.05, 1.2, c.S)
		block(
			c,
			CFrame.new(tx, ay, front - 0.32) * CFrame.Angles(0, 0, -0.7) * CFrame.new(0, 0.55, 0),
			V(0.14, 1.1, 0.05),
			gold
		)
		ball(c, tx, ay, front - 0.32, 0.3, gold, Mat.Metal)
		-- 달력판
		cyl(c, CFrame.new(tx, 2.2, front - 0.05) * ALONG_Z, 0.1, 2.1, gold, Mat.Metal)
		cyl(c, CFrame.new(tx, 2.2, front - 0.12) * ALONG_Z, 0.1, 1.7, rgb(240, 232, 210))
		-- 사도 창 2개 + 양옆 인형(해골 등)
		for _, sx in { -1, 1 } do
			box(c, tx + sx * 0.55, 7.3, front - 0.02, 0.55, 0.8, 0.06, DARK)
			col(c, tx + sx * 1.8, 4.6, front + 0.2, 1.2, 0.4, light)
			ball(c, tx + sx * 1.8, 6, front + 0.2, 0.45, if sx < 0 then WHITE else gold)
		end
	end

	-- 산토리니(이아): 칼데라 바다 + 붉은 화산암 절벽(비탈 + 두 단 테라스) + 층층이 쌓인 흰 집들(파란 문, 몇 채는 황토색)
	--   + 파란 돔 교회 2채(흰 십자가) + 종탑 + 풍차
	B.santorini = function(c)
		local rock = rgb(168, 104, 80)
		local rockDark = rgb(122, 82, 70)
		local white = c.P
		local cream = rgb(245, 234, 214)
		local ochre = mix(c.A, WHITE, 0.3)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(WATER, c.S, 0.5), Mat.Glass, 0.1)
		-- 절벽
		wedge(c, CFrame.new(0, 0.3 + 1.6, -1.6), V(9.8, 3.2, 2.2), rockDark, Mat.Rock)
		box(c, 0, 0.3, 2.25, 9.8, 3.2, 5.5, rock, Mat.Rock)
		box(c, 0, 3.5, 3.3, 9.8, 2, 3.4, rock, Mat.Rock)
		box(c, 0, 2.3, -0.53, 9.8, 0.35, 0.06, rgb(222, 206, 188), Mat.Rock)
		-- 집: { x, y, z, 가로, 높이, 세로, 색, 파란 문 }
		local houses = {
			{ -4, 3.5, 0.5, 1.6, 1.5, 1.8, white, true },
			{ -2.4, 3.5, 0.2, 1.4, 1.1, 1.4, ochre, false },
			{ -0.9, 3.5, 0.7, 1.5, 1.7, 1.6, white, true },
			{ 4.1, 3.5, 0.6, 1.5, 1.5, 1.6, cream, false },
			{ -3.8, 5.5, 2.6, 1.8, 1.2, 1.8, white, false },
			{ -2.2, 5.5, 3.8, 1.5, 1.6, 1.8, ochre, false },
			{ 1.8, 5.5, 2.5, 1.6, 1, 1.6, white, true },
			{ 3.7, 5.5, 2.8, 1.8, 1.4, 1.8, white, false },
			{ 1, 5.5, 4.2, 2, 1.8, 1.4, cream, false },
			{ -3, 1.6, -1.1, 1.2, 1, 1.2, white, false },
			{ 3, 1.3, -1.3, 1, 0.9, 1.2, white, false },
			{ -4.2, 2.3, -0.8, 1.1, 1.2, 1, white, true },
			{ -1.4, 2.2, -0.9, 1.3, 1.3, 1, cream, false },
			{ 0.8, 2.5, -0.8, 1.2, 1, 1, white, false },
			{ 4.1, 2, -1, 1, 1.1, 1.2, ochre, false },
		}
		for _, h in houses do
			box(c, h[1], h[2], h[3], h[4], h[5], h[6], h[7])
			if h[8] then
				box(c, h[1], h[2], h[3] - h[6] / 2 - 0.02, 0.4, 0.7, 0.06, c.S)
			end
		end
		-- 파란 돔 교회 2채
		for _, ch in { { -0.6, 5.5, 2.4, 1.8 }, { 2.4, 3.5, 0.4, 1.6 } } do
			local x, y, z, w = ch[1], ch[2], ch[3], ch[4]
			box(c, x, y, z, w, w * 0.85, w, white)
			ball(c, x, y + w * 0.85, z, w, c.S)
			box(c, x, y + w * 0.85 + w * 0.45, z, 0.12, 0.55, 0.12, white)
		end
		-- 종탑(흰 벽 + 종 창 + 작은 파란 돔)
		box(c, 0.7, 5.5, 1.9, 0.8, 2.6, 0.8, white)
		box(c, 0.7, 7, 1.48, 0.4, 0.6, 0.06, DARK)
		ball(c, 0.7, 8.1, 1.9, 0.6, c.S)
		-- 풍차
		col(c, -4, 5.5, 4.2, 1.8, 1, white)
		ball(c, -4, 7.3, 4.2, 1, rgb(150, 120, 90))
		for _, a in { PI / 4, -PI / 4 } do
			block(c, CFrame.new(-4, 7.1, 3.6) * CFrame.Angles(0, 0, a), V(0.12, 2.2, 0.06), WOOD, Mat.Wood)
		end
	end

	-- 헝가리 국회의사당: 도나우강 + 강변 둑 + 낮고 길쭉한 흰 고딕 본관(앞면 전체 창 띠, 붉은 박공지붕)
	--   + 가운데 전각의 큰 붉은 돔(창 두른 드럼 + 알 모양 돔 + 등롱 + 가는 첨탑, 둘레 작은 첨탑) + 입구 양옆 뾰족탑
	--   + 날개 전각(가파른 지붕, 앞 귀퉁이 첨탑) + 양 끝 전각
	B.hungaryparliament = function(c)
		local stone = c.P
		local roofC = c.S
		local shade = mix(c.P, BLACK, 0.55)
		box(c, 0, 0, -3.75, 9.8, 0.25, 2.5, WATER, Mat.Glass, 0.1)
		box(c, 0, 0, 1.25, 9.8, 0.5, 7.5, mix(c.P, ROCK, 0.5))
		-- 본관 + 창 띠
		box(c, 0, 0.5, 1.1, 9.4, 2.4, 3.8, stone)
		gable(c, 0, 2.9, 1.1, 9.4, 3.8, 1.6, roofC)
		box(c, 0, 1.2, -1.07, 9.4, 1, 0.06, shade)
		-- 가운데 전각 + 돔
		box(c, 0, 0.5, 1, 3, 3.6, 4, stone)
		col(c, 0, 4.1, 1, 1.8, 3.4, stone)
		col(c, 0, 4.55, 1, 0.8, 3.46, shade)
		ball(c, 0, 5.9, 1, 3.4, roofC)
		ball(c, 0, 7, 1, 2.2, roofC)
		col(c, 0, 7.8, 1, 1, 0.8, stone)
		col(c, 0, 8.8, 1, 3.6, 0.3, roofC)
		ball(c, 0, 12.5, 1, 0.35, c.A, Mat.Neon)
		for _, s in CORNERS do
			col(c, s[1] * 1.35, 4.1, 1 + s[2] * 1.35, 2.6, 0.28, stone)
		end
		for _, sx in { -1, 1 } do
			-- 입구 양옆 뾰족탑
			box(c, sx * 1.75, 0.5, -1, 0.6, 5.2, 0.6, stone)
			cone(c, sx * 1.75, 5.7, -1, 0.85, 2.2, 3, roofC)
			-- 날개 가운데 전각(가파른 지붕 + 앞 귀퉁이 첨탑)
			local mx = sx * 3
			box(c, mx, 0.5, 1, 1.4, 3.2, 4, stone)
			frontGable(c, mx, 3.7, 1, 1.4, 4, 1.8, roofC)
			for _, dx in { -0.7, 0.7 } do
				col(c, mx + dx, 0.5, -1.15, 4.4, 0.28, stone)
			end
			-- 양 끝 전각
			box(c, sx * 4.4, 0.5, 1, 1, 3.4, 4, stone)
			frontGable(c, sx * 4.4, 3.9, 1, 1, 4, 1.4, roofC)
		end
	end

	-- 보르군 목조 교회: 풀밭 + 둘레 회랑 + 층층이 겹친 가파른 박공지붕 3단(정면에서 삼각형이 겹쳐 보임)
	--   + 용마루 위 작은 탑(십자 박공) + 뾰족 첨탑 + 박공 끝의 용머리 + 뒤쪽 둥근 앱스 탑 + 전나무
	B.stavechurch = function(c)
		local wall = c.S
		local roofC = c.P
		local cz = -0.3
		col(c, 0, 0, 0, 0.3, 9.8, GRASS, Mat.Grass)
		-- 회랑 + 층층 지붕
		box(c, 0, 0.3, cz, 5.8, 1.2, 7.6, wall)
		box(c, 0, 0.3, cz - 3.82, 0.9, 1.1, 0.06, DARK)
		frontGable(c, 0, 1.5, cz, 6.6, 8.2, 1.3, roofC)
		box(c, 0, 1.5, cz, 4, 2.2, 6.4, wall)
		frontGable(c, 0, 3.4, cz, 5, 6.8, 1.2, roofC)
		box(c, 0, 3.4, cz, 2.8, 2.4, 5.6, wall)
		frontGable(c, 0, 5.8, cz, 3.6, 6, 2.6, roofC)
		-- 용마루 위 탑 + 십자 박공 + 첨탑
		box(c, 0, 7.4, cz, 1.3, 2, 1.3, wall)
		frontGable(c, 0, 9.4, cz, 1.9, 1.9, 0.9, roofC)
		gable(c, 0, 9.4, cz, 1.9, 1.9, 0.9, roofC)
		box(c, 0, 9.8, cz, 0.9, 0.8, 0.9, wall)
		frontGable(c, 0, 10.6, cz, 1.1, 1.1, 3, roofC)
		gable(c, 0, 10.6, cz, 1.1, 1.1, 3, roofC)
		-- 용머리(박공 끝에서 위·바깥으로)
		for _, sz in { -1, 1 } do
			beam(c, V(0, 8.2, cz + sz * 2.8), V(0, 9.2, cz + sz * 3.7), 0.24, c.A)
			beam(c, V(0, 10.1, cz + sz * 0.9), V(0, 10.7, cz + sz * 1.5), 0.18, c.A)
		end
		-- 뒤쪽 둥근 앱스 탑
		col(c, 0, 0.3, 4.1, 3.4, 1.6, wall)
		cone(c, 0, 3.7, 4.1, 1.8, 2.4, 3, roofC)
		-- 전나무
		for _, t in { { -3.9, -2.6 }, { 3.8, 1.8 } } do
			col(c, t[1], 0.3, t[2], 0.5, 0.35, WOOD, Mat.Wood)
			cone(c, t[1], 0.8, t[2], 1.9, 3.6, 4, mix(LEAF, BLACK, 0.2), Mat.Grass)
		end
	end

	-- 알함브라: 초록 사비카 언덕 + 평지 위 붉은 성벽(성가퀴) + 벨라 탑 + 코마레스 탑(창) + 흰 아케이드와 도금양 안뜰 연못
	--   + 사이프러스 + 뒤쪽 눈 덮인 시에라네바다 산
	B.alhambra = function(c)
		local wall = c.P
		local shade = mix(c.P, BLACK, 0.25)
		local stucco = rgb(236, 222, 196)
		local green = c.A
		local mountain = rgb(104, 114, 140)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(green, LEAF, 0.4), Mat.Grass)
		-- 눈 덮인 산(뒤)
		for _, m in { { -1.8, 4.2, 6.2, 7.5 }, { 2.6, 4.25, 4.8, 5.6 } } do
			local x, z, w, h = m[1], m[2], m[3], m[4]
			frontGable(c, x, 0.3, z, w, 1.4, h, mountain, Mat.Rock)
			frontGable(c, x, 0.3 + h * 0.58, z - 0.08, w * 0.42, 1.4, h * 0.42, WHITE, Mat.Snow)
		end
		-- 언덕 위 평지 + 성벽
		box(c, 0.2, 0.3, 0.1, 9.2, 1.2, 6.8, mix(c.S, SAND, 0.35))
		wedge(c, CFrame.new(0.2, 0.9, -3.9), V(9.2, 1.2, 1.2), mix(green, LEAF, 0.3), Mat.Grass)
		local y = 1.5
		box(c, 0.2, y, -3, 9, 1.6, 0.5, wall)
		box(c, -4.1, y, 0.2, 0.5, 1.4, 6.2, wall)
		box(c, 4.5, y, 0.2, 0.5, 1.4, 6.2, wall)
		box(c, 0.2, y, 3.2, 9, 1.2, 0.4, wall)
		for k = 0, 3 do
			box(c, -1.8 + k * 1.3, y + 1.6, -3, 0.45, 0.35, 0.5, wall)
		end
		box(c, -0.8, y, -3.27, 0.8, 1.1, 0.06, DARK)
		-- 벨라 탑(왼쪽 앞) + 종
		box(c, -3.5, y, -2.5, 1.8, 3.8, 1.8, wall)
		box(c, -3.5, y + 3.8, -2.5, 2, 0.35, 2, shade)
		box(c, -3.5, y + 4.15, -2.5, 0.6, 0.7, 0.6, stucco)
		-- 오른쪽 앞 탑
		box(c, 3.9, y, -2.4, 1.3, 3, 1.3, wall)
		box(c, 3.9, y + 3, -2.4, 1.5, 0.3, 1.5, shade)
		-- 코마레스 탑 + 창
		box(c, 1.8, y, 1.9, 2.4, 5.4, 2.4, wall)
		box(c, 1.8, y + 5.4, 1.9, 2.6, 0.3, 2.6, shade)
		for _, sx in { -1, 1 } do
			box(c, 1.8 + sx * 0.6, 4.6, 0.68, 0.35, 0.9, 0.06, DARK)
		end
		-- 아케이드 + 도금양 안뜰(연못과 산울타리)
		box(c, 1.8, y, 0.35, 2.8, 1.8, 0.6, stucco)
		for k = -1, 1 do
			box(c, 1.8 + k * 0.85, y, 0.03, 0.55, 1.2, 0.06, DARK)
		end
		box(c, 1.8, y, -1.3, 1.1, 0.06, 2.4, WATER, Mat.Glass, 0.1)
		for _, sx in { -1, 1 } do
			box(c, 1.8 + sx * 0.95, y, -1.3, 0.4, 0.45, 2.4, green, Mat.Grass)
		end
		-- 사이프러스 + 언덕 숲
		for _, t in { { -2.4, -1.9 }, { -2.4, 0.3 }, { -1.1, 2.4 } } do
			col(c, t[1], y, t[2], 1.9, 0.5, mix(LEAF, BLACK, 0.3), Mat.Grass)
		end
		for _, t in { { -4.2, -4.3, 1.1 }, { 1.4, -4.3, 1.2 }, { 4.2, -4.2, 1 } } do
			ball(c, t[1], 0.55 + t[3] * 0.35, t[2], t[3], mix(green, LEAF, 0.5), Mat.Grass)
		end
	end

	-- 노이슈반슈타인 성: 숲 + 바위 벼랑 위 흰 성. 높은 본관(창 띠 + 파란 박공지붕) + 가장 높은 가는 원탑(원뿔 지붕)
	--   + 작은 원탑 + 네모 탑 + 앞쪽 성문 건물(연분홍, 양옆 원뿔 지붕 작은 탑)
	B.neuschwanstein = function(c)
		local white = c.P
		local roofC = c.S
		local gateColor = mix(c.P, rgb(214, 150, 118), 0.55)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(GRASS, LEAF, 0.5), Mat.Grass)
		-- 바위 벼랑 + 숲
		box(c, 0.4, 0.3, 0.6, 8.2, 1.4, 7.2, ROCK, Mat.Slate)
		box(c, 0.6, 1.7, 0.8, 7.4, 1, 6.2, mix(ROCK, WHITE, 0.1), Mat.Slate)
		for _, t in { { -4.1, -3.9, 1.4 }, { -4, 2.9, 1.6 }, { 4.1, -4, 1.4 }, { 2.2, -4.2, 1.2 } } do
			ball(c, t[1], t[3] / 2 + 0.2, t[2], t[3], LEAF, Mat.Grass)
		end
		local y = 2.7
		-- 본관(팔라스)
		box(c, 1.3, y, 1.9, 5, 7, 2.4, white)
		for _, wy in { 5.2, 7.4 } do
			for k = -1, 1 do
				box(c, 1.3 + k * 1.5, wy, 0.68, 0.7, 1, 0.06, DARK)
			end
		end
		gable(c, 1.3, 9.7, 1.9, 5, 2.4, 2.4, roofC)
		-- 가장 높은 원탑
		col(c, -1.4, y, 0.5, 11.2, 1.4, white)
		col(c, -1.4, 13.9, 0.5, 0.35, 1.8, white)
		local top = cone(c, -1.4, 14.25, 0.5, 1.7, 3.6, 4, roofC)
		col(c, -1.4, top, 0.5, 1, 0.14, c.A, Mat.Metal)
		-- 작은 원탑(본관 오른쪽 끝)
		col(c, 4, y, 1, 8.6, 1, white)
		cone(c, 4, 11.3, 1, 1.2, 2.2, 3, roofC)
		-- 네모 탑(왼쪽 뒤)
		box(c, -2.9, y, 2.1, 1.6, 6, 1.6, white)
		stepped(c, -2.9, 2.1, 8.7, 1.8, 1.8, 2, roofC)
		-- 성문 건물 + 양옆 작은 탑
		box(c, 0.2, y, -1.5, 5, 3.2, 1.4, gateColor)
		gable(c, 0.2, 5.9, -1.5, 5, 1.4, 1.1, roofC)
		box(c, 0.2, y, -2.23, 0.9, 1.4, 0.06, DARK)
		for _, sx in { -1, 1 } do
			local x = 0.2 + sx * 2.5
			col(c, x, y, -2, 4.4, 0.9, gateColor)
			cone(c, x, 7.1, -2, 1.1, 1.8, 3, roofC)
		end
	end

	-- 세고비아 수도교: 광장 + 가늘고 높은 화강암 교각 위 2층 아치(아래층 높은 아치 5개, 위층 낮은 아치 5개) + 꼭대기 물길
	B.segovia = function(c)
		local stone = c.P
		local dark = mix(c.P, BLACK, 0.25)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.S, SAND, 0.4), Mat.Cobblestone)
		local pierW, depth = 0.78, 1.5
		local spacing = 1.76
		local lowTop, beamH = 8.2, 0.7
		local upBase = lowTop + beamH
		local upTop = upBase + 2.4
		for k = 0, 5 do
			local x = -4.4 + k * spacing
			box(c, x, 0.3, 0, pierW, lowTop - 0.3, depth, stone)
			box(c, x, upBase, 0, pierW * 0.9, upTop - upBase, depth * 0.85, stone)
		end
		box(c, 0, lowTop, 0, 9.6, beamH, depth, stone)
		box(c, 0, upTop, 0, 9.6, 0.7, depth * 0.85, stone)
		box(c, 0, upTop + 0.7, 0, 9.6, 0.3, depth * 0.7, dark)
		for k = 0, 4 do
			local xl = -4.4 + k * spacing
			local xr = xl + spacing
			archCorner(c, xl + pierW / 2, lowTop, 0, 0.32, depth, stone, -1)
			archCorner(c, xr - pierW / 2, lowTop, 0, 0.32, depth, stone, 1)
			archCorner(c, xl + pierW * 0.45, upTop, 0, 0.3, depth * 0.85, stone, -1)
			archCorner(c, xr - pierW * 0.45, upTop, 0, 0.3, depth * 0.85, stone, 1)
		end
		-- 뒤쪽 구시가 집(붉은 기와)
		local tile = rgb(176, 84, 56)
		for _, h in { { -3, 3.4, 2.6, 2.2, 2.2, rgb(226, 200, 160) }, { 3.2, 3.5, 2.4, 2.8, 2, rgb(214, 186, 150) } } do
			box(c, h[1], 0.3, h[2], h[3], h[4], h[5], h[6])
			gable(c, h[1], 0.3 + h[4], h[2], h[3] + 0.2, h[5] + 0.2, 0.9, tile)
		end
	end

	-- 메테오라: 초록 골짜기 + 둥글게 솟은 바위 기둥들(위로 조금씩 좁아짐) + 꼭대기 끝까지 지은 수도원(붉은 지붕, 돔, 종탑)
	B.meteora = function(c)
		local rock = c.P
		local rockDark = mix(c.P, BLACK, 0.18)
		local wallC = rgb(226, 214, 190)
		local roofC = c.S
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.A, LEAF, 0.4), Mat.Grass)
		-- 바위 기둥: 원기둥 몸통 + 비틀어 붙인 모난 덩어리(세로 골) + 불룩한 밑동
		local function pillar(x, z, h, d, twist)
			col(c, x, 0.3, z, h, d, rock, Mat.Rock)
			local cf = CFrame.new(x + d * 0.1, 0.3 + h * 0.46, z - d * 0.08) * CFrame.Angles(0, twist, 0.03)
			block(c, cf, V(d * 0.78, h * 0.92, d * 0.92), rockDark, Mat.Rock)
			ball(c, x - d * 0.12, 0.3 + d * 0.5, z + d * 0.05, d, rockDark, Mat.Rock)
			return 0.3 + h
		end
		-- 가장 큰 기둥 + 큰 수도원
		local top = pillar(0.6, 1.4, 10, 3.8, 0.3)
		box(c, 0.2, top, 1.8, 2.4, 1.3, 1.6, wallC)
		gable(c, 0.2, top + 1.3, 1.8, 2.6, 1.8, 0.8, roofC)
		box(c, 1.4, top, 0.7, 1.3, 1, 1.2, wallC)
		ball(c, 1.4, top + 1, 0.7, 0.9, roofC)
		box(c, -0.7, top, 0.6, 0.6, 2, 0.6, wallC)
		box(c, -0.7, top + 2, 0.6, 0.8, 0.3, 0.8, roofC)
		-- 왼쪽 기둥 + 수도원(꼭대기를 다 덮음)
		top = pillar(-2.9, -0.8, 7, 2.8, -0.4)
		box(c, -2.9, top, -0.8, 2.3, 1.2, 2, wallC)
		gable(c, -2.9, top + 1.2, -0.8, 2.5, 2.2, 0.8, roofC)
		-- 오른쪽 낮은 기둥 + 작은 예배당
		top = pillar(3.2, -2.2, 5.2, 2.2, 0.5)
		box(c, 3.2, top, -2.2, 1.2, 0.9, 1.2, wallC)
		gable(c, 3.2, top + 0.9, -2.2, 1.4, 1.4, 0.6, roofC)
		-- 뒤쪽 빈 기둥들(꼭대기 풀)
		for _, p in { { -2.6, 3.2, 8.5, 2.6, 0.7 }, { 3.3, 3.3, 6.5, 2.1, -0.2 } } do
			top = pillar(p[1], p[2], p[3], p[4], p[5])
			ball(c, p[1], top, p[2], p[4] * 0.95, rock, Mat.Rock)
		end
		-- 골짜기 나무
		for _, t in { { -4.2, -3.8 }, { -1, -3.6 }, { 1.4, -4.2 }, { 4.3, 0.8 }, { -4.4, 1.6 } } do
			ball(c, t[1], 0.8, t[2], 1.1, mix(c.A, LEAF, 0.6), Mat.Grass)
		end
	end

	-- 폼페이: 화산재 땅 + 뒤쪽 베수비오 화산(층층 원뿔 + 빛나는 분화구 + 용암 줄기 + 우산 소나무 모양 연기)
	--   + 앞쪽 포룸 유적(바닥 + 부서진 기둥 줄 + 유피테르 신전 기단과 기둥) + 지붕 없는 집 벽
	B.pompeii = function(c)
		local ruin = c.P
		local ruinDark = mix(c.P, BLACK, 0.2)
		local ash = c.S
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.P, ROCK, 0.45), Mat.Ground)
		-- 베수비오
		local vx, vz = 0.8, 2.3
		local y = 0.3
		local diameters = { 5.4, 4.8, 4.2, 3.6, 3, 2.5, 2.1 }
		for i, d in diameters do
			local t = (i - 1) / (#diameters - 1)
			col(c, vx, y, vz, 0.95, d, mix(mix(ash, GRASS, 0.3), mix(ash, BLACK, 0.15), t), Mat.Rock)
			y += 0.95
		end
		col(c, vx, y - 0.05, vz, 0.1, 1.5, c.A, Mat.Neon)
		beam(c, V(vx - 0.4, y - 0.1, vz - 0.8), V(vx - 1.3, 1.4, vz - 2.5), 0.3, c.A, Mat.Neon)
		beam(c, V(vx + 0.5, y - 0.1, vz - 0.7), V(vx + 1.9, 1.8, vz - 1.6), 0.25, c.A, Mat.Neon)
		local smoke = rgb(120, 112, 108)
		ball(c, vx, y + 1.1, vz, 1.6, smoke, Mat.SmoothPlastic, 0.15)
		ball(c, vx - 0.3, y + 2.5, vz + 0.2, 2.2, smoke, Mat.SmoothPlastic, 0.15)
		ball(c, vx + 0.2, y + 4.2, vz + 0.1, 3, mix(smoke, WHITE, 0.2), Mat.SmoothPlastic, 0.15)
		-- 포룸 바닥
		box(c, -0.6, 0.3, -2.6, 7.4, 0.12, 4, mix(ruin, WHITE, 0.2))
		-- 유피테르 신전(기단 + 계단 + 앞 기둥 4개, 일부 부러짐)
		box(c, 0.6, 0.3, -1.3, 2.6, 1, 2, ruin)
		wedge(c, CFrame.new(0.6, 0.8, -2.6), V(1.4, 1, 0.6), ruin)
		for k, h in { 2.2, 1.4, 2.2, 0.9 } do
			col(c, 0.6 + (k - 2.5) * 0.7, 1.3, -2, h, 0.38, ruin)
		end
		-- 포룸 양옆 부서진 기둥 줄
		for k, h in { 1.8, 1.8, 1, 1.8 } do
			col(c, -3.6, 0.42, -4.2 + (k - 1) * 1, h, 0.42, ruin)
		end
		box(c, -3.6, 2.22, -3.7, 0.5, 0.3, 1.5, ruin)
		for k, h in { 1.6, 0.8, 1.6 } do
			col(c, 3.6, 0.42, -4.2 + (k - 1) * 1.2, h, 0.42, ruin)
		end
		-- 지붕 없는 집 벽
		box(c, -3, 0.3, 1, 2.6, 1.3, 0.25, ruinDark)
		box(c, -4.2, 0.3, 2, 0.25, 1.3, 2.2, ruinDark)
		box(c, -2.2, 0.3, 2.4, 0.25, 0.9, 1.6, ruinDark)
		box(c, -3.2, 0.3, 3.4, 2, 1.1, 0.25, ruinDark)
		box(c, 4.4, 0.3, 1.5, 0.25, 1.2, 3, ruinDark)
		box(c, 4, 0.3, 3.9, 1, 0.9, 0.25, ruinDark)
	end

	-- 올림피아 제우스 상: 신전 대리석 바닥 + 올리브기름 연못 + 흑단 받침(금 띠) 위 옥좌에 앉은 상아·황금 거상
	--   (금 옷자락 두른 다리와 무릎, 드러난 상아 가슴, 금 머리칼·수염, 올리브 관) + 오른손의 승리의 여신 니케
	--   + 왼손에 쥔 독수리 홀 + 양옆 신전 기둥과 들보
	B.zeus = function(c)
		local ivory = c.P
		local gold = c.S
		local ebony = rgb(48, 36, 32)
		local marble = rgb(232, 228, 220)
		box(c, 0, 0, 0, 9.8, 0.4, 9.8, marble, Mat.Marble)
		box(c, 0, 0.4, -3.3, 4.6, 0.1, 2.2, c.A, Mat.Glass, 0.2)
		-- 받침 + 발판 + 옥좌
		box(c, 0, 0.4, 1.2, 5.4, 1.4, 4.6, ebony)
		box(c, 0, 1.5, 1.2, 5.5, 0.2, 4.7, gold, Mat.Metal)
		box(c, 0, 1.8, -0.7, 2.6, 0.4, 1, gold, Mat.Metal)
		box(c, 0, 1.8, 1.9, 3.8, 2.5, 2.8, ebony)
		box(c, 0, 1.8, 3.6, 4, 10, 0.6, ebony)
		box(c, 0, 11.6, 3.6, 4.2, 0.3, 0.7, gold, Mat.Metal)
		for _, sx in { -1, 1 } do
			ball(c, sx * 1.8, 12.2, 3.6, 0.6, gold, Mat.Metal)
			box(c, sx * 2.1, 4.3, 1.9, 0.5, 1.4, 2.6, gold, Mat.Metal)
		end
		-- 앉은 몸: 다리(금 옷자락) + 발 + 무릎 + 상아 가슴 + 어깨에 두른 옷자락
		for _, sx in { -1, 1 } do
			box(c, sx * 0.6, 2.2, -0.4, 0.9, 2.4, 0.9, gold)
			box(c, sx * 0.6, 2.2, -0.95, 0.6, 0.35, 0.5, ivory)
		end
		box(c, 0, 4.3, 1.1, 2.4, 1.1, 3.1, gold)
		box(c, 0, 5.2, 2.4, 2.2, 3.4, 1.5, ivory)
		beam(c, V(-1, 8.4, 1.6), V(0.9, 5.4, 1.6), 0.55, gold)
		-- 머리: 상아 얼굴 + 금 머리칼 + 금 수염 + 올리브 관
		ball(c, 0, 9.5, 2.3, 1.7, ivory)
		ball(c, 0, 9.75, 2.75, 1.7, gold)
		ball(c, 0, 8.75, 1.85, 1.05, gold)
		col(c, 0, 9.95, 2.4, 0.25, 1.6, rgb(110, 150, 70))
		-- 오른팔(앞으로 내밀어 니케를 받침) + 니케
		beam(c, V(1.3, 8.3, 2.4), V(1.5, 6.4, 1.6), 0.6, ivory)
		beam(c, V(1.5, 6.4, 1.6), V(1.6, 6.6, -0.2), 0.55, ivory)
		col(c, 1.6, 6.8, -0.3, 1.1, 0.45, gold, Mat.Metal)
		ball(c, 1.6, 8.1, -0.3, 0.42, gold, Mat.Metal)
		for _, sx in { -1, 1 } do
			block(
				c,
				CFrame.new(1.6 + sx * 0.32, 7.8, -0.05) * CFrame.Angles(0, 0, sx * 0.55),
				V(0.12, 0.95, 0.45),
				WHITE
			)
		end
		-- 왼팔(들어 올려 홀을 쥠) + 독수리 홀
		beam(c, V(-1.3, 8.3, 2.4), V(-2.1, 7.2, 1.6), 0.6, ivory)
		beam(c, V(-2.1, 7.2, 1.6), V(-2.3, 9, 1.2), 0.5, ivory)
		col(c, -2.35, 1.8, 1.2, 11.2, 0.22, gold, Mat.Metal)
		ball(c, -2.35, 13.2, 1.2, 0.55, gold, Mat.Metal)
		for _, sx in { -1, 1 } do
			beam(c, V(-2.35, 13.2, 1.2), V(-2.35 + sx * 0.75, 13.6, 1.2), 0.18, gold, Mat.Metal)
		end
		-- 신전 기둥 + 들보
		for _, sx in { -1, 1 } do
			for _, z in { 0.2, 4 } do
				col(c, sx * 4.3, 0.4, z, 13, 0.8, marble, Mat.Marble)
			end
			box(c, sx * 4.3, 13.4, 2.1, 0.9, 0.6, 5.2, marble, Mat.Marble)
		end
	end

	return B
end
