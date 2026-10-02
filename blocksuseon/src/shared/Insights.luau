-- 깨달음(悟)으로 올리는 영구 강화.
-- 경지를 오르고 천겁을 넘길 때마다 깨달음을 얻고, 여기서 쓴다.

export type Insight = {
	id: string,
	name: string,
	hanja: string?,
	flavor: string,
	perLevel: number,
	maxLevel: number,
	baseCost: number,
	costGrowth: number,
	describe: (level: number) -> string,
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
		flavor = "구결을 곱씹을수록 영기가 매끄럽게 돈다.",
		perLevel = 0.15,
		maxLevel = 25,
		baseCost = 3,
		costGrowth = 1.2,
		describe = function(level)
			return "운기조식 영기 흡수 +" .. pct(0.15 * level)
		end,
	},
	{
		id = "dosim",
		name = "도심",
		hanja = "道心",
		flavor = "흔들리지 않는 마음이 병목을 넘는다.",
		perLevel = 0.02,
		maxLevel = 15,
		baseCost = 6,
		costGrowth = 1.3,
		describe = function(level)
			return string.format(
				"돌파 성공률 +%dp · 주화입마/천겁 실패 손실 -%s",
				2 * level,
				pct(math.min(0.6, 0.04 * level))
			)
		end,
	},
	{
		id = "danche",
		name = "신체 단련",
		hanja = "鍛體",
		flavor = "영기로 뼈와 살을 다시 빚는다.",
		perLevel = 0.08,
		maxLevel = 25,
		baseCost = 4,
		costGrowth = 1.25,
		describe = function(level)
			return "최대 체력 +" .. pct(0.08 * level)
		end,
	},
	{
		id = "oseong",
		name = "무공 오성",
		hanja = "悟性",
		flavor = "초식 하나를 보고 열을 깨친다.",
		perLevel = 0.25,
		maxLevel = 20,
		baseCost = 3,
		costGrowth = 1.25,
		describe = function(level)
			return "무공 수련 효율 +" .. pct(0.25 * level)
		end,
	},
	{
		id = "geobun",
		name = "겁운 감지",
		hanja = "劫運",
		flavor = "천겁이 떨어질 자리가 먼저 보인다.",
		perLevel = 0.06,
		maxLevel = 10,
		baseCost = 10,
		costGrowth = 1.35,
		describe = function(level)
			return string.format("천겁 낙뢰 예고 시간 +%.2f초", 0.06 * level)
		end,
	},
	{
		id = "gamdyeol",
		name = "영초 감별",
		hanja = "鑑別",
		flavor = "약효가 짙은 영초를 골라 캔다.",
		perLevel = 0.2,
		maxLevel = 10,
		baseCost = 4,
		costGrowth = 1.3,
		describe = function(level)
			return "영초 채집 영력 +" .. pct(0.2 * level)
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
