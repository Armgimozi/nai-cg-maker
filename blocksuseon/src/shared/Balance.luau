-- 수치 공식 모음. 밸런스는 여기 숫자만 바꾸면 된다.

local Realms = require(script.Parent.Realms)
local Insights = require(script.Parent.Insights)
local MartialRanks = require(script.Parent.MartialRanks)

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

function Balance.qiRequired(step: number): number
	local req = Balance.QI_BASE * Balance.QI_GROWTH ^ (step - 1)
	if Realms.nextIsMajor(step) then
		req *= Balance.BOTTLENECK_MULT
	end
	return math.floor(req)
end

function Balance.qiPerSecond(step: number, veinMult: number, gongbeopLevel: number): number
	return Balance.GAIN_BASE
		* Balance.GAIN_GROWTH ^ (step - 1)
		* veinMult
		* (1 + Insights.value("gongbeop", gongbeopLevel))
end

function Balance.herbQi(step: number, gamdyeolLevel: number, rare: boolean): number
	local share = if rare then 1.2 else 0.3
	return Balance.qiRequired(step) * share * (1 + Insights.value("gamdyeol", gamdyeolLevel))
end

-- 돌파 -------------------------------------------------------------------------

function Balance.breakChance(baseChance: number, dosimLevel: number): number
	return math.min(0.98, baseChance + Insights.value("dosim", dosimLevel))
end

-- 주화입마(돌파 실패) 때 잃는 영력 비율
function Balance.deviationLoss(dosimLevel: number): number
	return 0.4 * (1 - math.min(0.6, 0.04 * dosimLevel))
end

-- 천겁에 쓰러졌을 때 잃는 영력 비율. 경지는 떨어지지 않는다.
function Balance.tribulationLoss(dosimLevel: number): number
	return 0.5 * (1 - math.min(0.6, 0.04 * dosimLevel))
end

function Balance.telegraphTime(baseTelegraph: number, geobunLevel: number): number
	return baseTelegraph + Insights.value("geobun", geobunLevel)
end

-- 깨달음 -----------------------------------------------------------------------

-- 같은 경지 안에서 한 단계 오를 때
function Balance.stepPoints(newStep: number): number
	return 1 + math.floor(newStep / 6)
end

-- 대경지를 돌파했을 때 (천겁 없이)
function Balance.breakthroughPoints(realmIndex: number): number
	return 5 * realmIndex
end

-- 천겁을 넘겼을 때
function Balance.tribulationPoints(realmIndex: number): number
	return 12 * realmIndex
end

Balance.RARE_HERB_POINTS = 3

-- 몸 ---------------------------------------------------------------------------

Balance.BASE_HP = 100
Balance.BASE_WALKSPEED = 16

function Balance.maxHealth(step: number, martialExp: number, dancheLevel: number): number
	local realm = Realms.get(step).realm
	local rank = MartialRanks.get(martialExp)
	return math.floor(Balance.BASE_HP * realm.hpMult * rank.hpMult * (1 + Insights.value("danche", dancheLevel)))
end

function Balance.walkSpeed(martialExp: number): number
	return Balance.BASE_WALKSPEED + MartialRanks.get(martialExp).speed
end

-- 무공 -------------------------------------------------------------------------

function Balance.martialExpPerHit(step: number, oseongLevel: number): number
	return (1 + 0.1 * (step - 1)) * (1 + Insights.value("oseong", oseongLevel))
end

Balance.MARTIAL_COOLDOWN = 0.3

return Balance
