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

-- 서버 굴림 간격 판정(서버 Roll · 클라이언트 스모크의 가짜 서버가 같이 씀). lastRoll: 지난 굴림의 기준 시각,
-- now: 요청이 서버에 닿은 시각. 받으면 (true, 새 기준 시각), 너무 이르면 (false, 다시 보낼 때까지 남은 초).
-- 허용 오차(tolerance)만큼 일찍 와도 받음. 새 기준 = max(원래 가능했던 시각, 닿은 시각 - 오차):
-- 받을 때마다 기준이 굴림 간격 이상 늘어나서 평균 속도는 1/굴림 간격을 넘지 못하고(오래 쉰 뒤 한 번만 2 × 오차 당겨짐),
-- 한 번 늦게 닿은 요청(업로드 지연이 튐) 뒤에 제때 보낸 요청이 2 × 오차 안에서 일찍 닿아도 거절하지 않음
-- (기준을 늦게 닿은 시각 그대로 두면 지연이 오차보다 줄어든 다음 굴림이 거절됨 — AUTO 가 굴림 간격대로 보내므로)
function RollLogic.cooldownGate(lastRoll: number, now: number, cooldown: number, tolerance: number): (boolean, number)
	local readyAt = lastRoll + cooldown
	if now < readyAt - tolerance then
		return false, readyAt - now
	end
	return true, math.max(readyAt, now - tolerance)
end

return RollLogic
