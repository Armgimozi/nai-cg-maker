--!strict
-- 오라(뽑기 결과) 목록. OneIn = "1/N 확률"의 N.
-- 새 오라를 추가하려면 Auras 표에 한 줄만 넣으면 됩니다(Id는 저장 키이므로 바꾸지 마세요).

export type Tier = {
	Rank: number,
	Name: string,
	MinOneIn: number,
	Color: Color3,
}

export type Aura = {
	Id: string,
	Name: string,
	Subtitle: string,
	OneIn: number,
	Color: Color3,
	Gradient: { Color3 }?,
	Tier: Tier,
}

local Auras = {}

-- 등급: OneIn 이 MinOneIn 이상이면 해당 등급(높은 등급부터 검사)
Auras.Tiers = {
	{ Rank = 1, Name = "일반", MinOneIn = 1, Color = Color3.fromRGB(200, 200, 200) },
	{ Rank = 2, Name = "고급", MinOneIn = 10, Color = Color3.fromRGB(110, 220, 110) },
	{ Rank = 3, Name = "희귀", MinOneIn = 100, Color = Color3.fromRGB(80, 160, 255) },
	{ Rank = 4, Name = "에픽", MinOneIn = 1000, Color = Color3.fromRGB(180, 100, 255) },
	{ Rank = 5, Name = "전설", MinOneIn = 10000, Color = Color3.fromRGB(255, 170, 40) },
	{ Rank = 6, Name = "신화", MinOneIn = 100000, Color = Color3.fromRGB(255, 70, 120) },
	{ Rank = 7, Name = "초월", MinOneIn = 1000000, Color = Color3.fromRGB(255, 255, 255) },
} :: { Tier }

local function tierFor(oneIn: number): Tier
	for i = #Auras.Tiers, 1, -1 do
		local tier = Auras.Tiers[i]
		if oneIn >= tier.MinOneIn then
			return tier
		end
	end
	return Auras.Tiers[1]
end

local rgb = Color3.fromRGB

-- stylua: ignore
local DEFINITIONS = {
	{ "common",    "평범",      "Common",     2,         rgb(190, 190, 190) },
	{ "breeze",    "산들바람",  "Breeze",     4,         rgb(170, 235, 220) },
	{ "dew",       "이슬",      "Dew",        8,         rgb(140, 200, 255) },
	{ "ember",     "불씨",      "Ember",      16,        rgb(255, 130, 70) },
	{ "pebble",    "조약돌",    "Pebble",     32,        rgb(160, 140, 120) },
	{ "frost",     "서리",      "Frost",      64,        rgb(170, 225, 255) },
	{ "bloom",     "꽃망울",    "Bloom",      128,       rgb(255, 150, 200) },
	{ "spark",     "섬광",      "Spark",      256,       rgb(255, 240, 90) },
	{ "tide",      "파도",      "Tide",       512,       rgb(40, 130, 255),  { rgb(40, 130, 255), rgb(120, 230, 255) } },
	{ "moonlight", "달빛",      "Moonlight",  1000,      rgb(210, 220, 255), { rgb(160, 170, 255), rgb(250, 250, 255) } },
	{ "sunflare",  "태양 섬광", "Sunflare",   2500,      rgb(255, 190, 60),  { rgb(255, 120, 30), rgb(255, 230, 90) } },
	{ "aurora",    "오로라",    "Aurora",     5000,      rgb(90, 255, 180),  { rgb(60, 255, 160), rgb(90, 140, 255), rgb(200, 90, 255) } },
	{ "crystal",   "수정",      "Crystal",    10000,     rgb(190, 250, 255), { rgb(140, 240, 255), rgb(255, 255, 255), rgb(200, 160, 255) } },
	{ "inferno",   "업화",      "Inferno",    25000,     rgb(255, 80, 30),   { rgb(120, 0, 0), rgb(255, 80, 20), rgb(255, 210, 60) } },
	{ "glacier",   "빙하",      "Glacier",    50000,     rgb(120, 200, 255), { rgb(20, 80, 200), rgb(140, 220, 255), rgb(255, 255, 255) } },
	{ "stardust",  "별가루",    "Stardust",   100000,    rgb(255, 230, 150), { rgb(40, 30, 90), rgb(255, 230, 150), rgb(40, 30, 90) } },
	{ "glitch",    "글리치",    "ERR_404",    404040,    rgb(0, 255, 90),    { rgb(0, 255, 90), rgb(255, 0, 200), rgb(0, 200, 255) } },
	{ "nebula",    "성운",      "Nebula",     250000,    rgb(200, 90, 255),  { rgb(80, 20, 160), rgb(255, 90, 200), rgb(90, 200, 255) } },
	{ "eclipse",   "일식",      "Eclipse",    500000,    rgb(255, 120, 40),  { rgb(10, 10, 10), rgb(255, 120, 40), rgb(10, 10, 10) } },
	{ "celestial", "천상",      "Celestial",  1000000,   rgb(255, 250, 210), { rgb(255, 255, 255), rgb(255, 220, 120), rgb(160, 220, 255) } },
	{ "void",      "공허",      "The Void",   2500000,   rgb(120, 60, 200),  { rgb(0, 0, 0), rgb(120, 60, 200), rgb(0, 0, 0) } },
	{ "genesis",   "창세",      "Genesis",    10000000,  rgb(255, 255, 255), { rgb(255, 80, 80), rgb(255, 230, 80), rgb(80, 255, 140), rgb(80, 160, 255), rgb(220, 90, 255) } },
	{ "infinity",  "무한",      "∞ Infinity", 100000000, rgb(255, 255, 255), { rgb(255, 255, 255), rgb(0, 0, 0), rgb(255, 255, 255) } },
}

Auras.List = {} :: { Aura }
Auras.ById = {} :: { [string]: Aura }

for _, def in DEFINITIONS do
	local oneIn = def[4] :: number
	local aura: Aura = {
		Id = def[1] :: string,
		Name = def[2] :: string,
		Subtitle = def[3] :: string,
		OneIn = oneIn,
		Color = def[5] :: Color3,
		Gradient = def[6] :: { Color3 }?,
		Tier = tierFor(oneIn),
	}
	assert(Auras.ById[aura.Id] == nil, "중복된 오라 Id: " .. aura.Id)
	table.insert(Auras.List, aura)
	Auras.ById[aura.Id] = aura
end

-- 흔한 것 → 희귀한 것 순서(도감 표시용)
table.sort(Auras.List, function(a, b)
	return a.OneIn < b.OneIn
end)

-- 희귀한 것 → 흔한 것 순서(굴림 판정용)
Auras.RarestFirst = table.clone(Auras.List)
table.sort(Auras.RarestFirst, function(a, b)
	return a.OneIn > b.OneIn
end)

Auras.Common = Auras.List[1]
Auras.tierFor = tierFor

return Auras
