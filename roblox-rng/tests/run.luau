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
	bridge = true,
	seastacks = true,
	reef = true,
	ruins = true,
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
test("여권 지역은 5대륙뿐, 모든 명소가 대륙에 속함", function()
	eq(#Landmarks.Regions, 5, "대륙 수")
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
test("공원 최대 전시 칸 = 격자 크기 (그 이상은 희귀한 순서로만 전시)", function()
	local park = PlayerState.UpgradesById.Park
	local maxSlots = Config.BASE_SLOTS + park.PerLevel * park.MaxLevel
	eq(maxSlots, Config.PARK_GRID * Config.PARK_GRID, "최대 칸")
	-- 전부 가진 플레이어도 격자만큼만 전시
	local d = PlayerState.new()
	for _, landmark in Landmarks.List do
		d.Inventory[landmark.Id] = 1
	end
	d.Upgrades.Park = park.MaxLevel
	eq(#PlayerState.park(d), math.min(maxSlots, #Landmarks.List), "전시 수")
	eq(PlayerState.park(d)[1], Landmarks.RarestFirst[1].Id, "가장 희귀한 것부터")
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
	eq(d.Rebirths, 0, "Rebirths")
	eq(next(d.Discovered), nil, "Discovered")
	eq(next(d.Boosts), nil, "Boosts")
	eq(#d.Receipts, 0, "Receipts")
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
	-- 여권은 역대 발견 기록 기준: 보유 명소가 없어도(환생 뒤) 도장 유지
	table.clear(d.Inventory)
	eq(#PlayerState.completedRegions(d), 1, "보유 명소가 없어도 도장 유지")
	-- 도장 조건 명소가 하나라도 미발견이면 미완성
	d.Discovered[needed[1]] = nil
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
	eq(d.Discovered.eiffel, true, "예전 저장: 보유 명소는 발견 기록으로 이전")
	eq(d.Discovered.removed_one, true, "모르는 명소 발견 기록 보존")
	eq(d.Rebirths, 0, "Rebirths 기본값")
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
	eq(s.Cooldown, PlayerState.cooldown(d), "Cooldown")
	eq(s.Rebirths, 0, "Rebirths")
	eq(s.ServerLuck, false, "mods 없으면 서버 행운 없음")
	eq(next(s.Passes), nil, "mods 없으면 게임패스 없음")
	eq(s.NextRebirth.Coins, Config.REBIRTHS[1].Coins, "다음 환생 코인")
	eq(#s.NextRebirth.Landmarks, #Config.REBIRTHS[1].Landmarks, "다음 환생 명소")
	eq(s.Discovered.eiffel, true, "Discovered")
	s.Inventory.eiffel = 999
	s.Upgrades.Globe = 99
	s.Discovered.pyramid = true
	s.NextRebirth.Landmarks[1] = "hack"
	eq(d.Inventory.eiffel, 1, "원본 Inventory 불변")
	eq(d.Upgrades.Globe, 0, "원본 Upgrades 불변")
	eq(d.Discovered.pyramid, nil, "원본 Discovered 불변")
	eq(Config.REBIRTHS[1].Landmarks[1], "eiffel", "Config 불변")
	-- 읽기 함수에 Snapshot 을 그대로 넘겨도 됨
	eq(#PlayerState.park(PlayerState.snapshot(d, 8)), 1, "snapshot 으로 park 계산")
end)

print("\n[환생]")
test("Config.REBIRTHS: 있는 명소만, 코인은 단계마다 증가", function()
	assert(#Config.REBIRTHS >= 1, "환생 단계 없음")
	for i, step in Config.REBIRTHS do
		assert(#step.Landmarks > 0, i .. "단계 명소 없음")
		for _, id in step.Landmarks do
			assert(Landmarks.ById[id], i .. "단계 모르는 명소 " .. id)
		end
		if i > 1 then
			assert(step.Coins > Config.REBIRTHS[i - 1].Coins, i .. "단계 코인이 늘지 않음")
		end
	end
end)
test("rebirthRequirement: 표 + 표를 넘으면 마지막 명소 + 코인 ×4", function()
	local first = PlayerState.rebirthRequirement(0)
	eq(first.Coins, 5000)
	eq(first.Landmarks[1], "eiffel")
	eq(first.Landmarks[2], "liberty")
	local last = #Config.REBIRTHS
	eq(PlayerState.rebirthRequirement(last - 1).Coins, Config.REBIRTHS[last].Coins, "마지막 단계")
	local beyond1 = PlayerState.rebirthRequirement(last)
	eq(beyond1.Coins, Config.REBIRTHS[last].Coins * 4, "표 +1")
	eq(#beyond1.Landmarks, #Config.REBIRTHS[last].Landmarks, "표 +1 명소")
	eq(beyond1.Landmarks[1], Config.REBIRTHS[last].Landmarks[1])
	eq(PlayerState.rebirthRequirement(last + 1).Coins, Config.REBIRTHS[last].Coins * 16, "표 +2")
	-- 복사본이라 고쳐도 Config 는 그대로
	first.Landmarks[1] = "hack"
	eq(Config.REBIRTHS[1].Landmarks[1], "eiffel", "Config 불변")
end)
test("canRebirth: 모자란 명소와 코인", function()
	local d = PlayerState.new()
	local ok, missing, short = PlayerState.canRebirth(d)
	eq(ok, false)
	eq(#missing, 2, "명소 2개 없음")
	eq(missing[1], "eiffel")
	eq(missing[2], "liberty")
	eq(short, 5000, "코인 부족분")
	PlayerState.applyRoll(d, Landmarks.ById.eiffel)
	PlayerState.applyRoll(d, Landmarks.ById.liberty)
	d.Coins = 4000.5
	ok, missing, short = PlayerState.canRebirth(d)
	eq(ok, false)
	eq(#missing, 0)
	eq(short, 1000, "코인 부족분(올림)")
	d.Coins = 5000
	ok, missing, short = PlayerState.canRebirth(d)
	eq(ok, true)
	eq(short, 0)
	-- 발견 기록만 있고 이번 판에 보유하지 않으면 안 됨
	d.Inventory.liberty = nil
	ok, missing = PlayerState.canRebirth(d)
	eq(ok, false, "발견 기록만으로는 불가")
	eq(missing[1], "liberty")
	-- Snapshot 으로도 판단 가능
	d.Inventory.liberty = 1
	eq((PlayerState.canRebirth(PlayerState.snapshot(d, 1))), true, "snapshot")
end)
test(
	"rebirth: 코인·업그레이드·보유 명소·대표 초기화, 발견 기록·도장·설정 유지",
	function()
		local d = PlayerState.new()
		local ok, reason = PlayerState.rebirth(d)
		eq(ok, false)
		eq(reason, "필요한 명소가 없습니다")
		-- 아프리카 도장 + 1단계 요구 명소
		for _, landmark in Landmarks.ByRegion.Africa do
			if PlayerState.countsForStamp(landmark) then
				PlayerState.applyRoll(d, landmark)
			end
		end
		PlayerState.applyRoll(d, Landmarks.ById.eiffel)
		PlayerState.applyRoll(d, Landmarks.ById.liberty)
		d.Coins = 100
		ok, reason = PlayerState.rebirth(d)
		eq(ok, false)
		eq(reason, "코인이 부족합니다")
		eq(d.Rebirths, 0, "실패 시 그대로")
		eq(d.Coins, 100, "실패 시 코인 그대로")

		d.Coins = 12345
		d.Upgrades.Globe = 3
		d.Upgrades.Park = 2
		d.Settings.AutoFeature = false
		PlayerState.feature(d, "eiffel")
		PlayerState.addBoost(d, "LuckBoost")
		PlayerState.addReceipt(d, "r1")
		local rolls = d.Rolls
		ok, reason = PlayerState.rebirth(d)
		eq(ok, true)
		eq(reason, nil)
		eq(d.Rebirths, 1)
		eq(d.Coins, 0, "코인 초기화")
		for _, upgrade in Config.Upgrades do
			eq(d.Upgrades[upgrade.Id], 0, "업그레이드 초기화 " .. upgrade.Id)
		end
		eq(next(d.Inventory), nil, "보유 명소 비움")
		eq(d.Featured, nil, "대표 해제")
		eq(#PlayerState.park(d), 0, "공원 비움")
		eq(PlayerState.incomePerSecond(d), 0, "수입 0")
		eq(d.Discovered.eiffel, true, "발견 기록 유지")
		eq(d.Discovered.liberty, true, "발견 기록 유지")
		eq(PlayerState.completedRegions(d)[1], "Africa", "여권 도장 유지")
		eq(d.Settings.AutoFeature, false, "설정 유지")
		eq(d.Rolls, rolls, "굴림 수 유지")
		eq(PlayerState.boostLeft(d, "LuckBoost"), 900, "부스트 유지")
		eq(PlayerState.hasReceipt(d, "r1"), true, "영수증 유지")
		eq(PlayerState.rebirthRequirement(d.Rebirths).Coins, Config.REBIRTHS[2].Coins, "다음 단계")

		-- 환생 뒤 예전에 발견한 명소를 다시 얻으면: 보너스·NEW·별 상승 없음, 보유는 1
		local bonus, isNew, starUp = PlayerState.applyRoll(d, Landmarks.ById.eiffel)
		eq(bonus, 0, "재발견 보너스 없음")
		eq(isNew, false, "재발견은 NEW 아님")
		eq(starUp, false, "재발견은 별 상승 아님")
		eq(d.Inventory.eiffel, 1)
		eq(PlayerState.stars(d.Inventory.eiffel), 1)
		-- 처음 보는 명소는 여전히 NEW + 보너스
		local bonus2, isNew2 = PlayerState.applyRoll(d, Landmarks.ById.namsan)
		eq(isNew2, true)
		eq(bonus2, PlayerState.discoveryBonus(Landmarks.ById.namsan))
	end
)
test("환생 보상: 행운 +20%, 수입 +50% (누적)", function()
	local d = owning({ "clocktower" })
	near(PlayerState.luck(d), 1, 1e-9, "0회")
	near(PlayerState.incomePerSecond(d), 1, 1e-9, "0회 수입")
	d.Rebirths = 2
	near(PlayerState.luck(d), 1 + 2 * Config.REBIRTH_LUCK_BONUS, 1e-9, "2회 행운")
	near(PlayerState.incomePerSecond(d), 1 + 2 * Config.REBIRTH_INCOME_BONUS, 1e-9, "2회 수입")
	eq(PlayerState.cooldown(d), Config.ROLL_COOLDOWN, "쿨타임은 그대로")
end)

print("\n[유료 상품]")
local ALL_PASSES = { Passes = { LuckVIP = true, FastRoll = true, DoubleIncome = true } }
test("Config: 상품 Id 중복 없음, 기본값 0 = 비활성", function()
	local seen = {}
	for _, pass in Config.GamePasses do
		assert(not seen[pass.Id], "중복 " .. pass.Id)
		seen[pass.Id] = true
		eq(type(pass.PassId), "number", pass.Id)
		eq(PlayerState.PassesById[pass.Id], pass)
	end
	for _, product in Config.Products do
		assert(not seen[product.Id], "중복 " .. product.Id)
		seen[product.Id] = true
		eq(type(product.ProductId), "number", product.Id)
		eq(PlayerState.ProductsById[product.Id], product)
	end
	assert(PlayerState.PassesById.LuckVIP and PlayerState.PassesById.FastRoll and PlayerState.PassesById.DoubleIncome)
	assert(
		PlayerState.ProductsById.LuckBoost and PlayerState.ProductsById.ServerLuck and PlayerState.ProductsById.CoinPack
	)
	eq(Config.MAX_BOOST_SECONDS, 3 * 3600)
end)
test("배율: mods 없음 = 빈 mods = 예전 값", function()
	local d = owning({ "eiffel", "pyramid", "clocktower" })
	d.Upgrades.Globe = 2
	d.Upgrades.Agency = 3
	d.Upgrades.Ticket = 1
	local luck, cooldown, income = PlayerState.luck(d), PlayerState.cooldown(d), PlayerState.incomePerSecond(d)
	near(luck, 1.2, 1e-9, "행운")
	near(cooldown, Config.ROLL_COOLDOWN * 0.85, 1e-9, "쿨타임")
	near(income, (5 + 12 + 1) * 1.2, 1e-9, "수입")
	for _, mods in { {}, { Passes = {} }, { ServerLuck = false }, { Passes = { Nope = true } } } do
		eq(PlayerState.luck(d, mods), luck, "행운")
		eq(PlayerState.cooldown(d, mods), cooldown, "쿨타임")
		eq(PlayerState.incomePerSecond(d, mods), income, "수입")
	end
end)
test("배율: 게임패스 / 서버 행운 / 행운 부스트 / 환생 곱", function()
	local d = owning({ "clocktower" })
	near(PlayerState.luck(d, { Passes = { LuckVIP = true } }), 2, 1e-9, "VIP")
	near(PlayerState.luck(d, { ServerLuck = true }), 2, 1e-9, "서버 행운")
	near(PlayerState.cooldown(d, { Passes = { FastRoll = true } }), Config.ROLL_COOLDOWN * 0.7, 1e-9, "빠른 굴림")
	near(PlayerState.incomePerSecond(d, { Passes = { DoubleIncome = true } }), 2, 1e-9, "수입 2배")
	eq(
		PlayerState.luck(d, { Passes = { FastRoll = true, DoubleIncome = true } }),
		1,
		"다른 패스는 행운 영향 없음"
	)
	eq(PlayerState.luck(d, { Passes = { LuckVIP = false } }), 1, "false 는 없는 것")
	PlayerState.addBoost(d, "LuckBoost")
	near(PlayerState.luck(d), 2, 1e-9, "행운 부스트(데이터라서 mods 없어도 적용)")
	d.Rebirths = 1
	d.Upgrades.Globe = 1
	local all = { Passes = ALL_PASSES.Passes, ServerLuck = true }
	near(PlayerState.luck(d, all), 1.1 * 1.2 * 2 * 2 * 2, 1e-9, "전부 곱")
	near(PlayerState.incomePerSecond(d, all), 1 * 1.5 * 2, 1e-9, "수입 전부 곱")
	-- 스냅샷은 mods 반영 + Snapshot 을 mods 로 다시 넘겨도 같은 값
	local s = PlayerState.snapshot(d, 1, all)
	near(s.Luck, 1.1 * 1.2 * 8, 1e-9, "snapshot Luck")
	near(s.Cooldown, Config.ROLL_COOLDOWN * 0.7, 1e-9, "snapshot Cooldown")
	near(s.Income, 3, 1e-9, "snapshot Income")
	eq(s.ServerLuck, true)
	eq(s.Passes.LuckVIP, true)
	eq(s.Passes.FastRoll, true)
	eq(s.Boosts.LuckBoost, 900)
	eq(s.Rebirths, 1)
	near(PlayerState.luck(s, s), s.Luck, 1e-9, "luck(snapshot, snapshot)")
	s.Boosts.LuckBoost = 1
	s.Passes.Hack = true
	eq(d.Boosts.LuckBoost, 900, "원본 Boosts 불변")
	eq(all.Passes.Hack, nil, "mods 불변")
end)
test("부스트: 추가·누적·최대·시간 경과", function()
	local d = PlayerState.new()
	eq(PlayerState.addBoost(d, "LuckBoost"), true)
	eq(d.Boosts.LuckBoost, 900)
	PlayerState.addBoost(d, "LuckBoost")
	eq(PlayerState.boostLeft(d, "LuckBoost"), 1800, "시간 누적")
	for _ = 1, 20 do
		PlayerState.addBoost(d, "LuckBoost")
	end
	eq(d.Boosts.LuckBoost, Config.MAX_BOOST_SECONDS, "최대 시간")
	eq(PlayerState.addBoost(d, "ServerLuck"), false, "서버 행운은 개인 부스트 아님")
	eq(PlayerState.addBoost(d, "CoinPack"), false, "코인 팩은 부스트 아님")
	eq(PlayerState.addBoost(d, "Nope"), false)
	eq(PlayerState.addBoost(d, 5), false)
	eq(d.Boosts.ServerLuck, nil)

	d.Boosts.LuckBoost = 10
	eq(PlayerState.tickBoosts(d, 4), false, "아직 안 끝남")
	near(d.Boosts.LuckBoost, 6, 1e-9, "남은 시간")
	eq(PlayerState.tickBoosts(d, 0), false, "0 초")
	eq(PlayerState.tickBoosts(d, -3), false, "음수")
	near(d.Boosts.LuckBoost, 6, 1e-9, "그대로")
	eq(PlayerState.tickBoosts(d, 6), true, "끝남")
	eq(d.Boosts.LuckBoost, nil, "지워짐")
	eq(PlayerState.boostLeft(d, "LuckBoost"), 0)
	eq(PlayerState.tickBoosts(d, 1), false, "부스트 없음")
	eq(PlayerState.luck(d), 1, "끝나면 행운 원래대로")
end)
test("영수증: 중복 기록 없음, 최근 50개만", function()
	local d = PlayerState.new()
	eq(PlayerState.hasReceipt(d, "abc"), false)
	PlayerState.addReceipt(d, "abc")
	eq(PlayerState.hasReceipt(d, "abc"), true)
	PlayerState.addReceipt(d, "abc")
	eq(#d.Receipts, 1, "중복 없음")
	PlayerState.addReceipt(d, 12345)
	eq(PlayerState.hasReceipt(d, "12345"), true, "숫자도 문자열로")
	eq(PlayerState.hasReceipt(d, 12345), true)
	for i = 1, 60 do
		PlayerState.addReceipt(d, "p" .. i)
	end
	eq(#d.Receipts, Config.MAX_RECEIPTS, "최대 개수")
	eq(PlayerState.hasReceipt(d, "abc"), false, "오래된 것 삭제")
	eq(PlayerState.hasReceipt(d, "p10"), false, "오래된 것 삭제")
	eq(PlayerState.hasReceipt(d, "p11"), true, "최근 50개 유지")
	eq(PlayerState.hasReceipt(d, "p60"), true)
	eq(d.Receipts[#d.Receipts], "p60", "최근 것이 끝")
end)
test("grantProduct: 코인 팩 = max(1000, 초당 수입 × 1800), 부스트, 서버 행운", function()
	local d = PlayerState.new()
	local ok, grant = PlayerState.grantProduct(d, "CoinPack")
	eq(ok, true)
	eq(grant.Coins, 1000, "수입 0 이면 최소 1000")
	eq(d.Coins, 1000)
	d = owning({ "pyramid" }) -- 12/초 → 21,600
	local before = d.Coins
	ok, grant = PlayerState.grantProduct(d, "CoinPack")
	eq(grant.Coins, 12 * 1800, "초당 수입 × 1800")
	eq(d.Coins, before + 12 * 1800)
	eq(grant.ServerWide, false)
	ok, grant = PlayerState.grantProduct(d, "CoinPack", { Passes = { DoubleIncome = true } })
	eq(grant.Coins, 24 * 1800, "수입 2배 반영")

	ok, grant = PlayerState.grantProduct(d, "LuckBoost")
	eq(ok, true)
	eq(grant.Seconds, 900)
	eq(grant.Coins, 0)
	eq(d.Boosts.LuckBoost, 900)
	d.Boosts.LuckBoost = Config.MAX_BOOST_SECONDS - 100
	ok, grant = PlayerState.grantProduct(d, "LuckBoost")
	eq(grant.Seconds, 100, "최대 시간까지만")

	local coins = d.Coins
	ok, grant = PlayerState.grantProduct(d, "ServerLuck")
	eq(ok, true)
	eq(grant.ServerWide, true, "서버가 처리")
	eq(grant.Seconds, 900)
	eq(d.Boosts.ServerLuck, nil, "데이터에 저장 안 함")
	eq(d.Coins, coins)

	eq((PlayerState.grantProduct(d, "Nope")), false)
	eq((PlayerState.grantProduct(d, nil)), false)
end)
test("reconcile: 환생·발견·부스트·영수증 정리", function()
	local receipts = { 5, "x", false }
	for i = 1, 55 do
		table.insert(receipts, "r" .. i)
	end
	local d = PlayerState.reconcile({
		Rebirths = 3.9,
		Inventory = { eiffel = 2 },
		Discovered = { pyramid = true, bad = 1, gone = true, [3] = true },
		Boosts = { LuckBoost = 1e9, ServerLuck = 50, CoinPack = 10, Nope = 5 },
		Receipts = receipts,
	})
	eq(d.Rebirths, 3, "환생 버림")
	eq(d.Discovered.pyramid, true)
	eq(d.Discovered.gone, true, "모르는 명소 발견 기록 보존")
	eq(d.Discovered.eiffel, true, "보유 ⇒ 발견")
	eq(d.Discovered.bad, nil, "true 가 아니면 무시")
	eq(d.Discovered[3], nil, "문자열 Id 만")
	eq(d.Boosts.LuckBoost, Config.MAX_BOOST_SECONDS, "최대 시간으로 제한")
	eq(d.Boosts.ServerLuck, nil, "서버 행운은 저장 안 함")
	eq(d.Boosts.CoinPack, nil)
	eq(d.Boosts.Nope, nil)
	eq(#d.Receipts, Config.MAX_RECEIPTS, "최근 50개")
	eq(d.Receipts[1], "r6", "오래된 것부터 삭제")
	eq(d.Receipts[#d.Receipts], "r55")
	eq(PlayerState.hasReceipt(d, "x"), false)

	local bad = PlayerState.reconcile({ Rebirths = -2, Boosts = { LuckBoost = -5 }, Receipts = "x", Discovered = 7 })
	eq(bad.Rebirths, 0, "음수")
	eq(bad.Boosts.LuckBoost, nil, "음수 부스트")
	eq(#bad.Receipts, 0)
	eq(next(bad.Discovered), nil)
	eq(PlayerState.reconcile({ Boosts = { LuckBoost = 0 / 0 } }).Boosts.LuckBoost, nil, "NaN 부스트")
	eq(PlayerState.reconcile({ Rebirths = math.huge }).Rebirths, 0, "inf")
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
