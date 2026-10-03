-- 영근(靈根)과 오행.
--
-- 영근은 천지의 영기를 느끼는 능력이다. 이 게임에서 영근은 오행 가운데 한 속성만 지닌다(게임 규칙).
-- 첫 운기 뒤 반응한 기운 하나를 플레이어가 고른다. 홍령삼을 먹은 범인은 홍령수지체가 되어 더 빨리 닦는다.
-- 사람마다 다른 점은 종족(Races.luau)이 맡는다.

export type Root = {
	kind: string, -- "cheon" | "hong"
	elements: { string }, -- 언제나 한 속성
}

local Roots = {}

Roots.ELEMENTS = { "wood", "fire", "earth", "metal", "water" }

Roots.ELEMENT = {
	wood = { name = "목", color = { 110, 200, 120 }, site = "el_wood", place = "만년목" },
	fire = { name = "화", color = { 240, 120, 80 }, site = "el_fire", place = "홍로성 용광로" },
	earth = { name = "토", color = { 210, 170, 100 }, site = "el_earth", place = "황구 토단" },
	metal = { name = "금", color = { 235, 235, 240 }, site = "el_metal", place = "백금굴" },
	water = { name = "수", color = { 90, 140, 230 }, site = "el_water", place = "명경호 물가 바위" },
}

-- 영근 종류별 효과. 숫자는 게임 밸런스 값이다.
--   gain   : 운기조식 흡수 배율
--   band   : 내관 미니게임 판정 폭 배율
--   window : 칠성제의 시운 길이(초)
--   skip   : 영력을 더 내고 퍼즐을 건너뛸 수 있는가 (선통후각)
Roots.KIND = {
	cheon = {
		name = "천영근",
		gain = 1.3,
		band = 1,
		window = 45,
		skip = true,
		summary = "한 속성만 지닌 영근. 퍼즐을 영력으로 건너뛸 수 있다.",
	},
	hong = {
		name = "홍령수지체",
		gain = 1.45,
		band = 1.1,
		window = 60,
		skip = true,
		summary = "홍령삼을 먹고 바뀐 몸. 같은 속성으로 더 빨리 닦는다.",
	},
}

-- 무극영운에서 잡아야 할 변화 가닥 수
Roots.STRANDS = 4

function Roots.isElement(value: any): boolean
	return type(value) == "string" and Roots.ELEMENT[value] ~= nil
end

-- 고른 속성이 올바르면 영근을 만든다. 속성 하나(문자열 또는 하나짜리 목록)만 받는다
function Roots.make(elements: any): Root?
	local element = elements
	if type(elements) == "table" then
		if #elements ~= 1 then
			return nil
		end
		element = elements[1]
	end
	if not Roots.isElement(element) then
		return nil
	end
	return { kind = "cheon", elements = { element } }
end

-- 홍령삼을 먹은 몸: 속성은 그대로, 종류만 바뀐다
function Roots.hong(element: string?): Root
	return { kind = "hong", elements = { if Roots.isElement(element) then element :: string else "wood" } }
end

-- 저장된 값을 지금 형식에 맞춘다. 예전 판의 여러 속성 영근은 prefer(본명 속성) 또는 첫 속성 하나만 남긴다
function Roots.reconcile(saved: any, prefer: string?): Root?
	if type(saved) ~= "table" or type(saved.elements) ~= "table" then
		return nil
	end
	local element = nil
	for _, value in saved.elements do
		if Roots.isElement(value) and (element == nil or value == prefer) then
			element = value
		end
	end
	if not element then
		return nil
	end
	if saved.kind == "hong" then
		return Roots.hong(element)
	end
	return Roots.make(element)
end

function Roots.gain(root: Root?): number
	return if root then Roots.KIND[root.kind].gain else 1
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

function Roots.strands(_root: Root?): number
	return Roots.STRANDS
end

-- 영근의 속성
function Roots.element(root: Root?): string?
	return if root then root.elements[1] else nil
end

-- "천영근 (목)"
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
