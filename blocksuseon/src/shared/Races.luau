-- 종족. 원작에 없는 게임 창작 종족이다. 처음 들어올 때 하나가 뽑히고, 로벅스로 다시 뽑을 수 있다.
-- 숫자는 게임 밸런스 값이다. 효과가 없는 칸은 1(배율) 또는 0(더하기)으로 친다.
--   gain     운기조식 흡수 배율
--   night    밤에만 더 붙는 흡수 배율
--   herb     영초·천년영지 영력 배율
--   hp       최대 체력 배율
--   guard    천겁 피해 배율 (작을수록 덜 다친다)
--   band     내관 판정 폭 배율
--   speed    걷는 속도 배율
--   jump     뛰는 높이 배율
--   attack   요수에게 주는 피해 배율
--   doubleHerb 영초를 캘 때 하나 더 얻을 확률

export type Race = {
	id: string,
	name: string,
	weight: number, -- 뽑힐 몫 (모두 더하면 100)
	color: { number }, -- 운기 기운 빛깔
	summary: string,
	gain: number?,
	night: number?,
	herb: number?,
	hp: number?,
	guard: number?,
	band: number?,
	speed: number?,
	jump: number?,
	attack: number?,
	doubleHerb: number?,
}

local Races = {}

Races.list = {
	{
		id = "human",
		name = "인족",
		weight = 34,
		color = { 236, 226, 200 },
		summary = "가장 흔한 사람. 영초를 다루는 솜씨가 좋다.",
		herb = 1.2,
		doubleHerb = 0.1,
	},
	{
		id = "stone",
		name = "석령족",
		weight = 16,
		color = { 170, 160, 140 },
		summary = "바위에서 깬 정령의 핏줄. 몸이 단단해 천겁을 잘 버티지만 걸음이 느리다.",
		hp = 1.2,
		guard = 0.88,
		speed = 0.93,
	},
	{
		id = "feather",
		name = "우인족",
		weight = 15,
		color = { 200, 230, 255 },
		summary = "깃털 같은 몸. 빠르게 걷고 높이 뛴다.",
		speed = 1.12,
		jump = 1.3,
	},
	{
		id = "ember",
		name = "염린족",
		weight = 12,
		color = { 255, 140, 80 },
		summary = "불씨 비늘을 지닌 이들. 싸움에 강하다.",
		attack = 1.2,
		hp = 1.05,
	},
	{
		id = "moon",
		name = "월영족",
		weight = 10,
		color = { 170, 170, 255 },
		summary = "달그림자에서 났다. 밤이면 영기를 훨씬 잘 받아들인다.",
		night = 1.3,
	},
	{
		id = "grove",
		name = "청림족",
		weight = 8,
		color = { 120, 210, 130 },
		summary = "숲의 숨결을 타고났다. 영초를 캐면 하나 더 얻는 일이 잦다.",
		doubleHerb = 0.35,
		gain = 1.05,
	},
	{
		id = "starlit",
		name = "성휘족",
		weight = 4,
		color = { 255, 230, 150 },
		summary = "별빛을 머금은 드문 핏줄. 내관이 맑고 흡수가 빠르다.",
		gain = 1.12,
		band = 1.15,
	},
	{
		id = "dragon",
		name = "용맥족",
		weight = 1,
		color = { 214, 170, 255 },
		summary = "땅속 용맥에서 태어났다는 전설의 핏줄. 모든 것이 조금씩 뛰어나다.",
		gain = 1.15,
		hp = 1.15,
		attack = 1.15,
		guard = 0.9,
	},
} :: { Race }

Races.byId = {} :: { [string]: Race }
local totalWeight = 0
for _, race in Races.list do
	Races.byId[race.id] = race
	totalWeight += race.weight
end
Races.TOTAL_WEIGHT = totalWeight

-- 다시 뽑기 개발자 상품 (Creator Hub 에서 만든 id, 49 로벅스)
Races.REROLL_PRODUCT_ID = 3716222762
Races.REROLL_PRICE = 49

-- roll: 0 이상 1 미만의 수. except 와 다른 종족이 나올 때까지 몫을 다시 나눈다
function Races.pick(roll: number, except: string?): string
	local pool = 0
	for _, race in Races.list do
		if race.id ~= except then
			pool += race.weight
		end
	end
	local target = math.clamp(roll, 0, 0.999999) * pool
	for _, race in Races.list do
		if race.id ~= except then
			target -= race.weight
			if target < 0 then
				return race.id
			end
		end
	end
	return Races.list[1].id
end

function Races.get(id: string?): Race
	return Races.byId[id or ""] or Races.list[1]
end

function Races.isRace(id: any): boolean
	return type(id) == "string" and Races.byId[id] ~= nil
end

-- 배율 하나 (없으면 1)
function Races.mult(id: string?, key: string): number
	local value = (Races.get(id) :: any)[key]
	return if type(value) == "number" then value else 1
end

-- 뽑힐 확률 (%). except 를 빼고 다시 뽑을 때의 확률
function Races.chance(id: string, except: string?): number
	if id == except then
		return 0
	end
	local pool = Races.TOTAL_WEIGHT - (if except and Races.byId[except] then Races.byId[except].weight else 0)
	return Races.byId[id].weight / pool * 100
end

-- 상태창에 보일 효과 줄 ("흡수 +12%, 내관 판정 +15%")
local LABELS = {
	{ "gain", "흡수" },
	{ "night", "밤 흡수" },
	{ "herb", "영초 영력" },
	{ "hp", "체력" },
	{ "guard", "천겁 피해" },
	{ "band", "내관 판정" },
	{ "speed", "걸음" },
	{ "jump", "도약" },
	{ "attack", "공격" },
}
function Races.effects(id: string?): string
	local race = Races.get(id) :: any
	local parts = {}
	for _, entry in LABELS do
		local value = race[entry[1]]
		if type(value) == "number" and value ~= 1 then
			local percent = math.floor((value - 1) * 100 + 0.5)
			table.insert(parts, string.format("%s %s%d%%", entry[2], if percent > 0 then "+" else "", percent))
		end
	end
	if race.doubleHerb then
		table.insert(parts, string.format("영초 하나 더 %d%%", math.floor(race.doubleHerb * 100 + 0.5)))
	end
	return table.concat(parts, ", ")
end

return Races
