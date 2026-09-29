-- 유럽 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 풍차 마을(windmill) · 피사의 사탑(leaning) · 로도스 거상(statue) 은 원래 그 명소를 위해 만든 모양을 그대로 씀.

return function(K)
	local B = {}

	local V, rgb, Mat, PI, TAU = K.V, K.rgb, K.Mat, K.PI, K.TAU
	local ALONG_Z = K.ALONG_Z
	local GRASS, LEAF, WATER, DARK, TILE = K.GRASS, K.LEAF, K.WATER, K.DARK, K.TILE
	local ROCK, WOOD, SAND, BLACK, WHITE = K.ROCK, K.WOOD, K.SAND, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local gable, plant = K.gable, K.plant

	-- 정면(-Z)에서 삼각형이 보이는 박공(용마루가 Z 방향). 바닥 y, 폭 w(X), 깊이 d(Z), 높이 h
	local function frontGable(c, x, y, z, w, d, h, color, material)
		wedge(c, CFrame.new(x - w / 4, y + h / 2, z) * CFrame.Angles(0, PI / 2, 0), V(d, h, w / 2), color, material)
		wedge(c, CFrame.new(x + w / 4, y + h / 2, z) * CFrame.Angles(0, -PI / 2, 0), V(d, h, w / 2), color, material)
	end

	-- 박공(용마루가 X 방향, 삼각형이 옆에서 보임) + 재질
	local function ridge(c, x, y, z, w, d, h, color, material)
		wedge(c, CFrame.new(x, y + h / 2, z - d / 4), V(w, h, d / 2), color, material)
		wedge(c, CFrame.new(x, y + h / 2, z + d / 4) * CFrame.Angles(0, PI, 0), V(w, h, d / 2), color, material)
	end

	-- 세 점을 잇는 삼각형 판(직각 쐐기 두 개): 한 변(밑변)에 맞은편 꼭짓점에서 수선을 내려 둘로 나눔.
	--   쐐기의 경계 상자 = 밑변 x 높이 직사각형이므로, 그 상자가 설계 공간(바닥 위, 10x10 안)에 들어가는 밑변을 고름
	local function tri(c, a, b, d, color, material, thick)
		local t = thick or 0.15
		local function fits(p)
			local limit = 5 - t / 2
			return p.Y >= t / 2 and math.abs(p.X) <= limit and math.abs(p.Z) <= limit
		end
		local chosen, fallback, longest = nil, nil, -1
		for _, o in { { a, b, d }, { b, d, a }, { d, a, b } } do
			local apex, p, q = o[1], o[2], o[3]
			local edge = q - p
			local s = (apex - p):Dot(edge) / edge:Dot(edge)
			if s > 1e-3 and s < 1 - 1e-3 then
				local up = apex - (p + edge * s)
				if fits(p) and fits(q) and fits(p + up) and fits(q + up) then
					chosen = o
					break
				end
				if edge.Magnitude > longest then
					fallback, longest = o, edge.Magnitude
				end
			end
		end
		local o = chosen or fallback
		if not o then
			return
		end
		local apex, p, q = o[1], o[2], o[3]
		local edge = q - p
		local foot = p + edge * ((apex - p):Dot(edge) / edge:Dot(edge))
		local height = (apex - foot).Magnitude
		local up = (apex - foot).Unit
		for _, e in { p, q } do
			local back = (foot - e).Unit
			local center = (e + apex) / 2
			wedge(c, CFrame.lookAt(center, center - back, up), V(t, height, (foot - e).Magnitude), color, material)
		end
	end

	-- a 에서 b 까지 이어지는 판: 가로 w(진행 방향의 오른쪽), 두께 t. a → b 는 수직이 아니어야 함
	local function slab(c, a, b, w, t, color, material)
		local mid = (a + b) / 2
		return block(c, CFrame.lookAt(mid, b), V(w, t, (b - a).Magnitude), color, material)
	end

	-- a 에서 b 까지 이어지는 원기둥(지름 d)
	local function rod(c, a, b, d, color, material)
		local mid = (a + b) / 2
		return cyl(c, CFrame.lookAt(mid, b) * CFrame.Angles(0, PI / 2, 0), (b - a).Magnitude, d, color, material)
	end

	-- 쌓은 원기둥으로 만든 원뿔 지붕. 꼭대기 높이를 돌려줌
	local function cone(c, x, y, z, d, h, steps, color, material)
		local step = h / steps
		for k = 0, steps - 1 do
			col(c, x, y + k * step, z, step, d * (1 - k / steps), color, material)
		end
		return y + h
	end

	-- 쌓은 상자로 만든 사각뿔 지붕. 꼭대기 높이를 돌려줌
	local function spire(c, x, y, z, w, h, steps, color, material)
		local step = h / steps
		for k = 0, steps - 1 do
			local s = w * (1 - k / steps)
			box(c, x, y + k * step, z, s, step, s, color, material)
		end
		return y + h
	end

	-- 브란덴부르크 문: 도리스 기둥 6쌍(사이 벽 = 통로 5개) + 엔타블러처 + 계단식 아틱 + 초록 청동 4두 마차(콰드리가) + 양옆 초소
	B.brandenburg = function(c)
		local shade = mix(c.P, BLACK, 0.2)
		local bronze = c.A
		box(c, 0, 0, 0, 9.8, 0.2, 5.6, mix(c.S, WHITE, 0.5))
		box(c, 0, 0.2, 0, 8.4, 0.4, 3.6, c.S)
		for _, x in { -3.5, -2.1, -0.7, 0.7, 2.1, 3.5 } do
			box(c, x, 0.6, 0, 0.45, 4.4, 2.2, shade)
			for _, z in { -1.3, 1.3 } do
				col(c, x, 0.6, z, 4.4, 0.72, c.P)
			end
		end
		box(c, 0, 5, 0, 8.2, 0.6, 3.3, c.P)
		box(c, 0, 5.6, 0, 8.3, 0.45, 3.4, mix(c.P, c.S, 0.55))
		box(c, 0, 6.05, 0, 8.7, 0.3, 3.7, c.P)
		box(c, 0, 6.35, 0, 5.6, 1, 2.8, c.P)
		box(c, 0, 7.35, 0, 3, 0.4, 2.2, c.P)
		-- 콰드리가: 네 말(몸통 + 치켜든 목) + 전차 + 월계관 지팡이를 든 승리의 여신
		local y = 7.75
		box(c, 0, y, -0.2, 2.6, 0.6, 1, mix(bronze, BLACK, 0.25))
		for _, x in { -0.96, -0.32, 0.32, 0.96 } do
			box(c, x, y + 0.55, -0.2, 0.46, 0.6, 1.4, bronze)
			beam(c, V(x, y + 1, -0.75), V(x, y + 1.95, -1.2), 0.34, bronze)
		end
		box(c, 0, y, 0.65, 1.3, 0.95, 0.7, bronze)
		col(c, 0, y + 0.95, 0.65, 1.3, 0.42, bronze)
		ball(c, 0, y + 2.45, 0.65, 0.42, bronze)
		col(c, 0.45, y + 0.95, 0.55, 2.7, 0.12, bronze)
		cyl(c, CFrame.new(0.45, y + 3.75, 0.55) * ALONG_Z, 0.1, 0.55, bronze)
		-- 양옆 초소
		for _, s in { -1, 1 } do
			box(c, s * 4.55, 0.2, 0, 0.9, 3.2, 3, c.P)
			box(c, s * 4.55, 3.4, 0, 0.9, 0.3, 3.2, c.S)
		end
	end

	-- 트레비 분수: 궁전 정면(창문 줄 + 벽기둥) + 가운데 개선문(큰 기둥 4, 어두운 벽감 속 오케아노스) + 문장 아틱
	--   + 흰 바위 더미(스코글리에라) + 쏟아지는 물줄기 + 말 두 마리 + 넓은 반원 수반
	B.trevi = function(c)
		local stone = mix(c.P, ROCK, 0.4)
		local reef = mix(c.P, ROCK, 0.12)
		local niche = mix(c.P, BLACK, 0.5)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, ROCK, 0.55))
		col(c, 0, 0.2, 0.2, 0.3, 9.4, stone)
		col(c, 0, 0.5, 0.2, 0.6, 8.6, c.P)
		col(c, 0, 0.5, 0.2, 0.62, 8, c.S, Mat.Glass, 0.1)
		-- 궁전
		box(c, 0, 0.2, 3.7, 9.8, 7.6, 2.2, c.P)
		box(c, 0, 7.8, 3.7, 9.8, 0.35, 2.3, stone)
		box(c, 0, 8.15, 3.8, 9.4, 1, 2, c.P)
		for _, s in { -1, 1 } do
			for _, wy in { 3.2, 5.6 } do
				box(c, s * 3.45, wy, 2.58, 2.5, 1, 0.06, DARK)
			end
			for _, px in { 2.85, 4.05 } do
				box(c, s * px, 0.2, 2.52, 0.3, 7.6, 0.16, c.P)
			end
		end
		-- 가운데 개선문 + 벽감 + 오케아노스
		box(c, 0, 0.2, 2.3, 4, 9.6, 1.2, c.P)
		box(c, 0, 9.8, 2.5, 3, 1.3, 0.8, c.P)
		box(c, 0, 11.1, 2.5, 1.4, 0.9, 0.4, c.A, Mat.Metal)
		for _, s in { -1, 1 } do
			col(c, s * 0.9, 11.1, 2.5, 0.8, 0.3, c.P)
		end
		box(c, 0, 2.2, 1.66, 2, 4.6, 0.1, niche)
		cyl(c, CFrame.new(0, 6.8, 1.66) * ALONG_Z, 0.1, 2, niche)
		block(c, CFrame.new(0, 4.3, 1.45), V(1, 3, 0.55), WHITE)
		ball(c, 0, 6.15, 1.45, 0.75, WHITE)
		ball(c, 0, 2.7, 1.15, 1.5, WHITE)
		for _, x in { -1.75, -1.3, 1.3, 1.75 } do
			col(c, x, 2, 1.55, 7.6, 0.42, c.P)
		end
		-- 바위 더미
		local rocks = {
			{ -3.3, 1.8, 2.6, 1.8, 1.6, 0.3 },
			{ -1.4, 1.5, 2.4, 2.6, 1.6, -0.2 },
			{ 1.4, 1.5, 2.4, 2.6, 1.6, 0.25 },
			{ 3.3, 1.8, 2.6, 1.8, 1.6, -0.3 },
			{ 0, 1.2, 3.2, 1.8, 1.4, 0.1 },
		}
		for _, r in rocks do
			block(c, CFrame.new(r[1], 0.9 + r[4] / 3, r[2]) * CFrame.Angles(0.15, r[6], 0.1), V(r[3], r[4], r[5]), reef)
		end
		for _, x in { -2.4, 0, 2.4 } do
			box(c, x, 0.9, 0.95, 1.1, 1.5, 0.15, mix(c.S, WHITE, 0.55), Mat.Glass, 0.25)
		end
		-- 트리톤이 끄는 말(날뛰는 말 / 얌전한 말)
		for _, s in { -1, 1 } do
			block(c, CFrame.new(s * 2.2, 1.7, 0.6) * CFrame.Angles(0.35, 0, 0), V(0.55, 0.7, 1.4), WHITE)
			beam(c, V(s * 2.2, 1.9, 0.05), V(s * 2.25, 2.8, -0.35), 0.38, WHITE)
		end
	end

	-- 리알토 다리: 운하 + 양쪽 둑과 집 + 돌 아치 하나(아치 고리 + 경사 상판) + 가운데 박공 문루
	--   + 양쪽 경사를 따라 아케이드 상점 줄(어두운 아치 창 + 지붕) + 난간 + 곤돌라와 뱃사공 + 계류 말뚝
	B.venice = function(c)
		local bank = mix(c.P, ROCK, 0.45)
		local lead = mix(c.P, TILE, 0.55)
		local depth = 3.2
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		for _, s in { -1, 1 } do
			box(c, s * 4.3, 0, 0, 1.4, 1, 9.8, bank)
		end
		box(c, -4.2, 1, 3.4, 1.6, 3.4, 2.8, rgb(214, 132, 96))
		box(c, -4.2, 3, 1.98, 1.1, 0.8, 0.06, DARK)
		box(c, 4.2, 1, 3.2, 1.6, 2.8, 3.2, rgb(228, 186, 112))
		box(c, 4.2, 2.6, 1.58, 1.1, 0.8, 0.06, DARK)
		-- 아치 고리
		local span = 3.6
		local function intrados(x: number): number
			local u = x / span
			return 1 + 2 * (1 - u * u)
		end
		local segments = 6
		for k = 0, segments - 1 do
			local x1 = span * (2 * k / segments - 1)
			local x2 = span * (2 * (k + 1) / segments - 1)
			local p1, p2 = V(x1, intrados(x1) + 0.3, 0), V(x2, intrados(x2) + 0.3, 0)
			slab(c, p1 - (p2 - p1) * 0.08, p2 + (p2 - p1) * 0.08, depth, 0.6, c.P)
		end
		-- 경사 상판(윗면: 끝 2.1 → 가운데 3.9)
		local function deck(x: number): number
			return 3.9 - 1.8 * math.abs(x) / 4.9
		end
		local drop = 0.53
		for _, s in { -1, 1 } do
			local a, b = V(s * 4.7, deck(4.7) - drop, 0), V(s * -0.05, deck(0) - drop, 0)
			if s > 0 then
				a, b = b, a
			end
			slab(c, a, b, depth, 1, c.P)
			box(c, s * 4.3, 1, 0, 1.3, 1.1, depth, c.P)
		end
		-- 난간(앞뒤) + 상점 줄 + 지붕 + 아치 창
		for _, s in { -1, 1 } do
			local x1, x2 = if s < 0 then -4.6 else 0.9, if s < 0 then -0.9 else 4.6
			for _, z in { -depth / 2 + 0.1, depth / 2 - 0.1 } do
				slab(c, V(x1, deck(x1) + 0.25, z), V(x2, deck(x2) + 0.25, z), 0.18, 0.5, c.P)
			end
			local s1, s2 = if s < 0 then -4.1 else 0.95, if s < 0 then -0.95 else 4.1
			slab(c, V(s1, deck(s1) + 0.6, 0), V(s2, deck(s2) + 0.6, 0), 1.7, 1.2, c.P)
			slab(c, V(s1 - 0.1, deck(s1) + 1.3, 0), V(s2 + 0.1, deck(s2) + 1.3, 0), 2, 0.25, lead)
			for _, ax in { 1.7, 2.6, 3.5 } do
				local x = s * ax
				box(c, x, deck(x) + 0.2, -0.86, 0.42, 0.62, 0.06, c.A)
			end
		end
		-- 가운데 문루
		box(c, 0, 3.7, 0, 1.6, 1.7, 2.3, c.P)
		frontGable(c, 0, 5.4, 0, 1.9, 2.5, 0.7, c.P)
		box(c, 0, 3.9, 0, 0.7, 1.05, 2.36, c.A)
		-- 곤돌라 + 뱃사공
		local gx = 1.5
		box(c, gx, 0.3, -3.4, 0.5, 0.28, 2.6, c.A)
		beam(c, V(gx, 0.45, -4.6), V(gx, 1, -4.85), 0.2, c.A)
		beam(c, V(gx, 0.45, -2.2), V(gx, 0.85, -1.95), 0.2, c.A)
		col(c, gx, 0.58, -2.5, 0.9, 0.34, WHITE)
		ball(c, gx, 1.65, -2.5, 0.34, rgb(236, 200, 160))
		-- 계류 말뚝
		col(c, -3.2, 0.3, -1.6, 1.7, 0.2, rgb(40, 90, 200))
		col(c, -3.2, 0.3, -2.3, 1.4, 0.2, WHITE)
	end

	-- 페나 궁전: 숲이 덮인 언덕 + 붉은 수도원 동과 붉은 시계탑(노란 전망대 + 작은 돔)
	--   + 노란 궁전 동과 노란 원형 탑(푸른 돔) + 가운데 푸른 타일 아치문 + 톱니 모양 성가퀴 + 망루
	B.pena = function(c)
		local forest = mix(LEAF, BLACK, 0.1)
		col(c, 0, 0, 0, 1.4, 9.8, forest, Mat.Grass)
		col(c, 0.2, 1.4, 0.3, 1.4, 7.8, GRASS, Mat.Grass)
		block(c, CFrame.new(-2.6, 1.8, -2.4) * CFrame.Angles(0.2, 0.5, 0.1), V(2, 1.6, 1.8), ROCK)
		block(c, CFrame.new(3.2, 1.7, -2) * CFrame.Angles(-0.1, -0.4, 0.15), V(1.8, 1.5, 1.6), ROCK)
		for _, t in { { -3.8, -1.2, 1.8 }, { 3.9, 1.4, 1.7 }, { -3.2, 3, 1.9 }, { 0.8, -4, 1.6 }, { 2.4, 3.8, 1.8 } } do
			ball(c, t[1], 1.7, t[2], t[3], LEAF, Mat.Grass)
		end
		local top = 2.8
		-- 붉은 수도원 동 + 시계탑
		box(c, -1.9, top, 1, 3.6, 3, 3.2, c.S)
		for _, x in { -3.3, -2.1, -0.9 } do
			box(c, x, top + 3, -0.4, 0.5, 0.45, 0.4, c.S)
		end
		box(c, -2.8, top, -1.1, 1.5, 7.4, 1.5, c.S)
		box(c, -2.8, top + 7.4, -1.1, 1.9, 0.9, 1.9, c.P)
		ball(c, -2.8, top + 8.5, -1.1, 1.3, c.P)
		col(c, -2.8, top + 9.1, -1.1, 0.8, 0.15, c.A, Mat.Metal)
		cyl(c, CFrame.new(-2.8, top + 6.2, -1.87) * ALONG_Z, 0.1, 0.9, WHITE)
		-- 노란 궁전 동 + 원형 탑
		box(c, 1.9, top, 0.8, 3.4, 2.6, 3.4, c.P)
		for _, z in { -0.5, 0.8, 2.1 } do
			box(c, 3.4, top + 2.6, z, 0.4, 0.45, 0.5, c.P)
		end
		col(c, 2.6, top, -1.1, 5.2, 2.3, c.P)
		col(c, 2.6, top + 5.2, -1.1, 0.45, 2.6, mix(c.P, c.S, 0.3))
		ball(c, 2.6, top + 6.1, -1.1, 2.3, c.A)
		col(c, 2.6, top + 7.2, -1.1, 0.7, 0.2, c.A, Mat.Metal)
		ball(c, 2.6, top + 8, -1.1, 0.35, rgb(250, 215, 90), Mat.Metal)
		for _, wy in { top + 1.4, top + 3.4 } do
			box(c, 2.2, wy, -2.26, 0.4, 0.8, 0.06, DARK)
		end
		-- 가운데 푸른 타일 아치문
		box(c, 0, top, -1, 2.2, 2.2, 1.4, c.A)
		box(c, 0, top, -1.72, 0.8, 1.3, 0.06, DARK)
		box(c, 0, top + 2.2, -1, 2.4, 0.3, 1.6, WHITE)
		-- 망루(모서리의 작은 원기둥 + 돔)
		for _, t in { { 3.5, 2.4 }, { -3.6, 2.5 } } do
			col(c, t[1], top + 1.6, t[2], 2, 0.7, c.P)
			ball(c, t[1], top + 3.7, t[2], 0.8, c.A)
		end
		wedge(c, CFrame.new(0.4, 2.1, -3.7), V(1, 1.4, 1.6), mix(c.P, WHITE, 0.4))
	end

	-- 브란 성(드라큘라 성): 숲 + 바위 벼랑 위 흰 벽 성채(가파른 붉은 지붕) + 높은 사각 탑(뾰족 지붕)
	--   + 원형 탑(원뿔 지붕) + 보랏빛으로 빛나는 창 + 보라 달과 박쥐
	B.bran = function(c)
		local cliff = mix(ROCK, rgb(125, 105, 85), 0.35)
		local pine = mix(LEAF, BLACK, 0.3)
		col(c, 0, 0, 0, 0.3, 9.8, GRASS, Mat.Grass)
		block(c, CFrame.new(0.2, 1.8, 0.5) * CFrame.Angles(0, 0.3, 0), V(6.2, 3, 5.4), cliff, Mat.Slate)
		block(c, CFrame.new(-1.6, 1.25, -1.4) * CFrame.Angles(0, -0.4, 0.12), V(3.8, 1.8, 3), ROCK, Mat.Slate)
		block(c, CFrame.new(1.8, 2.6, 1.4) * CFrame.Angles(0.1, 0.2, -0.08), V(3.4, 2.6, 3.2), cliff, Mat.Slate)
		for _, t in { { -3.6, -2.6, 2 }, { 3.6, -2.4, 2.2 }, { -3.8, 2.4, 2.2 }, { 3.4, 3.4, 2 }, { 0.2, -3.9, 1.8 } } do
			ball(c, t[1], 0.3 + t[3] / 2, t[2], t[3], pine, Mat.Grass)
		end
		local y = 3.2
		box(c, 0.2, y, 0.8, 4.4, 3.2, 3.2, c.P)
		gable(c, 0.2, y + 3.2, 0.8, 4.6, 3.4, 1.9, c.S)
		box(c, 1.9, y, 1.9, 2.2, 4.6, 2.4, c.P)
		frontGable(c, 1.9, y + 4.6, 1.9, 2.4, 2.6, 1.6, c.S)
		-- 앞 성벽(문) + 높은 사각 탑
		box(c, 0.15, 3.2, -1.55, 1.9, 1.5, 0.35, c.P)
		box(c, 0.15, 3.2, -1.74, 0.6, 0.9, 0.06, DARK)
		box(c, -1.6, 2.2, -1.2, 1.8, 7.4, 1.8, c.P)
		spire(c, -1.6, 9.6, -1.2, 2.2, 3.6, 4, c.S)
		-- 원형 탑
		col(c, 1.9, 2.6, -1, 6, 1.9, c.P)
		cone(c, 1.9, 8.6, -1, 2.4, 2.6, 4, c.S)
		-- 빛나는 창
		for _, w in
			{
				{ -1.6, 7.6, -2.12 },
				{ -1.6, 5.6, -2.12 },
				{ 1.9, 6.6, -1.97 },
				{ -0.1, 4.4, -0.82 },
				{ 1.3, 4.4, -0.82 },
			}
		do
			box(c, w[1], w[2], w[3], 0.4, 0.6, 0.06, c.A, Mat.Neon)
		end
		-- 보라 달 + 박쥐
		ball(c, -3.3, 13.6, 3.3, 2.4, c.A, Mat.Neon, 0.25)
		local bat = V(2.9, 12.6, -1.6)
		ball(c, bat.X, bat.Y, bat.Z, 0.35, BLACK)
		for _, s in { -1, 1 } do
			block(
				c,
				CFrame.new(bat.X + s * 0.45, bat.Y + 0.1, bat.Z) * CFrame.Angles(0, 0, s * 0.35),
				V(0.7, 0.08, 0.35),
				BLACK
			)
		end
	end

	-- 피렌체 두오모: 흰 대리석 + 초록 띠의 신랑(붉은 지붕) + 정면(박공, 둥근 창, 초록 줄) + 팔각 기단과 반원 제단부
	--   + 팔각 드럼 + 붉은 벽돌 큰 돔과 흰 갈비 8줄 + 흰 등탑 + 앞 오른쪽의 조토 종탑
	B.duomo = function(c)
		local gold = rgb(240, 200, 90)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, ROCK, 0.45))
		-- 신랑
		box(c, 0, 0.2, -2.1, 3, 3.6, 4.6, c.P)
		frontGable(c, 0, 3.8, -2.1, 3.2, 4.6, 1, c.S)
		-- 정면
		box(c, 0, 0.2, -4.4, 3.8, 5.2, 0.3, c.P)
		frontGable(c, 0, 5.4, -4.4, 1.8, 0.3, 0.7, c.P)
		cyl(c, CFrame.new(0, 4.1, -4.58) * ALONG_Z, 0.1, 1, c.A)
		box(c, 0, 0.2, -4.58, 0.9, 1.6, 0.08, DARK)
		for _, s in { -1, 1 } do
			box(c, s * 1.25, 0.2, -4.58, 0.16, 5, 0.06, c.A)
		end
		-- 네모 기단 + 제단부 반구 3
		local cz = 2
		box(c, 0, 0.2, cz, 5.6, 3.2, 5.6, c.P)
		for _, p in { { -3, cz, 2.2 }, { 3, cz, 2.2 }, { 0, 3.9, 2 } } do
			ball(c, p[1], 3.4, p[2], p[3], c.S)
		end
		-- 팔각 드럼(띠 4개) + 돔 + 모서리의 흰 갈비 8줄
		local flat = 2.3
		for k = 0, 3 do
			block(
				c,
				CFrame.new(0, 4.6, cz) * CFrame.Angles(0, k * PI / 4, 0),
				V(flat * 2, 2.4, flat * 2 * math.tan(PI / 8)),
				c.P
			)
		end
		local domeY = 5.8
		ball(c, 0, domeY, cz, 4.8, c.S)
		local corner = flat / math.cos(PI / 8)
		local profile = { { corner, domeY }, { 1.9, domeY + 1.6 }, { 0.4, domeY + 2.85 } }
		for i = 0, 7 do
			local angle = (i + 0.5) * TAU / 8
			local dx, dz = math.cos(angle), math.sin(angle)
			for k = 1, 2 do
				local p, q = profile[k], profile[k + 1]
				beam(c, V(dx * p[1], p[2], cz + dz * p[1]), V(dx * q[1], q[2], cz + dz * q[1]), 0.3, c.P)
			end
		end
		col(c, 0, domeY + 2.6, cz, 1, 0.8, c.P)
		col(c, 0, domeY + 3.6, cz, 0.5, 0.45, c.P)
		ball(c, 0, domeY + 4.3, cz, 0.35, gold, Mat.Metal)
		-- 조토의 종탑(정면에서 볼 때 오른쪽)
		local bx, bz = -3.6, -3.2
		box(c, bx, 0.2, bz, 1.5, 9.8, 1.5, c.P)
		for _, by in { 3.4, 6.6 } do
			box(c, bx, by, bz, 1.56, 0.25, 1.56, c.A)
		end
		box(c, bx, 7.6, bz - 0.77, 0.5, 1.6, 0.06, DARK)
		box(c, bx, 10, bz, 1.8, 0.3, 1.8, c.P)
	end

	-- 성 바실리 대성당: 붉은 벽돌 기단 + 가운데 높은 천막 첨탑(금빛 양파) + 둘레의 큰 탑 4개와 작은 탑 4개,
	--   탑마다 색이 다른 양파 돔(초록·파랑·금·빨강흰 줄무늬)과 금 꼭지
	B.stbasil = function(c)
		local cream = rgb(240, 226, 200)
		local blue = rgb(60, 110, 205)
		local orange = rgb(235, 130, 50)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, rgb(150, 150, 155))
		box(c, 0, 0.2, 0, 7.8, 1.4, 7.8, c.P)
		box(c, 0, 1.6, 0, 8, 0.2, 8, cream)
		-- 가운데 천막 첨탑: 드럼 + 코코시닉 띠 + 초록·크림 번갈아 칠한 사각뿔 천막 + 금빛 양파
		col(c, 0, 1.8, 0, 5.2, 2.4, c.P)
		col(c, 0, 6.4, 0, 0.6, 2.7, cream)
		local apex = V(0, 12.9, 0)
		local base = { V(0, 7, -1.5), V(1.5, 7, 0), V(0, 7, 1.5), V(-1.5, 7, 0) }
		for k = 1, 4 do
			tri(c, apex, base[k], base[k % 4 + 1], if k % 2 == 0 then cream else c.S, c.M, 0.15)
		end
		ball(c, 0, 13.2, 0, 0.8, c.A, Mat.Metal)
		col(c, 0, 13.5, 0, 0.9, 0.14, c.A, Mat.Metal)
		-- 큰 탑 4: { x, z, 돔 색, 줄무늬 색(없으면 민무늬) }
		local big = {
			{ 0, -2.7, c.S, c.A },
			{ 2.7, 0, blue, nil },
			{ 0, 2.7, c.A, nil },
			{ -2.7, 0, c.P, nil },
		}
		for _, t in big do
			col(c, t[1], 1.8, t[2], 3.6, 1.4, c.P)
			ball(c, t[1], 6.2, t[2], 2, t[3])
			if t[4] then
				col(c, t[1], 6.05, t[2], 0.3, 2.04, t[4])
			end
			col(c, t[1], 7.1, t[2], 0.7, 0.45, t[3])
			ball(c, t[1], 8, t[2], 0.3, c.A, Mat.Metal)
		end
		-- 작은 탑 4
		local small = { { 2.3, -2.3, orange }, { 2.3, 2.3, c.S }, { -2.3, 2.3, blue }, { -2.3, -2.3, c.A } }
		for _, t in small do
			col(c, t[1], 1.8, t[2], 2.4, 1, c.P)
			ball(c, t[1], 4.8, t[2], 1.4, t[3])
			col(c, t[1], 5.4, t[2], 0.6, 0.3, t[3])
		end
	end

	-- 노트르담 대성당: 평평한 두 탑(긴 첨두 창 2개씩) + 세 개의 뾰족 아치 문 + 왕들의 회랑 + 푸른 장미창
	--   + 신랑과 가파른 슬레이트 지붕 + 익랑 + 제단부 + 교차부의 가느다란 첨탑 + 플라잉 버트레스
	B.notredame = function(c)
		local shade = mix(c.P, BLACK, 0.12)
		local fz = -3.8
		local face = fz - 0.84
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, ROCK, 0.4))
		box(c, 0, 0.2, fz, 7.2, 6.8, 1.6, c.P)
		for _, s in { -1, 1 } do
			local x = s * 2.35
			box(c, x, 7, fz, 2.5, 3.8, 1.6, c.P)
			box(c, x, 10.8, fz, 2.7, 0.25, 1.8, shade)
			for _, dx in { -0.55, 0.55 } do
				box(c, x + dx, 7.5, face, 0.5, 2.7, 0.08, DARK)
			end
			box(c, s * 1.1, 0.2, face, 0.26, 10.6, 0.12, shade)
		end
		-- 장미창
		cyl(c, CFrame.new(0, 4.8, face + 0.02) * ALONG_Z, 0.08, 2.4, DARK)
		cyl(c, CFrame.new(0, 4.8, face - 0.02) * ALONG_Z, 0.08, 2, c.A, Mat.Glass)
		-- 왕들의 회랑 + 윗 회랑
		box(c, 0, 2.9, face, 7.2, 0.45, 0.1, shade)
		box(c, 0, 6.3, face, 7.2, 0.35, 0.1, shade)
		-- 뾰족 아치 문 3
		for _, p in { { 0, 1.2, 1.7 }, { -2.35, 0.9, 1.4 }, { 2.35, 0.9, 1.4 } } do
			local x, w, h = p[1], p[2], p[3]
			box(c, x, 0.2, face, w, h, 0.08, DARK)
			block(
				c,
				CFrame.new(x, 0.2 + h, face) * CFrame.Angles(0, 0, PI / 4),
				V(w / math.sqrt(2), w / math.sqrt(2), 0.08),
				DARK
			)
		end
		-- 신랑 + 익랑 + 제단부
		box(c, 0, 0.2, 0.2, 3.2, 5.4, 6.4, c.P)
		frontGable(c, 0, 5.6, 0.2, 3.4, 6.4, 2.2, c.S)
		box(c, 0, 0.2, 1.2, 7, 5, 1.8, c.P)
		gable(c, 0, 5.2, 1.2, 7, 2, 1.6, c.S)
		col(c, 0, 0.2, 3.4, 5, 3, c.P)
		cone(c, 0, 5.2, 3.4, 3.2, 1.6, 2, c.S)
		-- 첨탑
		box(c, 0, 7.2, 1.2, 0.9, 1.4, 0.9, c.S)
		col(c, 0, 8.6, 1.2, 1.5, 0.6, c.S)
		col(c, 0, 10.1, 1.2, 1.8, 0.36, c.S)
		col(c, 0, 11.9, 1.2, 2, 0.16, c.S)
		-- 플라잉 버트레스
		for _, s in { -1, 1 } do
			for _, z in { -1.6, -0.2 } do
				box(c, s * 3.3, 0.2, z, 0.5, 3.6, 0.5, c.P)
				beam(c, V(s * 3.3, 3.6, z), V(s * 1.6, 5, z), 0.3, c.P)
			end
		end
	end

	-- 성 베드로 대성당: 타원 광장을 감싸는 베르니니 주랑(두 팔) + 가운데 오벨리스크
	--   + 큰 기둥이 늘어선 넓은 정면(아틱 + 성인상) + 높은 드럼 위 청회색 큰 돔(갈비) + 등탑 + 양옆 작은 돔
	B.stpeters = function(c)
		local paving = mix(c.P, WHITE, 0.3)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, ROCK, 0.35))
		col(c, 0, 0.2, -2.3, 0.04, 5.4, paving)
		-- 주랑(타원의 양쪽 호)
		local a, b, cz0 = 4.3, 2.5, -2.3
		local pieces = 4
		for _, s in { -1, 1 } do
			for k = 0, pieces - 1 do
				local t1 = math.rad(-60 + 120 * k / pieces)
				local t2 = math.rad(-60 + 120 * (k + 1) / pieces)
				local p1 = V(s * a * math.cos(t1), 0.9, cz0 + b * math.sin(t1))
				local p2 = V(s * a * math.cos(t2), 0.9, cz0 + b * math.sin(t2))
				block(c, CFrame.lookAt((p1 + p2) / 2, p2), V(0.7, 1.4, (p2 - p1).Magnitude + 0.15), c.P)
			end
		end
		box(c, 0, 0.2, cz0, 0.32, 2.9, 0.32, c.P)
		-- 정면
		box(c, 0, 0.2, 1, 7.2, 4.6, 1, c.P)
		box(c, 0, 3.7, 0.45, 7.4, 0.3, 0.2, mix(c.P, BLACK, 0.1))
		box(c, 0, 0.2, 0.47, 5.8, 1.5, 0.06, DARK)
		for _, x in { -3.1, -1.9, -0.65, 0.65, 1.9, 3.1 } do
			col(c, x, 0.2, 0.42, 3.5, 0.42, c.P)
		end
		frontGable(c, 0, 3.7, 0.4, 2.4, 0.3, 0.6, c.P)
		-- 본당 + 드럼 + 돔
		local dz = 2.7
		box(c, 0, 0.2, dz, 6.2, 5.4, 3.2, c.P)
		col(c, 0, 5.6, dz, 2.2, 4, c.P)
		col(c, 0, 6.1, dz, 1, 4.06, mix(c.P, BLACK, 0.3))
		col(c, 0, 7.8, dz, 0.25, 4.3, c.P)
		local domeY, r = 8.05, 2.1
		ball(c, 0, domeY, dz, r * 2, c.S)
		for i = 0, 7 do
			local angle = i * TAU / 8
			local dx, dzz = math.cos(angle), math.sin(angle)
			local function at(phi: number, rr: number): Vector3
				return V(dx * rr * math.cos(phi), domeY + rr * math.sin(phi), dz + dzz * rr * math.cos(phi))
			end
			beam(c, at(math.rad(15), r + 0.12), at(math.rad(50), r + 0.12), 0.22, c.P)
			beam(c, at(math.rad(50), r + 0.12), at(math.rad(84), r + 0.12), 0.22, c.P)
		end
		col(c, 0, domeY + 1.9, dz, 1.3, 0.8, c.P)
		ball(c, 0, domeY + 3.4, dz, 0.4, c.A, Mat.Metal)
	end

	-- 몽생미셸: 갯벌과 물길 + 둑길 + 섬을 두른 성벽과 둥근 망루 + 가파른 육각뿔 바위산(비탈의 마을 집들, 숲)
	--   + 꼭대기 수도원(북쪽의 높은 라 메르베유 벽, 성당, 종탑) + 가느다란 첨탑 끝의 금빛 미카엘 상
	B.montsaintmichel = function(c)
		local rock = mix(c.P, ROCK, 0.45)
		local wall = mix(c.P, WHITE, 0.1)
		local house = mix(c.P, WHITE, 0.35)
		local roofColor = c.S
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(SAND, c.S, 0.35), Mat.Sand)
		box(c, -2.6, 0.2, -3.6, 4.4, 0.04, 2.4, mix(WATER, c.S, 0.3), Mat.Glass, 0.2)
		box(c, 0.9, 0.2, -4.2, 0.9, 0.3, 1.6, wall)
		-- 성벽 + 망루 + 성문
		local ox, oz = 0.3, 0.5
		col(c, ox, 0.2, oz, 1.4, 8.4, wall)
		for _, deg in { 205, 245, 325 } do
			local t = math.rad(deg)
			col(c, ox + 4.1 * math.cos(t), 0.2, oz + 4.1 * math.sin(t), 2, 1.1, wall)
		end
		box(c, 0.9, 0.2, oz - 4.17, 0.6, 0.9, 0.1, DARK)
		-- 바위산: 성벽 위에서 수도원 아래까지 오르는 육각뿔(정면이 평평한 면)
		local apex = V(0.4, 8.2, 1)
		local ry = 1.6
		for k = 0, 5 do
			local a1, a2 = math.rad(60 * k), math.rad(60 * (k + 1))
			local p1 = V(ox + 3.7 * math.cos(a1), ry, oz + 3.7 * math.sin(a1))
			local p2 = V(ox + 3.7 * math.cos(a2), ry, oz + 3.7 * math.sin(a2))
			tri(c, apex, p1, p2, rock, Mat.Slate, 0.2)
		end
		-- 마을 집: { x, y, z, 가로, 높이, 세로 }
		local houses = {
			{ -1.5, 1.6, -2.3, 1.3, 1.2, 1.1 },
			{ 0.7, 1.6, -2.45, 1.2, 1, 1 },
			{ -0.5, 3, -1.7, 1.2, 1.1, 1 },
			{ 1.5, 3, -1.45, 1, 0.9, 1 },
			{ -2.4, 2.4, -0.4, 1, 1, 1.2 },
		}
		for _, h in houses do
			box(c, h[1], h[2], h[3], h[4], h[5], h[6], house)
			box(c, h[1], h[2] + h[5], h[3], h[4] + 0.12, 0.35, h[6] + 0.12, roofColor)
		end
		ball(c, 2.7, 2.5, 2.2, 1.5, LEAF, Mat.Grass)
		ball(c, -2, 3.2, 2.3, 1.3, LEAF, Mat.Grass)
		-- 수도원
		box(c, 0.6, 2.8, 2.8, 3.4, 4.4, 1.4, c.P)
		box(c, 0.4, 5.6, 1, 3.8, 1.8, 1.5, c.P)
		gable(c, 0.4, 7.4, 1, 3.8, 1.5, 0.9, roofColor)
		box(c, 0.9, 7.4, 1, 1, 1.6, 1, c.P)
		box(c, 0.9, 9, 1, 0.7, 0.9, 0.7, roofColor)
		col(c, 0.9, 9.9, 1, 1.7, 0.45, roofColor)
		col(c, 0.9, 11.6, 1, 2.2, 0.22, roofColor)
		col(c, 0.9, 13.8, 1, 1.2, 0.1, roofColor)
		ball(c, 0.9, 15.2, 1, 0.35, c.A, Mat.Neon)
	end

	-- 파르테논: 아크로폴리스 바위 언덕 + 3단 기단 + 정면 8기둥·옆면 기둥 줄 + 어두운 안쪽 벽
	--   + 아키트레이브와 트리글리프 띠 + 삼각 박공 지붕 + 올리브 나무
	B.parthenon = function(c)
		local rock = mix(c.S, ROCK, 0.5)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(GRASS, SAND, 0.55), Mat.Grass)
		box(c, 0, 0.2, 0, 9.4, 1.2, 9.6, rock, Mat.Rock)
		block(
			c,
			CFrame.new(-3.2, 1.05, -2.4) * CFrame.Angles(0.1, 0.35, -0.12),
			V(2.2, 1.3, 3.4),
			mix(rock, BLACK, 0.12),
			Mat.Rock
		)
		block(
			c,
			CFrame.new(3.15, 1, 2.2) * CFrame.Angles(-0.08, -0.4, 0.1),
			V(2.2, 1.2, 3.6),
			mix(rock, BLACK, 0.12),
			Mat.Rock
		)
		box(c, 0, 1.4, 0, 8.6, 0.4, 9.2, mix(c.S, WHITE, 0.2))
		box(c, 0, 1.8, 0, 5.6, 0.3, 8.8, c.S)
		box(c, 0, 2.1, 0, 5.2, 0.3, 8.4, c.P)
		local floor = 2.4
		local h = 3.2
		local hx, hz = 2.17, 3.95
		for k = 0, 7 do
			local x = -hx + k * (2 * hx / 7)
			col(c, x, floor, -hz, h, 0.46, c.P)
			col(c, x, floor, hz, h, 0.46, c.P)
		end
		for j = 1, 7 do
			local z = -hz + j * (2 * hz / 8)
			col(c, -hx, floor, z, h, 0.46, c.P)
			col(c, hx, floor, z, h, 0.46, c.P)
		end
		box(c, 0, floor, 0, 3.4, h, 6.4, mix(c.P, BLACK, 0.25))
		box(c, 0, floor + h, 0, 4.9, 0.45, 8.4, c.P)
		box(c, 0, floor + h + 0.45, 0, 4.9, 0.4, 8.4, mix(c.P, c.S, 0.6))
		frontGable(c, 0, floor + h + 0.85, 0, 5.1, 8.6, 1.1, c.P)
		plant(c, -4, 1.8, -4.2, 1, 1.3, mix(LEAF, ROCK, 0.3))
	end

	-- 마터호른: 초원 + 호수 + 샬레 + 전나무 + 삼각 면을 이어 만든 뾰족한 뿔 봉우리(어깨 능선, 살짝 굽은 정상)
	--   + 아래 비탈과 정상의 눈
	B.matterhorn = function(c)
		local rockLight = mix(c.P, rgb(170, 150, 125), 0.4)
		local rockDark = mix(c.P, BLACK, 0.3)
		local snow = c.S
		local fir = mix(LEAF, BLACK, 0.35)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, GRASS, Mat.Grass)
		-- 봉우리 밑의 빙하 받침(삼각 면의 경계 상자가 바닥 아래로 내려가지 않도록 뿔을 조금 띄움)
		local base = 0.95
		col(c, 0, 0.3, 0, base - 0.3, 9.3, mix(snow, ROCK, 0.15), Mat.Snow)
		local T1 = V(-0.9, 13.4, 0.4)
		local T2 = V(0.4, 12.7, 0.9)
		local Sh = V(-0.3, 7.4, -2.3)
		local S = V(0.2, base, -4.5)
		local W = V(-4.5, base, 0.5)
		local E = V(4.5, base, -0.3)
		local N = V(0.3, base, 4.5)
		local center = V(0, 5, 0.3)
		local function face(a, b, d, color)
			tri(c, a, b, d, color, c.M, 0.2)
		end
		face(T1, W, Sh, rockLight)
		face(Sh, W, S, rockLight)
		face(T1, Sh, T2, c.P)
		face(T2, Sh, E, rockDark)
		face(Sh, S, E, rockDark)
		face(T2, E, N, rockDark)
		face(T1, T2, N, c.P)
		face(T1, N, W, c.P)
		-- 눈: 면 위(바깥쪽으로 조금 띄움)의 작은 삼각형
		local function lerp(p, q, t)
			return p + (q - p) * t
		end
		local function snowPatch(a, b, d)
			local n = (b - a):Cross(d - a).Unit
			local mid = (a + b + d) / 3
			if n:Dot(mid - center) < 0 then
				n = -n
			end
			tri(c, a + n * 0.14, b + n * 0.14, d + n * 0.14, snow, Mat.Snow, 0.12)
		end
		snowPatch(W, S, lerp(Sh, (W + S) / 2, 0.55))
		snowPatch(S, E, lerp(Sh, (S + E) / 2, 0.5))
		snowPatch(T1, lerp(T1, W, 0.18), lerp(T1, Sh, 0.22))
		snowPatch(lerp(Sh, W, 0.15), lerp(Sh, T1, 0.25), lerp(W, T1, 0.45))
		snowPatch(lerp(T2, Sh, 0.3), lerp(T2, E, 0.35), lerp(Sh, E, 0.3))
		-- 호수 + 샬레 + 전나무
		col(c, -3.9, 0.3, -3.9, 0.05, 1.7, c.A, Mat.Glass, 0.1)
		box(c, 3.9, 0.3, -4, 1.1, 0.8, 0.9, WOOD, Mat.WoodPlanks)
		gable(c, 3.9, 1.1, -4, 1.3, 1.1, 0.6, rgb(150, 60, 50))
		for _, t in { { -4.4, -2.6 }, { -2.6, -4.4 }, { 4.4, -2.7 }, { 4.2, 4.2 }, { -4.2, 4.2 } } do
			col(c, t[1], 0.3, t[2], 0.9, 1, fir)
			col(c, t[1], 1.2, t[2], 0.9, 0.55, fir)
		end
	end

	-- 자이언츠 코즈웨이: 바다 + 뒤쪽 풀 덮인 절벽(오르간 기둥) + 절벽에서 바다로 계단처럼 내려가는
	--   벌집처럼 맞물린 육각 현무암 기둥들(직육면체 3개를 60도씩 돌려 겹친 육각기둥) + 끝의 물거품
	B.giantscauseway = function(c)
		local earth = mix(c.P, rgb(110, 88, 64), 0.5)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		box(c, 0, 0.3, 4.2, 9.8, 4, 1.4, earth)
		box(c, 0, 4.3, 4.2, 9.8, 0.3, 1.4, GRASS, Mat.Grass)
		wedge(c, CFrame.new(0, 1.6, 2.9), V(9.8, 2.6, 1.2), mix(earth, GRASS, 0.35), Mat.Grass)
		for k, x in { 2.9, 3.6, 4.3 } do
			col(c, x, 0.3, 3.2, 3.3 + (k % 2) * 0.5, 0.66, c.P)
		end
		-- 육각기둥: 꼭짓점이 ±X, 이웃 기둥은 Z 로 R√3, 옆 줄은 X 로 1.5R(반 칸 엇갈림)
		local R = 0.85
		local shades = { mix(c.P, WHITE, 0.1), mix(c.P, WHITE, 0.24), mix(c.P, rgb(120, 104, 88), 0.4) }
		local function hex(x: number, z: number, h: number, shade: number)
			for k = 0, 2 do
				local cf = CFrame.new(x, 0.3 + h / 2, z) * CFrame.Angles(0, k * PI / 3, 0)
				block(c, cf, V(R, h, R * math.sqrt(3)), shades[shade])
			end
		end
		local dz = R * math.sqrt(3)
		local dx = 1.5 * R
		local columns = {
			{ 0, 2.2, 2.9, 1 },
			{ 0, 2.2 - dz, 2.3, 2 },
			{ 0, 2.2 - 2 * dz, 1.7, 3 },
			{ 0, 2.2 - 3 * dz, 1.1, 1 },
			{ 0, 2.2 - 4 * dz, 0.55, 2 },
			{ -dx, 2.2 - dz / 2, 2.6, 3 },
			{ -dx, 2.2 - 1.5 * dz, 1.95, 1 },
			{ -dx, 2.2 - 2.5 * dz, 1.25, 2 },
			{ dx, 2.2 - dz / 2, 2.2, 2 },
			{ dx, 2.2 - 1.5 * dz, 1.55, 3 },
			{ dx, 2.2 - 2.5 * dz, 0.9, 1 },
			{ -2 * dx, 2.2, 2.3, 2 },
		}
		for _, p in columns do
			hex(p[1], p[2], p[3], p[4])
		end
		col(c, 0, 0.3, -3.6, 0.05, 2.8, c.A, Mat.SmoothPlastic, 0.3)
	end

	-- 네스호의 네시: 짙은 호수 + 건너편 둥근 언덕(풀·헤더) + 곶 위의 어쿼트 성 폐허(무너진 탑, 성벽)
	--   + S자로 목을 높이 든 네시(머리, 빛나는 눈) + 물 위로 솟은 등 혹 3개 + 꼬리 + 물결
	B.lochness = function(c)
		local stone = rgb(150, 140, 124)
		local heather = mix(GRASS, rgb(130, 90, 150), 0.4)
		local waterTop = 0.9
		box(c, 0, 0, 0, 9.8, waterTop, 9.8, c.S, Mat.Glass, 0.1)
		box(c, 0, waterTop, 4.3, 9.8, 0.3, 1.4, GRASS, Mat.Grass)
		-- 뒤쪽 산: 앞을 보는 삼각 면 두 개씩(꼭대기, 왼쪽 뒤, 앞, 오른쪽 뒤)
		for _, hill in { { -1.4, 2.7, 3.5, heather }, { 2.6, 2, 2.3, mix(GRASS, LEAF, 0.4) } } do
			local x, top, w, color = hill[1], hill[2], hill[3], hill[4]
			local apex = V(x, waterTop + top, 3.6)
			local left, right = V(x - w, waterTop + 0.3, 4.3), V(x + w, waterTop + 0.3, 4.3)
			local front = V(x + 0.2, waterTop + 0.3, 3)
			tri(c, apex, left, front, color, Mat.Grass, 0.2)
			tri(c, apex, front, right, color, Mat.Grass, 0.2)
		end
		ball(c, 1.4, waterTop + 0.5, 3, 1.1, LEAF, Mat.Grass)
		-- 어쿼트 성
		col(c, -3.2, waterTop, 1.2, 0.4, 3.2, GRASS, Mat.Grass)
		local g = waterTop + 0.4
		box(c, -3.6, g, 1.6, 1.4, 3.6, 1.4, stone)
		box(c, -4.1, g + 3.6, 1.1, 0.4, 0.5, 0.4, stone)
		box(c, -3.1, g + 3.6, 1.1, 0.4, 0.3, 0.4, stone)
		box(c, -3.6, g + 1.8, 0.88, 0.25, 0.7, 0.06, DARK)
		box(c, -2.4, g, 0.5, 1.8, 0.9, 0.35, stone)
		box(c, -1.8, g, 1.4, 0.35, 0.6, 1.6, stone)
		ball(c, -2.5, g + 0.4, 2.4, 1, LEAF, Mat.Grass)
		-- 네시
		local skin = c.P
		local n0 = V(0.3, waterTop - 0.1, -0.3)
		local n1 = V(-0.25, 2.9, -0.7)
		local n2 = V(0.05, 4.7, -1.1)
		local head = V(-0.55, 5.7, -1.55)
		rod(c, n0, n1, 1, skin)
		ball(c, n1.X, n1.Y, n1.Z, 1, skin)
		rod(c, n1, n2, 0.84, skin)
		ball(c, n2.X, n2.Y, n2.Z, 0.84, skin)
		rod(c, n2, head, 0.7, skin)
		ball(c, head.X, head.Y, head.Z, 1.15, skin)
		rod(c, head, head + V(-0.75, -0.2, -0.6), 0.66, skin)
		for _, e in { V(-0.3, 0.3, -0.45), V(-0.68, 0.3, 0.05) } do
			local p = head + e
			ball(c, p.X, p.Y, p.Z, 0.22, c.A, Mat.Neon)
		end
		ball(c, 1.5, 0.8, 0.4, 1.6, skin)
		ball(c, 2.8, 0.7, 0.9, 1.4, skin)
		ball(c, 3.9, 0.55, 1.4, 1.1, skin)
		rod(c, V(4.1, waterTop - 0.1, 1.6), V(4.55, 1.7, 2.1), 0.4, skin)
		-- 물결
		for _, r in { { 0.3, -0.3, 2 }, { 1.5, 0.4, 2.3 }, { 2.8, 0.9, 2 } } do
			col(c, r[1], waterTop, r[2], 0.04, r[3], c.A, Mat.SmoothPlastic, 0.45)
		end
	end

	-- 미노타우로스의 미궁: 어두운 바닥 + 겹겹의 사각 미로 벽(엇갈린 틈과 막다른 길)
	--   + 미노아식 입구(아래가 좁은 붉은 기둥, 검은 기둥머리, 금빛 성스러운 뿔) + 횃불
	--   + 가운데 단 위에서 양날 도끼(라브리스)를 든 황소 머리 미노타우로스
	B.labyrinth = function(c)
		local t = 0.35
		local floorColor = mix(c.P, BLACK, 0.45)
		local wallColor = c.P
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, floorColor)
		local function hwall(x1: number, x2: number, z: number, h: number)
			box(c, (x1 + x2) / 2, 0.2, z, x2 - x1 + t, h, t, wallColor)
		end
		local function vwall(x: number, z1: number, z2: number, h: number)
			box(c, x, 0.2, (z1 + z2) / 2, t, h, z2 - z1 + t, wallColor)
		end
		-- 바깥 고리(입구 = 앞 가운데)
		local o, m, i = 4.7, 3.6, 2.5
		hwall(-o, o, o, 1.6)
		vwall(-o, -o, o, 1.6)
		vwall(o, -o, o, 1.6)
		hwall(-o, -1, -o, 1.6)
		hwall(1, o, -o, 1.6)
		-- 둘째 고리(틈 = 뒤 왼쪽)
		hwall(-m, m, -m, 1.3)
		vwall(-m, -m, m, 1.3)
		vwall(m, -m, m, 1.3)
		hwall(-2.4, m, m, 1.3)
		-- 셋째 고리(틈 = 앞 오른쪽)
		hwall(-i, i, i, 1.3)
		vwall(-i, -i, i, 1.3)
		vwall(i, -i, i, 1.3)
		hwall(-i, 1.1, -i, 1.3)
		-- 막다른 길
		hwall(m, o, 0.5, 1.3)
		vwall(1, m, o, 1.3)
		vwall(-1, -m, -i, 1.3)
		-- 입구
		local gz = -4.6
		for _, s in { -1, 1 } do
			col(c, s * 0.95, 0.2, gz, 2.5, 0.5, c.S)
			col(c, s * 0.95, 2.7, gz, 0.35, 0.66, rgb(30, 26, 24))
		end
		box(c, 0, 3.05, gz, 2.8, 0.45, 0.7, c.P)
		box(c, 0, 3.05, gz - 0.36, 2.8, 0.2, 0.04, c.S)
		box(c, 0, 3.5, gz, 1.3, 0.3, 0.4, c.A, Mat.Metal)
		for _, s in { -1, 1 } do
			box(c, s * 0.5, 3.8, gz, 0.26, 0.7, 0.36, c.A, Mat.Metal)
		end
		for _, x in { -m, m } do
			ball(c, x, 1.75, -m, 0.4, c.A, Mat.Neon)
		end
		-- 가운데 단 + 미노타우로스
		col(c, 0, 0.2, 0, 0.4, 2.9, mix(c.P, WHITE, 0.25))
		local fur = rgb(92, 58, 44)
		local base = 0.6
		for _, s in { -1, 1 } do
			box(c, s * 0.33, base, 0, 0.45, 1.7, 0.55, fur)
		end
		box(c, 0, base + 1.4, 0, 1.2, 0.5, 0.7, c.S)
		box(c, 0, base + 1.9, 0, 1.7, 1.6, 0.85, fur)
		beam(c, V(-1.05, base + 3.2, 0), V(-1.25, base + 1.9, -0.35), 0.42, fur)
		beam(c, V(1.05, base + 3.2, 0), V(1.3, base + 2.3, -0.5), 0.42, fur)
		box(c, 0, base + 3.4, -0.05, 0.85, 0.95, 0.85, fur)
		box(c, 0, base + 3.45, -0.6, 0.62, 0.5, 0.4, mix(fur, WHITE, 0.25))
		for _, s in { -1, 1 } do
			beam(c, V(s * 0.35, base + 4.2, -0.05), V(s * 1.05, base + 4.95, -0.2), 0.2, rgb(240, 230, 205))
			ball(c, s * 0.22, base + 4.05, -0.49, 0.16, c.A, Mat.Neon)
		end
		-- 라브리스(양날 도끼)
		beam(c, V(1.35, base + 1.3, -0.55), V(1.35, base + 3.9, -0.55), 0.14, WOOD)
		block(c, CFrame.new(1.35, base + 3.55, -0.55) * CFrame.Angles(0, 0, PI / 4), V(0.7, 0.7, 0.08), c.A, Mat.Metal)
	end

	return B
end
