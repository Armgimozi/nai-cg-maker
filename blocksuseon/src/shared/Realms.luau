-- 수선 경지 데이터.
--
-- 회귀수선전의 경지 순서(소경계 → 중경계)를 따른다. 이름·순서는 나무위키 설정
-- 문서를 참고했고, 세부 단계 수와 천겁 수치는 게임용으로 정한 값이다.
--
-- "단계(step)"는 한 칸씩 오르는 최소 단위다. 같은 대경지 안의 단계는 영력이 차면
-- 저절로 오르고, 다음 대경지의 첫 단계로 넘어갈 때만 돌파(또는 천겁)가 필요하다.

local function numbered(count: number, format: string): { string }
	local subs = {}
	for i = 1, count do
		subs[i] = string.format(format, i)
	end
	return subs
end

local STAGES4 = { "초기", "중기", "후기", "대원만" }

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
}

export type Realm = {
	id: string,
	name: string,
	hanja: string?,
	tier: string,
	subs: { string },
	hpMult: number,
	breakChance: number?, -- 천겁이 없는 돌파의 기본 성공률
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
		breakChance = 0.9,
		blurb = "법화단전을 열어 영기를 받아들일 그릇을 만든다.",
	},
	{
		id = "yeongi",
		name = "연기기",
		hanja = "練氣期",
		tier = "소경계",
		subs = numbered(14, "%d층"),
		hpMult = 1.25,
		breakChance = 0.8,
		blurb = "열네 층에 걸쳐 전신의 영맥을 잇는다.",
	},
	{
		id = "chukgi",
		name = "축기기",
		hanja = "築氣期",
		tier = "소경계",
		subs = numbered(28, "영성 %d"),
		hpMult = 1.5,
		breakChance = 0.65,
		blurb = "스물여덟 개의 영성을 응집한다.",
	},
	{
		id = "gyeoldan",
		name = "결단기",
		hanja = "結丹期",
		tier = "소경계",
		subs = STAGES4,
		hpMult = 2.0,
		tribulation = {
			name = "천겁",
			waves = 9,
			simul = 1,
			damage = 30,
			telegraph = 1.3,
			radius = 7,
			spread = 0,
			interval = 1.4,
			color = { 170, 210, 255 },
		},
		blurb = "금단을 맺는다. 처음으로 천겁을 맞는다.",
	},
	{
		id = "wonyeong",
		name = "원영기",
		tier = "소경계",
		subs = STAGES4,
		hpMult = 2.6,
		tribulation = {
			name = "금색 천겁",
			waves = 10,
			simul = 2,
			damage = 45,
			telegraph = 1.2,
			radius = 7,
			spread = 10,
			interval = 1.4,
			color = { 255, 210, 90 },
		},
		blurb = "원영을 빚어낸다. 금빛 천겁이 내린다.",
	},
	{
		id = "cheonin",
		name = "천인기",
		hanja = "天人期",
		tier = "소경계",
		subs = STAGES4,
		hpMult = 3.4,
		tribulation = {
			name = "오중 천겁",
			waves = 8,
			simul = 5,
			damage = 50,
			telegraph = 1.2,
			radius = 7,
			spread = 14,
			interval = 1.6,
			color = { 225, 225, 255 },
		},
		blurb = "사계를 완성한다. 천겁이 다섯 줄기씩 떨어진다.",
	},
	{
		id = "sachuk",
		name = "사축기",
		tier = "중경계",
		subs = numbered(4, "%d축"),
		hpMult = 4.4,
		tribulation = {
			name = "천겁",
			waves = 10,
			simul = 5,
			damage = 70,
			telegraph = 1.1,
			radius = 8,
			spread = 16,
			interval = 1.5,
			color = { 140, 190, 255 },
		},
		blurb = "네 개의 축을 세워 기축장막을 두른다.",
	},
	{
		id = "hapche",
		name = "합체기",
		hanja = "合體期",
		tier = "중경계",
		subs = numbered(6, "신통 %d"),
		hpMult = 5.6,
		tribulation = {
			name = "육뢰",
			waves = 10,
			simul = 6,
			damage = 90,
			telegraph = 1.1,
			radius = 8,
			spread = 16,
			interval = 1.5,
			color = { 120, 255, 220 },
		},
		blurb = "여섯 신통을 얻는다. 육합천겁, 육뢰가 내린다.",
	},
	{
		id = "swaeseong",
		name = "쇄성기",
		hanja = "碎星期",
		tier = "중경계",
		subs = numbered(7, "%d성"),
		hpMult = 7.0,
		tribulation = {
			name = "성겁",
			waves = 12,
			simul = 7,
			damage = 110,
			telegraph = 1.0,
			radius = 9,
			spread = 18,
			interval = 1.5,
			color = { 200, 130, 255 },
		},
		blurb = "일곱 별을 빚는다. 별의 겁, 성겁을 맞는다.",
	},
	{
		id = "seongban",
		name = "성반기",
		tier = "중경계",
		subs = numbered(8, "%d도"),
		hpMult = 9.0,
		tribulation = {
			name = "사계천겁",
			waves = 12,
			simul = 8,
			damage = 140,
			telegraph = 1.0,
			radius = 9,
			spread = 20,
			interval = 1.5,
			color = { 255, 150, 150 },
		},
		blurb = "팔도를 완성한다. 사계천겁이 몰아친다.",
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

-- "연기기 3층", "범인" 처럼 화면에 보여 줄 이름.
function Realms.label(step: number): string
	local s = Realms.get(step)
	if s.sub == "" then
		return s.realm.name
	end
	return s.realm.name .. " " .. s.sub
end

-- 다음 단계가 새 대경지라서 돌파가 필요한가 (= 지금이 병목인가)
function Realms.nextIsMajor(step: number): boolean
	if step >= Realms.maxStep then
		return false
	end
	return Realms.steps[step + 1].isMajor
end

return Realms
