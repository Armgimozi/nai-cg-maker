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
local Races = loader.require(shared.Races)
local Combat = loader.require(shared.Combat)
local Mobs = loader.require(shared.Mobs)
local Currency = loader.require(shared.Currency)

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
	eq(#Skills.actives, 7, "술법 7개 (경지에서 얻는 셋 포함)")
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

print("종족")
check("종족 뽑기", function()
	local total = 0
	for _, race in Races.list do
		total += race.weight
		assert(race.summary ~= "", race.id .. " 설명")
	end
	eq(total, 100, "몫을 모두 더하면 100")
	eq(Races.pick(0), Races.list[1].id, "가장 흔한 종족이 앞")
	eq(Races.pick(0.9999), Races.list[#Races.list].id, "가장 드문 종족이 끝")
	-- 다시 뽑기는 지금과 다른 종족
	for i = 0, 99 do
		assert(Races.pick(i / 100, "human") ~= "human", "다시 뽑으면 다른 종족")
	end
	-- 뽑힌 몫이 weight 와 맞다
	local counts = {}
	for i = 0, 9999 do
		local id = Races.pick((i + 0.5) / 10000)
		counts[id] = (counts[id] or 0) + 1
	end
	for _, race in Races.list do
		eq(counts[race.id], race.weight * 100, race.id .. " 몫")
	end
	assert(Races.effects("stone"):find("체력 %+20%%"), Races.effects("stone"))
	assert(Races.effects("stone"):find("천겁 피해 %-12%%"), Races.effects("stone"))
end)
check("종족 효과와 기록", function()
	local data = Progression.newData()
	data.step = 10
	data.root = Roots.make({ "wood" })
	local plain = Progression.qiPerSecond(data, 1)
	data.race = "moon"
	eq(Progression.qiPerSecond(data, 1), plain, "월영족 낮")
	assert(math.abs(Progression.qiPerSecond(data, 1, 1, true) - plain * 1.3) < 1e-6, "월영족 밤 +30%")
	data.race = "stone"
	assert(Progression.maxHealth(data) > (function()
		data.race = "human"
		return Progression.maxHealth(data)
	end)(), "석령족 체력")
	data.race = "dragon"
	local saved = Progression.reconcile({ step = 3, race = "dragon", receipts = { "a", "b" } })
	eq(saved.race, "dragon")
	eq(#saved.receipts, 2)
	eq(Progression.reconcile({ race = "elf" }).race, nil, "모르는 종족은 버린다")
	-- 같은 구매는 한 번만
	eq(Progression.claimReceipt(saved, "c"), true)
	eq(Progression.claimReceipt(saved, "c"), false)
	for i = 1, 80 do
		Progression.claimReceipt(saved, "p" .. i)
	end
	eq(#saved.receipts, Progression.RECEIPT_KEEP, "기록은 50개까지")
	local before = saved.race
	Progression.rollRace(saved, 0.5, true)
	assert(saved.race ~= before, "다시 뽑으면 바뀐다")
end)

print("싸움")
check("무기와 피해", function()
	eq(Combat.weaponName({ kind = "sword", grade = 1 }), "목검")
	eq(Combat.weaponName({ kind = "fan", grade = 1 }), "죽선")
	eq(Combat.weaponName({ kind = "spear", grade = 3 }), "청강창")
	assert(
		Combat.damage(20, { kind = "sword", grade = 1 }) > Combat.damage(10, { kind = "sword", grade = 1 }),
		"경지가 오르면 세진다"
	)
	assert(
		Combat.damage(10, { kind = "sword", grade = 3 }) > Combat.damage(10, { kind = "sword", grade = 1 }),
		"등급"
	)
	assert(
		Combat.damage(10, { kind = "sword", grade = 1 }, "ember") > Combat.damage(10, { kind = "sword", grade = 1 }),
		"염린족"
	)
	local sword = { kind = "sword", grade = 1 }
	-- 앞(-z)을 보고 선 사람 앞 6스터드 요수는 맞고, 뒤는 안 맞는다
	eq(Combat.inReach(0, 0, 0, -1, 0, -6, 2, sword), true)
	eq(Combat.inReach(0, 0, 0, -1, 0, 6, 2, sword), false, "뒤")
	eq(Combat.inReach(0, 0, 0, -1, 0, -30, 2, sword), false, "멀다")
	eq(Combat.inReach(0, 0, 0, -1, 0, 1, 2, sword), true, "붙어 있으면 방향 상관없이")
	local fan = { kind = "fan", grade = 1 }
	eq(Combat.inReach(0, 0, 0, -1, 1, -30, 2, fan), true, "부채는 멀리 앞 줄")
	eq(Combat.inReach(0, 0, 0, -1, 10, -30, 2, fan), false, "줄에서 비켜남")
	eq(Combat.isWeapon({ kind = "axe", grade = 1 }), false)
	eq(Combat.isWeapon({ kind = "sword", grade = 6 }), false)
end)
check("무기 얻기", function()
	local data = Progression.newData()
	eq(#data.weapons, 1, "처음엔 목검")
	eq(Progression.addWeapon(data, { kind = "sword", grade = 1 }), false, "같은 것")
	eq(Progression.addWeapon(data, { kind = "sword", grade = 2 }), true, "더 좋은 검은 바꾼다")
	eq(#data.weapons, 1)
	eq(data.weapons[1].grade, 2)
	eq(Progression.addWeapon(data, { kind = "spear", grade = 1 }), true)
	eq(#data.weapons, 2)
	local saved = Progression.reconcile({ weapons = { { kind = "fan", grade = 4 }, { kind = "x", grade = 1 } } })
	eq(#saved.weapons, 1)
	eq(saved.weapons[1].kind, "fan")
	eq(#Progression.reconcile({}).weapons, 1, "기록이 없으면 목검")
end)
check("요수", function()
	for _, mob in Mobs.list do
		assert(mob.tier >= 1 and mob.tier <= 5, mob.id .. " 위험도")
		assert(#mob.parts > 0, mob.id .. " 모양")
		assert(Mobs.LOOT[mob.tier], mob.id .. " 전리품")
	end
	for tier = 1, 5 do
		assert(Mobs.pick("nowhere", tier, 0.5), "위험도 " .. tier .. " 요수")
	end
	eq(Mobs.pick("desert", 3, 0.1).id, "sandstinger", "사막은 황사갈")
	eq(Mobs.pick("deungseon", 5, 0.9).id, "silverfox")
	-- 요수 피해는 그 위험도에 맞는 경지 체력으로 몇 번은 버틴다
	local recommended = { 6, 16, 30, 48, 54 }
	for _, mob in Mobs.list do
		local hp = Balance.maxHealth(recommended[mob.tier])
		assert(hp / mob.damage >= 3, `{mob.name} 이 너무 세다 ({hp} / {mob.damage})`)
		local hits = mob.hp / Combat.damage(recommended[mob.tier], { kind = "sword", grade = mob.tier })
		assert(hits >= 2 and hits <= 20, `{mob.name} 잡는 데 {hits} 번`)
	end
end)

print("영석")
check("영석 데이터", function()
	local ids = {}
	for _, ware in Currency.WARES do
		assert(not ids[ware.id], "상품 id 가 겹친다: " .. ware.id)
		ids[ware.id] = true
		eq(Currency.wareById[ware.id], ware, ware.id .. " 찾기")
		assert(ware.price > 0 and ware.price % 1 == 0, ware.id .. " 값")
		assert((ware.item ~= nil) ~= (ware.weapon ~= nil), ware.id .. " 은 물건이거나 무기 하나")
		if ware.item then
			assert(Balance.ITEMS[ware.item], ware.id .. " 물건")
			assert((ware.count or 1) >= 1, ware.id .. " 개수")
		else
			assert(Combat.isWeapon(ware.weapon), ware.id .. " 무기")
		end
	end
	eq(#Currency.UPGRADE, #Combat.GRADES - 1, "강화는 목~영 등급에서 한 등급씩")
	for grade = 2, #Currency.UPGRADE do
		assert(Currency.upgradeCost(grade) > Currency.upgradeCost(grade - 1), "높은 등급일수록 비싸다")
	end
	eq(Currency.upgradeCost(#Combat.GRADES), nil, "천 등급은 더 못 올린다")
	eq(#Currency.ORE, 5, "광맥은 위험도 1~5")
	for tier, ore in Currency.ORE do
		assert(ore.min >= 1 and ore.min <= ore.max and ore.hold > 0, "광맥 " .. tier)
	end
	eq(Currency.format(0), "0")
	eq(Currency.format(999), "999")
	eq(Currency.format(1250), "1,250")
	eq(Currency.format(1000000), "1,000,000")
	eq(Currency.format(12.7), "12")
end)
check("영석 지니기와 저장", function()
	local data = Progression.newData()
	eq(data.stones, Currency.START, "처음 영석")
	eq(Progression.reconcile({ step = 3, stones = 57.8 }).stones, 57, "정수로")
	eq(Progression.reconcile({ stones = -20 }).stones, 0, "음수는 0")
	eq(Progression.reconcile({ stones = 1e12 }).stones, Currency.MAX, "최대")
	eq(Progression.reconcile({ step = 10 }).stones, Currency.START, "예전 기록에는 처음 영석")
	eq(Progression.reconcile({ stones = "많이" }).stones, Currency.START)
	eq(Progression.reconcile({ stones = 0 / 0 }).stones, Currency.START, "NaN")
	eq(Progression.reconcile({ stones = math.huge }).stones, Currency.START, "무한")
	eq(Progression.reconcile({ stones = 0 }).stones, 0, "0 은 그대로")
	Progression.addStones(data, 15.9)
	eq(data.stones, Currency.START + 15)
	Progression.addStones(data, -1e9)
	eq(data.stones, 0, "0 아래로 내려가지 않는다")
	Progression.addStones(data, 1e12)
	eq(data.stones, Currency.MAX, "최대를 넘지 않는다")
	data.stones = 50
	eq(Progression.spendStones(data, 20), true)
	eq(data.stones, 30)
	eq(Progression.spendStones(data, 31), false, "모자라면 못 쓴다")
	eq(data.stones, 30, "못 쓰면 그대로")
	eq(Progression.spendStones(data, -5), false, "음수는 안 된다")
	eq(data.stones, 30)
	eq(Progression.spendStones(data, 0), true, "공짜")
	eq(Progression.spendStones(data, 30), true, "남김없이")
	eq(data.stones, 0)
end)
check("만물상에서 사기", function()
	local data = Progression.newData()
	data.stones = 200
	local herb = Currency.wareById.herb1
	local ok, message = Progression.buy(data, "herb1")
	eq(ok, true, message)
	eq(data.stones, 200 - herb.price)
	eq(data.items.herb, 1)
	eq(message, "영초 1개를 샀다.")
	ok, message = Progression.buy(data, "spear")
	eq(ok, true, message)
	eq(#data.weapons, 2, "무기를 지닌다")
	eq(data.weapons[2].kind, "spear")
	eq(data.weapons[2].grade, 1)
	eq(message, "목창을 샀다.")
	local left = data.stones
	eq(left, 200 - herb.price - Currency.wareById.spear.price)
	-- 이미 지닌 종류는 다시 팔지 않는다 (값도 받지 않는다)
	ok, message = Progression.buy(data, "spear")
	eq(ok, false)
	assert(message:find("대장간"), message)
	eq(data.stones, left, "이미 지닌 무기: 영석 그대로")
	eq(#data.weapons, 2)
	data.weapons[2].grade = 4
	eq((Progression.buy(data, "spear")), false, "등급이 높아도 같은 종류")
	-- 모자라면 사지 못한다
	data.stones = 10
	ok, message = Progression.buy(data, "lingzhi")
	eq(ok, false)
	assert(message:find("모자라"), message)
	assert(message:find(Currency.format(Currency.wareById.lingzhi.price), 1, true), message)
	eq(data.stones, 10, "모자라면 영석 그대로")
	eq(data.items.lingzhi, nil, "물건도 없다")
	eq((Progression.buy(data, "fan")), false, "무기도 모자라면")
	eq(#data.weapons, 2)
	eq(data.stones, 10)
	-- 무기 칸이 다 차면 사지 못한다
	data.stones = 1000
	data.weapons = {}
	for _ = 1, Combat.MAX_WEAPONS do
		table.insert(data.weapons, { kind = "sword", grade = 1 })
	end
	eq((Progression.buy(data, "fan")), false, "칸이 다 찼다")
	eq(data.stones, 1000)
	-- 없는 물건
	for _, bad in { "nope", "", 5, nil, {} } do
		eq((Progression.buy(data, bad)), false, "없는 물건 " .. tostring(bad))
	end
	eq(data.stones, 1000, "없는 물건: 영석 그대로")
	-- 묶음은 개수만큼
	ok = Progression.buy(data, "herb10")
	eq(ok, true)
	eq(data.items.herb, 1 + Currency.wareById.herb10.count)
end)
check("대장간에서 강화", function()
	local data = Progression.newData()
	data.stones = 1000
	local ok, message = Progression.upgradeWeapon(data, 1)
	eq(ok, true, message)
	eq(data.weapons[1].grade, 2)
	eq(data.stones, 1000 - Currency.upgradeCost(1))
	eq(message, "목검이 철검으로 거듭났다.")
	-- 모자라면 오르지 않는다
	data.stones = Currency.upgradeCost(2) - 1
	ok, message = Progression.upgradeWeapon(data, 1)
	eq(ok, false)
	assert(message:find("모자라"), message)
	eq(data.weapons[1].grade, 2, "모자라면 그대로")
	eq(data.stones, Currency.upgradeCost(2) - 1, "모자라면 영석 그대로")
	-- 가장 높은 등급
	data.stones = Currency.MAX
	data.weapons[1].grade = #Combat.GRADES
	ok, message = Progression.upgradeWeapon(data, 1)
	eq(ok, false, "천 등급은 끝")
	eq(data.weapons[1].grade, #Combat.GRADES)
	eq(data.stones, Currency.MAX, "못 올리면 영석 그대로")
	-- 없는 칸
	for _, bad in { 2, 0, -1, 1.5, "1", 0 / 0, nil } do
		eq((Progression.upgradeWeapon(data, bad)), false, "없는 칸 " .. tostring(bad))
	end
	eq(data.stones, Currency.MAX)
	-- 목검에서 천검까지 모두 올리는 값
	local total = 0
	for grade = 1, #Currency.UPGRADE do
		total += Currency.upgradeCost(grade)
	end
	data.weapons[1].grade = 1
	data.stones = total
	for _ = 1, #Currency.UPGRADE do
		eq((Progression.upgradeWeapon(data, 1)), true)
	end
	eq(data.weapons[1].grade, #Combat.GRADES)
	eq(data.stones, 0)
end)
check("전송진 삯과 로벅스 묶음", function()
	eq(Currency.travelFee(5000, true), 0, "집(연국)으로 가는 길은 공짜")
	eq(Currency.travelFee(0, true), 0)
	eq(Currency.travelFee(0, false), Currency.TRAVEL_MIN, "가까워도 최소 삯")
	eq(Currency.travelFee(1e6, false), Currency.TRAVEL_MAX, "멀어도 최대 삯")
	eq(Currency.travelFee(Currency.TRAVEL_PER * 10, false), 10)
	eq(Currency.travelFee(Currency.TRAVEL_PER * 10.4, false), 10, "반올림")
	eq(Currency.travelFee(Currency.TRAVEL_PER * 10.6, false), 11)
	eq(Currency.packByProduct(0), nil, "id 0 은 준비 중")
	eq(Currency.packByProduct(-1), nil)
	local seen = {}
	for _, pack in Currency.PACKS do
		assert(pack.stones > 0 and pack.robux > 0, pack.key)
		assert(not seen[pack.key], "묶음 key 가 겹친다")
		seen[pack.key] = true
		if pack.productId > 0 then
			eq(Currency.packByProduct(pack.productId), pack, pack.key)
			assert(pack.productId ~= Races.REROLL_PRODUCT_ID, "종족 다시 뽑기와 같은 상품 id")
		end
	end
	if Races.REROLL_PRODUCT_ID ~= 0 then
		eq(Currency.packByProduct(Races.REROLL_PRODUCT_ID), nil, "다시 뽑기는 영석 묶음이 아니다")
	end
end)

print("영근과 시계")
check("영근 고르기", function()
	-- 영근은 한 속성만
	eq(Roots.make({ "wood" }).kind, "cheon")
	eq(Roots.make("fire").elements[1], "fire", "문자열도 받는다")
	eq(Roots.make({ "fire", "wood" }), nil, "둘 이상은 거절")
	eq(Roots.make({}), nil)
	eq(Roots.make({ "light" }), nil)
	eq(Roots.strands(Roots.make({ "wood" })), Roots.STRANDS)
	eq(Roots.hong("water").elements[1], "water", "홍령수지체도 속성은 그대로")
	assert(Roots.gain(Roots.hong("water")) > Roots.gain(Roots.make({ "water" })))
	eq(Roots.describe(Roots.make({ "water" })), "천영근 (수)")
	-- 예전 판 여러 속성 영근: 본명 속성 또는 첫 속성 하나만 남는다
	eq(Roots.reconcile({ kind = "jin", elements = { "fire", "wood" } }).elements[1], "fire")
	eq(Roots.reconcile({ kind = "jin", elements = { "fire", "wood" } }, "wood").elements[1], "wood")
	eq(#Roots.reconcile({ kind = "jap", elements = { "wood", "fire", "earth", "metal" } }).elements, 1)
	eq(Roots.reconcile({ kind = "hong", elements = { "wood", "earth" } }, "earth").kind, "hong")
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
				data.root = Roots.make({ "wood" })
			elseif task.key == "chilsu" then
				data.choice.chilsu = "cheong"
			elseif task.key == "element" then
				data.choice.element = data.root.elements[1]
			elseif task.key == "center" then
				data.choice.center = "wood"
			elseif task.key == "dosim" then
				data.choice.dosim = "sitting"
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
check("축기기는 별마다 과업을 채우며 진수성까지 오르고 병목에서 멈춘다", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = CHUKGI
	for _ = 1, 40 do
		fill(data)
		Progression.addQi(data, 1e15)
	end
	eq(data.step, 44, "축기기 진수성에서 멈춤")
	fill(data)
	eq(Progression.isCapped(data), true)
	eq(Progression.attemptBreakthrough(data).kind, "trial", "금단 응결")
end)
check("제사한 칠수의 수에서는 별씨가 덜 든다", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = CHUKGI + 1 -- 1수 두 번째 별
	eq(Tasks.find(data, "condense").cost, nil, "청존칠수는 1수 짝수 별에 별씨가 안 든다")
	local favored = Progression.requiredQi(data)
	data.choice.chilsu = "yang"
	assert(Tasks.find(data, "condense").cost.starSeed == 1)
	assert(Progression.requiredQi(data) > favored, "제사한 수는 영력도 덜 든다")
	data.step = CHUKGI + 6
	eq(Tasks.find(data, "seat").sites[1], "star_east", "1수 마지막 별은 동쪽 성대")
	eq(Tasks.find(data, "constellation").params.labels[1], "각")
end)
check("범인부터 단수기까지", function()
	local data = Progression.newData()
	local tasks = Tasks.list(data)
	eq(#tasks, 3, "영기 느끼기, 영근, 영초")
	eq((Progression.choose(data, "root", { "wood" })), false, "영기를 느끼기 전에는 못 고른다")
	Tasks.set(data, "sense", 30)
	eq((Progression.choose(data, "root", { "wood", "fire" })), false, "속성은 하나만")
	eq((Progression.choose(data, "root", { "wood" })), true)
	eq(data.root.kind, "cheon")
	eq(data.choice.element, "wood", "영근 속성이 곧 본명 속성")
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
	eq(Tasks.find(data, "ohaeng").max, 1, "영근 속성 하나 = 오행처 한 곳")
end)
check("선통후각은 영근이 깨어난 뒤에", function()
	local data = Progression.newData()
	data.step = YEONGI
	data.root = nil
	eq((Progression.skipTask(data, "jisal")), false, "영근이 없다")
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
	data.root = Roots.make({ "water" })
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
	data.choice.element = "wood"
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
	fill(data)
	data.qi = Progression.requiredQi(data)
	eq(Progression.attemptBreakthrough(data).kind, "trial", "결단기는 금단 응결")
	for step = 17, 44 do
		data.step = step
		eq(Realms.tribulationAfter(step), nil, "축기기 천겁 없음")
	end
	data.step = 48
	fill(data)
	data.qi = Progression.requiredQi(data)
	local toWonyeong = Progression.attemptBreakthrough(data)
	eq(toWonyeong.kind, "trial", "원영기는 주마등부터")
	eq(toWonyeong.mode, "order")
	eq(Progression.nextEntry(data).after, "tribulation", "주마등 뒤에 천겁")
	assert(Realms.tribulationAfter(48), "결단 대원만 다음 천겁")
	eq(data.step, 48, "천겁 시작만으로는 오르지 않는다")
	local lost = Progression.failTribulation(data)
	assert(lost > 0, "천겁 실패 손실")
	eq(data.stats.tribulationFails, 1)
	data.qi = Progression.requiredQi(data)
	Progression.passBreakthrough(data, true)
	eq(data.step, 49, "원영기 여월지긍")
	eq(data.stats.tribulations, 1)
	-- 원영기 안에서도 단계마다 천겁
	fill(data)
	data.qi = Progression.requiredQi(data)
	eq(Progression.isCapped(data), true)
	eq(Progression.attemptBreakthrough(data).kind, "tribulation", "여월지긍→여일지승")
end)
check("원영기 술법과 천인기 도심", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	data.choice.chilsu = "cheong"
	data.step = Realms.firstStepById.wonyeong - 1
	fill(data)
	data.qi = Progression.requiredQi(data)
	Progression.passBreakthrough(data, true)
	eq(data.skills.heogong, true, "원영기에 들면 허공이동")
	eq(Tasks.find(data, "moon").when, "night")
	data.step = Realms.firstStepById.wonyeong + 2
	eq(Tasks.find(data, "missing").max, 4, "천영근은 없는 속성 넷")
	eq((Progression.choose(data, "dosim", "herb")), false, "도심은 불건불붕에서")
	data.step += 1
	eq((Progression.choose(data, "dosim", "herb")), true)
	data.step = Realms.firstStepById.cheonin
	local job = Tasks.find(data, "madness")
	eq(job.event, "herb", "채약 도심은 영초를 캘 때")
	eq(job.label, "광기 (채약)")
	local base = Progression.telegraphTime(data, 1)
	data.step += 2
	eq(Progression.telegraphTime(data, 1), base + Skills.EFFECT.foresight, "지천명 예지")
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
	data.root = Roots.make({ "metal" })
	data.step = 10
	Progression.addItem(data, "hongsam")
	eq(Progression.eat(data, "hongsam").ok, true)
	eq(data.root.kind, "hong")
	eq(data.root.elements[1], "metal", "속성은 그대로")
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
	eq(Progression.pureForce(data), 4, "결단기는 네 수를 모두 완성했다")
	eq(Progression.tribulationDamage(data, 100), 80, "정순지력 -20%")
	data.equipped = { "piroe", "cheongi", "cheongsim" }
	eq(math.round(Progression.tribulationDamage(data, 100)), 56, "피뢰결 -30%, 정순지력 -20%")
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
	eq(data.root.kind, "cheon", "예전 진영근은 천영근 하나로")
	eq(data.root.elements[1], "fire")
	eq(#data.root.elements, 1)
	eq(data.choice.chilsu, "baek")
	eq(data.choice.element, "fire", "본명 속성은 영근 속성")
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

print("검수 명령")
check("채팅 명령 읽기", function()
	local Commands = loader.require(shared.Commands)
	eq(Commands.parse("안녕"), nil)
	eq(Commands.parse("/없는명령"), nil)
	eq(Commands.parse("/경지 연기기 7").step, YEONGI + 6)
	eq(Commands.parse("/경지 천인기").step, Realms.firstStepById.cheonin)
	eq(Commands.parse("/realm chukgi 28").step, 44, "영어 이름과 경지 id")
	eq(Commands.parse("/경지 연기기 99").step, 16, "단계는 그 경지 안으로")
	assert(Commands.parse("/경지 사축기").error, "없는 경지")
	eq(Commands.parse("/단계 23").step, 23)
	assert(Commands.parse("/단계 57").error, "범위 밖")
	assert(Commands.parse("/단계 2.5").error, "소수")
	local item = Commands.parse("/주머니 별씨 5")
	eq(item.item, "starSeed")
	eq(item.count, 5)
	eq(Commands.parse("/주머니 영초").count, 1)
	eq(Commands.parse("/시간 밤").phase, "night")
	eq(Commands.parse("/초기화").confirmed, false)
	eq(Commands.parse("/초기화 확인").confirmed, true)
	eq(Commands.parse("/영력").command, "영력")
	eq(Commands.parse("/REALM Yeongi 3").step, YEONGI + 2, "대소문자를 가리지 않는다")
	eq(Commands.parse("/Item StarSeed 2").item, "starSeed")
	eq(Commands.parse("/TIME Night").phase, "night")
	assert(Commands.parse("/경지 연기기 nan").error, "NaN 단계")
	assert(
		string.find(Commands.parse("/경지 연기기 0").error, "단계 번호", 1, true),
		"단계 번호 오류는 따로"
	)
	assert(string.find(Commands.parse("/경지 없는경지").error, "경지 이름", 1, true))
	eq(Commands.parse("/검수").command, "검수")
	assert(Commands.parse("/단계 nan").error, "NaN")
	assert(Commands.parse("/주머니 영초 nan").error, "NaN 개수")
	eq(Commands.parse("/복구 확인").confirmed, true)
end)
check("검수용 단계 옮기기", function()
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
	Tasks.set(data, "sense", 30)
	data.qi = 10
	local notes = Progression.jumpTo(data, Realms.firstStepById.cheonin + 1)
	eq(data.step, Realms.firstStepById.cheonin + 1)
	eq(data.qi, 0)
	eq(data.prog.step, data.step, "진행을 비운다")
	eq(data.skills.heogong, true, "건너뛴 경지의 술법을 준다")
	eq(data.skills.yudo, true)
	eq(data.skills.yeongchul, true)
	eq(data.skills.chwiryeong, true, "취령진도")
	assert(#notes >= 3, "얻은 술법을 알린다")
	-- 내려가면 그 경지에 맞게
	data.skills.tonap, data.skills.baekcho, data.skills.geumgang = true, true, true
	data.equipped = { "tonap", "baekcho", "geumgang" }
	Progression.jumpTo(data, YEONGI)
	eq(#data.equipped, 2, "연기기는 공법 2칸")
	eq(data.skills.heogong, nil, "원영기 술법은 거둔다")
	eq(table.find(data.hotbar, "heogong"), nil, "단축칸에서도 뺀다")
	eq(data.skills.gyeongsin, nil, "비급 술법은 원래 없었다")
	-- 경지 술법은 얻는 단계 기준으로 거둔다 (원영 출규는 천인기 2단계부터)
	Progression.jumpTo(data, Realms.firstStepById.cheonin + 2)
	eq(data.skills.yeongchul, true)
	Progression.jumpTo(data, Realms.firstStepById.cheonin)
	eq(data.skills.yeongchul, nil, "천인기 1단계로 내려가면 원영 출규를 거둔다")
	eq(data.skills.yudo, true, "천기유도는 남는다")
	Progression.jumpTo(data, YEONGI)
	Progression.jumpTo(data, 0 / 0)
	eq(data.step, YEONGI, "NaN 은 무시한다")
	Progression.jumpTo(data, 1)
	eq(data.step, 1)
end)
check("건너뛴 고르기는 뒤 단계에서 먼저 고른다", function()
	local data = Progression.newData()
	data.root = Roots.make({ "fire" })
	data.choice.chilsu = "cheong"
	data.step = Realms.firstStepById.cheonin
	local ids = {}
	for _, job in Tasks.list(data) do
		ids[job.id] = job.kind
	end
	local order = {}
	for _, job in Tasks.list(data) do
		table.insert(order, job.id)
	end
	eq(table.concat(order, " ", 1, 3), "bonmyeong center dosim", "게임 순서대로 앞에")
	eq(Tasks.isOpen(data, Tasks.find(data, "madness")), false, "도심을 고르기 전에는 광기가 안 찬다")
	eq(ids.bonmyeong, "choose", "본명 속성")
	eq(ids.center, "choose", "오악 중심")
	eq(ids.dosim, "choose", "도심")
	eq(Tasks.allDone(data), false)
	eq((Progression.choose(data, "element", "fire")), true)
	eq((Progression.choose(data, "center", "water")), true)
	eq((Progression.choose(data, "dosim", "herb")), true)
	ids = {}
	for _, job in Tasks.list(data) do
		ids[job.id] = true
	end
	eq(ids.bonmyeong, nil)
	eq(ids.dosim, nil)
end)

print("플레이스 설정")
check("새 채팅(TextChatService)을 켜 둔다", function()
	-- 플레이스 파일에 TextChatService 가 없으면 ChatVersion 이 예전 채팅으로 저장된다 (알림이 안 뜨던 원인)
	local fs = require("@lune/fs")
	local serde = require("@lune/serde")
	local project = serde.decode("json", fs.readFile("default.project.json"))
	local service = project.tree.TextChatService
	assert(service, "default.project.json 에 TextChatService 가 없다")
	eq(service["$properties"].ChatVersion, "TextChatService")
	eq(service["$properties"].CreateDefaultTextChannels, true)
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
	Harness.mount(game)
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
	eq(tags.Ground, 5, "Ground 태그 (광장, 다리, 너럭바위, 서악 마당, 갯바위)")
	eq(tags.Vein, 8, "Vein 태그")
	eq(tags.HerbZone, 2, "HerbZone 태그 (영초숲, 등선향)")
	eq(tags.ManualSpot, 27, "ManualSpot 태그")
	eq(tags.Waypoint, 13, "Waypoint 태그")
	-- 맵 위의 것은 땅(지형) 높이에 맞게 놓였다: 묻히지도 뜨지도 않는다, 물속도 아니다
	local Land = worldLoader.require(worldLoader.folder("src/shared").Land)
	for _, inst in map:GetDescendants() do
		local kind = if inst:HasTag("Site")
			then "자리 " .. tostring(inst:GetAttribute("Site"))
			elseif inst:HasTag("Waypoint") then "전송진 " .. tostring(inst:GetAttribute("Name"))
			elseif inst:HasTag("ManualSpot") then "비급 자리"
			elseif inst:HasTag("Vein") then "영맥 " .. tostring(inst:GetAttribute("VeinId"))
			else nil
		if kind then
			local p = inst.CFrame.Position
			-- 섬 밑(폐허)에 놓인 것은 섬 윗면이 아니라 땅을 본다: 둘 가운데 가까운 쪽
			local ground = Land.surface(p.X, p.Z)
			local low = Land.height(p.X, p.Z)
			if math.abs(p.Y - low) < math.abs(p.Y - ground) then
				ground = low
			end
			local water = Land.water(p.X, p.Z, Land.height(p.X, p.Z))
			-- 수 오행처 갯바위, 용소 너럭바위, 나룻배 노인처럼 땅보다 높은 판 위에 놓인 것은 판 높이를 본다
			assert(p.Y > ground - 2.5, `{kind} 이 땅에 묻혔다 ({p}, 땅 {ground})`)
			assert(p.Y < ground + 9, `{kind} 이 떠 있다 ({p}, 땅 {ground})`)
			assert(water == nil or p.Y > water, `{kind} 이 물속이다 ({p}, 수면 {water})`)
		end
	end
	-- 등선향 밑 폐허의 토 오행처와 전송진은 섬 위가 아니라 땅에 있다
	for _, inst in map:GetDescendants() do
		local underIsland = inst:GetAttribute("Site") == "el_earth" or inst:GetAttribute("WaypointId") == "wp_ruins"
		if underIsland then
			local p = inst.CFrame.Position
			assert(
				math.abs(p.Y - Land.height(p.X, p.Z)) < 4,
				`{inst.Name} 이 땅이 아니라 섬 위에 있다 ({p})`
			)
		end
	end
	-- 전송진마다 그 이름의 땅에 있다
	local PlacesForPads = worldLoader.require(worldLoader.folder("src/shared").Places)
	local expectRegion = {
		wp_yeonguk = "yeonguk",
		wp_seoak = "seoak",
		wp_summit = "summit",
		wp_cheonsaek = "cheonsaek",
		wp_dapcheon = "dapcheondae",
		wp_ruins = "ruins",
		wp_deungseon = "deungseon",
		wp_star_south = "southisle",
	}
	for _, inst in map:GetDescendants() do
		local id = inst:GetAttribute("WaypointId")
		if id and expectRegion[id] then
			local p = inst.CFrame.Position
			eq(PlacesForPads.regionAt(p.X, p.Z, p.Y + 3).id, expectRegion[id], id .. " 의 땅")
		end
	end
	-- 땅 이름: 자리마다 이름이 나온다
	local Places = worldLoader.require(worldLoader.folder("src/shared").Places)
	eq(Places.regionAt(0, 0, 1).id, "yeonguk", "광장은 연국")
	eq(Places.regionAt(860, -40, 316).id, "deungseon", "섬 위는 등선향")
	eq(Places.regionAt(860, -40, 19).id, "ruins", "섬 아래는 폐허")
	eq(Places.regionAt(-860, -220, 440).id, "summit", "쇄천봉 꼭대기")
	eq(Places.regionAt(900, 300, 30).id, "desert", "답천사막")
	-- 과업이 가리키는 자리는 모두 맵에 있어야 한다
	local siteIds: { [string]: boolean } = {}
	for _, inst in map:GetDescendants() do
		if inst:HasTag("Site") then
			local id = inst:GetAttribute("Site")
			assert(not siteIds[id], "자리 id 가 겹친다: " .. tostring(id))
			siteIds[id] = true
		end
	end
	eq(tags.Site, 37, "Site 태그")
	for step = 1, Realms.maxStep do
		for _, combo in { { "wood", "fire", "earth", "metal", "water" } } do
			for _, element in combo do
				local data = Progression.newData()
				data.step = step
				data.root = Roots.make({ element })
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

	-- 마을 사람: 노인은 자리(Seat)와 과업 자리가 있고, 모두 생김새가 있다
	local Npcs = worldLoader.require(worldLoader.folder("src/shared").Npcs)
	local seats = {}
	for _, inst in map:GetDescendants() do
		if inst:IsA("Seat") and inst:GetAttribute("NpcSeat") then
			seats[inst:GetAttribute("NpcSeat")] = inst
		end
	end
	local SLOTS =
		{ Hat = true, Hair = true, Face = true, Back = true, Waist = true, Neck = true, Front = true, Shoulders = true }
	for _, npc in Npcs.list do
		local look = Npcs.look(npc.id)
		assert(look, npc.name .. " 생김새")
		assert(#npc.lines >= 3, npc.name .. " 대사")
		for slot, ids in look.rigid or {} do
			assert(SLOTS[slot], `{npc.name}: 모르는 장신구 칸 {slot}`)
			for _, id in ids do
				assert(type(id) == "number" and id > 0, npc.name .. " 아이템 id")
			end
		end
		for _, item in look.layered or {} do
			assert(roblox.Enum.AccessoryType[item.type], `{npc.name}: 모르는 레이어드 종류 {item.type}`)
		end
		if npc.seated then
			local seat = seats[npc.id]
			assert(seat, npc.name .. " 앉을 자리")
			local offset = seat.CFrame.Position - npc.position
			assert(
				roblox.Vector3.new(offset.X, 0, offset.Z).Magnitude < 1.5,
				`{npc.name} 의 자리(Npcs.position)가 맵의 걸상과 다르다`
			)
			-- 노인은 과업 자리(말 걸기 버튼)와 천순 부탁이 있다. 만물상 주인은 상점 버튼이 대신한다
			if npc.site then
				assert(siteIds[npc.site], npc.name .. " 과업 자리")
				assert(npc.request and npc.thanks, npc.name .. " 부탁과 인사")
			end
		else
			assert(npc.route and #npc.route >= 2, npc.name .. " 동선")
		end
	end
	-- 천순 과업이 가리키는 노인은 모두 있다
	for _, id in { "elder_1", "elder_2", "elder_3" } do
		assert(Npcs.byId[id], id)
	end
	-- 공중에 뜨는 이름표는 없고, 현판 글자는 모두 붓글씨 글자판에 있다
	local Art = worldLoader.require(worldLoader.folder("src/client").Art)
	local plaques = 0
	for _, inst in map:GetDescendants() do
		assert(not inst:IsA("BillboardGui"), "맵에 공중 이름표가 있다: " .. inst:GetFullName())
		if inst:HasTag("Plaque") then
			plaques += 1
			local text = inst:GetAttribute("Text")
			assert(type(text) == "string" and text ~= "", "현판에 글이 없다")
			for _, code in utf8.codes(text) do
				local ch = utf8.char(code)
				assert(ch == " " or Art.fonts.title.glyphs[ch], `현판 글자 {ch} 가 글자판에 없다 ({text})`)
			end
		end
	end
	assert(plaques >= 30, `현판 {plaques}개`)
	-- 판은 정해진 쪽을 본다 (Lune 의 CFrame.lookAt 은 Z 가 뒤집혀 나와서 World 는 face() 를 쓴다)
	local gates = 0
	for _, gate in map:FindFirstChild("마을"):GetChildren() do
		if gate.Name == "연국 문" then
			gates += 1
			local board = gate:FindFirstChild("Board")
			local p = board.CFrame.Position
			local inward = roblox.Vector3.new(-p.X, 0, -p.Z).Unit
			assert(board.CFrame.LookVector:Dot(inward) > 0.99, "연국 문 현판은 마을 쪽을 본다")
		end
	end
	eq(gates, 3, "연국 패루")
	for _, inst in map:GetDescendants() do
		if inst.Name == "Tag" and inst:HasTag("Plaque") then
			local lantern = inst.Parent:FindFirstChild("Lamp", true)
			local away = inst.CFrame.Position - lantern.CFrame.Position
			assert(
				inst.CFrame.LookVector:Dot(roblox.Vector3.new(away.X, 0, away.Z).Unit) > 0.9,
				"율점 패는 기둥 바깥(가운데)을 본다"
			)
		end
	end
	for _, inst in map:GetDescendants() do
		if inst:HasTag("Vein") then
			assert(Balance.VEINS[inst:GetAttribute("VeinId")], "영맥 id")
			assert(type(inst:GetAttribute("Radius")) == "number", "영맥 반경")
		end
	end
	-- 상점 자리: 만물상 판대와 대장간 모루. F 버튼은 창만 열고, 서버가 곁(수평 16)에 섰는지 다시 본다
	eq(tags.MarketSpot, 2, "MarketSpot 태그 (만물상, 대장간)")
	local shops: { [string]: any } = {}
	for _, inst in map:GetDescendants() do
		if inst:HasTag("MarketSpot") then
			local kind = inst:GetAttribute("Shop")
			assert(kind == "market" or kind == "smith", "상점 종류 " .. tostring(kind))
			assert(not shops[kind], "상점 자리가 겹친다: " .. kind)
			shops[kind] = inst
			assert(inst:IsA("BasePart"), "상점 자리는 판")
			eq(inst.CanCollide, false, "상점 자리는 부딪히지 않는다")
			local prompt = inst:FindFirstChildOfClass("ProximityPrompt")
			assert(prompt, kind .. " F 버튼")
			eq(prompt:GetAttribute("Shop"), kind, "버튼 Shop 속성")
			eq(prompt.ActionText, if kind == "market" then "상점" else "대장간")
			eq(prompt.KeyboardKeyCode, roblox.Enum.KeyCode.F)
			assert(math.abs(prompt.HoldDuration - 0.2) < 1e-3, "누르는 시간")
			eq(prompt.RequiresLineOfSight, false)
			eq(prompt.MaxActivationDistance, 10)
			local p = inst.CFrame.Position
			eq(Places.tierAt(p.X, p.Z, p.Y), 0, kind .. " 는 안전한 땅")
			eq(Places.regionAt(p.X, p.Z, p.Y).id, "yeonguk", kind .. " 는 연국")
		end
	end
	-- 만물상 주인은 판대 바로 뒤, 대장간 자리는 늙은 대장장이 말 걸기 버튼과 떨어져 있다
	local flat = function(a, b)
		local d = a - b
		return roblox.Vector3.new(d.X, 0, d.Z).Magnitude
	end
	assert(flat(shops.market.CFrame.Position, seats.merchant.CFrame.Position) < 6, "주인은 판대 곁")
	local elderSite
	for _, inst in map:GetDescendants() do
		if inst:GetAttribute("Site") == "elder_2" then
			elderSite = inst
		end
	end
	assert(
		flat(shops.smith.CFrame.Position, elderSite.CFrame.Position) > 12,
		"모루 버튼과 노인 버튼이 겹친다"
	)
	-- 현판은 광장(만물상)과 서쪽 길(대장간)을 본다
	for _, inst in map:GetDescendants() do
		local text = inst:GetAttribute("Text")
		if text == "만물상" then
			local p = inst.CFrame.Position
			assert(
				inst.CFrame.LookVector:Dot(roblox.Vector3.new(-p.X, 0, -p.Z).Unit) > 0.99,
				"만물상 현판은 광장 쪽"
			)
		elseif text == "대장간" then
			assert(inst.CFrame.LookVector.X < -0.99, "대장간 현판은 서쪽(광장 쪽)")
		end
	end
	print(`  파트 {parts}개`)
end)

print("\n진행 속도 (영맥 없이 / 상품 영맥, 천영근, 과업 시간 빼고 영력만)")
do
	local veinFor = function(_step: number): number
		local best = 1
		for _, vein in Balance.VEINS do
			best = math.max(best, vein.mult)
		end
		return best
	end
	local plain, veined = 0, 0
	local data = Progression.newData()
	data.root = Roots.make({ "wood" })
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
