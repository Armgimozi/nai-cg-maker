-- 단계마다 해야 하는 일(과업).
--
-- 영력은 연료이고, 다음 단계로 가는 열쇠는 그 단계에서 원작이 정한 일이다. 과업을 비워 둔 단계는
-- 영력만 차면 오른다. 진행은 data.prog = { step, t = { [과업 id] = 값 }, debt } 에 담고,
-- 단계가 바뀌면 비운다.
--
-- 과업 종류
--   meditate : 운기조식한 초. sites 가 있으면 그 자리마다 seconds 씩 (order 면 순서대로)
--   touch    : 자리를 F 로 만진다 (order 면 순서대로, 틀리면 처음부터)
--   eat      : 주머니의 물건을 먹는다
--   choose   : 무언가를 고른다 (영근, 칠수, 본명 속성)
--   trial    : 내관 미니게임 (Trials.luau)
--   offer    : 자리에 물건을 바친다
--   ritual   : 제의 (칠성제의)
--   have     : 물건을 가지고 있다 (optional 과업에 쓴다)

local Roots = require(script.Parent.Roots)
local Realms = require(script.Parent.Realms)

export type Task = {
	id: string,
	kind: string,
	label: string, -- HUD 한 줄
	hint: string, -- 어디서 무엇을 하는지
	max: number,
	seconds: number?,
	sites: { string }?,
	order: boolean?,
	when: string?, -- "day" | "night"
	formation: boolean?,
	item: string?,
	key: string?,
	mode: string?,
	params: { [string]: any }?,
	skippable: boolean?,
	after: string?, -- 이 과업이 끝나야 시작할 수 있다
	optional: boolean?,
}

export type Progress = {
	step: number,
	t: { [string]: number },
	debt: number, -- 퍼즐을 건너뛰느라 더 내야 하는 영력
}

local Tasks = {}

-- 영력을 더 내고 퍼즐을 건너뛸 때 그 단계 필요 영력에 더하는 배율 (2.5배 = 1.5배를 더 낸다)
Tasks.SKIP_EXTRA = 1.5

-- 고를 수 있는 것들
Tasks.CHOICES = {
	chilsu = { "cheong", "eum", "baek", "yang" },
}
Tasks.CHILSU = {
	cheong = {
		name = "청존칠수",
		mansion = 1,
		summary = "1수(각수~기수)를 돕는다. 일찍 도움을 받는다.",
	},
	eum = { name = "음존칠수", mansion = 2, summary = "2수(두수~벽수)를 돕는다." },
	baek = {
		name = "백존칠수",
		mansion = 3,
		summary = "3수(규수~참수)를 돕는다. 고비인 후반기에 힘이 된다.",
	},
	yang = {
		name = "양존칠수",
		mansion = 4,
		summary = "4수(정수~진수)를 돕는다. 마지막 고비를 쉽게 넘는다.",
	},
}

local function elementSites(root: Roots.Root?): { string }
	local sites = {}
	for _, element in (if root then root.elements else {}) do
		table.insert(sites, Roots.ELEMENT[element].site)
	end
	return sites
end

local function elementNames(root: Roots.Root?): string
	local names = {}
	for _, element in (if root then root.elements else {}) do
		table.insert(names, Roots.ELEMENT[element].name)
	end
	return table.concat(names, " ")
end

local ALL_ELEMENT_SITES = { "el_wood", "el_fire", "el_earth", "el_metal", "el_water" }
local LU_SITES = {}
for i = 1, 12 do
	LU_SITES[i] = "lu_" .. i
end
local TRIGRAM_SITES = {}
for i = 1, 8 do
	TRIGRAM_SITES[i] = "tri_" .. i
end

-- 단계별 과업. 키는 "경지id:단계번호". 함수는 data 를 받아 과업 목록과 영력 배율을 돌려준다.
type Builder = (data: any) -> ({ Task }, number?)

local STEP_TASKS: { [string]: Builder } = {}

STEP_TASKS["mortal:1"] = function(_data)
	return {
		{
			id = "sense",
			kind = "meditate",
			label = "영기 느끼기",
			hint = "어디서든 운기조식(R)을 30초 한다.",
			seconds = 30,
			max = 30,
		},
		{
			id = "root",
			kind = "choose",
			key = "root",
			label = "영근 깨우기",
			hint = "몸에 반응하는 기운을 고른다.",
			max = 1,
			after = "sense",
		},
		{
			id = "herb",
			kind = "eat",
			item = "herb",
			label = "영초 먹기",
			hint = "서쪽 영초숲에서 영초를 캐(F) 주머니에서 먹는다.",
			max = 1,
		},
	}
end

STEP_TASKS["dansu:1"] = function(data)
	local root = data.root
	local count = if root then #root.elements else 1
	return {
		{
			id = "ohaeng",
			kind = "meditate",
			label = "오행지의",
			hint = string.format(
				"내 영근 속성(%s)의 오행처에서 20초씩 운기조식한다.",
				elementNames(root)
			),
			sites = elementSites(root),
			seconds = 20,
			max = count,
		},
		{
			id = "yinyang",
			kind = "trial",
			mode = "rhythm",
			params = { beats = 12, interval = 0.9 },
			label = "음양지의",
			hint = "운기조식하며 음양의 기운을 박자에 맞춰 단전에 돌린다.",
			max = 1,
		},
		{
			id = "honwon",
			kind = "trial",
			mode = "balance",
			params = { bars = count, target = 20 },
			label = "혼원지의",
			hint = "영력 농도가 흔들리지 않게 붙잡아 혼원진기로 바꾼다.",
			skippable = true,
			max = 1,
			after = "yinyang",
		},
	},
		0.6
end

STEP_TASKS["yeongi:1"] = function(_data)
	return {
		{
			id = "jisal",
			kind = "trial",
			mode = "sequence",
			params = { nodes = 9, lengths = { 3, 3, 4, 4, 5, 5, 6, 6 }, style = "dots" },
			label = "칠십이지살 72맥",
			hint = "진언이 짚는 맥의 순서를 따라 짚는다. 아홉 맥씩 여덟 번.",
			skippable = true,
			max = 1,
		},
	},
		0.5
end

STEP_TASKS["yeongi:2"] = function(_data)
	return {
		{
			id = "cheongang",
			kind = "trial",
			mode = "sequence",
			params = { nodes = 9, lengths = { 4, 5, 6, 7 }, style = "cheongang" },
			label = "삼십육천강",
			hint = "천괴성부터 천교성까지, 법결을 읊는 순서대로 수결을 맺는다.",
			skippable = true,
			max = 1,
		},
	},
		0.5
end

STEP_TASKS["yeongi:3"] = function(_data)
	return {
		{
			id = "yul",
			kind = "meditate",
			label = "십이지율",
			hint = "광장 네 귀퉁이의 율점 등롱 곁에서 취령진을 펴고 운기조식한다.",
			sites = LU_SITES,
			seconds = 6,
			formation = true,
			max = #LU_SITES,
		},
	},
		0.5
end

STEP_TASKS["yeongi:4"] = function(_data)
	return {
		{
			id = "yanggan",
			kind = "meditate",
			label = "양간 (낮)",
			hint = "낮에 오행처 다섯 곳에서 10초씩 운기조식한다. 갑 병 무 경 임.",
			sites = ALL_ELEMENT_SITES,
			seconds = 10,
			when = "day",
			max = 5,
		},
		{
			id = "eumgan",
			kind = "meditate",
			label = "음간 (밤)",
			hint = "밤에 오행처 다섯 곳에서 10초씩 운기조식한다. 을 정 기 신 계.",
			sites = ALL_ELEMENT_SITES,
			seconds = 10,
			when = "night",
			max = 5,
		},
	},
		0.5
end

STEP_TASKS["yeongi:5"] = function(_data)
	return {
		{
			id = "gugung",
			kind = "trial",
			mode = "arrange",
			params = {},
			label = "구궁귀일",
			hint = "아홉 별의 패를 맞바꿔 가로, 세로, 대각선 합을 모두 15로 맞춘다.",
			skippable = true,
			max = 1,
		},
	},
		0.5
end

STEP_TASKS["yeongi:6"] = function(_data)
	return {
		{
			id = "palgwae",
			kind = "touch",
			label = "팔괘완로",
			hint = "천겁대 기둥을 건 태 리 진 손 감 간 곤 순서로 만진다(F).",
			sites = TRIGRAM_SITES,
			order = true,
			max = #TRIGRAM_SITES,
		},
	},
		0.3
end

STEP_TASKS["yeongi:7"] = function(data)
	local chilsu = data.choice and data.choice.chilsu
	return {
		{
			id = "chilsu",
			kind = "choose",
			key = "chilsu",
			label = "칠수 고르기",
			hint = "제사를 올릴 일곱 별을 고른다. 축기기에서 그 수를 쌓을 때 도움을 받는다.",
			max = 1,
		},
		{
			id = "offer",
			kind = "offer",
			item = "herb",
			label = "제물 바치기 (영초 7)",
			hint = "천겁대 칠성단에 영초 일곱 뿌리를 바친다(F).",
			sites = { "altar" },
			max = 1,
		},
		{
			id = "rite",
			kind = "ritual",
			label = if chilsu
				then string.format("칠성제의 (%s 시운)", Tasks.CHILSU[chilsu].name)
				else "칠성제의",
			hint = "밤, 칠수가 하늘 가운데 오는 시운에 칠성단에서 제의를 올리고 푸른 원으로 별빛을 받는다.",
			sites = { "altar" },
			max = 1,
			after = "offer",
		},
	},
		0.5
end

STEP_TASKS["yeongi:8"] = function(_data)
	return {
		{
			id = "yukhap",
			kind = "meditate",
			label = "육합만로",
			hint = "동 서 남 북 성대와 영산 꼭대기(위), 개울 바닥(아래)에서 12초씩 운기조식한다.",
			sites = { "star_east", "star_west", "star_south", "star_north", "up", "down" },
			seconds = 12,
			max = 6,
		},
	},
		0.5
end

STEP_TASKS["yeongi:9"] = function(data)
	local element = data.choice and data.choice.element
	local root = data.root
	local single = root and #root.elements == 1
	return {
		{
			id = "bonmyeong",
			kind = "choose",
			key = "element",
			label = "본명 속성 고르기",
			hint = if single
				then "천영근은 지닌 속성이 곧 본명 속성이다."
				else "내 영근 속성 가운데 공법의 주 속성으로 삼을 하나를 고른다.",
			max = 1,
		},
		{
			id = "ohaengjin",
			kind = "meditate",
			label = if element then string.format("오행진의 (%s)", Roots.ELEMENT[element].name) else "오행진의",
			hint = if element
				then string.format(
					"%s에서 30초 운기조식해 본명 속성을 깨운다.",
					Roots.ELEMENT[element].place
				)
				else "본명 속성의 오행처에서 30초 운기조식한다.",
			sites = if element then { Roots.ELEMENT[element].site } else {},
			seconds = 30,
			max = 1,
			after = "bonmyeong",
		},
	},
		0.5
end

STEP_TASKS["yeongi:10"] = function(_data)
	return {
		{
			id = "yangmaek",
			kind = "meditate",
			label = "양맥 (낮)",
			hint = "낮에 어디서든 20초 운기조식한다.",
			seconds = 20,
			when = "day",
			max = 20,
		},
		{
			id = "eummaek",
			kind = "meditate",
			label = "음맥 (밤)",
			hint = "밤에 어디서든 20초 운기조식한다.",
			seconds = 20,
			when = "night",
			max = 20,
		},
	},
		0.5
end

STEP_TASKS["yeongi:11"] = function(_data)
	return {
		{
			id = "samjae",
			kind = "meditate",
			label = "천지인규일",
			hint = "개울 바닥(지), 광장 영맥(인), 영산 꼭대기(천) 순서로 15초씩 운기조식한다.",
			sites = { "down", "plaza", "up" },
			order = true,
			seconds = 15,
			max = 3,
		},
	},
		0.5
end

STEP_TASKS["yeongi:12"] = function(_data)
	return {
		{
			id = "iui",
			kind = "trial",
			mode = "rhythm",
			params = { beats = 24, interval = 0.85, streak = true, speedUp = true },
			label = "이의합일",
			hint = "음양을 한 번도 끊기지 않고 돌린다. 박자가 점점 빨라진다.",
			skippable = true,
			max = 1,
		},
	},
		0.5
end

STEP_TASKS["yeongi:13"] = function(_data)
	return {
		{
			id = "ilwon",
			kind = "trial",
			mode = "ring",
			params = { hits = 3 },
			label = "일원일응",
			hint = "줄어드는 영력의 고리가 단전의 한 점에 겹치는 순간을 세 번 잇달아 잡는다.",
			skippable = true,
			max = 1,
		},
	},
		0.5
end

STEP_TASKS["yeongi:14"] = function(_data)
	return {
		{
			id = "pill",
			kind = "have",
			item = "pill",
			label = "축기단 (있으면 쉽다)",
			hint = "마을 연단로에서 영초 6뿌리와 천년영지 1개로 축기단을 빚는다(F). 무극영운의 가닥이 느려지고 시간이 늘어난다.",
			max = 1,
			optional = true,
		},
	},
		0.6
end

local function keyFor(step: number): string
	local s = Realms.get(step)
	return s.realm.id .. ":" .. s.subIndex
end

-- 과업을 실제로 켠 마지막 단계. 그 뒤 단계는 아직 예전처럼 영력만으로 오른다.
-- 경지별 과업을 하나씩 내보낼 때마다 늘린다.
Tasks.LIVE_UNTIL = 2

function Tasks.isLive(step: number): boolean
	return step <= Tasks.LIVE_UNTIL
end

-- 영근이 없는 기록(예전 판)은 어느 단계에서든 먼저 영근을 고른다
local PENDING_ROOT: Task = {
	id = "root",
	kind = "choose",
	key = "root",
	label = "영근 깨우기",
	hint = "몸에 반응하는 기운을 고른다.",
	max = 1,
}

local PENDING_CHILSU: Task = {
	id = "chilsu",
	kind = "choose",
	key = "chilsu",
	label = "칠수 고르기",
	hint = "칠성제의 때 제사한 일곱 별을 고른다.",
	max = 1,
}

-- 이 단계의 과업 목록과 영력 배율
function Tasks.list(data: any): ({ Task }, number)
	local builder = if Tasks.isLive(data.step) then STEP_TASKS[keyFor(data.step)] else nil
	local list: { Task } = {}
	local qiMult = 1
	if builder then
		local tasks, mult = builder(data)
		list = tasks
		qiMult = mult or 1
	end
	local seven = Realms.firstStepById.yeongi + 6
	if data.step > 1 and not data.root then
		table.insert(list, 1, PENDING_ROOT)
	end
	if data.step > seven and Tasks.isLive(seven) and not (data.choice and data.choice.chilsu) then
		table.insert(list, 1, PENDING_CHILSU)
	end
	return list, qiMult
end

function Tasks.find(data: any, id: string): Task?
	for _, task in (Tasks.list(data)) do
		if task.id == id then
			return task
		end
	end
	return nil
end

-- 단계가 바뀌었으면 진행을 비운다
function Tasks.ensure(data: any): Progress
	local prog = data.prog
	if type(prog) ~= "table" or prog.step ~= data.step then
		prog = { step = data.step, t = {}, debt = 0 }
		data.prog = prog
	end
	return prog
end

-- 과업의 지금 값. choose·have 처럼 데이터에서 바로 알 수 있는 것은 거기서 읽는다
function Tasks.value(data: any, task: Task): number
	if task.kind == "choose" then
		if task.key == "root" then
			return if data.root then 1 else 0
		end
		return if data.choice and data.choice[task.key] then 1 else 0
	elseif task.kind == "have" then
		return math.min(task.max, (data.items and data.items[task.item]) or 0)
	end
	local prog = Tasks.ensure(data)
	return math.min(task.max, prog.t[task.id] or 0)
end

function Tasks.isDone(data: any, task: Task): boolean
	return Tasks.value(data, task) >= task.max
end

-- after 로 묶인 과업이면 앞 과업이 끝났는가
function Tasks.isOpen(data: any, task: Task): boolean
	if not task.after then
		return true
	end
	local before = Tasks.find(data, task.after)
	return before == nil or Tasks.isDone(data, before)
end

function Tasks.set(data: any, id: string, value: number)
	local prog = Tasks.ensure(data)
	prog.t[id] = value
end

-- 값을 더한다. 반환: 이번에 막 끝났는가
function Tasks.add(data: any, task: Task, amount: number): boolean
	local before = Tasks.isDone(data, task)
	local prog = Tasks.ensure(data)
	prog.t[task.id] = math.min(task.max, (prog.t[task.id] or 0) + amount)
	return not before and Tasks.isDone(data, task)
end

-- 여러 자리를 도는 과업에서 자리별로 쌓인 초
function Tasks.siteKey(task: Task, site: string): string
	return task.id .. "@" .. site
end

-- 아직 남은 자리 (order 면 다음 한 곳만)
function Tasks.pendingSites(data: any, task: Task): { string }
	local sites = task.sites or {}
	local prog = Tasks.ensure(data)
	if task.order then
		local next = sites[(prog.t[task.id] or 0) + 1]
		return if next then { next } else {}
	end
	local pending = {}
	for _, site in sites do
		if (prog.t[Tasks.siteKey(task, site)] or 0) < (task.seconds or 1) then
			table.insert(pending, site)
		end
	end
	return pending
end

-- 자리 하나를 마쳤다고 표시한다 (touch, offer, 여러 자리 meditate)
function Tasks.finishSite(data: any, task: Task, site: string): boolean
	local prog = Tasks.ensure(data)
	prog.t[Tasks.siteKey(task, site)] = task.seconds or 1
	return Tasks.add(data, task, 1)
end

function Tasks.allDone(data: any): boolean
	for _, task in (Tasks.list(data)) do
		if not task.optional and not Tasks.isDone(data, task) then
			return false
		end
	end
	return true
end

function Tasks.qiMult(data: any): number
	local _, mult = Tasks.list(data)
	return mult
end

-- HUD 에 보낼 요약
function Tasks.snapshot(data: any): { { [string]: any } }
	local out = {}
	for _, task in (Tasks.list(data)) do
		local value = Tasks.value(data, task)
		table.insert(out, {
			id = task.id,
			kind = task.kind,
			label = task.label,
			hint = task.hint,
			value = value,
			max = task.max,
			done = value >= task.max,
			open = Tasks.isOpen(data, task),
			optional = task.optional == true,
			skippable = task.skippable == true,
			key = task.key,
			sites = if task.kind == "meditate"
					or task.kind == "touch"
					or task.kind == "offer"
					or task.kind == "ritual"
				then Tasks.pendingSites(data, task)
				else nil,
			when = task.when,
			seconds = task.seconds,
		})
	end
	return out
end

-- 이 단계에 과업이 있는가 (테스트·밸런스 표용)
function Tasks.hasTasks(step: number): boolean
	return Tasks.isLive(step) and STEP_TASKS[keyFor(step)] ~= nil
end

return Tasks
