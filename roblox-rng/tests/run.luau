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
local Landmarks = Harness.require(shared.Landmarks)
local RollLogic = Harness.require(shared.RollLogic)
local PlayerState = Harness.require(shared.PlayerState)
local Format = Harness.require(shared.Format)

local KNOWN_SHAPES = {
	clocktower = true,
	lighthouse = true,
	windmill = true,
	fountain = true,
	arch = true,
	gate = true,
	leaning = true,
	statue = true,
	needle = true,
	lattice = true,
	ring = true,
	dome = true,
	temple = true,
	sphinx = true,
	wall = true,
	pyramid = true,
	steps = true,
	terraces = true,
	facade = true,
	moai = true,
	stones = true,
	gardens = true,
	spiral = true,
	island = true,
	pagoda = true,
	skyisland = true,
	tree = true,
	globe = true,
}

print("\n[Landmarks]")
test("Id 중복 없음 + OneIn/지역/모형 정상", function()
	local seen = {}
	for _, landmark in Landmarks.List do
		assert(not seen[landmark.Id], "중복 " .. landmark.Id)
		seen[landmark.Id] = true
		assert(landmark.OneIn >= 1, landmark.Id .. " OneIn < 1")
		assert(Landmarks.ById[landmark.Id] == landmark)
		assert(Landmarks.RegionById[landmark.Region], landmark.Id .. " 지역 없음")
		assert(KNOWN_SHAPES[landmark.Shape], landmark.Id .. " 모르는 모형 " .. landmark.Shape)
	end
end)
test("RarestFirst 는 내림차순, 마지막은 가장 흔한 명소", function()
	for i = 2, #Landmarks.RarestFirst do
		assert(Landmarks.RarestFirst[i - 1].OneIn >= Landmarks.RarestFirst[i].OneIn, "정렬 깨짐 at " .. i)
	end
	eq(Landmarks.RarestFirst[#Landmarks.RarestFirst], Landmarks.Common, "마지막")
	eq(Landmarks.Common.Id, "clocktower", "가장 흔한 명소")
	eq(Landmarks.Common.Region, "Asia", "가장 흔한 명소도 대륙 소속")
end)
test("등급 경계", function()
	eq(Landmarks.ById.fountain.Tier.Name, "일반 명소")
	eq(Landmarks.ById.arc.Tier.Name, "도시 명소")
	eq(Landmarks.ById.namsan.Tier.Name, "국가 명소")
	eq(Landmarks.ById.sphinx.Tier.Name, "세계 명소")
	eq(Landmarks.ById.alexandria.Tier.Name, "불가사의")
	eq(Landmarks.ById.babel.Tier.Name, "잃어버린 유산")
	eq(Landmarks.ById.worldtree.Tier.Name, "전설")
	eq(Landmarks.ById.earth, nil, "지구는 명소가 아님")
end)
test("여권 지역은 4대륙뿐, 모든 명소가 대륙에 속함", function()
	eq(#Landmarks.Regions, 4, "대륙 수")
	for _, region in Landmarks.Regions do
		assert(#Landmarks.ByRegion[region.Id] > 0, region.Id .. " 비어 있음")
		local _, required = PlayerState.regionProgress(PlayerState.new(), region.Id)
		assert(required > 0, region.Id .. " 도장 조건 명소 없음")
	end
	local total = 0
	for _, list in Landmarks.ByRegion do
		total += #list
	end
	eq(total, #Landmarks.List, "합계")
	-- 장식용 지구본은 뽑기 목록에 없음
	for _, landmark in Landmarks.List do
		assert(landmark ~= Landmarks.Globe, "장식용 지구본이 뽑기 목록에 있음")
	end
	eq(Landmarks.Globe.Shape, "globe")
end)
test("전시 칸 최대치로 모든 명소를 전시할 수 있음", function()
	local park = PlayerState.UpgradesById.Park
	local maxSlots = Config.BASE_SLOTS + park.PerLevel * park.MaxLevel
	assert(maxSlots >= #Landmarks.List, string.format("최대 칸 %d < 명소 %d", maxSlots, #Landmarks.List))
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
		near(sum(RollLogic.probabilities(Landmarks.RarestFirst, luck)), 1, 1e-9, "luck " .. luck)
	end
end)
test("행운 1 에서 희귀 명소 확률 ≈ 1/N", function()
	local probs = RollLogic.probabilities(Landmarks.RarestFirst, 1)
	for _, landmark in Landmarks.List do
		if landmark.OneIn >= 1000 then
			near(probs[landmark.Id] * landmark.OneIn, 1, 0.01, landmark.Id .. " p*N")
		end
	end
end)
test("행운 2 면 희귀 확률 ≈ 2배", function()
	local p1 = RollLogic.probabilities(Landmarks.RarestFirst, 1)
	local p2 = RollLogic.probabilities(Landmarks.RarestFirst, 2)
	near(p2.yonggung / p1.yonggung, 2, 0.01, "yonggung 배율")
	near(p2.pyramid / p1.pyramid, 2, 0.01, "pyramid 배율")
end)
test("행운 ≥ N 이면 더 흔한 명소는 안 나옴", function()
	local probs = RollLogic.probabilities(Landmarks.RarestFirst, 5)
	eq(probs.clocktower, 0, "clocktower")
	eq(probs.lighthouse, 0, "lighthouse")
	for _ = 1, 20000 do
		local landmark = RollLogic.roll(Landmarks.RarestFirst, 5, math.random)
		assert(landmark.OneIn >= 5, "행운 5 인데 " .. landmark.Id)
	end
end)
test("몬테카를로: 실제 굴림 분포가 계산 확률과 일치 (200만 회)", function()
	math.randomseed(12345)
	for _, luck in { 1, 3 } do
		local counts = {}
		local n = 1000000
		for _ = 1, n do
			local landmark = RollLogic.roll(Landmarks.RarestFirst, luck, math.random)
			counts[landmark.Id] = (counts[landmark.Id] or 0) + 1
		end
		local probs = RollLogic.probabilities(Landmarks.RarestFirst, luck)
		for _, landmark in Landmarks.List do
			local p = probs[landmark.Id]
			if p * n >= 200 then
				local sd = math.sqrt(n * p * (1 - p))
				near(counts[landmark.Id] or 0, p * n, 5 * sd, string.format("luck %g %s", luck, landmark.Id))
			end
		end
	end
end)

print("\n[PlayerState]")
local function owning(ids: { string }): any
	local d = PlayerState.new()
	for _, id in ids do
		PlayerState.applyRoll(d, Landmarks.ById[id])
	end
	return d
end

test("새 데이터 기본값", function()
	local d = PlayerState.new()
	eq(d.Rolls, 0)
	eq(d.Coins, 0)
	eq(d.Settings.AutoFeature, true)
	for _, upgrade in Config.Upgrades do
		eq(d.Upgrades[upgrade.Id], 0, upgrade.Id)
	end
	eq(PlayerState.luck(d), Config.BASE_LUCK, "luck")
	eq(PlayerState.cooldown(d), Config.ROLL_COOLDOWN, "cooldown")
	eq(PlayerState.slots(d), Config.BASE_SLOTS, "slots")
	eq(PlayerState.incomePerSecond(d), 0, "income")
	eq(#PlayerState.park(d), 0, "park")
	eq(PlayerState.best(d), nil, "best")
end)
test("applyRoll: 처음 발견 보너스, 중복은 보너스 없음, 별 상승", function()
	local d = PlayerState.new()
	local eiffel = Landmarks.ById.eiffel
	local bonus, isNew, starUp = PlayerState.applyRoll(d, eiffel)
	eq(isNew, true, "첫 발견")
	eq(starUp, false, "첫 발견은 별 상승 아님")
	eq(bonus, math.ceil(Config.DISCOVERY_BONUS_MULT * 200 ^ 0.5), "보너스")
	eq(d.Coins, bonus)
	eq(d.Rolls, 1)
	local bonus2, isNew2, starUp2 = PlayerState.applyRoll(d, eiffel)
	eq(bonus2, 0, "중복 보너스 없음")
	eq(isNew2, false)
	eq(starUp2, false, "2회는 아직 1성")
	local _, _, starUp3 = PlayerState.applyRoll(d, eiffel)
	eq(starUp3, true, "3회 = 2성")
	eq(d.Inventory.eiffel, 3)
	eq(PlayerState.best(d), eiffel)
end)
test("별 기준", function()
	eq(PlayerState.stars(0), 0)
	eq(PlayerState.stars(1), 1)
	eq(PlayerState.stars(2), 1)
	eq(PlayerState.stars(3), 2)
	eq(PlayerState.stars(10), 3)
	eq(PlayerState.stars(99), 4)
	eq(PlayerState.stars(100), 5)
	eq(PlayerState.stars(100000), 5)
end)
test("공원: 희귀한 순서로 전시 칸만큼, 수입 계산", function()
	local d = owning({ "clocktower", "lighthouse", "windmill", "fountain", "arc", "bigben", "eiffel", "pyramid" })
	local park = PlayerState.park(d)
	eq(#park, Config.BASE_SLOTS, "칸 수만큼")
	eq(park[1], "pyramid", "가장 희귀한 게 먼저")
	eq(park[2], "eiffel")
	-- 흔한 시계탑/등대는 칸이 모자라 빠짐
	for _, id in park do
		assert(id ~= "clocktower" and id ~= "lighthouse", "흔한 명소가 전시됨: " .. id)
	end
	local expected = 0
	for _, id in park do
		expected += Config.TIER_INCOME[Landmarks.ById[id].Tier.Rank]
	end
	near(PlayerState.incomePerSecond(d), expected, 1e-9, "수입")

	-- 별이 오르면 그 명소 수입이 늘어남
	for _ = 1, 2 do
		PlayerState.applyRoll(d, Landmarks.ById.pyramid)
	end
	near(
		PlayerState.incomePerSecond(d),
		expected + Config.TIER_INCOME[4] * Config.STAR_INCOME_BONUS,
		1e-9,
		"2성 수입"
	)

	-- 수입 적립
	local coinsBefore = d.Coins
	local added = PlayerState.addIncome(d, 2)
	near(added, PlayerState.incomePerSecond(d) * 2, 1e-9, "2초 수입")
	near(d.Coins, coinsBefore + added, 1e-9, "코인 증가")
	eq(PlayerState.addIncome(d, -5), 0, "음수 dt 무시")
end)
test("업그레이드: 가격, 부족, 구매, 효과, 최대 레벨", function()
	local d = PlayerState.new()
	eq(PlayerState.upgradePrice("Globe", 0), 400)
	eq(PlayerState.upgradePrice("Globe", 1), math.floor(400 * 1.7))
	eq(PlayerState.upgradePrice("Nope", 0), nil)
	local ok, reason = PlayerState.buyUpgrade(d, "Globe")
	eq(ok, false)
	eq(reason, "코인이 부족합니다")
	eq(PlayerState.buyUpgrade(d, "Nope"), false, "없는 업그레이드")
	eq(PlayerState.buyUpgrade(d, 5), false, "잘못된 타입")

	d.Coins = 1e12
	for _, id in { "Globe", "Agency", "Park", "Ticket" } do
		assert(PlayerState.buyUpgrade(d, id), id)
	end
	near(PlayerState.luck(d), 1.1, 1e-9, "지구본 1레벨")
	near(PlayerState.cooldown(d), Config.ROLL_COOLDOWN * 0.95, 1e-9, "여행사 1레벨")
	eq(PlayerState.slots(d), Config.BASE_SLOTS + 3, "공원 확장 1레벨")
	PlayerState.applyRoll(d, Landmarks.ById.clocktower)
	near(PlayerState.incomePerSecond(d), 1 * 1.2, 1e-9, "입장료 1레벨")

	-- 최대 레벨
	d.Upgrades.Agency = PlayerState.UpgradesById.Agency.MaxLevel
	local coinsBefore = d.Coins
	local ok2, reason2 = PlayerState.buyUpgrade(d, "Agency")
	eq(ok2, false)
	eq(reason2, "이미 최대 레벨입니다")
	eq(d.Coins, coinsBefore, "실패 시 코인 유지")
	assert(PlayerState.cooldown(d) > 0, "최대 레벨에서도 쿨타임 > 0")
end)
test("여권 도장: 전설급을 뺀 대륙 명소를 다 모으면 행운 보너스", function()
	local needed, legendary = {}, nil
	for _, landmark in Landmarks.ByRegion.Africa do
		if PlayerState.countsForStamp(landmark) then
			table.insert(needed, landmark.Id)
		else
			legendary = landmark
		end
	end
	assert(legendary, "아프리카에 전설급 명소가 있어야 이 테스트가 의미 있음")
	local d = owning(needed)
	local found, required = PlayerState.regionProgress(d, "Africa")
	eq(found, required, "진행도")
	local completed = PlayerState.completedRegions(d)
	eq(#completed, 1, "완성 대륙 수")
	eq(completed[1], "Africa")
	eq((d.Inventory[legendary.Id] or 0), 0, "전설급 없이도 도장")
	near(PlayerState.luck(d), 1 + Config.REGION_LUCK_BONUS, 1e-9, "행운 보너스")
	-- 도장 조건 명소가 하나 빠지면 미완성
	d.Inventory[needed[1]] = nil
	eq(#PlayerState.completedRegions(d), 0, "미완성")
end)
test("대표 명소: 발견한 것만, nil 은 해제", function()
	local d = PlayerState.new()
	eq(PlayerState.feature(d, "eiffel"), false, "미발견")
	PlayerState.applyRoll(d, Landmarks.ById.eiffel)
	eq(PlayerState.feature(d, "eiffel"), true)
	eq(d.Featured, "eiffel")
	eq(PlayerState.feature(d, "없는명소"), false)
	eq(PlayerState.feature(d, {}), false)
	eq(PlayerState.feature(d, nil), true)
	eq(d.Featured, nil)
end)
test("설정: 알려진 키/타입만", function()
	local d = PlayerState.new()
	eq(PlayerState.setSetting(d, "AutoFeature", false), true)
	eq(d.Settings.AutoFeature, false)
	eq(PlayerState.setSetting(d, "AutoFeature", "yes"), false)
	eq(PlayerState.setSetting(d, "Hack", true), false)
end)
test("reconcile: 깨진 값 정리, 모르는 명소는 보존", function()
	eq(PlayerState.reconcile(nil).Rolls, 0)
	eq(PlayerState.reconcile("garbage").Coins, 0)
	local d = PlayerState.reconcile({
		Rolls = 12.7,
		Coins = 99.9,
		Inventory = { eiffel = 3, removed_one = 2, bad = "x", zero = 0, [5] = 1 },
		Featured = "removed_one",
		Upgrades = { Globe = 3, Agency = 999, Park = -1, Unknown = 5 },
		Settings = { AutoFeature = false },
	})
	eq(d.Rolls, 12)
	eq(d.Coins, 99, "코인 버림")
	eq(d.Inventory.eiffel, 3)
	eq(d.Inventory.removed_one, 2, "모르는 명소 보존")
	eq(d.Inventory.bad, nil)
	eq(d.Inventory.zero, nil)
	eq(d.Featured, nil, "없는 명소 대표 해제")
	eq(d.Upgrades.Globe, 3)
	eq(d.Upgrades.Agency, PlayerState.UpgradesById.Agency.MaxLevel, "최대 레벨로 제한")
	eq(d.Upgrades.Park, 0, "음수 무시")
	eq(d.Upgrades.Unknown, nil, "모르는 업그레이드 무시")
	eq(d.Settings.AutoFeature, false)
	eq(PlayerState.reconcile({ Rolls = 0 / 0 }).Rolls, 0, "NaN")
	eq(PlayerState.reconcile({ Coins = math.huge }).Coins, 0, "inf")
	-- 모르는 명소는 공원/수입에 영향 없음
	eq(#PlayerState.park(d), 1, "공원에는 아는 명소만")
end)
test("snapshot 은 복사본이고 파생 값 포함", function()
	local d = owning({ "eiffel" })
	local s = PlayerState.snapshot(d, 7)
	eq(s.Revision, 7)
	eq(s.Income, PlayerState.incomePerSecond(d), "Income")
	eq(s.Luck, PlayerState.luck(d), "Luck")
	s.Inventory.eiffel = 999
	s.Upgrades.Globe = 99
	eq(d.Inventory.eiffel, 1, "원본 Inventory 불변")
	eq(d.Upgrades.Globe, 0, "원본 Upgrades 불변")
	-- 읽기 함수에 Snapshot 을 그대로 넘겨도 됨
	eq(#PlayerState.park(PlayerState.snapshot(d, 8)), 1, "snapshot 으로 park 계산")
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
