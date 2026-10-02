-- 블록수선전 로직 테스트.   실행: lune run tests/run   (blocksuseon 폴더에서)
--
-- 1) 경지·공식·진행 로직(순수 Luau)을 검사하고
-- 2) @lune/roblox 로 연국 맵을 실제 인스턴스로 지어 속성 이름·태그를 검사한다.

local roblox = require("@lune/roblox")
local Harness = require("./harness")

local passed, failed = 0, 0

local function check(name: string, fn: () -> ())
	local ok, err = pcall(fn)
	if ok then
		passed += 1
	else
		failed += 1
		print(`  ✗ {name}\n      {err}`)
	end
end

local function eq(actual: any, expected: any, what: string?)
	if actual ~= expected then
		error(`{what or "값"}: {tostring(expected)} 기대, {tostring(actual)} 받음`, 2)
	end
end

local loader = Harness.new({
	-- shared 모듈은 Roblox 전역을 쓰지 않는다. World 는 아래에서 roblox 전역을 넣어 따로 부른다.
})
local shared = loader.folder("src/shared")

local Realms = loader.require(shared.Realms)
local Balance = loader.require(shared.Balance)
local Insights = loader.require(shared.Insights)
local MartialRanks = loader.require(shared.MartialRanks)
local Progression = loader.require(shared.Progression)
local Format = loader.require(shared.Format)

print("경지")
check("단계 수", function()
	eq(Realms.maxStep, 81, "maxStep")
	eq(Realms.label(1), "범인")
	eq(Realms.label(2), "단수기")
	eq(Realms.label(3), "연기기 1층")
	eq(Realms.label(16), "연기기 14층")
	eq(Realms.label(17), "축기기 영성 1")
	eq(Realms.label(45), "결단기 초기")
	eq(Realms.label(81), "성반기 8도")
end)
check("병목 위치", function()
	eq(Realms.nextIsMajor(1), true, "범인→단수기")
	eq(Realms.nextIsMajor(3), false, "연기기 1층→2층")
	eq(Realms.nextIsMajor(16), true, "연기기 14층→축기기")
	eq(Realms.nextIsMajor(81), false, "최고 경지")
	eq(Realms.firstStepById.gyeoldan, 45)
end)
check("천겁은 결단기부터", function()
	for _, realm in Realms.list do
		local index = table.find(Realms.list, realm) :: number
		local needs = index >= table.find(Realms.list, Realms.byId.gyeoldan) :: number
		eq(realm.tribulation ~= nil, needs, realm.name .. " 천겁")
		eq(realm.breakChance ~= nil, not needs and index > 1, realm.name .. " 돌파 확률")
	end
end)

print("공식")
check("병목 배율", function()
	local plain = math.floor(Balance.QI_BASE * Balance.QI_GROWTH ^ 2)
	eq(Balance.qiRequired(3), plain, "연기기 1층 필요 영력")
	eq(Balance.qiRequired(1), math.floor(Balance.QI_BASE * Balance.BOTTLENECK_MULT), "범인 필요 영력")
end)
check("깨달음 비용 증가", function()
	for _, def in Insights.list do
		local last = 0
		for level = 0, def.maxLevel - 1 do
			local cost = Insights.cost(def.id, level)
			assert(cost >= last and cost > 0, `{def.id} Lv.{level} 비용 {cost}`)
			last = cost
		end
	end
end)
check("무공 경지", function()
	eq(MartialRanks.indexFor(0), 1)
	eq(MartialRanks.indexFor(20), 2)
	eq(MartialRanks.indexFor(1e9), #MartialRanks.list)
end)
check("숫자 포맷", function()
	eq(Format.qi(999), "999")
	eq(Format.qi(12345), "1.2만")
	eq(Format.qi(10000), "1만")
	eq(Format.qi(3.4e8), "3.4억")
	eq(Format.qi(1234567), "123만")
	eq(Format.percent(0.805), "81%")
end)

print("진행")
check("같은 경지 안에서는 저절로 오르고 병목에서 멈춘다", function()
	local data = Progression.newData()
	data.step = 3 -- 연기기 1층
	local advanced, points = Progression.addQi(data, 1e12)
	eq(data.step, 16, "연기기 14층에서 멈춤")
	eq(advanced, 13)
	assert(points > 0, "깨달음을 얻어야 한다")
	eq(data.qi, Balance.qiRequired(16), "병목에서 영력 상한")
	eq(Progression.isCapped(data), true)
end)
check("돌파 성공/실패", function()
	local data = Progression.newData()
	data.step = 16
	data.qi = Balance.qiRequired(16)
	local fail = Progression.attemptBreakthrough(data, 0.9999)
	eq(fail.kind, "fail")
	eq(data.step, 16, "실패해도 경지 유지")
	assert(data.qi < Balance.qiRequired(16), "주화입마로 영력 손실")

	local blocked = Progression.attemptBreakthrough(data, 0)
	eq(blocked.kind, "blocked", "영력이 모자라면 막힘")

	data.qi = Balance.qiRequired(16)
	local before = data.enlightenment
	local ok = Progression.attemptBreakthrough(data, 0)
	eq(ok.kind, "success")
	eq(data.step, 17, "축기기 영성 1")
	eq(data.qi, 0)
	eq(data.enlightenment - before, Balance.breakthroughPoints(4))
end)
check("같은 경지 안에서는 돌파 버튼이 막힌다", function()
	local data = Progression.newData()
	data.step = 5
	data.qi = 1e9
	eq(Progression.attemptBreakthrough(data, 0).kind, "blocked")
end)
check("천겁", function()
	local data = Progression.newData()
	data.step = 44 -- 축기기 영성 28
	data.qi = Balance.qiRequired(44)
	eq(Progression.attemptBreakthrough(data, 0).kind, "tribulation")
	eq(data.step, 44, "천겁 시작만으로는 오르지 않는다")

	local lost = Progression.failTribulation(data)
	assert(lost > 0, "천겁 실패 손실")
	eq(data.step, 44, "천겁 실패해도 경지 유지")
	eq(data.stats.tribulationFails, 1)

	data.qi = Balance.qiRequired(44)
	local points = Progression.passTribulation(data)
	eq(data.step, 45, "결단기 초기")
	eq(points, Balance.tribulationPoints(5))
	eq(data.stats.tribulations, 1)
end)
check("최고 경지", function()
	local data = Progression.newData()
	data.step = Realms.maxStep
	Progression.addQi(data, 1e30)
	eq(data.step, Realms.maxStep)
	eq(data.qi, Balance.qiRequired(Realms.maxStep))
	eq(Progression.attemptBreakthrough(data, 0).kind, "blocked")
end)
check("깨달음 강화", function()
	local data = Progression.newData()
	local ok = Progression.buyInsight(data, "gongbeop")
	eq(ok, false, "깨달음 없으면 실패")
	data.enlightenment = 1000
	ok = Progression.buyInsight(data, "gongbeop")
	eq(ok, true)
	eq(data.insights.gongbeop, 1)
	eq(data.enlightenment, 1000 - Insights.cost("gongbeop", 0))
	eq((Progression.buyInsight(data, "없는것")), false)
	data.insights.geobun = Insights.byId.geobun.maxLevel
	eq((Progression.buyInsight(data, "geobun")), false, "최대 레벨")
end)
check("무공 수련", function()
	local data = Progression.newData()
	eq(Progression.addMartialExp(data, 5), nil)
	eq(Progression.addMartialExp(data, 20), 2, "삼류")
	assert(Progression.maxHealth(data) > Balance.BASE_HP, "무공이 체력을 올린다")
	assert(Progression.walkSpeed(data) > Balance.BASE_WALKSPEED, "무공이 경공을 올린다")
end)
check("저장 데이터 정리", function()
	local data = Progression.reconcile({
		step = 9999,
		qi = -5,
		martialExp = 0 / 0,
		enlightenment = 12.7,
		insights = { gongbeop = 999, unknown = 3, dosim = "x" },
		stats = { herbs = 4 },
	})
	eq(data.step, Realms.maxStep)
	eq(data.qi, 0)
	eq(data.martialExp, 0, "NaN 은 버린다")
	eq(data.enlightenment, 12)
	eq(data.insights.gongbeop, Insights.byId.gongbeop.maxLevel)
	eq(data.insights.unknown, nil)
	eq(data.insights.dosim, nil)
	eq(data.stats.herbs, 4)
	eq(data.stats.tribulations, 0)
	eq(Progression.reconcile(nil).step, 1)
	eq(Progression.reconcile("garbage").step, 1)
end)

print("조사")
check("받침에 맞는 조사", function()
	local Josa = loader.require(shared.Josa)
	eq(Josa.eul("결단기"), "결단기를")
	eq(Josa.eul("1.2만"), "1.2만을")
	eq(Josa.eul("35"), "35를")
	eq(Josa.eul("340"), "340을")
	eq(Josa.ro("단수기"), "단수기로")
	eq(Josa.ro("연국"), "연국으로")
	eq(Josa.ro("하늘"), "하늘로")
	eq(Josa.i("공법 숙련"), "공법 숙련이")
	eq(Josa.i("겁운 감지"), "겁운 감지가")
	eq(Josa.eun("도심"), "도심은")
end)

print("맵")
local World
check("연국 맵 짓기", function()
	local game = roblox.Instance.new("DataModel")
	local env = Harness.robloxGlobals(game)
	local worldLoader = Harness.new(env)
	World = worldLoader.require(worldLoader.folder("src/server").World)

	local workspace = game:GetService("Workspace")
	local map = World.build(workspace, game:GetService("Lighting"))
	eq(map.Parent, workspace)

	local tags: { [string]: number } = {}
	local parts = 0
	for _, inst in map:GetDescendants() do
		if inst:IsA("BasePart") then
			parts += 1
		end
		for _, tag in inst:GetTags() do
			tags[tag] = (tags[tag] or 0) + 1
		end
	end
	eq(tags.Ground, 1, "Ground 태그")
	eq(tags.Vein, 3, "Vein 태그")
	eq(tags.HerbZone, 1, "HerbZone 태그")
	eq(tags.TrainingDummy, 6, "TrainingDummy 태그")
	for _, inst in map:GetDescendants() do
		if inst:HasTag("Vein") then
			assert(Balance.VEINS[inst:GetAttribute("VeinId")], "영맥 id")
			assert(type(inst:GetAttribute("Radius")) == "number", "영맥 반경")
		end
	end
	print(`  파트 {parts}개`)
end)

print("\n진행 속도 (영맥 없이 / 각 경지에 맞는 최고 영맥, 강화 없음)")
do
	local veinFor = function(step: number): number
		local best = 1
		for _, vein in Balance.VEINS do
			if step >= Realms.firstStepById[vein.minRealm] then
				best = math.max(best, vein.mult)
			end
		end
		return best
	end
	local plain, veined = 0, 0
	for step = 1, Realms.maxStep - 1 do
		local req = Balance.qiRequired(step)
		plain += req / Balance.qiPerSecond(step, 1, 0)
		veined += req / Balance.qiPerSecond(step, veinFor(step), 0)
		if Realms.nextIsMajor(step) then
			local target = Realms.get(step + 1).realm
			print(string.format("  %-6s 도달: %6.1f분 / %6.1f분", target.name, plain / 60, veined / 60))
		end
	end
end

print(`\n통과 {passed} · 실패 {failed}`)
if failed > 0 then
	error("테스트 실패")
end
