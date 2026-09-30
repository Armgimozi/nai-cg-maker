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
	Price: number?, -- Robux 가격(상점 버튼에 먼저 보여 줌. 클라이언트가 GetProductInfo 로 실제 가격을 받으면 그 값으로 바꿈)
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
	Price: number?, -- Robux 가격(게임패스와 같음)
}

local Config = {
	-- 굴리기(지구본 돌리기) ----------------------------------------------
	ROLL_COOLDOWN = 1.2, -- 굴리기 사이 최소 간격(초). 서버가 강제합니다.
	-- 네트워크 지연을 감안한 허용 오차(초): 이만큼 일찍 닿아도 받음. 늦게 닿은 요청 뒤에는 2배까지(RollLogic.cooldownGate)
	COOLDOWN_TOLERANCE = 0.15,
	BASE_LUCK = 1,
	-- 자동 굴림(AUTO) 중 이미 발견한 명소는 지구본을 돌리지 않고 결과 카드만 퐁(빠른 결과, 새 발견·수동 굴림은 원래 연출).
	-- 연출을 기다리지 않아서 AUTO 는 굴림 간격대로 굴림 → 여행사(최대 -50%)·빠른 굴림(×0.7)이 AUTO 도 빠르게 함
	-- (후반 시간당 3,000 / 4,286 / 6,000 / 8,571번 = 없음 / 빠른 굴림 / 여행사 최대 / 둘 다 — 클라이언트가 원래 보낼 시각을
	-- 기준으로 해서 프레임 늦음이 쌓이지 않아 평균이 굴림 간격 그대로. balance/sim_results.md 9번).
	-- false 면 모든 결과를 등급 길이의 연출로(연출이 굴림 간격보다 길어 AUTO 가 느려짐)
	AUTO_QUICK_REVEAL = true,

	-- 1/N 이상 희귀한 명소를 발견하면 서버 전체에 "뉴스 속보"(샹그릴라·세계수 = 후반 1인 시간당 약 0.1~0.3번. AUTO 가 굴림
	-- 간격대로 빨라져서 1억(사하라 신기루 성 포함)이면 0.5~1.4번 — balance/sim_results.md 9번)
	ANNOUNCE_ONE_IN = 375000000,
	-- 1/N 이상이면 광장 하늘에 거대한 홀로그램까지 띄움(샹그릴라·세계수 — 속보와 같음)
	HOLOGRAM_ONE_IN = 375000000,

	-- 새 명소를 처음 발견했을 때 보너스 코인 = ceil(DISCOVERY_BONUS_MULT * N ^ 0.5)
	DISCOVERY_BONUS_MULT = 5,

	-- 관광 공원(타이쿤) ------------------------------------------------------
	BASE_SLOTS = 6, -- 처음 전시 칸 수 (공원 확장 업그레이드로 늘어남)
	PARK_GRID = 6, -- 공원 전시 격자 한 변의 칸 수(6×6 = 최대 36칸). 명소가 더 많으면 희귀한 순서로 36개만 전시
	-- 등급(Rank 1~7)별 명소 1개의 초당 관광 수입
	TIER_INCOME = { 1, 2, 5, 12, 35, 120, 500 },
	-- 별(★): 가챠 중복처럼 같은 명소를 또 뽑을 때마다 +1. 처음 발견 = 별 0, 2번째 = ★1 … 6번째 = ★5(최대).
	-- STAR_THRESHOLDS[k] = 별 k 개가 되는 이번 판 발견 수(보유 수). 별 수는 보유 수로 계산하고 저장하지 않음
	STAR_THRESHOLDS = { 2, 3, 4, 5, 6 },
	STAR_INCOME_BONUS = 0.3, -- 별 1개마다 그 명소 수입 +30% (★5 = ×2.5)

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
	-- 환생은 MAX_REBIRTHS 번까지(목록 길이와 같음). 다 하면 더 환생할 수 없음.
	-- (명소 목록이 늘어나도 그대로 쓸 수 있는 명소 Id 만 사용)
	-- 요구 명소는 그 판에 부스트를 다 켠 최대 행운보다 희귀해야 함(행운 ≥ N 이면 굴림에서 못 나옴 — 테스트가 확인).
	-- 진행 목표(무료, AUTO, 온라인 시간): 첫 환생 약 17분, 3번째 2.8시간, 5번째 약 26시간, 10번째 약 23일
	-- (유료 게임패스 3종 + 하루 부스트 1번 = 8분 · 78분 · 12시간 · 11일 — balance/sim_results.md 9번)
	REBIRTHS = {
		{ Coins = 400000, Landmarks = { "eiffel", "liberty" } },
		{ Coins = 4000000, Landmarks = { "pyramid", "chichen" } },
		{ Coins = 60000000, Landmarks = { "moai", "stonehenge", "alexandria" } },
		{ Coins = 500000000, Landmarks = { "babylon", "artemis", "rhodes" } },
		{ Coins = 3000000000, Landmarks = { "zeus", "mausoleum", "trojanhorse" } },
		{ Coins = 9000000000, Landmarks = { "atlantis", "labyrinth" } },
		{ Coins = 18000000000, Landmarks = { "hwangnyongsa", "eldorado" } },
		{ Coins = 40000000000, Landmarks = { "fountainofyouth", "yonggung" } },
		{ Coins = 90000000000, Landmarks = { "mu", "zealandia" } },
		{ Coins = 200000000000, Landmarks = { "skyisland" } },
	} :: { RebirthStep },
	MAX_REBIRTHS = 10, -- 환생 상한(= REBIRTHS 단계 수). 보너스도 여기서 멈춤
	REBIRTH_LUCK_MULT = 2, -- 환생 1회마다 행운 ×2 (행운 × 2^환생 수: 10번 = ×1,024)
	REBIRTH_INCOME_BONUS = 0.5, -- 환생 1회마다 관광 수입 +50% (수입 × (1 + 0.5 × 환생 수))

	-- 유료 상품(Robux) ----------------------------------------------------
	-- 2026-09-30 Open Cloud 로 등록한 번호(아이콘: art/products). 0 이면 그 상품은 비활성(화면에 안 나옴).
	-- Price 는 Creator Hub 에 넣은 Robux 가격과 같게 유지(상점 버튼에 먼저 보이는 값. 실제 가격은 클라이언트가 다시 받음)
	GamePasses = {
		{ Id = "LuckVIP", Name = "행운 VIP", PassId = 1999287690, LuckMult = 2, Price = 399 },
		{ Id = "FastRoll", Name = "빠른 굴림", PassId = 2002682533, CooldownMult = 0.7, Price = 199 },
		{ Id = "DoubleIncome", Name = "수입 2배", PassId = 2003390304, IncomeMult = 2, Price = 299 },
	} :: { GamePass },
	Products = {
		{
			Id = "LuckBoost",
			Name = "행운 부스트",
			ProductId = 3715550240,
			Seconds = 900,
			LuckMult = 2,
			Price = 49,
		},
		{
			Id = "ServerLuck",
			Name = "서버 행운",
			ProductId = 3715550255,
			Seconds = 900,
			LuckMult = 2,
			ServerWide = true,
			Price = 99,
		},
		{
			Id = "CoinPack",
			Name = "코인 팩",
			ProductId = 3715550261,
			IncomeSeconds = 1800,
			MinCoins = 1000,
			Price = 79,
		},
	} :: { Product },
	-- 시간 부스트(개인·서버): 남은 시간 + 부스트 시간이 이 값을 넘으면 서버가 구매 창을 띄우지 않음.
	-- 이미 결제된 영수증은 이 값과 상관없이 산 시간을 다 더함(동시에 연 구매 창, 늦게 온 영수증 — 돈 낸 시간을 버리지 않음)
	MAX_BOOST_SECONDS = 3 * 60 * 60,
	-- 지급·저장할 때의 남은 시간 상한. 데이터 손상 방지용일 뿐이라 보통은 닿지 않게 아주 큼
	MAX_BOOST_STORED_SECONDS = 24 * 60 * 60,
	-- 중복 지급 방지용으로 기억하는 최근 구매 영수증(PurchaseId) 수. 저장이 계속 실패하는 동안 쌓인 영수증이
	-- 밀려나 다시 지급되지 않도록 넉넉하게(1000개 ≈ 40KB, DataStore 한도 4MB)
	MAX_RECEIPTS = 1000,

	-- 저장 ---------------------------------------------------------------
	DATASTORE_NAME = "LandmarkRNG_v1",
	AUTOSAVE_INTERVAL = 120,
}

return Config
