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
local Skills = loader.require(shared.Skills)
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
check("술법·공법 데이터", function()
	eq(#Skills.actives, 4, "술법 4개")
	for index, def in Skills.actives do
		eq(def.key, index, def.name .. " 단축키")
		assert(def.cooldown and def.cooldown > 0, def.name .. " 쿨타임")
	end
	for _, def in Skills.list do
		assert(Realms.byId[def.minRealm], def.name .. " 경지 id")
	end
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
	local advanced = Progression.addQi(data, 1e12)
	eq(data.step, 16, "연기기 14층에서 멈춤")
	eq(advanced, 13)
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
	local ok = Progression.attemptBreakthrough(data, 0)
	eq(ok.kind, "success")
	eq(data.step, 17, "축기기 영성 1")
	eq(data.qi, 0)
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
	Progression.passTribulation(data)
	eq(data.step, 45, "결단기 초기")
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
check("비급 익히기와 공법 장착", function()
	local data = Progression.newData()
	eq(Progression.slots(data), 1, "범인은 공법 1칸")
	eq((Progression.learn(data, "chwiryeong")), false, "연기기부터 익힐 수 있는 비급")
	eq((Progression.learn(data, "없는것")), false)

	eq((Progression.learn(data, "tonap")), true)
	eq(Progression.knows(data, "tonap"), true)
	eq(Progression.passive(data, "tonap"), true, "빈 칸이 있으면 바로 장착")
	eq((Progression.learn(data, "tonap")), false, "같은 비급은 다시 못 익힌다")

	eq((Progression.learn(data, "baekcho")), true)
	eq(Progression.passive(data, "baekcho"), false, "칸이 없으면 익히기만")
	eq((Progression.equip(data, "baekcho")), false, "칸이 모자라다")
	eq((Progression.unequip(data, "tonap")), true)
	eq((Progression.equip(data, "baekcho")), true)
	eq(Progression.passive(data, "baekcho"), true)
	eq((Progression.equip(data, "gyeongsin")), false, "술법은 장착하지 않는다")

	data.step = Realms.firstStepById.yeongi
	eq(Progression.slots(data), 2, "연기기부터 2칸")
	data.step = Realms.firstStepById.gyeoldan
	eq(Progression.slots(data), 3, "결단기부터 3칸")
	eq(data.stats.manuals, 2)
end)
check("공법 효과", function()
	local data = Progression.newData()
	data.step = 45
	local baseRate = Progression.qiPerSecond(data, 1)
	local baseHp = Progression.maxHealth(data)
	local baseHerb = Progression.herbQi(data, false)
	for _, id in { "tonap", "geumgang", "baekcho", "piroe", "cheongi", "cheongsim" } do
		data.skills[id] = true
	end
	data.equipped = { "tonap", "geumgang", "baekcho" }
	assert(Progression.qiPerSecond(data, 1) > baseRate * 1.29, "토납법")
	assert(Progression.qiPerSecond(data, 1, 2) > Progression.qiPerSecond(data, 1) * 1.99, "취령진 배율")
	assert(Progression.maxHealth(data) > baseHp * 1.39, "금강체")
	assert(Progression.herbQi(data, false) > baseHerb * 1.59, "백초경")
	eq(Progression.tribulationDamage(data, 100), 100, "피뢰결 안 끼면 그대로")
	data.equipped = { "piroe", "cheongi", "cheongsim" }
	eq(Progression.tribulationDamage(data, 100), 70, "피뢰결")
	eq(Progression.telegraphTime(data, 1), 1.4, "천기감응")

	local d2 = Progression.newData()
	d2.step = 16
	local plain = Progression.breakChance(d2) :: number
	d2.skills.cheongsim = true
	d2.equipped = { "cheongsim" }
	eq(Progression.breakChance(d2), plain + 0.15, "청심결 돌파 확률")
end)
check("체력", function()
	local data = Progression.newData()
	eq(Progression.maxHealth(data), Balance.BASE_HP, "범인 기본 체력")
	data.step = 45
	assert(Progression.maxHealth(data) >= Balance.BASE_HP * 2, "경지가 체력을 올린다")
end)
check("저장 데이터 정리", function()
	local data = Progression.reconcile({
		step = 9999,
		qi = -5,
		enlightenment = 12.7, -- 예전 판의 깨달음은 버린다
		insights = { gongbeop = 3 },
		skills = { tonap = true, baekcho = true, unknown = true, cheongi = "x" },
		equipped = { "tonap", "tonap", "baekcho", "gyeongsin", "unknown", "cheongsim" },
		stats = { herbs = 4 },
	})
	eq(data.step, Realms.maxStep)
	eq(data.qi, 0)
	eq((data :: any).enlightenment, nil)
	eq((data :: any).insights, nil)
	eq(data.skills.tonap, true)
	eq(data.skills.unknown, nil)
	eq(data.skills.cheongi, nil)
	eq(#data.equipped, 2, "익힌 공법만, 겹치지 않게")
	eq(data.equipped[1], "tonap")
	eq(data.equipped[2], "baekcho")
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
	eq(tags.ManualSpot, 18, "ManualSpot 태그")
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
