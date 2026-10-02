-- 플레이어 저장 데이터를 다루는 순수 로직.
-- 인스턴스나 서비스에 손대지 않으므로 서버 밖(테스트)에서도 그대로 돌릴 수 있다.

local Realms = require(script.Parent.Realms)
local Balance = require(script.Parent.Balance)
local Skills = require(script.Parent.Skills)
local Josa = require(script.Parent.Josa)

export type Data = {
	version: number,
	step: number,
	qi: number,
	skills: { [string]: boolean }, -- 익힌 술법·공법
	equipped: { string }, -- 장착한 공법
	hotbar: { string }, -- 술법 단축칸마다 넣은 술법 ("" 은 빈 칸)
	keys: { string }, -- 단축칸마다 쓰는 키 이름 (KeyCode.Name)
	stats: { [string]: number },
}

export type BreakResult = {
	kind: "blocked" | "success" | "fail" | "tribulation",
	reason: string?,
	chance: number?,
	lost: number?,
}

local EFFECT = Skills.EFFECT

local Progression = {}

Progression.DATA_VERSION = 3

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
		skills = {},
		equipped = {},
		hotbar = table.create(Progression.HOTBAR_SIZE, ""),
		keys = table.clone(Progression.DEFAULT_KEYS),
		stats = {
			breakthroughs = 0,
			deviations = 0,
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
-- (예전 판의 깨달음·무공 기록은 여기서 버려진다)
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
	data.qi = math.clamp(data.qi, 0, Balance.qiRequired(data.step))

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

function Progression.isCapped(data: Data): boolean
	return data.step >= Realms.maxStep or Realms.nextIsMajor(data.step)
end

-- 영력을 더하고, 같은 대경지 안이면 단계를 저절로 올린다.
-- 병목(대경지 직전)이나 최고 경지에서는 필요량 이상 쌓이지 않는다.
-- 반환: 오른 단계 수
function Progression.addQi(data: Data, amount: number): number
	if not isNumber(amount) or amount <= 0 then
		return 0
	end
	data.qi += amount

	local advanced = 0
	while not Progression.isCapped(data) do
		local req = Balance.qiRequired(data.step)
		if data.qi < req then
			break
		end
		data.qi -= req
		data.step += 1
		advanced += 1
	end

	if Progression.isCapped(data) then
		data.qi = math.min(data.qi, Balance.qiRequired(data.step))
	end
	return advanced
end

function Progression.canBreakthrough(data: Data): (boolean, string?)
	if data.step >= Realms.maxStep then
		return false, "더 오를 경지가 없다."
	end
	if not Realms.nextIsMajor(data.step) then
		return false, "아직 병목이 아니다. 같은 경지 안에서는 영력이 차면 저절로 오른다."
	end
	if data.qi < Balance.qiRequired(data.step) then
		return false, "영력이 아직 덜 찼다."
	end
	return true, nil
end

function Progression.breakChance(data: Data): number?
	if data.step >= Realms.maxStep then
		return nil
	end
	local target = Realms.get(data.step + 1).realm
	if not target.breakChance then
		return nil
	end
	local bonus = if Progression.passive(data, "cheongsim") then EFFECT.cheongsimChance else 0
	return math.min(Balance.MAX_BREAK_CHANCE, target.breakChance + bonus)
end

-- 돌파·천겁 실패 손실에 곱하는 값
local function lossMult(data: Data): number
	return if Progression.passive(data, "cheongsim") then EFFECT.cheongsimLoss else 1
end

local function advanceMajor(data: Data)
	data.step += 1
	data.qi = 0
	data.stats.breakthroughs += 1
end

-- roll: 0 이상 1 미만의 난수
function Progression.attemptBreakthrough(data: Data, roll: number): BreakResult
	local ok, reason = Progression.canBreakthrough(data)
	if not ok then
		return { kind = "blocked", reason = reason }
	end

	local target = Realms.get(data.step + 1)
	if target.realm.tribulation then
		return { kind = "tribulation" }
	end

	local chance = Progression.breakChance(data) :: number
	if roll < chance then
		advanceMajor(data)
		return { kind = "success", chance = chance }
	end

	local lost = data.qi * Balance.DEVIATION_LOSS * lossMult(data)
	data.qi -= lost
	data.stats.deviations += 1
	return { kind = "fail", chance = chance, lost = lost }
end

-- 천겁을 끝까지 버텼다.
function Progression.passTribulation(data: Data)
	advanceMajor(data)
	data.stats.tribulations += 1
end

-- 천겁에 쓰러졌다(또는 도중에 떠났다). 경지는 그대로, 영력만 잃는다.
function Progression.failTribulation(data: Data): number
	local lost = data.qi * Balance.TRIBULATION_LOSS * lossMult(data)
	data.qi -= lost
	data.stats.tribulationFails += 1
	return lost
end

-- 공법이 반영된 수치 ------------------------------------------------------------------

-- extraMult: 취령진 같은 그 밖의 배율
function Progression.qiPerSecond(data: Data, veinMult: number, extraMult: number?): number
	local mult = if Progression.passive(data, "tonap") then 1 + EFFECT.tonap else 1
	return Balance.qiPerSecond(data.step, veinMult) * mult * (extraMult or 1)
end

function Progression.herbQi(data: Data, rare: boolean): number
	local mult = if Progression.passive(data, "baekcho") then 1 + EFFECT.baekcho else 1
	return Balance.herbQi(data.step, rare) * mult
end

function Progression.maxHealth(data: Data): number
	local mult = if Progression.passive(data, "geumgang") then 1 + EFFECT.geumgang else 1
	return math.floor(Balance.maxHealth(data.step) * mult)
end

function Progression.tribulationDamage(data: Data, damage: number): number
	return if Progression.passive(data, "piroe") then damage * (1 - EFFECT.piroe) else damage
end

function Progression.telegraphTime(data: Data, baseTime: number): number
	return baseTime + (if Progression.passive(data, "cheongi") then EFFECT.cheongi else 0)
end

return Progression
