-- 방어 법구. 몸의 부위와 상관없이 하나만 지닌 채 쓴다(장착). 겉모습은 없고 효과만 있다.
-- 공격 법구(검·도·창·선)는 Combat.luau. 등급은 범품~극품 다섯.
-- 얻는 곳: 대장간 제작(영석과 재료), 요수가 떨어뜨림(위험도와 같은 등급), 만물상(범품).
-- 숫자는 게임 밸런스 값이다. 효과 칸:
--   reduce  요수에게 받는 피해 감소 (0.1 = 10%)
--   hp      최대 체력 증가
--   trib    천겁 피해 감소
--   shield  호신강기 지속 시간 증가
--   regen   5초 동안 맞지 않으면 초마다 최대 체력의 이만큼 회복
--   reflect 요수에게 받은 피해의 이만큼을 되돌려 준다
--   speed   걸음 증가 (음수면 느려진다)

export type Guard = { kind: string, grade: number }
export type Kind = {
	id: string,
	name: string,
	summary: string,
	values: { [string]: { number } }, -- 효과 칸마다 등급 1~5 값
}

local Guards = {}

Guards.GRADES = { "범품", "하품", "중품", "상품", "극품" }
Guards.MAX = 8 -- 종류마다 하나씩

Guards.KINDS = {
	{
		id = "okpae",
		name = "호신옥패",
		summary = "몸을 지키는 옥패. 요수에게 받는 피해가 줄어든다.",
		values = { reduce = { 0.06, 0.1, 0.14, 0.18, 0.22 } },
	},
	{
		id = "palchi",
		name = "금강팔찌",
		summary = "기혈을 단단히 묶는 팔찌. 최대 체력이 늘어난다.",
		values = { hp = { 0.08, 0.14, 0.2, 0.27, 0.35 } },
	},
	{
		id = "gabui",
		name = "현무갑의",
		summary = "거북 등껍질처럼 단단한 겉옷. 피해를 크게 줄이지만 걸음이 조금 무겁다.",
		values = { reduce = { 0.1, 0.16, 0.22, 0.28, 0.34 }, speed = { -0.06, -0.06, -0.06, -0.06, -0.06 } },
	},
	{
		id = "jam",
		name = "청운잠",
		summary = "구름 무늬 비녀. 천겁의 벼락을 흘려보낸다.",
		values = { trib = { 0.08, 0.12, 0.16, 0.2, 0.25 } },
	},
	{
		id = "bangul",
		name = "진령방울",
		summary = "울릴 때마다 기운을 붙드는 방울. 호신강기가 더 오래 간다.",
		values = { shield = { 0.2, 0.35, 0.5, 0.7, 0.9 } },
	},
	{
		id = "hwan",
		name = "회춘환",
		summary = "생기를 머금은 고리. 한동안 맞지 않으면 체력이 차오른다.",
		values = { regen = { 0.005, 0.008, 0.011, 0.015, 0.02 } },
	},
	{
		id = "gyeong",
		name = "반탄경",
		summary = "작은 구리 거울. 받은 피해 일부를 요수에게 되돌린다.",
		values = { reflect = { 0.08, 0.12, 0.16, 0.22, 0.3 } },
	},
	{
		id = "tti",
		name = "질풍띠",
		summary = "바람을 엮은 허리띠. 걸음이 빨라지고 피해를 조금 줄인다.",
		values = { speed = { 0.05, 0.07, 0.09, 0.11, 0.14 }, reduce = { 0.03, 0.04, 0.05, 0.06, 0.08 } },
	},
} :: { Kind }

Guards.byId = {} :: { [string]: Kind }
Guards.ORDER = {} :: { string }
for _, kind in Guards.KINDS do
	Guards.byId[kind.id] = kind
	table.insert(Guards.ORDER, kind.id)
end

-- 대장간 제작 값: 등급마다 영석과 재료 (Balance.ITEMS 의 id)
export type Cost = { stones: number, items: { [string]: number } }
Guards.CRAFT = {
	{ stones = 40, items = { yodan = 3 } },
	{ stones = 160, items = { yodan = 8, herb = 4 } },
	{ stones = 500, items = { yodan = 16, lingzhi = 1 } },
	{ stones = 1500, items = { yodan = 30, lingzhi = 2 } },
	{ stones = 4000, items = { yodan = 50, lingzhi = 3, starSeed = 1 } },
} :: { Cost }

-- 요수 위험도(1~5)마다 방어 법구가 떨어질 확률 (그 위험도와 같은 등급)
Guards.DROP = { 0.05, 0.06, 0.07, 0.07, 0.09 }

-- 만물상에서 파는 범품 값
Guards.SHOP_PRICE = 70

function Guards.isGuard(value: any): boolean
	return type(value) == "table"
		and Guards.byId[value.kind] ~= nil
		and type(value.grade) == "number"
		and value.grade % 1 == 0
		and value.grade >= 1
		and value.grade <= #Guards.GRADES
end

function Guards.name(guard: Guard): string
	return Guards.GRADES[guard.grade] .. " " .. Guards.byId[guard.kind].name
end

-- 이 법구의 효과 하나 (없으면 0)
function Guards.value(guard: Guard?, key: string): number
	if not guard or not Guards.isGuard(guard) then
		return 0
	end
	local values = Guards.byId[guard.kind].values[key]
	return if values then values[guard.grade] else 0
end

-- 화면에 쓸 효과 줄 ("받는 피해 -10%, 걸음 -6%")
local LABELS = {
	{ "reduce", "받는 피해", -1 },
	{ "hp", "체력", 1 },
	{ "trib", "천겁 피해", -1 },
	{ "shield", "호신강기 지속", 1 },
	{ "regen", "초당 회복", 1 },
	{ "reflect", "피해 되돌림", 1 },
	{ "speed", "걸음", 1 },
}
function Guards.effects(guard: Guard): string
	local parts = {}
	for _, entry in LABELS do
		local value = Guards.value(guard, entry[1])
		if value ~= 0 then
			local percent = value * 100 * entry[3]
			local digits = if math.abs(percent) < 10 and percent % 1 ~= 0 then "%s %s%.1f%%" else "%s %s%d%%"
			local shown = if digits == "%s %s%d%%" then math.floor(math.abs(percent) + 0.5) else math.abs(percent)
			table.insert(parts, string.format(digits, entry[2], if percent > 0 then "+" else "-", shown))
		end
	end
	return table.concat(parts, ", ")
end

return Guards
