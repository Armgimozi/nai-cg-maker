-- 분석(AnalyticsService): Creator Hub 분석 대시보드(퍼널 · 경제 · 사용자 지정 이벤트)에 보낼 이벤트를 모두 여기서 만듦.
-- 서버 코드(init.server, Purchases 의 deps)가 일이 생긴 곳에서 한 줄로 부름. 무엇을 보내고 어디서 읽는지는 DESIGN.md "분석".
--
-- 지키는 것
--   · 게임을 멈추지 않음: 공개 함수는 모두 pcall 로 감쌈(오류는 같은 문장마다 한 번만 warn), 서비스가 없거나 Studio 면
--     보내지 않음(로블록스는 게시된 게임의 서버에서 보낸 이벤트만 받음)
--   · 한도(경험 전체): 사용자 지정 이벤트 이름 4개(RareFind · AutoOn · TapEdit · SessionEnd, 한도 100), 퍼널 4개 + 온보딩
--     (한도 10), 통화 1개(Coins, 한도 5), 거래 종류 3개(Gameplay · Shop · IAP, 한도 20), SKU 8개(한도 100).
--     사용자 지정 필드 값은 정해진 몇 가지(등급 · 환생 구간 · 상품 키 · 시간 구간 …)뿐 — 플레이어 이름·Id·명소 Id 같은
--     자유 값은 넣지 않음(세 필드 값 조합 8,000 개 한도)
--   · 굴림마다 보내지 않음: 희귀 발견(불가사의 이상 + 처음이거나 그 굴림 행운으로도 1/1,000 이상)만. 발견 보너스·공원 수입은
--     FLUSH_INTERVAL(5분)마다 합쳐서 한 번(+ 환생·퇴장 때). 화면 이벤트(클라이언트 Track)는 종류마다 최소 간격
--   · 서버 전체 속도 한도(분당 120 + 20 × 인원)의 RATE_SHARE(80%) 안: 넘치면 버림. 사용자 지정 이벤트(희귀 발견·AUTO·톡 배치)는
--     LOW_RESERVE(25%)를 남겨 두고 먼저 버림 — 퍼널·경제 이벤트가 밀리지 않게

local HttpService = game:GetService("HttpService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Landmarks = require(Shared.Landmarks)
local PlayerState = require(Shared.PlayerState)

local Analytics = {}

Analytics.CURRENCY = "Coins"
-- 공원 수입·발견 보너스를 모아 두었다가 보내는 간격(초)
Analytics.FLUSH_INTERVAL = 300
-- 온보딩 "첫 1/1,000 이상 발견"(세계 명소 등급부터)
Analytics.RARE_FIRST_ONE_IN = 1000
-- 희귀 발견(RareFind): 이 등급 이상 + (처음 발견 또는 1/N ≥ RARE_RELATIVE × 그 굴림 행운 — 후반 행운이 크면 불가사의·잃어버린
-- 유산은 거의 매 굴림이라 그때는 보내지 않음. 새 발견이 없으면 후반 AUTO 시간당 10번 안팎, 초반 약 2번 — 새 발견이 많은
-- 후반 첫 한 시간도 60번 이하, 테스트가 확인)
Analytics.RARE_MIN_RANK = 5
Analytics.RARE_RELATIVE = 1000
-- 서버 전체 속도 한도(분당 120 + 20 × 인원) 중 쓰는 몫, 사용자 지정 이벤트가 남겨 두는 몫
Analytics.RATE_SHARE = 0.8
Analytics.LOW_RESERVE = 0.25

-- 온보딩 퍼널(한 사람에 한 번 — Data.Analytics.Onboarding 에 저장, 1번부터 빈틈없이 이어진 단계까지만 보냄:
-- PlayerState.onboardingStep). 번호 = Creator Hub 퍼널 단계
Analytics.ONBOARDING = {
	Joined = 1, -- 처음 들어옴
	FirstRoll = 2, -- 첫 굴림
	FirstNew = 3, -- 첫 새 명소(발견 보너스)
	FirstStatue = 4, -- 내 공원에 첫 명소가 전시됨(희귀하면 연출이 끝난 뒤)
	FirstUpgrade = 5, -- 첫 강화
	OpenedCollection = 6, -- 도감 열기
	FirstRare = 7, -- 첫 1/1,000 이상 발견(굴려서)
	FirstRebirth = 8, -- 첫 환생
}
Analytics.ONBOARDING_NAMES = {
	"Joined",
	"First Roll",
	"First New Landmark",
	"First Statue On Display",
	"First Upgrade",
	"Opened Collection",
	"First 1-in-1000 Find",
	"First Rebirth",
}

-- 퍼널 이름(Creator Hub 분석 → 퍼널 탭)
Analytics.FUNNEL_SHOP = "Shop" -- 상점 열기 → 카드 누름 → 구매 창 → 구매 (상점을 열 때마다 새 세션)
Analytics.FUNNEL_PURCHASE = "Purchase" -- 카드 누름 → 구매 창 → 구매 (누를 때마다 새 세션, 필드 1 = 상품 키 → 상품별 전환)
Analytics.FUNNEL_REBIRTHS = "Rebirths" -- 환생 1 → 10 (한 사람에 한 번)
Analytics.FUNNEL_STAMPS = "Stamps" -- 대륙 도장 1 → 5 (한 사람에 한 번)

-- 화면에서만 알 수 있는 일(클라이언트가 Track 원격으로 알림) → 같은 플레이어가 다시 보내도 받는 최소 간격(초).
-- 이 목록에 없는 이름은 버림(가짜 클라이언트가 이벤트 이름을 늘리지 못하게)
Analytics.CLIENT_EVENTS = {
	ShopOpened = 2, -- 상점 퍼널 1단계
	CollectionOpened = 2, -- 온보딩 6단계
	AutoOn = 30, -- 사용자 지정 AutoOn
	TapEdit = 30, -- 사용자 지정 TapEdit(내 공원을 톡 눌러 배치 모드)
}

-- Enum.AnalyticsCustomFieldKeys.CustomField01~03 의 Name (customFields 표의 키)
local FIELD1, FIELD2, FIELD3 = "CustomField01", "CustomField02", "CustomField03"

-- 경제 거래 종류 = Enum.AnalyticsEconomyTransactionType 의 Name(로블록스 기본 종류라 경제 대시보드가 알아서 나눔).
-- 열거형을 못 읽는 환경(가짜 Roblox 는 "이름.값" 문자열)이면 같은 이름 글자
local function transactionName(item: string): string
	local ok, name = pcall(function()
		local value: any = (Enum :: any).AnalyticsEconomyTransactionType[item]
		if typeof(value) == "EnumItem" then
			return value.Name
		end
		return string.match(tostring(value), "([^%.]+)$")
	end)
	return if ok and type(name) == "string" and name ~= "" then name else item
end
Analytics.TRANSACTION = {
	Gameplay = transactionName("Gameplay"), -- 공원 수입 · 발견 보너스 · 환생으로 사라진 코인
	Shop = transactionName("Shop"), -- 코인으로 강화 사기
	IAP = transactionName("IAP"), -- Robux 로 산 코인 팩
}

-- 보낸 수(테스트·서버 출력용)
Analytics.stats = { Sent = 0, Dropped = 0, Failed = 0 }

-- 시계(초). 테스트가 바꿔 끼움
Analytics.clock = function(): number
	return time()
end

local service: any = nil
do
	local ok, result = pcall(function()
		if game:GetService("RunService"):IsStudio() then
			return nil -- Studio 에서는 로블록스가 이벤트를 받지 않음: 헛된 호출 없이 건너뜀
		end
		return game:GetService("AnalyticsService")
	end)
	service = if ok then result else nil
end

-- 보낼 서비스를 바꿈(테스트: 가짜 AnalyticsService, nil = 안 보냄)
function Analytics.setService(value: any)
	service = value
end

-- 오류 알림: 같은 문장은 한 번만, 모두 합쳐 20개까지(서버 출력이 분석 오류로 넘치지 않게)
local warned: { [string]: boolean } = {}
local warnedCount = 0
local function warnOnce(where: string, err: any)
	local message = where .. ": " .. tostring(err)
	if warned[message] or warnedCount >= 20 then
		return
	end
	warned[message] = true
	warnedCount += 1
	warn("[Analytics] " .. message)
end

-- 공개 함수 감싸기: 무슨 일이 있어도 오류를 밖으로 내보내지 않음(게임 코드는 분석 결과를 기다리거나 받지 않음)
local function guard(name: string, fn: (...any) -> ()): (...any) -> ()
	return function(...)
		local ok, err = pcall(fn, ...)
		if not ok then
			warnOnce(name, err)
		end
	end
end

-- 플레이어마다 이번 접속 동안만 기억하는 것
-- 누른 뒤 아직 안 끝난 구매: 구매 퍼널 세션, 상점 퍼널 세션(상점을 열었으면), 단계마다 같이 보내는 필드
-- (퍼널을 필드로 나눠 볼 때 모든 단계에 같은 값이 있어야 단계가 빠지지 않음)
type Pending = { Purchase: string, Shop: string?, Fields: { [string]: string }, ShopFields: { [string]: string }? }
type Tracked = {
	JoinedAt: number,
	FirstSession: boolean, -- 처음 해 보는 접속(굴림 0, 예전부터 하던 플레이어 아님)
	Stamps: number, -- 이미 알린 대륙 도장 수(접속할 때 가진 수부터)
	Income: number, -- 아직 안 보낸 공원 수입
	Discovery: number, -- 아직 안 보낸 발견 보너스
	FlushedAt: number,
	Shop: string?, -- 지금 상점 퍼널 세션(마지막으로 연 상점)
	ShopFields: { [string]: string }?, -- 그 상점 퍼널의 단계마다 같이 보내는 필드(연 때의 환생 구간)
	Pending: { [string]: Pending }, -- 상품 키 → 누른 뒤 아직 안 끝난 구매 퍼널
	ClientAt: { [string]: number }, -- 화면 이벤트 종류 → 마지막으로 받은 시각
}
local tracked: { [Player]: Tracked } = {}

-- 속도 한도(토큰 통 하나, 분당 한도만큼 차오름) -----------------------------------------------

local tokens: number? = nil
local tokensAt = 0

local function perMinute(): number
	local count = 0
	for _ in tracked do
		count += 1
	end
	return Analytics.RATE_SHARE * (120 + 20 * math.max(1, count))
end

-- low = 사용자 지정 이벤트(통에 LOW_RESERVE 보다 많이 남았을 때만)
local function take(low: boolean): boolean
	local now = Analytics.clock()
	local cap = perMinute()
	local current = cap
	if tokens then
		current = math.min(cap, tokens + math.max(0, now - tokensAt) * cap / 60)
	end
	tokensAt = now
	local need = if low then 1 + cap * Analytics.LOW_RESERVE else 1
	if current < need then
		tokens = current
		return false
	end
	tokens = current - 1
	return true
end

local function send(low: boolean, method: string, ...: any)
	local target = service
	if not target then
		return
	end
	if not take(low) then
		Analytics.stats.Dropped += 1
		return
	end
	local args = table.pack(...)
	local ok, err = pcall(function()
		target[method](target, table.unpack(args, 1, args.n))
	end)
	if ok then
		Analytics.stats.Sent += 1
	else
		Analytics.stats.Failed += 1
		warnOnce(method, err)
	end
end

-- 필드 값(정해진 몇 가지) ---------------------------------------------------------------------

-- 환생 구간: R0 · R1 · R2-3 · R4-6 · R7-9 · R10
function Analytics.rebirthBucket(rebirths: number?): string
	local n = math.max(0, math.floor(tonumber(rebirths) or 0))
	if n <= 1 then
		return "R" .. n
	elseif n <= 3 then
		return "R2-3"
	elseif n <= 6 then
		return "R4-6"
	elseif n <= 9 then
		return "R7-9"
	end
	return "R10"
end

-- 접속 시간 구간(분): <5m · 5-15m · 15-30m · 30-60m · 1-2h · 2h+
function Analytics.sessionBucket(minutes: number): string
	if minutes < 5 then
		return "<5m"
	elseif minutes < 15 then
		return "5-15m"
	elseif minutes < 30 then
		return "15-30m"
	elseif minutes < 60 then
		return "30-60m"
	elseif minutes < 120 then
		return "1-2h"
	end
	return "2h+"
end

-- 강화 레벨 구간(산 뒤의 레벨): Lv1-5 · Lv6-10 · Lv11-15 · Lv16-20
function Analytics.levelBucket(level: number): string
	local n = math.clamp(math.floor(level), 1, 20)
	local from = math.floor((n - 1) / 5) * 5 + 1
	return string.format("Lv%d-%d", from, from + 4)
end

-- 보내기 도우미 ---------------------------------------------------------------------------

local function guid(): string
	return HttpService:GenerateGUID(false)
end

local function onboard(player: Player, data: PlayerState.Data, step: number)
	for _, n in PlayerState.onboardingStep(data, step) do
		send(false, "LogOnboardingFunnelStepEvent", player, n, Analytics.ONBOARDING_NAMES[n] or ("Step " .. n))
	end
end

local function funnel(player: Player, name: string, session: string?, step: number, stepName: string, fields: any?)
	send(false, "LogFunnelStepEvent", player, name, session, step, stepName, fields)
end

local function economy(
	player: Player,
	flow: any,
	amount: number,
	balance: number,
	transaction: string,
	sku: string,
	fields: any?
)
	if not (amount > 0) then
		return
	end
	send(
		false,
		"LogEconomyEvent",
		player,
		flow,
		Analytics.CURRENCY,
		amount,
		math.max(0, math.floor(balance)),
		transaction, -- Enum.AnalyticsEconomyTransactionType 의 Name
		sku,
		fields
	)
end

local function progression(player: Player, path: string, level: number, levelName: string)
	send(false, "LogProgressionEvent", player, path, Enum.AnalyticsProgressionType.Complete, level, levelName)
end

-- 모아 둔 공원 수입·발견 보너스를 보냄(정수만, 남은 소수는 다음에). balance = 지금 코인, rebirths = 그 코인을 번 판의 환생 수
local function flush(player: Player, state: Tracked, balance: number, rebirths: number)
	state.FlushedAt = Analytics.clock()
	local fields = { [FIELD1] = Analytics.rebirthBucket(rebirths) }
	local income = math.floor(state.Income)
	if income > 0 then
		state.Income -= income
		economy(
			player,
			Enum.AnalyticsEconomyFlowType.Source,
			income,
			balance,
			Analytics.TRANSACTION.Gameplay,
			"ParkIncome",
			fields
		)
	end
	local discovery = math.floor(state.Discovery)
	if discovery > 0 then
		state.Discovery -= discovery
		economy(
			player,
			Enum.AnalyticsEconomyFlowType.Source,
			discovery,
			balance,
			Analytics.TRANSACTION.Gameplay,
			"DiscoveryBonus",
			fields
		)
	end
end

-- 공개: 서버가 일이 생긴 곳에서 부름 -----------------------------------------------------------

-- 데이터를 다 불러와 세션이 생김: 온보딩 1단계, 접속 시간·도장 기준
Analytics.playerAdded = guard("playerAdded", function(player: Player, data: PlayerState.Data)
	local now = Analytics.clock()
	tracked[player] = {
		JoinedAt = now,
		FirstSession = data.Rolls == 0 and not data.Analytics.Legacy,
		Stamps = #PlayerState.completedRegions(data),
		Income = 0,
		Discovery = 0,
		FlushedAt = now,
		Shop = nil,
		ShopFields = nil,
		Pending = {},
		ClientAt = {},
	}
	onboard(player, data, Analytics.ONBOARDING.Joined)
end)

-- 나감(서버 종료 포함): 남은 수입을 보내고 접속 시간 구간(SessionEnd, 값 = 분)
Analytics.playerRemoving = guard("playerRemoving", function(player: Player, data: PlayerState.Data)
	local state = tracked[player]
	if not state then
		return
	end
	tracked[player] = nil -- 먼저 지움(아래에서 무슨 일이 있어도 남지 않게)
	flush(player, state, data.Coins, data.Rebirths)
	local minutes = math.max(0, Analytics.clock() - state.JoinedAt) / 60
	send(false, "LogCustomEvent", player, "SessionEnd", math.floor(minutes * 10 + 0.5) / 10, {
		[FIELD1] = Analytics.sessionBucket(minutes),
		[FIELD2] = if state.FirstSession then "First" else "Returning",
		[FIELD3] = Analytics.rebirthBucket(data.Rebirths),
	})
end)

-- 굴림 판정 뒤(applyRoll 결과): 온보딩 2·3·7, 발견 보너스 모으기, 희귀 발견(RareFind)
Analytics.rolled = guard(
	"rolled",
	function(
		player: Player,
		data: PlayerState.Data,
		landmark: Landmarks.Landmark,
		isNew: boolean,
		bonus: number,
		luck: number
	)
		onboard(player, data, Analytics.ONBOARDING.FirstRoll)
		if isNew then
			onboard(player, data, Analytics.ONBOARDING.FirstNew)
		end
		if landmark.OneIn >= Analytics.RARE_FIRST_ONE_IN then
			onboard(player, data, Analytics.ONBOARDING.FirstRare)
		end
		local state = tracked[player]
		if state and bonus > 0 then
			state.Discovery += bonus
		end
		local rank = landmark.Tier.Rank
		if
			rank >= Analytics.RARE_MIN_RANK
			and (isNew or landmark.OneIn >= Analytics.RARE_RELATIVE * math.max(1, luck))
		then
			send(true, "LogCustomEvent", player, "RareFind", rank, {
				[FIELD1] = "Tier " .. rank,
				[FIELD2] = if isNew then "New" else "Repeat",
				[FIELD3] = Analytics.rebirthBucket(data.Rebirths),
			})
		end
	end
)

-- 공원을 다시 그림(visible = 연출 중인 발견을 뺀 데이터): 전시된 명소가 처음 생기면 온보딩 4
Analytics.parkShown = guard("parkShown", function(player: Player, data: PlayerState.Data, visible: PlayerState.Data)
	if PlayerState.onboardingDone(data, Analytics.ONBOARDING.FirstStatue) then
		return
	end
	if #PlayerState.park(visible) > 0 then
		onboard(player, data, Analytics.ONBOARDING.FirstStatue)
	end
end)

-- 코인 강화를 삼(spent = 쓴 코인): 온보딩 5, 경제 쓰기(Shop, SKU Upgrade_<Id>)
Analytics.upgradeBought = guard(
	"upgradeBought",
	function(player: Player, data: PlayerState.Data, upgradeId: string, spent: number)
		local upgrade = PlayerState.UpgradesById[upgradeId]
		if not upgrade then
			return
		end
		onboard(player, data, Analytics.ONBOARDING.FirstUpgrade)
		economy(
			player,
			Enum.AnalyticsEconomyFlowType.Sink,
			spent,
			data.Coins,
			Analytics.TRANSACTION.Shop,
			"Upgrade_" .. upgrade.Id,
			{
				[FIELD1] = Analytics.rebirthBucket(data.Rebirths),
				[FIELD2] = Analytics.levelBucket(PlayerState.upgradeLevel(data, upgrade.Id)),
			}
		)
	end
)

-- 환생함(data 는 이미 초기화됨, coinsBefore = 환생 직전 코인): 모아 둔 수입 먼저 보냄 → 경제 쓰기(RebirthReset = 사라진 코인),
-- 온보딩 8, 환생 퍼널(n 단계), 진행 이벤트(Rebirth, n)
Analytics.rebirthed = guard("rebirthed", function(player: Player, data: PlayerState.Data, coinsBefore: number)
	local n = data.Rebirths
	local state = tracked[player]
	if state then
		flush(player, state, coinsBefore, n - 1)
	end
	economy(
		player,
		Enum.AnalyticsEconomyFlowType.Sink,
		math.floor(coinsBefore),
		data.Coins,
		Analytics.TRANSACTION.Gameplay,
		"RebirthReset",
		{ [FIELD1] = Analytics.rebirthBucket(n - 1) }
	)
	onboard(player, data, Analytics.ONBOARDING.FirstRebirth)
	if not data.Analytics.Legacy then
		funnel(player, Analytics.FUNNEL_REBIRTHS, nil, n, "Rebirth " .. n)
	end
	progression(player, "Rebirth", n, "Rebirth " .. n)
end)

-- 상태를 보낸 뒤(자동 발견까지 끝남): 대륙 도장이 늘었으면 도장 퍼널 + 진행 이벤트(Stamps, 도장 수)
Analytics.synced = guard("synced", function(player: Player, data: PlayerState.Data)
	local state = tracked[player]
	if not state then
		return
	end
	local count = #PlayerState.completedRegions(data)
	if count <= state.Stamps then
		return
	end
	for n = state.Stamps + 1, count do
		if not data.Analytics.Legacy then
			funnel(player, Analytics.FUNNEL_STAMPS, nil, n, "Stamp " .. n)
		end
		progression(player, "Stamps", n, "Stamp " .. n)
	end
	state.Stamps = count
end)

-- 관광 수입 루프(1초마다, amount = 더한 코인): 모아 두었다가 FLUSH_INTERVAL 마다 경제 벌기(ParkIncome · DiscoveryBonus)
Analytics.earned = guard("earned", function(player: Player, data: PlayerState.Data, amount: number)
	local state = tracked[player]
	if not state then
		return
	end
	if amount > 0 then
		state.Income += amount
	end
	if Analytics.clock() - state.FlushedAt >= Analytics.FLUSH_INTERVAL then
		flush(player, state, data.Coins, data.Rebirths)
	end
end)

-- 클라이언트 Track 원격(화면에서만 알 수 있는 일). kind 는 믿지 않음: CLIENT_EVENTS 에 있는 이름만, 종류마다 최소 간격
Analytics.clientEvent = guard("clientEvent", function(player: Player, data: PlayerState.Data, kind: any)
	local gap = if type(kind) == "string" then Analytics.CLIENT_EVENTS[kind] else nil
	local state = tracked[player]
	if not gap or not state then
		return
	end
	local now = Analytics.clock()
	local last = state.ClientAt[kind]
	if last and now - last < gap then
		return
	end
	state.ClientAt[kind] = now
	local stage = Analytics.rebirthBucket(data.Rebirths)
	if kind == "ShopOpened" then
		local id = guid()
		local fields = { [FIELD1] = stage }
		state.Shop = id
		state.ShopFields = fields
		funnel(player, Analytics.FUNNEL_SHOP, id, 1, "Shop Opened", fields)
	elseif kind == "CollectionOpened" then
		onboard(player, data, Analytics.ONBOARDING.OpenedCollection)
	elseif kind == "AutoOn" then
		send(true, "LogCustomEvent", player, "AutoOn", 1, { [FIELD1] = stage })
	elseif kind == "TapEdit" then
		send(true, "LogCustomEvent", player, "TapEdit", 1, {
			[FIELD1] = stage,
			[FIELD2] = if data.Settings.AutoPark then "AutoPark" else "Manual",
		})
	end
end)

-- 상점 카드를 누름(BuyPass/BuyProduct 원격, sku = 게임패스·상품 키): 상점 퍼널 2(상점을 열었으면) + 구매 퍼널 1(새 세션).
-- 구매 퍼널 필드(모든 단계 같음): 1 = 상품 키(상품별 전환), 2 = 환생 구간
Analytics.itemPressed = guard("itemPressed", function(player: Player, data: PlayerState.Data?, sku: string)
	local state = tracked[player]
	if not state or not (PlayerState.PassesById[sku] or PlayerState.ProductsById[sku]) then
		return
	end
	local shop, shopFields = state.Shop, state.ShopFields
	if shop then
		funnel(player, Analytics.FUNNEL_SHOP, shop, 2, "Item Pressed", shopFields)
	end
	local id = guid()
	local fields = {
		[FIELD1] = sku,
		[FIELD2] = Analytics.rebirthBucket(if data then data.Rebirths else 0),
	}
	state.Pending[sku] = { Purchase = id, Shop = shop, Fields = fields, ShopFields = shopFields }
	funnel(player, Analytics.FUNNEL_PURCHASE, id, 1, "Item Pressed", fields)
end)

-- 구매 창을 띄움: 상점 퍼널 3 + 구매 퍼널 2
Analytics.promptShown = guard("promptShown", function(player: Player, sku: string)
	local state = tracked[player]
	local pending = if state then state.Pending[sku] else nil
	if not pending then
		return
	end
	if pending.Shop then
		funnel(player, Analytics.FUNNEL_SHOP, pending.Shop, 3, "Prompt Shown", pending.ShopFields)
	end
	funnel(player, Analytics.FUNNEL_PURCHASE, pending.Purchase, 2, "Prompt Shown", pending.Fields)
end)

-- 샀음(게임패스 구매 완료 · 개발자 상품 첫 지급): 상점 퍼널 4 + 구매 퍼널 3(이 서버에서 누른 것만), 코인 팩이면 경제 벌기(IAP)
Analytics.purchased = guard("purchased", function(player: Player, data: PlayerState.Data?, sku: string, coins: number?)
	local state = tracked[player]
	local pending = if state then state.Pending[sku] else nil
	if state and pending then
		state.Pending[sku] = nil
		if pending.Shop then
			funnel(player, Analytics.FUNNEL_SHOP, pending.Shop, 4, "Purchased", pending.ShopFields)
		end
		funnel(player, Analytics.FUNNEL_PURCHASE, pending.Purchase, 3, "Purchased", pending.Fields)
	end
	if data and coins and coins > 0 then
		economy(
			player,
			Enum.AnalyticsEconomyFlowType.Source,
			coins,
			data.Coins,
			Analytics.TRANSACTION.IAP,
			sku,
			{ [FIELD1] = Analytics.rebirthBucket(data.Rebirths) }
		)
	end
end)

-- 테스트용: 이번 서버의 기억(플레이어·속도 한도·보낸 수)을 비움
function Analytics.reset()
	table.clear(tracked)
	tokens = nil
	tokensAt = 0
	Analytics.stats = { Sent = 0, Dropped = 0, Failed = 0 }
end

return Analytics
