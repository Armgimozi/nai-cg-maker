-- 내관(內觀) 미니게임: 문제 만들기와 답 검사.
--
-- 서버가 seed 를 정해 문제를 내고, 클라이언트는 같은 seed 로 같은 문제를 그린다.
-- 답이 정해진 방식(순서, 배치)은 서버가 답을 다시 맞춰 보고, 손놀림 방식(균형, 박자, 응집, 가닥)은
-- 걸린 시간이 사람이 낼 수 있는 범위인지만 본다.
--
-- 방식
--   sequence : 빛나는 순서를 기억해 같은 순서로 누른다
--   rhythm   : 도는 점이 음·양 자리에 닿을 때 맞춰 누른다
--   balance  : 농도 막대의 바늘을 금색 띠 안에 붙잡아 둔다
--   ring     : 줄어드는 고리가 점에 겹칠 때 누른다
--   arrange  : 구궁판의 패를 맞바꿔 가로·세로·대각선 합을 같게 만든다
--   strands  : 흩어지는 변화 가닥을 시간 안에 모두 붙잡는다

local Trials = {}

-- Park–Miller 난수. Random 은 Lune 테스트에 없어서 직접 쓴다
function Trials.rng(seed: number)
	local state = math.max(1, math.floor(seed) % 2147483646 + 1)
	return function(): number
		state = (state * 16807) % 2147483647
		return state / 2147483647
	end
end

local function randomInt(rand: () -> number, min: number, max: number): number
	return min + math.floor(rand() * (max - min + 1)) % (max - min + 1)
end

-- 삼십육천강 (천괴성 ~ 천교성)
Trials.CHEONGANG = {
	"천괴",
	"천강",
	"천기",
	"천한",
	"천용",
	"천웅",
	"천맹",
	"천위",
	"천영",
	"천귀",
	"천부",
	"천만",
	"천고",
	"천상",
	"천립",
	"천첩",
	"천암",
	"천우",
	"천공",
	"천속",
	"천이",
	"천살",
	"천미",
	"천구",
	"천퇴",
	"천수",
	"천검",
	"천평",
	"천죄",
	"천손",
	"천패",
	"천뢰",
	"천혜",
	"천폭",
	"천곡",
	"천교",
}

-- 구궁의 아홉 별 (낙서 숫자 1~9 순)
Trials.GUGUNG = { "태을", "섭제", "헌원", "초요", "천부", "청룡", "함지", "태음", "천을" }

-- 낙서(洛書) 마방진. 가로·세로·대각선 합이 15
local LOSHU = { 4, 9, 2, 3, 5, 7, 8, 1, 6 }

local function transform(grid: { number }, rotations: number, mirror: boolean): { number }
	local out = table.clone(grid)
	for _ = 1, rotations do
		local rotated = table.create(9, 0)
		for r = 0, 2 do
			for c = 0, 2 do
				-- (r, c) → (c, 2 - r)
				rotated[c * 3 + (2 - r) + 1] = out[r * 3 + c + 1]
			end
		end
		out = rotated
	end
	if mirror then
		local mirrored = table.create(9, 0)
		for r = 0, 2 do
			for c = 0, 2 do
				mirrored[r * 3 + (2 - c) + 1] = out[r * 3 + c + 1]
			end
		end
		out = mirrored
	end
	return out
end

local function isMagic(grid: { number }): boolean
	local lines = {
		{ 1, 2, 3 },
		{ 4, 5, 6 },
		{ 7, 8, 9 },
		{ 1, 4, 7 },
		{ 2, 5, 8 },
		{ 3, 6, 9 },
		{ 1, 5, 9 },
		{ 3, 5, 7 },
	}
	for _, line in lines do
		local sum = 0
		for _, index in line do
			sum += grid[index]
		end
		if sum ~= 15 then
			return false
		end
	end
	return true
end
Trials.isMagic = isMagic

export type Puzzle = { [string]: any }

-- seed 와 params 로 문제를 만든다. 서버와 클라이언트가 똑같이 부른다.
function Trials.generate(mode: string, seed: number, params: { [string]: any }): Puzzle
	local rand = Trials.rng(seed)
	if mode == "sequence" then
		local nodes = params.nodes or 9
		local rounds = {}
		local labels = nil
		if params.style == "cheongang" then
			labels = {}
		end
		for round, length in params.lengths do
			local sequence = {}
			for i = 1, length do
				local node = randomInt(rand, 1, nodes)
				-- 같은 점이 바로 이어지지 않게
				if i > 1 and node == sequence[i - 1] then
					node = node % nodes + 1
				end
				sequence[i] = node
			end
			rounds[round] = sequence
			if labels then
				-- 천강 서른여섯을 아홉씩 네 번에 나눠 쓴다
				local names = {}
				for n = 1, nodes do
					local index = ((round - 1) * nodes + n - 1) % #Trials.CHEONGANG + 1
					names[n] = Trials.CHEONGANG[index]
				end
				labels[round] = names
			end
		end
		return { rounds = rounds, labels = labels }
	elseif mode == "arrange" then
		local solution = transform(LOSHU, randomInt(rand, 0, 3), rand() < 0.5)
		-- 가운데(5)와 두 칸을 고정으로 남기고 나머지를 섞는다
		local fixed = { [5] = true }
		local corners = { 1, 3, 7, 9 }
		fixed[corners[randomInt(rand, 1, 4)]] = true
		local edges = { 2, 4, 6, 8 }
		fixed[edges[randomInt(rand, 1, 4)]] = true
		local free = {}
		for index = 1, 9 do
			if not fixed[index] then
				table.insert(free, index)
			end
		end
		local start = table.clone(solution)
		-- 섞어도 우연히 정답이면 한 번 더 섞는다
		for _ = 1, 10 do
			for i = #free, 2, -1 do
				local j = randomInt(rand, 1, i)
				local a, b = free[i], free[j]
				start[a], start[b] = start[b], start[a]
			end
			if not isMagic(start) then
				break
			end
		end
		local fixedList = {}
		for index in fixed do
			table.insert(fixedList, index)
		end
		table.sort(fixedList)
		return { start = start, fixed = fixedList }
	elseif mode == "strands" then
		local strands = {}
		for i = 1, params.count do
			strands[i] = {
				angle = rand() * math.pi * 2,
				speed = 0.6 + rand() * 0.8,
				radius = 0.25 + rand() * 0.6,
			}
		end
		return { strands = strands }
	end
	-- 손놀림 방식은 seed 로 흔들림만 정한다
	return { wobble = rand() }
end

-- 사람이 이보다 빨리 끝낼 수는 없다 (초)
function Trials.minTime(mode: string, params: { [string]: any }): number
	if mode == "sequence" then
		local total = 0
		for _, length in params.lengths do
			total += length * 0.15 + length * 0.35 -- 보여 주는 시간 + 누르는 시간
		end
		return total * 0.8
	elseif mode == "rhythm" then
		return params.beats * (params.interval or 0.9) * 0.6
	elseif mode == "balance" then
		return params.target * 0.95
	elseif mode == "ring" then
		return params.hits * 0.5
	elseif mode == "arrange" then
		return 2
	elseif mode == "strands" then
		return params.count * 0.12
	end
	return 1
end

-- 답 검사. 답이 정해진 방식만 실제로 맞춰 보고, 나머지는 클라이언트가 성공이라 했는지만 본다.
function Trials.check(mode: string, puzzle: Puzzle, answer: any): boolean
	if mode == "sequence" then
		if type(answer) ~= "table" or #answer ~= #puzzle.rounds then
			return false
		end
		for round, sequence in puzzle.rounds do
			local given = answer[round]
			if type(given) ~= "table" or #given ~= #sequence then
				return false
			end
			for i, node in sequence do
				if given[i] ~= node then
					return false
				end
			end
		end
		return true
	elseif mode == "arrange" then
		if type(answer) ~= "table" or #answer ~= 9 then
			return false
		end
		local seen = {}
		for _, value in answer do
			if type(value) ~= "number" or value % 1 ~= 0 or value < 1 or value > 9 or seen[value] then
				return false
			end
			seen[value] = true
		end
		for _, index in puzzle.fixed do
			if answer[index] ~= puzzle.start[index] then
				return false
			end
		end
		return isMagic(answer)
	end
	return answer == true
end

return Trials
