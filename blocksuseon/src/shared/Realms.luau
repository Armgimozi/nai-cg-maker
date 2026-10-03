-- 수선 경지 데이터. 수계(하계)의 소경계, 범인부터 천인기까지.
--
-- 이름·순서·단계 이름은 나무위키의 회귀수선전 설정 문서를 따랐다. 천겁 수치(줄기 수 말고 피해·반경 등)는
-- 게임에 맞춰 정한 값이다. 천인기 대원만이 하계의 끝이다.
--
-- "단계(step)"는 지금 닦고 있는 자리다. "연기기 3성 십이지율"이면 십이지율을 닦는 중이다.
-- 그 단계의 영력과 과업(Tasks.luau)을 채우면 다음 단계로 오른다. 같은 경지 안에서는 저절로 오르고,
-- 다음 경지로 넘어갈 때만 돌파(B)가 필요하다. 돌파 방식은 경지마다 다르다(entry).

export type Tribulation = {
	name: string,
	waves: number, -- 뇌격 횟수
	simul: number, -- 한 번에 떨어지는 줄기 수 (첫 줄기는 언제나 발밑)
	damage: number, -- 줄기당 피해
	telegraph: number, -- 낙뢰 예고 시간(초)
	radius: number, -- 낙뢰 반경(스터드)
	spread: number, -- 나머지 줄기가 흩어지는 반경
	interval: number, -- 뇌격 사이 간격(초)
	color: { number }, -- RGB
	track: number?, -- 예고가 플레이어를 따라오는 시간(초). 있으면 무거운 금뢰
	gather: number?, -- 겁운이 모이는 시간(초). 기본 3
}

-- 다음 경지로 넘어가는 방식
--   plain       : 과업과 영력을 채우고 B 를 누르면 바로 오른다
--   trial       : B 를 누르면 내관(미니게임). 실패하면 영력 일부를 잃는다
--   tribulation : B 를 누르면 천겁이 내린다
export type Entry = {
	kind: "plain" | "trial" | "tribulation",
	mode: string?, -- trial 의 미니게임 방식
	params: { [string]: any }?, -- trial 의 미니게임 조건
	title: string?, -- 돌파 버튼 이름
	after: string?, -- trial 을 넘으면 이어서 시작할 것 ("tribulation")
	noLoss: boolean?, -- trial 에 실패해도 영력을 잃지 않는다
}

export type Realm = {
	id: string,
	name: string,
	hanja: string?,
	tier: string,
	subs: { string },
	hpMult: number,
	entry: Entry?, -- 이 경지로 들어오는 방식
	tribulation: Tribulation?,
	blurb: string,
}

export type Step = {
	index: number,
	realm: Realm,
	realmIndex: number,
	sub: string,
	subIndex: number,
	isMajor: boolean, -- 이 단계로 올라오려면 돌파가 필요한가
}

local Realms = {}

-- 연기기 14성. 원작의 구결 이름
Realms.YEONGI_SUBS = {
	"1성 칠십이지살",
	"2성 삼십육천강",
	"3성 십이지율",
	"4성 십천간도",
	"5성 구궁귀일",
	"6성 팔괘완로",
	"7성 칠성제의",
	"8성 육합만로",
	"9성 오행진의",
	"10성 사상이의",
	"11성 삼재규일",
	"12성 이의합일",
	"13성 일원일응",
	"14성 무극영운",
}

-- 축기기: 단전에 맺는 스물여덟 영기의 별. 7개씩 1수~4수
Realms.CHUKGI_SUBS = {
	"각수성",
	"항수성",
	"저수성",
	"방수성",
	"심수성",
	"미수성",
	"기수성",
	"두수성",
	"우수성",
	"여수성",
	"허수성",
	"위수성",
	"실수성",
	"벽수성",
	"규수성",
	"누수성",
	"위수성",
	"묘수성",
	"필수성",
	"자수성",
	"참수성",
	"정수성",
	"귀수성",
	"유수성",
	"성수성",
	"장수성",
	"익수성",
	"진수성",
}

Realms.list = {
	{
		id = "mortal",
		name = "범인",
		hanja = "凡人",
		tier = "범인",
		subs = { "" },
		hpMult = 1,
		blurb = "영기를 모르는 평범한 사람.",
	},
	{
		id = "dansu",
		name = "단수기",
		hanja = "丹修期",
		tier = "소경계",
		subs = { "" },
		hpMult = 1.1,
		entry = { kind = "plain", title = "단수기로" },
		blurb = "법화단전을 빚어 법력을 담을 그릇을 만든다.",
	},
	{
		id = "yeongi",
		name = "연기기",
		hanja = "練氣期",
		tier = "소경계",
		subs = Realms.YEONGI_SUBS,
		hpMult = 1.25,
		entry = { kind = "plain", title = "연기기로" },
		blurb = "열네 성에 걸쳐 몸 안에 영맥을 깔고 진도를 그린다.",
	},
	{
		id = "chukgi",
		name = "축기기",
		hanja = "築氣期",
		tier = "소경계",
		subs = Realms.CHUKGI_SUBS,
		hpMult = 1.5,
		entry = { kind = "trial", mode = "strands", title = "무극영운" },
		blurb = "단전에 스물여덟 영기의 별을 맺는다.",
	},
	{
		id = "gyeoldan",
		name = "결단기",
		hanja = "結丹期",
		tier = "소경계",
		subs = { "천시원", "태미원", "자미원", "천상열차분야" },
		hpMult = 2.0,
		entry = {
			kind = "trial",
			mode = "balance",
			params = { bars = 3, target = 18, labels = { "천", "지", "인" } },
			title = "금단 응결",
		},
		blurb = "스물여덟 별로 하늘을 그려 금단을 맺는다.",
	},
	{
		id = "wonyeong",
		name = "원영기",
		hanja = "元靈期",
		tier = "소경계",
		subs = { "여월지긍", "여일지승", "여오악지수", "불건불붕" },
		hpMult = 2.6,
		-- 주마등을 거슬러 태어난 날에 닿으면 원영이 맺히고, 이어서 첫 금색 천겁이 내린다
		entry = { kind = "trial", mode = "order", title = "주마등", after = "tribulation", noLoss = true },
		tribulation = {
			name = "금색 천겁",
			waves = 1,
			simul = 1,
			damage = 120,
			telegraph = 1.6,
			radius = 11,
			spread = 0,
			interval = 1,
			color = { 255, 210, 90 },
			track = 4,
			gather = 8,
		},
		blurb = "혼의 계위에 올라 원영을 빚는다. 처음으로 금색 천겁이 내린다.",
	},
	{
		id = "cheonin",
		name = "천인기",
		hanja = "天人期",
		tier = "소경계",
		subs = { "지선과 이립", "불혹과 지천명", "천순과 종심", "천원" },
		hpMult = 3.4,
		entry = { kind = "tribulation", title = "천겁 맞기" },
		tribulation = {
			name = "천겁 다섯 줄기",
			waves = 1,
			simul = 5,
			damage = 60,
			gather = 6,
			telegraph = 1.6,
			radius = 7,
			spread = 14,
			interval = 1.6,
			color = { 255, 215, 120 },
		},
		blurb = "원영이 사계를 따라 늙는다. 천인 대원만이 하계의 끝이다.",
	},
} :: { Realm }

Realms.byId = {} :: { [string]: Realm }
Realms.firstStepById = {} :: { [string]: number }
Realms.steps = {} :: { Step }

for realmIndex, realm in Realms.list do
	Realms.byId[realm.id] = realm
	for subIndex, sub in realm.subs do
		local index = #Realms.steps + 1
		if subIndex == 1 then
			Realms.firstStepById[realm.id] = index
		end
		Realms.steps[index] = {
			index = index,
			realm = realm,
			realmIndex = realmIndex,
			sub = sub,
			subIndex = subIndex,
			isMajor = subIndex == 1 and realmIndex > 1,
		}
	end
end

Realms.maxStep = #Realms.steps

function Realms.get(step: number): Step
	return Realms.steps[math.clamp(step, 1, Realms.maxStep)]
end

-- "연기기 3성 십이지율", "범인" 처럼 화면에 보여 줄 이름.
function Realms.label(step: number): string
	local s = Realms.get(step)
	if s.sub == "" then
		return s.realm.name
	end
	return s.realm.name .. " " .. s.sub
end

-- 다음 단계가 새 경지라서 돌파가 필요한가 (= 지금이 그 경지의 마지막 단계인가)
function Realms.nextIsMajor(step: number): boolean
	if step >= Realms.maxStep then
		return false
	end
	return Realms.steps[step + 1].isMajor
end

-- 원영기·천인기 안에서 다음 단계로 오를 때 내리는 천겁 (원작: 원영 1·2·3·4, 천인 5·10·15·20 줄기)
-- 경지 진입 천겁은 realm.tribulation 이고, 여기는 경지 안의 경계다.
local INNER_TRIBULATIONS = {
	wonyeong = function(subIndex: number): Tribulation
		local count = subIndex + 1
		return {
			name = string.format("금색 천겁 %d줄기", count),
			waves = count,
			simul = 1,
			damage = 110,
			telegraph = 1.6,
			radius = 10,
			spread = 0,
			interval = 1.2,
			color = { 255, 210, 90 },
			track = 3,
			gather = 6,
		}
	end,
	cheonin = function(subIndex: number): Tribulation
		local waves = subIndex + 1 -- 다섯 줄기씩 2·3·4번 = 10·15·20줄기
		return {
			name = string.format("천겁 %d줄기", waves * 5),
			waves = waves,
			simul = 5,
			damage = 55,
			gather = 6,
			telegraph = 1.6,
			radius = 7,
			spread = 14,
			interval = 1.8,
			color = { 255, 215, 120 },
		}
	end,
}

-- step 에서 다음 단계로 오를 때 내리는 천겁. 없으면 nil
function Realms.tribulationAfter(step: number): Tribulation?
	if step >= Realms.maxStep then
		return nil
	end
	local nextStep = Realms.steps[step + 1]
	if nextStep.isMajor then
		local entry = nextStep.realm.entry
		local withTribulation = entry ~= nil and (entry.kind == "tribulation" or entry.after == "tribulation")
		return if withTribulation then nextStep.realm.tribulation else nil
	end
	local inner = INNER_TRIBULATIONS[nextStep.realm.id]
	return if inner then inner(Realms.steps[step].subIndex) else nil
end

return Realms
