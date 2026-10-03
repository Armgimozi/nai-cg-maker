-- 균형 내관(혼원지의, 금단 응결, 연단) 난이도 시뮬레이션.   실행: lune run tools/sim/balance
-- 사람처럼 늦게 보고(0.25초), 막대 하나만 누르고, 옮길 때 0.15초 쓰는 손으로 몇 초 만에 끝내는지 잰다.
-- 설정 a 가 지금 게임 값(src/client/Naegwan.luau playBalance)이다. 사람은 이 손보다 서투르니 여유를 둔다.
local function rng(seed)
	local state = seed
	return function()
		state = (state * 16807) % 2147483647
		return state / 2147483647
	end
end

local function simulate(cfg, count, band, turbulence, seed)
	local rand = rng(seed)
	local halfBand = math.min(cfg.cap, cfg.half * band)
	local fall = (cfg.fall + cfg.fallTurb * turbulence) / (if cfg.scaleFall then math.sqrt(count) else 1)
	local bars = {}
	for i = 1, count do
		local center = 0.35 + rand() * 0.35
		bars[i] = { value = center, center = center, phase = rand() * 6.28, speed = 1.2 + rand() * 1.4 }
	end
	local dt = 1 / 60
	local held, clock = 0, 0
	local holding = nil
	local switchUntil = 0
	local history = {}
	local REACT = 0.25
	while clock < 90 do
		clock += dt
		-- 늦게 본 상태
		table.insert(
			history,
			{
				t = clock,
				values = (function()
					local v = {}
					for i, b in bars do
						v[i] = b.value
					end
					return v
				end)(),
			}
		)
		local seen = history[1].values
		while #history > 1 and history[2].t <= clock - REACT do
			table.remove(history, 1)
			seen = history[1].values
		end
		-- 판단: 지금 누르는 막대가 띠 위쪽 근처까지 왔으면 놓고, 가장 많이 처진 막대로 옮긴다
		if holding and seen[holding] >= bars[holding].center + 0.1 * halfBand then
			holding = nil
		end
		if not holding then
			local worst, deficit = nil, 0
			for i, b in bars do
				local d = b.center - seen[i]
				if d > 0.35 * halfBand and d > deficit then
					worst, deficit = i, d
				end
			end
			if worst then
				holding = worst
				switchUntil = clock + 0.15
			end
		end
		local allIn = true
		for i, b in bars do
			local drift = math.sin(clock * b.speed + b.phase) * cfg.drift * turbulence
			local push = if holding == i and clock >= switchUntil then cfg.rise else -fall
			b.value = math.clamp(b.value + (push + drift) * dt, 0, 1)
			if math.abs(b.value - b.center) > halfBand then
				allIn = false
			end
		end
		if allIn then
			held += dt
		else
			held = math.max(0, held - dt * cfg.decay)
		end
		if held >= cfg.target then
			return clock
		end
	end
	return nil
end

local CONFIGS = {
	a = {
		half = 0.13,
		cap = 0.28,
		rise = 0.35,
		fall = 0.1,
		fallTurb = 0.03,
		drift = 0.05,
		decay = 0,
		target = 15,
		scaleFall = true,
	},
	old = {
		half = 0.1,
		cap = 0.24,
		rise = 0.5,
		fall = 0.11,
		fallTurb = 0.03,
		drift = 0.06,
		decay = 0.5,
		target = 20,
		scaleFall = false,
	},
}
for _, name in { "a", "old" } do
	print("== " .. name)
	for _, case in { { 1, 1.0 }, { 2, 1.1 }, { 3, 1.1 }, { 4, 1.3 }, { 5, 1.3 } } do
		for _, turbulence in { 0.8, 1.7 } do
			local ok, total, worst = 0, 0, 0
			for seed = 1, 60 do
				local t = simulate(CONFIGS[name], case[1], case[2], turbulence, seed * 7919)
				if t then
					ok += 1
					total += t
					worst = math.max(worst, t)
				end
			end
			print(
				string.format(
					"  막대 %d 판정 %.1f 흔들림 %.1f: 성공 %d/60, 평균 %s초, 가장 오래 %.0f초",
					case[1],
					case[2],
					turbulence,
					ok,
					if ok > 0 then string.format("%.0f", total / ok) else "-",
					worst
				)
			)
		end
	end
end
