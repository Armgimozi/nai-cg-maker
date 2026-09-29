--!strict
-- 굴림 판정 (순수 함수 — 서버/테스트에서 공용)
--
-- 방식: 가장 희귀한 오라부터 차례로 "luck / N" 확률 판정을 하고, 처음 성공한 오라를 줍니다.
-- 모두 실패하면 가장 흔한 오라. 그래서 행운 1 에서 희귀 오라는 거의 정확히 1/N,
-- 행운이 L 배면 희귀 오라 확률도 약 L 배가 됩니다. 행운이 N 이상이면 그보다 흔한 오라는 안 나옵니다.

export type Rollable = { Id: string, OneIn: number }

local RollLogic = {}

-- rarestFirst: OneIn 내림차순 목록. nextNumber: [0, 1) 난수 함수.
function RollLogic.roll<T>(rarestFirst: { T & Rollable }, luck: number, nextNumber: () -> number): T & Rollable
	local count = #rarestFirst
	for i = 1, count - 1 do
		local aura = rarestFirst[i]
		-- nextNumber() < luck / OneIn 과 같지만 나눗셈 오차가 없음
		if nextNumber() * aura.OneIn < luck then
			return aura
		end
	end
	return rarestFirst[count]
end

-- 주어진 행운에서 각 오라가 실제로 나올 확률 { [Id] = p } (합계 1)
function RollLogic.probabilities(rarestFirst: { Rollable }, luck: number): { [string]: number }
	local result = {}
	local remaining = 1
	local count = #rarestFirst
	for i = 1, count - 1 do
		local aura = rarestFirst[i]
		local p = math.min(1, luck / aura.OneIn)
		result[aura.Id] = remaining * p
		remaining *= 1 - p
	end
	result[rarestFirst[count].Id] = remaining
	return result
end

return RollLogic
