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
			-- 더 희귀한 명소들이 먼저 판정되므로 정확히 1/N 보다 살짝 낮음(명소가 많을수록 차이 커짐)
			near(probs[landmark.Id] * landmark.OneIn, 1, 0.02, landmark.Id .. " p*N")
		end
	end
end)
test("행운 2 면 희귀 확률 ≈ 2배", function()
	local p1 = RollLogic.probabilities(Landmarks.RarestFirst, 1)
	local p2 = RollLogic.probabilities(Landmarks.RarestFirst, 2)
	near(p2.yonggung / p1.yonggung, 2, 0.01, "yonggung 배율")
	near(p2.pyramid / p1.pyramid, 2, 0.02, "pyramid 배율")
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

print("\n[공원 배치]")
local EIGHT = { "clocktower", "lighthouse", "windmill", "fountain", "arc", "bigben", "eiffel", "pyramid" }

-- 열린 칸마다 전시 명소(빈 칸 = "-")를 쉼표로 이은 글자: 비교하기 쉽게
local function slotsText(d): string
	local slots, unlocked = PlayerState.parkSlots(d)
	local parts = {}
	for slot = 1, unlocked do
		table.insert(parts, slots[slot] or "-")
	end
	return table.concat(parts, ",")
end

-- Display 는 구멍 없는 문자열 배열, 길이 ≤ 격자 칸 수, 끝 빈 칸 없음 (DataStore 안전)
local function checkDisplay(d)
	local n = 0
	for key, value in d.Display do
		assert(type(key) == "number" and key % 1 == 0 and key >= 1, "배열 키 " .. tostring(key))
		assert(type(value) == "string", "문자열 값 " .. tostring(value))
		n += 1
	end
	eq(n, #d.Display, "구멍 없음")
	assert(#d.Display <= Config.PARK_GRID * Config.PARK_GRID, "길이 제한")
	if #d.Display > 0 then
		assert(d.Display[#d.Display] ~= "", "끝 빈 칸은 잘라 냄")
	end
end

-- 수입 = 전시 칸에 있는 명소 수입 합 (입장료·환생·게임패스 없는 데이터 기준)
local function slotIncome(d): number
	local slots, unlocked = PlayerState.parkSlots(d)
	local total = 0
	for slot = 1, unlocked do
		local id = slots[slot]
		if id then
			total += PlayerState.landmarkIncome(Landmarks.ById[id], d.Inventory[id])
		end
	end
	return total
end

test("slotCell: 칸 번호 <-> 격자 자리 일대일, 입구 줄부터 가운데부터", function()
	local grid = Config.PARK_GRID
	local seen = {}
	for slot = 1, grid * grid do
		local row, column = PlayerState.slotCell(slot)
		assert(row >= 1 and row <= grid and column >= 1 and column <= grid, "범위 " .. slot)
		local key = row * 100 + column
		assert(not seen[key], "겹침 " .. slot)
		seen[key] = true
		eq(row, (slot - 1) // grid + 1, "입구 쪽 줄부터 " .. slot)
	end
	eq(PlayerState.MAX_SLOTS, grid * grid)
	-- 한 줄: 가운데 오른쪽 -> 가운데 왼쪽 -> … -> 왼쪽 끝 (입구에서 공원 안쪽을 볼 때)
	eq(select(2, PlayerState.slotCell(1)), grid / 2 + 1, "1번 = 가운데 오른쪽")
	eq(select(2, PlayerState.slotCell(2)), grid / 2, "2번 = 가운데 왼쪽")
	eq(select(2, PlayerState.slotCell(grid - 1)), grid, "오른쪽 끝")
	eq(select(2, PlayerState.slotCell(grid)), 1, "줄 마지막 = 왼쪽 끝")
end)
test("새 데이터 / reconcile: 자동 배치 기본값, 배치 정리", function()
	local d = PlayerState.new()
	eq(d.Settings.AutoPark, true, "기본 자동 배치")
	eq(#d.Display, 0)
	local old = PlayerState.reconcile({ Settings = { AutoFeature = false } })
	eq(old.Settings.AutoPark, true, "예전 저장 = 자동 배치")
	eq(old.Settings.AutoFeature, false)
	eq(#old.Display, 0)
	eq(
		PlayerState.reconcile({ Settings = { AutoPark = "no" } }).Settings.AutoPark,
		true,
		"타입이 틀리면 기본값"
	)
	eq(#PlayerState.reconcile({ Display = "x" }).Display, 0, "표가 아니면 빈 배치")

	local long = {}
	for i = 1, 50 do
		long[i] = "id" .. i
	end
	local r = PlayerState.reconcile({ Settings = { AutoPark = false }, Display = long })
	eq(r.Settings.AutoPark, false)
	eq(#r.Display, PlayerState.MAX_SLOTS, "최대 길이까지만")
	checkDisplay(r)
	local trailing = PlayerState.reconcile({ Display = { "eiffel", "", 0, false } })
	eq(#trailing.Display, 1, "끝 빈 칸 잘라 냄")

	-- 겹친 Id -> 뒤 칸은 빈 칸, 문자열이 아니면 빈 칸, 모르는·보유하지 않은 명소 Id 는 보존(전시할 때만 건너뜀)
	local m = PlayerState.reconcile({
		Inventory = { eiffel = 1, pyramid = 1, arc = 1 },
		Settings = { AutoPark = false },
		Display = { "eiffel", "eiffel", 5, "pyramid", "nope", "sphinx" },
	})
	eq(table.concat(m.Display, ","), "eiffel,,,pyramid,nope,sphinx")
	checkDisplay(m)
	eq(slotsText(m), "eiffel,-,-,pyramid,-,-", "보이는 칸")
	-- 데이터를 직접 고쳐 겹쳐도 앞 칸 하나만 전시
	m.Display[2] = "eiffel"
	eq(slotsText(m), "eiffel,-,-,pyramid,-,-", "겹침은 앞 칸만")
	-- 편집하면 보이는 그대로 정리됨
	eq((PlayerState.setDisplay(m, 3, "arc")), true)
	eq(slotsText(m), "eiffel,-,arc,pyramid,-,-")
	eq(table.concat(m.Display, ","), "eiffel,,arc,pyramid", "안 보이던 Id 는 정리")
	checkDisplay(m)
end)
test("parkSlots: 자동 배치 = 희귀한 순서로 1번 칸부터, 열린 칸 수만큼", function()
	local d = owning(EIGHT)
	local slots, unlocked = PlayerState.parkSlots(d)
	eq(unlocked, Config.BASE_SLOTS, "열린 칸 수")
	eq(slotsText(d), "pyramid,eiffel,bigben,arc,fountain,windmill")
	local park = PlayerState.park(d)
	eq(#park, unlocked)
	for i, id in park do
		eq(id, slots[i], "park = 빈 칸을 뺀 parkSlots")
	end
	eq(#d.Display, 0, "자동 배치는 Display 를 안 씀")
	eq(slotsText(PlayerState.new()), "-,-,-,-,-,-", "빈 공원")
end)
test(
	"setDisplay: 첫 편집은 자동 배치에서 시작해 자동을 끔, 놓기·자리 바꾸기·빼기",
	function()
		local d = owning(EIGHT)
		-- 전시 안 된 시계탑을 1번 칸에: 피라미드가 빠지고 나머지는 자동 배치 그대로
		local ok, reason = PlayerState.setDisplay(d, 1, "clocktower")
		eq(ok, true, reason)
		eq(reason, nil)
		eq(d.Settings.AutoPark, false, "자동 배치 꺼짐")
		eq(slotsText(d), "clocktower,eiffel,bigben,arc,fountain,windmill")
		checkDisplay(d)
		-- 다른 칸에 전시 중인 명소를 놓으면 두 칸이 자리를 바꿈
		eq((PlayerState.setDisplay(d, 1, "windmill")), true)
		eq(slotsText(d), "windmill,eiffel,bigben,arc,fountain,clocktower")
		-- 빼기(nil)
		eq((PlayerState.setDisplay(d, 2, nil)), true)
		eq(slotsText(d), "windmill,-,bigben,arc,fountain,clocktower")
		-- 빈 칸으로 옮기면 원래 칸은 빈 칸
		eq((PlayerState.setDisplay(d, 2, "arc")), true)
		eq(slotsText(d), "windmill,arc,bigben,-,fountain,clocktower")
		-- 같은 칸에 같은 명소 = 그대로, 빈 칸 빼기 = 그대로
		eq((PlayerState.setDisplay(d, 2, "arc")), true)
		eq((PlayerState.setDisplay(d, 4, nil)), true)
		eq(slotsText(d), "windmill,arc,bigben,-,fountain,clocktower")
		-- 마지막 칸을 빼면 끝 빈 칸은 저장 안 함
		eq((PlayerState.setDisplay(d, 6, nil)), true)
		eq(table.concat(d.Display, ","), "windmill,arc,bigben,,fountain")
		checkDisplay(d)
		eq(d.Settings.AutoPark, false, "편집해도 자동 배치로 안 돌아감")
		-- 빈 칸에 빼 둔 명소를 다시 놓기
		eq((PlayerState.setDisplay(d, 6, "pyramid")), true)
		eq(slotsText(d), "windmill,arc,bigben,-,fountain,pyramid")
	end
)
test(
	"setDisplay 검증: 잘못된 칸·잠긴 칸·없거나 보유하지 않은 명소 (실패하면 그대로)",
	function()
		local d = owning(EIGHT)
		local before = slotsText(d)
		local badSlots = { 0, -1, 1.5, 0 / 0, math.huge, -math.huge, "1", {}, true, PlayerState.MAX_SLOTS + 1 }
		for _, bad in badSlots do
			local ok, reason = PlayerState.setDisplay(d, bad, "eiffel")
			eq(ok, false, "칸 " .. tostring(bad))
			eq(reason, "잘못된 칸입니다", "사유 " .. tostring(bad))
		end
		eq((PlayerState.setDisplay(d, nil, "eiffel")), false, "칸 nil")
		local ok, reason = PlayerState.setDisplay(d, Config.BASE_SLOTS + 1, "eiffel")
		eq(ok, false, "잠긴 칸")
		eq(reason, "잠긴 칸입니다")
		eq((PlayerState.setDisplay(d, PlayerState.MAX_SLOTS, nil)), false, "잠긴 칸 빼기")
		for _, bad in { "sphinx", "없는명소", "", 5, {}, true } do
			local okId, reasonId = PlayerState.setDisplay(d, 1, bad)
			eq(okId, false, "명소 " .. tostring(bad))
			eq(reasonId, "보유하지 않은 명소입니다")
		end
		eq(d.Settings.AutoPark, true, "실패하면 자동 배치 그대로")
		eq(slotsText(d), before, "실패하면 배치 그대로")
		eq(#d.Display, 0)
		-- 모르는 명소 Id 는 Inventory 에 있어도(명소를 잠시 뺀 경우) 놓을 수 없음
		d.Inventory.removed_one = 3
		eq((PlayerState.setDisplay(d, 1, "removed_one")), false, "모르는 명소")
		-- 공원 확장 뒤에는 열린 칸
		d.Upgrades.Park = 1
		eq((PlayerState.setDisplay(d, Config.BASE_SLOTS + 1, "eiffel")), true, "새로 열린 칸")
	end
)
test("자동 배치 다시 켜기(autoPark / setSetting) · 끄기", function()
	local d = owning(EIGHT)
	PlayerState.setDisplay(d, 1, "clocktower")
	PlayerState.setDisplay(d, 2, nil)
	PlayerState.autoPark(d)
	eq(d.Settings.AutoPark, true)
	eq(slotsText(d), "pyramid,eiffel,bigben,arc,fountain,windmill", "가장 희귀한 명소들로 다시 채움")
	eq(#d.Display, 0, "직접 배치는 지움")
	-- 설정으로 끄기만 하면 지금 배치 그대로에서 시작
	eq(PlayerState.setSetting(d, "AutoPark", false), true)
	eq(d.Settings.AutoPark, false)
	eq(slotsText(d), "pyramid,eiffel,bigben,arc,fountain,windmill", "끄기만 하면 그대로")
	eq(table.concat(d.Display, ","), "pyramid,eiffel,bigben,arc,fountain,windmill")
	-- 이미 꺼져 있을 때 또 끄면 배치 유지
	PlayerState.setDisplay(d, 1, "clocktower")
	eq(PlayerState.setSetting(d, "AutoPark", false), true)
	eq(slotsText(d), "clocktower,eiffel,bigben,arc,fountain,windmill")
	eq(PlayerState.setSetting(d, "AutoPark", true), true)
	eq(slotsText(d), "pyramid,eiffel,bigben,arc,fountain,windmill")
	eq(PlayerState.setSetting(d, "AutoPark", "no"), false, "타입 검사")
	eq(d.Settings.AutoPark, true)
end)
test("직접 배치: 이번 판에 처음 얻은 명소는 첫 빈 칸에, 빈 칸이 없으면 안 놓임", function()
	local d = owning({ "clocktower", "lighthouse" })
	eq(PlayerState.setSetting(d, "AutoPark", false), true)
	eq(slotsText(d), "lighthouse,clocktower,-,-,-,-")
	PlayerState.setDisplay(d, 1, nil)
	PlayerState.applyRoll(d, Landmarks.ById.windmill)
	eq(slotsText(d), "windmill,clocktower,-,-,-,-", "첫 빈 칸(칸 번호 순서)")
	PlayerState.applyRoll(d, Landmarks.ById.fountain)
	eq(slotsText(d), "windmill,clocktower,fountain,-,-,-")
	-- 이미 가진 명소를 또 얻으면 새로 놓지 않음(빼 둔 명소는 계속 빠져 있음)
	PlayerState.setDisplay(d, 1, nil)
	PlayerState.applyRoll(d, Landmarks.ById.windmill)
	eq(slotsText(d), "-,clocktower,fountain,-,-,-", "두 번째부터는 안 놓음")
	eq(d.Inventory.windmill, 2)
	-- 빈 칸을 다 채운 뒤에는 더 희귀한 명소를 얻어도 자동으로 바꾸지 않음
	for _, id in { "arc", "bigben", "eiffel", "pyramid" } do
		PlayerState.applyRoll(d, Landmarks.ById[id])
	end
	eq(slotsText(d), "arc,clocktower,fountain,bigben,eiffel,pyramid")
	PlayerState.applyRoll(d, Landmarks.ById.sphinx)
	eq(slotsText(d), "arc,clocktower,fountain,bigben,eiffel,pyramid", "빈 칸 없음")
	eq(d.Inventory.sphinx, 1)
	checkDisplay(d)
	-- 자동 배치에서는 Display 를 안 건드림
	eq(#owning(EIGHT).Display, 0)
end)
test(
	"직접 배치: 공원 확장으로 새로 열린 칸은 전시 안 된 명소 중 희귀한 순서로 채움",
	function()
		local d = owning(EIGHT)
		PlayerState.setDisplay(d, 1, "clocktower") -- 피라미드·등대가 빠짐
		d.Coins = 1e9
		eq((PlayerState.buyUpgrade(d, "Park")), true)
		eq(PlayerState.slots(d), Config.BASE_SLOTS + 3)
		eq(slotsText(d), "clocktower,eiffel,bigben,arc,fountain,windmill,pyramid,lighthouse,-")
		checkDisplay(d)
		-- 원래 열려 있던 빈 칸(2번, 9번)은 확장해도 안 채움. 새로 열린 칸(10~12번)에만
		-- 전시 안 된 명소(빼 둔 에펠탑 포함) 중 희귀한 순서로
		PlayerState.setDisplay(d, 2, nil)
		eq((PlayerState.buyUpgrade(d, "Park")), true)
		eq(slotsText(d), "clocktower,-,bigben,arc,fountain,windmill,pyramid,lighthouse,-,eiffel,-,-")
		checkDisplay(d)
		-- 새로 얻은 명소는 첫 빈 칸(2번)
		PlayerState.applyRoll(d, Landmarks.ById.sphinx)
		eq(
			slotsText(d),
			"clocktower,sphinx,bigben,arc,fountain,windmill,pyramid,lighthouse,-,eiffel,-,-",
			"새 명소는 첫 빈 칸"
		)
		-- 자동 배치면 그냥 희귀한 순서(Display 안 씀)
		local a = owning(EIGHT)
		a.Coins = 1e9
		PlayerState.buyUpgrade(a, "Park")
		eq(slotsText(a), "pyramid,eiffel,bigben,arc,fountain,windmill,lighthouse,clocktower,-")
		eq(#a.Display, 0)
	end
)
test("환생: 직접 배치를 비우고 자동 배치로 되돌림 (다른 설정은 유지)", function()
	local d = owning({ "eiffel", "liberty", "clocktower" })
	PlayerState.setDisplay(d, 2, "clocktower")
	d.Settings.AutoFeature = false
	eq(d.Settings.AutoPark, false)
	d.Coins = Config.REBIRTHS[1].Coins
	eq((PlayerState.rebirth(d)), true)
	eq(#d.Display, 0, "배치 비움")
	eq(d.Settings.AutoPark, true, "자동 배치로")
	eq(d.Settings.AutoFeature, false, "다른 설정은 유지")
	eq(slotsText(d), "-,-,-,-,-,-")
	-- 환생 뒤에는 희귀한 순서로 자동 전시: 흔한 명소를 먼저 얻어도 더 희귀한 명소가 앞 칸으로
	PlayerState.applyRoll(d, Landmarks.ById.windmill)
	PlayerState.applyRoll(d, Landmarks.ById.eiffel)
	eq(slotsText(d), "eiffel,windmill,-,-,-,-")
	eq(#d.Display, 0, "자동 배치는 Display 를 안 씀")
	-- 원래 자동 배치였어도 그대로 자동
	local a = owning({ "eiffel", "liberty" })
	a.Coins = Config.REBIRTHS[1].Coins
	PlayerState.rebirth(a)
	eq(a.Settings.AutoPark, true)
	-- 환생 실패면 설정도 그대로
	local f = owning({ "clocktower" })
	PlayerState.setDisplay(f, 1, nil)
	eq((PlayerState.rebirth(f)), false)
	eq(f.Settings.AutoPark, false, "실패하면 그대로")
end)
test("setDisplay 옮기는 명소의 원래 칸 확인(expectedFrom): 밀려난 명소를 옮기면 stale", function()
	-- 자동 배치, 6칸이 꽉 참. 클라이언트는 6번 칸 명소를 집어 1번으로 옮기려는 화면을 보고 있음
	local ids = {}
	for i = #Landmarks.RarestFirst, 1, -1 do
		local id = Landmarks.RarestFirst[i].Id
		table.insert(ids, id)
		if #ids == 6 then
			break
		end
	end
	local d = owning(ids)
	PlayerState.setAutoPark(d, true)
	local view = PlayerState.parkSlots(d)
	local carried, target = view[6], view[1]
	-- 그 사이 서버에서 가장 희귀한 명소가 나와 자동 배치가 한 칸씩 밀림 -> 6번 명소는 전시에서 빠짐
	PlayerState.applyRoll(d, Landmarks.RarestFirst[1])
	local now = PlayerState.parkSlots(d)
	local before = {}
	for slot = 1, 6 do
		before[slot] = now[slot] or "-"
	end
	-- 옛 화면 기준(6번에서 집음)이면 거절, 아무것도 안 바뀜 (예전에는 1번 명소가 빠져 버렸음)
	local ok, reason = PlayerState.setDisplay(d, 1, carried, now[1] or "", 6)
	eq(ok, false)
	eq(reason, "stale")
	eq(d.Settings.AutoPark, true, "거절하면 자동 배치도 그대로")
	local after = PlayerState.parkSlots(d)
	for slot = 1, 6 do
		eq(after[slot] or "-", before[slot], "칸 " .. slot)
	end
	-- 지금 화면 기준(전시 안 됨 = 0)이면 받아들임: 1번에 놓이고 1번에 있던 명소는 밀려남
	eq((PlayerState.setDisplay(d, 1, carried, now[1] or "", 0)), true)
	eq(PlayerState.parkSlots(d)[1], carried)
	-- 전시 중인 명소를 옮길 때: 본 칸이 맞으면 자리 바꿈
	local shown = PlayerState.parkSlots(d)
	eq((PlayerState.setDisplay(d, 2, shown[1], shown[2] or "", 1)), true)
	eq(PlayerState.parkSlots(d)[2], carried)
	-- 이상한 값은 stale
	eq(select(2, PlayerState.setDisplay(d, 3, carried, PlayerState.parkSlots(d)[3] or "", "2")), "stale")
	eq(target ~= nil, true)
end)
test(
	"setDisplay 본 칸 확인(expected): 화면이 늦으면 stale 로 거절하고 아무것도 안 바꿈",
	function()
		-- 직접 배치에서 3번 칸을 비움(등대를 뺌). 클라이언트는 3번이 빈 칸인 화면을 보고 있음
		local d = owning({ "clocktower", "lighthouse", "windmill", "fountain" })
		PlayerState.setDisplay(d, 3, nil)
		eq(slotsText(d), "fountain,windmill,-,clocktower,-,-")
		local seen = PlayerState.snapshot(d, 1) -- 클라이언트가 가진 옛 상태
		-- 그 사이 서버에서 자동 굴림이 새 명소를 첫 빈 칸(3번)에 놓음
		PlayerState.applyRoll(d, Landmarks.ById.eiffel)
		eq(slotsText(d), "fountain,windmill,eiffel,clocktower,-,-")
		-- 옛 화면 기준(3번 = 빈 칸)으로 3번에 놓기/빼기 -> 거절, 방금 놓인 에펠탑은 그대로
		local before = table.concat(d.Display, ",")
		local ok, reason = PlayerState.setDisplay(d, 3, "lighthouse", "")
		eq(ok, false)
		eq(reason, "stale")
		eq((PlayerState.setDisplay(d, 3, nil, "")), false, "빼기도 확인")
		eq(table.concat(d.Display, ","), before, "거절하면 그대로")
		eq(slotsText(seen), "fountain,windmill,-,clocktower,-,-", "옛 상태")
		-- 지금 보이는 것과 같으면 그대로 적용 (빈 칸 = "")
		eq((PlayerState.setDisplay(d, 3, "clocktower", "eiffel")), true, "새 화면 기준")
		eq(slotsText(d), "fountain,windmill,clocktower,eiffel,-,-", "자리 바꿈")
		eq((PlayerState.setDisplay(d, 6, "eiffel", "")), true, "빈 칸 확인")
		eq(slotsText(d), "fountain,windmill,clocktower,-,-,eiffel")
		checkDisplay(d)
		-- 자동 배치에서도 보이는 칸 기준, 거절하면 자동 배치 그대로
		local a = owning(EIGHT)
		eq((PlayerState.setDisplay(a, 1, "clocktower", "eiffel")), false, "1번은 피라미드")
		eq(a.Settings.AutoPark, true, "거절하면 자동 배치 그대로")
		eq(#a.Display, 0)
		eq((PlayerState.setDisplay(a, 1, "clocktower", "pyramid")), true)
		eq(a.Settings.AutoPark, false)
		-- 문자열이 아닌 expected 는 거절, nil 은 확인 안 함(서버 내부 · 옛 클라이언트)
		for _, bad in { 5, true, {} } do
			eq((PlayerState.setDisplay(a, 2, nil, bad)), false, "expected " .. tostring(bad))
		end
		eq((PlayerState.setDisplay(a, 2, nil)), true, "expected 없음")
		-- 칸·명소 검사가 먼저
		eq(select(2, PlayerState.setDisplay(a, 99, nil, "x")), "잘못된 칸입니다")
		eq(select(2, PlayerState.setDisplay(a, 1, "sphinx", "clocktower")), "보유하지 않은 명소입니다")
	end
)
test(
	"집어서 옮기기(고른 칸의 명소를 다른 칸에 놓기): 빈 칸이면 옮기고, 명소가 있으면 자리 바꿈",
	function()
		-- 배치 창: 명소가 있는 칸을 고른 뒤 다른 열린 칸을 누르면 setDisplay(누른 칸, 고른 칸의 명소, 누른 칸에 보이던 것)
		local d = owning(EIGHT)
		PlayerState.setDisplay(d, 6, nil)
		eq(slotsText(d), "pyramid,eiffel,bigben,arc,fountain,-")
		local function drop(from: number, to: number): boolean
			local slots = PlayerState.parkSlots(d)
			return (PlayerState.setDisplay(d, to, slots[from], slots[to] or ""))
		end
		eq(drop(1, 6), true, "빈 칸으로")
		eq(slotsText(d), "-,eiffel,bigben,arc,fountain,pyramid", "옮긴 칸은 빈 칸")
		eq(drop(2, 6), true, "명소가 있는 칸으로")
		eq(slotsText(d), "-,pyramid,bigben,arc,fountain,eiffel", "두 칸 자리 바꿈")
		eq(drop(5, 1), true)
		eq(slotsText(d), "fountain,pyramid,bigben,arc,-,eiffel")
		checkDisplay(d)
		local income = PlayerState.incomePerSecond(d)
		eq(drop(3, 4), true)
		near(PlayerState.incomePerSecond(d), income, 1e-9, "옮기기만 하면 수입 그대로")
	end
)
test(
	"betterHidden: 직접 배치에서 전시 칸의 가장 약한 명소보다 수입이 큰 전시 안 된 명소",
	function()
		-- 자동 배치면 늘 빈 목록
		eq(#PlayerState.betterHidden(owning(EIGHT)), 0, "자동 배치")
		eq(#PlayerState.betterHidden(PlayerState.new()), 0, "빈 데이터")
		-- 흔한 명소 6개로 공원을 채운 뒤 더 희귀한 명소를 얻으면 전시 안 됨 -> 목록에
		local d = owning({ "clocktower", "lighthouse", "windmill", "fountain", "arc", "bigben" })
		eq((PlayerState.setSetting(d, "AutoPark", false)), true)
		eq(#PlayerState.betterHidden(d), 0, "다 전시 중")
		PlayerState.applyRoll(d, Landmarks.ById.eiffel)
		PlayerState.applyRoll(d, Landmarks.ById.pyramid)
		eq(slotsText(d), "bigben,arc,fountain,windmill,lighthouse,clocktower", "꽉 차서 안 놓임")
		eq(table.concat(PlayerState.betterHidden(d), ","), "pyramid,eiffel", "희귀한 순서")
		-- 수입이 가장 약한 명소와 같거나 작으면 안 셈: 같은 등급 흔한 명소를 또 하나 얻어도(★1) 그대로
		PlayerState.applyRoll(d, Landmarks.ById.harbourbridge)
		eq(table.concat(PlayerState.betterHidden(d), ","), "pyramid,eiffel", "약한 명소와 같으면 안 셈")
		-- 전시하면 빠짐
		PlayerState.setDisplay(d, 6, "pyramid")
		eq(table.concat(PlayerState.betterHidden(d), ","), "eiffel")
		-- 스냅샷으로도 같은 값
		eq(table.concat(PlayerState.betterHidden(PlayerState.snapshot(d, 1)), ","), "eiffel", "snapshot")
		-- 일부러 뺀 약한 명소는 안 셈(빈 칸은 기준이 아님), 전시가 하나도 없으면 수입이 있는 명소 전부
		local e = owning({ "clocktower", "eiffel" })
		PlayerState.setDisplay(e, 2, nil)
		eq(slotsText(e), "eiffel,-,-,-,-,-")
		eq(#PlayerState.betterHidden(e), 0, "약한 명소를 뺀 건 안 셈")
		PlayerState.setDisplay(e, 1, nil)
		eq(table.concat(PlayerState.betterHidden(e), ","), "eiffel,clocktower", "전시 없음")
		-- 자동 배치로 돌아가면 빈 목록
		PlayerState.autoPark(d)
		eq(#PlayerState.betterHidden(d), 0)
	end
)
test(
	"missedByFullPark: 직접 배치 중 처음 얻은 명소가 빈 칸이 없어 전시 못 됨 = 공원 꽉 참 알림",
	function()
		-- 자동 배치면 늘 false (공원이 꽉 차도 희귀한 순서로 알아서 바뀜)
		local a = owning({ "clocktower", "lighthouse", "windmill", "fountain", "arc", "bigben" })
		PlayerState.applyRoll(a, Landmarks.ById.harbourbridge)
		eq(PlayerState.missedByFullPark(a, "harbourbridge"), false, "자동 배치")
		-- 직접 배치 + 꽉 참: 더 좋은 명소든 같은 흔한 명소든 처음 얻어서 못 놓였으면 true
		local d = owning({ "clocktower", "lighthouse", "windmill", "fountain", "arc", "bigben" })
		PlayerState.setSetting(d, "AutoPark", false)
		PlayerState.applyRoll(d, Landmarks.ById.eiffel)
		eq(PlayerState.missedByFullPark(d, "eiffel"), true, "더 좋은 명소")
		PlayerState.applyRoll(d, Landmarks.ById.harbourbridge)
		eq(PlayerState.missedByFullPark(d, "harbourbridge"), true, "흔한 명소도")
		eq(PlayerState.missedByFullPark(PlayerState.snapshot(d, 1), "eiffel"), true, "snapshot")
		-- 두 번째로 얻은 명소(★ 오름)는 "처음" 이 아니라 false
		PlayerState.applyRoll(d, Landmarks.ById.eiffel)
		eq(PlayerState.missedByFullPark(d, "eiffel"), false, "두 번째")
		-- 전시 중인 명소 · 빈 칸이 있어 놓인 명소는 false
		eq(PlayerState.missedByFullPark(d, "bigben"), false, "이미 전시 중")
		local e = owning({ "clocktower", "fountain" })
		PlayerState.setDisplay(e, 2, nil)
		PlayerState.applyRoll(e, Landmarks.ById.pyramid)
		eq(slotsText(e), "fountain,pyramid,-,-,-,-", "빈 칸에 놓임")
		eq(PlayerState.missedByFullPark(e, "pyramid"), false, "놓였음")
		eq(PlayerState.missedByFullPark(e, "sphinx"), false, "보유 안 함")
	end
)
test(
	"수입 = 전시 칸에 있는 명소 합 (자리만 바꾸면 그대로, 빼거나 바꾸면 줄어듦)",
	function()
		local d = owning(EIGHT)
		near(PlayerState.incomePerSecond(d), slotIncome(d), 1e-9, "자동")
		local auto = PlayerState.incomePerSecond(d)
		PlayerState.setDisplay(d, 6, "pyramid") -- 1번 피라미드 <-> 6번 풍차
		eq(slotsText(d), "windmill,eiffel,bigben,arc,fountain,pyramid")
		near(PlayerState.incomePerSecond(d), auto, 1e-9, "자리만 바뀜")
		PlayerState.setDisplay(d, 4, "clocktower") -- 개선문(도시 명소) 대신 시계탑(일반)
		near(PlayerState.incomePerSecond(d), slotIncome(d), 1e-9, "바꿈")
		assert(PlayerState.incomePerSecond(d) < auto, "덜 희귀한 명소로 바꾸면 수입 감소")
		PlayerState.setDisplay(d, 2, nil)
		near(PlayerState.incomePerSecond(d), slotIncome(d), 1e-9, "뺌")
		-- 입장료 배율도 같은 합에 곱해짐, 스냅샷 수입도 같은 값
		d.Upgrades.Ticket = 2
		near(PlayerState.incomePerSecond(d), slotIncome(d) * (1 + 2 * PlayerState.UpgradesById.Ticket.PerLevel), 1e-9)
		near(PlayerState.snapshot(d, 1).Income, PlayerState.incomePerSecond(d), 1e-9, "snapshot")
		-- 다 빼면 0
		for slot = 1, Config.BASE_SLOTS do
			PlayerState.setDisplay(d, slot, nil)
		end
		eq(PlayerState.incomePerSecond(d), 0, "빈 공원")
		eq(#d.Display, 0)
	end
)
test("snapshot: 배치 복사본 + 자동 배치 설정 (옛 서버 스냅샷은 자동 배치로)", function()
	local d = owning(EIGHT)
	PlayerState.setDisplay(d, 1, "clocktower")
	local s = PlayerState.snapshot(d, 1)
	eq(s.Settings.AutoPark, false)
	eq(s.Display[1], "clocktower")
	eq(slotsText(s), slotsText(d), "스냅샷으로 parkSlots")
	s.Display[1] = "pyramid"
	s.Settings.AutoPark = true
	eq(d.Display[1], "clocktower", "원본 Display 불변")
	eq(d.Settings.AutoPark, false, "원본 설정 불변")
	local old: any = PlayerState.snapshot(owning(EIGHT), 2)
	old.Display = nil
	old.Settings.AutoPark = nil
	eq(slotsText(old), "pyramid,eiffel,bigben,arc,fountain,windmill")
	-- 스냅샷 사본에 편집을 미리 적용해 볼 수 있음(클라이언트 미리보기)
	local preview: any = PlayerState.snapshot(d, 3)
	eq((PlayerState.setDisplay(preview, 2, "pyramid")), true)
	eq(slotsText(preview), "clocktower,pyramid,bigben,arc,fountain,windmill")
	eq(slotsText(d), "clocktower,eiffel,bigben,arc,fountain,windmill", "원본 불변")
end)

print("\n[ParkGrid — 3D 배치 모드]")
local ParkGrid = Harness.require(shared.ParkGrid)

test(
	"slotOffset: 예전 ParkService 받침대 자리 그대로(간격 12, 입구 여백 6), 입구 줄 가운데가 1번",
	function()
		local grid = Config.PARK_GRID
		for slot = 1, PlayerState.MAX_SLOTS do
			local row, column = PlayerState.slotCell(slot)
			local x, z = ParkGrid.slotOffset(slot)
			near(x, ((grid + 1) / 2 - column) * 12, 1e-9, "x " .. slot)
			near(z, -80 / 2 + 6 + 6 + (row - 1) * 12, 1e-9, "z " .. slot)
		end
		-- 1번 = 입구 줄(가장 작은 z) 가운데 오른쪽(입구에서 볼 때) = -X 쪽 가운데 칸
		local x1, z1 = ParkGrid.slotOffset(1)
		eq(x1, -6, "1번 x")
		eq(z1, -28, "1번 z")
		local x2 = ParkGrid.slotOffset(2)
		eq(x2, 6, "2번 = 가운데 왼쪽")
	end
)

test(
	"slotAt: 칸 가운데·칸 안은 그 칸, 격자 밖·반지름 밖은 nil (가장 가까운 칸으로 붙기)",
	function()
		for slot = 1, PlayerState.MAX_SLOTS do
			local x, z = ParkGrid.slotOffset(slot)
			eq(ParkGrid.slotAt(x, z), slot, "가운데 " .. slot)
			-- 칸 한 변(12) 안쪽 네 귀퉁이 근처도 그 칸
			for _, d in { { 5.9, 5.9 }, { -5.9, 5.9 }, { 5.9, -5.9 }, { -5.9, -5.9 }, { 0, 5.99 } } do
				eq(ParkGrid.slotAt(x + d[1], z + d[2]), slot, "칸 안 " .. slot)
			end
			-- 반지름을 좁히면 받침대 밖은 nil
			eq(ParkGrid.slotAt(x + 5.5, z, 5), nil, "좁은 반지름 " .. slot)
		end
		-- 두 칸 사이 경계: 더 가까운 쪽
		local ax, az = ParkGrid.slotOffset(1)
		eq(ParkGrid.slotAt(ax - 5.9, az), 1, "경계 안쪽")
		eq(ParkGrid.slotAt(ax + 6.1, az), 2, "경계 너머 = 이웃 칸")
		-- 격자 바깥: 맨 앞 줄보다 입구 쪽으로 10 스터드면 nil, 3 스터드면 가장 가까운 앞 줄 칸
		eq(ParkGrid.slotAt(ax, az - 10), nil, "입구 쪽 멀리")
		eq(ParkGrid.slotAt(ax, az - 8), 1, "입구 쪽 가까이 = 앞 줄")
		eq(ParkGrid.slotAt(0, 500), nil, "아주 멀리")
		eq(ParkGrid.slotAt(0 / 0, 0), nil, "NaN")
		-- 부지 가운데(x 0)는 두 가운데 열의 경계 — 어느 쪽이든 칸이 나옴
		assert(ParkGrid.slotAt(0, 2) ~= nil, "부지 가운데")
	end
)

test("onPlot: 부지 바닥(76×80) + 여유", function()
	eq(ParkGrid.onPlot(0, 0), true)
	eq(ParkGrid.onPlot(37.9, 39.9), true, "모서리 안")
	eq(ParkGrid.onPlot(38.5, 0), false, "옆으로 벗어남")
	eq(ParkGrid.onPlot(38.5, 0, 2), true, "여유 안")
	eq(ParkGrid.onPlot(0, -41, 2), true, "입구 앞 여유")
	eq(ParkGrid.onPlot(0, -43), false, "입구 밖")
end)

test(
	"look / slotOf / storage: 칸 모습, 전시 칸, 보관함 = 전시 안 된 보유 명소(희귀한 순서)",
	function()
		local d = owning(EIGHT)
		-- 자동 배치(6칸): 가장 흔한 둘이 보관함
		eq(ParkGrid.look(d, 1), "pyramid")
		eq(ParkGrid.look(d, 7), ParkGrid.LOOK_LOCKED, "잠긴 칸")
		eq(table.concat(ParkGrid.storage(d), ","), "lighthouse,clocktower", "자동: 남는 흔한 명소")
		eq(ParkGrid.slotOf(d, "eiffel"), 2)
		eq(ParkGrid.slotOf(d, "clocktower"), 0, "전시 안 됨 = 0")
		-- 직접 배치로 3번(빅벤)을 빼면 빈 칸 + 보관함 맨 앞(더 희귀)
		eq((PlayerState.setDisplay(d, 3, nil)), true)
		eq(ParkGrid.look(d, 3), ParkGrid.LOOK_EMPTY)
		eq(table.concat(ParkGrid.storage(d), ","), "bigben,lighthouse,clocktower", "희귀한 순서")
		-- 보유하지 않은 명소는 보관함에 없음, 빈 데이터 = 빈 보관함
		eq(#ParkGrid.storage(PlayerState.new()), 0)
		-- 스냅샷으로도 같음
		eq(table.concat(ParkGrid.storage(PlayerState.snapshot(d, 1)), ","), "bigben,lighthouse,clocktower")
	end
)

test(
	"dropPlan / storePlan: 옮기기·자리 바꾸기·보관함에서 놓기·바꿔 넣기·제자리·잠긴 칸",
	function()
		local d = owning(EIGHT)
		eq((PlayerState.setDisplay(d, 3, nil)), true) -- 1 pyramid, 2 eiffel, 3 빈 칸, 4 arc, 5 fountain, 6 windmill
		local function plan(id, target)
			local p = ParkGrid.dropPlan(d, id, target)
			return string.format("%s %d %s %d %s %s", p.Kind, p.Slot, p.Id, p.From, p.Expected, p.Partner or "-")
		end
		eq(plan("eiffel", 3), "move 3 eiffel 2  -", "빈 칸으로 옮김")
		eq(plan("eiffel", 1), "swap 1 eiffel 2 pyramid pyramid", "자리 바꿈")
		eq(plan("eiffel", 2), "cancel 2 eiffel 2 eiffel -", "제자리")
		eq(plan("bigben", 3), "place 3 bigben 0  -", "보관함에서 빈 칸")
		eq(plan("bigben", 4), "replace 4 bigben 0 arc arc", "보관함에서 바꿔 넣기")
		eq(ParkGrid.dropPlan(d, "eiffel", 7).Kind, "locked", "잠긴 칸")
		eq(ParkGrid.dropPlan(d, "eiffel", 40).Kind, "cancel", "격자 밖 번호")
		eq(ParkGrid.dropPlan(d, "eiffel", 0).Kind, "cancel", "0번")
		-- 계획 그대로 setDisplay 하면 그대로 됨(stale 아님), 자리 바꿈 상대는 원래 칸으로
		local p = ParkGrid.dropPlan(d, "eiffel", 1)
		eq((PlayerState.setDisplay(d, p.Slot, p.Id, p.Expected, p.From)), true)
		eq(slotsText(d), "eiffel,pyramid,-,arc,fountain,windmill")
		local r = ParkGrid.dropPlan(d, "bigben", 4)
		eq((PlayerState.setDisplay(d, r.Slot, r.Id, r.Expected, r.From)), true)
		eq(slotsText(d), "eiffel,pyramid,-,bigben,fountain,windmill")
		eq(table.concat(ParkGrid.storage(d), ","), "arc,lighthouse,clocktower", "밀려난 명소는 보관함")
		-- 보관: 전시 중이면 그 칸을 비우는 계획, 보관함에 있으면 nil
		local s = ParkGrid.storePlan(d, "pyramid")
		assert(s, "보관 계획")
		eq(s.Slot, 2)
		eq(s.Expected, "pyramid")
		eq(ParkGrid.storePlan(d, "arc"), nil)
		eq((PlayerState.setDisplay(d, s.Slot, nil, s.Expected)), true)
		eq(ParkGrid.look(d, 2), ParkGrid.LOOK_EMPTY)
		-- 들고 있는 사이 자동 굴림으로 자리가 밀리면(자동 배치) From 은 지금 화면 기준으로 다시 셈
		local a = owning(EIGHT)
		eq(ParkGrid.dropPlan(a, "arc", 1).From, 4)
		PlayerState.applyRoll(a, Landmarks.RarestFirst[1])
		eq(ParkGrid.dropPlan(a, "arc", 1).From, 5, "한 칸 밀림")
	end
)

test("autoWouldChange / preview: 자동을 켜면 바뀌는지, 사본 미리 보기(원본 불변)", function()
	local d = owning(EIGHT)
	eq(ParkGrid.autoWouldChange(d), false, "자동 배치 그대로")
	PlayerState.setAutoPark(d, false)
	eq(ParkGrid.autoWouldChange(d), false, "끄기만 하면 같은 배치")
	local s: any = PlayerState.snapshot(d, 1)
	local moved = ParkGrid.preview(s, function(copy)
		return (PlayerState.setDisplay(copy, 1, "clocktower"))
	end)
	assert(moved, "미리 보기")
	eq(slotsText(moved), "clocktower,eiffel,bigben,arc,fountain,windmill")
	eq(slotsText(s), "pyramid,eiffel,bigben,arc,fountain,windmill", "원본 불변")
	assert(moved.Income < s.Income, "미리 보기 수입도 다시 셈")
	eq(ParkGrid.autoWouldChange(moved), true, "직접 바꾼 배치")
	eq(
		ParkGrid.preview(s, function(copy)
			return (PlayerState.setDisplay(copy, 30, "clocktower"))
		end),
		nil,
		"규칙에 안 맞으면 nil"
	)
end)

test(
	"topView: 맞출 줄(기본 6줄 = 36칸)이 HUD 가 가리지 않은 영역 안에 딱 맞게(PC·휴대폰·태블릿·세로 화면), 줄 수, 휠 배율",
	function()
		local cases = {
			{ Aspect = 16 / 9, Fov = 70, Top = 0.06, Bottom = 0.24, Left = 0.03, Right = 0.03 },
			{ Aspect = 667 / 375, Fov = 70, Top = 0.12, Bottom = 0.3, Left = 0.03, Right = 0.03 },
			{ Aspect = 844 / 390, Fov = 70, Top = 0.11, Bottom = 0.29, Left = 0.03, Right = 0.2 },
			{ Aspect = 4 / 3, Fov = 70, Top = 0.05, Bottom = 0.2, Left = 0.03, Right = 0.03 },
			{ Aspect = 0.6, Fov = 70, Top = 0.05, Bottom = 0.2, Left = 0.03, Right = 0.03 },
			{ Aspect = 16 / 9, Fov = 50, Top = 0, Bottom = 0, Left = 0, Right = 0 },
			{ Aspect = 667 / 375, Fov = 70, Top = 0.12, Bottom = 0.3, Left = 0.03, Right = 0.03, Rows = 2 },
			{ Aspect = 844 / 390, Fov = 70, Top = 0.11, Bottom = 0.29, Left = 0.03, Right = 0.03, Rows = 1 },
			{ Aspect = 16 / 9, Fov = 70, Top = 0.06, Bottom = 0.24, Left = 0.03, Right = 0.03, Rows = 4 },
		}
		local function extent(view, case, distance)
			local minX, maxX, minY, maxY = math.huge, -math.huge, math.huge, -math.huge
			for _, point in ParkGrid.topFitPoints(case.Rows) do
				local x, y = ParkGrid.project(point, view.Target[1], view.Target[3], distance, case.Aspect, case.Fov)
				assert(x and y, "카메라 앞")
				minX, maxX = math.min(minX, x), math.max(maxX, x)
				minY, maxY = math.min(minY, y), math.max(maxY, y)
			end
			return minX, maxX, minY, maxY
		end
		for index, case in cases do
			local view = ParkGrid.topView(case)
			local left, right = -1 + 2 * case.Left, 1 - 2 * case.Right
			local bottom, top = -1 + 2 * case.Bottom, 1 - 2 * case.Top
			local minX, maxX, minY, maxY = extent(view, case, view.Distance)
			local tag = "경우 " .. index
			assert(minX >= left - 0.01 and maxX <= right + 0.01, tag .. ": 가로가 영역 안")
			assert(minY >= bottom - 0.01 and maxY <= top + 0.01, tag .. ": 세로가 영역 안")
			-- 딱 맞음: 한쪽 방향은 영역을 거의 다 씀, 다른 방향은 영역 가운데
			local fillX, fillY = (maxX - minX) / (right - left), (maxY - minY) / (top - bottom)
			assert(math.max(fillX, fillY) > 0.97, tag .. ": 가장 크게")
			near((minX + maxX) / 2, (left + right) / 2, 0.02, tag .. ": 가로 가운데")
			near((minY + maxY) / 2, (bottom + top) / 2, 0.02, tag .. ": 세로 가운데")
			-- 카메라 = 바라보는 곳에서 입구 쪽 위로 TOP_PITCH 만큼 (부지 바닥 위, 입구 쪽)
			near(view.Eye[2] - view.Target[2], math.sin(ParkGrid.TOP_PITCH) * view.Distance, 1e-6, tag)
			near(view.Target[3] - view.Eye[3], math.cos(ParkGrid.TOP_PITCH) * view.Distance, 1e-6, tag)
			near(view.Eye[1], view.Target[1], 1e-9, tag)
		end
		-- 쓰는 줄만 맞추면 더 가까이(명소가 크게): 2줄 < 4줄 < 6줄
		local function distance(rows)
			return ParkGrid.topView({ Aspect = 16 / 9, Fov = 70, Top = 0.06, Bottom = 0.24, Rows = rows }).Distance
		end
		assert(distance(2) < distance(4) and distance(4) < distance(6), "줄이 적으면 가까이")
		near(distance(nil), distance(6), 1e-9, "기본 = 6줄")
		eq(ParkGrid.topRows(0), 1, "칸 없음 = 첫 줄")
		eq(ParkGrid.topRows(6), 2, "한 줄 꽉 참 + 잠긴 줄")
		eq(ParkGrid.topRows(7), 3, "둘째 줄 한 칸")
		eq(ParkGrid.topRows(30), 6, "다섯 줄 + 잠긴 줄")
		eq(ParkGrid.topRows(36), 6, "최대")
		-- 오른쪽을 가리면 격자가 화면 왼쪽으로: 화면 오른쪽 = 부지 -X 라서 카메라가 부지 -X 쪽으로 비킴
		local open = ParkGrid.topView(cases[2])
		local shifted =
			ParkGrid.topView({ Aspect = 667 / 375, Fov = 70, Top = 0.12, Bottom = 0.3, Left = 0.03, Right = 0.3 })
		assert(shifted.Target[1] < open.Target[1] - 1, "오른쪽이 가려지면 비켜 감")
		-- 휠: 배율만큼 멀어지고(범위 안), 가까이 가도 가운데는 그대로
		local far = ParkGrid.topView({ Aspect = 16 / 9, Fov = 70, Top = 0.06, Bottom = 0.24, Zoom = 1.4 })
		local base = ParkGrid.topView({ Aspect = 16 / 9, Fov = 70, Top = 0.06, Bottom = 0.24 })
		near(far.Distance, base.Distance * 1.4, 1e-6, "멀리")
		assert(
			ParkGrid.topView({ Aspect = 16 / 9, Fov = 70, Zoom = 0.01 }).Distance >= ParkGrid.TOP_MIN_DISTANCE,
			"최소 거리"
		)
		-- 가리는 비율이 말이 안 돼도(1 이상) 멈추지 않고 숫자가 나옴
		local odd = ParkGrid.topView({ Aspect = 16 / 9, Fov = 70, Top = 0.9, Bottom = 0.9 })
		assert(odd.Distance == odd.Distance and odd.Distance <= ParkGrid.TOP_MAX_DISTANCE, "이상한 여백")
	end
)

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

print("\n[ParkLayout / Scenery]")
-- 서버 쪽 순수 모듈(Instance 없이 숫자만): 부지 배치 기준 + 주변 풍경 배치 계획
local server = Harness.folder("src/server")
local ParkLayout = Harness.require(server.ParkLayout)
local SceneryPlan = Harness.require(server.Scenery.Plan)
local SceneryRng = Harness.require(server.Scenery.Rng)

-- 부지 좌표(lx, lz) → 월드 (x, z)
local function plotPoint(footprint, lx: number, lz: number): (number, number)
	return footprint.CenterX + footprint.RightX * lx + footprint.DirX * lz,
		footprint.CenterZ + footprint.RightZ * lx + footprint.DirZ * lz
end

-- 막힌 이유("plot" 등) 또는 "free"
local function blockedWhy(x: number, z: number, pad: number?): string
	local hit, why = ParkLayout.blocked(x, z, pad)
	return if hit then why or "?" else "free"
end

test(
	"ParkLayout: 부지 8칸 위치·방향은 예전 ParkService 식(247.5 + 45i 도, 입구 반지름 115) 그대로",
	function()
		eq(#ParkLayout.LAYOUT, 8, "부지 수")
		for i, footprint in ParkLayout.footprints() do
			local angle = math.rad(247.5 + 45 * (i - 1))
			near(ParkLayout.LAYOUT[i].Angle, angle, 1e-12, "각도 " .. i)
			near(footprint.CenterX, math.cos(angle) * 155, 1e-9, "중심 x " .. i)
			near(footprint.CenterZ, math.sin(angle) * 155, 1e-9, "중심 z " .. i)
			-- CFrame.lookAt(중심, 원점).RightVector = (sin a, 0, -cos a)
			near(footprint.RightX, math.sin(angle), 1e-12, "Right x " .. i)
			near(footprint.RightZ, -math.cos(angle), 1e-12, "Right z " .. i)
			eq(footprint.PathFrom, 44, "길 시작 " .. i)
			eq(footprint.PathTo, 116, "길 끝 " .. i)
			local lx, lz = ParkLayout.toLocal(footprint, plotPoint(footprint, 12, -30))
			near(lx, 12, 1e-9, "toLocal x")
			near(lz, -30, 1e-9, "toLocal z")
		end
		-- 틈 반폭: 부지 앞 모서리(r ~ 120)에서 약 7, 뒤(r ~ 200)에서 약 40
		near(ParkLayout.gapHalfWidth(120), 6.95, 0.05, "앞쪽 틈")
		near(ParkLayout.gapHalfWidth(200), 40.1, 0.1, "뒤쪽 틈")
	end
)

test(
	"ParkGrid 부지 크기 = ParkLayout 부지 크기 (클라이언트 배치 모드와 서버 받침대가 같은 자리)",
	function()
		eq(ParkGrid.PLOT_WIDTH, ParkLayout.PLOT_WIDTH, "폭")
		eq(ParkGrid.PLOT_DEPTH, ParkLayout.PLOT_DEPTH, "깊이")
		-- 모든 칸이 부지 안(받침대 반 변 5 + 여유)
		for slot = 1, PlayerState.MAX_SLOTS do
			local x, z = ParkGrid.slotOffset(slot)
			assert(ParkGrid.onPlot(x, z, -ParkGrid.PEDESTAL_SIZE / 2), "칸 " .. slot .. " 이 부지 밖")
		end
	end
)

test("ParkLayout.blocked: 부지·간판 자리·길·광장은 막고 빈 잔디는 허용", function()
	local footprint = ParkLayout.footprints()[1]
	eq(blockedWhy(plotPoint(footprint, 0, 0)), "plot", "부지 가운데")
	eq(blockedWhy(plotPoint(footprint, 39, 41)), "plot", "뒤 모서리 안")
	eq(blockedWhy(plotPoint(footprint, 41.5, 0)), "plot", "둘레 띠 + 여유 3 안")
	eq(blockedWhy(plotPoint(footprint, 43, 0)), "free", "여유 밖(틈)")
	local gx, gz = plotPoint(footprint, 43, 0)
	eq(blockedWhy(gx, gz, 1), "plot", "반지름 1 이면 여유에 걸림")
	eq(blockedWhy(plotPoint(footprint, 12, -46)), "sign", "입구 앞 간판 자리(길 옆)")
	eq(blockedWhy(plotPoint(footprint, -16, -49)), "sign", "간판 자리 반대쪽 끝")
	eq(blockedWhy(plotPoint(footprint, 20, -46)), "free", "간판 자리 옆")
	eq(blockedWhy(plotPoint(footprint, 0, -60)), "path", "입구 길 위")
	eq(blockedWhy(plotPoint(footprint, 6.9, -80)), "path", "길 + 여유 2 안")
	eq(blockedWhy(plotPoint(footprint, 7.5, -80)), "free", "길 여유 밖")
	eq(blockedWhy(0, 0), "plaza", "스폰")
	eq(blockedWhy(0, -26), "plaza", "지구본")
	local gap = ParkLayout.gapAngles()[1]
	near(gap, math.rad(270), 1e-12, "첫 틈 = 지구본 뒤(270도)")
	eq(blockedWhy(math.cos(gap) * 61, math.sin(gap) * 61), "plaza", "광장 둘레 나무 고리 안")
	eq(blockedWhy(math.cos(gap) * 64, math.sin(gap) * 64), "free", "광장 바로 바깥 잔디")
	eq(blockedWhy(math.cos(gap) * 170, math.sin(gap) * 170), "free", "틈 정원 가운데")
	-- 틈 정원 옆(가운데 선에서 30): 부지 안
	local sx, sz = -math.sin(gap) * 30, math.cos(gap) * 30
	eq(blockedWhy(math.cos(gap) * 170 + sx, math.sin(gap) * 170 + sz), "plot", "틈 옆은 부지")
	eq(blockedWhy(math.cos(footprint.Angle) * 230, math.sin(footprint.Angle) * 230), "free", "부지 뒤 숲띠")
end)

test("Scenery Rng: 같은 시드 = 같은 수열, 범위 지킴", function()
	local a, b = SceneryRng.new(42), SceneryRng.new(42)
	local c = SceneryRng.new(43)
	local same, different = true, false
	for _ = 1, 200 do
		local x, y, z = a:NextNumber(), b:NextNumber(), c:NextNumber()
		same = same and x == y
		different = different or x ~= z
		assert(x >= 0 and x < 1, "NextNumber 범위")
		local n = a:NextInteger(3, 7)
		b:NextInteger(3, 7)
		assert(n >= 3 and n <= 7 and n == math.floor(n), "NextInteger 범위")
		local r = a:NextNumber(-2, 5)
		b:NextNumber(-2, 5)
		assert(r >= -2 and r < 5, "NextNumber(min, max) 범위")
	end
	assert(same, "같은 시드인데 다름")
	assert(different, "다른 시드인데 같음")
end)

test("Scenery Plan: 산책로 판정(고리 둘 + 틈 오솔길)", function()
	local T = SceneryPlan.Tuning
	local gap = ParkLayout.gapAngles()[3]
	assert(SceneryPlan.onRoute(T.INNER_RING.Radius, 0), "안쪽 고리")
	assert(SceneryPlan.onRoute(0, -T.OUTER_RING.Radius), "바깥 고리")
	assert(SceneryPlan.onRoute(math.cos(gap) * 150, math.sin(gap) * 150), "틈 오솔길")
	local sx, sz = -math.sin(gap) * 10, math.cos(gap) * 10
	assert(not SceneryPlan.onRoute(math.cos(gap) * 150 + sx, math.sin(gap) * 150 + sz), "오솔길 옆 10")
	local plotAngle = ParkLayout.LAYOUT[1].Angle
	assert(
		not SceneryPlan.onRoute(math.cos(plotAngle) * 150, math.sin(plotAngle) * 150),
		"산책로 아닌 곳(부지 방향)"
	)
	local hit, why = SceneryPlan.islandBlocked(0, -(ParkLayout.ISLAND_RADIUS - 1))
	assert(hit and why == "edge", "섬 가장자리")
end)

test(
	"Scenery Plan: 두 변형 모두 결정적이고, 장식은 부지·간판·길·광장·산책로를 비켜 가며 서로 안 겹침",
	function()
		local island = { Inner = true, Gardens = true, Belt = true }
		for _, variant in SceneryPlan.VARIANTS do
			local a = SceneryPlan.make(variant)
			local b = SceneryPlan.make(variant)
			eq(a.Variant, variant, "변형 이름")
			eq(#a.Items, #b.Items, variant .. " 장식 수")
			assert(#a.Items > 300, variant .. " 장식이 너무 적음: " .. #a.Items)
			local solids, patches = {}, {}
			local wall = a.Wall.Radius
			for i, item in a.Items do
				local other = b.Items[i]
				assert(
					item.Kind == other.Kind and item.X == other.X and item.Z == other.Z and item.Scale == other.Scale,
					variant .. " 결정적이지 않음 #" .. i
				)
				local label = string.format("%s %s/%s (%.1f, %.1f)", variant, item.Zone, item.Kind, item.X, item.Z)
				local hit, why = ParkLayout.blocked(item.X, item.Z, item.Radius)
				assert(not hit, label .. " 이(가) " .. tostring(why) .. " 침범")
				assert(not SceneryPlan.onRoute(item.X, item.Z, item.Radius, 0), label .. " 이(가) 산책로 위")
				local distance = math.sqrt(item.X * item.X + item.Z * item.Z)
				if island[item.Zone] then
					assert(distance + item.Radius <= ParkLayout.ISLAND_RADIUS, label .. " 이(가) 섬 밖")
				elseif item.Zone == "Beach" and item.Kind ~= "Pier" then
					assert(distance + item.Radius <= wall, label .. " 이(가) 벽 밖(못 가는 곳)")
				end
				if item.Layer == "Solid" then
					table.insert(solids, item)
				elseif item.Layer == "Patch" then
					table.insert(patches, item)
				end
			end
			for _, list in { solids, patches } do
				for i = 1, #list do
					for j = i + 1, #list do
						local p, q = list[i], list[j]
						local d = math.sqrt((p.X - q.X) ^ 2 + (p.Z - q.Z) ^ 2)
						assert(
							d >= p.Radius + q.Radius,
							string.format(
								"%s 겹침: %s(%.1f, %.1f) - %s(%.1f, %.1f)",
								variant,
								p.Kind,
								p.X,
								p.Z,
								q.Kind,
								q.X,
								q.Z
							)
						)
					end
				end
			end
			-- 가장자리 벽은 섬 밖, 모래사장/숲 가장자리에
			assert(wall > ParkLayout.ISLAND_RADIUS, variant .. " 벽이 섬 안")
			assert(#a.Rings == 2 and #a.Trails == #ParkLayout.gapAngles(), variant .. " 산책로")
		end
	end
)

test("Scenery Plan: 틈 정원 8곳이 모두 채워지고, 변형별 명물이 있음", function()
	local gaps = ParkLayout.gapAngles()
	for _, variant in SceneryPlan.VARIANTS do
		local plan = SceneryPlan.make(variant)
		local perGap = {}
		local kinds = SceneryPlan.countKinds(plan)
		for _, item in plan.Items do
			if item.Zone == "Gardens" then
				local best, index = math.huge, 0
				local angle = math.atan2(item.Z, item.X)
				for i, gap in gaps do
					local d = math.abs(math.atan2(math.sin(angle - gap), math.cos(angle - gap)))
					if d < best then
						best, index = d, i
					end
				end
				perGap[index] = (perGap[index] or 0) + 1
			end
		end
		for i = 1, #gaps do
			assert((perGap[i] or 0) >= 7, string.format("%s 정원 %d 장식 %d개", variant, i, perGap[i] or 0))
		end
		for _, kind in { "Pond", "Fountain", "Picnic", "Topiary", "Bench", "Lamp", "Mound", "Patch", "FlowerBed" } do
			assert((kinds[kind] or 0) > 0, variant .. " 에 " .. kind .. " 없음")
		end
		if variant == "Ocean" then
			for _, kind in { "Lighthouse", "Pier", "Boat", "Islet", "PalmTree", "Umbrella" } do
				assert((kinds[kind] or 0) > 0, "Ocean 에 " .. kind .. " 없음")
			end
			eq(#plan.Peaks, 0, "Ocean 에 산")
		else
			for _, kind in { "Waterfall", "Hill", "Blob", "PineTree" } do
				assert((kinds[kind] or 0) > 0, "Mountains 에 " .. kind .. " 없음")
			end
			eq(#plan.Peaks, SceneryPlan.Tuning.MOUNTAINS.Peaks.Count, "산 수")
			assert(#plan.Stream > 0, "개울 없음")
			for _, peak in plan.Peaks do
				assert(#peak.Triangles > 0, "면 없는 산")
				for _, t in peak.Triangles do
					local ux, uy, uz = t.B[1] - t.A[1], t.B[2] - t.A[2], t.B[3] - t.A[3]
					local vx, vy, vz = t.C[1] - t.A[1], t.C[2] - t.A[2], t.C[3] - t.A[3]
					local cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
					assert(math.sqrt(cx * cx + cy * cy + cz * cz) > 1, "납작한 산 면")
				end
			end
		end
	end
	eq(SceneryPlan.variant("nope"), "Ocean", "모르는 변형은 Ocean")
	eq(SceneryPlan.variant(nil), "Ocean", "변형 없음은 Ocean")
end)

test("Scenery: 계획의 모든 장식 종류를 Props 가 만들 수 있음", function()
	local source = readfile("src/server/Scenery/Props.luau")
	local known = {}
	for name in source:gmatch("function BUILD%.([%w_]+)%(") do
		known[name] = true
	end
	for _, variant in SceneryPlan.VARIANTS do
		for kind in SceneryPlan.countKinds(SceneryPlan.make(variant)) do
			assert(known[kind], variant .. " 의 " .. kind .. " 를 만드는 함수가 Props 에 없음")
		end
	end
end)

test("default.project.json: 바닥은 반지름 ISLAND_RADIUS 인 세운 원기둥, 윗면 y = 0", function()
	local project = readfile("default.project.json")
	assert(project, "default.project.json 을 읽지 못함")
	local block = project:match('"Baseplate"%s*:%s*(%b{})')
	assert(block, "Baseplate 없음")
	assert(block:find('"Shape"%s*:%s*"Cylinder"'), "원기둥이 아님")
	local h, d1, d2 = block:match('"Size"%s*:%s*%[%s*([%d%.]+)%s*,%s*([%d%.]+)%s*,%s*([%d%.]+)%s*%]')
	eq(tonumber(d1), ParkLayout.ISLAND_RADIUS * 2, "지름(Y)")
	eq(tonumber(d2), ParkLayout.ISLAND_RADIUS * 2, "지름(Z)")
	local y = block:match('"position"%s*:%s*%[%s*[-%d%.]+%s*,%s*([-%d%.]+)')
	near(tonumber(y) + tonumber(h) / 2, 0, 1e-9, "윗면 높이")
	-- 원기둥 축(로컬 X)이 월드 ±Y 로: 회전 행렬 첫 열 (R00, R10, R20) = (0, ±1, 0)
	local r00, r10, r20 = block:match(
		'"orientation"%s*:%s*%[%s*%[%s*([-%d%.]+)%s*,[^%]]*%]%s*,%s*%[%s*([-%d%.]+)%s*,[^%]]*%]%s*,%s*%[%s*([-%d%.]+)'
	)
	eq(tonumber(r00), 0, "R00")
	eq(math.abs(tonumber(r10) :: number), 1, "|R10|")
	eq(tonumber(r20), 0, "R20")
end)

if not Harness.finish() then
	error("테스트 실패")
end
