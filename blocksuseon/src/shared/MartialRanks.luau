-- 무공 경지. 목인장에서 수련해 오른다.
-- 수선과는 별개의 체계로, 체력과 이동 속도(경공)를 올려 천겁을 버티고 피하는 데 쓰인다.

export type Rank = {
	name: string,
	hanja: string?,
	exp: number, -- 이 경지에 오르는 데 필요한 누적 수련치
	hpMult: number,
	speed: number, -- 기본 이동 속도에 더하는 값
}

local MartialRanks = {}

MartialRanks.list = {
	{ name = "무공 없음", exp = 0, hpMult = 1, speed = 0 },
	{ name = "삼류", hanja = "三流", exp = 20, hpMult = 1.1, speed = 1 },
	{ name = "이류", hanja = "二流", exp = 80, hpMult = 1.25, speed = 2 },
	{ name = "일류", hanja = "一流", exp = 250, hpMult = 1.45, speed = 3 },
	{ name = "절정", hanja = "絶頂", exp = 700, hpMult = 1.75, speed = 5 },
	{ name = "삼화취정", hanja = "三花聚頂", exp = 2000, hpMult = 2.1, speed = 7 },
	{ name = "오기조원", hanja = "五氣朝元", exp = 5000, hpMult = 2.6, speed = 9 },
} :: { Rank }

function MartialRanks.indexFor(exp: number): number
	local index = 1
	for i, rank in MartialRanks.list do
		if exp >= rank.exp then
			index = i
		end
	end
	return index
end

function MartialRanks.get(exp: number): Rank
	return MartialRanks.list[MartialRanks.indexFor(exp)]
end

return MartialRanks
