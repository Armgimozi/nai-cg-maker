-- 사용법 (roblox-rng 폴더에서): luaurun tests/run.luau
-- 1) src 아래 모든 .luau 파일이 문법적으로 컴파일되는지 확인
-- 2) src/shared 순수 모듈 단위 테스트 + 확률 몬테카를로 검증

local Harness = compile(readfile("tests/harness.luau"), "tests/harness.luau")()
local test, eq, near = Harness.test, Harness.eq, Harness.near

print("[compile]")
local function compileTree(dir)
	for _, name in listdir(dir) do
		local path = dir .. "/" .. name
		if name:match("%.luau$") then
			test(path, function()
				compile(readfile(path), path)
			end)
		elseif not name:find("%.") then
			compileTree(path)
		end
	end
end
compileTree("src")

local shared = Harness.folder("src/shared")
local Config = Harness.require(shared.Config)
local Auras = Harness.require(shared.Auras)
local RollLogic = Harness.require(shared.RollLogic)
local PlayerState = Harness.require(shared.PlayerState)
local Format = Harness.require(shared.Format)

print("\n[Auras]")
test("Id 중복 없음 + OneIn 정상", function()
	local seen = {}
	for _, aura in Auras.List do
		assert(not seen[aura.Id], "중복 " .. aura.Id)
		seen[aura.Id] = true
		assert(aura.OneIn >= 1, aura.Id .. " OneIn < 1")
		assert(Auras.ById[aura.Id] == aura)
	end
end)
test("RarestFirst 는 내림차순, 마지막은 Common", function()
	for i = 2, #Auras.RarestFirst do
		assert(Auras.RarestFirst[i - 1].OneIn >= Auras.RarestFirst[i].OneIn, "정렬 깨짐 at " .. i)
	end
	eq(Auras.RarestFirst[#Auras.RarestFirst], Auras.Common, "마지막")
	eq(Auras.Common.Id, "common", "Common Id")
end)
test("등급 경계", function()
	eq(Auras.ById.common.Tier.Name, "일반")
	eq(Auras.ById.ember.Tier.Name, "고급")
	eq(Auras.ById.bloom.Tier.Name, "희귀")
	eq(Auras.ById.moonlight.Tier.Name, "에픽")
	eq(Auras.ById.crystal.Tier.Name, "전설")
	eq(Auras.ById.stardust.Tier.Name, "신화")
	eq(Auras.ById.celestial.Tier.Name, "초월")
end)

print("\n[RollLogic]")
local function sum(t)
	local s = 0
	for _, v in t do
		s += v
	end
	return s
end

test("확률 합계 = 1 (여러 행운)", function()
	for _, luck in { 1, 1.5, 2, 10, 1000, 1e9 } do
		near(sum(RollLogic.probabilities(Auras.RarestFirst, luck)), 1, 1e-9, "luck " .. luck)
	end
end)
test("행운 1 에서 희귀 오라 확률 ≈ 1/N", function()
	local probs = RollLogic.probabilities(Auras.RarestFirst, 1)
	for _, aura in Auras.List do
		if aura.OneIn >= 1000 then
			local p = probs[aura.Id]
			near(p * aura.OneIn, 1, 0.01, aura.Id .. " p*N")
		end
	end
end)
test("행운 2 면 희귀 확률 ≈ 2배", function()
	local p1 = RollLogic.probabilities(Auras.RarestFirst, 1)
	local p2 = RollLogic.probabilities(Auras.RarestFirst, 2)
	near(p2.celestial / p1.celestial, 2, 0.01, "celestial 배율")
	near(p2.crystal / p1.crystal, 2, 0.01, "crystal 배율")
end)
test("행운 ≥ N 이면 더 흔한 오라는 안 나옴", function()
	local probs = RollLogic.probabilities(Auras.RarestFirst, 8)
	eq(probs.common, 0, "common")
	eq(probs.breeze, 0, "breeze")
	-- dew(1/8) 는 행운 8 에서 확정이므로, 더 희귀한 오라가 전부 실패할 확률과 같아야 함
	local allRarerFail = 1
	for _, aura in Auras.RarestFirst do
		if aura.OneIn > 8 then
			allRarerFail *= 1 - 8 / aura.OneIn
		end
	end
	near(probs.dew, allRarerFail, 1e-12, "dew")
	local calls = 0
	for _ = 1, 20000 do
		local aura = RollLogic.roll(Auras.RarestFirst, 8, function()
			calls += 1
			return math.random()
		end)
		assert(aura.OneIn >= 8, "행운 8 인데 " .. aura.Id)
	end
	assert(calls > 0)
end)
test("몬테카를로: 실제 굴림 분포가 계산 확률과 일치 (200만 회)", function()
	math.randomseed(12345)
	for _, luck in { 1, 3 } do
		local counts = {}
		local n = 1000000
		for _ = 1, n do
			local aura = RollLogic.roll(Auras.RarestFirst, luck, math.random)
			counts[aura.Id] = (counts[aura.Id] or 0) + 1
		end
		local probs = RollLogic.probabilities(Auras.RarestFirst, luck)
		for _, aura in Auras.List do
			local p = probs[aura.Id]
			if p * n >= 200 then -- 표본이 충분한 오라만 비교 (±5 표준편차)
				local expected = p * n
				local sd = math.sqrt(n * p * (1 - p))
				near(counts[aura.Id] or 0, expected, 5 * sd, string.format("luck %g %s", luck, aura.Id))
			end
		end
	end
end)
test("난수 경계값: 0 이면 가장 희귀, 1 에 가까우면 Common", function()
	eq(
		RollLogic.roll(Auras.RarestFirst, 1, function()
			return 0
		end).Id,
		Auras.RarestFirst[1].Id,
		"0"
	)
	eq(
		RollLogic.roll(Auras.RarestFirst, 1, function()
			return 0.9999999
		end).Id,
		"common",
		"~1"
	)
end)

print("\n[PlayerState]")
test("새 데이터 기본값", function()
	local d = PlayerState.new()
	eq(d.Rolls, 0)
	eq(d.Coins, 0)
	eq(d.Settings.AutoEquip, true)
	eq(PlayerState.luck(d), Config.BASE_LUCK, "luck")
	eq(PlayerState.cooldown(d), Config.ROLL_COOLDOWN, "cooldown")
	eq(PlayerState.best(d), nil, "best")
end)
test("applyRoll: 개수/굴림수/코인/신규 여부", function()
	local d = PlayerState.new()
	local coins, isNew = PlayerState.applyRoll(d, Auras.ById.moonlight)
	eq(isNew, true, "첫 획득")
	eq(coins, math.ceil(1000 ^ Config.COIN_EXPONENT), "코인")
	eq(d.Coins, coins)
	eq(d.Rolls, 1)
	local _, again = PlayerState.applyRoll(d, Auras.ById.moonlight)
	eq(again, false, "두 번째")
	eq(d.Inventory.moonlight, 2)
	PlayerState.applyRoll(d, Auras.ById.common)
	eq(PlayerState.best(d), Auras.ById.moonlight, "best")
end)
test("코인은 희귀할수록 많고 최소 1", function()
	eq(PlayerState.coinsFor(Auras.ById.common), 2, "common")
	local prev = 0
	for _, aura in Auras.List do
		local c = PlayerState.coinsFor(aura)
		assert(c >= 1 and c >= prev, aura.Id)
		prev = c
	end
end)
test("행운 굴림: 매 10번째", function()
	local d = PlayerState.new()
	local luckyCount = 0
	for _ = 1, 30 do
		local luck, lucky = PlayerState.rollLuck(d)
		if lucky then
			luckyCount += 1
			eq(luck, Config.BASE_LUCK * Config.LUCKY_ROLL_MULT, "행운 굴림 배수")
			eq((d.Rolls + 1) % Config.LUCKY_ROLL_EVERY, 0, "번호")
		end
		PlayerState.applyRoll(d, Auras.Common)
	end
	eq(luckyCount, 3, "30회 중 행운 굴림")
	eq(PlayerState.rollsUntilLucky(0), 10)
	eq(PlayerState.rollsUntilLucky(9), 1)
	eq(PlayerState.rollsUntilLucky(10), 10)
end)
test("물약: 코인 부족 / 구매 / 효과 / 상한 / 만료", function()
	local d = PlayerState.new()
	local ok, reason = PlayerState.buyPotion(d, "Luck")
	eq(ok, false)
	eq(reason, "코인이 부족합니다")
	eq(PlayerState.buyPotion(d, "Nope"), false, "없는 물약")
	eq(PlayerState.buyPotion(d, 123), false, "잘못된 타입")

	d.Coins = 100000
	assert(PlayerState.buyPotion(d, "Luck"))
	assert(PlayerState.buyPotion(d, "Speed"))
	eq(d.Coins, 100000 - 300 - 400, "차감")
	eq(PlayerState.luck(d), 1.5, "행운 물약")
	near(PlayerState.cooldown(d), Config.ROLL_COOLDOWN * 0.6, 1e-9, "신속 물약")
	assert(PlayerState.buyPotion(d, "Fortune"))
	near(PlayerState.luck(d), 4.5, 1e-9, "행운 x 대박 중첩")

	-- 같은 물약은 시간만 늘어남
	assert(PlayerState.buyPotion(d, "Luck"))
	eq(d.Potions.Luck, 600, "시간 연장")
	eq(PlayerState.luck(d) / 3, 1.5, "배수는 그대로")

	-- 상한
	d.Potions.Luck = Config.MAX_POTION_SECONDS - 10
	local coinsBefore = d.Coins
	eq(PlayerState.buyPotion(d, "Luck"), false, "상한 초과")
	eq(d.Coins, coinsBefore, "실패 시 코인 유지")

	-- 만료
	d.Potions = { Speed = 1.5 }
	eq(PlayerState.tickPotions(d, 1), false)
	eq(PlayerState.tickPotions(d, 1), true, "만료")
	eq(d.Potions.Speed, nil)
	eq(PlayerState.cooldown(d), Config.ROLL_COOLDOWN)
end)
test("장착: 보유한 것만, nil 은 해제", function()
	local d = PlayerState.new()
	eq(PlayerState.equip(d, "moonlight"), false, "미보유")
	PlayerState.applyRoll(d, Auras.ById.moonlight)
	eq(PlayerState.equip(d, "moonlight"), true)
	eq(d.Equipped, "moonlight")
	eq(PlayerState.equip(d, "없는오라"), false)
	eq(PlayerState.equip(d, {}), false)
	eq(PlayerState.equip(d, nil), true)
	eq(d.Equipped, nil)
end)
test("설정: 알려진 키/타입만", function()
	local d = PlayerState.new()
	eq(PlayerState.setSetting(d, "AutoEquip", false), true)
	eq(d.Settings.AutoEquip, false)
	eq(PlayerState.setSetting(d, "AutoEquip", "yes"), false)
	eq(PlayerState.setSetting(d, "Hack", true), false)
end)
test("reconcile: 깨진 값 정리, 모르는 오라는 보존", function()
	eq(PlayerState.reconcile(nil).Rolls, 0)
	eq(PlayerState.reconcile("garbage").Coins, 0)
	local d = PlayerState.reconcile({
		Rolls = 12.7,
		Coins = -5,
		Inventory = { moonlight = 3, removed_aura = 2, bad = "x", zero = 0, [5] = 1 },
		Equipped = "removed_aura",
		Potions = { Luck = 99999, Unknown = 10, Speed = -1 },
		Settings = { AutoEquip = false },
	})
	eq(d.Rolls, 12)
	eq(d.Coins, 0, "음수 코인")
	eq(d.Inventory.moonlight, 3)
	eq(d.Inventory.removed_aura, 2, "모르는 오라 보존")
	eq(d.Inventory.bad, nil)
	eq(d.Inventory.zero, nil)
	eq(d.Equipped, nil, "없는 오라 장착 해제")
	eq(d.Potions.Luck, Config.MAX_POTION_SECONDS, "물약 상한")
	eq(d.Potions.Unknown, nil)
	eq(d.Potions.Speed, nil)
	eq(d.Settings.AutoEquip, false)
	eq(PlayerState.reconcile({ Rolls = 0 / 0 }).Rolls, 0, "NaN")
	eq(PlayerState.reconcile({ Coins = math.huge }).Coins, 0, "inf")
end)
test("snapshot 은 복사본", function()
	local d = PlayerState.new()
	PlayerState.applyRoll(d, Auras.Common)
	local s = PlayerState.snapshot(d, 7)
	eq(s.Revision, 7)
	s.Inventory.common = 999
	eq(d.Inventory.common, 1, "원본 불변")
end)

print("\n[Format]")
test("commas", function()
	eq(Format.commas(0), "0")
	eq(Format.commas(999), "999")
	eq(Format.commas(1000), "1,000")
	eq(Format.commas(404040), "404,040")
	eq(Format.commas(-1234567), "-1,234,567")
end)
test("short / oneIn", function()
	eq(Format.short(999), "999")
	eq(Format.short(1500), "1.5K")
	eq(Format.short(404040), "404K")
	eq(Format.short(999999), "999K")
	eq(Format.short(2500000), "2.5M")
	eq(Format.short(10000000), "10M")
	eq(Format.short(100000000), "100M")
	eq(Format.oneIn(2500), "1 in 2,500")
	eq(Format.oneIn(404040), "1 in 404,040")
	eq(Format.oneIn(1000000), "1 in 1M")
end)
test("multiplier / duration / hex / escape", function()
	eq(Format.multiplier(1), "x1")
	eq(Format.multiplier(1.5), "x1.5")
	eq(Format.multiplier(4.5), "x4.5")
	eq(Format.multiplier(1.25), "x1.25")
	eq(Format.multiplier(10), "x10")
	eq(Format.duration(0), "0:00")
	eq(Format.duration(299.2), "5:00")
	eq(Format.duration(3723), "1:02:03")
	eq(Format.hex(Color3.fromRGB(255, 0, 128)), "#ff0080")
	eq(Format.escape('<b>&"'), "&lt;b&gt;&amp;&quot;")
end)

if not Harness.finish() then
	error("테스트 실패")
end
