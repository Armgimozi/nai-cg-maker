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
	-- Id, 이름, 영문, N, 대륙, 모양(전용 모형이 없을 때), 주 색, 보조 색, 강조 색, 재질
	{ "clocktower", "홍콩 시계탑", "Clock Tower, Hong Kong", 2, "Asia", "clocktower", rgb(200, 170, 140), rgb(90, 70, 60), rgb(255, 245, 210), M.Brick },
	{ "lighthouse", "희망봉 등대", "Cape Point Lighthouse", 3, "Africa", "lighthouse", rgb(240, 240, 240), rgb(210, 60, 60), rgb(255, 240, 150), M.SmoothPlastic },
	{ "harbourbridge", "하버 브리지", "Sydney Harbour Bridge", 4, "Oceania", "bridge", rgb(150, 155, 160), rgb(95, 100, 110), rgb(255, 225, 150), M.Metal },
	{ "windmill", "풍차 마을", "Kinderdijk Windmills", 5, "Europe", "windmill", rgb(230, 220, 200), rgb(140, 90, 60), rgb(250, 250, 250), M.WoodPlanks },
	{ "dolhareubang", "돌하르방", "Dol Hareubang, Jeju", 6, "Asia", "moai", rgb(80, 80, 85), rgb(70, 130, 60), rgb(255, 160, 40), M.Basalt },
	{ "fountain", "버킹엄 분수", "Buckingham Fountain", 7, "Americas", "fountain", rgb(215, 205, 185), rgb(80, 170, 255), rgb(200, 240, 255), M.Marble },
	{ "washingtonmonument", "워싱턴 기념탑", "Washington Monument", 8, "Americas", "needle", rgb(240, 235, 225), rgb(180, 175, 165), rgb(200, 220, 255), M.Marble },
	{ "moeraki", "모에라키 볼더스", "Moeraki Boulders", 9, "Oceania", "stones", rgb(140, 120, 100), rgb(230, 210, 170), rgb(60, 160, 200), M.Rock },

	{ "gatewayarch", "게이트웨이 아치", "Gateway Arch", 10, "Americas", "arch", rgb(210, 215, 220), rgb(120, 130, 140), rgb(255, 240, 200), M.Metal },
	{ "cheomseongdae", "첨성대", "Cheomseongdae Observatory", 11, "Asia", "lighthouse", rgb(210, 195, 165), rgb(160, 145, 125), rgb(120, 170, 255), M.Granite },
	{ "arc", "개선문", "Arc de Triomphe", 12, "Europe", "arch", rgb(225, 210, 180), rgb(190, 175, 150), rgb(255, 230, 160), M.Limestone },
	{ "boulders", "볼더스 비치 펭귄", "Boulders Beach Penguins", 13, "Africa", "stones", rgb(184, 175, 163), rgb(43, 43, 43), rgb(63, 181, 201), M.Granite },
	{ "flindersst", "플린더스 스트리트 역", "Flinders Street Station", 14, "Oceania", "dome", rgb(230, 180, 80), rgb(180, 80, 60), rgb(80, 160, 140), M.Brick },
	{ "brandenburg", "브란덴부르크 문", "Brandenburg Gate", 15, "Europe", "gate", rgb(216, 203, 174), rgb(154, 140, 112), rgb(78, 143, 110), M.Sandstone },
	{ "dabotap", "다보탑", "Dabotap Pagoda", 16, "Asia", "pagoda", rgb(200, 195, 185), rgb(140, 135, 130), rgb(220, 180, 90), M.Granite },
	{ "brooklynbridge", "브루클린 다리", "Brooklyn Bridge", 18, "Americas", "bridge", rgb(180, 160, 140), rgb(90, 95, 105), rgb(255, 230, 170), M.Granite },
	{ "bigben", "빅벤", "Big Ben", 20, "Europe", "clocktower", rgb(200, 175, 120), rgb(40, 60, 50), rgb(255, 230, 140), M.Sandstone },
	{ "chefchaouen", "셰프샤우엔 파란 마을", "Chefchaouen Blue Town", 22, "Africa", "facade", rgb(74, 144, 217), rgb(244, 247, 251), rgb(232, 116, 59), M.Plaster },
	{ "pancakerocks", "팬케이크 바위", "Punakaiki Pancake Rocks", 24, "Oceania", "seastacks", rgb(180, 170, 150), rgb(120, 105, 90), rgb(40, 160, 200), M.Limestone },
	{ "skytower", "스카이타워", "Sky Tower, Auckland", 25, "Oceania", "needle", rgb(230, 230, 235), rgb(80, 85, 95), rgb(120, 220, 255), M.Concrete },
	{ "trevi", "트레비 분수", "Trevi Fountain", 27, "Europe", "fountain", rgb(237, 230, 216), rgb(79, 176, 224), rgb(255, 208, 96), M.Marble },
	{ "sungnyemun", "숭례문", "Sungnyemun Gate", 30, "Asia", "gate", rgb(170, 160, 150), rgb(60, 120, 90), rgb(200, 50, 45), M.Slate },
	{ "tablemountain", "테이블 마운틴", "Table Mountain", 32, "Africa", "island", rgb(140, 131, 120), rgb(94, 140, 74), rgb(244, 247, 250), M.Rock },
	{ "sugarloaf", "빵산", "Sugarloaf Mountain", 35, "Americas", "seastacks", rgb(140, 140, 130), rgb(70, 150, 60), rgb(255, 200, 60), M.Granite },
	{ "towerbridge", "타워 브리지", "Tower Bridge", 38, "Europe", "bridge", rgb(216, 210, 196), rgb(60, 120, 180), rgb(240, 200, 80), M.Limestone },
	{ "gyeongbokgung", "경복궁", "Gyeongbokgung Palace", 40, "Asia", "temple", rgb(180, 60, 50), rgb(60, 120, 90), rgb(240, 220, 160), M.WoodPlanks },
	{ "cathedralcove", "캐시드럴 코브", "Cathedral Cove", 42, "Oceania", "arch", rgb(240, 230, 210), rgb(40, 170, 200), rgb(120, 180, 80), M.Limestone },
	{ "pisa", "피사의 사탑", "Leaning Tower of Pisa", 45, "Europe", "leaning", rgb(240, 235, 220), rgb(200, 190, 170), rgb(255, 250, 235), M.Marble },
	{ "baobab", "바오밥나무 거리", "Avenue of the Baobabs", 48, "Africa", "tree", rgb(166, 123, 91), rgb(110, 158, 58), rgb(242, 158, 76), M.Wood },
	{ "pragueclock", "프라하 천문시계", "Prague Astronomical Clock", 50, "Europe", "clocktower", rgb(94, 90, 86), rgb(47, 95, 168), rgb(232, 184, 74), M.Slate },
	{ "seongsan", "성산일출봉", "Seongsan Ilchulbong", 55, "Asia", "island", rgb(90, 140, 70), rgb(60, 90, 120), rgb(255, 160, 60), M.Grass },
	{ "goldengate", "금문교", "Golden Gate Bridge", 60, "Americas", "bridge", rgb(192, 54, 44), rgb(140, 155, 165), rgb(255, 210, 140), M.Metal },
	{ "lakehillier", "힐리어 핑크 호수", "Lake Hillier (Pink Lake)", 65, "Oceania", "island", rgb(255, 140, 180), rgb(46, 139, 87), rgb(30, 120, 200), M.SmoothPlastic },
	{ "liberty", "자유의 여신상", "Statue of Liberty", 70, "Americas", "statue", rgb(120, 190, 160), rgb(160, 140, 110), rgb(255, 200, 80), M.Metal },
	{ "venice", "베네치아 리알토 다리", "Rialto Bridge, Venice", 75, "Europe", "bridge", rgb(239, 230, 212), rgb(47, 143, 160), rgb(30, 30, 36), M.Marble },
	{ "chocolatehills", "초콜릿 힐", "Chocolate Hills", 80, "Asia", "stones", rgb(140, 90, 50), rgb(120, 180, 70), rgb(255, 230, 180), M.Grass },
	{ "aitbenhaddou", "아이트벤하두", "Ait Benhaddou", 88, "Africa", "terraces", rgb(201, 138, 90), rgb(143, 90, 58), rgb(94, 158, 74), M.Mud },
	{ "pitons", "피통스 봉우리", "The Pitons", 95, "Americas", "seastacks", rgb(60, 130, 60), rgb(40, 140, 200), rgb(240, 230, 200), M.LeafyGrass },

	{ "santorini", "산토리니", "Santorini (Oia)", 100, "Europe", "dome", rgb(250, 250, 250), rgb(42, 111, 214), rgb(245, 160, 65), M.Plaster },
	{ "hawamahal", "하와마할", "Hawa Mahal (Palace of the Winds)", 105, "Asia", "facade", rgb(240, 140, 120), rgb(210, 100, 75), rgb(255, 230, 200), M.Sandstone },
	{ "waverock", "웨이브 록", "Wave Rock", 110, "Oceania", "wall", rgb(200, 140, 80), rgb(90, 75, 60), rgb(240, 210, 160), M.Granite },
	{ "whitehouse", "백악관", "The White House", 115, "Americas", "facade", rgb(245, 245, 240), rgb(90, 150, 80), rgb(255, 210, 120), M.Marble },
	{ "namsan", "남산타워", "Namsan Tower, Seoul", 120, "Asia", "needle", rgb(235, 235, 240), rgb(60, 60, 70), rgb(90, 200, 255), M.SmoothPlastic },
	{ "deadvlei", "데드블레이", "Deadvlei", 130, "Africa", "tree", rgb(224, 112, 58), rgb(242, 237, 225), rgb(58, 42, 30), M.Sand },
	{ "himeji", "히메지성", "Himeji Castle", 140, "Asia", "pagoda", rgb(245, 245, 240), rgb(90, 100, 115), rgb(220, 190, 110), M.Plaster },
	{ "oldfaithful", "옐로스톤 간헐천", "Old Faithful Geyser", 145, "Americas", "fountain", rgb(200, 180, 140), rgb(240, 250, 255), rgb(110, 200, 230), M.Rock },
	{ "pena", "페나 궁전", "Pena Palace", 155, "Europe", "facade", rgb(240, 194, 60), rgb(192, 80, 74), rgb(108, 140, 200), M.Plaster },
	{ "rockislands", "팔라우 락 아일랜드", "Rock Islands of Palau", 165, "Oceania", "island", rgb(46, 125, 50), rgb(64, 224, 208), rgb(220, 210, 180), M.Grass },
	{ "kinkakuji", "금각사", "Kinkaku-ji (Golden Pavilion)", 175, "Asia", "pagoda", rgb(230, 190, 60), rgb(60, 110, 60), rgb(120, 180, 220), M.Foil },
	{ "niagara", "나이아가라 폭포", "Niagara Falls", 180, "Americas", "fountain", rgb(74, 168, 224), rgb(78, 140, 70), rgb(240, 250, 255), M.SmoothPlastic },
	{ "tsingy", "칭기 드 베마라하", "Tsingy de Bemaraha", 190, "Africa", "seastacks", rgb(142, 142, 134), rgb(90, 90, 85), rgb(79, 143, 58), M.Limestone },
	{ "eiffel", "에펠탑", "Eiffel Tower", 200, "Europe", "lattice", rgb(120, 95, 70), rgb(90, 70, 50), rgb(255, 210, 120), M.Metal },
	{ "bran", "드라큘라 성", "Bran Castle (Dracula's Castle)", 215, "Europe", "facade", rgb(237, 227, 208), rgb(176, 80, 58), rgb(140, 90, 210), M.Plaster },
	{ "pamukkale", "파묵칼레", "Pamukkale Travertines", 225, "Asia", "terraces", rgb(248, 248, 245), rgb(100, 200, 230), rgb(220, 230, 235), M.Salt },
	{ "morainelake", "모레인 호수", "Moraine Lake", 240, "Americas", "island", rgb(60, 180, 200), rgb(90, 110, 130), rgb(255, 255, 255), M.Rock },
	{ "apostles", "12사도 바위", "Twelve Apostles", 250, "Oceania", "seastacks", rgb(210, 160, 110), rgb(50, 140, 200), rgb(240, 230, 210), M.Sandstone },
	{ "hungaryparliament", "헝가리 국회의사당", "Hungarian Parliament Building", 265, "Europe", "dome", rgb(240, 232, 220), rgb(194, 74, 58), rgb(255, 216, 120), M.Limestone },
	{ "templeofheaven", "천단", "Temple of Heaven", 280, "Asia", "pagoda", rgb(30, 80, 180), rgb(200, 50, 30), rgb(250, 245, 235), M.Marble },
	{ "rainbowmountain", "무지개산", "Rainbow Mountain (Vinicunca)", 300, "Americas", "terraces", rgb(220, 90, 90), rgb(240, 200, 80), rgb(80, 180, 160), M.Sandstone },
	{ "lalibela", "랄리벨라 암굴 교회", "Church of St. George, Lalibela", 315, "Africa", "temple", rgb(176, 106, 74), rgb(122, 69, 51), rgb(232, 195, 158), M.Rock },
	{ "duomo", "피렌체 두오모", "Florence Cathedral (Duomo)", 330, "Europe", "dome", rgb(242, 238, 230), rgb(192, 80, 60), rgb(62, 143, 106), M.Marble },
	{ "colosseum", "콜로세움", "Colosseum", 350, "Europe", "ring", rgb(215, 190, 150), rgb(170, 145, 110), rgb(255, 225, 170), M.Limestone },
	{ "fuji", "후지산", "Mount Fuji", 370, "Asia", "pyramid", rgb(70, 110, 170), rgb(245, 248, 255), rgb(255, 140, 170), M.Rock },
	{ "panamacanal", "파나마 운하", "Panama Canal", 390, "Americas", "terraces", rgb(155, 160, 165), rgb(60, 140, 200), rgb(255, 140, 60), M.Concrete },
	{ "borabora", "보라보라 섬", "Bora Bora", 410, "Oceania", "island", rgb(60, 140, 70), rgb(60, 220, 220), rgb(250, 240, 200), M.Grass },
	{ "stbasil", "성 바실리 대성당", "Saint Basil's Cathedral", 435, "Europe", "dome", rgb(210, 60, 60), rgb(46, 158, 106), rgb(242, 199, 68), M.Brick },
	{ "potala", "포탈라궁", "Potala Palace", 460, "Asia", "facade", rgb(250, 250, 245), rgb(160, 40, 50), rgb(255, 200, 60), M.Plaster },
	{ "karnak", "카르나크 신전", "Karnak Temple", 485, "Africa", "temple", rgb(216, 185, 138), rgb(156, 122, 79), rgb(62, 143, 176), M.Sandstone },
	{ "stavechurch", "보르군 목조 교회", "Borgund Stave Church", 515, "Europe", "pagoda", rgb(58, 42, 30), rgb(106, 74, 48), rgb(232, 176, 96), M.Wood },
	{ "arenal", "아레날 화산", "Arenal Volcano", 540, "Americas", "pyramid", rgb(90, 80, 75), rgb(70, 150, 60), rgb(255, 120, 40), M.Basalt },
	{ "seokguram", "석굴암", "Seokguram Grotto", 570, "Asia", "dome", rgb(230, 225, 215), rgb(140, 135, 130), rgb(255, 230, 160), M.Granite },
	{ "tajmahal", "타지마할", "Taj Mahal", 600, "Asia", "dome", rgb(250, 248, 240), rgb(220, 215, 200), rgb(255, 215, 120), M.Marble },
	{ "notredame", "노트르담 대성당", "Notre-Dame de Paris", 640, "Europe", "facade", rgb(216, 205, 181), rgb(110, 124, 134), rgb(60, 120, 216), M.Limestone },
	{ "peritomoreno", "페리토 모레노 빙하", "Perito Moreno Glacier", 675, "Americas", "wall", rgb(210, 240, 255), rgb(100, 180, 230), rgb(255, 255, 255), M.Ice },
	{ "hagiasophia", "아야 소피아", "Hagia Sophia", 715, "Asia", "dome", rgb(220, 180, 160), rgb(140, 140, 145), rgb(255, 210, 100), M.Brick },
	{ "alhambra", "알함브라 궁전", "Alhambra", 750, "Europe", "facade", rgb(200, 104, 62), rgb(140, 90, 58), rgb(79, 163, 107), M.Brick },
	{ "meroe", "메로에 피라미드", "Pyramids of Meroe", 800, "Africa", "pyramid", rgb(181, 101, 58), rgb(122, 75, 46), rgb(240, 201, 135), M.Sandstone },
	{ "angkor", "앙코르와트", "Angkor Wat", 850, "Asia", "temple", rgb(150, 140, 110), rgb(100, 110, 80), rgb(230, 200, 120), M.Sandstone },
	{ "tikal", "티칼 신전", "Tikal Temple I", 900, "Americas", "steps", rgb(180, 170, 150), rgb(60, 140, 70), rgb(230, 220, 190), M.Limestone },
	{ "stpeters", "성 베드로 대성당", "St. Peter's Basilica", 950, "Europe", "dome", rgb(232, 223, 203), rgb(138, 154, 160), rgb(255, 216, 120), M.Limestone },

	{ "milfordsound", "밀퍼드 사운드", "Milford Sound (Mitre Peak)", 1000, "Oceania", "island", rgb(60, 90, 80), rgb(30, 90, 140), rgb(255, 255, 255), M.Slate },
	{ "cappadocia", "카파도키아", "Cappadocia", 1080, "Asia", "stones", rgb(230, 200, 160), rgb(180, 140, 100), rgb(255, 90, 90), M.Sandstone },
	{ "uyuni", "우유니 소금사막", "Salar de Uyuni", 1150, "Americas", "island", rgb(245, 245, 245), rgb(150, 200, 240), rgb(255, 180, 200), M.Salt },
	{ "sphinx", "스핑크스", "Great Sphinx", 1200, "Africa", "sphinx", rgb(215, 180, 120), rgb(190, 155, 100), rgb(80, 120, 200), M.Sandstone },
	{ "neuschwanstein", "노이슈반슈타인 성", "Neuschwanstein Castle", 1300, "Europe", "facade", rgb(242, 239, 232), rgb(74, 111, 165), rgb(255, 216, 120), M.Limestone },
	{ "halong", "하롱베이", "Ha Long Bay", 1400, "Asia", "seastacks", rgb(110, 140, 120), rgb(60, 180, 170), rgb(200, 60, 40), M.Rock },
	{ "kilimanjaro", "킬리만자로산", "Mount Kilimanjaro", 1500, "Africa", "pyramid", rgb(110, 94, 78), rgb(245, 248, 250), rgb(124, 179, 66), M.Rock },
	{ "greatwall", "만리장성", "Great Wall", 1600, "Asia", "wall", rgb(160, 150, 135), rgb(90, 130, 70), rgb(220, 60, 50), M.Cobblestone },
	{ "iguazu", "이과수 폭포", "Iguazu Falls", 1700, "Americas", "terraces", rgb(90, 180, 230), rgb(70, 130, 60), rgb(200, 100, 60), M.SmoothPlastic },
	{ "montsaintmichel", "몽생미셸", "Mont-Saint-Michel", 1800, "Europe", "island", rgb(184, 174, 156), rgb(94, 107, 120), rgb(255, 211, 90), M.Slate },
	{ "victoriafalls", "빅토리아 폭포", "Victoria Falls", 1900, "Africa", "fountain", rgb(79, 179, 232), rgb(94, 90, 85), rgb(244, 251, 255), M.Slate },
	{ "kilauea", "킬라우에아 화산", "Kilauea Volcano", 2000, "Oceania", "island", rgb(60, 50, 50), rgb(255, 90, 30), rgb(255, 200, 60), M.Basalt },
	{ "pyramid", "기자 피라미드", "Pyramids of Giza", 2200, "Africa", "pyramid", rgb(225, 195, 130), rgb(200, 170, 110), rgb(255, 225, 120), M.Sandstone },
	{ "grandcanyon", "그랜드 캐니언", "Grand Canyon", 2400, "Americas", "terraces", rgb(200, 100, 60), rgb(230, 160, 100), rgb(90, 180, 230), M.Sandstone },
	{ "zhangjiajie", "장가계", "Zhangjiajie Stone Pillars", 2500, "Asia", "seastacks", rgb(140, 130, 120), rgb(60, 160, 70), rgb(220, 240, 255), M.Rock },
	{ "segovia", "세고비아 수도교", "Aqueduct of Segovia", 2650, "Europe", "arch", rgb(191, 168, 138), rgb(140, 122, 98), rgb(242, 221, 176), M.Granite },
	{ "reef", "그레이트 배리어 리프", "Great Barrier Reef", 2800, "Oceania", "reef", rgb(255, 120, 150), rgb(40, 170, 210), rgb(255, 215, 90), M.SmoothPlastic },
	{ "chichen", "치첸이트사", "Chichen Itza", 3000, "Americas", "steps", rgb(190, 180, 160), rgb(80, 140, 80), rgb(230, 220, 190), M.Limestone },
	{ "forbiddencity", "자금성", "Forbidden City", 3300, "Asia", "temple", rgb(200, 50, 40), rgb(255, 200, 50), rgb(240, 230, 210), M.Brick },
	{ "serengeti", "세렝게티 초원", "Serengeti", 3500, "Africa", "tree", rgb(217, 181, 74), rgb(107, 142, 35), rgb(242, 140, 40), M.Grass },
	{ "parthenon", "파르테논 신전", "Parthenon", 3750, "Europe", "temple", rgb(240, 232, 216), rgb(200, 184, 154), rgb(111, 160, 216), M.Marble },
	{ "machupicchu", "마추픽추", "Machu Picchu", 4000, "Americas", "terraces", rgb(150, 145, 135), rgb(90, 160, 80), rgb(200, 230, 255), M.Slate },
	{ "amazon", "아마존 열대우림", "Amazon Rainforest", 4300, "Americas", "tree", rgb(46, 139, 60), rgb(140, 110, 60), rgb(255, 90, 60), M.LeafyGrass },
	{ "borobudur", "보로부두르 사원", "Borobudur", 4600, "Asia", "steps", rgb(140, 140, 130), rgb(90, 150, 90), rgb(220, 210, 180), M.Basalt },
	{ "sahara", "사하라 사막", "Sahara Desert", 4900, "Africa", "island", rgb(239, 194, 122), rgb(201, 139, 69), rgb(63, 163, 77), M.Sand },
	{ "meteora", "메테오라 수도원", "Meteora Monasteries", 5200, "Europe", "seastacks", rgb(184, 164, 136), rgb(200, 96, 60), rgb(136, 184, 104), M.Rock },
	{ "petra", "페트라", "Petra", 5500, "Asia", "facade", rgb(215, 130, 100), rgb(180, 100, 75), rgb(255, 200, 150), M.Sandstone },
	{ "galapagos", "갈라파고스 제도", "Galapagos Islands", 5900, "Americas", "island", rgb(78, 140, 70), rgb(40, 160, 200), rgb(140, 122, 90), M.Ground },
	{ "abusimbel", "아부심벨 신전", "Abu Simbel Temples", 6300, "Africa", "facade", rgb(217, 168, 108), rgb(168, 116, 63), rgb(242, 193, 78), M.Sandstone },
	{ "matterhorn", "마터호른", "Matterhorn", 6600, "Europe", "pyramid", rgb(140, 138, 136), rgb(255, 255, 255), rgb(111, 176, 232), M.Rock },
	{ "moai", "모아이 석상", "Moai", 7000, "Oceania", "moai", rgb(110, 105, 100), rgb(80, 150, 90), rgb(200, 60, 50), M.Basalt },
	{ "angelfalls", "앙헬 폭포", "Angel Falls", 7500, "Americas", "fountain", rgb(110, 80, 70), rgb(70, 150, 60), rgb(240, 250, 255), M.Sandstone },
	{ "everest", "에베레스트산", "Mount Everest", 8000, "Asia", "pyramid", rgb(245, 248, 255), rgb(110, 120, 135), rgb(255, 180, 90), M.Snow },
	{ "teotihuacan", "테오티우아칸", "Teotihuacan", 8500, "Americas", "steps", rgb(160, 130, 100), rgb(110, 90, 70), rgb(255, 200, 120), M.Cobblestone },
	{ "stonehenge", "스톤헨지", "Stonehenge", 9000, "Europe", "stones", rgb(150, 150, 145), rgb(90, 150, 80), rgb(200, 220, 255), M.Slate },

	{ "waitomo", "와이토모 반딧불이 동굴", "Waitomo Glowworm Caves", 10000, "Oceania", "arch", rgb(80, 75, 70), rgb(30, 40, 60), rgb(120, 240, 255), M.Rock },
	{ "giantscauseway", "자이언츠 코즈웨이", "Giant's Causeway", 11000, "Europe", "steps", rgb(60, 60, 68), rgb(44, 143, 184), rgb(167, 216, 240), M.Basalt },
	{ "terracotta", "진시황 병마용", "Terracotta Army", 12500, "Asia", "statue", rgb(160, 130, 110), rgb(120, 100, 80), rgb(200, 170, 140), M.Sandstone },
	{ "bluehole", "그레이트 블루홀", "Great Blue Hole", 14000, "Americas", "reef", rgb(20, 40, 90), rgb(70, 200, 220), rgb(240, 230, 200), M.SmoothPlastic },
	{ "alexandria", "알렉산드리아 등대", "Lighthouse of Alexandria", 15000, "Africa", "lighthouse", rgb(245, 240, 225), rgb(220, 200, 160), rgb(255, 170, 60), M.Marble },
	{ "tutankhamun", "투탕카멘의 무덤", "Tomb of Tutankhamun", 17000, "Africa", "statue", rgb(232, 185, 35), rgb(30, 58, 138), rgb(201, 160, 106), M.Foil },
	{ "nazca", "나스카 라인", "Nazca Lines", 20000, "Americas", "ruins", rgb(200, 150, 110), rgb(140, 100, 70), rgb(240, 220, 200), M.Sand },
	{ "yapstone", "얍섬 돌 화폐", "Rai Stones of Yap", 22000, "Oceania", "ring", rgb(190, 180, 160), rgb(140, 130, 112), rgb(80, 160, 80), M.Limestone },
	{ "pompeii", "폼페이", "Pompeii & Mount Vesuvius", 25000, "Europe", "ruins", rgb(201, 178, 142), rgb(106, 90, 80), rgb(255, 106, 42), M.Sandstone },
	{ "babylon", "바빌론 공중정원", "Hanging Gardens of Babylon", 30000, "Asia", "gardens", rgb(210, 180, 130), rgb(60, 170, 70), rgb(120, 200, 255), M.Sandstone },
	{ "richat", "사하라의 눈", "Richat Structure (Eye of the Sahara)", 33000, "Africa", "ring", rgb(217, 138, 78), rgb(138, 90, 60), rgb(242, 208, 138), M.Sand },
	{ "olmechead", "올멕 거대 두상", "Olmec Colossal Head", 36000, "Americas", "moai", rgb(110, 105, 100), rgb(78, 140, 70), rgb(200, 160, 110), M.Basalt },
	{ "artemis", "아르테미스 신전", "Temple of Artemis at Ephesus", 40000, "Asia", "temple", rgb(240, 235, 225), rgb(200, 180, 150), rgb(255, 210, 110), M.Marble },
	{ "nanmadol", "난마돌", "Nan Madol", 45000, "Oceania", "ruins", rgb(70, 70, 78), rgb(40, 150, 175), rgb(110, 200, 110), M.Basalt },
	{ "greatzimbabwe", "그레이트 짐바브웨", "Great Zimbabwe", 50000, "Africa", "ruins", rgb(154, 143, 126), rgb(107, 99, 88), rgb(201, 162, 74), M.Granite },
	{ "rhodes", "로도스 거상", "Colossus of Rhodes", 60000, "Europe", "statue", rgb(190, 130, 60), rgb(230, 225, 210), rgb(255, 140, 40), M.Foil },
	{ "tenochtitlan", "테노치티틀란", "Tenochtitlan", 65000, "Americas", "island", rgb(210, 180, 140), rgb(60, 150, 200), rgb(200, 60, 60), M.Limestone },
	{ "zeus", "올림피아 제우스 상", "Statue of Zeus at Olympia", 72000, "Europe", "statue", rgb(242, 230, 204), rgb(212, 166, 42), rgb(127, 216, 255), M.Marble },
	{ "heracleion", "헤라클레이온 해저 도시", "Sunken City of Heracleion", 80000, "Africa", "ruins", rgb(201, 185, 154), rgb(31, 127, 168), rgb(111, 224, 208), M.Limestone },
	{ "mausoleum", "마우솔로스 영묘", "Mausoleum at Halicarnassus", 90000, "Asia", "temple", rgb(237, 230, 214), rgb(184, 159, 122), rgb(255, 210, 110), M.Marble },

	{ "lochness", "네스호의 네시", "Loch Ness & Nessie", 100000, "Europe", "island", rgb(46, 90, 74), rgb(58, 110, 154), rgb(126, 216, 176), M.Slate },
	{ "babel", "바벨탑", "Tower of Babel", 150000, "Asia", "spiral", rgb(200, 170, 120), rgb(150, 120, 90), rgb(255, 230, 180), M.Sandstone },
	{ "trojanhorse", "트로이 목마", "Trojan Horse", 200000, "Asia", "statue", rgb(160, 120, 75), rgb(110, 80, 50), rgb(255, 220, 140), M.WoodPlanks },
	{ "libraryalex", "알렉산드리아 도서관", "Library of Alexandria", 250000, "Africa", "temple", rgb(242, 237, 225), rgb(201, 163, 107), rgb(255, 179, 71), M.Marble },
	{ "zealandia", "질랜디아", "Zealandia (Sunken Continent)", 300000, "Oceania", "island", rgb(60, 140, 110), rgb(10, 60, 120), rgb(120, 255, 230), M.Glass },
	{ "atlantis", "아틀란티스", "Atlantis", 400000, "Europe", "island", rgb(230, 240, 250), rgb(40, 120, 200), rgb(90, 255, 230), M.Marble },
	{ "labyrinth", "미노타우로스의 미궁", "Labyrinth of the Minotaur", 500000, "Europe", "ruins", rgb(216, 200, 168), rgb(184, 72, 58), rgb(255, 208, 106), M.Sandstone },
	{ "hwangnyongsa", "황룡사 9층 목탑", "Hwangnyongsa Nine-Story Pagoda", 650000, "Asia", "pagoda", rgb(180, 70, 60), rgb(60, 110, 90), rgb(255, 210, 90), M.WoodPlanks },
	{ "eldorado", "엘도라도", "El Dorado", 800000, "Americas", "steps", rgb(255, 200, 60), rgb(200, 140, 30), rgb(255, 250, 180), M.Foil },

	{ "fountainofyouth", "젊음의 샘", "Fountain of Youth", 1000000, "Americas", "fountain", rgb(230, 230, 220), rgb(80, 220, 200), rgb(255, 230, 120), M.Marble },
	{ "yonggung", "용궁", "Dragon King's Palace", 2000000, "Asia", "pagoda", rgb(230, 70, 70), rgb(40, 130, 150), rgb(120, 255, 220), M.Glass },
	{ "mu", "무 대륙", "Lost Continent of Mu", 3000000, "Oceania", "island", rgb(175, 165, 125), rgb(30, 110, 170), rgb(255, 210, 90), M.Slate },
	{ "skyisland", "사하라 신기루 성", "Mirage Citadel of the Sahara", 5000000, "Africa", "skyisland", rgb(235, 200, 130), rgb(190, 140, 80), rgb(170, 240, 255), M.Sand },
	{ "shangrila", "샹그릴라", "Shangri-La", 10000000, "Asia", "pagoda", rgb(250, 250, 250), rgb(255, 200, 70), rgb(255, 240, 180), M.Marble },
	{ "worldtree", "세계수", "World Tree", 40000000, "Europe", "tree", rgb(120, 90, 60), rgb(90, 220, 120), rgb(255, 255, 200), M.Wood },
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
	Primary = rgb(30, 95, 200), -- 바다
	Secondary = rgb(96, 190, 80), -- 초록 땅(숲·사막·눈 색은 Models 의 globe 가 정함)
	Accent = rgb(255, 255, 255),
	Material = M.SmoothPlastic,
	Tier = Landmarks.Tiers[1],
} :: Landmark
Landmarks.tierFor = tierFor

return Landmarks
