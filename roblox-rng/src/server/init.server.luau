-- 서버 진입점: 플레이어 데이터, 굴림 판정(서버 권위), 관광 수입, 업그레이드, 환생, 유료 상품,
-- 공원/대표 명소 표시, 뉴스 속보

local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local Net = require(Shared.Net)
local PlayerState = require(Shared.PlayerState)
local RollLogic = require(Shared.RollLogic)

local DataService = require(script.DataService)
local FeaturedDisplay = require(script.FeaturedDisplay)
local ParkService = require(script.ParkService)
local Purchases = require(script.Purchases)
local Scenery = require(script.Scenery)
local World = require(script.World)

-- 세계 명소(Rank 4) 이상은 굴린 사람의 연출(최대 약 4초)이 끝난 뒤에 공원/리더보드/뉴스/홀로그램에 반영
-- (굴린 본인의 클라이언트는 연출이 끝날 때까지 자기 뉴스 속보를 따로 보류함)
local REVEAL_GRACE = 4.5
local REVEAL_RANK = 4
-- 관광 수입은 서버가 1초마다 쌓고, 클라이언트는 Income 으로 코인을 부드럽게 올려 보여 줌.
-- 마지막으로 상태를 보낸 뒤 이만큼 지나면 다시 보내서 오차를 바로잡음(매초 보내지 않음)
local RESYNC_INTERVAL = 10
local TELEPORT_COOLDOWN = 1
-- 공원 배치 바꾸기(SetDisplay, 자동 배치 설정)는 칸마다 미니어처를 다시 만들 수 있으므로 속도 제한:
-- 연속 EDIT_BURST 번까지 바로, 그다음은 초당 EDIT_RATE 번
local EDIT_BURST = 10
local EDIT_RATE = 4

type Session = {
	Data: PlayerState.Data,
	LockId: string?, -- nil 이면 저장하지 않음(Studio 등)
	LastRoll: number,
	Revision: number,
	LastSync: number, -- 마지막으로 Snapshot 을 만든(보낸) 시각
	LastTeleport: number,
	EditTokens: number, -- 공원 배치 바꾸기 속도 제한(토큰 버킷)
	EditAt: number,
	Stats: { Rolls: IntValue, Rebirths: IntValue, Best: StringValue },
	Plot: number?, -- 배정된 공원 부지 번호(부지가 모자라면 nil)
	-- 연출이 아직 안 끝나 공원/리더보드에 공개하지 않은 발견(명소 Id -> 횟수)
	Hidden: { [string]: number },
	-- 가진 게임패스 Id -> true (세션에만 저장. 접속 시 확인 + 구매 완료 이벤트로 갱신)
	Passes: { [string]: boolean },
}

local sessions: { [Player]: Session } = {}
local started: { [Player]: boolean } = {}
-- 게임패스 소유 정보. 데이터 로드와 동시에 확인하므로 세션보다 먼저 만들어 두고 세션이 같은 표를 씀
local passesByPlayer: { [Player]: { [string]: boolean } } = {}
-- 접속 시 게임패스 확인(다시 확인 포함)이 끝났는지. 실패로 끝나도 true (코인 팩 영수증이 이걸 잠깐 기다림)
local passesReady: { [Player]: boolean } = {}
local rng = Random.new()

-- 서버 행운(서버 전원에게 적용, 저장 안 함). os.clock() 기준 끝나는 시각
local serverLuckUntil = 0
local serverLuckOn = false -- 마지막으로 모두에게 알린 상태(끝날 때 한 번 상태를 다시 보내기 위함)
local serverLuckBy: { UserId: number, Name: string }? = nil -- 마지막 구매자

local function nextNumber(): number
	return rng:NextNumber()
end

local function serverLuckLeft(): number
	return math.max(0, serverLuckUntil - os.clock())
end

local function modsFor(session: Session): PlayerState.Mods
	return { Passes = session.Passes, ServerLuck = serverLuckLeft() > 0 }
end

-- 상태를 보낼 때마다 먼저 자동 발견(PlayerState.sync — 영구 행운 이하 확률의 미발견 명소 -> 발견 기록). 접속·굴림·
-- 업그레이드·환생·게임패스 등 행운이 바뀌는 일은 모두 상태를 보내므로 도감·여권이 서버와 화면에서 늘 같음
local function snapshot(session: Session): PlayerState.Snapshot
	session.Revision += 1
	session.LastSync = time()
	return PlayerState.sync(session.Data, session.Revision, modsFor(session))
end

local function pushState(player: Player)
	local session = sessions[player]
	if session then
		Net.event("State"):FireClient(player, snapshot(session))
	end
end

local function pushStateAll()
	for player in sessions do
		pushState(player)
	end
end

-- 연출 중인 발견을 뺀 "남에게 보이는" 데이터. 공원·간판·리더보드로 결과가 미리 새지 않게 함.
-- (예: 세계 명소를 뽑고 1초 뒤 흔한 명소를 뽑아도 공원에는 세계 명소가 아직 안 나타남)
local function visibleData(session: Session): PlayerState.Data
	if next(session.Hidden) == nil then
		return session.Data
	end
	local inventory = table.clone(session.Data.Inventory)
	for id, count in session.Hidden do
		local left = (inventory[id] or 0) - count
		inventory[id] = if left > 0 then left else nil
	end
	local view = table.clone(session.Data)
	view.Inventory = inventory
	return view
end

-- 공원 전시 + 간판 + 리더보드 "최고"
local function refreshVisible(player: Player, session: Session)
	local visible = visibleData(session)
	local best = PlayerState.best(visible)
	session.Stats.Best.Value = if best then best.Name else "-"
	local ok, err = pcall(ParkService.update, player, visible, modsFor(session))
	if not ok then
		warn("[LandmarkRNG] 공원 갱신 실패: " .. tostring(err))
	end
end

-- 공원 배치 바꾸기 속도 제한. 허용이면 토큰 하나를 씀
local function takeEditToken(session: Session): boolean
	local now = time()
	session.EditTokens = math.min(EDIT_BURST, session.EditTokens + (now - session.EditAt) * EDIT_RATE)
	session.EditAt = now
	if session.EditTokens < 1 then
		return false
	end
	session.EditTokens -= 1
	return true
end

local function refreshFeatured(player: Player)
	local session = sessions[player]
	local featured = if session and session.Data.Featured then Landmarks.ById[session.Data.Featured] else nil
	local ok, err = pcall(FeaturedDisplay.apply, player.Character, featured)
	if not ok then
		warn("[LandmarkRNG] 대표 명소 표시 실패: " .. tostring(err))
	end
end

local function createLeaderstats(player: Player): { Rolls: IntValue, Rebirths: IntValue, Best: StringValue }
	local folder = Instance.new("Folder")
	folder.Name = "leaderstats"
	local rolls = Instance.new("IntValue")
	rolls.Name = "굴림"
	rolls.Parent = folder
	local rebirths = Instance.new("IntValue")
	rebirths.Name = "환생"
	rebirths.Parent = folder
	local best = Instance.new("StringValue")
	best.Name = "최고"
	best.Value = "-"
	best.Parent = folder
	folder.Parent = player
	return { Rolls = rolls, Rebirths = rebirths, Best = best }
end

local function onCharacter(player: Player, character: Model)
	-- 머리/몸통이 생길 때까지 기다린 뒤 대표 명소를 붙임
	character:WaitForChild("Head", 10)
	character:WaitForChild("HumanoidRootPart", 10)
	if player.Character == character then
		refreshFeatured(player)
	end
end

-- BindToClose 가 진행 중인 저장을 기다릴 수 있도록 개수를 셈
local savesInFlight = 0

local function trackedSave(player: Player, data: PlayerState.Data, lockId: string, release: boolean): boolean
	savesInFlight += 1
	local ok, saved = pcall(DataService.save, player, data, lockId, release)
	savesInFlight -= 1
	if not ok then
		warn("[LandmarkRNG] 저장 오류: " .. tostring(saved))
		return false
	end
	return saved == true
end

-- 게임패스 ----------------------------------------------------------------

-- 가진 게임패스가 늘었을 때: 내 화면(상태) + 모두가 보는 공원 간판(수입 2배가 간판 수입에 들어감)
local function onPassesChanged(player: Player)
	local session = sessions[player]
	if session then
		refreshVisible(player, session)
		pushState(player)
	end
end

-- 서버 행운 ----------------------------------------------------------------

-- 클라이언트용 서버 행운 정보. Until 은 workspace:GetServerTimeNow() 기준 끝나는 시각, Left 는 보낼 때 남은 초
local function serverLuckInfo()
	local left = serverLuckLeft()
	return {
		UserId = if serverLuckBy then serverLuckBy.UserId else 0,
		Name = if serverLuckBy then serverLuckBy.Name else "",
		Until = workspace:GetServerTimeNow() + left,
		Left = left,
	}
end

-- 결제된 시간은 다 더함(구매 창 상한 MAX_BOOST_SECONDS 로 자르지 않음 — Purchases.extendUntil)
local function extendServerLuck(buyer: Player, seconds: number)
	local added
	serverLuckUntil, added = Purchases.extendUntil(serverLuckUntil, os.clock(), seconds)
	serverLuckOn = true
	serverLuckBy = { UserId = buyer.UserId, Name = buyer.DisplayName }
	Net.event("ServerLuck"):FireAllClients(serverLuckInfo())
	pushStateAll()
	print(string.format("[LandmarkRNG] %s 님이 서버 행운 %d초 추가", buyer.Name, math.floor(added + 0.5)))
end

-- 유료 상품 처리(Purchases)에 넘기는 서버 쪽 일 --------------------------------------

local purchaseDeps: Purchases.Deps = {
	findPlayer = function(userId: number): Player?
		return Players:GetPlayerByUserId(userId)
	end,
	session = function(player: Player): Purchases.Session?
		return sessions[player]
	end,
	inGame = function(player: Player): boolean
		return player.Parent == Players
	end,
	passesReady = function(player: Player): boolean
		return passesReady[player] == true
	end,
	mods = function(session: Purchases.Session): PlayerState.Mods
		return modsFor(session :: any)
	end,
	save = function(player: Player, session: Purchases.Session): boolean
		local lockId = session.LockId
		return lockId ~= nil and trackedSave(player, session.Data, lockId, false)
	end,
	serverLuck = extendServerLuck,
	pushState = pushState,
	ownsPass = function(player: Player, passId: number): boolean
		return MarketplaceService:UserOwnsGamePassAsync(player.UserId, passId)
	end,
	passesChanged = onPassesChanged,
	wait = function(seconds: number)
		task.wait(seconds)
	end,
	clock = os.clock,
}

-- 게임패스 구매 창이 닫힘: 샀으면 바로 반영. 안 샀는데 아직 모르는 패스면 한 번 더 확인
-- (이미 가진 패스라서 로블록스가 "이미 보유" 로 닫은 경우 — 접속 확인이 오류였던 때)
MarketplaceService.PromptGamePassPurchaseFinished:Connect(
	function(player: Player, passId: number, wasPurchased: boolean)
		local pass = Purchases.passByPassId(passId)
		local owned = passesByPlayer[player]
		if not pass or not owned or owned[pass.Id] then
			return
		end
		if wasPurchased then
			owned[pass.Id] = true
			onPassesChanged(player)
		else
			Purchases.recheckPass(player, owned, pass, purchaseDeps)
		end
	end
)

-- 접속 시 게임패스 확인(오류 난 패스는 몇 번 다시). owned 는 세션과 같은 표라서 확인되는 대로 반영됨
local function loadPasses(player: Player, owned: { [string]: boolean })
	Purchases.checkPasses(player, owned, purchaseDeps)
	if passesByPlayer[player] == owned then -- 그사이 나갔다 들어오지 않았으면
		passesReady[player] = true
	end
end

-- 플레이어 입장/퇴장 -----------------------------------------------------------

local function onPlayerAdded(player: Player)
	if started[player] then
		return
	end
	started[player] = true

	-- 게임패스 확인은 데이터 로드와 동시에 진행
	local passes = {}
	passesByPlayer[player] = passes
	task.spawn(loadPasses, player, passes)

	local data, lockId = DataService.load(player)
	if player.Parent == nil then
		-- 불러오는 동안 나감: 방금 건 세션 잠금을 풀어 둬야 다음 접속이 기다리지 않음
		started[player] = nil
		passesByPlayer[player] = nil
		passesReady[player] = nil
		if data and lockId then
			trackedSave(player, data, lockId, true)
		end
		return
	end
	if not data then
		player:Kick("데이터를 불러오지 못했습니다. 잠시 후 다시 접속해 주세요.")
		return
	end

	local session: Session = {
		Data = data,
		LockId = lockId,
		LastRoll = -math.huge,
		Revision = 0,
		LastSync = time(),
		LastTeleport = -math.huge,
		EditTokens = EDIT_BURST,
		EditAt = time(),
		Stats = createLeaderstats(player),
		Plot = nil,
		Hidden = {},
		Passes = passes,
	}
	sessions[player] = session
	session.Stats.Rolls.Value = data.Rolls
	session.Stats.Rebirths.Value = data.Rebirths

	-- 공원 부지 배정 + 전시
	local ok, result = pcall(ParkService.assign, player)
	if ok then
		session.Plot = result
	else
		warn("[LandmarkRNG] 공원 부지 배정 실패: " .. tostring(result))
	end
	refreshVisible(player, session)

	player.CharacterAdded:Connect(function(character)
		onCharacter(player, character)
	end)
	-- 일부 아바타(다이나믹 헤드 등)는 외형 로딩 중 머리를 교체하므로 로딩이 끝난 뒤 한 번 더 붙임
	player.CharacterAppearanceLoaded:Connect(function(character)
		if player.Character == character then
			refreshFeatured(player)
		end
	end)
	if player.Character then
		task.spawn(onCharacter, player, player.Character)
	end
	pushState(player)
	-- 서버 행운이 이미 진행 중이면 남은 시간을 알려 줌
	if serverLuckLeft() > 0 then
		Net.event("ServerLuck"):FireClient(player, serverLuckInfo())
	end
end

local function saveAndRelease(player: Player)
	started[player] = nil
	passesByPlayer[player] = nil
	passesReady[player] = nil
	local ok, err = pcall(ParkService.release, player)
	if not ok then
		warn("[LandmarkRNG] 공원 부지 정리 실패: " .. tostring(err))
	end
	local session = sessions[player]
	if not session then
		return
	end
	sessions[player] = nil
	if session.LockId then
		trackedSave(player, session.Data, session.LockId, true)
	end
end

-- 월드(광장 + 지구본), 공원 부지, 주변 풍경. 실패해도 굴리기/저장은 되도록 pcall
do
	local ok, err = pcall(World.build)
	if not ok then
		warn("[LandmarkRNG] 광장을 만들지 못했습니다: " .. tostring(err))
	end
	ok, err = pcall(ParkService.init)
	if not ok then
		warn("[LandmarkRNG] 공원 부지를 만들지 못했습니다: " .. tostring(err))
	end
	ok, err = pcall(Scenery.build)
	if not ok then
		warn("[LandmarkRNG] 주변 풍경을 만들지 못했습니다: " .. tostring(err))
	end
end

Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(saveAndRelease)
for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end

-- 서버 종료 시 남은 플레이어를 병렬로 저장하고, 퇴장 처리 중인 저장까지 끝나길 기다림(최대 약 25초)
game:BindToClose(function()
	for player in sessions do
		task.spawn(saveAndRelease, player)
	end
	local deadline = os.clock() + 25
	while savesInFlight > 0 and os.clock() < deadline do
		task.wait(0.1)
	end
end)

-- 자동 저장
task.spawn(function()
	while true do
		task.wait(Config.AUTOSAVE_INTERVAL)
		for player, session in sessions do
			if session.LockId then
				task.spawn(DataService.save, player, session.Data, session.LockId, false)
			end
		end
	end
end)

-- 관광 수입 + 시간 부스트 (접속 중에만). 상태는 매초 보내지 않고 RESYNC_INTERVAL 마다 재동기화만.
-- 굴리는 중인 플레이어는 굴림 응답마다 상태를 받으므로 재동기화가 연출 도중에 끼어들지 않음.
-- 부스트가 끝나거나 서버 행운이 끝나면 행운이 바뀌므로 바로 상태를 보냄.
task.spawn(function()
	while true do
		local dt = task.wait(1)
		local now = time()
		local serverLuckEnded = serverLuckOn and serverLuckLeft() <= 0
		if serverLuckEnded then
			serverLuckOn = false
		end
		for player, session in sessions do
			PlayerState.addIncome(session.Data, dt, modsFor(session))
			local expired = PlayerState.tickBoosts(session.Data, dt)
			if expired or serverLuckEnded or now - session.LastSync >= RESYNC_INTERVAL then
				pushState(player)
			end
		end
	end
end)

local function announce(player: Player, landmark: Landmarks.Landmark, rollNumber: number)
	local hologram = landmark.OneIn >= Config.HOLOGRAM_ONE_IN
	Net.event("Announce"):FireAllClients({
		UserId = player.UserId,
		Name = player.DisplayName,
		LandmarkId = landmark.Id,
		Rolls = rollNumber,
		Hologram = hologram,
	})
	if hologram then
		local ok, err = pcall(World.hologram, landmark)
		if not ok then
			warn("[LandmarkRNG] 홀로그램 실패: " .. tostring(err))
		end
	end
	print(
		string.format(
			"[LandmarkRNG] %s 님이 %s (%s) 발견 — %d번째 굴림",
			player.Name,
			landmark.Name,
			Format.oneIn(landmark.OneIn),
			rollNumber
		)
	)
end

-- 희귀 발견을 연출이 끝날 때까지 숨겼다가 공개
local function revealLater(player: Player, session: Session, landmark: Landmarks.Landmark)
	session.Hidden[landmark.Id] = (session.Hidden[landmark.Id] or 0) + 1
	task.delay(REVEAL_GRACE, function()
		local left = (session.Hidden[landmark.Id] or 1) - 1
		session.Hidden[landmark.Id] = if left > 0 then left else nil
		if sessions[player] == session then
			refreshVisible(player, session)
		end
	end)
end

-- 개발자 상품 구매 처리 --------------------------------------------------------
-- 규칙은 Purchases.processReceipt: 지급 + 저장 성공 후에만 PurchaseGranted, 같은 PurchaseId 는 Data.Receipts 로
-- 한 번만 지급, 데이터를 불러오는 중이면 세션을 기다림. 저장이 실패하면 NotProcessedYet → Roblox 가 나중에 다시 부름.

local function processReceipt(receiptInfo: { [string]: any }): Enum.ProductPurchaseDecision
	return Purchases.processReceipt(receiptInfo, purchaseDeps)
end

MarketplaceService.ProcessReceipt = function(receiptInfo)
	local ok, decision = pcall(processReceipt, receiptInfo)
	if ok then
		return decision
	end
	warn("[LandmarkRNG] 구매 처리 오류: " .. tostring(decision))
	return Enum.ProductPurchaseDecision.NotProcessedYet
end

-- 원격 함수 --------------------------------------------------------------

Net.fn("GetState").OnServerInvoke = function(player: Player)
	-- 클라이언트가 데이터 로드보다 먼저 시작할 수 있으므로 최대 30초 대기
	local deadline = os.clock() + 30
	while not sessions[player] and player.Parent and os.clock() < deadline do
		task.wait(0.2)
	end
	local session = sessions[player]
	return if session then snapshot(session) else nil
end

Net.fn("Roll").OnServerInvoke = function(player: Player)
	local session = sessions[player]
	if not session then
		return { Ok = false, Reason = "loading" }
	end

	-- 쿨타임(RollLogic.cooldownGate): 허용 오차만큼 일찍 와도 받아주되, 기준 시각이 받을 때마다 굴림 간격 이상 밀려서
	-- 오차를 반복 악용해도 평균 속도가 빨라지지 않음. 네트워크 지연이 들쭉날쭉해도(늦게 닿은 요청 뒤 제때 보낸 요청)
	-- 거절하지 않게 기준은 "닿은 시각 - 오차"까지만 늦춤
	local mods = modsFor(session)
	local now = time()
	local ok, value = RollLogic.cooldownGate(
		session.LastRoll,
		now,
		PlayerState.cooldown(session.Data, mods),
		Config.COOLDOWN_TOLERANCE
	)
	if not ok then
		return { Ok = false, Reason = "cooldown", RetryIn = value }
	end
	session.LastRoll = value

	-- 굴리기 전에 자동 발견(도장이 늘면 행운이 오름 — rollLuck). 굴린 뒤의 자동 발견은 응답 State(snapshot)에서
	local luck = PlayerState.rollLuck(session.Data, mods)
	local landmark = RollLogic.roll(Landmarks.RarestFirst, luck, nextNumber)
	local bonus, isNew, starUp = PlayerState.applyRoll(session.Data, landmark)
	local rollNumber = session.Data.Rolls
	session.Stats.Rolls.Value = rollNumber

	-- 세계 명소 이상은 연출이 끝난 뒤에 공원/리더보드("최고")에 반영해야 결과가 미리 새지 않음
	if landmark.Tier.Rank >= REVEAL_RANK then
		revealLater(player, session, landmark)
	else
		refreshVisible(player, session)
	end
	if landmark.OneIn >= Config.ANNOUNCE_ONE_IN then
		task.delay(REVEAL_GRACE, announce, player, landmark, rollNumber)
	end

	return {
		Ok = true,
		LandmarkId = landmark.Id,
		Luck = luck,
		Bonus = bonus,
		IsNew = isNew,
		StarUp = starUp,
		Stars = PlayerState.stars(session.Data.Inventory[landmark.Id] or 0),
		State = snapshot(session),
	}
end

-- 대표 명소 지정/해제. 자동 지정 여부는 클라이언트가 연출 뒤에 판단해서 요청함(서버는 검증만).
Net.fn("Feature").OnServerInvoke = function(player: Player, landmarkId: any)
	local session = sessions[player]
	if not session then
		return { Ok = false }
	end
	local before = session.Data.Featured
	local ok = PlayerState.feature(session.Data, landmarkId)
	if ok and session.Data.Featured ~= before then
		refreshFeatured(player)
	end
	return { Ok = ok, State = snapshot(session) }
end

Net.fn("BuyUpgrade").OnServerInvoke = function(player: Player, upgradeId: any)
	local session = sessions[player]
	if not session then
		return { Ok = false, Reason = "데이터를 불러오는 중입니다" }
	end
	local ok, reason = PlayerState.buyUpgrade(session.Data, upgradeId)
	if ok then
		-- 공원 확장(칸 수), 입장료(간판의 수입) 등이 바뀔 수 있음. 바뀐 칸만 다시 만듦
		refreshVisible(player, session)
	end
	return { Ok = ok, Reason = reason, State = snapshot(session) }
end

Net.fn("SetSetting").OnServerInvoke = function(player: Player, key: any, value: any)
	local session = sessions[player]
	if not session then
		return { Ok = false }
	end
	-- 자동 배치를 켜면 공원이 다시 채워지므로 배치 편집과 같은 속도 제한
	local park = key == "AutoPark"
	if park and not takeEditToken(session) then
		return { Ok = false, State = snapshot(session) }
	end
	local ok = PlayerState.setSetting(session.Data, key, value)
	if ok and park then
		refreshVisible(player, session)
	end
	return { Ok = ok, State = snapshot(session) }
end

-- 공원 전시 칸에 명소 놓기(이미 다른 칸에 있으면 자리 바꿈) / 빼기(nil). 검증은 PlayerState.setDisplay.
-- expected: 클라이언트가 본 그 칸의 명소 Id("" = 빈 칸), expectedFrom: 옮기는 명소가 있던 칸(0 = 전시 안 됨).
-- 둘 중 하나라도 지금과 다르면 Reason "stale" + 새 상태(클라이언트가 다시 그림).
-- 자동 배치 중 첫 편집이면 자동 배치가 꺼지고 지금 배치에서 시작
Net.fn("SetDisplay").OnServerInvoke = function(
	player: Player,
	slot: any,
	landmarkId: any,
	expected: any,
	expectedFrom: any
)
	local session = sessions[player]
	if not session then
		return { Ok = false, Reason = "데이터를 불러오는 중입니다" }
	end
	if not takeEditToken(session) then
		return { Ok = false, Reason = "busy", State = snapshot(session) }
	end
	local ok, reason = PlayerState.setDisplay(session.Data, slot, landmarkId, expected, expectedFrom)
	if ok then
		refreshVisible(player, session)
	end
	return { Ok = ok, Reason = reason, State = snapshot(session) }
end

-- 환생: 코인·업그레이드·보유 명소·대표 명소 초기화 → 공원/간판/리더보드/대표 명소 표시 갱신
Net.fn("Rebirth").OnServerInvoke = function(player: Player)
	local session = sessions[player]
	if not session then
		return { Ok = false, Reason = "데이터를 불러오는 중입니다" }
	end
	local ok, reason = PlayerState.rebirth(session.Data)
	if ok then
		session.Stats.Rebirths.Value = session.Data.Rebirths
		refreshVisible(player, session)
		refreshFeatured(player)
		pushState(player)
		print(string.format("[LandmarkRNG] %s 님 %d번째 환생", player.Name, session.Data.Rebirths))
	end
	return { Ok = ok, Reason = reason, State = snapshot(session) }
end

-- 구매 창 띄우기. 결과는 구매 완료 이벤트 / ProcessReceipt 에서 State(+ServerLuck) 이벤트로 반영됨.
-- 못 띄우면 { Ok = false, Reason }: "owned" 이미 가진 게임패스, "loading" 데이터 불러오는 중,
-- "max" 부스트 시간이 가득 참(3시간), nil 그 밖의 실패
Net.fn("BuyPass").OnServerInvoke = function(player: Player, passKey: any)
	local pass = if type(passKey) == "string" then PlayerState.PassesById[passKey] else nil
	if not pass or pass.PassId <= 0 then
		return { Ok = false }
	end
	-- 접속 때 확인이 오류였거나 웹사이트에서 산 경우를 위해 한 번 더 확인(가졌으면 구매 창 대신 바로 반영)
	local owned = passesByPlayer[player]
	if owned and Purchases.recheckPass(player, owned, pass, purchaseDeps) then
		return { Ok = false, Reason = "owned" }
	end
	local ok, err = pcall(function()
		MarketplaceService:PromptGamePassPurchase(player, pass.PassId)
	end)
	if not ok then
		warn("[LandmarkRNG] 게임패스 구매 창 실패: " .. tostring(err))
	end
	return { Ok = ok }
end

Net.fn("BuyProduct").OnServerInvoke = function(player: Player, productKey: any)
	-- 시간 부스트는 남은 시간이 최대(MAX_BOOST_SECONDS)를 넘게 되면 구매 창을 띄우지 않음(Purchases.promptCheck)
	local product, reason = Purchases.promptCheck(productKey, sessions[player], serverLuckLeft())
	if not product then
		return { Ok = false, Reason = reason }
	end
	local ok, err = pcall(function()
		MarketplaceService:PromptProductPurchase(player, product.ProductId)
	end)
	if not ok then
		warn("[LandmarkRNG] 개발자 상품 구매 창 실패: " .. tostring(err))
	end
	return { Ok = ok }
end

Net.fn("Teleport").OnServerInvoke = function(player: Player, where: any)
	if where ~= "Park" and where ~= "Plaza" then
		return { Ok = false }
	end
	local session = sessions[player]
	if not session then
		return { Ok = false }
	end
	local now = time()
	if now - session.LastTeleport < TELEPORT_COOLDOWN then
		return { Ok = false }
	end

	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if not character or not humanoid or humanoid.Health <= 0 or not root then
		return { Ok = false }
	end

	local target: CFrame
	if where == "Park" then
		local entrance = ParkService.entranceCFrame(player)
		if not entrance then
			return { Ok = false }
		end
		target = entrance + Vector3.new(0, 3, 0) -- 캐릭터 피벗(HumanoidRootPart)은 발바닥보다 약 3 스터드 위
	else
		target = World.plazaCFrame()
	end

	session.LastTeleport = now
	humanoid.Sit = false
	character:PivotTo(target)
	return { Ok = true }
end
