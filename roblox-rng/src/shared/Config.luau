--!strict
-- 게임 전체 밸런스/설정 값. 숫자만 바꿔서 난이도를 조절할 수 있습니다.

local Config = {
	-- 굴리기(지구본 돌리기) ----------------------------------------------
	ROLL_COOLDOWN = 1.2, -- 굴리기 사이 최소 간격(초). 서버가 강제합니다.
	COOLDOWN_TOLERANCE = 0.15, -- 네트워크 지연을 감안한 허용 오차(초)
	BASE_LUCK = 1,

	-- 1/N 이상 희귀한 명소를 발견하면 서버 전체에 "뉴스 속보"
	ANNOUNCE_ONE_IN = 1000,
	-- 1/N 이상이면 광장 하늘에 거대한 홀로그램까지 띄움
	HOLOGRAM_ONE_IN = 10000,

	-- 새 명소를 처음 발견했을 때 보너스 코인 = ceil(DISCOVERY_BONUS_MULT * N ^ 0.5)
	DISCOVERY_BONUS_MULT = 5,

	-- 관광 공원(타이쿤) ------------------------------------------------------
	BASE_SLOTS = 6, -- 처음 전시 칸 수 (공원 확장 업그레이드로 늘어남)
	-- 등급(Rank 1~7)별 명소 1개의 초당 관광 수입
	TIER_INCOME = { 1, 2, 5, 12, 30, 80, 250 },
	-- 같은 명소를 여러 번 발견하면 별(★)이 오름. 별 k 개가 되는 누적 발견 수
	STAR_THRESHOLDS = { 1, 3, 10, 30, 100 },
	STAR_INCOME_BONUS = 0.5, -- 별 1개 추가마다 그 명소 수입 +50%

	-- 여권 도장: 한 대륙에서 이 등급(Rank) 이하의 명소를 모두 발견하면 영구 행운 보너스(대륙마다 더해짐).
	-- 5 = 불가사의까지. 그보다 희귀한 전설급은 도장에 필요 없는 보너스 수집.
	STAMP_MAX_RANK = 5,
	REGION_LUCK_BONUS = 0.25,

	-- 업그레이드(영구). 가격 = floor(BasePrice * Growth ^ 현재레벨)
	Upgrades = {
		{
			Id = "Globe",
			Name = "지구본",
			Emoji = "🌐",
			Description = "행운 +10%",
			BasePrice = 400,
			Growth = 1.7,
			MaxLevel = 20,
			PerLevel = 0.10,
		},
		{
			Id = "Agency",
			Name = "여행사",
			Emoji = "✈️",
			Description = "굴림 간격 -5%",
			BasePrice = 300,
			Growth = 1.8,
			MaxLevel = 10,
			PerLevel = 0.05,
		},
		{
			Id = "Park",
			Name = "공원 확장",
			Emoji = "🏞️",
			Description = "전시 칸 +3",
			BasePrice = 250,
			Growth = 2.0,
			MaxLevel = 9, -- 6 + 3*9 = 33칸 = 전체 명소 수
			PerLevel = 3,
		},
		{
			Id = "Ticket",
			Name = "입장료",
			Emoji = "🎟️",
			Description = "관광 수입 +20%",
			BasePrice = 500,
			Growth = 1.9,
			MaxLevel = 15,
			PerLevel = 0.20,
		},
	},

	-- 저장 ---------------------------------------------------------------
	DATASTORE_NAME = "LandmarkRNG_v1",
	AUTOSAVE_INTERVAL = 120,
}

return Config
