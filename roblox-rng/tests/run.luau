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
test("applyRoll: 처음 발견 보너스, 중복은 보너스 없음, 중복마다 별 +1 (가챠식)", function()
	local d = PlayerState.new()
	local eiffel = Landmarks.ById.eiffel
	local bonus, isNew, starUp = PlayerState.applyRoll(d, eiffel)
	eq(isNew, true, "첫 발견")
	eq(starUp, false, "첫 발견은 별 상승 아님(별 0)")
	eq(PlayerState.stars(d.Inventory.eiffel), 0, "첫 발견 = 별 0")
	eq(bonus, math.ceil(Config.DISCOVERY_BONUS_MULT * 200 ^ 0.5), "보너스")
	eq(d.Coins, bonus)
	eq(d.Rolls, 1)
	local bonus2, isNew2, starUp2 = PlayerState.applyRoll(d, eiffel)
	eq(bonus2, 0, "중복 보너스 없음")
	eq(isNew2, false)
	eq(starUp2, true, "2번째 = ★1")
	-- 3~6번째도 매번 별 +1, 7번째부터는 ★5 그대로
	for n = 3, 6 do
		local _, _, up = PlayerState.applyRoll(d, eiffel)
		eq(up, true, n .. "번째 별 상승")
		eq(PlayerState.stars(d.Inventory.eiffel), n - 1, n .. "번째 별")
	end
	local _, _, starUp7 = PlayerState.applyRoll(d, eiffel)
	eq(starUp7, false, "★5(최대) 뒤로는 별 상승 없음")
	eq(d.Inventory.eiffel, 7)
	eq(PlayerState.stars(d.Inventory.eiffel), PlayerState.MAX_STARS)
	eq(PlayerState.best(d), eiffel)
end)
test("별 기준: 처음 발견 = 별 0, 중복마다 +1, 6번째에 ★5(최대)", function()
	eq(PlayerState.MAX_STARS, 5)
	eq(#Config.STAR_THRESHOLDS, PlayerState.MAX_STARS)
	for count = 0, 12 do
		eq(PlayerState.stars(count), math.clamp(count - 1, 0, 5), "발견 " .. count .. "번")
	end
	eq(PlayerState.stars(100000), 5)
	-- 기준은 2부터 1씩: 처음 발견은 별이 없음
	for k, threshold in Config.STAR_THRESHOLDS do
		eq(threshold, k + 1, "STAR_THRESHOLDS[" .. k .. "]")
	end
end)
test("별 수입: 기본 × (1 + 보너스 × 별), ★5 가 ★0 보다 확실히 많음", function()
	local pyramid = Landmarks.ById.pyramid
	local base = Config.TIER_INCOME[pyramid.Tier.Rank]
	eq(PlayerState.landmarkIncome(pyramid, 0), 0, "보유 안 함 = 0")
	near(PlayerState.landmarkIncome(pyramid, 1), base, 1e-9, "★0 = 기본")
	near(PlayerState.landmarkIncome(pyramid, 2), base * (1 + Config.STAR_INCOME_BONUS), 1e-9, "★1")
	near(PlayerState.landmarkIncome(pyramid, 6), base * (1 + 5 * Config.STAR_INCOME_BONUS), 1e-9, "★5")
	near(PlayerState.landmarkIncome(pyramid, 500), PlayerState.landmarkIncome(pyramid, 6), 1e-9, "★5 에서 멈춤")
	assert(
		PlayerState.landmarkIncome(pyramid, 6) >= 2 * PlayerState.landmarkIncome(pyramid, 1),
		"★5 는 ★0 의 2배 이상이어야 별이 의미 있음"
	)
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

	-- 별이 오르면 그 명소 수입이 늘어남(3번째 발견 = ★2)
	for _ = 1, 2 do
		PlayerState.applyRoll(d, Landmarks.ById.pyramid)
	end
	near(
		PlayerState.incomePerSecond(d),
		expected + Config.TIER_INCOME[4] * Config.STAR_INCOME_BONUS * 2,
		1e-9,
		"★2 수입"
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
test("rebirthRequirement: 표 그대로, 최대(10번)까지 하면 nil", function()
	eq(Config.MAX_REBIRTHS, 10)
	eq(#Config.REBIRTHS, Config.MAX_REBIRTHS, "단계 수 = 최대")
	local first = PlayerState.rebirthRequirement(0)
	assert(first, "첫 환생 조건")
	eq(first.Coins, 300000)
	eq(first.Landmarks[1], "eiffel")
	eq(first.Landmarks[2], "liberty")
	for n = 1, Config.MAX_REBIRTHS do
		local req = PlayerState.rebirthRequirement(n - 1)
		assert(req, n .. "번째 조건")
		eq(req.Coins, Config.REBIRTHS[n].Coins, n .. "번째 코인")
		eq(#req.Landmarks, #Config.REBIRTHS[n].Landmarks, n .. "번째 명소")
	end
	eq(PlayerState.rebirthRequirement(Config.MAX_REBIRTHS), nil, "최대 뒤에는 없음")
	eq(PlayerState.rebirthRequirement(Config.MAX_REBIRTHS + 3), nil, "넘어도 없음")
	-- 복사본이라 고쳐도 Config 는 그대로
	first.Landmarks[1] = "hack"
	eq(Config.REBIRTHS[1].Landmarks[1], "eiffel", "Config 불변")
end)
test("환생 최대: 10번 하면 더 못 하고, 스냅샷 NextRebirth 는 nil", function()
	local d = PlayerState.new()
	d.Rebirths = Config.MAX_REBIRTHS
	d.Coins = 1e12
	for _, step in Config.REBIRTHS do
		for _, id in step.Landmarks do
			d.Inventory[id] = 1
		end
	end
	eq(PlayerState.rebirthMaxed(d), true)
	local can, missing, short = PlayerState.canRebirth(d)
	eq(can, false)
	eq(#missing, 0)
	eq(short, 0)
	local ok, reason = PlayerState.rebirth(d)
	eq(ok, false)
	eq(reason, "최대 환생입니다")
	eq(d.Rebirths, Config.MAX_REBIRTHS, "그대로")
	eq(d.Coins, 1e12, "코인 그대로")
	eq(PlayerState.snapshot(d, 1).NextRebirth, nil, "다음 조건 없음")
	-- 9번 한 사람은 10번째 가능
	d.Rebirths = Config.MAX_REBIRTHS - 1
	eq(PlayerState.rebirthMaxed(d), false)
	eq((PlayerState.rebirth(d)), true, "10번째 환생")
	eq(d.Rebirths, Config.MAX_REBIRTHS)
end)
test("canRebirth: 모자란 명소와 코인", function()
	local d = PlayerState.new()
	local ok, missing, short = PlayerState.canRebirth(d)
	eq(ok, false)
	eq(#missing, 2, "명소 2개 없음")
	eq(missing[1], "eiffel")
	eq(missing[2], "liberty")
	eq(short, 300000, "코인 부족분")
	PlayerState.applyRoll(d, Landmarks.ById.eiffel)
	PlayerState.applyRoll(d, Landmarks.ById.liberty)
	d.Coins = 299000.5
	ok, missing, short = PlayerState.canRebirth(d)
	eq(ok, false)
	eq(#missing, 0)
	eq(short, 1000, "코인 부족분(올림)")
	d.Coins = 300000
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

		d.Coins = Config.REBIRTHS[1].Coins + 12345
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
		eq(PlayerState.stars(d.Inventory.eiffel), 0, "환생 뒤 다시 얻으면 별 0 부터")
		-- 처음 보는 명소는 여전히 NEW + 보너스
		local bonus2, isNew2 = PlayerState.applyRoll(d, Landmarks.ById.namsan)
		eq(isNew2, true)
		eq(bonus2, PlayerState.discoveryBonus(Landmarks.ById.namsan))
	end
)
test("환생 보상: 행운 ×2^환생 수(10번 = ×1,024), 수입 +50% (누적)", function()
	eq(Config.REBIRTH_LUCK_MULT, 2)
	local d = owning({ "clocktower" })
	near(PlayerState.luck(d), 1, 1e-9, "0회")
	near(PlayerState.incomePerSecond(d), 1, 1e-9, "0회 수입")
	d.Rebirths = 2
	near(PlayerState.luck(d), 4, 1e-9, "2회 행운 ×4")
	near(PlayerState.incomePerSecond(d), 1 + 2 * Config.REBIRTH_INCOME_BONUS, 1e-9, "2회 수입")
	eq(PlayerState.cooldown(d), Config.ROLL_COOLDOWN, "쿨타임은 그대로")
	for r = 0, Config.MAX_REBIRTHS do
		eq(PlayerState.rebirthLuckMult(r), 2 ^ r, r .. "번 행운 배율")
		near(PlayerState.rebirthIncomeMult(r), 1 + 0.5 * r, 1e-9, r .. "번 수입 배율")
	end
	eq(PlayerState.rebirthLuckMult(10), 1024, "10번 = ×1,024")
	eq(PlayerState.rebirthLuckMult(Config.MAX_REBIRTHS + 5), 1024, "최대에서 멈춤")
	eq(PlayerState.rebirthLuckMult(-3), 1, "음수 = 0번")
	d.Rebirths = Config.MAX_REBIRTHS
	near(PlayerState.luck(d), 1024, 1e-9, "10번 행운")
	-- 최대: 지구본 20레벨 ×3, 도장 5개 ×2.25, 환생 ×1,024 = 6,912 (행운 VIP ×2 = 13,824)
	d.Upgrades.Globe = PlayerState.UpgradesById.Globe.MaxLevel
	for _, landmark in Landmarks.List do
		if PlayerState.countsForStamp(landmark) then
			d.Discovered[landmark.Id] = true
		end
	end
	near(PlayerState.luck(d), 6912, 1e-6, "무료 최대 행운")
	near(PlayerState.luck(d, { Passes = { LuckVIP = true } }), 13824, 1e-6, "행운 VIP 최대 행운")
end)

print("\n[밸런스 2026-09-30 · 자동 발견]")
-- 승인된 추천안(balance/variant_rec.json, balance/PROPOSAL.md) + 구현 라운드(짧은 연출·가챠식 별)
test("확률표: 등급 경계·등급별 명소 수(재조정 전과 같음)·가장 희귀 1/100억", function()
	local mins, counts = {}, { 0, 0, 0, 0, 0, 0, 0 }
	for _, tier in Landmarks.Tiers do
		table.insert(mins, tier.MinOneIn)
	end
	eq(table.concat(mins, ","), "1,10,100,1000,12500,250000,8000000", "등급 경계")
	for _, landmark in Landmarks.List do
		counts[landmark.Tier.Rank] += 1
	end
	eq(table.concat(counts, ","), "8,30,42,35,20,9,6", "등급별 명소 수(어느 명소도 등급이 안 바뀜)")
	eq(table.concat(Config.TIER_INCOME, ","), "1,2,5,12,35,120,500", "등급 수입")
	-- 1/1,000 미만(1~3등급)은 그대로
	eq(Landmarks.ById.liberty.OneIn, 70)
	eq(Landmarks.ById.eiffel.OneIn, 200)
	eq(Landmarks.ById.stpeters.OneIn, 950)
	eq(Landmarks.ById.milfordsound.OneIn, 1000)
	-- 희귀할수록 늘림(variant_rec.json)
	eq(Landmarks.ById.sphinx.OneIn, 1250)
	eq(Landmarks.ById.alexandria.OneIn, 20000)
	eq(Landmarks.ById.trojanhorse.OneIn, 650000)
	eq(Landmarks.ById.fountainofyouth.OneIn, 8000000)
	eq(Landmarks.ById.skyisland.OneIn, 110000000)
	eq(Landmarks.ById.shangrila.OneIn, 375000000)
	eq(Landmarks.RarestFirst[1].Id, "worldtree", "가장 희귀")
	eq(Landmarks.ById.worldtree.OneIn, 10000000000, "세계수 1/100억")
	eq(Format.oneIn(Landmarks.ById.worldtree.OneIn), "1 in 10,000,000,000", "확률은 콤마 자연수")
	eq(Format.oneIn(Landmarks.ById.shangrila.OneIn), "1 in 375,000,000")
end)
test("환생 표: 코인 30만 → 1,400억, 요구 명소", function()
	local expected = {
		{ 300000, "eiffel,liberty" },
		{ 1500000, "pyramid,chichen" },
		{ 25000000, "moai,stonehenge,alexandria" },
		{ 250000000, "babylon,artemis,rhodes" },
		{ 1500000000, "zeus,mausoleum,trojanhorse" },
		{ 6000000000, "atlantis,labyrinth" },
		{ 13000000000, "hwangnyongsa,eldorado" },
		{ 28000000000, "fountainofyouth,yonggung" },
		{ 65000000000, "mu,zealandia" },
		{ 140000000000, "skyisland" },
	}
	eq(#Config.REBIRTHS, #expected, "단계 수")
	for k, row in expected do
		eq(Config.REBIRTHS[k].Coins, row[1], k .. "단계 코인")
		eq(table.concat(Config.REBIRTHS[k].Landmarks, ","), row[2], k .. "단계 명소")
	end
end)
test("환생 조건 명소는 그 판에 부스트를 다 켠 최대 행운에서도 굴림에서 나옴", function()
	-- 그 판(환생 r 번)의 최대 행운: 지구본 최대, 도장 5개, 게임패스 전부, 행운 부스트, 서버 행운
	local mods = { Passes = { LuckVIP = true, FastRoll = true, DoubleIncome = true }, ServerLuck = true }
	for k, step in Config.REBIRTHS do
		local d = PlayerState.new()
		d.Rebirths = k - 1
		d.Upgrades.Globe = PlayerState.UpgradesById.Globe.MaxLevel
		for _, landmark in Landmarks.List do
			if PlayerState.countsForStamp(landmark) then
				d.Discovered[landmark.Id] = true
			end
		end
		PlayerState.addBoost(d, "LuckBoost")
		local maxLuck = PlayerState.luck(d, mods)
		local probs = RollLogic.probabilities(Landmarks.RarestFirst, maxLuck)
		for _, id in step.Landmarks do
			local landmark = Landmarks.ById[id]
			assert(
				landmark.OneIn > maxLuck,
				string.format("%d단계 %s (1/%d) ≤ 최대 행운 %g — 못 뽑음", k, id, landmark.OneIn, maxLuck)
			)
			assert(probs[id] > 0, k .. "단계 " .. id .. " 확률 0")
			-- 자동 발견은 보유(Inventory)를 안 채우므로 조건은 직접 뽑아야 함
			PlayerState.autoDiscover(d, mods)
			eq(d.Inventory[id], nil, k .. "단계 " .. id .. " 자동 발견으로 보유되지 않음")
		end
	end
end)
test(
	"속보·홀로그램 기준: 속보 = 사하라 신기루 성·샹그릴라·세계수, 홀로그램 = 샹그릴라·세계수",
	function()
		local news, hologram = {}, {}
		for _, landmark in Landmarks.RarestFirst do
			if landmark.OneIn >= Config.ANNOUNCE_ONE_IN then
				table.insert(news, landmark.Id)
			end
			if landmark.OneIn >= Config.HOLOGRAM_ONE_IN then
				table.insert(hologram, landmark.Id)
			end
		end
		eq(table.concat(news, ","), "worldtree,shangrila,skyisland", "속보")
		eq(table.concat(hologram, ","), "worldtree,shangrila", "홀로그램")
		assert(Config.HOLOGRAM_ONE_IN >= Config.ANNOUNCE_ONE_IN, "홀로그램은 속보 중에서만")
		eq(Config.AUTO_KNOWN_REVEAL_RANK, 3, "AUTO 에서 이미 발견한 명소는 3등급처럼 짧은 연출")
	end
)
test("permanentLuck: 지구본·도장·환생·행운 VIP 만 (시간 부스트·서버 행운 제외)", function()
	local d = PlayerState.new()
	d.Rebirths = 3
	d.Upgrades.Globe = 5
	near(PlayerState.permanentLuck(d), 1.5 * 8, 1e-9, "지구본 ×1.5 × 환생 ×8")
	near(PlayerState.permanentLuck(d, { Passes = { LuckVIP = true } }), 1.5 * 8 * 2, 1e-9, "VIP 포함")
	PlayerState.addBoost(d, "LuckBoost")
	local boosted = { Passes = { LuckVIP = true }, ServerLuck = true }
	near(PlayerState.permanentLuck(d, boosted), 1.5 * 8 * 2, 1e-9, "부스트·서버 행운 제외")
	near(PlayerState.luck(d, boosted), 1.5 * 8 * 2 * 2 * 2, 1e-9, "굴림 행운은 부스트 포함")
end)
test("autoDiscover: 영구 행운 이하 확률만 발견 기록, 보유·수입·코인은 그대로", function()
	local d = PlayerState.new()
	d.Rebirths = 2
	d.Upgrades.Globe = 20 -- 행운 4 × 3 = 12
	PlayerState.applyRoll(d, Landmarks.ById.arc) -- 1/12, 이미 발견
	local coins, rolls = d.Coins, d.Rolls
	local added = PlayerState.autoDiscover(d)
	local expected = {}
	for _, landmark in Landmarks.List do
		if landmark.OneIn <= 12 and landmark.Id ~= "arc" then
			table.insert(expected, landmark.Id)
		end
	end
	eq(table.concat(added, ","), table.concat(expected, ","), "흔한 것부터, 이미 발견한 건 빼고")
	for _, landmark in Landmarks.List do
		eq(PlayerState.isDiscovered(d, landmark.Id), landmark.OneIn <= 12, landmark.Id)
	end
	eq(d.Inventory.arc, 1, "보유 그대로")
	eq(d.Inventory.clocktower, nil, "자동 발견은 보유가 아님")
	eq(table.concat(PlayerState.park(d), ","), "arc", "공원엔 보유한 것만")
	eq(
		PlayerState.incomePerSecond(d),
		PlayerState.landmarkIncome(Landmarks.ById.arc, 1) * 2,
		"수입 그대로(환생 2번 ×2)"
	)
	eq(d.Coins, coins, "발견 보너스 없음")
	eq(d.Rolls, rolls, "굴림 수 그대로")
	eq(#PlayerState.autoDiscover(d), 0, "두 번 불러도 더 없음")
	-- 굴려서 다시 나오면(행운 = N 인 명소는 판정이 늘 성공해서 나올 수 있음) NEW·보너스 없이 보유만 늘어남
	local bonus, isNew = PlayerState.applyRoll(d, Landmarks.ById.arc)
	eq(bonus, 0)
	eq(isNew, false)
end)
test("autoDiscover: 새 도장이 행운을 올리면 한 번 더 (고정점)", function()
	local d = PlayerState.new()
	d.Rebirths = 3 -- 행운 8
	for _, landmark in Landmarks.ByRegion.Oceania do
		if PlayerState.countsForStamp(landmark) and landmark.Id ~= "harbourbridge" then
			d.Discovered[landmark.Id] = true -- 오세아니아 도장까지 하버 브리지(1/4) 하나만 남음
		end
	end
	eq(#PlayerState.completedRegions(d), 0)
	local added = PlayerState.autoDiscover(d)
	eq(table.concat(PlayerState.completedRegions(d), ","), "Oceania", "자동 발견으로 도장")
	near(PlayerState.permanentLuck(d), 8 * (1 + Config.REGION_LUCK_BONUS), 1e-9, "도장으로 행운 10")
	eq(added[#added], "gatewayarch", "행운 10 이 되어 1/10 까지 한 번 더")
	eq(PlayerState.isDiscovered(d, "gatewayarch"), true)
	eq(PlayerState.isDiscovered(d, "cheomseongdae"), false, "1/11 은 아직")
end)
test("autoDiscover: 행운 VIP 로 시작한 새 플레이어도 여권이 막히지 않음", function()
	local vip = { Passes = { LuckVIP = true } }
	local d = PlayerState.new()
	eq(#PlayerState.autoDiscover(d), 0, "무료 새 플레이어(행운 1)는 없음")
	eq(
		table.concat(PlayerState.autoDiscover(d, vip), ","),
		"clocktower",
		"행운 2 = 1/2 는 못 뽑으니 발견 처리"
	)
	-- 부스트·서버 행운은 기준이 아님
	local e = PlayerState.new()
	PlayerState.addBoost(e, "LuckBoost")
	eq(#PlayerState.autoDiscover(e, { ServerLuck = true }), 0, "시간 부스트로는 자동 발견 안 함")
	-- 모든 도장 조건 명소는 부스트 없이 굴려서 얻을 수 있거나 자동 발견됨: 여권 5개가 다 찰 수 있음
	-- (시간 부스트 중에는 영구 행운 ~ 부스트 행운 사이 명소가 잠깐 안 나오지만 부스트가 끝나면 다시 나옴)
	local full = PlayerState.new()
	full.Rebirths = Config.MAX_REBIRTHS
	full.Upgrades.Globe = PlayerState.UpgradesById.Globe.MaxLevel
	PlayerState.autoDiscover(full, vip)
	local luck = PlayerState.permanentLuck(full, vip)
	local probs = RollLogic.probabilities(Landmarks.RarestFirst, luck)
	for _, landmark in Landmarks.List do
		if PlayerState.countsForStamp(landmark) then
			assert(
				probs[landmark.Id] > 0 or PlayerState.isDiscovered(full, landmark.Id),
				landmark.Id .. " 못 뽑는데 자동 발견도 안 됨"
			)
		end
	end
end)
test(
	"snapshot: PermanentLuck + 자동 발견이 Discovered 에 들어 있어 화면 계산이 서버와 같음",
	function()
		local mods = { Passes = { LuckVIP = true } }
		local d = PlayerState.new()
		d.Rebirths = 4 -- 행운 16 × VIP 2 = 32
		PlayerState.addBoost(d, "LuckBoost")
		PlayerState.autoDiscover(d, mods) -- 서버: 상태를 보내기 전에 부름
		local s = PlayerState.snapshot(d, 1, mods)
		eq(s.PermanentLuck, 32)
		eq(s.Luck, 64, "부스트 포함")
		for _, landmark in Landmarks.List do
			eq(s.Discovered[landmark.Id] == true, landmark.OneIn <= 32, landmark.Id)
			eq(PlayerState.isDiscovered(s, landmark.Id), PlayerState.isDiscovered(d, landmark.Id), landmark.Id)
		end
		for _, region in Landmarks.Regions do
			local a, b = PlayerState.regionProgress(s, region.Id)
			local c, e = PlayerState.regionProgress(d, region.Id)
			eq(a .. "/" .. b, c .. "/" .. e, region.Id .. " 여권 진행도")
		end
		eq(PlayerState.luck(s, s), s.Luck, "화면에서 다시 계산해도 같은 행운")
		eq(PlayerState.permanentLuck(s, s), s.PermanentLuck)
	end
)
test("옛 저장 불러오기: 예전 표로 환생한 플레이어 · 발견 기록 · 보유 · 공원", function()
	-- 환생 10번(예전 표 = 약 4일)을 끝낸 저장: 행운 ×3 → ×1,024, 보유·발견 그대로, 별은 개수로 다시 계산
	local old = {
		Rolls = 250000,
		Coins = 3000000000,
		Rebirths = 10,
		Inventory = { clocktower = 812, eiffel = 40, pyramid = 3, sphinx = 1, yonggung = 1, worldtree = 1 },
		Discovered = {
			eiffel = true,
			pyramid = true,
			sphinx = true,
			yonggung = true,
			worldtree = true,
			atlantis = true,
		},
		Upgrades = { Globe = 20, Agency = 10, Park = 10, Ticket = 15 },
		Settings = { AutoFeature = true, AutoPark = true },
		Display = {},
		Boosts = { LuckBoost = 120 },
		Receipts = { "r1" },
	}
	local d = PlayerState.reconcile(old)
	eq(d.Rebirths, 10, "환생 수 그대로")
	eq(d.Inventory.clocktower, 812, "보유 수 그대로")
	eq(PlayerState.stars(d.Inventory.clocktower), 5)
	eq(PlayerState.stars(d.Inventory.pyramid), 2, "3번 발견 = ★2")
	eq(PlayerState.stars(d.Inventory.sphinx), 0, "1번 발견 = ★0 (수입은 예전 ★1 과 같은 기본)")
	eq(PlayerState.rebirthMaxed(d), true)
	eq(PlayerState.snapshot(d, 1).NextRebirth, nil, "최대까지 했으면 다음 조건 없음")
	local luck = PlayerState.permanentLuck(d)
	near(luck, 1024 * 3, 1e-9, "도장 없이 ×1,024 × 지구본 ×3")
	local added = PlayerState.autoDiscover(d)
	assert(#added > 0, "행운이 올라 흔한 명소가 자동 발견됨")
	for _, landmark in Landmarks.List do
		if landmark.OneIn <= PlayerState.permanentLuck(d) then
			eq(PlayerState.isDiscovered(d, landmark.Id), true, landmark.Id)
		end
	end
	eq(d.Discovered.atlantis, true, "예전 발견 기록 유지")
	eq(d.Inventory.atlantis, nil, "보유는 그대로(없음)")
	eq(PlayerState.park(d)[1], "worldtree", "공원은 보유한 명소를 희귀한 순서로")
	eq(#PlayerState.park(d), 6, "보유한 6개만 전시")
	-- 환생 3번(예전 표 = 약 33분)에서 멈춘 저장: 행운 ×8, 다음은 새 표의 4단계
	local mid = PlayerState.reconcile({ Rebirths = 3, Coins = 700000, Inventory = { babylon = 1 } })
	near(PlayerState.luck(mid), 8, 1e-9, "환생 3번 = ×8")
	local req = PlayerState.rebirthRequirement(mid.Rebirths)
	eq(req.Coins, 250000000, "새 표 4단계 코인")
	eq(table.concat(req.Landmarks, ","), "babylon,artemis,rhodes")
	local can, missing, short = PlayerState.canRebirth(mid)
	eq(can, false)
	eq(table.concat(missing, ","), "artemis,rhodes", "보유한 바빌론은 인정")
	eq(short, 250000000 - 700000)
	-- 발견 기록이 없던 아주 옛 저장: 보유 → 발견, 그다음 자동 발견
	local ancient = PlayerState.reconcile({ Rebirths = 1, Inventory = { eiffel = 2 } })
	eq(ancient.Discovered.eiffel, true)
	eq(table.concat(PlayerState.autoDiscover(ancient), ","), "clocktower", "행운 2 → 1/2 자동 발견")
end)
test(
	"별은 보유 수로 계산 — 저장 데이터·스냅샷에 별 값이 없음(저장 형식 그대로)",
	function()
		local d = owning({ "eiffel", "eiffel", "eiffel" })
		for key in d do
			assert(not string.find(string.lower(key), "star"), "Data 에 별 값: " .. key)
		end
		for key in PlayerState.snapshot(d, 1) do
			assert(not string.find(string.lower(key), "star"), "Snapshot 에 별 값: " .. key)
		end
		local r: any = PlayerState.reconcile({ Inventory = { eiffel = 3 }, Stars = { eiffel = 5 } })
		eq(r.Stars, nil, "모르는 필드는 버림")
		eq(PlayerState.stars(r.Inventory.eiffel), 2, "개수로 다시 계산")
	end
)

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
	near(PlayerState.luck(d, all), 1.1 * 2 * 2 * 2 * 2, 1e-9, "전부 곱(환생 1번 = ×2)")
	near(
		PlayerState.permanentLuck(d, all),
		1.1 * 2 * 2,
		1e-9,
		"영구 행운 = 부스트·서버 행운 빼고(VIP 는 포함)"
	)
	near(PlayerState.incomePerSecond(d, all), 1 * 1.5 * 2, 1e-9, "수입 전부 곱")
	-- 스냅샷은 mods 반영 + Snapshot 을 mods 로 다시 넘겨도 같은 값
	local s = PlayerState.snapshot(d, 1, all)
	near(s.Luck, 1.1 * 2 * 8, 1e-9, "snapshot Luck")
	near(s.PermanentLuck, 1.1 * 2 * 2, 1e-9, "snapshot PermanentLuck")
	near(PlayerState.permanentLuck(s, s), s.PermanentLuck, 1e-9, "permanentLuck(snapshot, snapshot)")
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
	eq(d.Boosts.LuckBoost, 22 * 900, "결제된 시간은 구매 창 상한(3시간)을 넘어도 다 더함")
	d.Boosts.LuckBoost = Config.MAX_BOOST_STORED_SECONDS - 100
	PlayerState.addBoost(d, "LuckBoost")
	eq(d.Boosts.LuckBoost, Config.MAX_BOOST_STORED_SECONDS, "저장 상한(데이터 손상 방지)에서만 멈춤")
	eq(PlayerState.stackSeconds(100, 900), 1000)
	eq(PlayerState.stackSeconds(-5, 900), 900, "음수 남은 시간 = 0")
	eq(PlayerState.stackSeconds(Config.MAX_BOOST_SECONDS, 900), Config.MAX_BOOST_SECONDS + 900)
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
test("영수증: 중복 기록 없음, 최근 MAX_RECEIPTS 개만", function()
	-- 저장이 계속 실패하는 동안 한 세션에서 수십 번 사도 밀려나지 않을 만큼 넉넉해야 함(밀려난 영수증은 다시 지급됨)
	assert(Config.MAX_RECEIPTS >= 500, "MAX_RECEIPTS 가 너무 작음: " .. Config.MAX_RECEIPTS)
	local d = PlayerState.new()
	eq(PlayerState.hasReceipt(d, "abc"), false)
	PlayerState.addReceipt(d, "abc")
	eq(PlayerState.hasReceipt(d, "abc"), true)
	PlayerState.addReceipt(d, "abc")
	eq(#d.Receipts, 1, "중복 없음")
	PlayerState.addReceipt(d, 12345)
	eq(PlayerState.hasReceipt(d, "12345"), true, "숫자도 문자열로")
	eq(PlayerState.hasReceipt(d, 12345), true)
	local total = Config.MAX_RECEIPTS + 10
	for i = 1, total do
		PlayerState.addReceipt(d, "p" .. i)
	end
	eq(#d.Receipts, Config.MAX_RECEIPTS, "최대 개수")
	eq(PlayerState.hasReceipt(d, "abc"), false, "오래된 것 삭제")
	eq(PlayerState.hasReceipt(d, "p10"), false, "오래된 것 삭제")
	eq(PlayerState.hasReceipt(d, "p11"), true, "최근 MAX_RECEIPTS 개 유지")
	eq(PlayerState.hasReceipt(d, "p" .. total), true)
	eq(d.Receipts[#d.Receipts], "p" .. total, "최근 것이 끝")
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
	eq(grant.Seconds, 900, "결제된 시간은 구매 창 상한(3시간)을 넘어도 다 더함")
	eq(d.Boosts.LuckBoost, Config.MAX_BOOST_SECONDS + 800)

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
	local total = Config.MAX_RECEIPTS + 5
	for i = 1, total do
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
	eq(d.Boosts.LuckBoost, Config.MAX_BOOST_STORED_SECONDS, "저장 상한으로 제한")
	eq(d.Boosts.ServerLuck, nil, "서버 행운은 저장 안 함")
	eq(d.Boosts.CoinPack, nil)
	eq(d.Boosts.Nope, nil)
	eq(#d.Receipts, Config.MAX_RECEIPTS, "최근 MAX_RECEIPTS 개")
	eq(d.Receipts[1], "r6", "오래된 것부터 삭제")
	eq(d.Receipts[#d.Receipts], "r" .. total)
	eq(PlayerState.hasReceipt(d, "x"), false)

	local bad = PlayerState.reconcile({ Rebirths = -2, Boosts = { LuckBoost = -5 }, Receipts = "x", Discovered = 7 })
	eq(bad.Rebirths, 0, "음수")
	eq(bad.Boosts.LuckBoost, nil, "음수 부스트")
	eq(#bad.Receipts, 0)
	eq(next(bad.Discovered), nil)
	eq(PlayerState.reconcile({ Boosts = { LuckBoost = 0 / 0 } }).Boosts.LuckBoost, nil, "NaN 부스트")
	eq(
		PlayerState.reconcile({ Boosts = { LuckBoost = Config.MAX_BOOST_SECONDS + 500 } }).Boosts.LuckBoost,
		Config.MAX_BOOST_SECONDS + 500,
		"구매 창 상한을 넘게 산 시간도 다음 접속에 그대로"
	)
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

test(
	"storageStart: 보관함에서 집은 명소가 처음 떠 있을 칸 = 첫 빈 칸 > 가장 약한 전시 명소 칸 > 1",
	function()
		local d = owning(EIGHT) -- 자동 배치 6칸 꽉 참: pyramid, eiffel, bigben, arc, fountain, windmill
		eq(ParkGrid.storageStart(d), 5, "꽉 참: 가장 약한 명소(fountain·windmill 같음 -> 앞 번호)")
		d.Inventory.fountain = 5 -- 별이 늘어 수입이 windmill 보다 큼
		eq(ParkGrid.storageStart(d), 6, "가장 약한 명소 = windmill")
		eq(ParkGrid.storageStart(PlayerState.snapshot(d, 1)), 6, "스냅샷으로도 같음")
		eq((PlayerState.setDisplay(d, 3, nil)), true)
		eq(ParkGrid.storageStart(d), 3, "빈 칸이 있으면 첫 빈 칸")
		eq(ParkGrid.storageStart(PlayerState.new()), 1, "아무것도 없음 = 1")
	end
)

test("pinchZoom: 두 손가락 벌리면 가까이(배율 작아짐), 모으면 멀리, 범위 안", function()
	eq(ParkGrid.pinchZoom(1, 100, 100), 1, "그대로")
	near(ParkGrid.pinchZoom(1, 200, 160), 1.25, 1e-9, "모음 = 멀리")
	near(ParkGrid.pinchZoom(1, 100, 110), 1 / 1.1, 1e-9, "벌림 = 가까이")
	eq(ParkGrid.pinchZoom(1, 100, 400), ParkGrid.ZOOM_MIN, "가장 가까이")
	eq(ParkGrid.pinchZoom(1.2, 100, 20), ParkGrid.ZOOM_MAX, "가장 멀리")
	eq(ParkGrid.pinchZoom(1.1, 0, 50), 1.1, "처음 거리 0 = 그대로")
	eq(ParkGrid.pinchZoom(1.1, 50, 0), 1.1, "지금 거리 0 = 그대로")
	eq(ParkGrid.pinchZoom(3, 0, 50), ParkGrid.ZOOM_MAX, "범위 밖 배율은 안으로")
	assert(ParkGrid.ZOOM_MIN < 1 and ParkGrid.ZOOM_MAX > 1, "1(딱 맞음)이 범위 안")
end)

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
	eq(Format.oneIn(1000000), "1 in 1,000,000")
	eq(Format.oneIn(40000000), "1 in 40,000,000")
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
local SceneryIsland = Harness.require(server.Scenery.Island)
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
	assert(SceneryPlan.onRoute(SceneryPlan.ringRadius(T.INNER_RING, 0), 0), "안쪽 고리")
	-- 안쪽 고리는 원이 아님(구불구불): 반지름이 15 이상 달라짐, 광장 둘레 나무 고리와 부지 입구 간판 자리 사이
	local low, high = math.huge, -math.huge
	for k = 0, 359 do
		local r = SceneryPlan.ringRadius(T.INNER_RING, math.rad(k))
		low, high = math.min(low, r), math.max(high, r)
	end
	assert(high - low >= 15, string.format("안쪽 고리가 거의 원(%.1f ~ %.1f)", low, high))
	assert(low - T.INNER_RING.Width / 2 > ParkLayout.PLAZA_CLEAR, "안쪽 고리가 광장 둘레 나무에 걸림")
	assert(
		high + T.INNER_RING.Width / 2 < ParkLayout.RING_RADIUS - ParkLayout.SIGN_DEPTH - ParkLayout.BORDER - 2,
		"안쪽 고리가 부지 입구 간판 자리에 걸림"
	)
	assert(SceneryPlan.onRoute(0, -T.OUTER_RING.Radius), "바깥 고리")
	-- 오솔길은 틈이 좁은 곳(rho < 140)에서는 가운데 선 위, 넓은 곳에서는 굽이칠 수 있음
	assert(SceneryPlan.onRoute(math.cos(gap) * 125, math.sin(gap) * 125), "틈 오솔길")
	local sx, sz = -math.sin(gap) * 10, math.cos(gap) * 10
	assert(not SceneryPlan.onRoute(math.cos(gap) * 125 + sx, math.sin(gap) * 125 + sz), "오솔길 옆 10")
	local plotAngle = ParkLayout.LAYOUT[1].Angle
	assert(
		not SceneryPlan.onRoute(math.cos(plotAngle) * 150, math.sin(plotAngle) * 150),
		"산책로 아닌 곳(부지 방향)"
	)
	local south = -math.pi / 2
	local hit, why = SceneryPlan.islandBlocked(0, -(SceneryIsland.grassEdge(south) - 1))
	assert(hit and why == "edge", "풀밭 끝(모래 시작)")
end)

-- 부지(둘레 띠 포함) 네 모서리 중 광장에서 가장 먼 곳까지 거리
local function farthestPlotCorner(): number
	local far = 0
	for _, footprint in ParkLayout.footprints() do
		for _, sx in { -1, 1 } do
			for _, sz in { -1, 1 } do
				local x, z = plotPoint(footprint, sx * footprint.HalfWidth, sz * footprint.HalfDepth)
				far = math.max(far, math.sqrt(x * x + z * z))
			end
		end
	end
	return far
end

test(
	"Scenery Island: 해안선은 구불구불(원이 아님)하고 매끄러우며, 부지·바깥 산책로에서 충분히 떨어짐",
	function()
		local I, T = SceneryIsland, SceneryPlan.Tuning
		local walkwayOut = T.OUTER_RING.Radius + T.OUTER_RING.Width / 2
		assert(walkwayOut > farthestPlotCorner(), "바깥 산책로가 부지 뒤에 있어야 함")
		local low, high = math.huge, -math.huge
		local steps = 3600
		local previous = I.coastRadius(0)
		for k = 1, steps do
			local a = k / steps * math.pi * 2
			local coast, grass = I.coastRadius(a), I.grassEdge(a)
			low, high = math.min(low, coast), math.max(high, coast)
			assert(coast >= I.COAST_MIN and coast <= I.COAST_MAX, "해안선 범위 " .. coast)
			-- 0.1 도마다 0.5 스터드 이하로 변함(뾰족한 톱니 없음)
			assert(math.abs(coast - previous) < 0.5, string.format("해안선이 %.1f 도에서 튐", math.deg(a)))
			previous = coast
			-- 풀밭 끝(모래 시작)이 바깥 산책로에서 20 이상, 모래사장 폭 6 이상
			assert(
				grass - walkwayOut >= 20,
				string.format("%.1f 도: 풀밭 끝 %.1f 이 산책로에 너무 가까움", math.deg(a), grass)
			)
			assert(coast - grass >= 6, string.format("%.1f 도: 모래사장이 너무 좁음", math.deg(a)))
		end
		assert(high - low >= 25, string.format("해안선이 거의 원(%.1f ~ %.1f)", low, high))
		-- 같은 각도 = 같은 값(순수 함수), 한 바퀴 돌면 제자리
		eq(I.coastRadius(1.234), I.coastRadius(1.234), "결정적")
		near(I.coastRadius(-0.3), I.coastRadius(math.pi * 2 - 0.3), 1e-9, "각도 감싸기")
	end
)

test(
	"Scenery Island: 공원 자리는 y = 0 평평, 숲띠는 낮은 언덕, 모래사장은 물속으로 완만하게",
	function()
		local I = SceneryIsland
		assert(farthestPlotCorner() < I.FLAT_RADIUS, "부지가 평지 밖")
		-- 광장·부지·길·산책로 자리(r <= FLAT_RADIUS)는 정확히 0
		for k = 0, 359, 7 do
			local a = math.rad(k)
			for _, r in { 0, 30, 84, 150, 200, 208.5, I.FLAT_RADIUS - 0.01 } do
				eq(I.height(math.cos(a) * r, math.sin(a) * r), 0, string.format("평지 %d 도 r %.1f", k, r))
			end
		end
		local mounds = 0
		for k = 0, 359, 3 do
			local a = math.rad(k)
			local dx, dz = math.cos(a), math.sin(a)
			local grass, coast = I.grassEdge(a), I.coastRadius(a)
			-- 숲띠: 0 ~ TOP
			for r = I.FLAT_RADIUS, grass, 2 do
				local h = I.height(dx * r, dz * r)
				assert(h >= 0 and h <= I.TOP, string.format("숲띠 높이 %.2f", h))
				if h > 1 then
					mounds += 1
				end
			end
			-- 모래사장 → 물가 → 얕은 턱 → 깊은 바다: 바깥으로 갈수록 낮아짐(바위 자리 제외)
			local _, name = I.surface(dx * (grass + 0.5), dz * (grass + 0.5))
			local previous = math.huge
			local rocky = false
			for r = grass + 0.5, grass + 90, 1.5 do
				local h, m = I.surface(dx * r, dz * r)
				rocky = rocky or m == "Rock"
				if not rocky then
					assert(h <= previous + 1e-9, string.format("%d 도 r %.1f 에서 다시 높아짐", k, r))
				end
				previous = h
			end
			if not rocky then
				assert(name == "Sand", "풀밭 끝 너머는 모래")
				near(I.height(dx * coast, dz * coast), I.WATER_LEVEL, 0.05, "물가 높이 = 물 높이")
				-- 물가 바로 너머는 얕은 물(깊이 3 이내 = 청록)
				local shallow = I.height(dx * (coast + 8), dz * (coast + 8))
				assert(shallow < I.WATER_LEVEL and shallow > I.WATER_LEVEL - 3.01, "얕은 모래 턱")
			end
		end
		assert(mounds > 40, "숲띠 언덕이 거의 없음")
		-- 먼 바다는 깊은 바닥
		eq(I.height(0, -500), I.SEA_FLOOR, "먼 바다 바닥")
	end
)

test(
	"Scenery Island.voxels: 복셀 표(공원 = y 0 까지 땅, 바다 = 물), 칠하기, WriteVoxels 표 바꾸기",
	function()
		local I = SceneryIsland
		local V = I.VOXEL
		-- 광장 옆 공원 칸 2x2: 땅 윗면 0 = 복셀 경계
		local grid = I.voxels(-100, -4, 2, 2, {
			Paint = { { Kind = "Circle", X = -98, Z = -2, R = 0.5, Material = "Salt", Margin = 0 } },
		})
		eq(grid.SizeY, (I.TOP - I.SEA_FLOOR) // V, "층 수")
		local zeroLayer = (0 - I.SEA_FLOOR) // V -- y -4~0 층 번호
		for i = 1, 2 do
			for k = 1, 2 do
				-- Roblox 는 단단한 지형 윗면을 "맨 위 땅 복셀 바닥 + 2 + 4·점유율" 에 그림(실측) → 윗면 0 = -4~0 층 반
				eq(grid.Solid[i][zeroLayer][k], 0.5, "y -4~0 은 반만 땅")
				eq(-4 + I.SOLID_LIFT + 4 * grid.Solid[i][zeroLayer][k], 0, "Roblox 가 그리는 윗면 = 0")
				eq(grid.Solid[i][zeroLayer - 1][k], 1, "y -8~-4 는 가득")
				eq(grid.Solid[i][zeroLayer + 1][k], 0, "y 0~4 는 빔")
				eq(grid.Liquid[i][zeroLayer + 1][k], 0, "공원에 물 없음")
			end
		end
		eq(grid.Material[1][zeroLayer][1], "Salt", "칠한 칸")
		local plain = grid.Material[2][zeroLayer][2]
		assert(plain == "Grass" or plain == "LeafyGrass", "안 칠한 칸은 잔디: " .. tostring(plain))
		-- 먼 바다 칸: 바닥 한 층 + 물(물 높이까지 가득)
		local sea = I.voxels(-4, -420, 1, 1)
		eq(sea.Solid[1][1][1], 0, "바닥 윗면 = 표 맨 아래")
		local waterLayers = (I.WATER_LEVEL - I.SEA_FLOOR) // V
		for j = 1, waterLayers do
			eq(sea.Liquid[1][j][1], 1, "물 층 " .. j)
		end
		eq(sea.Liquid[1][waterLayers + 1][1], 0, "물 위는 빔")
		eq(sea.WaterCount, waterLayers, "물 복셀 수")
		-- 예전 API 용 표: 물 복셀은 Water 재질·점유율 1
		local materials, occupancies = I.legacy(sea, "Water", "Air")
		eq(materials[1][1][1], "Water", "legacy 물")
		eq(occupancies[1][1][1], 1, "legacy 물 점유율")
		eq(materials[1][waterLayers + 1][1], "Air", "legacy 빈 칸")
		-- 지형 표 범위: 본섬 한 장이 해안선 + 얕은 턱 + 비탈을 다 담고, 복셀 경계에 맞음
		local total = 0
		for _, area in I.areas() do
			eq(area.MinX % V, 0, area.Name .. " x 경계")
			eq(area.MinZ % V, 0, area.Name .. " z 경계")
			total += area.SizeX * area.SizeZ * grid.SizeY
		end
		assert(total < 600000, "복셀 표가 너무 큼: " .. total)
		eq(
			I.height(I.REGION_HALF - 1, 0),
			I.SEA_FLOOR,
			"본섬 표 가장자리는 깊은 바닥(먼 바다와 이어짐)"
		)
	end
)

test(
	"Scenery Plan: 결정적이고, 장식은 부지·간판·길·광장·산책로를 비켜 가며 서로 안 겹침",
	function()
		local I = SceneryIsland
		local a = SceneryPlan.make()
		local b = SceneryPlan.make()
		eq(#a.Items, #b.Items, "장식 수")
		assert(#a.Items > 250, "장식이 너무 적음: " .. #a.Items)
		local solids = {}
		local island = { Inner = true, Gardens = true, Belt = true }
		-- 일부러 산책로 위에 두는 것(분수 광장 가운데 분수 — 둘레로 돌아감)
		local onRouteKinds = { Fountain = true }
		for i, item in a.Items do
			local other = b.Items[i]
			assert(
				item.Kind == other.Kind and item.X == other.X and item.Z == other.Z and item.Scale == other.Scale,
				"결정적이지 않음 #" .. i
			)
			local label = string.format("%s/%s (%.1f, %.1f)", item.Zone, item.Kind, item.X, item.Z)
			local hit, why = ParkLayout.blocked(item.X, item.Z, item.Radius)
			assert(not hit, label .. " 이(가) " .. tostring(why) .. " 침범")
			local distance = math.sqrt(item.X * item.X + item.Z * item.Z)
			if island[item.Zone] then
				assert(
					distance + item.Radius <= I.grassEdge(math.atan2(item.Z, item.X)),
					label .. " 이(가) 풀밭 밖"
				)
			end
			if island[item.Zone] and item.Layer == "Solid" and not onRouteKinds[item.Kind] then
				assert(not SceneryPlan.onRoute(item.X, item.Z, item.Radius, 0), label .. " 이(가) 산책로 위")
			end
			if item.Zone == "Beach" and item.Kind ~= "Pier" and item.Kind ~= "Lighthouse" then
				assert(I.isDry(item.X, item.Z), label .. " 이(가) 물속")
			end
			if item.Layer == "Solid" then
				table.insert(solids, item)
			end
		end
		for i = 1, #solids do
			for j = i + 1, #solids do
				local p, q = solids[i], solids[j]
				local d = math.sqrt((p.X - q.X) ^ 2 + (p.Z - q.Z) ^ 2)
				assert(
					d >= p.Radius + q.Radius,
					string.format("겹침: %s(%.1f, %.1f) - %s(%.1f, %.1f)", p.Kind, p.X, p.Z, q.Kind, q.X, q.Z)
				)
			end
		end
		eq(#a.Rings, 2, "산책로 고리")
		assert(#a.Trails >= #ParkLayout.gapAngles(), "정원 오솔길")
		for _, segment in a.Trails do
			assert(segment.Top ~= a.Rings[1].Top, "오솔길과 고리 윗면이 같으면 겹친 곳이 깜빡임")
		end
	end
)

test("Scenery Plan: 나무는 무리 지어(숲과 빈터) 놓이고 줄기끼리 겹치지 않음", function()
	local plan = SceneryPlan.make()
	local trees = {}
	for _, item in plan.Items do
		if item.Kind == "Tree" or item.Kind == "Palm" then
			table.insert(trees, item)
		end
	end
	assert(#trees >= 60, "나무가 너무 적음: " .. #trees)
	-- 숲띠 나무의 가장 가까운 이웃 거리: 겹치지 않되(줄기 + 여유) 대부분 가까이 모여 있음(고르게 흩뿌리지 않음)
	local close = 0
	local belt = 0
	for i, p in trees do
		if p.Zone == "Belt" then
			belt += 1
			local nearest = math.huge
			for j, q in trees do
				if i ~= j then
					nearest = math.min(nearest, math.sqrt((p.X - q.X) ^ 2 + (p.Z - q.Z) ^ 2))
				end
			end
			assert(nearest >= p.Radius, "줄기 겹침")
			if nearest < 14 then
				close += 1
			end
		end
	end
	assert(close >= belt * 0.6, string.format("숲띠 나무가 무리를 이루지 않음(%d/%d)", close, belt))
end)

test("Scenery Plan: 틈 정원 8곳은 주제가 모두 다르고 채워짐, 물가 명물이 있음", function()
	local gaps = ParkLayout.gapAngles()
	local themes = SceneryPlan.Tuning.GARDEN_THEMES
	eq(#themes, #gaps, "주제 수")
	local seen = {}
	for _, theme in themes do
		assert(not seen[theme], "같은 주제 두 번: " .. theme)
		seen[theme] = true
	end
	local plan = SceneryPlan.make()
	local perGap = {}
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
		assert((perGap[i] or 0) >= 7, string.format("정원 %d 장식 %d개", i, perGap[i] or 0))
	end
	local kinds = SceneryPlan.countKinds(plan)
	for _, kind in
		{
			"Lighthouse",
			"Pier",
			"Boat",
			"BeachSet",
			"Kiosk",
			"Lifeguard",
			"Buoy",
			"Sandcastle",
			"Palm",
			"Tree",
			"Bush",
			"Hedge",
			"FlowerBed",
			"Fountain",
			"PondDeco",
			"Bridge",
			"Gazebo",
			"Topiary",
			"Blanket",
			"Rock",
			"Lantern",
			"Arch",
			"Bench",
			"Lamp",
		}
	do
		assert((kinds[kind] or 0) > 0, kind .. " 없음")
	end
	eq(#plan.Ponds, 1, "연못 정원의 지형 연못")
	assert((kinds.Boat or 0) >= 4, "돛단배")
	eq(next(plan.Skipped), nil, "자리가 없어 못 놓은 장식이 있음")
end)

test(
	"Scenery Plan.wallPath: 보이지 않는 벽은 물가 바로 바깥(모래사장을 막지 않음)을 따르고 부두를 감쌈",
	function()
		local I, T = SceneryIsland, SceneryPlan.Tuning
		local points = SceneryPlan.wallPath()
		assert(#points >= 20 and #points <= 120, "벽 점 수 " .. #points)
		-- 원점에서 뻗은 반직선이 벽 꺾은선과 만나는 거리
		local function wallDistance(a: number): number
			local dx, dz = math.cos(a), math.sin(a)
			local best = math.huge
			for i, p in points do
				local q = points[i % #points + 1]
				local ex, ez = q[1] - p[1], q[2] - p[2]
				local den = dx * ez - dz * ex
				if math.abs(den) > 1e-9 then
					local t = (p[1] * ez - p[2] * ex) / den
					local s = (p[1] * dz - p[2] * dx) / den
					if t > 0 and s >= -1e-9 and s <= 1 + 1e-9 then
						best = math.min(best, t)
					end
				end
			end
			return best
		end
		local pierAngle, pierFrom, pierTo = SceneryPlan.pierLine()
		for k = 0, 719 do
			local a = k / 720 * math.pi * 2
			local gap = wallDistance(a) - I.coastRadius(a)
			assert(
				gap >= 1.5,
				string.format("%.1f 도: 벽이 물가 안쪽(모래사장을 막음) %.2f", math.deg(a), gap)
			)
			local offPier = math.abs(math.atan2(math.sin(a - pierAngle), math.cos(a - pierAngle))) > math.rad(5)
			if offPier then
				assert(
					gap <= T.WALL.Offset + 2,
					string.format("%.1f 도: 벽이 물가에서 너무 멂 %.2f", math.deg(a), gap)
				)
			end
		end
		-- 부두 끝까지 벽 안(부두 가운데 선이 벽을 가로지르지 않음)
		eq(wallDistance(pierAngle) > pierTo, true, "부두 끝이 벽 밖")
		assert(pierFrom < I.coastRadius(pierAngle), "부두는 모래사장에서 시작")
	end
)

test("Scenery: 계획의 모든 장식 종류를 Props 가 만들 수 있음", function()
	local source = readfile("src/server/Scenery/Props.luau")
	local known = {}
	for name in source:gmatch("function BUILD%.([%w_]+)%(") do
		known[name] = true
	end
	for kind in SceneryPlan.countKinds(SceneryPlan.make()) do
		assert(known[kind], kind .. " 를 만드는 함수가 Props 에 없음")
	end
end)

test(
	"default.project.json: 비상 바닥은 공원 전체를 덮는 세운 원기둥, 윗면이 지형 윗면 바로 밑",
	function()
		local I, T = SceneryIsland, SceneryPlan.Tuning
		local project = readfile("default.project.json")
		assert(project, "default.project.json 을 읽지 못함")
		assert(not project:find('"Baseplate"'), "예전 Baseplate 가 남아 있음")
		local block = project:match('"FallbackGround"%s*:%s*(%b{})')
		assert(block, "FallbackGround 없음")
		assert(block:find('"Shape"%s*:%s*"Cylinder"'), "원기둥이 아님")
		assert(block:find('"Anchored"%s*:%s*true'), "고정 안 됨")
		local h, d1, d2 = block:match('"Size"%s*:%s*%[%s*([%d%.]+)%s*,%s*([%d%.]+)%s*,%s*([%d%.]+)%s*%]')
		eq(tonumber(d1), I.FALLBACK_RADIUS * 2, "지름(Y)")
		eq(tonumber(d2), I.FALLBACK_RADIUS * 2, "지름(Z)")
		local y = block:match('"position"%s*:%s*%[%s*[-%d%.]+%s*,%s*([-%d%.]+)')
		near(tonumber(y) + tonumber(h) / 2, I.FALLBACK_TOP, 1e-9, "윗면 높이")
		assert(I.FALLBACK_TOP < 0 and I.FALLBACK_TOP > -1, "윗면은 지형(y 0) 바로 밑")
		-- 부지·바깥 산책로까지 덮고, 모래사장(지형이 0 보다 낮아지는 곳)에는 안 나옴
		assert(I.FALLBACK_RADIUS > T.OUTER_RING.Radius + T.OUTER_RING.Width / 2, "산책로 밑이 비어 있음")
		assert(I.FALLBACK_RADIUS > farthestPlotCorner(), "부지 밑이 비어 있음")
		assert(I.FALLBACK_RADIUS < I.GRASS_MIN, "모래사장 쪽으로 튀어나옴")
		-- 원기둥 축(로컬 X)이 월드 ±Y 로: 회전 행렬 첫 열 (R00, R10, R20) = (0, ±1, 0)
		local r00, r10, r20 = block:match(
			'"orientation"%s*:%s*%[%s*%[%s*([-%d%.]+)%s*,[^%]]*%]%s*,%s*%[%s*([-%d%.]+)%s*,[^%]]*%]%s*,%s*%[%s*([-%d%.]+)'
		)
		eq(tonumber(r00), 0, "R00")
		eq(math.abs(tonumber(r10) :: number), 1, "|R10|")
		eq(tonumber(r20), 0, "R20")
		-- Scenery 는 지형을 다 만든 뒤 이 이름의 파트를 치움
		assert(
			readfile("src/server/Scenery/init.luau"):find('"FallbackGround"', 1, true),
			"Scenery 가 비상 바닥 이름을 모름"
		)
	end
)

test(
	"default.project.json: 풀잎 장식(Terrain.Decoration)은 place 파일에서 켬 — 스크립트는 안 씀",
	function()
		local project = readfile("default.project.json")
		assert(project, "default.project.json 을 읽지 못함")
		local workspaceBlock = project:match('"Workspace"%s*:%s*(%b{})')
		assert(workspaceBlock, "Workspace 없음")
		local terrain = workspaceBlock:match('"Terrain"%s*:%s*(%b{})')
		assert(terrain, "Workspace.Terrain 없음")
		assert(terrain:find('"%$className"%s*:%s*"Terrain"'), "Terrain 의 $className")
		assert(terrain:find('"Decoration"%s*:%s*true'), "Decoration = true 아님")
		-- NotScriptable: 게임 스크립트가 쓰면 오류(예전엔 pcall + 매번 경고). 주석을 뺀 코드에 쓰기가 없어야 함
		local function code(path: string): string
			local out = {}
			for line in (readfile(path) or ""):gmatch("[^\n]*") do
				table.insert(out, (line:gsub("%-%-.*$", "")))
			end
			return table.concat(out, "\n")
		end
		local function scan(dir: string)
			for _, name in listdir(dir) do
				local path = dir .. "/" .. name
				if name:match("%.luau$") then
					local source = code(path)
					assert(not source:find("%.Decoration%s*="), path .. " 가 Terrain.Decoration 을 씀")
					assert(not source:find("%.GrassLength%s*="), path .. " 가 Terrain.GrassLength 를 씀")
				elseif not name:find("%.") then
					scan(path)
				end
			end
		end
		scan("src")
	end
)

print("\n[ParkService — 부지 바닥·빈 부지 칸 자리 표시 (가짜 Roblox)]")
-- 가짜 Roblox 전역(tools/roblox_mock.luau)은 이 테스트 동안만 깔고 끝나면 되돌림(다른 테스트는 하네스 전역을 씀)
local function withMock(fn: (any, any, any) -> ())
	local saved = {}
	for key, value in _G do
		saved[key] = value
	end
	local ok, err = pcall(function()
		local H = compile(readfile("tests/harness.luau"), "tests/harness.luau")() -- 새 모듈 캐시(가짜 Color3 로 다시 읽음)
		local Mock = compile(readfile("tools/roblox_mock.luau"), "tools/roblox_mock.luau")()
		local sharedNode = H.folder("src/shared")
		Mock.link(Mock.ReplicatedStorage, "Shared", sharedNode)
		fn(H, Mock, sharedNode)
	end)
	for key in _G do
		if saved[key] == nil then
			_G[key] = nil
		end
	end
	for key, value in saved do
		_G[key] = value
	end
	assert(ok, err)
end

test(
	"ParkService: 부지 바닥은 포석, 빈 부지에만 칸 자리 표시 판 36개(충돌·광선·그림자 없음) — 주인이 오면 치우고 떠나면 되돌림",
	function()
		withMock(function(H, Mock, sharedNode)
			local Service = H.require(H.folder("src/server").ParkService)
			local State = H.require(sharedNode.PlayerState)
			local Grid = H.require(sharedNode.ParkGrid)
			local player = { Name = "Tester", DisplayName = "테스터", UserId = 777 }
			local built, buildError = Mock.run(function()
				Service.init()
			end)
			assert(built, buildError)
			local parks = Mock.Workspace:FindFirstChild("Parks")
			assert(parks, "Parks 폴더")

			local function checkGrid(model: any)
				local grid = model:FindFirstChild("EmptyGrid")
				assert(grid, model.Name .. ": EmptyGrid 없음")
				local origin = model:GetAttribute("Origin")
				local marks = grid:GetChildren()
				eq(#marks, State.MAX_SLOTS, model.Name .. " 판 수")
				local seen = {}
				for _, mark in marks do
					eq(mark.Name, "GridMark", "이름")
					assert(
						not mark.CanCollide and not mark.CanQuery and not mark.CanTouch and not mark.CastShadow,
						"충돌·광선·닿기·그림자 끔"
					)
					local p = origin:PointToObjectSpace(mark.Position)
					local bottom, top = p.Y - mark.Size.Y / 2, p.Y + mark.Size.Y / 2
					assert(bottom > Grid.BASE_TOP + 0.005, "밑면이 부지 윗면보다 위(" .. bottom .. ")")
					assert(top - Grid.BASE_TOP >= 0.05 and top - Grid.BASE_TOP <= 0.12, "윗면 높이 " .. top)
					assert(mark.Size.X < Grid.SPACING and mark.Size.Z < Grid.SPACING, "칸보다 작음")
					local slot = Grid.slotAt(p.X, p.Z, 0.01)
					assert(slot and not seen[slot], "칸 가운데에 하나씩")
					seen[slot] = true
				end
			end

			local plots = parks:GetChildren()
			eq(#plots, 8, "부지 수")
			for _, model in plots do
				local base = model:FindFirstChild("Base")
				eq(base.Material, Enum.Material.Pavement, model.Name .. " 바닥 재질")
				local c = base.Color
				assert(
					c.R > 0.85 and c.G > 0.8 and c.B > 0.7 and c.R > c.B,
					model.Name .. " 바닥은 밝고 따뜻한 색"
				)
				checkGrid(model)
				eq(#model:FindFirstChild("Slots"):GetChildren(), 0, "빈 부지에는 칸 모델 없음")
			end

			-- 주인 배정: 그 부지만 표시 판을 치우고, 받침대·잠긴 칸(Slot/Look 속성)이 대신함
			local data = State.new()
			local assigned, assignError = Mock.run(function()
				Service.assign(player :: any)
				Service.update(player :: any, data)
			end)
			assert(assigned, assignError)
			local mine, others = nil, 0
			for _, model in plots do
				if model:GetAttribute("OwnerUserId") == player.UserId then
					mine = model
				else
					others += 1
					checkGrid(model)
				end
			end
			assert(mine, "배정된 부지")
			eq(others, 7, "나머지 빈 부지")
			assert(not mine:FindFirstChild("EmptyGrid"), "주인 부지에는 표시 판 없음")
			local containers = mine:FindFirstChild("Slots"):GetChildren()
			eq(#containers, State.MAX_SLOTS, "칸 모델 36개")
			local locked = 0
			for _, container in containers do
				assert(type(container:GetAttribute("Slot")) == "number", "Slot 속성")
				local look = container:GetAttribute("Look")
				if look == Grid.LOOK_LOCKED then
					locked += 1
					assert(container:FindFirstChild("Locked"), "잠긴 칸 판")
				else
					eq(look, Grid.LOOK_EMPTY, "명소 없는 열린 칸")
					assert(container:FindFirstChild("Pedestal"), "빈 받침대")
				end
			end
			local _, unlocked = State.parkSlots(data)
			eq(locked, State.MAX_SLOTS - unlocked, "잠긴 칸 수")

			-- 떠나면 칸 모델을 치우고 표시 판을 되돌림
			local released, releaseError = Mock.run(function()
				Service.release(player :: any)
			end)
			assert(released, releaseError)
			eq(mine:GetAttribute("OwnerUserId"), nil, "주인 없음")
			eq(#mine:FindFirstChild("Slots"):GetChildren(), 0, "칸 모델 치움")
			checkGrid(mine)
		end)
	end
)

print("\n[Scenery — 산울타리 모양 (가짜 Roblox)]")
test(
	"Scenery: 산울타리는 네모 몸통 + 윗면 잎 공 줄(누운 원기둥 없음), 폭·키·충돌은 예전 발자국 그대로",
	function()
		withMock(function(H)
			local Props = H.require(H.folder("src/server").Scenery.Props)
			for _, length in { 7.5, 12, 22.77 } do
				for style = 1, 3 do
					local folder = Instance.new("Folder")
					local item =
						{ Kind = "Hedge", X = 40.3, Y = 0, Z = -17.8, Turn = 0.7, Height = length, Style = style }
					item.Tint, item.Scale, item.Radius = 0.3, 1, 0.9
					assert(Props.build(folder, item), "Hedge 를 만들지 못함")
					local frame = CFrame.new(item.X, item.Y, item.Z) * CFrame.Angles(0, -item.Turn, 0)
					local what = string.format("길이 %.2f Style %d", length, style)
					local solids, lumps, flowers = 0, 0, 0
					local parts = folder:GetChildren()
					for _, part in parts do
						assert(part.Shape ~= Enum.PartType.Cylinder, what .. ": 원기둥(통나무처럼 보임)")
						local p = frame:PointToObjectSpace(part.Position)
						local size = part.Size
						local halfAlong, halfAcross, halfUp = size.X / 2, size.Z / 2, size.Y / 2
						if part.Shape == Enum.PartType.Block then
							local rel = frame:ToObjectSpace(part.CFrame)
							assert(math.abs(rel.RightVector.X) > 0.999, what .. ": 몸통이 길이 방향")
						end
						assert(
							math.abs(p.X) + halfAlong <= length / 2 + 0.01,
							what .. ": 끝보다 길게 " .. part.Name
						)
						assert(math.abs(p.Z) + halfAcross <= 0.92, what .. ": 폭 1.84 넘음 " .. part.Name)
						assert(p.Y + halfUp <= 2.35, what .. ": 너무 높음 " .. part.Name)
						if math.max(size.X, size.Y, size.Z) < 1.2 then
							assert(not part.CastShadow, what .. ": 작은 조각 그림자")
						end
						if part.CanCollide then
							solids += 1
							eq(part.Name, "Hedge", what .. ": 부딪히는 건 몸통 하나")
							near(part.Size.X, length, 1e-6, what .. ": 몸통 길이")
							assert(
								p.Y + halfUp >= 1.2 and p.Y - halfUp <= 0,
								what .. ": 몸통이 땅부터 1.2 이상"
							)
						else
							assert(not part.CanQuery and not part.CanTouch, what .. ": 잎·꽃 검색·닿기 끔")
						end
						if part.Name == "HedgeTop" then
							lumps += 1
							eq(part.Shape, Enum.PartType.Ball, what .. ": 잎 공")
						elseif part.Name == "Flower" then
							flowers += 1
						end
					end
					eq(solids, 1, what .. ": 부딪히는 몸통")
					assert(
						lumps >= math.max(2, length / 2.5) and lumps <= length / 1.6 + 2,
						what .. ": 잎 공 " .. lumps
					)
					eq(flowers > 0, style == 3, what .. ": 꽃은 꽃 산울타리(Style 3)만")
					eq(#parts, 1 + lumps + flowers, what .. ": 조각 수")
				end
			end
		end)
	end
)

print("\n[유료 상품 — 영수증 처리 · 게임패스 확인 (Purchases, 가짜 Roblox)]")
-- src/server/Purchases.luau 를 실제 Config 상품 번호로 돌림. 서버 쪽 일(세션 표·저장·이벤트·UserOwnsGamePassAsync)은
-- 가짜 deps 로 바꾸고, 기다림(deps.wait)은 가짜 시계만 넘김(onWait 로 "기다리는 동안 생기는 일"을 흉내)
withMock(function(H, _Mock, sharedNode)
	local Purchases = H.require(H.folder("src/server").Purchases)
	local State = H.require(sharedNode.PlayerState)
	local Cfg = H.require(sharedNode.Config)
	local Marks = H.require(sharedNode.Landmarks)
	local GRANTED = Enum.ProductPurchaseDecision.PurchaseGranted
	local NOT_YET = Enum.ProductPurchaseDecision.NotProcessedYet

	-- 가짜 서버: 플레이어·세션·저장·알림 기록
	local function world(): any
		local w: any = {
			now = 0,
			players = {},
			sessions = {},
			present = {},
			ready = {},
			saves = 0,
			saveOk = true,
			pushes = 0,
			serverLuck = {},
			owns = {}, -- PassId -> { 차례로 돌려줄 값("error" = 오류) }. 마지막 값을 계속 씀
			ownsCalls = {},
			changed = 0,
			waits = {},
			onWait = nil,
		}
		w.deps = {
			findPlayer = function(userId)
				return w.players[userId]
			end,
			session = function(player)
				return w.sessions[player]
			end,
			inGame = function(player)
				return w.present[player] == true
			end,
			passesReady = function(player)
				return w.ready[player] == true
			end,
			mods = function(session)
				return { Passes = session.Passes, ServerLuck = false }
			end,
			save = function()
				w.saves += 1
				return w.saveOk
			end,
			serverLuck = function(_player, seconds)
				table.insert(w.serverLuck, seconds)
			end,
			pushState = function()
				w.pushes += 1
			end,
			ownsPass = function(_player, passId)
				w.ownsCalls[passId] = (w.ownsCalls[passId] or 0) + 1
				local script = w.owns[passId] or { false }
				local value = script[math.min(w.ownsCalls[passId], #script)]
				if value == "error" then
					error("HTTP 503 (가짜)")
				end
				return value
			end,
			passesChanged = function()
				w.changed += 1
			end,
			wait = function(seconds)
				table.insert(w.waits, seconds)
				w.now += seconds
				if w.onWait then
					w.onWait(w)
				end
			end,
			clock = function()
				return w.now
			end,
		}
		return w
	end
	-- 접속해서 데이터까지 불러온 플레이어(loaded = false 면 서버에는 있지만 아직 불러오는 중)
	local function join(w: any, userId: number, loaded: boolean?): (any, any)
		local player = { Name = "P" .. userId, DisplayName = "플레이어", UserId = userId }
		w.players[userId] = player
		w.present[player] = true
		local session = { Data = State.new(), LockId = "lock-" .. userId, Passes = {} }
		if loaded ~= false then
			w.sessions[player] = session
			w.ready[player] = true
		end
		return player, session
	end
	local function receipt(userId: number, productKey: string, purchaseId: string): { [string]: any }
		return {
			PlayerId = userId,
			ProductId = State.ProductsById[productKey].ProductId,
			PurchaseId = purchaseId,
			CurrencySpent = 49,
			PlaceIdWherePurchased = 1,
		}
	end
	local function process(w: any, info: { [string]: any }): any
		return Purchases.processReceipt(info, w.deps)
	end

	test(
		"Config: 실제 상품 번호 6개(0 아님·겹치지 않음) + Robux 가격, 번호로 상품 찾기",
		function()
			local seen = {}
			for _, pass in Cfg.GamePasses do
				assert(pass.PassId > 0, pass.Id .. " PassId 가 0")
				assert(not seen[pass.PassId], "번호 중복 " .. pass.PassId)
				seen[pass.PassId] = true
				assert(type(pass.Price) == "number" and pass.Price > 0, pass.Id .. " Price")
				eq(Purchases.passByPassId(pass.PassId), pass, pass.Id)
				eq(
					Purchases.productByProductId(pass.PassId),
					nil,
					pass.Id .. " 게임패스 번호는 개발자 상품이 아님"
				)
			end
			for _, product in Cfg.Products do
				assert(product.ProductId > 0, product.Id .. " ProductId 가 0")
				assert(not seen[product.ProductId], "번호 중복 " .. product.ProductId)
				seen[product.ProductId] = true
				assert(type(product.Price) == "number" and product.Price > 0, product.Id .. " Price")
				eq(Purchases.productByProductId(product.ProductId), product, product.Id)
				eq(
					Purchases.productByProductId(tostring(product.ProductId)),
					product,
					product.Id .. " 문자열 번호"
				)
				eq(Purchases.passByPassId(product.ProductId), nil)
			end
			eq(Purchases.productByProductId(0), nil, "0 = 없음")
			eq(Purchases.productByProductId(nil), nil)
			eq(Purchases.passByPassId(12345), nil)
			assert(
				Cfg.MAX_BOOST_STORED_SECONDS > Cfg.MAX_BOOST_SECONDS * 2,
				"저장 상한은 구매 창 상한보다 훨씬 커야 함"
			)
		end
	)

	test(
		"영수증: PurchaseId 마다 한 번만 지급, 같은 영수증을 다시 불러도 저장만 다시(PurchaseGranted)",
		function()
			local w = world()
			local _, session = join(w, 1)
			eq(process(w, receipt(1, "LuckBoost", "p1")), GRANTED, "첫 지급")
			eq(session.Data.Boosts.LuckBoost, 900, "행운 부스트 15분")
			eq(w.saves, 1, "저장 1번")
			eq(w.pushes, 1, "상태 보냄")
			eq(State.hasReceipt(session.Data, "p1"), true, "영수증 기록")
			eq(process(w, receipt(1, "LuckBoost", "p1")), GRANTED, "다시 불림")
			eq(session.Data.Boosts.LuckBoost, 900, "두 번 지급 안 함")
			eq(w.saves, 2, "저장만 다시")
			eq(w.pushes, 1)
			eq(process(w, receipt(1, "LuckBoost", "p2")), GRANTED, "다른 구매")
			eq(session.Data.Boosts.LuckBoost, 1800, "시간 누적")
			eq(#w.waits, 0, "데이터가 있으면 기다리지 않음")
		end
	)

	test(
		"영수증: 저장 실패 = NotProcessedYet(효과는 한 번만), 다시 불렸을 때 저장되면 PurchaseGranted",
		function()
			local w = world()
			local _, session = join(w, 2)
			w.saveOk = false
			eq(process(w, receipt(2, "CoinPack", "c1")), NOT_YET, "저장 실패")
			eq(session.Data.Coins, 1000, "코인은 바로 줌(수입 0 이면 최소 1000)")
			eq(process(w, receipt(2, "CoinPack", "c1")), NOT_YET, "또 저장 실패")
			eq(session.Data.Coins, 1000, "다시 불려도 두 번 주지 않음")
			w.saveOk = true
			eq(process(w, receipt(2, "CoinPack", "c1")), GRANTED, "저장 성공")
			eq(session.Data.Coins, 1000)
			eq(w.saves, 3)
		end
	)

	test(
		"영수증: 모르는 상품 · 서버에 없는 플레이어 · Studio(저장 안 함) = NotProcessedYet",
		function()
			local w = world()
			local _, session = join(w, 3)
			local unknown = receipt(3, "CoinPack", "u1")
			unknown.ProductId = 999
			eq(process(w, unknown), NOT_YET, "모르는 상품 번호")
			local passNumber = receipt(3, "CoinPack", "u2")
			passNumber.ProductId = Cfg.GamePasses[1].PassId
			eq(process(w, passNumber), NOT_YET, "게임패스 번호")
			eq(#session.Data.Receipts, 0, "영수증 기록 없음")
			eq(session.Data.Coins, 0, "아무것도 안 줌")
			eq(w.saves, 0, "저장 안 함")
			eq(process(w, receipt(404, "CoinPack", "u3")), NOT_YET, "서버에 없는 플레이어")
			eq(#w.waits, 0, "없는 플레이어는 기다리지 않음")

			session.LockId = nil
			eq(process(w, receipt(3, "LuckBoost", "s1")), NOT_YET, "Studio: 완료 처리 안 함")
			eq(session.Data.Boosts.LuckBoost, 900, "효과는 적용")
			eq(process(w, receipt(3, "LuckBoost", "s1")), NOT_YET)
			eq(session.Data.Boosts.LuckBoost, 900, "두 번 지급 안 함")
			eq(w.saves, 0)
		end
	)

	test(
		"영수증: 데이터를 불러오는 중이면 세션이 생길 때까지 기다렸다가 지급(나가거나 너무 오래면 NotProcessedYet)",
		function()
			local w = world()
			local player, session = join(w, 4, false)
			w.onWait = function(world)
				if world.now >= 3 then
					world.sessions[player] = session
				end
			end
			eq(process(w, receipt(4, "LuckBoost", "l1")), GRANTED, "불러온 뒤 지급")
			near(w.now, 3, 1e-9, "3초 기다림")
			eq(session.Data.Boosts.LuckBoost, 900)

			w = world()
			player, session = join(w, 5, false)
			eq(process(w, receipt(5, "LuckBoost", "l2")), NOT_YET, "끝내 못 불러옴")
			assert(w.now >= Purchases.SESSION_WAIT and w.now < Purchases.SESSION_WAIT + 1, "최대 대기 " .. w.now)
			eq(session.Data.Boosts.LuckBoost, nil, "지급 안 함")

			w = world()
			player, session = join(w, 6, false)
			w.onWait = function(world)
				if world.now >= 2 then
					world.present[player] = false -- 불러오는 중에 나감(또는 불러오기 실패로 Kick)
				end
			end
			eq(process(w, receipt(6, "LuckBoost", "l3")), NOT_YET, "나가면 바로 그만")
			assert(w.now < 3, "나간 뒤 더 기다리지 않음 " .. w.now)
			eq(session.Data.Boosts.LuckBoost, nil)
			eq(w.saves, 0)
		end
	)

	test(
		"코인 팩: max(1000, 초당 수입 × 1800), 수입 2배 반영 — 접속 시 게임패스 확인을 기다렸다가 지급",
		function()
			local function withPyramid(w: any, userId: number): (any, any)
				local player, session = join(w, userId)
				State.applyRoll(session.Data, Marks.ById.pyramid) -- 초당 12
				session.Data.Coins = 0
				return player, session
			end
			local w = world()
			local _, session = withPyramid(w, 7)
			eq(process(w, receipt(7, "CoinPack", "k1")), GRANTED)
			eq(session.Data.Coins, 12 * 1800, "초당 수입 × 1800")

			-- 게임패스 확인 중에 온 코인 팩: 확인이 끝나(수입 2배 보유) 2배로 지급
			w = world()
			local player
			player, session = withPyramid(w, 8)
			w.ready[player] = false
			w.onWait = function(world)
				if world.now >= 2 then
					session.Passes.DoubleIncome = true
					world.ready[player] = true
				end
			end
			eq(process(w, receipt(8, "CoinPack", "k2")), GRANTED)
			eq(session.Data.Coins, 24 * 1800, "수입 2배 확인 뒤 지급")
			near(w.now, 2, 1e-9, "확인이 끝날 때까지만 기다림")
			w.now = 0
			eq(process(w, receipt(8, "CoinPack", "k2")), GRANTED, "같은 영수증")
			eq(w.now, 0, "이미 준 영수증은 기다리지 않음")
			eq(session.Data.Coins, 24 * 1800)

			-- 확인이 끝나지 않으면 PASS_WAIT 뒤 지금 아는 대로(무한정 미루지 않음)
			w = world()
			player, session = withPyramid(w, 9)
			w.ready[player] = false
			eq(process(w, receipt(9, "CoinPack", "k3")), GRANTED)
			eq(session.Data.Coins, 12 * 1800)
			assert(w.now >= Purchases.PASS_WAIT and w.now < Purchases.PASS_WAIT + 1, "PASS_WAIT " .. w.now)

			-- 부스트는 게임패스와 상관없으니 기다리지 않음
			w = world()
			player, session = join(w, 10)
			w.ready[player] = false
			eq(process(w, receipt(10, "LuckBoost", "k4")), GRANTED)
			eq(w.now, 0, "행운 부스트는 바로")
		end
	)

	test(
		"시간 부스트: 결제된 시간은 3시간 넘어도 다 더함, 서버 행운은 서버 타이머로, 구매 창은 3시간에서 막음",
		function()
			local w = world()
			local _, session = join(w, 11)
			session.Data.Boosts.LuckBoost = Cfg.MAX_BOOST_SECONDS - 100
			eq(process(w, receipt(11, "LuckBoost", "b1")), GRANTED)
			eq(session.Data.Boosts.LuckBoost, Cfg.MAX_BOOST_SECONDS + 800, "15분 다")
			eq(process(w, receipt(11, "ServerLuck", "b2")), GRANTED)
			eq(#w.serverLuck, 1, "서버 행운 한 번")
			eq(w.serverLuck[1], 900, "15분")
			eq(session.Data.Boosts.ServerLuck, nil, "개인 데이터에 저장 안 함")
			eq(process(w, receipt(11, "ServerLuck", "b2")), GRANTED)
			eq(#w.serverLuck, 1, "같은 영수증은 한 번만")

			-- 서버 행운 타이머: (끝나는 시각, 지금, 초) -> (새 끝나는 시각, 더한 초)
			local untilTime, added = Purchases.extendUntil(0, 100, 900)
			eq(untilTime, 1000, "꺼져 있으면 지금부터")
			eq(added, 900)
			untilTime, added = Purchases.extendUntil(100 + Cfg.MAX_BOOST_SECONDS - 100, 100, 900)
			eq(added, 900, "3시간 가까이 남아도 다 더함")
			eq(untilTime, 100 + Cfg.MAX_BOOST_SECONDS + 800)
			untilTime, added = Purchases.extendUntil(100 + Cfg.MAX_BOOST_STORED_SECONDS - 10, 100, 900)
			eq(added, 10, "저장 상한에서만 멈춤")

			-- 구매 창 조건(BuyProduct): 남은 시간 + 15분이 3시간을 넘으면 "max"
			local product, reason = Purchases.promptCheck("LuckBoost", nil, 0)
			eq(product, nil)
			eq(reason, "loading", "세션 없음 = 불러오는 중")
			session.Data.Boosts.LuckBoost = nil
			product, reason = Purchases.promptCheck("LuckBoost", session, 0)
			eq(product, State.ProductsById.LuckBoost, "부스트 없음 = 구매 창")
			eq(reason, nil)
			session.Data.Boosts.LuckBoost = Cfg.MAX_BOOST_SECONDS - 900
			eq(
				(Purchases.promptCheck("LuckBoost", session, 0)),
				State.ProductsById.LuckBoost,
				"딱 3시간까지는 됨"
			)
			session.Data.Boosts.LuckBoost = Cfg.MAX_BOOST_SECONDS - 899
			product, reason = Purchases.promptCheck("LuckBoost", session, 0)
			eq(product, nil)
			eq(reason, "max", "3시간 넘음")
			product, reason = Purchases.promptCheck("ServerLuck", session, Cfg.MAX_BOOST_SECONDS - 899)
			eq(reason, "max", "서버 행운은 서버 타이머 기준")
			eq((Purchases.promptCheck("ServerLuck", session, 0)), State.ProductsById.ServerLuck)
			eq((Purchases.promptCheck("CoinPack", session, Cfg.MAX_BOOST_SECONDS)), State.ProductsById.CoinPack)
			product, reason = Purchases.promptCheck("Nope", session, 0)
			eq(product, nil)
			eq(reason, nil, "모르는 상품")
			eq((Purchases.promptCheck(5, session, 0)), nil)
		end
	)

	test(
		"게임패스: 접속 확인이 오류 나면 오류 난 패스만 1·2·4초 뒤 다시, 찾으면 바로 반영",
		function()
			local VIP = State.PassesById.LuckVIP.PassId
			local FAST = State.PassesById.FastRoll.PassId
			local DOUBLE = State.PassesById.DoubleIncome.PassId
			local w = world()
			local player = join(w, 20)
			w.owns[VIP] = { true }
			w.owns[FAST] = { false }
			w.owns[DOUBLE] = { "error", "error", true }
			local owned = {}
			eq(Purchases.checkPasses(player, owned, w.deps), 0, "모두 확인")
			eq(owned.LuckVIP, true)
			eq(owned.FastRoll, nil, "안 가진 패스")
			eq(owned.DoubleIncome, true, "세 번째에 확인")
			eq(w.ownsCalls[VIP], 1, "확인된 패스는 다시 안 물음")
			eq(w.ownsCalls[FAST], 1)
			eq(w.ownsCalls[DOUBLE], 3)
			eq(w.changed, 2, "찾을 때마다 반영(처음 VIP, 나중에 수입 2배)")
			eq(w.now, 1 + 2, "1초, 2초 기다림")

			w = world()
			player = join(w, 21)
			w.owns[VIP] = { "error" }
			w.owns[FAST] = { "error" }
			w.owns[DOUBLE] = { "error" }
			owned = {}
			eq(Purchases.checkPasses(player, owned, w.deps), 3, "끝까지 실패")
			eq(w.ownsCalls[VIP], 1 + #Purchases.PASS_RETRY, "처음 + 다시 확인")
			eq(w.now, 1 + 2 + 4)
			eq(next(owned), nil)
			eq(w.changed, 0)

			w = world()
			player = join(w, 22)
			w.owns[DOUBLE] = { "error" }
			w.onWait = function(world)
				world.present[player] = false
			end
			owned = {}
			eq(Purchases.checkPasses(player, owned, w.deps), 1, "나가면 그만")
			eq(w.ownsCalls[DOUBLE], 1)
			eq(#w.waits, 1)
		end
	)

	test(
		"게임패스: 구매 창 전에 다시 확인(접속 확인 실패·웹사이트 구매) — 가졌으면 반영하고 창을 안 띄움",
		function()
			local pass = State.PassesById.DoubleIncome
			local w = world()
			local player = join(w, 30)
			local owned = { DoubleIncome = true }
			eq(Purchases.recheckPass(player, owned, pass, w.deps), true, "이미 앎")
			eq(w.ownsCalls[pass.PassId], nil, "묻지 않음")
			owned = {}
			w.owns[pass.PassId] = { true }
			eq(Purchases.recheckPass(player, owned, pass, w.deps), true, "다시 확인하니 가짐")
			eq(owned.DoubleIncome, true)
			eq(w.changed, 1, "상태·간판 갱신")
			owned = {}
			w.owns[pass.PassId] = { false }
			w.ownsCalls = {}
			eq(Purchases.recheckPass(player, owned, pass, w.deps), false, "안 가짐 = 구매 창")
			w.owns[pass.PassId] = { "error" }
			w.ownsCalls = {}
			eq(
				Purchases.recheckPass(player, owned, pass, w.deps),
				false,
				"오류 = 구매 창(로블록스가 중복 결제는 막음)"
			)
			eq(owned.DoubleIncome, nil)
			eq(w.changed, 1)
		end
	)
end)

if not Harness.finish() then
	error("테스트 실패")
end
