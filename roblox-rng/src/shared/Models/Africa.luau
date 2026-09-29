-- 아프리카 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 희망봉 등대(lighthouse) · 스핑크스(sphinx) · 기자 피라미드(pyramid) · 알렉산드리아 등대(lighthouse 불가사의판)는
-- 원래 그 명소를 위해 만든 모양을 그대로 씀. 사하라 신기루 성은 나무 섬(skyisland) 대신 떠 있는 성채 전용 모형.
-- 좌우 주의: 정면(-Z 쪽)에서 바라보면 +X 가 왼쪽, -X 가 오른쪽.

return function(K)
	local B = {}

	local V, rgb, Mat, PI, TAU = K.V, K.rgb, K.Mat, K.PI, K.TAU
	local ALONG_Z, CORNERS = K.ALONG_Z, K.CORNERS
	local GRASS, LEAF, WATER, DARK = K.GRASS, K.LEAF, K.WATER, K.DARK
	local ROCK, WOOD, SAND, BLACK, WHITE = K.ROCK, K.WOOD, K.SAND, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local plant = K.plant

	-- 공용 도우미 -----------------------------------------------------------------

	-- a 에서 b 까지 이어지는 판: 가로 w(진행 방향의 오른쪽), 두께 t. a → b 는 수직이 아니어야 함
	local function slab(c, a, b, w, t, color, material, transparency)
		local mid = (a + b) / 2
		return block(c, CFrame.lookAt(mid, b), V(w, t, (b - a).Magnitude), color, material, transparency)
	end

	-- 정면(-Z)에서 삼각형이 보이는 박공(용마루가 Z 방향). 바닥 y, 폭 w(X), 깊이 d(Z), 높이 h
	local function frontGable(c, x, y, z, w, d, h, color, material)
		wedge(c, CFrame.new(x - w / 4, y + h / 2, z) * CFrame.Angles(0, PI / 2, 0), V(d, h, w / 2), color, material)
		wedge(c, CFrame.new(x + w / 4, y + h / 2, z) * CFrame.Angles(0, -PI / 2, 0), V(d, h, w / 2), color, material)
	end

	-- 칼날 봉우리: 용마루(길이 w)가 yaw 만큼 돈 박공. 밑변 d, 높이 h, 바닥 y
	local function blade(c, x, y, z, w, d, h, yaw, color, material)
		local base = CFrame.new(x, y + h / 2, z) * CFrame.Angles(0, yaw, 0)
		wedge(c, base * CFrame.new(0, 0, -d / 4), V(w, h, d / 2), color, material)
		wedge(c, base * CFrame.new(0, 0, d / 4) * CFrame.Angles(0, PI, 0), V(w, h, d / 2), color, material)
	end

	-- 세 점을 잇는 삼각형 판(직각 쐐기 두 개, 한 꼭짓점에서 내린 수선으로 나눔).
	--   쐐기 경계 상자가 설계 공간(바닥 위, 10x10 안)에 드는 나눔을 고르고, 없으면 가장 긴 변의 가운데에서 둘로 쪼갬
	local function tri(c, a, b, d, color, material, thick, depth)
		local t = thick or 0.2
		local function fits(p)
			local limit = 5 - t / 2
			return p.Y >= t / 2 and math.abs(p.X) <= limit and math.abs(p.Z) <= limit
		end
		local chosen
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
			end
		end
		if not chosen then
			if (depth or 0) >= 3 then
				return
			end
			-- 가장 긴 변을 반으로 나눠 두 삼각형으로
			local best, pts = -1, nil
			for _, o in { { a, b, d }, { b, d, a }, { d, a, b } } do
				local len = (o[2] - o[1]).Magnitude
				if len > best then
					best, pts = len, o
				end
			end
			local m = (pts[1] + pts[2]) / 2
			tri(c, pts[1], m, pts[3], color, material, t, (depth or 0) + 1)
			tri(c, m, pts[2], pts[3], color, material, t, (depth or 0) + 1)
			return
		end
		local apex, p, q = chosen[1], chosen[2], chosen[3]
		local edge = q - p
		local foot = p + edge * ((apex - p):Dot(edge) / edge:Dot(edge))
		local height = (apex - foot).Magnitude
		local up = (apex - foot).Unit
		for _, e in { p, q } do
			local len = (foot - e).Magnitude
			if len > 0.02 then
				local center = (e + apex) / 2
				wedge(c, CFrame.lookAt(center, center - (foot - e).Unit, up), V(t, height, len), color, material)
			end
		end
	end

	-- 원뿔 비탈을 판 n 장으로 덮음: 반지름 r1(높이 y1) → r2(높이 y2). colorOf(i) 로 판마다 색
	local function slopeRing(c, center, n, r1, y1, r2, y2, w, colorOf, material, turn)
		for i = 0, n - 1 do
			local a = (i + (turn or 0)) / n * TAU
			local dir = V(math.sin(a), 0, -math.cos(a))
			local p1 = center + V(0, y1, 0) + dir * r1
			local p2 = center + V(0, y2, 0) + dir * r2
			local normal = V(0, r1 - r2, 0) + dir * (y2 - y1)
			local mid = (p1 + p2) / 2 - normal.Unit * 0.2
			block(c, CFrame.lookAt(mid, mid + (p2 - p1)), V(w, 0.4, (p2 - p1).Magnitude + 0.15), colorOf(i), material)
		end
	end

	-- 우산 모양 아카시아: 기운 줄기 + 납작한 잎 판 두 장
	local function acacia(c, x, y, z, h, d, leaf, lean)
		local top = V(x + (lean or 0.3), y + h, z)
		beam(c, V(x, y, z), top, 0.26, WOOD, Mat.Wood)
		col(c, top.X, top.Y, top.Z, 0.35, d, leaf, Mat.Grass)
		col(c, top.X - d * 0.12, top.Y + 0.3, top.Z + d * 0.08, 0.3, d * 0.62, mix(leaf, BLACK, 0.12), Mat.Grass)
	end

	-- 야자수: 기운 줄기 + 늘어진 잎 네 장
	local function palm(c, x, y, z, h, leaf, turn)
		local top = V(x + 0.25, y + h, z + 0.1)
		beam(c, V(x, y, z), top, 0.24, WOOD, Mat.Wood)
		for k = 0, 3 do
			local a = (turn or 0) + k * PI / 2
			local tip = top + V(math.cos(a) * 1.05, -0.45, math.sin(a) * 1.05)
			slab(c, top + V(0, 0.08, 0), tip, 0.42, 0.08, leaf, Mat.Grass)
		end
	end

	-- 기린: 다리(앞뒤 판) + 몸통 + 긴 목 + 머리. yaw = 바라보는 방향(0 이면 -Z)
	local function giraffe(c, x, y, z, yaw, s)
		local coat = rgb(222, 168, 82)
		local cf = CFrame.new(x, y, z) * CFrame.Angles(0, yaw, 0)
		block(c, cf * CFrame.new(0, 0.8 * s, -0.42 * s), V(0.5 * s, 1.6 * s, 0.18 * s), coat)
		block(c, cf * CFrame.new(0, 0.8 * s, 0.42 * s), V(0.5 * s, 1.6 * s, 0.18 * s), coat)
		block(c, cf * CFrame.new(0, 1.85 * s, 0.05 * s) * CFrame.Angles(0.2, 0, 0), V(0.6 * s, 0.6 * s, 1.35 * s), coat)
		local neckFoot = cf * V(0, 2 * s, -0.5 * s)
		local head = cf * V(0, 3.9 * s, -1 * s)
		beam(c, neckFoot, head, 0.28 * s, coat)
		block(
			c,
			CFrame.new(head) * CFrame.Angles(0, yaw, 0) * CFrame.new(0, 0, -0.18 * s),
			V(0.3 * s, 0.32 * s, 0.62 * s),
			mix(coat, WOOD, 0.3)
		)
	end

	-- 코끼리: 다리(앞뒤 판) + 몸통 + 머리 + 귀 + 코
	local function elephant(c, x, y, z, yaw, s)
		local grey = rgb(128, 122, 118)
		local cf = CFrame.new(x, y, z) * CFrame.Angles(0, yaw, 0)
		block(c, cf * CFrame.new(0, 0.4 * s, -0.55 * s), V(0.95 * s, 0.8 * s, 0.4 * s), grey)
		block(c, cf * CFrame.new(0, 0.4 * s, 0.6 * s), V(0.95 * s, 0.8 * s, 0.4 * s), grey)
		block(c, cf * CFrame.new(0, 1.3 * s, 0.05 * s), V(1.15 * s, 1.1 * s, 1.9 * s), grey)
		block(c, cf * CFrame.new(0, 1.55 * s, -1.05 * s), V(0.8 * s, 0.85 * s, 0.6 * s), grey)
		block(c, cf * CFrame.new(0, 1.5 * s, -0.95 * s), V(1.7 * s, 0.95 * s, 0.12 * s), mix(grey, BLACK, 0.1))
		beam(c, cf * V(0, 1.3 * s, -1.35 * s), cf * V(0, 0.15 * s, -1.55 * s), 0.26 * s, grey)
	end

	-- 명소 -------------------------------------------------------------------

	-- 볼더스 비치: 청록 바다 + 흰 모래 후미 + 둥근 화강암 바위들 + 뒤뚱거리는 아프리카펭귄 무리(검은 몸, 흰 배, 검은 머리)
	B.boulders = function(c)
		local wet = mix(c.P, BLACK, 0.18)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, c.A, Mat.Glass, 0.1)
		box(c, -0.9, 0.2, 1.3, 8, 0.2, 7.2, SAND, Mat.Sand)
		box(c, -0.9, 0.2, -2.45, 8, 0.1, 0.4, mix(c.A, WHITE, 0.65), Mat.SmoothPlastic)
		box(c, 3.25, 0.2, 1.3, 0.4, 0.1, 7.2, mix(c.A, WHITE, 0.65), Mat.SmoothPlastic)
		-- 바위: { x, z, 지름 } (앞 가운데는 비워 펭귄이 보이게)
		for k, r in
			{
				{ -3.5, 3.5, 2.8 },
				{ -1, 3.9, 2 },
				{ 1.5, 3.9, 1.9 },
				{ 3.6, 2.8, 2.6 },
				{ -3.9, 0.1, 2 },
				{ 3.95, -0.9, 1.8 },
				{ -3.9, -3.7, 1.6 },
				{ 3.5, -3.9, 1.4 },
			}
		do
			ball(c, r[1], r[3] / 2, r[2], r[3], if k % 3 == 0 then wet else c.P)
		end
		-- 펭귄: 검은 몸통 + 앞으로 불룩한 흰 배 + 검은 머리 + 흰 뺨
		local function penguin(x, z, yaw)
			local y = 0.4
			local dir = V(-math.sin(yaw), 0, -math.cos(yaw))
			col(c, x, y, z, 1.6, 1.05, c.S, Mat.SmoothPlastic)
			local belly = V(x, y + 0.72, z) + dir * 0.24
			ball(c, belly.X, belly.Y, belly.Z, 0.92, WHITE, Mat.SmoothPlastic)
			ball(c, x, y + 1.9, z, 0.78, c.S, Mat.SmoothPlastic)
			local cheek = V(x, y + 1.84, z) + dir * 0.24
			ball(c, cheek.X, cheek.Y, cheek.Z, 0.4, WHITE, Mat.SmoothPlastic)
		end
		for _, p in
			{
				{ -1.9, 1.3, 0.3 },
				{ -0.2, 1.9, -0.2 },
				{ 1.5, 1, 0.5 },
				{ -1.1, -0.6, 0 },
				{ 0.7, -1.1, -0.4 },
				{ 2.1, -2.2, 0.9 },
			}
		do
			penguin(p[1], p[2], p[3])
		end
	end

	-- 셰프샤우엔: 뒤로 올라가는 비탈(푸른 벽 계단식 단) 위의 파랗게 칠한 네모 집들(흰 지붕 테두리, 주황 화분·문)
	--   + 가운데 파란 계단 골목 + 흙빛 카스바 탑 + 뒤쪽 리프 산맥 봉우리
	B.chefchaouen = function(c)
		local light, deep = mix(c.P, WHITE, 0.45), mix(c.P, rgb(30, 60, 160), 0.35)
		local wall = mix(c.P, WHITE, 0.7)
		local mountain = mix(LEAF, ROCK, 0.55)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, wall)
		box(c, 0, 0.3, 1.9, 9.8, 1, 6.2, wall)
		box(c, 0, 1.3, 3.3, 9.8, 1.1, 3.4, wall)
		frontGable(c, -2.2, 2.4, 4.4, 5.4, 1.1, 6.4, mountain, Mat.Rock)
		frontGable(c, 2.6, 2.4, 4.5, 4.6, 0.9, 5, mix(mountain, BLACK, 0.15), Mat.Rock)
		-- 집: { x, 바닥, z, 가로, 높이, 세로, 색, 문 x 치우침 }
		for k, h in
			{
				{ -3.1, 0.3, -3.3, 3.4, 2.2, 2.6, c.P, 0.6 },
				{ 3, 0.3, -3.4, 3.6, 1.8, 2.4, light, -0.8 },
				{ -3, 1.3, -0.1, 3.6, 2.4, 2, deep, 0.9 },
				{ 3.1, 1.3, 0, 3.4, 2.8, 2.2, c.P, -0.7 },
				{ -2.6, 2.4, 2.7, 4.2, 2.6, 2.2, light, 0.8 },
				{ 2.4, 2.4, 2.9, 3.6, 2, 2.4, deep, -0.4 },
			}
		do
			local x, y, z, w, hh, d = h[1], h[2], h[3], h[4], h[5], h[6]
			box(c, x, y, z, w, hh, d, h[7])
			box(c, x, y + hh, z, w + 0.1, 0.2, d + 0.1, c.S)
			box(c, x + h[8], y, z - d / 2 - 0.04, 0.6, 1.1, 0.1, if k % 2 == 0 then c.A else mix(c.P, BLACK, 0.45))
		end
		-- 창문과 벽에 건 주황 화분
		box(c, -2.4, 1.3, -4.64, 0.5, 0.5, 0.1, DARK)
		box(c, 3.9, 3, -1.14, 0.5, 0.5, 0.1, DARK)
		for _, p in
			{ { -3.6, 1.5, -4.66 }, { 2.2, 1.3, -4.66 }, { -2, 2.9, -1.16 }, { 2.3, 3.3, -1.16 }, { -3.8, 3.9, 1.54 } }
		do
			box(c, p[1], p[2], p[3], 0.32, 0.3, 0.16, c.A)
		end
		-- 가운데 파란 계단 골목
		wedge(c, CFrame.new(0, 0.8, -1.9), V(2, 1, 1.4), c.P)
		wedge(c, CFrame.new(0, 1.85, 0.9), V(2, 1.1, 1.4), c.P)
		-- 카스바 탑
		local ochre = rgb(196, 138, 92)
		box(c, -4.15, 2.4, 4.2, 1.2, 5, 1.2, ochre)
		box(c, -4.15, 7.4, 4.2, 1.4, 0.3, 1.4, mix(ochre, BLACK, 0.2))
		box(c, -4.15, 7.7, 4.2, 0.7, 0.6, 0.7, ochre)
	end

	-- 테이블 마운틴: 앞바다 + 해안 도시 + 꼭대기가 평평한 거대한 사암 절벽(골짜기 줄, 초록 비탈)
	--   + 꼭대기를 덮고 흘러내리는 "식탁보" 구름 + 왼쪽 데블스 피크, 오른쪽 라이언스 헤드 + 케이블카
	B.tablemountain = function(c)
		local cliff = mix(c.P, BLACK, 0.12)
		local gully = mix(c.P, BLACK, 0.35)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, WATER, Mat.Glass, 0.1)
		box(c, 0, 0.2, 1.2, 9.8, 0.2, 7.4, mix(c.S, SAND, 0.45), Mat.Grass)
		-- 도시: { x, z, 가로, 높이, 세로 }
		for k, b in
			{
				{ 3.9, -2, 0.9, 0.9, 1 },
				{ 2.8, -2.1, 0.8, 1.5, 0.9 },
				{ 1.7, -1.9, 1, 0.7, 1 },
				{ 0.5, -2.1, 0.7, 2, 0.7 },
				{ -0.6, -1.9, 1, 1.1, 1 },
				{ -1.8, -2.1, 0.8, 1.6, 0.8 },
			}
		do
			local color = if k % 3 == 0 then rgb(150, 190, 220) elseif k % 3 == 1 then WHITE else rgb(236, 226, 205)
			box(c, b[1], 0.4, b[2], b[3], b[4], b[5], color, if k % 3 == 0 then Mat.Glass else Mat.SmoothPlastic)
		end
		col(c, -3.6, 0.4, -2.1, 0.5, 1.6, WHITE, Mat.SmoothPlastic)
		-- 산 덩어리 + 앞·옆 비탈 + 골짜기
		box(c, 0, 0.4, 2.7, 7, 5.8, 4.2, c.P)
		wedge(c, CFrame.new(0, 1.9, -0.3), V(7, 3, 1.8), c.S, Mat.Grass)
		for _, x in { 2.2, 0.2, -1.5 } do
			box(c, x, 2.4, 0.56, 0.3, 3.6, 0.1, gully)
		end
		-- 식탁보 구름
		box(c, 0, 6.2, 2.7, 7.3, 0.55, 4.5, c.A, Mat.SmoothPlastic, 0.05)
		for _, d in { { 2.8, 1.4 }, { 1.1, 0.8 }, { -0.7, 1.6 }, { -2.6, 1 } } do
			box(c, d[1], 6.2 - d[2], 0.4, 1.3, d[2] + 0.1, 0.3, c.A, Mat.SmoothPlastic, 0.2)
		end
		-- 데블스 피크(정면에서 왼쪽 = +X, 뾰족) + 라이언스 헤드(오른쪽 = -X, 초록 비탈 위 바위 머리)
		frontGable(c, 4.15, 0.4, 2.6, 1.6, 3.8, 5.6, cliff)
		frontGable(c, -4.1, 0.4, 1.4, 1.7, 3.2, 2.8, c.S, Mat.Grass)
		frontGable(c, -4.1, 0.4, 1.5, 1.3, 1.6, 4.6, cliff)
		-- 케이블카
		box(c, -2.4, 0.4, -0.9, 0.6, 1.3, 0.5, WHITE)
		beam(c, V(-2.4, 1.7, -0.9), V(-2.4, 6.75, 0.8), 0.06, DARK)
		box(c, -2.4, 3.9, -0.3, 0.4, 0.4, 0.4, rgb(210, 50, 50))
	end

	-- 바오밥 거리: 붉은 흙길 양옆으로 늘어선 키 큰 바오밥(곧고 굵은 줄기 + 꼭대기에만 짧은 가지와 납작한 잎)
	--   + 풀밭 + 길 끝에 지는 주황 해 + 제부 소달구지
	B.baobab = function(c)
		local soil = mix(c.P, rgb(190, 90, 50), 0.45)
		local road = mix(soil, SAND, 0.45)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, soil, Mat.Sand)
		box(c, 0, 0.25, 0, 2, 0.05, 9.8, road, Mat.Sand)
		box(c, -3.5, 0.25, -0.5, 2.6, 0.06, 8, mix(c.S, SAND, 0.3), Mat.Grass)
		box(c, 3.5, 0.25, 0.5, 2.6, 0.06, 8, mix(c.S, SAND, 0.3), Mat.Grass)
		cyl(c, CFrame.new(0, 2.3, 4.9) * ALONG_Z, 0.1, 3.4, c.A, Mat.Neon)
		local function tree(x, z, h, d, turn)
			col(c, x, 0.25, z, h, d, c.P, Mat.Wood)
			local top = V(x, 0.25 + h, z)
			for k = 0, 2 do
				local a = turn + k * TAU / 3
				beam(c, top - V(0, 0.4, 0), top + V(math.cos(a) * 1.15, 1, math.sin(a) * 1.15), 0.3, c.P, Mat.Wood)
			end
			col(c, x, top.Y + 0.85, z, 0.4, 3, c.S, Mat.Grass)
		end
		tree(-2.5, -3.3, 7, 1.5, 0.2)
		tree(2.5, -2.2, 8, 1.6, 0.9)
		tree(-2.6, 0.2, 8.6, 1.7, 1.4)
		tree(2.4, 1.3, 7.4, 1.4, 0.5)
		tree(-2.3, 3.3, 7.8, 1.5, 1.1)
		tree(2.6, 3.4, 6.6, 1.3, 0.3)
		-- 소달구지
		box(c, 0.2, 0.75, -1.6, 0.9, 0.5, 1.2, WOOD, Mat.Wood)
		cyl(c, CFrame.new(0.2, 0.6, -1.5), 1.2, 0.7, DARK)
		box(c, 0.2, 0.3, -3, 0.6, 0.8, 1.2, rgb(150, 110, 80))
		box(c, 0.2, 0.8, -3.75, 0.45, 0.45, 0.5, rgb(150, 110, 80))
	end

	-- 아이트벤하두: 강과 야자수 앞, 언덕을 따라 층층이 쌓인 흙벽 성채(모서리마다 솟은 탑 + 톱니 테두리 + 좁은 창)
	--   + 언덕 꼭대기의 곡물 창고(아가디르)
	B.aitbenhaddou = function(c)
		local mud, dark = c.P, c.S
		local hill = mix(c.S, ROCK, 0.3)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, SAND, 0.4), Mat.Sand)
		box(c, 0, 0.2, -4.35, 9.8, 0.08, 1.1, WATER, Mat.Glass, 0.1)
		for _, x in { -3.8, -1.2, 3.6 } do
			plant(c, x, 0.2, -3.25, 1.3, 1, c.A)
		end
		box(c, 0, 0.2, 1.2, 9.6, 1, 7.2, hill, Mat.Rock)
		box(c, 0.4, 1.2, 2.2, 7.4, 1.5, 5.2, hill, Mat.Rock)
		box(c, 0.6, 2.7, 3.2, 4.6, 1.6, 3.2, hill, Mat.Rock)
		-- 아가디르
		box(c, 0.6, 4.3, 3.4, 3.4, 1.6, 1.6, mud)
		box(c, 0.6, 5.9, 3.4, 3.6, 0.25, 1.8, dark)
		-- 성채: 몸채 + 톱니 테두리 + 네 귀퉁이 탑 + 창
		local function kasbah(x, y, z, w, h, d, tower)
			box(c, x, y, z, w, h, d, mud)
			box(c, x, y + h, z, w + 0.1, 0.2, d + 0.1, dark)
			for _, s in CORNERS do
				local tx, tz = x + s[1] * (w / 2 - 0.3), z + s[2] * (d / 2 - 0.3)
				box(c, tx, y, tz, 0.75, h + tower, 0.75, mix(mud, WHITE, 0.08))
				if s[2] < 0 then
					box(c, tx, y + h + tower, tz, 0.95, 0.3, 0.95, dark)
				end
			end
			box(c, x, y + h * 0.55, z - d / 2 - 0.03, w * 0.45, 0.35, 0.08, DARK)
		end
		kasbah(-2.6, 1.2, -1.2, 3, 2.6, 2.4, 1.2)
		kasbah(2.4, 2.7, 0.8, 2.6, 2.2, 2.2, 1)
		-- 작은 집: { x, 바닥, z, 가로, 높이, 세로 }
		for _, h in
			{
				{ 0.3, 1.2, -1.7, 1.8, 1.6, 1.3 },
				{ 3.4, 1.2, -1.7, 2.2, 1.2, 1.2 },
				{ -2.2, 2.7, 1.3, 2.4, 1.6, 1.8 },
				{ -0.1, 2.7, 0.8, 1.4, 2, 1.2 },
			}
		do
			box(c, h[1], h[2], h[3], h[4], h[5], h[6], mix(mud, dark, 0.2))
			box(c, h[1], h[2] + h[5] * 0.5, h[3] - h[6] / 2 - 0.03, 0.4, 0.4, 0.08, DARK)
		end
		-- 성문 + 강에서 오르는 길
		box(c, -0.9, 0.2, -2.9, 1, 0.1, 1.8, mix(c.P, SAND, 0.6), Mat.Sand)
		box(c, -0.9, 0.2, -2.42, 0.8, 1.3, 0.1, DARK)
	end

	-- 데드블레이: 하얗게 갈라진 점토 바닥 + 검게 말라 죽은 낙타가시나무 + 뒤쪽의 거대한 주황 모래언덕(볕 든 면 / 그늘 면)
	B.deadvlei = function(c)
		local shade = mix(c.P, rgb(90, 30, 20), 0.5)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, SAND, 0.3), Mat.Sand)
		box(c, -0.6, 0.2, -2.2, 7.8, 0.1, 5, c.S, Mat.Sand)
		box(c, -2.2, 0.2, 0.6, 4, 0.1, 1.8, c.S, Mat.Sand)
		-- 큰 모래언덕(뒤쪽 전체): 왼쪽 뒤 꼭대기 H 에서 오른쪽 앞(F)으로 길게 내려오는 칼날 능선.
		--   능선 왼쪽·앞 면은 볕, 오른쪽 뒤 면은 그늘
		local H, F = V(-3.2, 5.8, 4.2), V(4, 0.2, -0.4)
		local L, BL, BR = V(-4.8, 0.2, 0.8), V(-4.8, 0.2, 4.8), V(4.8, 0.2, 4.8)
		tri(c, H, F, L, c.P, Mat.Sand, 0.3)
		tri(c, H, L, BL, mix(c.P, shade, 0.15), Mat.Sand, 0.3)
		tri(c, H, F, BR, shade, Mat.Sand, 0.3)
		-- 죽은 나무: 기운 줄기 + 비틀린 가지 셋
		local function deadTree(x, z, h, turn)
			local fork = V(x + 0.2, 0.3 + h * 0.5, z)
			beam(c, V(x, 0.3, z), fork, 0.34, c.A, Mat.Wood)
			for k = 0, 2 do
				local a = turn + k * 2.1
				local tip = fork + V(math.cos(a) * h * 0.42, h * (0.28 + 0.12 * k), math.sin(a) * h * 0.42)
				beam(c, fork, tip, 0.2, c.A, Mat.Wood)
			end
		end
		deadTree(-3, -3.2, 3.2, 0.3)
		deadTree(0.3, -2.4, 3.8, 1.2)
		deadTree(2.6, -3.8, 2.6, 2.2)
		deadTree(-2, 0.2, 2.8, 0.8)
		deadTree(1.2, -0.3, 2.4, 2.8)
	end

	-- 칭기 드 베마라하: 숲 바닥 + 좁은 협곡을 사이에 둔 회색 석회암 덩어리 둘 + 그 위로 빽빽이 솟은 칼날 봉우리들
	--   + 봉우리 사이를 잇는 흔들다리 + 협곡 속 초록 숲
	B.tsingy = function(c)
		local pale = mix(c.P, WHITE, 0.18)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.A, BLACK, 0.25), Mat.Grass)
		box(c, -2.75, 0.3, 0.3, 4.3, 1.6, 9, c.S)
		box(c, 2.85, 0.3, 0, 4.1, 1.2, 9.6, c.S)
		-- 봉우리: { x, z, 용마루 길이, 밑변, 높이, 방향 }
		for k, b in
			{
				{ -3.8, -3.3, 0.8, 1.6, 5.2, 0.3 },
				{ -2.5, -2.1, 0.7, 1.5, 6.8, 1.2 },
				{ -1.3, -3.5, 0.6, 1.3, 4.2, 0.7 },
				{ -3.7, -0.5, 0.9, 1.7, 7.4, 2 },
				{ -1.6, 0.5, 0.7, 1.4, 5.8, 0.2 },
				{ -3.1, 2.1, 0.8, 1.6, 6.2, 1 },
				{ -1.3, 2.9, 0.7, 1.3, 4.6, 2.4 },
				{ -3.8, 3.9, 0.8, 1.4, 5, 0.5 },
				{ 1.6, -3.6, 0.7, 1.4, 4.4, 0.9 },
				{ 3.3, -2.8, 0.8, 1.6, 6.4, 0.1 },
				{ 2, -1, 0.6, 1.2, 5, 1.8 },
				{ 3.8, 0.3, 0.8, 1.6, 7, 0.6 },
				{ 1.8, 1.9, 0.7, 1.4, 5.6, 2.6 },
				{ 3.4, 3.2, 0.8, 1.5, 6, 1.3 },
				{ 1.6, 4, 0.6, 1.2, 4, 0.2 },
			}
		do
			local y = if b[1] < 0 then 1.9 else 1.5
			blade(c, b[1], y, b[2], b[3], b[4], b[5], b[6], if k % 3 == 0 then pale else c.P)
		end
		-- 흔들다리(널판 + 난간 줄 둘)
		local a, e = V(-1.3, 4.2, -1.3), V(1.7, 4, -1.1)
		slab(c, a, e, 0.6, 0.1, WOOD, Mat.Wood)
		beam(c, a + V(0, 0.55, -0.3), e + V(0, 0.55, -0.3), 0.05, rgb(200, 180, 140))
		beam(c, a + V(0, 0.55, 0.3), e + V(0, 0.55, 0.3), 0.05, rgb(200, 180, 140))
		-- 협곡 숲
		for _, t in { { 0.1, -3.4, 1.3 }, { 0.2, -0.2, 1.1 }, { 0, 2.6, 1.3 }, { -4.3, -4.5, 0.8 } } do
			ball(c, t[1], 0.3 + t[3] / 2, t[2], t[3], c.A, Mat.Grass)
		end
	end

	-- 랄리벨라 성 게오르기우스 교회: 붉은 바위 고원을 네모나게 파낸 구덩이 + 그 속에 통째로 깎아 만든 십자가 모양 교회
	--   (3단 기단, 창문 두 줄, 지붕 위 겹십자 무늬, 지붕이 땅 높이와 같음) + 벽에 뚫린 은자의 굴 + 흰 옷 순례자
	B.lalibela = function(c)
		local rock = mix(c.P, c.S, 0.45)
		local church = mix(c.P, c.A, 0.12)
		local top = 4.2
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.S, BLACK, 0.15))
		box(c, -4.25, 0.3, 0, 1.3, top - 0.3, 9.8, rock)
		box(c, 4.25, 0.3, 0, 1.3, top - 0.3, 9.8, rock)
		box(c, 0, 0.3, 4.25, 7.2, top - 0.3, 1.3, rock)
		box(c, 0, 0.3, -4.25, 7.2, 0.9, 1.3, rock)
		local grass = mix(rgb(170, 150, 80), GRASS, 0.3)
		box(c, -4.25, top, 0, 1.3, 0.12, 9.8, grass, Mat.Grass)
		box(c, 4.25, top, 0, 1.3, 0.12, 9.8, grass, Mat.Grass)
		box(c, 0, top, 4.25, 7.2, 0.12, 1.3, grass, Mat.Grass)
		-- 십자가 교회: 기단 + 몸체 + 지붕 판(각각 가로·세로 두 팔)
		for _, arm in { { 6, 2.4 }, { 2.4, 6 } } do
			box(c, 0, 0.3, 0, arm[1] + 0.5, 0.8, arm[2] + 0.5, church)
			box(c, 0, 1.1, 0, arm[1], top - 1.4, arm[2], church)
			box(c, 0, top - 0.3, 0, arm[1] + 0.2, 0.3, arm[2] + 0.2, mix(church, c.A, 0.3))
		end
		-- 지붕의 겹십자 무늬
		box(c, 0, top, 0, 4, 0.1, 0.7, mix(c.P, BLACK, 0.2))
		box(c, 0, top, 0, 0.7, 0.1, 4, mix(c.P, BLACK, 0.2))
		box(c, 0, top + 0.1, 0, 2, 0.08, 0.3, c.A)
		box(c, 0, top + 0.1, 0, 0.3, 0.08, 2, c.A)
		-- 창문(위층 창 + 아래층 창)과 문
		local glass = DARK
		box(c, 0, 1.1, -3.03, 0.7, 1.2, 0.1, glass)
		box(c, 0, 2.8, -3.03, 0.5, 0.8, 0.1, glass)
		for _, sx in { -1, 1 } do
			box(c, sx * 3.03, 2.8, 0, 0.1, 0.8, 0.5, glass)
			box(c, sx * 3.03, 1.5, 0, 0.1, 0.8, 0.5, glass)
			box(c, sx * 2.1, 2.8, -1.23, 0.5, 0.8, 0.1, glass)
		end
		-- 은자의 굴 + 순례자
		box(c, -3.58, 1.2, 1.6, 0.1, 1, 0.8, DARK)
		box(c, 1.8, 1.6, 3.58, 0.9, 1, 0.1, DARK)
		for _, p in { { -2.6, -3.1 }, { -2.1, -3.3 }, { 2.5, -2.6 } } do
			col(c, p[1], 0.3, p[2], 0.8, 0.45, WHITE, Mat.Fabric)
			ball(c, p[1], 1.25, p[2], 0.3, rgb(90, 60, 45))
		end
	end

	-- 카르나크 신전: 숫양 스핑크스 길 + 오벨리스크 한 쌍 + 파피루스 기둥 숲(대열주실, 가운데 줄이 더 높고 푸른 칠 주두)
	--   + 들보 + 뒤쪽의 거대한 탑문(파일론)과 어두운 문
	B.karnak = function(c)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.P, SAND, 0.4), Mat.Sand)
		box(c, 0, 0.25, -2.5, 1.8, 0.06, 5, mix(c.P, WHITE, 0.25))
		-- 숫양 스핑크스(몸 + 머리)
		for _, sx in { -1, 1 } do
			for _, z in { -4.1, -2.8 } do
				box(c, sx * 1.35, 0.25, z, 0.6, 0.55, 1, c.S)
				ball(c, sx * 1.35, 1.05, z - 0.45, 0.55, c.S)
			end
		end
		-- 오벨리스크(몸 + 금빛 피라미드 머리)
		for _, sx in { -1, 1 } do
			box(c, sx * 3.7, 0.25, -3.4, 0.7, 6.4, 0.7, c.P)
			block(c, CFrame.new(sx * 3.7, 7, -3.4) * CFrame.Angles(0, PI / 4, 0), V(0.48, 0.7, 0.48), c.A)
		end
		-- 대열주실: { x, 높이 }
		for _, colm in { { -3.3, 4.4 }, { -1.1, 5.6 }, { 1.1, 5.6 }, { 3.3, 4.4 } } do
			local x, h = colm[1], colm[2]
			for _, z in { -0.6, 1.5 } do
				col(c, x, 0.25, z, h, 1.05, c.P)
				col(c, x, 0.25 + h, z, 0.55, 1.5, c.A)
			end
			box(c, x, 0.8 + h, 0.45, 1.2, 0.5, 3.4, c.S)
		end
		-- 탑문
		for _, sx in { -1, 1 } do
			box(c, sx * 2.7, 0.25, 3.9, 3.8, 4.6, 1.6, c.P)
			box(c, sx * 2.6, 4.85, 3.9, 3.4, 2.2, 1.4, c.P)
			box(c, sx * 2.6, 7.05, 3.9, 3.7, 0.35, 1.6, c.S)
		end
		box(c, 0, 0.25, 3.9, 1.8, 4.4, 1.2, mix(c.P, c.S, 0.3))
		box(c, 0, 0.25, 3.28, 1, 3, 0.1, DARK)
	end

	-- 메로에 피라미드: 주황 모래언덕 위에 줄지어 선 가파르고 뾰족한 누비아 피라미드들(계단 층) + 앞(동쪽)의 작은 예배당
	B.meroe = function(c)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, c.A, Mat.Sand)
		local dune = mix(c.A, c.P, 0.3)
		wedge(c, CFrame.new(-2.6, 0.6, -3.7) * CFrame.Angles(0, 0.3, 0), V(3.4, 0.7, 1.6), dune, Mat.Sand)
		wedge(c, CFrame.new(2.9, 0.55, -3.9) * CFrame.Angles(0, PI - 0.2, 0), V(3, 0.6, 1.4), dune, Mat.Sand)
		-- { x, z, 밑변, 높이, 단 수, 색 }
		local shade = mix(c.P, c.S, 0.4)
		for _, p in
			{
				{ -3.1, 2.3, 2.6, 5.4, 6, c.P },
				{ 0, 2.9, 2.9, 6.4, 7, shade },
				{ 3.1, 2, 2.5, 5, 6, c.P },
				{ -1.7, -0.9, 2.3, 4.4, 5, shade },
				{ 1.8, -0.6, 2.1, 3.6, 4, c.P },
			}
		do
			K.stepped(c, p[1], p[2], 0.25, p[3], p[4], p[5], p[6])
		end
		-- 예배당(탑문 모양 입구)
		for _, p in { { -3.1, 0.55 }, { 0, 1.05 }, { -1.7, -2.5 } } do
			box(c, p[1], 0.25, p[2], 1.2, 1.1, 0.9, c.S)
			box(c, p[1], 0.25, p[2] - 0.47, 0.4, 0.7, 0.06, DARK)
		end
	end

	-- 킬리만자로: 황금빛 초원 + 완만하고 넓은 화산(키보) 비탈 + 빙하 줄무늬 + 평평한 눈 덮인 꼭대기와 분화구
	--   + 정면에서 왼쪽(+X)의 들쭉날쭉한 마웬지 봉 + 앞쪽 우산 아카시아와 코끼리
	B.kilimanjaro = function(c)
		local savanna = mix(c.A, rgb(214, 190, 110), 0.55)
		local snow = c.S
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, savanna, Mat.Grass)
		local center = V(0, 0.25, 0.6)
		local lower = mix(c.P, c.A, 0.25)
		slopeRing(c, center, 11, 4.2, 0.2, 2.4, 3.3, 2.5, function(i)
			return if i % 2 == 0 then lower else mix(lower, BLACK, 0.08)
		end, Mat.Rock)
		slopeRing(c, center, 10, 2.5, 3.2, 1.75, 4.9, 1.7, function(i)
			return if i % 3 == 1 then c.P else snow
		end, Mat.Rock, 0.5)
		col(c, center.X, 4.85, center.Z, 0.3, 3.7, snow, Mat.Snow)
		col(c, center.X, 4.9, center.Z, 0.3, 1.8, mix(snow, ROCK, 0.4))
		-- 마웬지
		local craggy = mix(c.P, BLACK, 0.15)
		for _, b in { { 3.5, 2.8, 1.3, 3.8, 0.4, 0.12 }, { 3, 3.4, 1, 4.6, 0.9, -0.1 }, { 4, 3.3, 0.9, 3, 0.2, 0.2 } } do
			block(
				c,
				CFrame.new(b[1], 0.25 + b[4] / 2, b[2]) * CFrame.Angles(0, b[5], b[6]),
				V(b[3], b[4], b[3]),
				craggy
			)
		end
		acacia(c, -3.5, 0.25, -3.4, 2, 2.4, c.A, 0.3)
		acacia(c, 3.7, 0.25, -2.4, 1.6, 2, c.A, -0.2)
		elephant(c, 0.8, 0.25, -3.6, PI / 2, 1)
	end

	-- 빅토리아 폭포: 뒤쪽 고원 위 잠베지강 + 좁은 틈으로 폭 넓게 쏟아지는 흰 물 커튼(섬 사이로 나뉨) + 틈 바닥의 물
	--   + 앞쪽 낮은 고원의 열대우림 + 오른쪽으로 빠져나가는 협곡과 강철 아치 다리 + 피어오르는 물보라와 무지개
	B.victoriafalls = function(c)
		local basalt = c.S
		local top, front = 4.6, 1.2
		local white = mix(c.A, c.P, 0.12)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.P, rgb(20, 70, 130), 0.3), Mat.Glass, 0.1)
		-- 뒤 고원 + 강 + 강 위의 섬(리빙스턴섬 등)
		box(c, 0, 0.25, 2.85, 9.8, top - 0.35, 4.1, basalt)
		box(c, 0, top - 0.1, 2.85, 9.8, 0.2, 4.1, c.P)
		for _, i in { { -2, 1.6 }, { 1.2, 1.8 } } do
			box(c, i[1], top - 0.1, i[2], 0.7, 0.4, 2, LEAF, Mat.Grass)
			ball(c, i[1], top + 0.6, i[2] + 0.2, 0.9, LEAF, Mat.Grass)
		end
		-- 물 커튼(섬 자리에서 끊김) + 물줄기 결 + 바닥 물거품
		for _, seg in { { -4.9, -2.35 }, { -1.65, 0.85 }, { 1.55, 4.9 } } do
			box(c, (seg[1] + seg[2]) / 2, 0.25, 0.65, seg[2] - seg[1], top - 0.1, 0.3, white, Mat.Neon, 0.05)
		end
		for _, x in { -4.2, -3.1, -1, 0.3, 2.3, 3.4, 4.4 } do
			box(c, x, 0.8, 0.48, 0.22, top - 1.2, 0.06, mix(c.P, WHITE, 0.6), Mat.SmoothPlastic)
		end
		box(c, 0, 0.25, 0.1, 9.8, 0.7, 0.9, WHITE, Mat.SmoothPlastic, 0.1)
		-- 앞 고원(낮음, 오른쪽으로 빠지는 협곡으로 둘로 나뉨)
		local rim = mix(LEAF, GRASS, 0.3)
		box(c, -1.45, 0.25, -2.95, 7.1, front - 0.25, 3.9, basalt)
		box(c, 4.25, 0.25, -2.95, 1.3, front - 0.25, 3.9, basalt)
		box(c, -1.45, front, -2.95, 7.1, 0.15, 3.9, rim, Mat.Grass)
		box(c, 4.25, front, -2.95, 1.3, 0.15, 3.9, rim, Mat.Grass)
		for _, t in { { -4.3, -1.9, 1.1 }, { -4.2, -3.9, 1.2 }, { -3.2, -4.3, 0.9 }, { 4.3, -4.3, 0.9 } } do
			ball(c, t[1], front + 0.15 + t[3] * 0.4, t[2], t[3], LEAF, Mat.Grass)
		end
		-- 다리(강철 아치 + 상판)
		local steel = rgb(150, 140, 120)
		local span = { V(2.05, 0.4, -3.4), V(2.55, 1.05, -3.4), V(3.05, 1.05, -3.4), V(3.55, 0.4, -3.4) }
		for k = 1, 3 do
			beam(c, span[k], span[k + 1], 0.18, steel, Mat.Metal)
		end
		box(c, 2.8, front, -3.4, 1.8, 0.18, 0.6, steel, Mat.Metal)
		-- 피어오르는 물보라("천둥 치는 연기") + 무지개(빨강·노랑·파랑 호)
		ball(c, -2.6, 4.9, 0.1, 2.8, WHITE, Mat.SmoothPlastic, 0.7)
		ball(c, 2.4, 5.3, 0.3, 2.4, WHITE, Mat.SmoothPlastic, 0.72)
		local bands = { { 2.2, rgb(255, 90, 90) }, { 1.95, rgb(255, 225, 80) }, { 1.7, rgb(90, 160, 255) } }
		for _, band in bands do
			local points = {}
			for k = 0, 4 do
				local a = k / 4 * PI
				table.insert(points, V(-2.3 + band[1] * math.cos(a), 0.4 + band[1] * math.sin(a) * 1.3, -0.4))
			end
			for k = 1, 4 do
				beam(c, points[k], points[k + 1], 0.2, band[2], Mat.Neon, 0.3)
			end
		end
	end

	-- 세렝게티: 황금빛 풀밭 + 우산 아카시아 + 사자가 올라앉은 화강암 바위 언덕(코피) + 기린 + 얼룩말 + 누 떼 + 지는 해
	B.serengeti = function(c)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, c.P, Mat.Grass)
		box(c, -2.4, 0.25, 2.2, 3.8, 0.05, 3.2, mix(c.S, c.P, 0.45), Mat.Grass)
		box(c, 2.6, 0.25, -1.4, 3.4, 0.05, 2.6, mix(c.S, c.P, 0.45), Mat.Grass)
		cyl(c, CFrame.new(1.2, 2.2, 4.9) * ALONG_Z, 0.1, 3.4, c.A, Mat.Neon)
		-- 코피 + 사자(정면을 보고 앉음: 몸 + 갈기 + 얼굴)
		local granite = rgb(150, 140, 126)
		ball(c, -3.3, 1.25, 3.4, 2.5, granite)
		ball(c, -1.8, 0.95, 3.9, 1.9, mix(granite, BLACK, 0.12))
		block(c, CFrame.new(-2.7, 2.35, 3) * CFrame.Angles(0, 0.3, 0.1), V(2.4, 0.45, 1.5), granite)
		local lion, mane = rgb(214, 168, 92), rgb(140, 82, 38)
		box(c, -2.7, 2.55, 3.2, 0.6, 0.65, 1.1, lion)
		ball(c, -2.7, 3.35, 2.75, 0.9, mane)
		ball(c, -2.7, 3.3, 2.4, 0.5, lion)
		-- 아카시아
		acacia(c, 2.3, 0.25, 2.4, 2.8, 3.2, c.S, 0.4)
		acacia(c, -3.7, 0.25, -1.2, 2, 2.4, c.S, 0.35)
		acacia(c, 3.4, 0.25, -3.6, 1.5, 2, c.S, 0.2)
		-- 기린 + 얼룩말(흰 몸 + 검은 줄) + 누 떼
		giraffe(c, 0.4, 0.25, 0.8, PI / 2 + 0.4, 1)
		local cf = CFrame.new(-0.8, 0.25, -2.4) * CFrame.Angles(0, -PI / 2 + 0.3, 0)
		block(c, cf * CFrame.new(0, 0.42, -0.36), V(0.42, 0.84, 0.14), WHITE)
		block(c, cf * CFrame.new(0, 0.42, 0.36), V(0.42, 0.84, 0.14), WHITE)
		block(c, cf * CFrame.new(0, 1.05, 0), V(0.52, 0.5, 1.15), WHITE)
		for _, dz in { -0.25, 0.05, 0.35 } do
			block(c, cf * CFrame.new(0, 1.05, dz), V(0.56, 0.54, 0.1), BLACK)
		end
		beam(c, cf * V(0, 1.1, -0.45), cf * V(0, 1.75, -0.85), 0.28, WHITE)
		local gnu = rgb(70, 66, 62)
		for _, g in { { -3.9, -3.8 }, { -2.7, -4.1 }, { -3.3, -3 }, { -1.9, -3.4 } } do
			block(c, CFrame.new(g[1], 0.75, g[2]) * CFrame.Angles(0, 0.3, 0), V(0.8, 0.5, 0.42), gnu)
			block(c, CFrame.new(g[1] + 0.45, 0.8, g[2] + 0.15) * CFrame.Angles(0, 0.3, 0.5), V(0.4, 0.28, 0.26), gnu)
		end
	end

	-- 사하라 사막: 칼날 능선의 모래언덕 셋(볕 든 면 / 그늘 면) + 야자수 오아시스 + 투아레그 사람을 태운 낙타 대상
	B.sahara = function(c)
		local shade = mix(c.S, rgb(120, 60, 30), 0.3)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, c.P, Mat.Sand)
		-- 큰 모래언덕: 왼쪽 뒤 꼭대기에서 오른쪽 앞으로 길게 내려오는 칼날 능선(볕 든 면 / 그늘 면)
		local lit = mix(c.P, WHITE, 0.12)
		local H, F = V(-3.2, 4.6, 4.2), V(4, 0.25, -0.2)
		tri(c, H, F, V(-4.8, 0.25, 0.8), lit, Mat.Sand, 0.3)
		tri(c, H, V(-4.8, 0.25, 0.8), V(-4.8, 0.25, 4.8), mix(lit, shade, 0.25), Mat.Sand, 0.3)
		tri(c, H, F, V(4.8, 0.25, 4.8), shade, Mat.Sand, 0.3)
		-- 낮은 모래 물결(완만한 비탈 하나) + 바람 자국
		wedge(c, CFrame.new(-3.4, 0.45, -3.6) * CFrame.Angles(0, -0.2, 0), V(2.6, 0.4, 1.6), lit, Mat.Sand)
		block(c, CFrame.new(0.2, 0.27, -3.5) * CFrame.Angles(0, 0.1, 0), V(3.4, 0.04, 0.08), shade, Mat.Sand)
		-- 오아시스
		col(c, 2.9, 0.25, -3.2, 0.08, 3.2, c.A, Mat.Grass)
		col(c, 2.9, 0.3, -3.2, 0.08, 2.2, WATER, Mat.Glass, 0.1)
		palm(c, 3.3, 0.25, -2.2, 2.8, c.A, 0.3)
		palm(c, 1.8, 0.25, -3.7, 2.2, c.A, 0.9)
		-- 낙타 대상(오른쪽 = -X 로 걸어감)
		local fur = rgb(196, 150, 96)
		local function camel(x, z)
			local cf = CFrame.new(x, 0.25, z) * CFrame.Angles(0, PI / 2, 0)
			block(c, cf * CFrame.new(0, 0.55, -0.42), V(0.5, 1.1, 0.16), fur)
			block(c, cf * CFrame.new(0, 0.55, 0.45), V(0.5, 1.1, 0.16), fur)
			block(c, cf * CFrame.new(0, 1.35, 0), V(0.55, 0.55, 1.3), fur)
			local hump = cf * V(0, 1.65, 0.1)
			ball(c, hump.X, hump.Y, hump.Z, 0.75, fur)
			beam(c, cf * V(0, 1.35, -0.6), cf * V(0, 2.2, -0.95), 0.28, fur)
			block(c, cf * CFrame.new(0, 2.25, -1.15), V(0.3, 0.3, 0.55), fur)
		end
		camel(-2.8, -1.7)
		camel(-0.6, -1.4)
		camel(1.4, -1.1)
		col(c, -2.7, 1.9, -1.7, 0.9, 0.5, rgb(40, 70, 160), Mat.Fabric)
		ball(c, -2.7, 3, -1.7, 0.42, rgb(30, 50, 120), Mat.Fabric)
	end

	-- 아부심벨 대신전: 사암 절벽을 깎은 정면(위쪽 개코원숭이 띠) + 앉은 람세스 2세 거상 넷(네메스 두건, 이중관, 수염;
	--   정면에서 왼쪽 두 번째는 부서져 머리가 발치에 떨어져 있음) + 가운데 문 + 문 위 라-호라크티 신상과 태양 원반 + 나세르 호수
	B.abusimbel = function(c)
		local cliff = mix(c.P, c.S, 0.75)
		local nemes = mix(c.P, WHITE, 0.25)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.P, SAND, 0.4), Mat.Sand)
		box(c, 0, 0, -4.3, 9.8, 0.34, 1.2, WATER, Mat.Glass, 0.1)
		box(c, 0, 0.3, 0.1, 9.6, 0.4, 3.6, c.S)
		box(c, 0, 0.3, 3.1, 9.8, 8.4, 3.4, cliff)
		box(c, 0, 8.1, 1.3, 9.4, 0.6, 0.3, c.S)
		box(c, 0, 7.8, 1.3, 9.4, 0.15, 0.3, c.A)
		box(c, 0, 0.7, 1.35, 1.1, 2.8, 0.1, DARK)
		box(c, 0, 3.9, 1.35, 1.2, 2.4, 0.1, mix(cliff, BLACK, 0.35))
		col(c, 0, 3.9, 1.2, 1.7, 0.55, c.P)
		cyl(c, CFrame.new(0, 6.05, 1.15) * ALONG_Z, 0.12, 0.75, c.A, Mat.Neon)
		local y0 = 0.7
		local function colossus(x, broken)
			for _, side in { -1, 1 } do
				box(c, x + side * 0.42, y0, -0.9, 0.62, 2.6, 0.9, c.P)
			end
			box(c, x, y0 + 2.6, -0.05, 1.8, 0.6, 2.6, c.P)
			if broken then
				box(c, x, y0 + 3.2, 0.7, 1.7, 1, 1.2, c.P)
				block(c, CFrame.new(x - 0.3, 0.95, -2.3) * CFrame.Angles(0.2, 0.5, PI / 2 - 0.2), V(1.05, 1.3, 1), c.P)
				return
			end
			box(c, x, y0 + 3.2, 0.7, 1.7, 2.3, 1.2, c.P)
			box(c, x, y0 + 4.9, 0.8, 2.05, 1.9, 1.1, nemes)
			box(c, x, y0 + 5.4, 0.35, 1.05, 1.35, 0.9, c.P)
			box(c, x, y0 + 5, -0.05, 0.3, 0.55, 0.3, c.P)
			col(c, x, y0 + 6.75, 0.6, 1.15, 0.8, nemes)
		end
		colossus(3.7, false)
		colossus(1.55, true)
		colossus(-1.55, false)
		colossus(-3.7, false)
	end

	-- 투탕카멘의 황금 가면: 사암 받침 + 황금 가슴과 층층이 좁아지는 보석 목깃 + 파란 줄무늬 네메스 두건(양옆으로 벌어진 날개,
	--   앞으로 늘어진 두 자락) + 금빛 얼굴(검은 눈화장, 코, 입) + 땋은 파란 수염 + 이마의 코브라·독수리
	B.tutankhamun = function(c)
		local gold, lapis = c.P, c.S
		local face = mix(c.P, WHITE, 0.1)
		box(c, 0, 0, 0.4, 6.8, 1, 4.4, c.A, Mat.Sandstone)
		box(c, 0, 1, 0.7, 6, 2.4, 2.6, gold)
		for k, band in { { 5.8, lapis }, { 5, rgb(64, 180, 190) }, { 4, rgb(190, 70, 50) }, { 2.8, lapis } } do
			box(c, 0, 3.4 - k * 0.4, -0.64, band[1], 0.4, 0.1, band[2])
		end
		-- 네메스: 뒤통수 덩어리 + 둥근 윗부분 + 벌어진 양옆 날개(줄무늬) + 윗머리 줄무늬 + 앞 자락(줄무늬)
		box(c, 0, 3.4, 0.8, 3.6, 3.8, 2.6, gold)
		box(c, 0, 7.2, 0.8, 3, 0.5, 2.3, gold)
		for _, sx in { -1, 1 } do
			local flap = CFrame.new(sx * 2.05, 5.1, -0.1) * CFrame.Angles(0, 0, sx * 0.2)
			block(c, flap, V(1.3, 3.4, 1.6), gold)
			for _, dy in { -1.15, -0.25, 0.65 } do
				block(c, flap * CFrame.new(0, dy, -0.82), V(1.34, 0.3, 0.06), lapis)
			end
			box(c, sx * 1.55, 1.2, -0.72, 0.8, 2.3, 0.3, gold)
			for _, y in { 1.7, 2.6 } do
				box(c, sx * 1.55, y, -0.9, 0.84, 0.3, 0.06, lapis)
			end
		end
		box(c, 0, 6.95, -0.52, 3.4, 0.28, 0.1, lapis)
		box(c, 0, 7.4, -0.37, 2.9, 0.22, 0.1, lapis)
		-- 얼굴
		box(c, 0, 4, -0.75, 2.3, 2.7, 0.9, face)
		box(c, 0, 6.5, -0.78, 2.5, 0.35, 0.96, gold)
		for _, sx in { -1, 1 } do
			box(c, sx * 0.55, 5.3, -1.22, 0.62, 0.3, 0.06, WHITE)
			box(c, sx * 0.55, 5.32, -1.26, 0.26, 0.26, 0.04, BLACK)
			block(c, CFrame.new(sx * 0.6, 5.85, -1.23) * CFrame.Angles(0, 0, sx * -0.12), V(0.8, 0.14, 0.06), lapis)
		end
		wedge(c, CFrame.new(0, 5.05, -1.35), V(0.42, 0.8, 0.3), face)
		box(c, 0, 4.4, -1.22, 0.7, 0.14, 0.06, rgb(170, 70, 50))
		beam(c, V(0, 4.1, -0.95), V(0, 2.75, -1.3), 0.45, lapis)
		col(c, 0, 6.6, -1.3, 0.6, 0.26, gold)
		ball(c, 0, 7.25, -1.3, 0.36, gold)
	end

	-- 사하라의 눈(리샤트 구조): 사막 한가운데 밝고 어두운 띠가 번갈아 도는 거대한 과녁 모양 돔(안쪽으로 갈수록 조금씩 높음)
	--   + 가장자리로 밀려드는 주황 모래언덕
	B.richat = function(c)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, mix(c.P, SAND, 0.35), Mat.Sand)
		local rings = {
			{ 9.4, c.S },
			{ 8.3, c.A },
			{ 7.3, c.S },
			{ 6.2, c.P },
			{ 5.1, c.S },
			{ 4, c.A },
			{ 2.9, c.S },
			{ 1.8, c.P },
			{ 0.8, c.A },
		}
		for k, r in rings do
			col(c, 0, 0.2, 0, 0.15 + k * 0.14, r[1], r[2], if r[2] == c.S then Mat.Rock else Mat.Sand)
		end
		for _, d in { { 3.7, -3.7, 2, 0.6, 0.8 }, { 4, -2.4, 1.4, 0.4, 0.8 }, { 2.4, -4, 1.4, 0.4, 0.8 } } do
			wedge(
				c,
				CFrame.new(d[1], 0.2 + d[4] / 2, d[2]) * CFrame.Angles(0, d[5], 0),
				V(d[3], d[4], 1),
				mix(c.P, rgb(230, 120, 50), 0.3),
				Mat.Sand
			)
		end
	end

	-- 그레이트 짐바브웨: 풀밭 위 타원형으로 휘어 도는 높은 마른돌 성벽(대 울타리, 앞쪽에 입구, 앞 왼쪽 벽 윗부분의 V자 띠 장식)
	--   + 안쪽의 평행 성벽과 원뿔 탑 + 돌기둥 위의 짐바브웨 새 + 바위 언덕 + 나무
	B.greatzimbabwe = function(c)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(GRASS, SAND, 0.45), Mat.Grass)
		local cx, cz, a, b = 0.2, -0.3, 4, 3.5
		local n = 14
		local function point(t, scale)
			return V(cx + a * scale * math.cos(t), 0.25, cz + b * scale * math.sin(t))
		end
		for i = 0, n - 1 do
			if i ~= 8 then
				local t1, t2 = i / n * TAU, (i + 1) / n * TAU
				local p1, p2 = point(t1, 1), point(t2, 1)
				local tm = (t1 + t2) / 2
				local h = 2.7 + 0.5 * math.sin(tm)
				local mid = (p1 + p2) / 2 + V(0, h / 2, 0)
				local cf = CFrame.lookAt(mid, p2 + V(0, h / 2, 0))
				local len = (p2 - p1).Magnitude + 0.25
				block(c, cf, V(0.8, h, len), if i % 2 == 0 then c.P else mix(c.P, c.S, 0.25))
				-- 앞 왼쪽(+X, -Z) 벽의 V자 띠(바깥면)
				if i >= 11 then
					for k = -1, 1 do
						local chevron = cf * CFrame.new(-0.42, h / 2 - 0.45, k * len / 3) * CFrame.Angles(PI / 4, 0, 0)
						block(c, chevron, V(0.08, 0.34, 0.34), c.S)
					end
				end
			end
		end
		-- 안쪽 평행 성벽(뒤 왼쪽)
		for i = 1, 3 do
			local t1, t2 = i / n * TAU, (i + 1) / n * TAU
			local p1, p2 = point(t1, 0.74), point(t2, 0.74)
			local mid = (p1 + p2) / 2 + V(0, 1.1, 0)
			block(c, CFrame.lookAt(mid, p2 + V(0, 1.1, 0)), V(0.6, 2.2, (p2 - p1).Magnitude + 0.2), mix(c.P, c.S, 0.15))
		end
		-- 원뿔 탑
		local tx, tz = 1.3, 0.9
		col(c, tx, 0.25, tz, 2.2, 1.8, c.P)
		col(c, tx, 2.45, tz, 1.5, 1.4, c.P)
		col(c, tx, 3.95, tz, 1, 1, c.P)
		col(c, tx, 4.95, tz, 0.4, 0.66, c.P)
		-- 짐바브웨 새(돌기둥 위, 금빛)
		local bx, bz = -1.4, -0.9
		col(c, bx, 0.25, bz, 2.8, 0.5, c.S)
		block(c, CFrame.new(bx, 3.55, bz) * CFrame.Angles(0.25, 0, 0), V(0.45, 1.1, 0.6), c.A, Mat.Metal)
		ball(c, bx, 4.25, bz - 0.25, 0.42, c.A, Mat.Metal)
		wedge(c, CFrame.new(bx, 4.2, bz - 0.6) * CFrame.Angles(PI, 0, 0), V(0.16, 0.2, 0.35), c.A, Mat.Metal)
		-- 바위 언덕 + 나무
		ball(c, -4.1, 0.9, 4.1, 1.6, mix(c.S, ROCK, 0.3))
		ball(c, 4.2, 0.8, 4.2, 1.4, mix(c.S, ROCK, 0.3))
		plant(c, -4.2, 0.25, -4.1, 1.3, 1.3, LEAF)
		plant(c, 4.2, 0.25, -4, 1.1, 1.2, mix(LEAF, rgb(170, 90, 50), 0.3))
	end

	-- 헤라클레이온 해저 도시: 바닷속(투명한 물 덩어리) 모래 바닥 위의 붉은 화강암 거상(하피 신) + 무너진 신전(선 기둥, 부러진 기둥,
	--   쓰러진 기둥과 들보) + 검은 석비 + 작은 스핑크스 + 항아리 + 해초 + 물고기 + 햇살 줄기 + 수면 위의 작은 배
	B.heracleion = function(c)
		local stone = c.P
		local granite = rgb(170, 88, 76)
		local basalt = rgb(62, 64, 70)
		local surface = 7.7
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.P, SAND, 0.35), Mat.Sand)
		-- 거상(정면을 봄)
		local sx, sz = 1.6, 2.2
		box(c, sx, 0.3, sz, 1.9, 0.6, 1.5, stone)
		box(c, sx, 0.9, sz, 1.15, 2.4, 0.85, granite)
		box(c, sx, 3.3, sz, 1.6, 1.8, 0.9, granite)
		for _, side in { -1, 1 } do
			box(c, sx + side * 1, 2.5, sz, 0.4, 2.4, 0.55, granite)
		end
		box(c, sx, 5.1, sz - 0.05, 0.8, 0.9, 0.8, granite)
		box(c, sx, 4.9, sz + 0.15, 1.3, 1, 0.7, mix(granite, BLACK, 0.2))
		col(c, sx, 6, sz, 1.1, 0.7, granite)
		-- 무너진 신전
		box(c, -2.6, 0.3, 1.5, 4, 0.4, 3.4, stone)
		for _, p in { { -3.8, 0.3, 3.4 }, { -1.5, 0.3, 3 } } do
			col(c, p[1], 0.7, p[2], p[3], 0.65, stone)
			box(c, p[1], 0.7 + p[3], p[2], 0.95, 0.3, 0.95, stone)
		end
		col(c, -3.8, 0.7, 2.7, 1.2, 0.65, stone)
		cyl(c, CFrame.new(-2.2, 1.02, 2.6) * CFrame.Angles(0, 0.35, 0), 2.6, 0.62, stone)
		block(c, CFrame.new(-2.8, 0.62, -1.3) * CFrame.Angles(0, 0.45, 0.12), V(2.6, 0.5, 0.65), stone)
		-- 석비 + 스핑크스 + 항아리
		box(c, 3.6, 0.3, -0.6, 1, 2.2, 0.3, basalt)
		cyl(c, CFrame.new(3.6, 2.5, -0.6) * ALONG_Z, 0.3, 1, basalt)
		box(c, 0.2, 0.3, -2.4, 0.8, 0.6, 1.7, stone)
		box(c, 0.2, 0.6, -3.1, 0.75, 0.95, 0.65, stone)
		ball(c, 2.7, 0.62, -3.4, 0.64, rgb(180, 112, 72))
		ball(c, 3.4, 0.56, -3.9, 0.52, rgb(165, 100, 64))
		-- 해초
		for _, w in { { -4.3, -3, 2.2 }, { -3.8, -3.6, 1.6 }, { 4.3, 3.7, 2.4 } } do
			beam(c, V(w[1], 0.3, w[2]), V(w[1] - 0.25, 0.3 + w[3], w[2] - 0.15), 0.14, LEAF, Mat.Grass)
		end
		-- 물고기(몸 + 꼬리)
		local fish = rgb(255, 170, 60)
		for _, f in { { -0.8, 4.4, 0.4, 0.3 }, { -0.3, 5, 0.9, 0.3 }, { 3.3, 3.8, -2.2, -0.5 } } do
			local cf = CFrame.new(f[1], f[2], f[3]) * CFrame.Angles(0, f[4], 0)
			block(c, cf, V(0.55, 0.3, 0.2), fish)
			wedge(c, cf * CFrame.new(0.4, 0, 0) * CFrame.Angles(0, PI / 2, 0), V(0.1, 0.34, 0.28), fish)
		end
		-- 햇살 줄기
		for _, r in { { -1, 0.35 }, { 2.4, 0.3 } } do
			block(c, CFrame.new(r[1], 4, -0.4) * CFrame.Angles(0, 0, r[2]), V(0.5, 6.6, 0.1), c.A, Mat.Neon, 0.8)
		end
		-- 바닷물 + 수면 위의 배
		box(c, 0, 0.3, 0, 9.8, surface - 0.3, 9.8, c.S, Mat.Glass, 0.6)
		box(c, -2.6, surface, -3, 2, 0.35, 0.8, WOOD, Mat.Wood)
		col(c, -2.6, surface + 0.35, -3, 1.8, 0.1, WOOD, Mat.Wood)
		box(c, -2.4, surface + 0.8, -3, 0.9, 1.1, 0.05, WHITE, Mat.Fabric)
	end

	-- 알렉산드리아 도서관: 3단 기단 위 그리스식 신전(이오니아 기둥 열, 금빛 띠, 박공 지붕) + 기둥 사이로 보이는
	--   두루마리 가득한 서가 + 빛나는 문 + 앞의 두루마리 독서대 + 금빛 화로 둘
	B.libraryalex = function(c)
		local marble, gold, glow = c.P, c.S, c.A
		local scroll = rgb(236, 218, 172)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, mix(c.S, SAND, 0.5), Mat.Sandstone)
		for k = 0, 2 do
			box(c, 0, 0.3 + k * 0.3, 0.6 + k * 0.1, 9.2 - k * 0.6, 0.3, 7.6 - k * 0.6, marble)
		end
		box(c, 0, 1.2, 1.9, 6.4, 4.8, 3.8, mix(marble, gold, 0.15))
		-- 서가(두루마리 세 줄) + 빛나는 문
		for _, sx in { -1, 1 } do
			box(c, sx * 2, 1.4, -0.06, 2.1, 4.1, 0.12, WOOD, Mat.Wood)
			for k = 0, 2 do
				cyl(c, CFrame.new(sx * 2, 2 + k * 1.25, -0.3), 1.9, 0.42, scroll)
			end
		end
		box(c, 0, 1.2, -0.06, 1.2, 3.1, 0.12, glow, Mat.Neon)
		-- 기둥: 앞줄 6 + 양옆 3씩
		for _, x in { -3.5, -2.1, -0.7, 0.7, 2.1, 3.5 } do
			col(c, x, 1.2, -2, 4.8, 0.6, marble)
		end
		for _, sx in { -1, 1 } do
			for _, z in { -0.2, 1.6, 3.4 } do
				col(c, sx * 3.7, 1.2, z, 4.8, 0.6, marble)
			end
		end
		box(c, 0, 6, 0.8, 8, 0.7, 6.4, marble)
		box(c, 0, 6.2, -2.44, 8, 0.3, 0.1, gold)
		frontGable(c, 0, 6.7, 0.8, 8, 6.4, 1.6, marble)
		ball(c, 0, 8.45, -2.3, 0.5, gold, Mat.Metal)
		-- 화로 + 독서대(펼친 두루마리)
		for _, sx in { -1, 1 } do
			col(c, sx * 4, 0.3, -4, 1.2, 0.4, gold, Mat.Metal)
			ball(c, sx * 4, 1.8, -4, 0.7, glow, Mat.Neon)
		end
		box(c, 0, 0.3, -3.9, 0.3, 0.8, 0.3, WOOD, Mat.Wood)
		block(c, CFrame.new(0, 1.2, -3.9) * CFrame.Angles(-0.4, 0, 0), V(1.3, 0.05, 0.7), scroll)
		for _, sx in { -1, 1 } do
			col(c, sx * 0.7, 0.95, -3.9, 0.5, 0.2, scroll)
		end
	end

	-- 사하라 신기루 성: 땅에 닿지 않고 떠 있는 사암 섬(아래로 뾰족) 위의 흙벽 성채(톱니 성벽, 네 귀퉁이 둥근 탑, 가운데 성관 +
	--   신기루처럼 빛나는 유리 돔, 가느다란 첨탑) + 야자수 + 흘러내리는 모래 폭포 + 아래에 일렁이는 신기루 빛 고리 + 떠다니는 돌
	B.skyisland = function(c)
		local sand, stone = c.P, c.S
		local rock = Mat.Sandstone
		col(c, 0, 6.6, 0, 1.4, 9.4, stone, rock)
		col(c, 0.2, 5.2, -0.1, 1.4, 7.2, stone, rock)
		col(c, -0.1, 3.9, 0.2, 1.3, 5, mix(stone, BLACK, 0.1), rock)
		col(c, 0.1, 2.8, 0, 1.1, 2.8, mix(stone, BLACK, 0.15), rock)
		ball(c, 0.1, 2.6, 0, 1.4, mix(stone, BLACK, 0.2), rock)
		col(c, 0, 8, 0, 0.3, 9, sand, Mat.Sand)
		local g = 8.3
		-- 성벽 + 성문 + 앞 성벽 톱니
		box(c, 0, g, -3, 6.4, 1.8, 0.45, sand)
		box(c, 0, g, 3, 6.4, 1.8, 0.45, sand)
		box(c, -3, g, 0, 0.45, 1.8, 6.4, sand)
		box(c, 3, g, 0, 0.45, 1.8, 6.4, sand)
		box(c, 0, g, -3.25, 1, 1.3, 0.1, DARK)
		for _, x in { -2, -1, 1, 2 } do
			box(c, x, g + 1.8, -3, 0.5, 0.4, 0.45, sand)
		end
		-- 네 귀퉁이 탑
		for _, s in CORNERS do
			col(c, s[1] * 3, g, s[2] * 3, 3, 1.3, sand)
			col(c, s[1] * 3, g + 3, s[2] * 3, 0.4, 1.55, stone)
		end
		-- 성관 + 유리 돔 + 첨탑
		box(c, 0.4, g, 0.8, 2.8, 3.2, 2.8, sand)
		col(c, 0.4, g + 3.2, 0.8, 0.4, 2.4, stone)
		ball(c, 0.4, g + 4.1, 0.8, 2.3, c.A, Mat.Glass, 0.2)
		col(c, 0.4, g + 5.2, 0.8, 0.8, 0.15, c.A, Mat.Neon)
		col(c, -1.7, g, 1.9, 5.8, 0.7, sand)
		col(c, -1.7, g + 4.6, 1.9, 0.25, 1.1, stone)
		ball(c, -1.7, g + 6.1, 1.9, 0.75, c.A, Mat.Glass, 0.2)
		-- 야자수
		plant(c, 2, g, -1.8, 1.3, 1.1, LEAF)
		plant(c, -1.9, g, -1.6, 1, 0.9, LEAF)
		-- 모래 폭포 + 신기루 빛 고리 + 떠다니는 돌
		box(c, 3.9, 1.6, -2.4, 0.6, 6.4, 0.3, sand, Mat.Sand, 0.35)
		col(c, 0, 0.6, 0, 0.08, 7.4, c.A, Mat.Neon, 0.75)
		col(c, 0, 1.2, 0, 0.08, 4.6, c.A, Mat.Neon, 0.65)
		ball(c, 4.3, 6.2, 2.6, 0.9, stone, rock)
		ball(c, -4.3, 9.6, -1.2, 0.7, stone, rock)
	end

	return B
end
