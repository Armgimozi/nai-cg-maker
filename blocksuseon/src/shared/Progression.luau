-- 플레이어 저장 데이터를 다루는 순수 로직.
-- 인스턴스나 서비스에 손대지 않으므로 서버 밖(테스트)에서도 그대로 돌릴 수 있다.

local Realms = require(script.Parent.Realms)
local Balance = require(script.Parent.Balance)
local Insights = require(script.Parent.Insights)
local MartialRanks = require(script.Parent.MartialRanks)

export type Data = {
	version: number,
	step: number,
	qi: number,
	martialExp: number,
	enlightenment: number,
	insights: { [string]: number },
	stats: { [string]: number },
}

export type BreakResult = {
	kind: "blocked" | "success" | "fail" | "tribulation",
	reason: string?,
	chance: number?,
	lost: number?,
	points: number?,
}

local Progression = {}

Progression.DATA_VERSION = 1

function Progression.newData(): Data
	return {
		version = Progression.DATA_VERSION,
		step = 1,
		qi = 0,
		martialExp = 0,
		enlightenment = 0,
		insights = {},
		stats = {
			breakthroughs = 0,
			deviations = 0,
			tribulations = 0,
			tribulationFails = 0,
			herbs = 0,
		},
	}
end

local function isNumber(value: any): boolean
	return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

-- 저장소에서 읽은 값을 현재 형식에 맞춘다. 빠진 칸은 기본값, 이상한 값은 버린다.
function Progression.reconcile(saved: any): Data
	local data = Progression.newData()
	if type(saved) ~= "table" then
		return data
	end

	for _, key in { "step", "qi", "martialExp", "enlightenment" } do
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
	if type(saved.insights) == "table" then
		for id, level in saved.insights do
			local def = Insights.byId[id]
			if def and isNumber(level) then
				data.insights[id] = math.clamp(math.floor(level), 0, def.maxLevel)
			end
		end
	end

	data.step = math.clamp(math.floor(data.step), 1, Realms.maxStep)
	data.qi = math.clamp(data.qi, 0, Balance.qiRequired(data.step))
	data.martialExp = math.max(0, data.martialExp)
	data.enlightenment = math.max(0, math.floor(data.enlightenment))
	return data
end

function Progression.insight(data: Data, id: string): number
	return data.insights[id] or 0
end

function Progression.isCapped(data: Data): boolean
	return data.step >= Realms.maxStep or Realms.nextIsMajor(data.step)
end

-- 영력을 더하고, 같은 대경지 안이면 단계를 저절로 올린다.
-- 병목(대경지 직전)이나 최고 경지에서는 필요량 이상 쌓이지 않는다.
-- 반환: 오른 단계 수, 얻은 깨달음
function Progression.addQi(data: Data, amount: number): (number, number)
	if not isNumber(amount) or amount <= 0 then
		return 0, 0
	end
	data.qi += amount

	local advanced, points = 0, 0
	while not Progression.isCapped(data) do
		local req = Balance.qiRequired(data.step)
		if data.qi < req then
			break
		end
		data.qi -= req
		data.step += 1
		advanced += 1
		points += Balance.stepPoints(data.step)
	end

	if Progression.isCapped(data) then
		data.qi = math.min(data.qi, Balance.qiRequired(data.step))
	end
	data.enlightenment += points
	return advanced, points
end

function Progression.canBreakthrough(data: Data): (boolean, string?)
	if data.step >= Realms.maxStep then
		return false, "더 오를 경지가 없다."
	end
	if not Realms.nextIsMajor(data.step) then
		return false, "같은 경지 안에서는 영력이 차면 저절로 오른다."
	end
	if data.qi < Balance.qiRequired(data.step) then
		return false, "영력이 아직 차지 않았다."
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
	return Balance.breakChance(target.breakChance, Progression.insight(data, "dosim"))
end

local function advanceMajor(data: Data, points: number)
	data.step += 1
	data.qi = 0
	data.stats.breakthroughs += 1
	data.enlightenment += points
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
		local points = Balance.breakthroughPoints(target.realmIndex)
		advanceMajor(data, points)
		return { kind = "success", chance = chance, points = points }
	end

	local lost = data.qi * Balance.deviationLoss(Progression.insight(data, "dosim"))
	data.qi -= lost
	data.stats.deviations += 1
	return { kind = "fail", chance = chance, lost = lost }
end

-- 천겁을 끝까지 버텼다.
function Progression.passTribulation(data: Data): number
	local target = Realms.get(data.step + 1)
	local points = Balance.tribulationPoints(target.realmIndex)
	advanceMajor(data, points)
	data.stats.tribulations += 1
	return points
end

-- 천겁에 쓰러졌다(또는 도중에 떠났다). 경지는 그대로, 영력만 잃는다.
function Progression.failTribulation(data: Data): number
	local lost = data.qi * Balance.tribulationLoss(Progression.insight(data, "dosim"))
	data.qi -= lost
	data.stats.tribulationFails += 1
	return lost
end

function Progression.buyInsight(data: Data, id: string): (boolean, string)
	local def = Insights.byId[id]
	if not def then
		return false, "알 수 없는 깨달음이다."
	end
	local level = Progression.insight(data, id)
	if level >= def.maxLevel then
		return false, def.name .. "은(는) 이미 끝까지 깨달았다."
	end
	local cost = Insights.cost(id, level)
	if data.enlightenment < cost then
		return false, "깨달음이 부족하다."
	end
	data.enlightenment -= cost
	data.insights[id] = level + 1
	return true, string.format("%s Lv.%d", def.name, level + 1)
end

-- 반환: 새로 오른 무공 경지 인덱스 (안 올랐으면 nil)
function Progression.addMartialExp(data: Data, amount: number): number?
	local before = MartialRanks.indexFor(data.martialExp)
	data.martialExp += amount
	local after = MartialRanks.indexFor(data.martialExp)
	if after > before then
		return after
	end
	return nil
end

function Progression.qiPerSecond(data: Data, veinMult: number): number
	return Balance.qiPerSecond(data.step, veinMult, Progression.insight(data, "gongbeop"))
end

function Progression.herbQi(data: Data, rare: boolean): number
	return Balance.herbQi(data.step, Progression.insight(data, "gamdyeol"), rare)
end

function Progression.maxHealth(data: Data): number
	return Balance.maxHealth(data.step, data.martialExp, Progression.insight(data, "danche"))
end

function Progression.walkSpeed(data: Data): number
	return Balance.walkSpeed(data.martialExp)
end

return Progression
