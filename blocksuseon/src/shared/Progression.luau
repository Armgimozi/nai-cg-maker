-- 플레이어 저장 데이터를 다루는 순수 로직.
-- 인스턴스나 서비스에 손대지 않으므로 서버 밖(테스트)에서도 그대로 돌릴 수 있다.

local Realms = require(script.Parent.Realms)
local Balance = require(script.Parent.Balance)
local Skills = require(script.Parent.Skills)
local Josa = require(script.Parent.Josa)
local Roots = require(script.Parent.Roots)
local Races = require(script.Parent.Races)
local Combat = require(script.Parent.Combat)
local Currency = require(script.Parent.Currency)
local Guards = require(script.Parent.Guards)
local Tasks = require(script.Parent.Tasks)

export type Data = {
	version: number,
	step: number,
	qi: number,
	root: Roots.Root?, -- 영근
	prog: Tasks.Progress, -- 지금 단계의 과업 진행
	choice: { [string]: string }, -- 칠수(chilsu), 본명 속성(element)
	items: { [string]: number }, -- 주머니
	log: { { e: string, s: number } }, -- 수행 일지 (원영기 주마등에 쓴다)
	skills: { [string]: boolean }, -- 익힌 술법·공법
	equipped: { string }, -- 장착한 공법
	hotbar: { string }, -- 술법 단축칸마다 넣은 술법 ("" 은 빈 칸)
	keys: { string }, -- 단축칸마다 쓰는 키 이름 (KeyCode.Name)
	stats: { [string]: number },
	waypoints: { [string]: boolean }, -- 밟아 본 전송진
	race: string?, -- 종족 (Races.luau). 처음 들어올 때 서버가 뽑는다
	weapons: { Combat.Weapon }, -- 지닌 공격 법구 (숫자 키 1~9 도구 칸)
	guards: { Guards.Guard }, -- 지닌 방어 법구 (종류마다 하나)
	guard: string?, -- 지금 지닌(장착한) 방어 법구 종류. 하나만
	receipts: { string }, -- 처리한 로벅스 구매 (같은 구매를 두 번 주지 않으려고)
	stones: number, -- 영석 (Currency.luau)
}

export type BreakResult = {
	kind: "blocked" | "success" | "trial" | "tribulation",
	reason: string?,
	mode: string?,
}

local EFFECT = Skills.EFFECT

local Progression = {}

Progression.DATA_VERSION = 7
Progression.LOG_SIZE = 40
Progression.RECEIPT_KEEP = 50
-- 옛 세계 전송진 id → 옥반 전송진 id
Progression.OLD_WAYPOINTS = {
	wp_yeonguk = "wp_home",
	wp_yeonsan = "wp_grove",
	wp_seoak = "wp_ungok",
	wp_star_west = "wp_west",
	wp_star_north = "wp_north",
	wp_cheonsaek = "wp_city",
	wp_dapcheon = "wp_mesa",
	wp_star_east = "wp_east",
	wp_coast = "wp_port",
	wp_star_south = "wp_south",
	wp_deungseon = "wp_sky",
} :: { [string]: string }

-- 술법 단축칸. 숫자 키는 장비·도구 칸으로 남겨 두고, 손이 쉽게 가는 글자 키를 쓴다.
Progression.HOTBAR_SIZE = 4
Progression.DEFAULT_KEYS = { "Q", "E", "Z", "X" }
-- 단축키로 쓸 수 있는 키 (이동 WASD, 운기 R, 돌파 B, 상태창 C, 채집 F 등은 뺀다)
Progression.BINDABLE_KEYS = {
	"Q",
	"E",
	"T",
	"Y",
	"U",
	"G",
	"H",
	"J",
	"K",
	"L",
	"Z",
	"X",
	"V",
	"N",
	"P",
}
local BINDABLE: { [string]: boolean } = {}
for _, key in Progression.BINDABLE_KEYS do
	BINDABLE[key] = true
end

function Progression.isBindable(key: any): boolean
	return type(key) == "string" and BINDABLE[key] == true
end

function Progression.newData(): Data
	return {
		version = Progression.DATA_VERSION,
		step = 1,
		qi = 0,
		root = nil,
		prog = { step = 1, t = {}, debt = 0 },
		choice = {},
		items = {},
		log = {},
		skills = {},
		equipped = {},
		hotbar = table.create(Progression.HOTBAR_SIZE, ""),
		keys = table.clone(Progression.DEFAULT_KEYS),
		waypoints = {},
		race = nil,
		receipts = {},
		weapons = { { kind = "sword", grade = 1 } },
		stones = Currency.START,
		guards = {},
		guard = nil,
		stats = {
			breakthroughs = 0,
			trialFails = 0,
			tribulations = 0,
			tribulationFails = 0,
			herbs = 0,
			manuals = 0,
		},
	}
end

local function isNumber(value: any): boolean
	return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

-- 지금 단계를 마치는 데 필요한 영력 (과업 배율과 건너뛴 퍼즐 몫 포함)
function Progression.requiredQi(data: Data): number
	local prog = Tasks.ensure(data)
	return math.floor(Balance.qiRequired(data.step) * Tasks.qiMult(data)) + math.floor(prog.debt)
end

-- 공법 장착 칸 수
function Progression.slots(data: Data): number
	local count = 0
	for _, realmId in Skills.SLOT_REALMS do
		if data.step >= Realms.firstStepById[realmId] then
			count += 1
		end
	end
	return count
end

-- 저장소에서 읽은 값을 현재 형식에 맞춘다. 빠진 칸은 기본값, 이상한 값은 버린다.
-- (예전 판의 깨달음·무공 기록, 사축기 이상 경지는 여기서 버려진다)
function Progression.reconcile(saved: any): Data
	local data = Progression.newData()
	if type(saved) ~= "table" then
		return data
	end

	for _, key in { "step", "qi" } do
		if isNumber(saved[key]) then
			data[key] = saved[key]
		end
	end
	if type(saved.stats) == "table" then
		for key, value in saved.stats do
			if type(key) == "string" and isNumber(value) then
				data.stats[key] = value
			end
		end
	end
	if type(saved.skills) == "table" then
		for id, known in saved.skills do
			if Skills.byId[id] and known == true then
				data.skills[id] = true
			end
		end
	end

	data.step = math.clamp(math.floor(data.step), 1, Realms.maxStep)
	local savedElement = if type(saved.choice) == "table" then saved.choice.element else nil
	data.root = Roots.reconcile(saved.root, savedElement)

	-- 과업 진행은 같은 단계일 때만 이어 간다. 예전 판 기록은 지금 단계를 새로 시작한다
	-- (지난 단계의 과업은 끝낸 것으로 친다)
	local prog = saved.prog
	if type(prog) == "table" and prog.step == data.step and type(prog.t) == "table" then
		for id, value in prog.t do
			if type(id) == "string" and isNumber(value) and value >= 0 then
				data.prog.t[id] = value
			end
		end
		if isNumber(prog.debt) and prog.debt > 0 then
			data.prog.debt = prog.debt
		end
	end
	data.prog.step = data.step

	if type(saved.choice) == "table" then
		if table.find(Tasks.CHOICES.chilsu, saved.choice.chilsu) then
			data.choice.chilsu = saved.choice.chilsu
		end
		if Roots.isElement(saved.choice.center) then
			data.choice.center = saved.choice.center
		end
		if table.find(Tasks.CHOICES.dosim, saved.choice.dosim) then
			data.choice.dosim = saved.choice.dosim
		end
	end
	if Races.isRace(saved.race) then
		data.race = saved.race
	end
	if type(saved.weapons) == "table" then
		local weapons = {}
		for _, weapon in saved.weapons do
			if Combat.isWeapon(weapon) and #weapons < Combat.MAX_WEAPONS then
				table.insert(weapons, { kind = weapon.kind, grade = weapon.grade })
			end
		end
		if #weapons > 0 then
			data.weapons = weapons
		end
	end
	-- 영석 (예전 판 기록에는 없어서 처음 값을 준다)
	if isNumber(saved.stones) then
		data.stones = math.clamp(math.floor(saved.stones), 0, Currency.MAX)
	end
	-- 방어 법구: 종류마다 가장 좋은 것 하나, 장착은 가진 것만
	if type(saved.guards) == "table" then
		for _, guard in saved.guards do
			if Guards.isGuard(guard) then
				Progression.addGuard(data, { kind = guard.kind, grade = guard.grade })
			end
		end
	end
	if type(saved.guard) == "string" and Progression.guardOf(data, saved.guard) then
		data.guard = saved.guard
	end
	if type(saved.receipts) == "table" then
		for _, id in saved.receipts do
			if type(id) == "string" and #id <= 80 and #data.receipts < Progression.RECEIPT_KEEP then
				table.insert(data.receipts, id)
			end
		end
	end
	-- 영근 속성이 하나뿐이니 본명 속성은 그 속성이다
	if data.root then
		data.choice.element = Roots.element(data.root)
	end
	-- 전송진 id 는 맵이 정하므로 여기서는 모양만 본다 (없는 진은 Travel 이 무시한다).
	-- 옛 세계에서 밟은 진은 새 세계(옥반)에서 그 자리를 맡은 진으로 옮겨 준다
	if type(saved.waypoints) == "table" then
		for id, open in saved.waypoints do
			if type(id) == "string" and #id <= 40 and open == true then
				data.waypoints[Progression.OLD_WAYPOINTS[id] or id] = true
			end
		end
	end
	if type(saved.items) == "table" then
		for id, count in saved.items do
			if Balance.ITEMS[id] and isNumber(count) and count >= 1 then
				data.items[id] = math.floor(count)
			end
		end
	end
	if type(saved.log) == "table" then
		for _, entry in saved.log do
			if type(entry) == "table" and type(entry.e) == "string" and isNumber(entry.s) then
				table.insert(data.log, { e = entry.e, s = entry.s })
			end
		end
		while #data.log > Progression.LOG_SIZE do
			table.remove(data.log, 1)
		end
	end

	data.qi = math.clamp(data.qi, 0, Progression.requiredQi(data))

	if type(saved.equipped) == "table" then
		for _, id in saved.equipped do
			local def = Skills.byId[id]
			if
				def
				and def.kind == "passive"
				and data.skills[id]
				and not table.find(data.equipped, id)
				and #data.equipped < Progression.slots(data)
			then
				table.insert(data.equipped, id)
			end
		end
	end

	-- 단축칸: 익힌 술법만, 한 술법은 한 칸에만
	if type(saved.hotbar) == "table" then
		for slot = 1, Progression.HOTBAR_SIZE do
			local id = saved.hotbar[slot]
			local def = Skills.byId[id]
			if def and def.kind == "active" and data.skills[id] and not table.find(data.hotbar, id) then
				data.hotbar[slot] = id
			end
		end
	end
	-- 예전 기록처럼 단축칸이 없으면 익힌 술법을 빈 칸에 채운다
	for _, def in Skills.actives do
		if data.skills[def.id] and not table.find(data.hotbar, def.id) then
			local empty = table.find(data.hotbar, "")
			if empty then
				data.hotbar[empty] = def.id
			end
		end
	end

	-- 키: 쓸 수 있는 키만, 겹치지 않게. 모자라면 기본값부터 채운다
	local keys = table.create(Progression.HOTBAR_SIZE, "")
	if type(saved.keys) == "table" then
		for slot = 1, Progression.HOTBAR_SIZE do
			local key = saved.keys[slot]
			if Progression.isBindable(key) and not table.find(keys, key) then
				keys[slot] = key
			end
		end
	end
	for slot = 1, Progression.HOTBAR_SIZE do
		if keys[slot] == "" then
			for _, candidate in Progression.DEFAULT_KEYS do
				if not table.find(keys, candidate) then
					keys[slot] = candidate
					break
				end
			end
		end
	end
	data.keys = keys
	return data
end

-- 술법·공법 ----------------------------------------------------------------------

function Progression.knows(data: Data, id: string): boolean
	return data.skills[id] == true
end

-- 장착해서 효과가 걸려 있는 공법인가
function Progression.passive(data: Data, id: string): boolean
	return table.find(data.equipped, id) ~= nil
end

function Progression.canComprehend(data: Data, id: string): boolean
	local def = Skills.byId[id]
	return def ~= nil and data.step >= Realms.firstStepById[def.minRealm]
end

-- 비급을 익힌다. 빈 칸이 있으면 공법은 바로 장착한다.
function Progression.learn(data: Data, id: string): (boolean, string)
	local def = Skills.byId[id]
	if not def then
		return false, "알 수 없는 비급이다."
	end
	if Progression.knows(data, id) then
		return false, string.format("%s 이미 익혔다.", Josa.eun(def.name))
	end
	if not Progression.canComprehend(data, id) then
		return false,
			string.format(
				"경지가 모자라 아직 이 비급을 이해할 수 없다. (%s부터)",
				Realms.byId[def.minRealm].name
			)
	end
	data.skills[id] = true
	data.stats.manuals += 1
	if def.kind == "passive" and #data.equipped < Progression.slots(data) then
		table.insert(data.equipped, id)
		return true, string.format("%s 익혀 장착했다!", Josa.eul(def.name))
	end
	if def.kind == "active" then
		local empty = table.find(data.hotbar, "")
		if empty then
			data.hotbar[empty] = id
			return true, string.format("%s 익혀 %s 키 칸에 넣었다!", Josa.eul(def.name), data.keys[empty])
		end
	end
	return true, string.format("%s 익혔다!", Josa.eul(def.name))
end

function Progression.equip(data: Data, id: string): (boolean, string)
	local def = Skills.byId[id]
	if not def or def.kind ~= "passive" or not Progression.knows(data, id) then
		return false, "익히지 않은 공법이다."
	end
	if Progression.passive(data, id) then
		return false, string.format("%s 이미 장착했다.", Josa.eun(def.name))
	end
	if #data.equipped >= Progression.slots(data) then
		return false, "공법 칸이 모자라다. 다른 공법을 먼저 해제해야 한다."
	end
	table.insert(data.equipped, id)
	return true, string.format("%s 장착했다.", Josa.eul(def.name))
end

function Progression.unequip(data: Data, id: string): (boolean, string)
	local index = table.find(data.equipped, id)
	if not index then
		return false, "장착하지 않은 공법이다."
	end
	table.remove(data.equipped, index)
	return true, string.format("%s 해제했다.", Josa.eul(Skills.byId[id].name))
end

-- 술법을 단축칸에 넣는다. 이미 다른 칸에 있던 술법이면 두 칸을 맞바꾼다. id 가 "" 이면 비운다.
function Progression.assignSkill(data: Data, slot: any, id: any): (boolean, string)
	if type(slot) ~= "number" or slot % 1 ~= 0 or slot < 1 or slot > Progression.HOTBAR_SIZE then
		return false, "없는 단축칸이다."
	end
	if id == "" then
		data.hotbar[slot] = ""
		return true, string.format("%s 키 칸을 비웠다.", data.keys[slot])
	end
	local def = Skills.byId[id]
	if not def or def.kind ~= "active" or not Progression.knows(data, id) then
		return false, "익히지 않은 술법은 넣을 수 없다."
	end
	local current = table.find(data.hotbar, id)
	if current then
		data.hotbar[current] = data.hotbar[slot]
	end
	data.hotbar[slot] = id
	return true, string.format("%s %s 키 칸에 넣었다.", Josa.eul(def.name), data.keys[slot])
end

-- 단축칸의 키를 바꾼다. 다른 칸이 쓰던 키면 두 칸의 키를 맞바꾼다.
function Progression.bindKey(data: Data, slot: any, key: any): (boolean, string)
	if type(slot) ~= "number" or slot % 1 ~= 0 or slot < 1 or slot > Progression.HOTBAR_SIZE then
		return false, "없는 단축칸이다."
	end
	if not Progression.isBindable(key) then
		return false, "그 키는 단축키로 쓸 수 없다."
	end
	local other = table.find(data.keys, key)
	if other then
		data.keys[other] = data.keys[slot]
	end
	data.keys[slot] = key
	return true, string.format("단축키를 %s 키로 바꿨다.", key)
end

-- 영력과 단계 -----------------------------------------------------------------------

-- 이 단계에서 다음 단계로 가려면 돌파(B)가 필요한가: 새 경지, 또는 경지 안 천겁
function Progression.needsBreakthrough(step: number): boolean
	return Realms.nextIsMajor(step) or Realms.tribulationAfter(step) ~= nil
end

function Progression.isCapped(data: Data): boolean
	return data.step >= Realms.maxStep or Progression.needsBreakthrough(data.step) or not Tasks.allDone(data)
end

function Progression.isFull(data: Data): boolean
	return data.qi >= Progression.requiredQi(data)
end

function Progression.addLog(data: Data, event: string)
	table.insert(data.log, { e = event, s = data.step })
	while #data.log > Progression.LOG_SIZE do
		table.remove(data.log, 1)
	end
end

-- 비급이 아니라 경지에 올라 얻는 술법과 그 단계
local GRANTS = {
	{
		id = "heogong",
		step = Realms.firstStepById.wonyeong,
		note = "원영이 혼의 계위를 알아본다. 허공이동을 얻었다.",
	},
	{
		id = "yudo",
		step = Realms.firstStepById.cheonin,
		note = "천지 현상을 의지로 비튼다. 천기유도를 얻었다.",
	},
	{
		id = "yeongchul",
		step = Realms.firstStepById.cheonin + 1,
		note = "이립에 이르러 원영이 몸 밖으로 나간다. 원영 출규를 얻었다.",
	},
}
Progression.GRANTS = GRANTS

-- 새 단계에 들어설 때 주는 것. 반환: 알릴 문구 목록
local function enterStep(data: Data): { string }
	local notes = {}
	-- 연기기 3성 십이지율은 진법을 직접 펼쳐 봐야 한다. 취령진이 없으면 기초본을 준다
	if data.step == Realms.firstStepById.yeongi + 2 and not data.skills.chwiryeong then
		data.skills.chwiryeong = true
		local empty = table.find(data.hotbar, "")
		if empty then
			data.hotbar[empty] = "chwiryeong"
		end
		table.insert(
			notes,
			"십이지율을 닦으려면 진법을 펼쳐 봐야 한다. 취령진 기초본을 익혔다."
		)
	end
	for _, grant in GRANTS do
		if data.step >= grant.step and not data.skills[grant.id] then
			data.skills[grant.id] = true
			local empty = table.find(data.hotbar, "")
			if empty then
				data.hotbar[empty] = grant.id
			end
			table.insert(notes, grant.note)
		end
	end
	local cheonin = Realms.firstStepById.cheonin
	if data.step == cheonin + 2 then
		table.insert(
			notes,
			"지천명에 이르렀다. 천겁 낙뢰가 떨어질 자리를 조금 더 일찍 본다(예지)."
		)
	end
	if data.step == Realms.firstStepById.gyeoldan and data.skills.gyeongsin then
		table.insert(
			notes,
			"금단이 맺히자 경신술이 비둔술로 바뀌었다. 빛줄기처럼 더 멀리 난다."
		)
	end
	if data.step == Realms.firstStepById.gyeoldan + 3 then
		table.insert(
			notes,
			"자미원을 새겼다. 이제 쓰러져도 금단이 몸을 다시 빚는다(10분에 한 번)."
		)
	end
	return notes
end

local function advanceStep(data: Data, carry: boolean): { string }
	local req = Progression.requiredQi(data)
	data.qi = if carry then math.max(0, data.qi - req) else 0
	data.step += 1
	Tasks.ensure(data)
	return enterStep(data)
end

-- 검수용: 단계를 바로 옮긴다. 영력과 과업 진행은 비우고, 그 단계까지 얻는 술법은 준다
function Progression.jumpTo(data: Data, step: number): { string }
	if not isNumber(step) then
		return {}
	end
	data.step = math.clamp(math.floor(step), 1, Realms.maxStep)
	data.qi = 0
	data.prog = { step = data.step, t = {}, debt = 0 }
	-- 내려갔으면 그 경지에 맞게: 공법 칸을 넘는 장착은 풀고, 더 높은 경지에서 얻는 술법은 거둔다
	while #data.equipped > Progression.slots(data) do
		table.remove(data.equipped)
	end
	for _, grant in GRANTS do
		if data.step < grant.step and data.skills[grant.id] then
			data.skills[grant.id] = nil
			local slot = table.find(data.hotbar, grant.id)
			if slot then
				data.hotbar[slot] = ""
			end
		end
	end
	-- 연기기 3성을 건너뛰었으면 취령진도 준다 (십이지율 이후 과업이 진법을 쓴다)
	if data.step > Realms.firstStepById.yeongi + 2 and not data.skills.chwiryeong then
		data.skills.chwiryeong = true
		local empty = table.find(data.hotbar, "")
		if empty then
			data.hotbar[empty] = "chwiryeong"
		end
	end
	return enterStep(data)
end

-- 같은 경지 안이고 영력과 과업이 다 찼으면 단계를 올린다. 반환: 오른 단계 수, 알릴 문구
function Progression.tryAdvance(data: Data): (number, { string })
	local advanced = 0
	local notes = {}
	while not Progression.isCapped(data) and Progression.isFull(data) do
		for _, note in advanceStep(data, true) do
			table.insert(notes, note)
		end
		advanced += 1
	end
	if Progression.isCapped(data) then
		data.qi = math.min(data.qi, Progression.requiredQi(data))
	end
	return advanced, notes
end

-- 영력을 더하고, 같은 경지 안에서 과업까지 끝났으면 단계를 저절로 올린다.
-- 과업이 남았거나 돌파가 필요한 단계에서는 필요량 이상 쌓이지 않는다.
-- 반환: 오른 단계 수, 알릴 문구
function Progression.addQi(data: Data, amount: number): (number, { string })
	if not isNumber(amount) or amount <= 0 then
		return 0, {}
	end
	data.qi += amount
	return Progression.tryAdvance(data)
end

function Progression.canBreakthrough(data: Data): (boolean, string?)
	if data.step >= Realms.maxStep then
		return false, "이 세계에서 오를 수 있는 끝이다."
	end
	if not Progression.needsBreakthrough(data.step) then
		return false, "같은 경지 안에서는 영력과 과업을 채우면 저절로 오른다."
	end
	if not Tasks.allDone(data) then
		return false, "아직 이 단계의 과업이 남았다."
	end
	if not Progression.isFull(data) then
		return false, "영력이 아직 덜 찼다."
	end
	return true, nil
end

-- 다음 경지로 넘어가는 방식
function Progression.nextEntry(data: Data): Realms.Entry?
	if data.step >= Realms.maxStep then
		return nil
	end
	if Realms.nextIsMajor(data.step) then
		local entry = Realms.get(data.step + 1).realm.entry
		-- 과업을 아직 켜지 않은 경지의 돌파 내관은 미뤄 두고 바로 오른다
		if entry and entry.kind == "trial" and not Tasks.isLive(data.step) then
			return { kind = "plain", title = "돌파" }
		end
		return entry
	end
	if Realms.tribulationAfter(data.step) then
		return { kind = "tribulation", title = "천겁 맞기" }
	end
	return nil
end

local function advanceMajor(data: Data): { string }
	data.stats.breakthroughs += 1
	return advanceStep(data, false)
end

-- 돌파 버튼. plain 이면 바로 오르고, 아니면 무엇을 시작해야 하는지 돌려준다
function Progression.attemptBreakthrough(data: Data): BreakResult
	local ok, reason = Progression.canBreakthrough(data)
	if not ok then
		return { kind = "blocked", reason = reason }
	end
	local entry = Progression.nextEntry(data)
	if entry and entry.kind == "tribulation" then
		return { kind = "tribulation" }
	elseif entry and entry.kind == "trial" then
		return { kind = "trial", mode = entry.mode }
	end
	advanceMajor(data)
	return { kind = "success" }
end

-- 돌파 내관(무극영운)이나 천겁을 넘었다. 반환: 알릴 문구
function Progression.passBreakthrough(data: Data, viaTribulation: boolean): { string }
	if viaTribulation then
		data.stats.tribulations += 1
	end
	return advanceMajor(data)
end

-- 실패 손실에 곱하는 값 (청심결)
local function lossMult(data: Data): number
	return if Progression.passive(data, "cheongsim") then EFFECT.cheongsimLoss else 1
end

-- 돌파 내관에 실패했다. 경지는 그대로, 영력 일부를 잃는다
function Progression.failTrial(data: Data): number
	local lost = data.qi * Balance.TRIAL_LOSS * lossMult(data)
	data.qi -= lost
	data.stats.trialFails += 1
	return lost
end

-- 천겁에 쓰러졌다(또는 도중에 떠났다). 경지는 그대로, 영력만 잃는다.
function Progression.failTribulation(data: Data): number
	local lost = data.qi * Balance.TRIBULATION_LOSS * lossMult(data)
	data.qi -= lost
	data.stats.tribulationFails += 1
	return lost
end

-- 과업 ------------------------------------------------------------------------------

-- 선통후각: 영력을 더 내고 퍼즐을 건너뛴다 (천·진영근만)
function Progression.skipTask(data: Data, id: string): (boolean, string)
	local task = Tasks.find(data, id)
	if not task or task.kind ~= "trial" or not task.skippable then
		return false, "건너뛸 수 없는 과업이다."
	end
	if Tasks.isDone(data, task) then
		return false, "이미 끝낸 과업이다."
	end
	if not Tasks.isOpen(data, task) then
		return false, "앞의 과업부터 끝내야 한다."
	end
	if not Roots.canSkip(data.root) then
		return false, "잡영근은 구결을 먼저 깨쳐야 한다(선각후통). 직접 풀어야 한다."
	end
	local prog = Tasks.ensure(data)
	prog.debt += math.floor(Balance.qiRequired(data.step) * Tasks.qiMult(data) * Tasks.SKIP_EXTRA)
	Tasks.set(data, task.id, task.max)
	return true,
		string.format("%s 재능으로 먼저 뚫었다. 이 단계에 영력이 더 든다.", Josa.eul(task.label))
end

-- 무기 ------------------------------------------------------------------------------

-- 무기를 얻는다. 같은 종류를 같거나 더 높은 등급으로 이미 가졌거나 칸이 차면 false
function Progression.addWeapon(data: Data, weapon: Combat.Weapon): boolean
	if not Combat.isWeapon(weapon) then
		return false
	end
	for i, owned in data.weapons do
		if owned.kind == weapon.kind then
			if owned.grade >= weapon.grade then
				return false
			end
			-- 더 좋은 같은 종류는 그 칸을 바꾼다
			data.weapons[i] = { kind = weapon.kind, grade = weapon.grade }
			return true
		end
	end
	if #data.weapons >= Combat.MAX_WEAPONS then
		return false
	end
	table.insert(data.weapons, { kind = weapon.kind, grade = weapon.grade })
	return true
end

-- 영석 ------------------------------------------------------------------------------

function Progression.addStones(data: Data, amount: number)
	data.stones = math.clamp(data.stones + math.floor(amount), 0, Currency.MAX)
end

-- 반환: 넉넉해서 뺐는가
function Progression.spendStones(data: Data, amount: number): boolean
	amount = math.floor(amount)
	if amount < 0 or data.stones < amount then
		return false
	end
	data.stones -= amount
	return true
end

local function short(price: number): string
	return string.format("영석이 모자라다. (%s 필요)", Currency.format(price))
end

-- 마을 상점에서 산다. 반환: 샀는가, 알림
function Progression.buy(data: Data, wareId: any): (boolean, string)
	local ware = if type(wareId) == "string" then Currency.wareById[wareId] else nil
	if not ware then
		return false, "그런 물건은 없다."
	end
	local weapon = ware.weapon
	local guard = ware.guard
	if guard and Progression.guardOf(data, guard.kind) then
		return false, "이미 지닌 종류의 방어 법구다. 대장간에서 더 좋은 것을 만들 수 있다."
	end
	if weapon then
		for _, owned in data.weapons do
			if owned.kind == weapon.kind then
				return false, "이미 지닌 종류의 공격 법구다. 대장간에서 강화할 수 있다."
			end
		end
		if #data.weapons >= Combat.MAX_WEAPONS then
			return false, "공격 법구 칸이 다 찼다."
		end
	end
	if not Progression.spendStones(data, ware.price) then
		return false, short(ware.price)
	end
	if guard then
		local bought = { kind = guard.kind, grade = guard.grade }
		Progression.addGuard(data, bought)
		if not data.guard then
			data.guard = bought.kind
		end
		return true, string.format("%s 샀다.", Josa.eul(Guards.name(bought)))
	end
	if weapon then
		local bought = { kind = weapon.kind, grade = weapon.grade }
		Progression.addWeapon(data, bought)
		return true, string.format("%s 샀다.", Josa.eul(Combat.weaponName(bought)))
	end
	local item = ware.item :: string
	local count = ware.count or 1
	Progression.addItem(data, item, count)
	return true, string.format("%s %d개를 샀다.", Balance.ITEMS[item].name, count)
end

-- 대장간에서 index 칸 무기를 한 등급 올린다. 반환: 올렸는가, 알림
function Progression.upgradeWeapon(data: Data, index: any): (boolean, string)
	local weapon = if type(index) == "number" then data.weapons[index] else nil
	if not weapon then
		return false, "그 칸에 법구가 없다."
	end
	local cost = Currency.upgradeCost(weapon.grade)
	if not cost then
		return false, "더 올릴 수 없는 등급이다."
	end
	if not Progression.spendStones(data, cost) then
		return false, short(cost)
	end
	local before = Combat.weaponName(weapon)
	local after = { kind = weapon.kind, grade = weapon.grade + 1 }
	data.weapons[index] = after
	return true, string.format("%s %s 거듭났다.", Josa.i(before), Josa.ro(Combat.weaponName(after)))
end

-- 방어 법구 -------------------------------------------------------------------------

-- 지닌 그 종류 방어 법구 (없으면 nil)
function Progression.guardOf(data: Data, kind: string): Guards.Guard?
	for _, owned in data.guards do
		if owned.kind == kind then
			return owned
		end
	end
	return nil
end

-- 방어 법구를 얻는다. 같은 종류를 같거나 더 높은 등급으로 이미 가졌으면 false
function Progression.addGuard(data: Data, guard: Guards.Guard): boolean
	if not Guards.isGuard(guard) then
		return false
	end
	for i, owned in data.guards do
		if owned.kind == guard.kind then
			if owned.grade >= guard.grade then
				return false
			end
			data.guards[i] = { kind = guard.kind, grade = guard.grade }
			return true
		end
	end
	if #data.guards >= Guards.MAX then
		return false
	end
	table.insert(data.guards, { kind = guard.kind, grade = guard.grade })
	return true
end

-- 지금 지닌 방어 법구
function Progression.equippedGuard(data: Data): Guards.Guard?
	return if data.guard then Progression.guardOf(data, data.guard) else nil
end

-- 지닌 방어 법구의 효과 하나 (Guards.luau 의 칸, 없으면 0)
function Progression.guardValue(data: Data, key: string): number
	return Guards.value(Progression.equippedGuard(data), key)
end

-- 방어 법구를 바꿔 지닌다 (하나만). kind 가 "" 이면 내려놓는다. 반환: 바뀌었는가, 알림
function Progression.equipGuard(data: Data, kind: any): (boolean, string)
	if kind == "" or kind == nil then
		if not data.guard then
			return false, "지닌 방어 법구가 없다."
		end
		data.guard = nil
		return true, "방어 법구를 내려놓았다."
	end
	local owned = if type(kind) == "string" then Progression.guardOf(data, kind) else nil
	if not owned then
		return false, "가지지 않은 방어 법구다."
	end
	if data.guard == owned.kind then
		return false, "이미 지니고 있다."
	end
	data.guard = owned.kind
	return true, string.format("%s 지녔다. %s", Josa.eul(Guards.name(owned)), Guards.effects(owned))
end

-- 대장간에서 방어 법구를 만든다. 반환: 만들었는가, 알림
function Progression.craftGuard(data: Data, kind: any, grade: any): (boolean, string)
	local def = if type(kind) == "string" then Guards.byId[kind] else nil
	local cost = if type(grade) == "number" then Guards.CRAFT[grade] else nil
	if not def or not cost then
		return false, "만들 수 없는 법구다."
	end
	local owned = Progression.guardOf(data, def.id)
	if owned and owned.grade >= grade then
		return false, "이미 같거나 더 좋은 것을 지녔다."
	end
	if data.stones < cost.stones then
		return false, short(cost.stones)
	end
	for item, count in cost.items do
		if Progression.itemCount(data, item) < count then
			return false,
				string.format(
					"%s %d개가 모자라다.",
					Balance.ITEMS[item].name,
					count - Progression.itemCount(data, item)
				)
		end
	end
	Progression.takeItems(data, cost.items)
	data.stones -= cost.stones
	local made = { kind = def.id, grade = grade }
	Progression.addGuard(data, made)
	if not data.guard then
		data.guard = made.kind
	end
	return true, string.format("%s 만들었다.", Josa.eul(Guards.name(made)))
end

-- 요수에게 받는 피해 (방어 법구가 줄인다)
function Progression.mobDamage(data: Data, damage: number): number
	return damage * (1 - Progression.guardValue(data, "reduce"))
end

-- 걸음 배율 (종족과 방어 법구)
function Progression.walkMult(data: Data): number
	return Races.mult(data.race, "speed") * (1 + Progression.guardValue(data, "speed"))
end

-- 호신강기 지속 배율
function Progression.shieldMult(data: Data): number
	return 1 + Progression.guardValue(data, "shield")
end

-- 종족 ------------------------------------------------------------------------------

-- 종족을 뽑는다 (roll: 0~1). 다시 뽑기면 지금과 다른 종족이 나온다
function Progression.rollRace(data: Data, roll: number, reroll: boolean?): string
	local race = Races.pick(roll, if reroll then data.race else nil)
	data.race = race
	return race
end

-- 이 로벅스 구매를 이미 처리했는가. 아니면 기록한다 (오래된 것부터 지운다)
function Progression.claimReceipt(data: Data, purchaseId: string): boolean
	if table.find(data.receipts, purchaseId) then
		return false
	end
	table.insert(data.receipts, purchaseId)
	while #data.receipts > Progression.RECEIPT_KEEP do
		table.remove(data.receipts, 1)
	end
	return true
end

-- 고르기: 영근(root), 칠수(chilsu), 본명 속성(element)
function Progression.choose(data: Data, key: any, value: any): (boolean, string)
	if key == "root" then
		if data.root then
			return false, "영근은 이미 깨어났다."
		end
		local sense = Tasks.find(data, "sense")
		if sense and not Tasks.isDone(data, sense) then
			return false, "먼저 영기를 느껴야 한다. 운기조식을 이어 간다."
		end
		local root = Roots.make(value)
		if not root then
			return false, "고를 수 없는 기운이다."
		end
		data.root = root
		-- 속성이 하나뿐이니 그 속성이 곧 본명 속성이다
		data.choice.element = Roots.element(root)
		Progression.addLog(data, "root")
		return true, string.format("%s 깨어났다.", Josa.i(Roots.describe(root)))
	elseif key == "chilsu" then
		if data.choice.chilsu then
			return false, "칠수는 이미 정했다."
		end
		if data.step < Realms.firstStepById.yeongi + 6 then
			return false, "칠수는 연기기 7성에서 고른다."
		end
		if not table.find(Tasks.CHOICES.chilsu, value) then
			return false, "고를 수 없는 칠수다."
		end
		data.choice.chilsu = value
		Progression.addLog(data, "chilsu")
		return true, string.format("%s에게 제사를 올리기로 했다.", Tasks.CHILSU[value].name)
	elseif key == "element" then
		if data.choice.element then
			return false, "본명 속성은 이미 정했다."
		end
		if data.step < Realms.firstStepById.yeongi + 8 then
			return false, "본명 속성은 연기기 9성에서 고른다."
		end
		if not data.root or not table.find(data.root.elements, value) then
			return false, "내 영근에 없는 속성이다."
		end
		data.choice.element = value
		return true, string.format("본명 속성을 %s 정했다.", Josa.ro(Roots.ELEMENT[value].name))
	elseif key == "center" then
		if data.choice.center then
			return false, "오악의 중심은 이미 정했다."
		end
		if data.step < Realms.firstStepById.wonyeong + 2 then
			return false, "오악은 원영기 여오악지수에서 세운다."
		end
		if not Roots.isElement(value) then
			return false, "고를 수 없는 속성이다."
		end
		data.choice.center = value
		return true, string.format("오악의 중심을 %s 삼았다.", Josa.ro(Roots.ELEMENT[value].name))
	elseif key == "dosim" then
		if data.choice.dosim then
			return false, "도심은 이미 정했다."
		end
		if data.step < Realms.firstStepById.wonyeong + 3 then
			return false, "도심은 천인기에 들기 전에 고른다."
		end
		if not table.find(Tasks.CHOICES.dosim, value) then
			return false, "고를 수 없는 도심이다."
		end
		data.choice.dosim = value
		Progression.addLog(data, "dosim")
		return true, string.format("%s에 미치기로 했다.", Tasks.DOSIM[value].name)
	end
	return false, "고를 수 없다."
end

-- 주머니 ------------------------------------------------------------------------------

function Progression.itemCount(data: Data, id: string): number
	return data.items[id] or 0
end

function Progression.addItem(data: Data, id: string, count: number?)
	data.items[id] = (data.items[id] or 0) + (count or 1)
end

-- 반환: 다 있어서 뺐는가
function Progression.takeItems(data: Data, cost: { [string]: number }): boolean
	for id, count in cost do
		if Progression.itemCount(data, id) < count then
			return false
		end
	end
	for id, count in cost do
		data.items[id] -= count
		if data.items[id] <= 0 then
			data.items[id] = nil
		end
	end
	return true
end

export type EatResult = {
	ok: boolean,
	message: string,
	qi: number?,
	rootChanged: boolean?,
}

-- 주머니에서 하나 먹는다
function Progression.eat(data: Data, id: any): EatResult
	local def = Balance.ITEMS[id]
	if not def or Progression.itemCount(data, id) < 1 then
		return { ok = false, message = "주머니에 없다." }
	end
	if id == "pill" then
		return { ok = false, message = "축기단은 무극영운을 시작할 때 저절로 먹는다." }
	end
	if id == "starSeed" then
		return { ok = false, message = "별씨는 먹는 것이 아니라 단전에 별로 응결한다." }
	end
	if id == "hongsam" then
		if data.step >= Realms.firstStepById.gyeoldan then
			return { ok = false, message = "결단기에 이른 몸은 홍령삼으로 바뀌지 않는다." }
		end
		if data.root and data.root.kind == "hong" then
			return { ok = false, message = "이미 홍령수지체다." }
		end
		Progression.takeItems(data, { hongsam = 1 })
		data.root = Roots.hong(Roots.element(data.root))
		data.choice.element = Roots.element(data.root)
		Progression.addLog(data, "hongsam")
		return {
			ok = true,
			message = "홍령삼을 먹었다. 몸이 홍령수지체로 바뀌었다!",
			rootChanged = true,
		}
	end
	-- 영력이 가득 차 있어도 먹을 수는 있다 (영초 먹기 과업이 막히지 않게). 넘치는 영력은 흩어진다
	local wasted = Progression.isFull(data) and Progression.isCapped(data)
	Progression.takeItems(data, { [id] = 1 })
	data.stats.herbs += 1
	if data.stats.herbs == 1 then
		Progression.addLog(data, "firstHerb")
	end
	if wasted then
		return {
			ok = true,
			message = string.format("%s 먹었지만 영력이 이미 가득 차 흩어졌다.", Josa.eul(def.name)),
			qi = 0,
		}
	end
	local amount = Progression.herbQi(data, id)
	return { ok = true, message = string.format("%s 먹었다.", Josa.eul(def.name)), qi = amount }
end

-- 축기단 빚기 재료가 있는가
function Progression.canCraftPill(data: Data): boolean
	for id, count in Balance.PILL_RECIPE do
		if Progression.itemCount(data, id) < count then
			return false
		end
	end
	return true
end

-- 공법이 반영된 수치 ------------------------------------------------------------------

-- extraMult: 취령진 같은 그 밖의 배율. isNight: 지금 밤인가 (월영족)
function Progression.qiPerSecond(data: Data, veinMult: number, extraMult: number?, isNight: boolean?): number
	local mult = if Progression.passive(data, "tonap") then 1 + EFFECT.tonap else 1
	mult *= Races.mult(data.race, "gain") * (if isNight then Races.mult(data.race, "night") else 1)
	return Balance.qiPerSecond(data.step, veinMult) * mult * Roots.gain(data.root) * (extraMult or 1)
end

function Progression.herbQi(data: Data, item: string): number
	local mult = if Progression.passive(data, "baekcho") then 1 + EFFECT.baekcho else 1
	return Balance.herbQi(data.step, item) * mult * Races.mult(data.race, "herb")
end

-- 내관 미니게임 판정 폭 배율 (잡영근은 넉넉하고, 청심결은 더 넓힌다)
function Progression.trialBand(data: Data): number
	local mult = if Progression.passive(data, "cheongsim") then 1 + EFFECT.cheongsimBand else 1
	return Roots.band(data.root) * mult * Races.mult(data.race, "band")
end

-- 정순지력: 축기기에서 완성한 수(宿)의 수 (0~4)
function Progression.pureForce(data: Data): number
	local first = Realms.firstStepById.chukgi
	return math.clamp((data.step - first) // 7, 0, 4)
end

function Progression.maxHealth(data: Data): number
	local mult = if Progression.passive(data, "geumgang") then 1 + EFFECT.geumgang else 1
	mult *= 1 + Balance.PURE_FORCE_HP * Progression.pureForce(data)
	mult *= Races.mult(data.race, "hp")
	mult *= 1 + Progression.guardValue(data, "hp")
	return math.floor(Balance.maxHealth(data.step) * mult)
end

function Progression.tribulationDamage(data: Data, damage: number): number
	local mult = if Progression.passive(data, "piroe") then 1 - EFFECT.piroe else 1
	mult *= 1 - Balance.PURE_FORCE_GUARD * Progression.pureForce(data)
	mult *= Races.mult(data.race, "guard")
	mult *= 1 - Progression.guardValue(data, "trib")
	return damage * mult
end

function Progression.telegraphTime(data: Data, baseTime: number): number
	local extra = if Progression.passive(data, "cheongi") then EFFECT.cheongi else 0
	-- 천인기 지천명의 예지
	if data.step >= Realms.firstStepById.cheonin + 2 then
		extra += EFFECT.foresight
	end
	return baseTime + extra
end

return Progression
