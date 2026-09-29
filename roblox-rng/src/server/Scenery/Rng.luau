--!strict
-- 풍경 배치용 고정 시드 난수(순수 Luau). Roblox 의 Random 과 같은 모양(NextNumber / NextInteger)이지만
-- 알고리즘을 직접 갖고 있어서 Roblox 밖의 미리보기 도구(가짜 환경)에서도 게임과 똑같은 배치가 나옵니다.
-- 선형 합동 생성기(mod 2^32). 곱이 2^53 보다 작아서 실수 계산으로도 정확합니다.

local MODULUS = 4294967296 -- 2^32
local MULTIPLIER = 1664525
local INCREMENT = 1013904223

export type Rng = {
	State: number,
	NextNumber: (self: Rng, min: number?, max: number?) -> number,
	NextInteger: (self: Rng, min: number, max: number) -> number,
	Pick: <T>(self: Rng, list: { T }) -> T,
	Sign: (self: Rng) -> number,
}

local Rng = {}

local function step(self: Rng): number
	self.State = (self.State * MULTIPLIER + INCREMENT) % MODULUS
	return self.State / MODULUS
end

-- [min, max) 실수. 인자가 없으면 [0, 1)
local function nextNumber(self: Rng, min: number?, max: number?): number
	local value = step(self)
	if min and max then
		return min + (max - min) * value
	end
	return value
end

-- [min, max] 정수
local function nextInteger(self: Rng, min: number, max: number): number
	return math.min(max, min + math.floor(step(self) * (max - min + 1)))
end

local function pick<T>(self: Rng, list: { T }): T
	return list[nextInteger(self, 1, #list)]
end

-- -1 또는 1
local function sign(self: Rng): number
	return if step(self) < 0.5 then -1 else 1
end

function Rng.new(seed: number): Rng
	local self: Rng = {
		State = math.floor(math.abs(seed)) % MODULUS,
		NextNumber = nextNumber,
		NextInteger = nextInteger,
		Pick = pick,
		Sign = sign,
	}
	-- 비슷한 시드끼리 첫 값이 닮지 않게 몇 번 섞어 둠
	for _ = 1, 4 do
		step(self)
	end
	return self
end

return Rng
