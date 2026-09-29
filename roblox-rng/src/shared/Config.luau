--!strict
-- 게임 전체 밸런스/설정 값. 숫자만 바꿔서 난이도를 조절할 수 있습니다.

-- n 번째 환생 조건(코인 + 이번 판에 보유해야 하는 명소 Id)
export type RebirthStep = {
	Coins: number,
	Landmarks: { string },
}

-- 게임패스(한 번 사면 영구). PassId 가 0 이면 비활성(화면에 안 나옴)
export type GamePass = {
	Id: string,
	Name: string,
	PassId: number,
	LuckMult: number?, -- 행운 배율
	CooldownMult: number?, -- 굴림 간격 배율
	IncomeMult: number?, -- 관광 수입 배율
}

-- 개발자 상품(여러 번 구매). ProductId 가 0 이면 비활성(화면에 안 나옴)
export type Product = {
	Id: string,
	Name: string,
	ProductId: number,
	Seconds: number?, -- 시간 부스트 길이(초). 같은 부스트를 또 사면 시간이 더해짐
	LuckMult: number?, -- 부스트 중 행운 배율
	ServerWide: boolean?, -- true 면 서버 전체 부스트(저장 안 하는 서버 변수), 아니면 개인 부스트(Data.Boosts)
	IncomeSeconds: number?, -- 코인 팩: 초당 관광 수입 × 이 초만큼 코인
	MinCoins: number?, -- 코인 팩: 최소 코인
}

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
	PARK_GRID = 6, -- 공원 전시 격자 한 변의 칸 수(6×6 = 최대 36칸). 명소가 더 많으면 희귀한 순서로 36개만 전시
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
			MaxLevel = 10, -- 6 + 3*10 = 36칸 = 격자(6×6) 가득
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

	-- 환생 ---------------------------------------------------------------
	-- REBIRTHS[n] = n 번째 환생 조건. 요구 명소는 이번 판에 보유하고 있어야 함(환생하면 보유 명소는 비워짐).
	-- 목록을 넘어서면 마지막 단계의 명소 + 코인 × REBIRTH_COIN_GROWTH 씩 증가.
	-- (명소 목록이 늘어나도 그대로 쓸 수 있는 명소 Id 만 사용)
	REBIRTHS = {
		{ Coins = 5000, Landmarks = { "eiffel", "liberty" } },
		{ Coins = 30000, Landmarks = { "colosseum", "tajmahal" } },
		{ Coins = 150000, Landmarks = { "sphinx", "greatwall" } },
		{ Coins = 600000, Landmarks = { "pyramid", "chichen", "machupicchu" } },
		{ Coins = 2500000, Landmarks = { "petra", "moai", "stonehenge" } },
		{ Coins = 10000000, Landmarks = { "alexandria", "reef" } },
		{ Coins = 40000000, Landmarks = { "babylon", "rhodes", "nanmadol" } },
		{ Coins = 160000000, Landmarks = { "babel" } },
	} :: { RebirthStep },
	REBIRTH_COIN_GROWTH = 4,
	REBIRTH_LUCK_BONUS = 0.2, -- 환생 1회마다 행운 +20% (행운 × (1 + 0.2 × 환생 수))
	REBIRTH_INCOME_BONUS = 0.5, -- 환생 1회마다 관광 수입 +50% (수입 × (1 + 0.5 × 환생 수))

	-- 유료 상품(Robux) ----------------------------------------------------
	-- Creator Hub 에서 만든 뒤 PassId / ProductId 를 넣으세요. 0 이면 그 상품은 비활성(화면에 안 나옴).
	-- 추천 가격(Robux): LuckVIP 399, FastRoll 199, DoubleIncome 299
	GamePasses = {
		{ Id = "LuckVIP", Name = "행운 VIP", PassId = 0, LuckMult = 2 },
		{ Id = "FastRoll", Name = "빠른 굴림", PassId = 0, CooldownMult = 0.7 },
		{ Id = "DoubleIncome", Name = "수입 2배", PassId = 0, IncomeMult = 2 },
	} :: { GamePass },
	-- 추천 가격(Robux): LuckBoost 49, ServerLuck 99, CoinPack 79
	Products = {
		{ Id = "LuckBoost", Name = "행운 부스트", ProductId = 0, Seconds = 900, LuckMult = 2 },
		{ Id = "ServerLuck", Name = "서버 행운", ProductId = 0, Seconds = 900, LuckMult = 2, ServerWide = true },
		{ Id = "CoinPack", Name = "코인 팩", ProductId = 0, IncomeSeconds = 1800, MinCoins = 1000 },
	} :: { Product },
	MAX_BOOST_SECONDS = 3 * 60 * 60, -- 시간 부스트(개인·서버)는 남은 시간이 이 이상 쌓이지 않음
	MAX_RECEIPTS = 50, -- 중복 지급 방지용으로 기억하는 최근 구매 영수증(PurchaseId) 수

	-- 저장 ---------------------------------------------------------------
	DATASTORE_NAME = "LandmarkRNG_v1",
	AUTOSAVE_INTERVAL = 120,
}

return Config
