--!strict
-- 명소(뽑기 결과) 목록. OneIn = "1/N 확률"의 N.
-- 새 명소를 추가하려면 DEFINITIONS 에 한 줄만 넣으면 됩니다(Id는 저장 키이므로 게시 후엔 바꾸지 마세요).
-- 모형: Shape 이름으로 Models.luau 가 코드로 임시 모형을 만듭니다.
--       ReplicatedStorage.LandmarkModels 폴더에 Id 와 같은 이름의 Model 을 넣으면 그 모형(예: AI 메쉬)을 대신 씁니다.

export type Tier = {
	Rank: number,
	Name: string,
	MinOneIn: number,
	Color: Color3,
}

export type Region = {
	Id: string,
	Name: string,
	Emoji: string,
	Color: Color3,
}

export type Landmark = {
	Id: string,
	Name: string,
	Subtitle: string, -- 영문 이름
	OneIn: number,
	Region: string, -- Region.Id (대륙)
	Shape: string, -- Models.luau 의 임시 모형 종류
	Primary: Color3, -- 주 색
	Secondary: Color3, -- 보조 색
	Accent: Color3, -- 강조 색(빛/장식)
	Material: Enum.Material, -- 주 재질
	Tier: Tier,
}

local Landmarks = {}

-- 등급: OneIn 이 MinOneIn 이상이면 해당 등급(높은 등급부터 검사)
Landmarks.Tiers = {
	{ Rank = 1, Name = "일반 명소", MinOneIn = 1, Color = Color3.fromRGB(190, 200, 210) },
	{ Rank = 2, Name = "도시 명소", MinOneIn = 10, Color = Color3.fromRGB(110, 215, 120) },
	{ Rank = 3, Name = "국가 명소", MinOneIn = 100, Color = Color3.fromRGB(80, 165, 255) },
	{ Rank = 4, Name = "세계 명소", MinOneIn = 1000, Color = Color3.fromRGB(185, 110, 255) },
	{ Rank = 5, Name = "불가사의", MinOneIn = 10000, Color = Color3.fromRGB(255, 175, 45) },
	{ Rank = 6, Name = "잃어버린 유산", MinOneIn = 100000, Color = Color3.fromRGB(255, 85, 110) },
	{ Rank = 7, Name = "전설", MinOneIn = 1000000, Color = Color3.fromRGB(120, 255, 235) },
} :: { Tier }

-- 여권에 나오는 대륙(도장 대상). 순서 = 여권/지구본 연출 순서
Landmarks.Regions = {
	{ Id = "Asia", Name = "아시아", Emoji = "🏯", Color = Color3.fromRGB(255, 120, 120) },
	{ Id = "Europe", Name = "유럽", Emoji = "🏰", Color = Color3.fromRGB(110, 150, 255) },
	{ Id = "Africa", Name = "아프리카", Emoji = "🐪", Color = Color3.fromRGB(240, 190, 90) },
	{ Id = "Americas", Name = "아메리카", Emoji = "🗽", Color = Color3.fromRGB(90, 210, 150) },
	{ Id = "Oceania", Name = "오세아니아", Emoji = "🏝️", Color = Color3.fromRGB(70, 200, 235) },
} :: { Region }

Landmarks.RegionById = {} :: { [string]: Region }
for _, region in Landmarks.Regions do
	Landmarks.RegionById[region.Id] = region
end

local function tierFor(oneIn: number): Tier
	for i = #Landmarks.Tiers, 1, -1 do
		local tier = Landmarks.Tiers[i]
		if oneIn >= tier.MinOneIn then
			return tier
		end
	end
	return Landmarks.Tiers[1]
end

local rgb = Color3.fromRGB
local M = Enum.Material

-- stylua: ignore
local DEFINITIONS = {
	-- Id,           이름,               영문,                          N,         지역,       모형,         주 색,               보조 색,              강조 색,              재질
	{ "clocktower",  "홍콩 시계탑",      "Clock Tower, Hong Kong",      2,         "Asia",     "clocktower", rgb(200, 170, 140), rgb(90, 70, 60),    rgb(255, 245, 210), M.Brick },
	{ "lighthouse",  "희망봉 등대",      "Cape Point Lighthouse",       3,         "Africa",   "lighthouse", rgb(240, 240, 240), rgb(210, 60, 60),   rgb(255, 240, 150), M.SmoothPlastic },
	{ "harbourbridge", "하버 브리지",    "Sydney Harbour Bridge",       4,         "Oceania",  "bridge",     rgb(150, 155, 160), rgb(95, 100, 110),  rgb(255, 225, 150), M.Metal },
	{ "windmill",    "풍차 마을",        "Kinderdijk Windmills",        5,         "Europe",   "windmill",   rgb(230, 220, 200), rgb(140, 90, 60),   rgb(250, 250, 250), M.WoodPlanks },
	{ "fountain",    "버킹엄 분수",      "Buckingham Fountain",         7,         "Americas", "fountain",   rgb(215, 205, 185), rgb(80, 170, 255),  rgb(200, 240, 255), M.Marble },

	{ "arc",         "개선문",           "Arc de Triomphe",             12,        "Europe",   "arch",       rgb(225, 210, 180), rgb(190, 175, 150), rgb(255, 230, 160), M.Limestone },
	{ "bigben",      "빅벤",             "Big Ben",                     20,        "Europe",   "clocktower", rgb(200, 175, 120), rgb(40, 60, 50),    rgb(255, 230, 140), M.Sandstone },
	{ "skytower",    "스카이타워",       "Sky Tower, Auckland",         25,        "Oceania",  "needle",     rgb(230, 230, 235), rgb(80, 85, 95),    rgb(120, 220, 255), M.Concrete },
	{ "sungnyemun",  "숭례문",           "Sungnyemun Gate",             30,        "Asia",     "gate",       rgb(170, 160, 150), rgb(60, 120, 90),   rgb(200, 50, 45),   M.Slate },
	{ "pisa",        "피사의 사탑",      "Leaning Tower of Pisa",       45,        "Europe",   "leaning",    rgb(240, 235, 220), rgb(200, 190, 170), rgb(255, 250, 235), M.Marble },
	{ "liberty",     "자유의 여신상",    "Statue of Liberty",           70,        "Americas", "statue",     rgb(120, 190, 160), rgb(160, 140, 110), rgb(255, 200, 80),  M.Metal },

	{ "namsan",      "남산타워",         "N Seoul Tower",               120,       "Asia",     "needle",     rgb(235, 235, 240), rgb(60, 60, 70),    rgb(90, 200, 255),  M.SmoothPlastic },
	{ "eiffel",      "에펠탑",           "Eiffel Tower",                200,       "Europe",   "lattice",    rgb(120, 95, 70),   rgb(90, 70, 50),    rgb(255, 210, 120), M.Metal },
	{ "apostles",    "12사도 바위",      "Twelve Apostles",             250,       "Oceania",  "seastacks",  rgb(210, 160, 110), rgb(50, 140, 200),  rgb(240, 230, 210), M.Sandstone },
	{ "colosseum",   "콜로세움",         "Colosseum",                   350,       "Europe",   "ring",       rgb(215, 190, 150), rgb(170, 145, 110), rgb(255, 225, 170), M.Limestone },
	{ "tajmahal",    "타지마할",         "Taj Mahal",                   600,       "Asia",     "dome",       rgb(250, 248, 240), rgb(220, 215, 200), rgb(255, 215, 120), M.Marble },
	{ "angkor",      "앙코르와트",       "Angkor Wat",                  850,       "Asia",     "temple",     rgb(150, 140, 110), rgb(100, 110, 80),  rgb(230, 200, 120), M.Sandstone },

	{ "sphinx",      "스핑크스",         "Great Sphinx",                1200,      "Africa",   "sphinx",     rgb(215, 180, 120), rgb(190, 155, 100), rgb(80, 120, 200),  M.Sandstone },
	{ "greatwall",   "만리장성",         "Great Wall",                  1600,      "Asia",     "wall",       rgb(160, 150, 135), rgb(90, 130, 70),   rgb(220, 60, 50),   M.Cobblestone },
	{ "pyramid",     "기자 피라미드",    "Pyramids of Giza",            2200,      "Africa",   "pyramid",    rgb(225, 195, 130), rgb(200, 170, 110), rgb(255, 225, 120), M.Sandstone },
	{ "reef",        "그레이트 배리어 리프", "Great Barrier Reef",      2800,      "Oceania",  "reef",       rgb(255, 120, 150), rgb(40, 170, 210),  rgb(255, 215, 90),  M.SmoothPlastic },
	{ "chichen",     "치첸이트사",       "Chichen Itza",                3000,      "Americas", "steps",      rgb(190, 180, 160), rgb(80, 140, 80),   rgb(230, 220, 190), M.Limestone },
	{ "machupicchu", "마추픽추",         "Machu Picchu",                4000,      "Americas", "terraces",   rgb(150, 145, 135), rgb(90, 160, 80),   rgb(200, 230, 255), M.Slate },
	{ "petra",       "페트라",           "Petra",                       5500,      "Asia",     "facade",     rgb(215, 130, 100), rgb(180, 100, 75),  rgb(255, 200, 150), M.Sandstone },
	{ "moai",        "모아이 석상",      "Moai",                        7000,      "Oceania",  "moai",       rgb(110, 105, 100), rgb(80, 150, 90),   rgb(200, 60, 50),   M.Basalt },
	{ "stonehenge",  "스톤헨지",         "Stonehenge",                  9000,      "Europe",   "stones",     rgb(150, 150, 145), rgb(90, 150, 80),   rgb(200, 220, 255), M.Slate },

	{ "alexandria",  "알렉산드리아 등대", "Lighthouse of Alexandria",   15000,     "Africa",   "lighthouse", rgb(245, 240, 225), rgb(220, 200, 160), rgb(255, 170, 60),  M.Marble },
	{ "babylon",     "바빌론 공중정원",  "Hanging Gardens of Babylon",  30000,     "Asia",     "gardens",    rgb(210, 180, 130), rgb(60, 170, 70),   rgb(120, 200, 255), M.Sandstone },
	{ "nanmadol",    "난마돌",           "Nan Madol",                   45000,     "Oceania",  "ruins",      rgb(70, 70, 78),    rgb(40, 150, 175),  rgb(110, 200, 110), M.Basalt },
	{ "rhodes",      "로도스 거상",      "Colossus of Rhodes",          60000,     "Europe",   "statue",     rgb(190, 130, 60),  rgb(230, 225, 210), rgb(255, 140, 40),  M.Foil },

	{ "babel",       "바벨탑",           "Tower of Babel",              150000,    "Asia",     "spiral",     rgb(200, 170, 120), rgb(150, 120, 90),  rgb(255, 230, 180), M.Sandstone },
	{ "atlantis",    "아틀란티스",       "Atlantis",                    400000,    "Europe",   "island",     rgb(230, 240, 250), rgb(40, 120, 200),  rgb(90, 255, 230),  M.Marble },
	{ "eldorado",    "엘도라도",         "El Dorado",                   800000,    "Americas", "steps",      rgb(255, 200, 60),  rgb(200, 140, 30),  rgb(255, 250, 180), M.Foil },

	{ "mu",          "무 대륙",          "Lost Continent of Mu",        3000000,   "Oceania",  "island",     rgb(175, 165, 125), rgb(30, 110, 170),  rgb(255, 210, 90),  M.Slate },
	{ "yonggung",    "용궁",             "Dragon King's Palace",        2000000,   "Asia",     "pagoda",     rgb(230, 70, 70),   rgb(40, 130, 150),  rgb(120, 255, 220), M.Glass },
	{ "skyisland",   "사하라 신기루 성", "Mirage Citadel of the Sahara", 5000000,  "Africa",   "skyisland",  rgb(235, 200, 130), rgb(190, 140, 80),  rgb(170, 240, 255), M.Sand },
	{ "shangrila",   "샹그릴라",         "Shangri-La",                  10000000,  "Asia",     "pagoda",     rgb(250, 250, 250), rgb(255, 200, 70),  rgb(255, 240, 180), M.Marble },
	{ "worldtree",   "세계수",           "World Tree",                  40000000,  "Europe",   "tree",       rgb(120, 90, 60),   rgb(90, 220, 120),  rgb(255, 255, 200), M.Wood },
}

Landmarks.List = {} :: { Landmark }
Landmarks.ById = {} :: { [string]: Landmark }

for _, def in DEFINITIONS do
	local oneIn = def[4] :: number
	local landmark: Landmark = {
		Id = def[1] :: string,
		Name = def[2] :: string,
		Subtitle = def[3] :: string,
		OneIn = oneIn,
		Region = def[5] :: string,
		Shape = def[6] :: string,
		Primary = def[7] :: Color3,
		Secondary = def[8] :: Color3,
		Accent = def[9] :: Color3,
		Material = def[10] :: Enum.Material,
		Tier = tierFor(oneIn),
	}
	assert(Landmarks.ById[landmark.Id] == nil, "중복된 명소 Id: " .. landmark.Id)
	assert(Landmarks.RegionById[landmark.Region], "없는 지역: " .. landmark.Region)
	table.insert(Landmarks.List, landmark)
	Landmarks.ById[landmark.Id] = landmark
end

-- 흔한 것 → 희귀한 것 순서(여권/표시용)
table.sort(Landmarks.List, function(a, b)
	return a.OneIn < b.OneIn
end)

-- 희귀한 것 → 흔한 것 순서(굴림 판정용)
Landmarks.RarestFirst = table.clone(Landmarks.List)
table.sort(Landmarks.RarestFirst, function(a, b)
	return a.OneIn > b.OneIn
end)

-- 지역별 목록(흔한 것 → 희귀한 것)
Landmarks.ByRegion = {} :: { [string]: { Landmark } }
for _, region in Landmarks.Regions do
	Landmarks.ByRegion[region.Id] = {}
end
for _, landmark in Landmarks.List do
	table.insert(Landmarks.ByRegion[landmark.Region], landmark)
end

Landmarks.Common = Landmarks.List[1]

-- 장식용 지구본(뽑기·수집 대상 아님): 광장의 거대 지구본, 굴림 연출의 도는 지구본에 씀.
-- Models.create 에 명소처럼 넘길 수 있게 같은 모양의 표. LandmarkModels 폴더에 "globe" 로 교체 가능.
Landmarks.Globe = {
	Id = "globe",
	Name = "지구본",
	Subtitle = "Globe",
	OneIn = 0,
	Region = Landmarks.Regions[1].Id,
	Shape = "globe",
	Primary = rgb(40, 110, 220),
	Secondary = rgb(70, 190, 90),
	Accent = rgb(255, 255, 255),
	Material = M.SmoothPlastic,
	Tier = Landmarks.Tiers[1],
} :: Landmark
Landmarks.tierFor = tierFor

return Landmarks
