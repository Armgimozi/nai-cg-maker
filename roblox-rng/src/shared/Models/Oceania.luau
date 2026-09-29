-- 오세아니아 명소 전용 모형. Models/init.luau 가 K(파트 헬퍼·색·기존 모양)를 넘겨 호출합니다.
-- 규칙: 바닥 10x10 안, 높이 22 이하, 바닥 y = 0, 정면 -Z, 파트 45개 이하. c.P/c.S/c.A = 명소 주/보조/강조 색, c.M = 재질.
-- 하버 브리지(bridge) · 스카이타워(needle) · 12사도 바위(seastacks) · 그레이트 배리어 리프(reef) · 모아이(moai)
-- · 난마돌(ruins) · 무 대륙(island 의 mu 버전) 은 원래 그 명소를 위해 만든 모양을 그대로 씀.

return function(K)
	local B = {}

	local V, rgb, Mat, PI = K.V, K.rgb, K.Mat, K.PI
	local UPRIGHT, ALONG_Z = K.UPRIGHT, K.ALONG_Z
	local GRASS, LEAF, WATER, DARK = K.GRASS, K.LEAF, K.WATER, K.DARK
	local ROCK, WOOD, SAND, CLOUD, BLACK, WHITE = K.ROCK, K.WOOD, K.SAND, K.CLOUD, K.BLACK, K.WHITE
	local mix, block, box, ball, cyl, col, wedge, beam = K.mix, K.block, K.box, K.ball, K.cyl, K.col, K.wedge, K.beam
	local gable, plant, archCorner, facing = K.gable, K.plant, K.archCorner, K.facing

	-- a 에서 b 까지 이어지는 판: 가로 w(진행 방향의 오른쪽), 두께 t. a → b 는 수직이 아니어야 함
	local function slab(c, a, b, w, t, color, material)
		local mid = (a + b) / 2
		return block(c, CFrame.lookAt(mid, b), V(w, t, (b - a).Magnitude), color, material)
	end

	-- 세 점을 잇는 삼각형 판(직각 쐐기 두 개): 한 변(밑변)에 맞은편 꼭짓점에서 수선을 내려 둘로 나눔.
	--   쐐기의 경계 상자가 설계 공간(바닥 위, 10x10 안)에 들어가는 밑변을 고름
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

	-- 야자수: 기운 줄기 + 늘어진 잎 4장. (x, y, z) = 밑동, (dx, dz) = 기우는 방향
	local function palm(c, x, y, z, h, dx, dz, leaf)
		local top = V(x + dx, y + h, z + dz)
		beam(c, V(x, y, z), top, 0.24, WOOD, Mat.Wood)
		for k = 0, 3 do
			local angle = k * PI / 2 + 0.5
			local tip = top + V(math.cos(angle) * 1.15, -0.5, math.sin(angle) * 1.15)
			slab(c, top + V(0, 0.08, 0), tip, 0.42, 0.08, leaf, Mat.Grass)
		end
	end

	-- 네 삼각 면으로 된 뾰족한 봉우리(바닥 네 점 base, 꼭짓점 apex). 바닥 면은 없음
	local function pyramid(c, apex, base, color, material, thick)
		for k = 1, #base do
			tri(c, apex, base[k], base[k % #base + 1], color, material, thick or 0.25)
		end
	end

	-- cf(바닥 중앙) 기준 박공 능선: 길이 w(로컬 X), 폭 d(로컬 Z), 높이 h
	local function gableAt(c, cf, w, d, h, color, material)
		wedge(c, cf * CFrame.new(0, h / 2, -d / 4), V(w, h, d / 2), color, material)
		wedge(c, cf * CFrame.new(0, h / 2, d / 4) * CFrame.Angles(0, PI, 0), V(w, h, d / 2), color, material)
	end

	-- 모에라키 볼더스: 바다(앞) → 젖은 모래 경사 → 모래사장 → 낮은 흙 절벽(뒤, 풀).
	--   모래에 반쯤 묻힌 둥근 바위들(거북 등껍질 같은 밝은 금 = 바위를 두른 얇은 원판) + 파도 거품
	B.moeraki = function(c)
		local vein = mix(c.P, c.S, 0.62)
		local wet = mix(c.S, c.P, 0.4)
		local beachY = 0.7
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.A, Mat.Glass, 0.1)
		box(c, 0, 0, 1.6, 9.8, beachY, 6.6, c.S, Mat.Sand)
		wedge(c, CFrame.new(0, beachY / 2, -2.3), V(9.8, beachY, 1.2), wet, Mat.Sand)
		box(c, -0.4, 0.3, -3.15, 8.8, 0.05, 0.3, WHITE, Mat.SmoothPlastic, 0.15)
		box(c, 1, 0.3, -4.25, 6.4, 0.05, 0.25, WHITE, Mat.SmoothPlastic, 0.3)
		-- 뒤쪽 흙 절벽(높낮이 둘) + 풀
		local bank = mix(c.S, c.P, 0.55)
		box(c, 1.6, beachY, 4.45, 6.6, 1.3, 0.9, bank)
		box(c, -3.1, beachY, 4.3, 3.6, 2, 1.2, mix(bank, c.P, 0.3))
		box(c, 1.6, beachY + 1.3, 4.45, 6.6, 0.25, 0.9, GRASS, Mat.Grass)
		box(c, -3.1, beachY + 2, 4.3, 3.6, 0.25, 1.2, GRASS, Mat.Grass)
		-- 바위: { x, z, 지름, 모래 위(true)/물속(false), 금 방향 }
		local boulders = {
			{ -3, -1, 2.4, true, 0.3 },
			{ -0.6, -0.5, 2.6, true, -0.5 },
			{ 1.8, -1.4, 2.2, true, 0.9 },
			{ 3.8, -0.1, 1.9, true, -0.2 },
			{ 0.6, 1.9, 1.7, true, 0.6 },
			{ -3.2, 2.2, 1.5, true, 0 },
			{ -1.7, -3.5, 1.9, false, 1.1 },
			{ 2.6, -3.7, 1.6, false, -0.8 },
			{ 4.1, -2.6, 1.2, false, 0 },
		}
		for k, b in boulders do
			local x, z, d = b[1], b[2], b[3]
			local y = if b[4] then beachY + d * 0.25 else d / 2 + 0.02
			ball(c, x, y, z, d, c.P)
			if k <= 4 or k == 7 then
				local rot = CFrame.new(x, y, z) * CFrame.Angles(0, b[5], 0)
				cyl(c, rot * CFrame.Angles(0, 0, 0.35), 0.12, d + 0.1, vein)
				cyl(c, rot * CFrame.Angles(0, 1.7, 0) * CFrame.Angles(0, 0, -0.6), 0.12, d + 0.1, vein)
			end
		end
	end

	-- 플린더스 스트리트 역: 노란 벽 + 붉은 벽돌 띠의 긴 2층 역사, 왼쪽 모퉁이의 큰 초록 돔 파빌리온
	--   (큰 아치 창 + 입구 위 시계 줄), 오른쪽 끝 시계탑, 앞 도로의 초록 트램
	B.flindersst = function(c)
		local glass = rgb(52, 62, 78)
		local cream = mix(c.P, WHITE, 0.45)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, rgb(160, 158, 152), Mat.Concrete)
		box(c, 0, 0.2, -3.75, 9.8, 0.04, 2.1, rgb(72, 74, 80), Mat.Asphalt)
		-- 본관
		box(c, 0, 0.2, 1.3, 9.6, 3, 3.4, c.P)
		box(c, 0, 1.6, 1.3, 9.7, 0.22, 3.5, c.S)
		box(c, 0, 3.2, 1.3, 9.7, 0.3, 3.5, c.S)
		box(c, 0.85, 2, -0.43, 4, 0.9, 0.06, glass)
		box(c, 0.85, 0.45, -0.43, 4, 1, 0.06, glass)
		for _, x in { -0.3, 0.85, 2 } do
			box(c, x, 0.2, -0.46, 0.26, 3, 0.1, c.S)
		end
		-- 돔 파빌리온(왼쪽 모퉁이)
		local px, pz = -2.9, 0.3
		box(c, px, 0.2, pz, 3.4, 5, 3.4, c.P)
		for _, sx in { -1, 1 } do
			box(c, px + sx * 1.55, 0.2, pz - 1.55, 0.42, 5, 0.42, c.S)
		end
		local face = pz - 1.73
		box(c, px, 2.2, face, 1.8, 1.9, 0.06, glass)
		cyl(c, CFrame.new(px, 4.1, face) * ALONG_Z, 0.06, 1.8, glass)
		box(c, px, 0.2, face, 1.5, 1.1, 0.06, DARK)
		box(c, px, 1.45, face - 0.02, 2.3, 0.55, 0.06, c.S)
		for k = 0, 3 do
			cyl(c, CFrame.new(px - 0.84 + k * 0.56, 1.72, face - 0.08) * ALONG_Z, 0.06, 0.42, WHITE)
		end
		box(c, px, 5.2, pz, 3.8, 0.3, 3.8, c.S)
		col(c, px, 5.5, pz, 0.8, 2.8, cream)
		ball(c, px, 6.3, pz, 3, c.A, Mat.Metal)
		col(c, px, 7.6, pz, 0.8, 0.6, cream)
		ball(c, px, 8.55, pz, 0.45, c.A, Mat.Metal)
		-- 시계탑(오른쪽 끝)
		local tx = 3.8
		box(c, tx, 0.2, 0, 1.8, 7.3, 1.8, c.P)
		box(c, tx, 3, 0, 1.9, 0.3, 1.9, c.S)
		box(c, tx, 5.2, 0, 1.9, 0.3, 1.9, c.S)
		cyl(c, CFrame.new(tx, 6.35, -0.93) * ALONG_Z, 0.08, 1.1, WHITE)
		box(c, tx, 6.35, -0.99, 0.08, 0.45, 0.04, DARK)
		box(c, tx, 7.5, 0, 2.1, 0.3, 2.1, c.S)
		col(c, tx, 7.8, 0, 0.6, 1.3, cream)
		ball(c, tx, 8.1, 0, 1.3, c.A, Mat.Metal)
		col(c, tx, 8.7, 0, 0.6, 0.12, cream)
		-- 초록 트램
		local tram = rgb(46, 112, 74)
		box(c, 0.6, 0.24, -3.7, 3.4, 1.15, 1.1, tram, Mat.SmoothPlastic)
		box(c, 0.6, 0.35, -3.7, 3.45, 0.25, 1.15, rgb(236, 214, 150), Mat.SmoothPlastic)
		box(c, 0.6, 0.85, -3.7, 3.45, 0.35, 1.15, glass, Mat.SmoothPlastic)
		box(c, 0.6, 1.39, -3.7, 3, 0.15, 0.9, rgb(70, 70, 70), Mat.SmoothPlastic)
		beam(c, V(0.6, 1.54, -3.7), V(1.4, 2.4, -3.7), 0.06, DARK)
	end

	-- 팬케이크 바위: 바다 + 얇은 석회암 판을 겹겹이 쌓은 바위 무더기(무른 층은 들어가고 단단한 층은 튀어나옴)
	--   뒤쪽 곶은 네모난 판, 앞쪽 바위 기둥은 둥근 판(팬케이크 더미) + 바위 틈 분수공의 물보라 + 꼭대기 덤불
	B.pancakerocks = function(c)
		local seam = mix(c.S, BLACK, 0.1)
		local light = mix(c.P, WHITE, 0.2)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.A, Mat.Glass, 0.1)
		-- 어두운 심 + 튀어나온 밝은 판 n장. round 이면 둥근 판
		local function pancakes(x, z, w, d, h, n, yaw, round)
			if round then
				col(c, x, 0.3, z, h - 0.05, w * 0.78, seam)
			else
				block(
					c,
					CFrame.new(x, 0.3 + h / 2 - 0.03, z) * CFrame.Angles(0, yaw, 0),
					V(w * 0.8, h - 0.06, d * 0.8),
					seam
				)
			end
			local t = h / n
			for k = 0, n - 1 do
				local s = (1 - 0.05 * ((k * 7) % 3)) * (1 - k * 0.03)
				local y = 0.3 + (k + 1) * t - t * 0.29
				local dx = ((k * 5) % 3 - 1) * 0.08
				local color = if k % 2 == 0 then light else c.P
				if round then
					col(c, x + dx, y - t * 0.29, z - dx, t * 0.58, w * s, color)
				else
					local cf = CFrame.new(x + dx, y, z) * CFrame.Angles(0, yaw + (k % 3 - 1) * 0.07, 0)
					block(c, cf, V(w * s, t * 0.58, d * s), color)
				end
			end
		end
		pancakes(-1.3, 2.9, 7.1, 3.5, 5.4, 7, 0.04, false)
		pancakes(3, 0, 2.8, 2.6, 4.4, 6, 0, true)
		pancakes(-2.6, -1.5, 2.4, 2.4, 3.4, 5, 0, true)
		pancakes(0.8, -3.3, 1.6, 1.6, 1.9, 3, 0, true)
		-- 분수공 물보라
		local spray = mix(WHITE, c.A, 0.12)
		col(c, 0.1, 0.3, -0.5, 0.08, 2, WHITE, Mat.SmoothPlastic, 0.25)
		col(c, 0.1, 0.3, -0.5, 3.8, 0.8, spray, Mat.SmoothPlastic, 0.3)
		ball(c, 0.1, 4.3, -0.5, 1.7, spray, Mat.SmoothPlastic, 0.3)
		ball(c, -0.5, 5.1, -0.3, 1.3, spray, Mat.SmoothPlastic, 0.45)
		ball(c, 0.7, 4.9, -0.8, 1.1, spray, Mat.SmoothPlastic, 0.45)
		-- 덤불(아마 풀)
		ball(c, -3.4, 5.8, 3.3, 1.4, LEAF, Mat.Grass)
		ball(c, -1.3, 5.75, 3.8, 1.1, mix(LEAF, GRASS, 0.5), Mat.Grass)
		ball(c, 1.2, 5.7, 3.1, 1, LEAF, Mat.Grass)
		ball(c, 3, 4.75, 0.2, 0.9, mix(LEAF, GRASS, 0.5), Mat.Grass)
	end

	-- 캐시드럴 코브: 바다 + 오른쪽 모래사장(앞뒤로 이어짐) + 흰 석회암 곶을 뚫은 높고 뾰족한 동굴 아치
	--   + 곶 위 덤불과 포후투카와 나무 + 앞바다의 테호호 바위(뾰족한 바다 기둥)
	B.cathedralcove = function(c)
		local rock = c.P
		local shade = mix(c.P, ROCK, 0.3)
		local wet = mix(c.P, ROCK, 0.6)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		box(c, 1.6, 0, 0.3, 6.6, 0.45, 9.2, SAND, Mat.Sand)
		wedge(c, CFrame.new(1.6, 0.225, -4.6), V(6.6, 0.45, 0.6), SAND, Mat.Sand)
		wedge(c, CFrame.new(-2, 0.225, 0.3) * facing(-1, 0), V(9.2, 0.45, 0.6), SAND, Mat.Sand)
		-- 곶: 왼쪽·오른쪽 벽 + 아치 위 덩어리 + 뾰족한 아치 모서리
		local z, depth = 1.5, 3.8
		box(c, -0.9, 0.3, z, 2.6, 7.2, depth, rock)
		box(c, 3.85, 0.3, z, 2.1, 6.6, depth, rock)
		box(c, 1.6, 5.4, z, 2.4, 1.8, depth, rock)
		archCorner(c, 0.4, 5.4, z, 1.1, depth, rock, -1)
		archCorner(c, 2.8, 5.4, z, 1.1, depth, rock, 1)
		box(c, -0.9, 0.3, z, 2.7, 0.7, depth + 0.1, wet)
		wedge(c, CFrame.new(-2.9, 0.3 + 2.6, z + 0.2) * facing(-1, 0), V(depth - 0.4, 5.2, 1.4), shade)
		box(c, 3.85, 0.3, z, 2.2, 0.7, depth + 0.1, wet)
		block(c, CFrame.new(0.4, 7.4, 1.8) * CFrame.Angles(0, 0.08, 0.05), V(5, 1, 3.4), shade)
		block(c, CFrame.new(3.6, 7, 1.4) * CFrame.Angles(0, -0.1, -0.06), V(2.3, 1, 3.2), shade)
		box(c, 0.9, 7.85, 1.8, 5.6, 0.25, 3.2, c.A, Mat.Grass)
		plant(c, -0.8, 8.1, 2.2, 1.1, 1.6, mix(c.A, LEAF, 0.5))
		plant(c, 2.4, 8.1, 1.3, 0.9, 1.3, c.A)
		ball(c, 4, 7.9, 2.4, 1.2, mix(c.A, LEAF, 0.3), Mat.Grass)
		-- 테호호 바위: 앞바다에 선 뾰족한 바위(삼각 면 4개) + 꼭대기 덤불 + 물거품
		local hx, hz = -3.1, -2.5
		col(c, hx, 0.3, hz, 0.06, 3.4, WHITE, Mat.SmoothPlastic, 0.25)
		pyramid(c, V(hx + 0.5, 5.8, hz + 0.6), {
			V(hx - 1.5, 0.3, hz - 1),
			V(hx - 0.2, 0.3, hz - 1.6),
			V(hx + 1.4, 0.3, hz - 0.9),
			V(hx + 1.3, 0.3, hz + 1.3),
			V(hx - 1.3, 0.3, hz + 1.4),
		}, mix(rock, ROCK, 0.15))
		ball(c, hx + 0.45, 5.15, hz + 0.6, 1, c.A, Mat.Grass)
	end

	-- 힐리어 핑크 호수: 바다(짙은 파랑) + 얕은 물 + 해변 + 숲 덮인 섬 가운데의 분홍 타원 호수(흰 소금 테두리)
	--   + 호수와 바다를 가르는 좁은 숲 띠 + 뒤쪽 언덕
	B.lakehillier = function(c)
		local forest = c.S
		local deep = mix(c.S, BLACK, 0.25)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.A, Mat.Glass, 0.1)
		box(c, 0, 0.3, -3.3, 9.8, 0.04, 1.2, mix(c.A, WHITE, 0.45), Mat.Glass, 0.1)
		box(c, 0, 0, 1.6, 9.8, 1, 6.6, forest, Mat.Grass)
		box(c, 0, 0, -2.2, 9.8, 0.6, 1.2, SAND, Mat.Sand)
		box(c, 0, 0.3, -2.86, 9.8, 0.05, 0.25, WHITE, Mat.SmoothPlastic, 0.2)
		ball(c, 3.4, 1.35, 3.5, 2.7, deep, Mat.Grass)
		-- 호수: 원 3개를 겹친 타원(흰 테두리 → 분홍 물)
		local lakes = { { -2.2, 3.6 }, { 0, 4.4 }, { 2.2, 3.6 } }
		for _, l in lakes do
			col(c, l[1], 1, 1.2, 0.05, l[2] + 0.5, rgb(246, 240, 232), Mat.Sand)
		end
		for _, l in lakes do
			col(c, l[1], 1, 1.2, 0.1, l[2], c.P, Mat.SmoothPlastic)
		end
		-- 숲(나무 공): { x, z, 지름 }
		local trees = {
			{ -4.1, -1.1, 1.1 },
			{ -2.6, -1.2, 1.2 },
			{ -1, -1.25, 1 },
			{ 0.6, -1.2, 1.2 },
			{ 2.2, -1.25, 1 },
			{ 3.8, -1.1, 1.2 },
			{ -4.2, 1.8, 1.3 },
			{ 4.3, 1, 1.1 },
			{ -3.4, 4.1, 1.4 },
			{ -0.9, 4.2, 1.3 },
			{ 1.4, 4.1, 1.2 },
		}
		for k, t in trees do
			ball(c, t[1], 1 + t[3] * 0.3, t[2], t[3], if k % 2 == 0 then forest else deep, Mat.Grass)
		end
	end

	-- 웨이브 록: 붉은 흙 바닥 위, 앞(-Z)으로 말려드는 파도 모양 화강암 절벽.
	--   곡면은 세로 조각 5개 x 원호 토막 6개(조각마다 색이 달라 세로 줄무늬) + 발치의 경사 + 뒤쪽 바위 덩어리와 덤불
	B.waverock = function(c)
		local ground = rgb(186, 112, 70)
		box(c, 0, 0, 0, 9.8, 0.2, 9.8, ground, Mat.Ground)
		local zc, yc, R, T = -2.4, 4.33, 3.4, 0.75
		local a0, a1, segments = math.rad(8), math.rad(172), 6
		local tints = {
			c.P,
			mix(c.P, c.S, 0.4),
			mix(c.P, c.A, 0.35),
			mix(c.P, c.S, 0.6),
			mix(c.P, c.A, 0.12),
		}
		for i = 0, 4 do
			local x = -3.92 + i * 1.96
			local r = R + ((i * 3) % 4 - 1.5) * 0.05
			for k = 0, segments - 1 do
				local t1 = a0 + (a1 - a0) * k / segments
				local t2 = a0 + (a1 - a0) * (k + 1) / segments
				local tm = (t1 + t2) / 2
				local rm = r + T / 2
				local length = 2 * (r + T) * math.sin((t2 - t1) / 2) + 0.06
				local color = tints[i + 1]
				if k == 0 then
					color = mix(color, c.A, 0.4)
				elseif k == segments - 1 then
					color = mix(color, c.S, 0.25)
				end
				local cf = CFrame.new(x, yc - rm * math.cos(tm), zc + rm * math.sin(tm)) * CFrame.Angles(-tm, 0, 0)
				block(c, cf, V(1.98, T, length), color)
			end
		end
		wedge(c, CFrame.new(0, 0.2 + 0.4, -2.45), V(9.8, 0.8, 1.1), mix(c.P, c.A, 0.45))
		box(c, 0, 0.2, 3.15, 9.8, 7, 3.5, mix(c.P, c.S, 0.3))
		box(c, 0, 7, 2, 9.8, 1.5, 5.8, mix(c.P, c.S, 0.2))
		block(c, CFrame.new(0.4, 8.7, 2.9) * CFrame.Angles(0, 0, 0.03), V(8.4, 0.5, 3.6), mix(c.P, c.S, 0.45))
		ball(c, -3, 8.9, 3.6, 1.3, LEAF, Mat.Grass)
		ball(c, 2.6, 9, 3.8, 1.1, mix(LEAF, SAND, 0.2), Mat.Grass)
		ball(c, -4.1, 0.55, -4.1, 0.9, mix(LEAF, SAND, 0.3), Mat.Grass)
		ball(c, 3.9, 0.5, -4.2, 0.8, mix(LEAF, SAND, 0.3), Mat.Grass)
		-- 파도를 타는 사람(크기 비교)
		box(c, 1.6, 0.2, -3.3, 0.3, 0.8, 0.25, rgb(220, 60, 60), Mat.SmoothPlastic)
		ball(c, 1.6, 1.2, -3.3, 0.35, rgb(235, 195, 160), Mat.SmoothPlastic)
	end

	-- 팔라우 락 아일랜드: 옥색 석호 + 짙은 물길 + 흰 모래 여울 + 버섯 모양 섬들
	--   (물가가 파여 드러난 흰 석회암 밑동 위에 둥글게 덮인 밀림) + 카약
	B.rockislands = function(c)
		local lime = c.A
		local deepChannel = mix(c.S, rgb(20, 70, 150), 0.55)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		block(c, CFrame.new(0.4, 0.32, 0.2) * CFrame.Angles(0, 0.5, 0), V(1.6, 0.04, 9), deepChannel, Mat.Glass, 0.1)
		col(c, -2.4, 0.3, 2.4, 0.04, 4.4, mix(c.S, WHITE, 0.45), Mat.Sand)
		col(c, 2.6, 0.3, -1.6, 0.04, 3.2, mix(c.S, WHITE, 0.45), Mat.Sand)
		-- 섬: { x, z, 지름, 덧붙은 둥근 덩어리들 {dx, dz, 지름} }
		local islands = {
			{ -2.5, 2.3, 3.2, { { 1.5, 0.9, 2.4 }, { -0.8, -1.3, 2 } } },
			{ 2.6, 3, 2.8, { { -1.2, 0.6, 1.9 } } },
			{ 2.8, -1.5, 2.3, { { 0.8, 0.8, 1.5 } } },
			{ 0, 0, 1.9, {} },
			{ -2.9, -2.5, 1.7, {} },
			{ -0.6, -3.6, 1.2, {} },
			{ 4.1, 0.9, 1.2, {} },
			{ 1.1, -3.8, 0.9, {} },
		}
		for k, isle in islands do
			local x, z, d = isle[1], isle[2], isle[3]
			local green = if k % 2 == 0 then c.P else mix(c.P, LEAF, 0.4)
			-- 공 중심을 조금 띄워 물가에 파인 흰 밑동(지름 0.8d)이 드러나게
			local function dome(px, pz, pd, color)
				local y = pd / 2 + 0.25
				col(c, px, 0.3, pz, y - 0.3, pd * 0.8, lime, Mat.Limestone)
				ball(c, px, y, pz, pd, color, Mat.Grass)
			end
			dome(x, z, d, green)
			for _, lump in isle[4] do
				dome(x + lump[1], z + lump[2], lump[3], mix(green, BLACK, 0.12))
			end
		end
		block(c, CFrame.new(-1.8, 0.4, -1) * CFrame.Angles(0, 0.4, 0), V(0.35, 0.18, 1.4), rgb(250, 200, 40))
		block(c, CFrame.new(-1.8, 0.55, -1) * CFrame.Angles(0, 0.4 + PI / 2, 0.3), V(0.06, 0.06, 1.3), DARK)
	end

	-- 보라보라: 짙은 바다 + 옥빛 석호 + 둘레의 모투(모래 산호섬, 야자) + 가운데 초록 섬.
	--   가파른 초록 비탈(삼각 면 4개) 위에 깎아지른 검은 바위 봉우리 오테마누 + 옆의 파히아 산
	--   + 앞쪽 수상 방갈로(초가지붕) 줄과 나무 잔교
	B.borabora = function(c)
		local sand = c.A
		local thatch = rgb(190, 150, 90)
		local rock = mix(c.P, DARK, 0.6)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, rgb(25, 95, 175), Mat.Glass, 0.1)
		col(c, 0, 0, 0, 0.36, 9.6, c.S, Mat.Glass, 0.1)
		-- 모투: 각도(도)
		for k, deg in { -15, 30, 70, 110, 150, 195 } do
			local a = math.rad(deg)
			local p = V(4.2 * math.cos(a), 0.46, 4.2 * math.sin(a))
			local tangent = V(-math.sin(a), 0, math.cos(a))
			block(c, CFrame.lookAt(p, p + tangent), V(0.7, 0.25, 1.9), sand, Mat.Sand)
			if k % 2 == 1 then
				ball(c, p.X, 0.9, p.Z, 0.8, LEAF, Mat.Grass)
			end
		end
		-- 가운데 섬 + 오테마누
		col(c, 0.3, 0.3, 1.2, 0.35, 5.4, sand, Mat.Sand)
		col(c, 0.3, 0.3, 1.2, 0.85, 4.8, c.P, Mat.Grass)
		pyramid(c, V(0.5, 6.6, 1.5), {
			V(-1.3, 1.1, -0.4),
			V(2.1, 1.1, -0.3),
			V(2.1, 1.1, 3),
			V(-1.2, 1.1, 3),
		}, c.P, Mat.Grass)
		block(c, CFrame.new(0.55, 6, 1.5) * CFrame.Angles(0, 0.3, 0.04), V(1.9, 3.2, 1.6), rock, Mat.Basalt)
		block(c, CFrame.new(0.75, 7.75, 1.5) * CFrame.Angles(0, 0.3, 0.18), V(1.6, 0.8, 1.4), rock, Mat.Basalt)
		ball(c, -1.4, 2.3, 2.9, 2, mix(c.P, LEAF, 0.25), Mat.Grass)
		ball(c, -0.9, 3.3, 3.1, 1.3, mix(c.P, LEAF, 0.25), Mat.Grass)
		-- 수상 방갈로 + 잔교
		box(c, 0.4, 0.55, -2.55, 5.8, 0.1, 0.35, WOOD, Mat.Wood)
		box(c, 0.4, 0.55, -1.55, 0.35, 0.1, 2, WOOD, Mat.Wood)
		for _, x in { -1.9, -0.4, 1.1, 2.6 } do
			box(c, x, 0.3, -3.3, 0.95, 0.35, 0.95, WOOD, Mat.Wood)
			box(c, x, 0.65, -3.3, 0.8, 0.5, 0.8, rgb(215, 185, 140), Mat.Wood)
			gable(c, x, 1.15, -3.3, 1.05, 1.05, 0.55, thatch)
		end
	end

	-- 밀퍼드 사운드: 짙은 피오르 물 + 물에서 곧장 솟은 뾰족한 마이터 봉(삼각 면 4개, 꼭대기 눈)
	--   + 밑동 숲 + 오른쪽 뒤의 초록 산과 비탈을 흘러내리는 폭포(물보라) + 낮게 걸린 구름 + 유람선
	B.milfordsound = function(c)
		local rockColor = mix(c.P, ROCK, 0.75)
		local forest = mix(c.P, LEAF, 0.6)
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, c.S, Mat.Glass, 0.1)
		-- 마이터 봉 + 꼭대기 눈(같은 면을 바깥으로 조금 띄운 작은 삼각형)
		local apex = V(-1.2, 17, 1.1)
		local base = {
			V(-4.3, 0.3, -1.6),
			V(1.6, 0.3, -1.5),
			V(1.5, 0.3, 3.9),
			V(-4.4, 0.3, 3.7),
		}
		pyramid(c, apex, base, rockColor, Mat.Slate)
		local snowLine = 0.7
		for k = 1, 4 do
			local p1 = base[k] + (apex - base[k]) * snowLine
			local p2 = base[k % 4 + 1] + (apex - base[k % 4 + 1]) * snowLine
			local n = (p1 - apex):Cross(p2 - apex).Unit
			if n.Y < 0 then
				n = -n
			end
			tri(c, apex + n * 0.18, p1 + n * 0.18, p2 + n * 0.18, c.A, Mat.Snow, 0.12)
		end
		-- 오른쪽 뒤 산 + 폭포
		local peak = V(3.3, 10.5, 3.2)
		local foot = {
			V(1.6, 0.3, 0.3),
			V(4.6, 0.3, 0.3),
			V(4.6, 0.3, 4.6),
			V(1.4, 0.3, 4.6),
		}
		pyramid(c, peak, foot, forest, Mat.Grass)
		local edgeMid = (foot[1] + foot[2]) / 2
		local n = (foot[1] - peak):Cross(foot[2] - peak).Unit
		if n.Y < 0 then
			n = -n
		end
		local fallTop = edgeMid + (peak - edgeMid) * 0.62 + n * 0.2
		local fallFoot = edgeMid + n * 0.25 + V(0, 0.15, 0)
		beam(c, fallTop, fallFoot, 0.4, WHITE, Mat.SmoothPlastic, 0.1)
		ball(c, fallFoot.X, 0.85, fallFoot.Z - 0.1, 1.3, WHITE, Mat.SmoothPlastic, 0.35)
		-- 밑동 숲
		ball(c, -3.4, 1.1, -1.3, 1.8, forest, Mat.Grass)
		ball(c, -1.5, 1, -1.6, 1.6, mix(forest, LEAF, 0.3), Mat.Grass)
		ball(c, 0.6, 1.05, -1.4, 1.7, forest, Mat.Grass)
		ball(c, -4, 1.1, 1.2, 1.6, mix(forest, LEAF, 0.3), Mat.Grass)
		-- 구름
		ball(c, -3.4, 9.2, -0.2, 1.8, CLOUD, Mat.SmoothPlastic, 0.3)
		ball(c, 1.1, 8.3, -0.6, 1.4, CLOUD, Mat.SmoothPlastic, 0.35)
		ball(c, 3.2, 11.2, 2.4, 1.5, CLOUD, Mat.SmoothPlastic, 0.3)
		-- 유람선
		box(c, 1.2, 0.3, -3.5, 2.4, 0.45, 0.8, WHITE, Mat.SmoothPlastic)
		box(c, 1, 0.75, -3.5, 1.3, 0.45, 0.6, rgb(40, 60, 90), Mat.SmoothPlastic)
		col(c, 1.9, 0.75, -3.5, 0.6, 0.3, rgb(200, 50, 40), Mat.SmoothPlastic)
	end

	-- 킬라우에아: 바다 위 넓고 완만한 방패 화산(얇은 원판을 계단처럼) + 꼭대기 칼데라와 붉은 용암 호수
	--   + 바다로 흘러드는 용암 줄기와 김 기둥 + 화구의 화산 가스 + 옆구리 분석구의 용암 분수 + 비탈의 숲
	B.kilauea = function(c)
		local crust = mix(c.P, BLACK, 0.3)
		local lava = c.S
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, rgb(30, 110, 190), Mat.Glass, 0.1)
		local cx, cz = 0, 0.6
		local step = 0.35
		for k = 0, 6 do
			local d = 8.6 - k * 0.7
			col(c, cx, 0.3 + k * step, cz, step, d, if k % 2 == 0 then c.P else mix(c.P, crust, 0.5), Mat.Basalt)
		end
		local top = 0.3 + 7 * step
		-- 칼데라(어두운 바닥 + 둘레 턱) + 용암 호수
		col(c, cx, top, cz, 0.04, 3.6, crust, Mat.Basalt)
		for k = 0, 5 do
			local rot = CFrame.new(cx, 0, cz) * CFrame.Angles(0, k * PI / 3, 0)
			block(c, rot * CFrame.new(0, top + 0.2, -1.95), V(2.3, 0.4, 0.5), c.P, Mat.Basalt)
		end
		col(c, cx + 0.4, top, cz - 0.2, 0.1, 1.9, lava, Mat.Neon)
		ball(c, cx + 0.4, top + 0.1, cz - 0.2, 0.7, c.A, Mat.Neon)
		-- 용암 줄기(비탈을 따라 바다까지): 방향 각(정면 -Z 기준)
		local function surface(rho)
			return 0.3 + (4.3 - rho) + step
		end
		for _, flow in { { 0.25, 5.1 }, { -0.8, 4.2 } } do
			local dir = V(math.sin(flow[1]), 0, -math.cos(flow[1]))
			local p1 = V(cx, 0, cz) + dir * 2.2 + V(0, surface(2.2), 0)
			local p2 = V(cx, 0, cz) + dir * 4.3 + V(0, surface(4.3) - 0.1, 0)
			beam(c, p1, p2, 0.36, lava, Mat.Neon)
			local p3 = V(cx, 0, cz) + dir * flow[2] + V(0, 0.4, 0)
			beam(c, p2, p3, 0.3, lava, Mat.Neon)
		end
		-- 바다에 닿은 곳: 용암 삼각주 + 김 기둥
		local entry = V(cx, 0, cz) + V(math.sin(0.25), 0, -math.cos(0.25)) * 4.9
		box(c, entry.X, 0.3, entry.Z, 1.4, 0.12, 0.7, lava, Mat.Neon)
		ball(c, entry.X + 0.2, 1.3, entry.Z + 0.1, 1.5, WHITE, Mat.SmoothPlastic, 0.35)
		ball(c, entry.X + 0.7, 2.5, entry.Z + 0.4, 1.8, WHITE, Mat.SmoothPlastic, 0.45)
		ball(c, entry.X + 1.3, 3.8, entry.Z + 0.7, 1.6, WHITE, Mat.SmoothPlastic, 0.55)
		-- 화산 가스
		local gas = rgb(215, 210, 205)
		ball(c, cx + 0.5, top + 1.5, cz + 0.1, 1.8, gas, Mat.SmoothPlastic, 0.3)
		ball(c, cx + 0.9, top + 3, cz + 0.5, 2.2, gas, Mat.SmoothPlastic, 0.4)
		ball(c, cx + 1.5, top + 4.7, cz + 0.9, 2.5, gas, Mat.SmoothPlastic, 0.5)
		-- 분석구(푸우오오) + 용암 분수
		local vx, vz = 2.8, 0.9
		col(c, vx, 1.9, vz, 0.5, 1.4, crust, Mat.Basalt)
		col(c, vx, 2.4, vz, 0.35, 0.9, crust, Mat.Basalt)
		col(c, vx, 2.7, vz, 1.2, 0.25, lava, Mat.Neon)
		ball(c, vx, 3.9, vz, 0.55, c.A, Mat.Neon)
		-- 비탈의 숲
		ball(c, -2.6, 1.4, 3.2, 1.2, LEAF, Mat.Grass)
		ball(c, -3.5, 1, 1.4, 1, mix(LEAF, GRASS, 0.4), Mat.Grass)
		ball(c, -1.2, 1.3, 3.9, 1, LEAF, Mat.Grass)
	end

	-- 와이토모 반딧불이 동굴: 풀 언덕(양 한 마리, 싱크홀) 아래로 뚫린 넓은 동굴 입구.
	--   어두운 동굴 벽을 수놓은 청록 반딧불이 점 + 천장에서 늘어진 빛나는 실 + 종유석 + 동굴 강의 나무배
	B.waitomo = function(c)
		local rock = c.P
		local dark = c.S
		local glow = c.A
		local lime = mix(c.P, WHITE, 0.4)
		local mouthZ, backZ, top = -1.2, 2.4, 5.6
		box(c, 0, 0, 0, 9.8, 0.3, 9.8, rock)
		box(c, 0, 0.3, (backZ + 4.9) / 2, 6.4, top - 0.3, 4.9 - backZ, dark)
		-- 양옆: 바깥으로 비탈진 수풀 언덕(안쪽 면은 곧은 동굴 벽)
		local hillH = top + 1.2 - 0.3
		for _, sx in { -1, 1 } do
			local cf = CFrame.new(sx * 4.05, 0.3 + hillH / 2, (mouthZ + 4.9) / 2) * facing(sx, 0)
			wedge(c, cf, V(4.9 - mouthZ, hillH, 1.7), mix(GRASS, rock, 0.35), Mat.Grass)
			box(c, sx * 3.18, 0.3, (mouthZ + backZ) / 2, 0.06, top - 0.3, backZ - mouthZ, dark)
		end
		box(c, 0, top, 1.6, 6.4, 1.2, 6.6, rock)
		box(c, 0, top + 1.2, 1.6, 6.4, 0.3, 6.6, GRASS, Mat.Grass)
		ball(c, -1.9, top + 1.4, 2.8, 2.6, GRASS, Mat.Grass)
		ball(c, 2, top + 1.3, 3.4, 2.4, mix(GRASS, LEAF, 0.3), Mat.Grass)
		col(c, 0.9, top + 1.5, 1, 0.05, 1.3, DARK)
		box(c, -0.8, top + 1.5, -0.8, 0.7, 0.45, 0.45, WHITE, Mat.SmoothPlastic)
		box(c, -1.2, top + 1.75, -0.8, 0.25, 0.3, 0.25, DARK)
		-- 동굴 강 + 나무배
		box(c, 0.3, 0.3, -1.6, 2.8, 0.06, 6.6, mix(dark, WATER, 0.4), Mat.Glass, 0.15)
		box(c, 0.3, 0.3, -1, 1.1, 0.35, 2, WOOD, Mat.Wood)
		ball(c, 0.3, 0.9, -1.4, 0.42, rgb(230, 190, 160), Mat.SmoothPlastic)
		ball(c, 0.3, 0.9, -0.6, 0.42, rgb(230, 190, 160), Mat.SmoothPlastic)
		-- 둥글게 깎인 입구 모서리 + 입구의 바위
		archCorner(c, -3.15, top, (mouthZ + backZ) / 2, 1.2, backZ - mouthZ, mix(rock, dark, 0.4), -1)
		archCorner(c, 3.15, top, (mouthZ + backZ) / 2, 1.2, backZ - mouthZ, mix(rock, dark, 0.4), 1)
		ball(c, -2.9, 0.75, -1.6, 1.2, rock)
		ball(c, 3.1, 0.65, -1.9, 1, rock)
		-- 종유석(입구 천장)
		for k, x in { -1.6, -0.6, 1.6 } do
			local h = 0.5 + (k % 2) * 0.35
			col(c, x, top - h, -1.45, h, 0.3, lime)
		end
		-- 반딧불이 점: 뒷벽 { x, y } + 옆벽
		local dots = {
			{ -2.6, 3.9 },
			{ -1.7, 2.8 },
			{ -0.8, 3.6 },
			{ 0.2, 2.4 },
			{ 1, 3.9 },
			{ 1.9, 2.9 },
			{ 2.7, 3.7 },
			{ -2.2, 1.8 },
			{ 2.4, 1.6 },
			{ -0.4, 1.4 },
		}
		for _, d in dots do
			ball(c, d[1], d[2], backZ - 0.05, 0.32, glow, Mat.Neon)
		end
		for _, sx in { -1, 1 } do
			ball(c, sx * 3.12, 3.4, 0.2, 0.3, glow, Mat.Neon)
			ball(c, sx * 3.12, 2.2, 1.4, 0.3, glow, Mat.Neon)
		end
		-- 늘어진 빛 실
		for _, t in { { -2.2, -0.4, 1.4 }, { -1, 0.8, 1 }, { 0.2, -0.7, 1.6 }, { 1.4, 0.5, 1.2 }, { 2.4, -0.2, 1.5 } } do
			box(c, t[1], top - t[3], t[2], 0.07, t[3], 0.07, glow, Mat.Neon, 0.3)
		end
	end

	-- 얍섬 돌 화폐(라이): 풀밭 + 돌길 + 길가에 세워 둔 가운데 구멍 뚫린 거대한 돌 원판들(크기 제각각, 뒤로 살짝 기댐)
	--   + 가장 큰 돌의 구멍을 꿴 나무 장대 + 바닥에 누운 돌 + 야자수
	B.yapstone = function(c)
		local stone = c.P
		local grass = mix(c.A, BLACK, 0.1)
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, grass, Mat.Grass)
		box(c, 0, 0.25, -1.2, 9.8, 0.1, 1.8, mix(c.S, WHITE, 0.2), Mat.Slate)
		local function rai(x, z, d, yaw, lean)
			local t = math.max(0.35, d * 0.13)
			local cf = CFrame.new(x, 0.3 + d / 2, z) * CFrame.Angles(0, yaw, 0) * CFrame.Angles(lean, 0, 0)
			cyl(c, cf * ALONG_Z, t, d, stone)
			cyl(c, cf * ALONG_Z, t + 0.06, d * 0.24, DARK)
			return cf
		end
		local big = rai(-2.5, 0.8, 4.2, 0.12, 0.1)
		rai(1.1, 1.2, 3.2, -0.15, 0.08)
		rai(3.6, 1.6, 2.4, 0.25, 0.1)
		rai(-0.6, 3.5, 2.6, 0.3, 0.06)
		rai(2.5, 3.9, 1.8, -0.2, 0.05)
		rai(-4.1, -3, 1.2, 0.4, 0.05)
		beam(c, big.Position - big.LookVector * 1.4, big.Position + big.LookVector * 1.4, 0.2, WOOD, Mat.Wood)
		-- 누운 돌
		cyl(c, CFrame.new(1.6, 0.53, -3.2) * UPRIGHT, 0.36, 2, stone)
		cyl(c, CFrame.new(1.6, 0.53, -3.2) * UPRIGHT, 0.42, 0.5, DARK)
		palm(c, -4.2, 0.25, 3.9, 4.6, 0.5, -0.5, LEAF)
		palm(c, 4.1, 0.25, -3.8, 3.8, -0.5, 0.4, mix(LEAF, GRASS, 0.3))
		palm(c, 4.3, 0.25, 4.3, 3.4, -0.6, -0.6, LEAF)
		ball(c, -1.3, 0.55, -3.9, 1, mix(LEAF, GRASS, 0.4), Mat.Grass)
	end

	-- 질랜디아: 짙은 해저 + 물에 잠긴 긴 대륙(등고선처럼 두 단, 단마다 가장자리가 청록으로 빛남) + 반투명 바다
	--   + 물 위로 나온 뉴질랜드(북섬의 설산 화산, 남섬의 눈 덮인 남알프스) + 뉴칼레도니아 + 채텀 제도 + 탐사선
	B.zealandia = function(c)
		local glow = c.A
		local yaw = -0.67
		box(c, 0, 0, 0, 9.8, 0.25, 9.8, mix(c.S, BLACK, 0.35), Mat.Slate)
		-- 대지: { x, z, 가로, 세로, 비틀기 }, 단마다 { 바닥, 높이, 색 }
		local tiers = {
			{
				0.25,
				0.8,
				mix(c.P, c.S, 0.35),
				{
					{ -2.3, 2.6, 2, 3.8, 0 },
					{ -0.7, 0.7, 3.6, 4.6, 0 },
					{ 1.3, -1.4, 3.4, 4.2, 0.05 },
					{ 2.6, -3.3, 3, 2.2, 0.45 },
				},
			},
			{
				1.05,
				0.55,
				c.P,
				{
					{ -2.2, 2.5, 1.1, 2.8, 0 },
					{ -0.4, 0.4, 2.2, 3.4, 0.1 },
					{ 1.3, -1.3, 2.2, 3.4, 0 },
				},
			},
		}
		for _, tier in tiers do
			local y0, h, color = tier[1], tier[2], tier[3]
			for _, p in tier[4] do
				local cf = CFrame.new(p[1], y0 + h / 2, p[2]) * CFrame.Angles(0, yaw + p[5], 0)
				block(c, cf * CFrame.new(0, -0.08, 0), V(p[3] + 0.28, h - 0.16, p[4] + 0.28), glow, Mat.Neon)
				block(c, cf, V(p[3], h, p[4]), color, Mat.Slate)
			end
		end
		box(c, 0, 0.25, 0, 9.8, 2.1, 9.8, mix(c.S, WATER, 0.5), Mat.Glass, 0.6)
		-- 물 위의 섬들
		local function isle(x, z, w, h, d, turn, color)
			block(c, CFrame.new(x, 1.6 + h / 2, z) * CFrame.Angles(0, turn, 0), V(w, h, d), color, Mat.Grass)
		end
		isle(2, 0.1, 1.2, 1.2, 2.4, -0.55, GRASS)
		isle(1.3, 1.5, 0.6, 1, 1.6, -0.9, GRASS)
		isle(0.6, -2.2, 1.4, 0.9, 3.4, -0.7, mix(GRASS, LEAF, 0.4))
		isle(-2.8, 3.1, 0.6, 0.85, 2.4, -0.9, GRASS)
		isle(4.1, -1, 0.7, 0.85, 0.6, 0, GRASS)
		isle(-0.6, -3.8, 0.6, 0.85, 0.5, 0, GRASS)
		-- 루아페후 화산(원뿔 + 눈) + 남섬 등줄기의 눈 덮인 남알프스(박공 능선)
		col(c, 2.1, 2.8, 0, 0.3, 0.95, ROCK)
		col(c, 2.1, 3.1, 0, 0.3, 0.6, ROCK)
		col(c, 2.1, 3.4, 0, 0.18, 0.3, WHITE, Mat.Snow)
		local alps = CFrame.new(0.6, 2.5, -2.2) * CFrame.Angles(0, -0.7, 0) * CFrame.Angles(0, PI / 2, 0)
		gableAt(c, alps, 3.4, 1.4, 0.9, mix(GRASS, LEAF, 0.4), Mat.Grass)
		gableAt(c, alps * CFrame.new(0, 0.49, 0), 2.6, 0.72, 0.45, WHITE, Mat.Snow)
		-- 탐사선
		box(c, -2.6, 2.35, -2.2, 1.6, 0.35, 0.6, WHITE, Mat.SmoothPlastic)
		box(c, -2.9, 2.7, -2.2, 0.6, 0.4, 0.45, rgb(220, 70, 50), Mat.SmoothPlastic)
	end

	return B
end
