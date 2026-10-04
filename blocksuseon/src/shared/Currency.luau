-- 영석(靈石): 이 세계의 돈. 영석 광맥을 캐거나 로벅스로 산다.
-- 마을 상점(물건·무기), 대장간(무기 강화), 전송진 삯에 쓴다. 숫자는 게임 밸런스 값이다.
-- 데이터 바꾸기(더하기·빼기·사기·강화)는 Progression.luau, 서버 처리는 server/Market.luau·Ores.luau.

local Currency = {}

Currency.NAME = "영석"
Currency.START = 30 -- 처음 들어온 사람이 지닌 영석
Currency.MAX = 9999999

-- 영석 광맥 (server/Ores.luau). 땅의 위험도(1~5)마다 캐는 양과 F 를 누르고 있는 시간(초)
export type Ore = { min: number, max: number, hold: number }
Currency.ORE = {
	{ min = 3, max = 5, hold = 1.5 },
	{ min = 5, max = 8, hold = 1.8 },
	{ min = 8, max = 13, hold = 2.1 },
	{ min = 12, max = 19, hold = 2.4 },
	{ min = 18, max = 28, hold = 2.7 },
} :: { Ore }

local Guards = require(script.Parent.Guards)

-- 마을 상점에서 파는 것. item 은 Balance.ITEMS 의 id, weapon 은 공격 법구(Combat), guard 는 방어 법구(Guards)
export type Ware = {
	id: string,
	price: number,
	item: string?,
	count: number?,
	weapon: { kind: string, grade: number }?,
	guard: { kind: string, grade: number }?,
}
Currency.WARES = {
	{ id = "herb1", item = "herb", count = 1, price = 15 },
	{ id = "herb10", item = "herb", count = 10, price = 135 },
	{ id = "lingzhi", item = "lingzhi", count = 1, price = 150 },
	{ id = "yodan5", item = "yodan", count = 5, price = 60 },
	{ id = "saber", weapon = { kind = "saber", grade = 1 }, price = 40 },
	{ id = "spear", weapon = { kind = "spear", grade = 1 }, price = 40 },
	{ id = "fan", weapon = { kind = "fan", grade = 1 }, price = 60 },
} :: { Ware }
-- 방어 법구는 범품을 종류마다 판다
for _, id in Guards.ORDER do
	table.insert(Currency.WARES, { id = "guard_" .. id, guard = { kind = id, grade = 1 }, price = Guards.SHOP_PRICE })
end

Currency.wareById = {} :: { [string]: Ware }
for _, ware in Currency.WARES do
	Currency.wareById[ware.id] = ware
end

-- 대장간 무기 강화: 지금 등급에서 한 등급 올리는 값 (목→철, 철→청강, 청강→영, 영→천). 반드시 오른다
Currency.UPGRADE = { 120, 450, 1500, 4500 }

function Currency.upgradeCost(grade: number): number?
	return Currency.UPGRADE[grade]
end

-- 전송진 삯: 처음부터 열린 진(집)으로 돌아가는 길은 공짜. 나머지는 거리에 따라
Currency.TRAVEL_PER = 150 -- 이 거리(스터드)마다 1
Currency.TRAVEL_MIN, Currency.TRAVEL_MAX = 2, 25

function Currency.travelFee(distance: number, toHome: boolean): number
	if toHome then
		return 0
	end
	return math.clamp(math.floor(distance / Currency.TRAVEL_PER + 0.5), Currency.TRAVEL_MIN, Currency.TRAVEL_MAX)
end

-- 로벅스로 사는 영석 묶음 (개발자 상품). productId 는 Creator Hub 에서 만든 id (0 이면 아직 준비 중)
export type Pack = { key: string, name: string, stones: number, robux: number, productId: number }
Currency.PACKS = {
	{ key = "handful", name = "영석 한 줌", stones = 120, robux = 25, productId = 3716222765 },
	{ key = "pouch", name = "영석 주머니", stones = 700, robux = 129, productId = 3716222767 },
	{ key = "chest", name = "영석 상자", stones = 1600, robux = 279, productId = 3716222768 },
} :: { Pack }

function Currency.packByProduct(productId: number): Pack?
	if productId == 0 then
		return nil
	end
	for _, pack in Currency.PACKS do
		if pack.productId == productId then
			return pack
		end
	end
	return nil
end

-- 화면에 쓸 금액 ("영석 1,250")
function Currency.format(amount: number): string
	local digits = tostring(math.floor(amount))
	local out = digits:reverse():gsub("(%d%d%d)", "%1,"):reverse()
	if out:sub(1, 1) == "," then
		out = out:sub(2)
	end
	return out
end

return Currency
