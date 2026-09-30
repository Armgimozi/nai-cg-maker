-- 밸런스 시뮬레이터(tools/balance/sim.py)용: 게임의 실제 Luau 모듈을 그대로 불러서 JSON 으로 내보냅니다.
-- 게임 코드는 읽기만 합니다(tests/harness.luau 의 가짜 require 사용).
--
-- 사용법 (roblox-rng 폴더에서):
--   tools/luaurun/target/release/luaurun tools/balance/dump.luau config
--       -> Config + Landmarks(등급·대륙 포함) JSON
--   tools/luaurun/target/release/luaurun tools/balance/dump.luau validate [상태 수] [굴림 수]
--       -> 무작위 플레이어 상태마다 PlayerState.luck / cooldown / incomePerSecond / slots / completedRegions
--          + RollLogic.probabilities + RollLogic.roll 몬테카를로 횟수 (sim.py --check 가 파이썬 공식과 대조)

local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()
local shared = Harness.folder("src/shared")
local Config = Harness.require(shared.Config)
local Landmarks = Harness.require(shared.Landmarks)
local RollLogic = Harness.require(shared.RollLogic)
local PlayerState = Harness.require(shared.PlayerState)

-- 아주 작은 JSON 인코더 ------------------------------------------------------
local encode

local function encodeString(s: string): string
	local escaped = s:gsub('[%c"\\]', function(c)
		if c == '"' then
			return '\\"'
		elseif c == "\\" then
			return "\\\\"
		elseif c == "\n" then
			return "\\n"
		end
		return string.format("\\u%04x", string.byte(c))
	end)
	return '"' .. escaped .. '"'
end

local function isArray(t): boolean
	local n = #t
	local count = 0
	for _ in t do
		count += 1
	end
	return count == n
end

function encode(v: any): string
	local kind = type(v)
	if v == nil then
		return "null"
	elseif kind == "boolean" then
		return tostring(v)
	elseif kind == "number" then
		if v ~= v or v == math.huge or v == -math.huge then
			return "null"
		end
		return string.format("%.17g", v)
	elseif kind == "string" then
		return encodeString(v)
	elseif kind == "table" then
		if isArray(v) then
			local parts = {}
			for _, item in ipairs(v) do
				table.insert(parts, encode(item))
			end
			return "[" .. table.concat(parts, ",") .. "]"
		end
		local keys = {}
		for key in v do
			table.insert(keys, tostring(key))
		end
		table.sort(keys)
		local parts = {}
		for _, key in keys do
			table.insert(parts, encodeString(key) .. ":" .. encode(v[key]))
		end
		return "{" .. table.concat(parts, ",") .. "}"
	end
	error("JSON 으로 못 바꾸는 값: " .. kind)
end

-- config ---------------------------------------------------------------------
local function dumpConfig()
	local upgrades = {}
	local order = {}
	for _, u in Config.Upgrades do
		table.insert(order, u.Id)
		upgrades[u.Id] = { base_price = u.BasePrice, growth = u.Growth, max_level = u.MaxLevel, per_level = u.PerLevel }
	end
	local rebirths = {}
	for _, step in Config.REBIRTHS do
		table.insert(rebirths, { coins = step.Coins, landmarks = step.Landmarks })
	end
	local passes = {}
	for _, pass in Config.GamePasses do
		passes[pass.Id] = {
			luck_mult = pass.LuckMult or 1,
			cooldown_mult = pass.CooldownMult or 1,
			income_mult = pass.IncomeMult or 1,
		}
	end
	local products = {}
	for _, product in Config.Products do
		products[product.Id] = {
			seconds = product.Seconds or 0,
			luck_mult = product.LuckMult or 1,
			server_wide = product.ServerWide == true,
			income_seconds = product.IncomeSeconds or 0,
			min_coins = product.MinCoins or 0,
		}
	end
	local tiers = {}
	for _, tier in Landmarks.Tiers do
		table.insert(tiers, { rank = tier.Rank, name = tier.Name, min_one_in = tier.MinOneIn })
	end
	local regions = {}
	for _, region in Landmarks.Regions do
		table.insert(regions, region.Id)
	end
	-- 정의 순서가 아니라 흔한 것 -> 희귀한 것(Landmarks.List). sim.py 가 다시 희귀한 순서로 정렬
	local landmarks = {}
	for _, lm in Landmarks.List do
		table.insert(landmarks, { id = lm.Id, name = lm.Name, one_in = lm.OneIn, region = lm.Region, rank = lm.Tier.Rank })
	end
	return {
		source = "luaurun",
		roll_cooldown = Config.ROLL_COOLDOWN,
		cooldown_tolerance = Config.COOLDOWN_TOLERANCE,
		base_luck = Config.BASE_LUCK,
		announce_one_in = Config.ANNOUNCE_ONE_IN,
		hologram_one_in = Config.HOLOGRAM_ONE_IN,
		discovery_bonus_mult = Config.DISCOVERY_BONUS_MULT,
		base_slots = Config.BASE_SLOTS,
		park_grid = Config.PARK_GRID,
		tier_income = Config.TIER_INCOME,
		star_thresholds = Config.STAR_THRESHOLDS,
		star_income_bonus = Config.STAR_INCOME_BONUS,
		stamp_max_rank = Config.STAMP_MAX_RANK,
		region_luck_bonus = Config.REGION_LUCK_BONUS,
		upgrades = upgrades,
		upgrade_order = order,
		rebirths = rebirths,
		max_rebirths = Config.MAX_REBIRTHS,
		rebirth_luck = { type = "linear", per = Config.REBIRTH_LUCK_BONUS },
		rebirth_income = { type = "linear", per = Config.REBIRTH_INCOME_BONUS },
		passes = passes,
		products = products,
		max_boost_seconds = Config.MAX_BOOST_SECONDS,
		tiers = tiers,
		regions = regions,
		landmarks = landmarks,
	}
end

-- validate ---------------------------------------------------------------------
-- 결정적인 난수(LCG) — 파이썬 쪽은 이 상태들을 그대로 받아서 다시 계산만 함
local seed = 987654321
local function rand(): number
	seed = (seed * 1103515245 + 12345) % 2147483648
	return seed / 2147483648
end
local function randInt(lo: number, hi: number): number
	return lo + math.floor(rand() * (hi - lo + 1))
end

local function randomState(index: number)
	local data = PlayerState.new()
	data.Rebirths = randInt(0, Config.MAX_REBIRTHS)
	for _, upgrade in Config.Upgrades do
		data.Upgrades[upgrade.Id] = randInt(0, upgrade.MaxLevel)
	end
	-- 희귀할수록 덜 가짐. 몇몇 상태는 대륙 몇 개를 도장 조건까지 전부 발견
	local reach = 10 ^ (1 + rand() * 5)
	local fullRegions = {}
	if index % 3 == 0 then
		for _, region in Landmarks.Regions do
			if rand() < 0.5 then
				fullRegions[region.Id] = true
			end
		end
	end
	for _, lm in Landmarks.List do
		if rand() < math.min(1, reach / lm.OneIn) then
			data.Inventory[lm.Id] = randInt(1, 150)
			data.Discovered[lm.Id] = true
		elseif rand() < 0.3 * math.min(1, reach / lm.OneIn) then
			data.Discovered[lm.Id] = true -- 예전 판에 발견
		end
		if fullRegions[lm.Region] and PlayerState.countsForStamp(lm) then
			data.Discovered[lm.Id] = true
		end
	end
	local mods = { Passes = {}, ServerLuck = rand() < 0.3 }
	for _, pass in Config.GamePasses do
		if rand() < 0.5 then
			mods.Passes[pass.Id] = true
		end
	end
	for _, product in Config.Products do
		if product.Seconds and not product.ServerWide and rand() < 0.4 then
			data.Boosts[product.Id] = 100
		end
	end
	return data, mods
end

local function dumpValidate(stateCount: number, rollCount: number)
	local states = {}
	for i = 1, stateCount do
		local data, mods = randomState(i)
		local park = PlayerState.park(data)
		table.insert(states, {
			rebirths = data.Rebirths,
			upgrades = data.Upgrades,
			inventory = data.Inventory,
			discovered = data.Discovered,
			boosts = data.Boosts,
			passes = mods.Passes,
			server_luck = mods.ServerLuck,
			luck = PlayerState.luck(data, mods),
			cooldown = PlayerState.cooldown(data, mods),
			income = PlayerState.incomePerSecond(data, mods),
			slots = PlayerState.slots(data),
			park = park,
			completed_regions = PlayerState.completedRegions(data),
		})
	end
	local probabilities = {}
	for _, luck in { 1, 3.7, 50, 1234, 250000 } do
		table.insert(probabilities, { luck = luck, p = RollLogic.probabilities(Landmarks.RarestFirst, luck) })
	end
	local monteCarlo = {}
	math.randomseed(20260930)
	for _, luck in { 1, 20 } do
		local counts = {}
		for _ = 1, rollCount do
			local lm = RollLogic.roll(Landmarks.RarestFirst, luck, math.random)
			counts[lm.Id] = (counts[lm.Id] or 0) + 1
		end
		table.insert(monteCarlo, { luck = luck, rolls = rollCount, counts = counts })
	end
	local bonus = {}
	for _, lm in Landmarks.List do
		bonus[lm.Id] = PlayerState.discoveryBonus(lm)
	end
	return { states = states, probabilities = probabilities, monte_carlo = monteCarlo, discovery_bonus = bonus }
end

local mode = ARGS[1] or "config"
if mode == "config" then
	print(encode(dumpConfig()))
elseif mode == "validate" then
	print(encode(dumpValidate(tonumber(ARGS[2]) or 40, tonumber(ARGS[3]) or 200000)))
else
	error("모드: config | validate")
end
