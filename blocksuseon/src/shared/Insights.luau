-- 깨달음(悟)으로 올리는 영구 강화.
-- 경지를 오르고 천겁을 넘길 때마다 깨달음을 얻고, 여기서 쓴다.

export type Insight = {
	id: string,
	name: string,
	hanja: string?,
	stat: string, -- 짧은 효과 이름
	perLevel: number,
	maxLevel: number,
	baseCost: number,
	costGrowth: number,
	show: (level: number) -> string, -- 그 레벨의 효과 수치
}

local function pct(x: number): string
	return string.format("%d%%", math.floor(x * 100 + 0.5))
end

local Insights = {}

Insights.list = {
	{
		id = "gongbeop",
		name = "공법 숙련",
		hanja = "功法",
		stat = "영기 흡수",
		perLevel = 0.15,
		maxLevel = 25,
		baseCost = 3,
		costGrowth = 1.2,
		show = function(level)
			return "+" .. pct(0.15 * level)
		end,
	},
	{
		id = "dosim",
		name = "도심",
		hanja = "道心",
		stat = "돌파 확률, 실패 손실",
		perLevel = 0.02,
		maxLevel = 15,
		baseCost = 6,
		costGrowth = 1.3,
		show = function(level)
			return string.format("+%dp, -%s", 2 * level, pct(math.min(0.6, 0.04 * level)))
		end,
	},
	{
		id = "danche",
		name = "신체 단련",
		hanja = "鍛體",
		stat = "최대 체력",
		perLevel = 0.08,
		maxLevel = 25,
		baseCost = 4,
		costGrowth = 1.25,
		show = function(level)
			return "+" .. pct(0.08 * level)
		end,
	},
	{
		id = "oseong",
		name = "무공 오성",
		hanja = "悟性",
		stat = "무공 수련",
		perLevel = 0.25,
		maxLevel = 20,
		baseCost = 3,
		costGrowth = 1.25,
		show = function(level)
			return "+" .. pct(0.25 * level)
		end,
	},
	{
		id = "geobun",
		name = "겁운 감지",
		hanja = "劫運",
		stat = "낙뢰 예고",
		perLevel = 0.06,
		maxLevel = 10,
		baseCost = 10,
		costGrowth = 1.35,
		show = function(level)
			return string.format("+%.2f초", 0.06 * level)
		end,
	},
	{
		id = "gamdyeol",
		name = "영초 감별",
		hanja = "鑑別",
		stat = "영초 영력",
		perLevel = 0.2,
		maxLevel = 10,
		baseCost = 4,
		costGrowth = 1.3,
		show = function(level)
			return "+" .. pct(0.2 * level)
		end,
	},
} :: { Insight }

Insights.byId = {} :: { [string]: Insight }
for _, insight in Insights.list do
	Insights.byId[insight.id] = insight
end

-- level → level+1 로 올리는 데 드는 깨달음
function Insights.cost(id: string, level: number): number
	local def = Insights.byId[id]
	return math.floor(def.baseCost * def.costGrowth ^ level)
end

function Insights.value(id: string, level: number): number
	return Insights.byId[id].perLevel * level
end

return Insights
