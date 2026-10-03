-- 영근(靈根)과 오행.
--
-- 원작: 영근은 천지의 영기를 느끼는 능력이다. 속성이 하나면 천영근, 둘·셋이면 진영근, 넷·다섯이면
-- 잡영근이다. 속성이 많을수록 여러 공법을 다룰 수 있지만 수련 속도는 기하급수적으로 느려진다.
-- 홍령삼을 먹은 범인은 홍령수지체(목·토)가 되어 천영근만큼 빠르게 닦는다.
-- 영근을 고르는 절차는 원작에 없어서, 여기서는 첫 운기 뒤 반응한 기운을 플레이어가 고른다(게임 규칙).

export type Root = {
	kind: string, -- "cheon" | "jin" | "jap" | "hong"
	elements: { string },
}

local Roots = {}

Roots.ELEMENTS = { "wood", "fire", "earth", "metal", "water" }

Roots.ELEMENT = {
	wood = { name = "목", color = { 110, 200, 120 }, site = "el_wood", place = "영초숲 고목" },
	fire = { name = "화", color = { 240, 120, 80 }, site = "el_fire", place = "천색성 용암 화로" },
	earth = { name = "토", color = { 210, 170, 100 }, site = "el_earth", place = "중령성국 폐허의 뱀 머리" },
	metal = { name = "금", color = { 235, 235, 240 }, site = "el_metal", place = "쇄천봉 금맥굴" },
	water = { name = "수", color = { 90, 140, 230 }, site = "el_water", place = "연하 하구 갯바위" },
}

-- 영근 종류별 효과. 숫자는 게임 밸런스 값이다.
--   gain   : 운기조식 흡수 배율
--   band   : 내관 미니게임 판정 폭 배율 (잡영근은 넉넉하다)
--   window : 칠성제의 시운 길이(초). 천영근은 시운을 정확히 맞춰야 해서 가장 짧다
--   skip   : 영력을 더 내고 퍼즐을 건너뛸 수 있는가 (선통후각은 천·진영근만)
Roots.KIND = {
	cheon = {
		name = "천영근",
		gain = 1.3,
		band = 1,
		window = 30,
		skip = true,
		summary = "가장 빠르다. 퍼즐을 영력으로 건너뛸 수 있다. 칠성제의 시운이 가장 짧다.",
	},
	jin = {
		name = "진영근",
		gain = 1.1,
		band = 1.1,
		window = 60,
		skip = true,
		summary = "무난하다. 퍼즐을 영력으로 건너뛸 수 있다.",
	},
	jap = {
		name = "잡영근",
		gain = 0.85,
		band = 1.3,
		window = 120,
		skip = false,
		summary = "느리고 무극영운이 험하다. 대신 내관 판정이 넉넉하고 시운이 길다.",
	},
	hong = {
		name = "홍령수지체",
		gain = 1.3,
		band = 1.1,
		window = 60,
		skip = true,
		summary = "홍령삼을 먹고 바뀐 몸. 목과 토를 지녔지만 천영근만큼 빠르다.",
	},
}

-- 속성 수에 따라 더 느려진다 (진영근 셋, 잡영근 다섯은 한 단계 더)
local COUNT_GAIN = { 1, 1, 0.92, 1, 0.88 }

function Roots.kindFor(count: number): string
	if count <= 1 then
		return "cheon"
	elseif count <= 3 then
		return "jin"
	end
	return "jap"
end

function Roots.isElement(value: any): boolean
	return type(value) == "string" and Roots.ELEMENT[value] ~= nil
end

-- 고른 속성 목록이 올바르면 영근을 만든다. 겹치거나 모르는 속성은 거절
function Roots.make(elements: any): Root?
	if type(elements) ~= "table" or #elements < 1 or #elements > 5 then
		return nil
	end
	local seen = {}
	local list = {}
	for _, element in Roots.ELEMENTS do
		if table.find(elements, element) then
			table.insert(list, element)
			seen[element] = true
		end
	end
	if #list ~= #elements then
		return nil -- 겹친 속성
	end
	for _, value in elements do
		if not seen[value] then
			return nil
		end
	end
	return { kind = Roots.kindFor(#list), elements = list }
end

function Roots.hong(): Root
	return { kind = "hong", elements = { "wood", "earth" } }
end

-- 저장된 값이 올바른 영근인가
function Roots.reconcile(saved: any): Root?
	if type(saved) ~= "table" then
		return nil
	end
	if saved.kind == "hong" then
		return Roots.hong()
	end
	return Roots.make(saved.elements)
end

function Roots.gain(root: Root?): number
	if not root then
		return 1
	end
	return Roots.KIND[root.kind].gain * (if root.kind == "hong" then 1 else COUNT_GAIN[#root.elements])
end

function Roots.band(root: Root?): number
	return if root then Roots.KIND[root.kind].band else 1
end

function Roots.window(root: Root?): number
	return if root then Roots.KIND[root.kind].window else 60
end

function Roots.canSkip(root: Root?): boolean
	return root ~= nil and Roots.KIND[root.kind].skip
end

-- 무극영운에서 잡아야 할 변화 가닥 수: 속성 수의 제곱 (홍령수지체는 둘로 친다)
function Roots.strands(root: Root?): number
	local count = if root then #root.elements else 1
	return count * count
end

-- "진영근 (목, 화)"
function Roots.describe(root: Root?): string
	if not root then
		return "아직 모름"
	end
	local names = {}
	for _, element in root.elements do
		table.insert(names, Roots.ELEMENT[element].name)
	end
	return string.format("%s (%s)", Roots.KIND[root.kind].name, table.concat(names, ", "))
end

return Roots
