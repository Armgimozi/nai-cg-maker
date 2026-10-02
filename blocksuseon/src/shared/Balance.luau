-- 수치 공식 모음. 밸런스는 여기 숫자만 바꾸면 된다.

local Realms = require(script.Parent.Realms)

local Balance = {}

-- 영력 -------------------------------------------------------------------------

Balance.QI_BASE = 20 -- 1단계에서 다음 단계로 가는 데 필요한 영력
Balance.QI_GROWTH = 1.21 -- 단계마다 필요한 영력 배율
Balance.BOTTLENECK_MULT = 3 -- 대경지 직전(병목) 단계의 추가 배율
Balance.GAIN_BASE = 2 -- 범인이 운기조식으로 1초에 얻는 영력
Balance.GAIN_GROWTH = 1.13 -- 단계마다 흡수 속도 배율
Balance.TICK = 0.5 -- 서버가 영력을 정산하는 주기(초)

-- 영맥: 그 위에서 운기조식하면 흡수 배율이 붙는다. 경지가 모자라면 거친 영기를 받아들이지 못한다.
Balance.VEINS = {
	low = { name = "하품 영맥", mult = 1.5, minRealm = "mortal" },
	mid = { name = "중품 영맥", mult = 2.5, minRealm = "chukgi" },
	high = { name = "상품 영맥", mult = 4, minRealm = "gyeoldan" },
}

-- 과업 배율(Tasks)을 곱하기 전의 기본 필요 영력
function Balance.qiRequired(step: number): number
	local req = Balance.QI_BASE * Balance.QI_GROWTH ^ (step - 1)
	if Realms.nextIsMajor(step) then
		req *= Balance.BOTTLENECK_MULT
	end
	return math.floor(req)
end

function Balance.qiPerSecond(step: number, veinMult: number): number
	return Balance.GAIN_BASE * Balance.GAIN_GROWTH ^ (step - 1) * veinMult
end

function Balance.herbQi(step: number, item: string): number
	return Balance.qiRequired(step) * (Balance.ITEMS[item].qi or 0)
end

-- 돌파 -------------------------------------------------------------------------

Balance.TRIAL_LOSS = 0.4 -- 무극영운 같은 돌파 내관에 실패했을 때 잃는 영력 비율
Balance.TRIBULATION_LOSS = 0.5 -- 천겁에 쓰러졌을 때 잃는 영력 비율. 경지는 떨어지지 않는다.

-- 물건 ---------------------------------------------------------------------------

-- 주머니에 담기는 것. qi 는 먹었을 때 그 단계 필요 영력의 몇 배를 얻는가
Balance.ITEMS = {
	herb = { name = "영초", qi = 0.3 },
	lingzhi = { name = "천년영지", qi = 1.5 },
	hongsam = { name = "홍령삼" },
	pill = { name = "축기단" },
	starSeed = { name = "별씨" },
}
Balance.ITEM_ORDER = { "herb", "lingzhi", "hongsam", "pill", "starSeed" }

-- 정순지력: 축기기에서 수(宿)를 하나 완성할 때마다 오르는 몸의 단단함
Balance.PURE_FORCE_HP = 0.05 -- 수마다 최대 체력 +
Balance.PURE_FORCE_GUARD = 0.05 -- 수마다 천겁 피해 -

-- 축기단 연단 재료
Balance.PILL_RECIPE = { herb = 6, lingzhi = 1 }

-- 몸 ---------------------------------------------------------------------------

Balance.BASE_HP = 100

function Balance.maxHealth(step: number): number
	return math.floor(Balance.BASE_HP * Realms.get(step).realm.hpMult)
end

return Balance
