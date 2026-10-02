-- 술법과 공법.
--   술법(active)  : 단축칸(기본 Q·E·Z·X)에 넣어 쓴다. 쿨타임이 있다.
--   공법(passive) : 장착해 두면 늘 효과가 걸린다. 장착 칸은 경지에 따라 늘어난다.
-- 둘 다 맵 곳곳에 나타나는 비급을 주워 익힌다. 비급마다 이해할 수 있는 최소 경지가 있다.

export type Skill = {
	id: string,
	kind: "active" | "passive",
	name: string,
	icon: string, -- Art.images 이름
	minRealm: string, -- 이 경지부터 비급을 이해할 수 있다
	summary: string, -- 상태창 설명 한 줄
	cooldown: number?, -- 술법
	duration: number?, -- 술법 지속 시간
}

local Skills = {}

Skills.list = {
	{
		id = "gyeongsin",
		kind = "active",
		name = "경신술",
		icon = "skillDash",
		minRealm = "mortal",
		cooldown = 5,
		summary = "보는 방향으로 몸을 날린다",
	},
	{
		id = "yeongan",
		kind = "active",
		name = "영안",
		icon = "skillEye",
		minRealm = "dansu",
		cooldown = 30,
		duration = 12,
		summary = "영초와 비급이 벽 너머로 보인다",
	},
	{
		id = "chwiryeong",
		kind = "active",
		name = "취령진",
		icon = "skillFormation",
		minRealm = "yeongi",
		cooldown = 30,
		duration = 15,
		summary = "진 안에서 운기조식하면 흡수가 두 배",
	},
	{
		id = "hosin",
		kind = "active",
		name = "호신강기",
		icon = "skillShield",
		minRealm = "chukgi",
		cooldown = 25,
		duration = 3,
		summary = "3초 동안 천겁 낙뢰를 막는다",
	},
	{
		id = "tonap",
		kind = "passive",
		name = "토납법",
		icon = "skillBreath",
		minRealm = "mortal",
		summary = "운기조식 흡수 +30%",
	},
	{
		id = "baekcho",
		kind = "passive",
		name = "백초경",
		icon = "skillHerb",
		minRealm = "mortal",
		summary = "영초에서 얻는 영력 +60%",
	},
	{
		id = "cheongsim",
		kind = "passive",
		name = "청심결",
		icon = "skillCalm",
		minRealm = "dansu",
		summary = "내관 판정 폭 +20%, 실패 손실 절반",
	},
	{
		id = "geumgang",
		kind = "passive",
		name = "금강체",
		icon = "skillVajra",
		minRealm = "yeongi",
		summary = "최대 체력 +40%",
	},
	{
		id = "piroe",
		kind = "passive",
		name = "피뢰결",
		icon = "skillBolt",
		minRealm = "gyeoldan",
		summary = "천겁 낙뢰 피해 -30%",
	},
	{
		id = "cheongi",
		kind = "passive",
		name = "천기감응",
		icon = "skillStar",
		minRealm = "gyeoldan",
		summary = "천겁 낙뢰와 제의 별빛 예고 +0.4초",
	},
} :: { Skill }

-- 효과 수치 (summary 문구와 맞춰 둘 것)
Skills.EFFECT = {
	tonap = 0.3, -- 흡수 배율 +
	baekcho = 0.6, -- 영초 영력 배율 +
	cheongsimBand = 0.2, -- 내관 판정 폭 +
	cheongsimLoss = 0.5, -- 실패 손실 배율
	geumgang = 0.4, -- 최대 체력 배율 +
	piroe = 0.3, -- 낙뢰 피해 감소
	cheongi = 0.4, -- 낙뢰 예고 +초
	formationMult = 2, -- 취령진 안 흡수 배율
	formationRadius = 10, -- 취령진 반경(스터드)
	dashSpeed = 85, -- 경신술 속도
	dashTime = 0.22, -- 경신술 지속(초)
}

Skills.byId = {} :: { [string]: Skill }
Skills.actives = {} :: { Skill }
Skills.passives = {} :: { Skill }
for _, skill in Skills.list do
	Skills.byId[skill.id] = skill
	table.insert(if skill.kind == "active" then Skills.actives else Skills.passives, skill)
end

-- 공법 장착 칸: 처음 1칸, 연기기부터 2칸, 결단기부터 3칸
Skills.SLOT_REALMS = { "mortal", "yeongi", "gyeoldan" }

return Skills
