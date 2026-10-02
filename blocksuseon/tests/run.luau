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

local Roots = loader.require(shared.Roots)
local Tasks = loader.require(shared.Tasks)
local Clock = loader.require(shared.Clock)
local Trials = loader.require(shared.Trials)

-- 테스트는 모든 경지의 과업을 켠 상태로 검사한다
Tasks.LIVE_UNTIL = Realms.maxStep
local YEONGI = Realms.firstStepById.yeongi
local CHUKGI = Realms.firstStepById.chukgi

print("경지")
check("단계 수", function()
	eq(Realms.maxStep, 56, "maxStep (범인~천인기)")
	eq(Realms.label(1), "범인")
	eq(Realms.label(2), "단수기")
	eq(Realms.label(3), "연기기 1성 칠십이지살")
	eq(Realms.label(16), "연기기 14성 무극영운")
	eq(Realms.label(17), "축기기 각수성")
	eq(Realms.label(44), "축기기 진수성")
	eq(Realms.label(45), "결단기 천시원")
	eq(Realms.label(56), "천인기 천원")
end)
check("병목 위치", function()
	eq(Realms.nextIsMajor(1), true, "범인→단수기")
	eq(Realms.nextIsMajor(3), false, "연기기 1성→2성")
	eq(Realms.nextIsMajor(16), true, "연기기 14성→축기기")
	eq(Realms.nextIsMajor(56), false, "최고 경지")
	eq(Realms.firstStepById.gyeoldan, 45)
end)
check("천겁은 원영기부터, 원작 줄기 수", function()
	for step = 1, Realms.firstStepById.wonyeong - 2 do
		eq(Realms.tribulationAfter(step), nil, Realms.label(step) .. " 다음 천겁 없음")
	end
	local counts = {}
	for step = Realms.firstStepById.wonyeong - 1, Realms.maxStep - 1 do
		local trib = Realms.tribulationAfter(step)
		assert(trib, Realms.label(step) .. " 다음 천겁")
		table.insert(counts, trib.waves * trib.simul)
	end
	eq(table.concat(counts, " "), "1 2 3 4 5 10 15 20", "원영 1~4, 천인 5~20")
	eq(Realms.tribulationAfter(Realms.maxStep), nil)
end)

print("공식")
check("병목 배율", function()
	local plain = math.floor(Balance.QI_BASE * Balance.QI_GROWTH ^ 2)
	eq(Balance.qiRequired(3), plain, "연기기 1성 필요 영력")
	eq(Balance.qiRequired(1), math.floor(Balance.QI_BASE * Balance.BOTTLENECK_MULT), "범인 필요 영력")
end)
check("술법·공법 데이터", function()
	eq(#Skills.actives, 4, "술법 4개")
	for _, def in Skills.actives do
		assert(def.cooldown and def.cooldown > 0, def.name .. " 쿨타임")
	end
	for _, key in Progression.DEFAULT_KEYS do
		assert(Progression.isBindable(key), key .. " 기본 키는 쓸 수 있어야 한다")
	end
	for _, reserved in { "W", "A", "S", "D", "R", "B", "C", "F", "One", "Two", "Space" } do
		eq(Progression.isBindable(reserved), false, reserved .. " 는 막아야 한다")
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

print("영근과 시계")
check("영근 고르기", function()
	eq(Roots.make({ "wood" }).kind, "cheon")
	eq(Roots.make({ "fire", "wood" }).kind, "jin")
	eq(Roots.make({ "fire", "wood" }).elements[1], "wood", "오행 순서로 정리")
	eq(Roots.make({ "wood", "fire", "earth", "metal" }).kind, "jap")
	eq(Roots.make({}), nil)
	eq(Roots.make({ "wood", "wood" }), nil, "겹치면 거절")
	eq(Roots.make({ "light" }), nil)
	eq(Roots.strands(Roots.make({ "wood", "fire", "earth", "metal", "water" })), 25)
	eq(Roots.strands(Roots.hong()), 4)
	assert(Roots.gain(Roots.make({ "wood" })) > Roots.gain(Roots.make({ "wood", "fire", "earth", "metal", "water" })))
	eq(Roots.canSkip(Roots.make({ "wood", "fire", "earth", "metal" })), false, "잡영근은 선각후통만")
	eq(Roots.describe(Roots.make({ "water", "wood" })), "진영근 (목, 수)")
end)
check("낮밤과 시운", function()
	eq(Clock.phase(0), "day")
	eq(Clock.phase(430), "dusk")
	eq(Clock.phase(500), "night")
	eq(Clock.phase(700), "dawn")
	eq(Clock.clockTime(0), 6)
	eq(Clock.clockTime(450), 20)
	eq(Clock.untilPhase(400, "night"), 50)
	eq(Clock.untilPhase(500, "night"), 0)
	local from, to = Clock.sigun("cheong", 30)
	eq(to - from, 30, "천영근 시운 30초")
	local inside, left = Clock.sigunState(from + 5, "cheong", 30)
	eq(inside, true)
	eq(left, 25)
	local outside, wait = Clock.sigunState(0, "yang", 120)
	eq(outside, false)
	assert(wait > 0)
	eq(Clock.format(192), "3분 12초")
	eq(Clock.format(40), "40초")
end)
check("내관 문제와 답", function()
	local params = { nodes = 9, lengths = { 3, 4 } }
	local a = Trials.generate("sequence", 77, params)
	local b = Trials.generate("sequence", 77, params)
	eq(table.concat(a.rounds[2], ","), table.concat(b.rounds[2], ","), "같은 seed 같은 문제")
	eq(Trials.check("sequence", a, a.rounds), true)
	eq(Trials.check("sequence", a, { a.rounds[1] }), false)
	for seed = 1, 30 do
		local puzzle = Trials.generate("arrange", seed, {})
		eq(Trials.isMagic(puzzle.start), false, "섞인 판은 정답이 아니다")
		eq(#puzzle.fixed, 3)
		eq(Trials.check("arrange", puzzle, puzzle.start), false)
	end
	local puzzle = Trials.generate("arrange", 5, {})
	-- 고정 칸을 지키는 정답이 하나는 있다: 낙서를 돌리고 뒤집은 8가지 중에서 찾는다
	local found = false
	for _, grid in
		{
			{ 4, 9, 2, 3, 5, 7, 8, 1, 6 },
			{ 8, 3, 4, 1, 5, 9, 6, 7, 2 },
			{ 6, 1, 8, 7, 5, 3, 2, 9, 4 },
			{ 2, 7, 6, 9, 5, 1, 4, 3, 8 },
			{ 2, 9, 4, 7, 5, 3, 6, 1, 8 },
			{ 4, 3, 8, 9, 5, 1, 2, 7, 6 },
			{ 8, 1, 6, 3, 5, 7, 4, 9, 2 },
			{ 6, 7, 2, 1, 5, 9, 8, 3, 4 },
		}
	do
		if Trials.check("arrange", puzzle, grid) then
			found = true
		end
	end
	eq(found, true, "풀 수 있는 구궁")
	eq(Trials.check("balance", {}, true), true)
	eq(Trials.check("balance", {}, "yes"), false)
end)

print("진행")
local function fill(data)
	-- 이 단계의 과업을 모두 끝낸 것으로 친다 (choose 는 직접 고른다)
	for _, task in (Tasks.list(data)) do
		if task.kind == "choose" then
			if task.key == "root" then
				data.root = Roots.make({ "wood", "fire" })
			elseif task.key == "chilsu" then
				data.choice.chilsu = "cheong"
			elseif task.key == "element" then
				data.choice.element = data.root.elements[1]
			end
		elseif task.kind == "have" then
			data.items[task.item] = task.max
		else
			Tasks.set(data, task.id, task.max)
		end
	end
end
check("과업이 남으면 영력이 차도 오르지 않는다", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.step = YEONGI -- 연기기 1성
	local advanced = Progression.addQi(data, 1e12)
	eq(advanced, 0, "칠십이지살을 안 풀었으면 그대로")
	eq(data.qi, Progression.requiredQi(data), "필요량에서 멈춤")
	fill(data)
	advanced = Progression.tryAdvance(data)
	eq(advanced, 1, "과업을 마치면 오른다")
	eq(data.step, YEONGI + 1)
	eq(data.prog.step, YEONGI + 1, "새 단계는 진행을 비운다")
	eq(Tasks.allDone(data), false, "2성 과업이 새로 생긴다")
end)
check("과업 없는 단계는 영력만으로 오르고 병목에서 멈춘다", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = CHUKGI
	Progression.addQi(data, 1e15)
	eq(data.step, 44, "축기기 진수성에서 멈춤")
	eq(Progression.isCapped(data), true)
end)
check("범인부터 단수기까지", function()
	local data = Progression.newData()
	local tasks = Tasks.list(data)
	eq(#tasks, 3, "영기 느끼기, 영근, 영초")
	eq((Progression.choose(data, "root", { "wood" })), false, "영기를 느끼기 전에는 못 고른다")
	Tasks.set(data, "sense", 30)
	eq((Progression.choose(data, "root", { "wood", "fire", "fire" })), false)
	eq((Progression.choose(data, "root", { "wood", "fire" })), true)
	eq(data.root.kind, "jin")
	eq((Progression.choose(data, "root", { "wood" })), false, "다시 못 고른다")
	eq(data.log[1].e, "root", "수행 일지")

	data.qi = Progression.requiredQi(data)
	eq(Progression.attemptBreakthrough(data).kind, "blocked", "영초를 안 먹었다")
	Progression.addItem(data, "herb", 2)
	local eaten = Progression.eat(data, "herb")
	eq(eaten.ok, true, "영력이 가득 차도 먹을 수는 있다")
	eq(eaten.qi, 0, "넘치는 영력은 흩어진다")
	Progression.addItem(data, "herb", 1)
	data.qi = 0
	eaten = Progression.eat(data, "herb")
	eq(eaten.ok, true)
	assert((eaten.qi or 0) > 0, "영초 영력")
	Tasks.add(data, Tasks.find(data, "herb") :: any, 1)
	data.qi = Progression.requiredQi(data)
	eq(Progression.attemptBreakthrough(data).kind, "success")
	eq(data.step, 2, "단수기")
	eq(#Tasks.list(data), 3, "오행지의 음양지의 혼원지의")
	eq(Tasks.find(data, "ohaeng").max, 2, "진영근 두 속성 = 오행처 두 곳")
end)
check("선통후각은 천·진영근만", function()
	local data = Progression.newData()
	data.step = YEONGI
	data.root = Roots.make({ "wood", "fire", "earth", "metal" })
	eq((Progression.skipTask(data, "jisal")), false, "잡영근")
	data.root = Roots.make({ "wood" })
	local before = Progression.requiredQi(data)
	eq((Progression.skipTask(data, "jisal")), true)
	eq(Tasks.allDone(data), true)
	eq(Progression.requiredQi(data), before + math.floor(before * Tasks.SKIP_EXTRA), "2.5배")
	eq((Progression.skipTask(data, "jisal")), false, "이미 끝냄")
end)
check("연기기 3성에 오르면 취령진을 받는다", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.step = YEONGI + 1
	fill(data)
	data.qi = Progression.requiredQi(data)
	local advanced, notes = Progression.tryAdvance(data)
	eq(advanced, 1)
	eq(data.skills.chwiryeong, true)
	eq(#notes, 1)
end)
check("칠수와 본명 속성", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood", "water" })
	eq((Progression.choose(data, "chilsu", "cheong")), false, "7성 전에는 못 고른다")
	data.step = YEONGI + 6
	eq((Progression.choose(data, "chilsu", "moon")), false)
	eq((Progression.choose(data, "chilsu", "baek")), true)
	data.step = YEONGI + 8
	eq((Progression.choose(data, "element", "fire")), false, "영근에 없는 속성")
	eq((Progression.choose(data, "element", "water")), true)
	eq(Tasks.find(data, "ohaengjin").sites[1], "el_water")
end)
check("무극영운은 내관, 실패하면 영력 손실", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = 16
	data.qi = Progression.requiredQi(data)
	local result = Progression.attemptBreakthrough(data)
	eq(result.kind, "trial", "축단 없이도 시도할 수 있다 (선택 과업)")
	eq(result.mode, "strands")
	local lost = Progression.failTrial(data)
	assert(lost > 0)
	eq(data.step, 16, "실패해도 경지 유지")
	data.qi = Progression.requiredQi(data)
	Progression.passBreakthrough(data, false)
	eq(data.step, 17, "축기기 각수성")
	eq(data.qi, 0)
end)
check("결단기까지는 천겁이 없고 원영기 진입은 천겁", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = 44
	data.qi = Progression.requiredQi(data)
	eq(Progression.attemptBreakthrough(data).kind, "success", "결단기")
	data.step = 48
	data.qi = Progression.requiredQi(data)
	eq(Progression.attemptBreakthrough(data).kind, "tribulation", "원영기")
	eq(data.step, 48, "천겁 시작만으로는 오르지 않는다")
	local lost = Progression.failTribulation(data)
	assert(lost > 0, "천겁 실패 손실")
	eq(data.stats.tribulationFails, 1)
	data.qi = Progression.requiredQi(data)
	Progression.passBreakthrough(data, true)
	eq(data.step, 49, "원영기 여월지긍")
	eq(data.stats.tribulations, 1)
	-- 원영기 안에서도 단계마다 천겁
	data.qi = Progression.requiredQi(data)
	eq(Progression.isCapped(data), true)
	eq(Progression.attemptBreakthrough(data).kind, "tribulation", "여월지긍→여일지승")
end)
check("최고 경지", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = Realms.maxStep
	Progression.addQi(data, 1e30)
	eq(data.step, Realms.maxStep)
	eq(data.qi, Progression.requiredQi(data))
	eq(Progression.attemptBreakthrough(data).kind, "blocked")
end)
check("홍령삼", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood", "fire", "earth", "metal", "water" })
	data.step = 10
	Progression.addItem(data, "hongsam")
	eq(Progression.eat(data, "hongsam").ok, true)
	eq(data.root.kind, "hong")
	eq(Progression.itemCount(data, "hongsam"), 0)
	Progression.addItem(data, "hongsam")
	data.root = Roots.make({ "wood" })
	data.step = 45
	eq(Progression.eat(data, "hongsam").ok, false, "결단기부터는 안 바뀐다")
end)
check("축기단 재료", function()
	local data = Progression.newData()
	eq(Progression.canCraftPill(data), false)
	Progression.addItem(data, "herb", 6)
	Progression.addItem(data, "lingzhi", 1)
	eq(Progression.canCraftPill(data), true)
	eq(Progression.takeItems(data, Balance.PILL_RECIPE), true)
	eq(Progression.itemCount(data, "herb"), 0)
	eq(data.items.herb, nil, "다 쓰면 칸을 지운다")
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
check("술법 단축칸과 키", function()
	local data = Progression.newData()
	eq(#data.hotbar, Progression.HOTBAR_SIZE)
	eq(data.keys[1], "Q")
	eq(data.keys[2], "E")

	Progression.learn(data, "gyeongsin")
	eq(data.hotbar[1], "gyeongsin", "익힌 술법은 빈 칸에 들어간다")
	data.step = Realms.firstStepById.dansu
	Progression.learn(data, "yeongan")
	eq(data.hotbar[2], "yeongan")

	eq((Progression.assignSkill(data, 1, "yeongan")), true)
	eq(data.hotbar[1], "yeongan", "맞바꾼다")
	eq(data.hotbar[2], "gyeongsin")
	eq((Progression.assignSkill(data, 3, "hosin")), false, "안 익힌 술법")
	eq((Progression.assignSkill(data, 9, "yeongan")), false, "없는 칸")
	eq((Progression.assignSkill(data, 1.5, "yeongan")), false, "없는 칸")
	eq((Progression.assignSkill(data, 2, "")), true)
	eq(data.hotbar[2], "", "비우기")

	eq((Progression.bindKey(data, 1, "T")), true)
	eq(data.keys[1], "T")
	eq((Progression.bindKey(data, 1, "E")), true, "다른 칸이 쓰던 키면 맞바꾼다")
	eq(data.keys[1], "E")
	eq(data.keys[2], "T")
	eq((Progression.bindKey(data, 1, "W")), false, "이동 키는 막는다")
	eq((Progression.bindKey(data, 1, "One")), false, "숫자 키는 도구 칸")
end)
check("공법 효과", function()
	local data = Progression.newData()
	data.step = 45
	local baseRate = Progression.qiPerSecond(data, 1)
	local baseHp = Progression.maxHealth(data)
	local baseHerb = Progression.herbQi(data, "herb")
	for _, id in { "tonap", "geumgang", "baekcho", "piroe", "cheongi", "cheongsim" } do
		data.skills[id] = true
	end
	data.equipped = { "tonap", "geumgang", "baekcho" }
	assert(Progression.qiPerSecond(data, 1) > baseRate * 1.29, "토납법")
	assert(Progression.qiPerSecond(data, 1, 2) > Progression.qiPerSecond(data, 1) * 1.99, "취령진 배율")
	assert(Progression.maxHealth(data) > baseHp * 1.39, "금강체")
	assert(Progression.herbQi(data, "herb") > baseHerb * 1.59, "백초경")
	eq(Progression.tribulationDamage(data, 100), 100, "피뢰결 안 끼면 그대로")
	data.equipped = { "piroe", "cheongi", "cheongsim" }
	eq(Progression.tribulationDamage(data, 100), 70, "피뢰결")
	eq(Progression.telegraphTime(data, 1), 1.4, "천기감응")
	eq(Progression.trialBand(data), 1.2, "청심결 판정 폭")
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
		root = { kind = "jin", elements = { "fire", "wood" } },
		choice = { chilsu = "baek", element = "metal" },
		items = { herb = 3.7, bogus = 2, pill = -1 },
		prog = { step = 9999, t = { x = 1 } },
		qi = -5,
		enlightenment = 12.7, -- 예전 판의 깨달음은 버린다
		insights = { gongbeop = 3 },
		skills = { tonap = true, baekcho = true, unknown = true, cheongi = "x" },
		equipped = { "tonap", "tonap", "baekcho", "gyeongsin", "unknown", "cheongsim" },
		stats = { herbs = 4 },
	})
	eq(data.step, Realms.maxStep, "사축기 이상은 천인 대원만으로")
	eq(data.qi, 0)
	eq(data.root.kind, "jin")
	eq(data.root.elements[1], "wood")
	eq(data.choice.chilsu, "baek")
	eq(data.choice.element, nil, "영근에 없는 본명 속성은 버린다")
	eq(data.items.herb, 3)
	eq(data.items.bogus, nil)
	eq(data.items.pill, nil)
	eq(data.prog.step, Realms.maxStep)
	eq(data.prog.t.x, nil, "다른 단계의 진행은 버린다")
	eq((data :: any).enlightenment, nil)
	eq((data :: any).insights, nil)
	eq(data.skills.tonap, true)
	eq(data.skills.unknown, nil)
	eq(data.skills.cheongi, nil)
	eq(#data.equipped, 2, "익힌 공법만, 겹치지 않게")
	eq(data.equipped[1], "tonap")
	eq(data.equipped[2], "baekcho")

	-- 단축칸이 없던 예전 기록: 익힌 술법을 빈 칸에 채운다
	local old = Progression.reconcile({ step = 20, skills = { gyeongsin = true, yeongan = true } })
	eq(old.hotbar[1], "gyeongsin")
	eq(old.hotbar[2], "yeongan")
	eq(old.keys[1], "Q")
	-- 이상한 키·겹친 키·안 익힌 술법은 걸러 낸다
	local messy = Progression.reconcile({
		step = 20,
		skills = { gyeongsin = true },
		hotbar = { "hosin", "gyeongsin", "gyeongsin", 5 },
		keys = { "W", "E", "E", "Z" },
	})
	eq(messy.hotbar[1], "")
	eq(messy.hotbar[2], "gyeongsin")
	eq(messy.hotbar[3], "")
	eq(messy.keys[2], "E")
	eq(messy.keys[4], "Z")
	eq(messy.keys[1], "Q", "막힌 키 자리는 기본값으로")
	eq(messy.keys[3], "X", "이미 쓰는 기본값은 건너뛴다")
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
	-- 과업이 가리키는 자리는 모두 맵에 있어야 한다
	local siteIds: { [string]: boolean } = {}
	for _, inst in map:GetDescendants() do
		if inst:HasTag("Site") then
			local id = inst:GetAttribute("Site")
			assert(not siteIds[id], "자리 id 가 겹친다: " .. tostring(id))
			siteIds[id] = true
		end
	end
	eq(tags.Site, 34, "Site 태그")
	for step = 1, Realms.maxStep do
		for _, combo in { { "wood", "fire", "earth", "metal", "water" } } do
			for _, element in combo do
				local data = Progression.newData()
				data.step = step
				data.root = Roots.make(combo)
				data.choice = { chilsu = "cheong", element = element }
				for _, job in Tasks.list(data) do
					for _, site in job.sites or {} do
						assert(siteIds[site], `{Realms.label(step)} {job.label} 의 자리 {site} 가 맵에 없다`)
					end
				end
			end
		end
	end
	assert(siteIds.furnace, "연단로")
	for _, inst in map:GetDescendants() do
		if inst:HasTag("Vein") then
			assert(Balance.VEINS[inst:GetAttribute("VeinId")], "영맥 id")
			assert(type(inst:GetAttribute("Radius")) == "number", "영맥 반경")
		end
	end
	print(`  파트 {parts}개`)
end)

print(
	"\n진행 속도 (영맥 없이 / 각 경지에 맞는 최고 영맥, 진영근 둘, 과업 시간 빼고 영력만)"
)
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
	local data = Progression.newData()
	data.root = Roots.make({ "wood", "fire" })
	data.choice.chilsu = "cheong"
	data.choice.element = "wood"
	for step = 1, Realms.maxStep - 1 do
		data.step = step
		local req = Progression.requiredQi(data)
		plain += req / Progression.qiPerSecond(data, 1)
		veined += req / Progression.qiPerSecond(data, veinFor(step))
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
