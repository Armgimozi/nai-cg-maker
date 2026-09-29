-- 서버 진입점: 플레이어 데이터, 굴림 판정(서버 권위), 관광 수입, 업그레이드, 공원/대표 명소 표시, 뉴스 속보

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
local World = require(script.World)

-- 세계 명소(Rank 4) 이상은 굴린 사람의 연출(최대 약 4초)이 끝난 뒤에 공원/리더보드/뉴스/홀로그램에 반영
-- (굴린 본인의 클라이언트는 연출이 끝날 때까지 자기 뉴스 속보를 따로 보류함)
local REVEAL_GRACE = 4.5
local REVEAL_RANK = 4
-- 관광 수입은 서버가 1초마다 쌓고, 클라이언트는 Income 으로 코인을 부드럽게 올려 보여 줌.
-- 마지막으로 상태를 보낸 뒤 이만큼 지나면 다시 보내서 오차를 바로잡음(매초 보내지 않음)
local RESYNC_INTERVAL = 10
local TELEPORT_COOLDOWN = 1

type Session = {
	Data: PlayerState.Data,
	LockId: string?, -- nil 이면 저장하지 않음(Studio 등)
	LastRoll: number,
	Revision: number,
	LastSync: number, -- 마지막으로 Snapshot 을 만든(보낸) 시각
	LastTeleport: number,
	Stats: { Rolls: IntValue, Best: StringValue },
	Plot: number?, -- 배정된 공원 부지 번호(부지가 모자라면 nil)
	-- 연출이 아직 안 끝나 공원/리더보드에 공개하지 않은 발견(명소 Id -> 횟수)
	Hidden: { [string]: number },
}

local sessions: { [Player]: Session } = {}
local started: { [Player]: boolean } = {}
local rng = Random.new()

local function nextNumber(): number
	return rng:NextNumber()
end

local function snapshot(session: Session): PlayerState.Snapshot
	session.Revision += 1
	session.LastSync = time()
	return PlayerState.snapshot(session.Data, session.Revision)
end

local function pushState(player: Player)
	local session = sessions[player]
	if session then
		Net.event("State"):FireClient(player, snapshot(session))
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
	local ok, err = pcall(ParkService.update, player, visible)
	if not ok then
		warn("[LandmarkRNG] 공원 갱신 실패: " .. tostring(err))
	end
end

local function refreshFeatured(player: Player)
	local session = sessions[player]
	local featured = if session and session.Data.Featured then Landmarks.ById[session.Data.Featured] else nil
	local ok, err = pcall(FeaturedDisplay.apply, player.Character, featured)
	if not ok then
		warn("[LandmarkRNG] 대표 명소 표시 실패: " .. tostring(err))
	end
end

local function createLeaderstats(player: Player): { Rolls: IntValue, Best: StringValue }
	local folder = Instance.new("Folder")
	folder.Name = "leaderstats"
	local rolls = Instance.new("IntValue")
	rolls.Name = "굴림"
	rolls.Parent = folder
	local best = Instance.new("StringValue")
	best.Name = "최고"
	best.Value = "-"
	best.Parent = folder
	folder.Parent = player
	return { Rolls = rolls, Best = best }
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

local function trackedSave(player: Player, data: PlayerState.Data, lockId: string, release: boolean)
	savesInFlight += 1
	DataService.save(player, data, lockId, release)
	savesInFlight -= 1
end

local function onPlayerAdded(player: Player)
	if started[player] then
		return
	end
	started[player] = true

	local data, lockId = DataService.load(player)
	if player.Parent == nil then
		-- 불러오는 동안 나감: 방금 건 세션 잠금을 풀어 둬야 다음 접속이 기다리지 않음
		started[player] = nil
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
		Stats = createLeaderstats(player),
		Plot = nil,
		Hidden = {},
	}
	sessions[player] = session
	session.Stats.Rolls.Value = data.Rolls

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
end

local function saveAndRelease(player: Player)
	started[player] = nil
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

-- 월드(광장 + 지구본)와 공원 부지. 실패해도 굴리기/저장은 되도록 pcall
do
	local ok, err = pcall(World.build)
	if not ok then
		warn("[LandmarkRNG] 광장을 만들지 못했습니다: " .. tostring(err))
	end
	ok, err = pcall(ParkService.init)
	if not ok then
		warn("[LandmarkRNG] 공원 부지를 만들지 못했습니다: " .. tostring(err))
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

-- 관광 수입 (접속 중에만). 상태는 매초 보내지 않고 RESYNC_INTERVAL 마다 재동기화만.
-- 굴리는 중인 플레이어는 굴림 응답마다 상태를 받으므로 재동기화가 연출 도중에 끼어들지 않음.
task.spawn(function()
	while true do
		local dt = task.wait(1)
		local now = time()
		for player, session in sessions do
			PlayerState.addIncome(session.Data, dt)
			if now - session.LastSync >= RESYNC_INTERVAL then
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

	-- 쿨타임: 허용 오차만큼 일찍 와도 받아주되, 기준 시각은 "원래 가능했던 시각"으로 밀어서
	-- 오차를 반복 악용해도 평균 속도가 빨라지지 않게 합니다.
	local now = time()
	local cooldown = PlayerState.cooldown(session.Data)
	local readyAt = session.LastRoll + cooldown
	if now < readyAt - Config.COOLDOWN_TOLERANCE then
		return { Ok = false, Reason = "cooldown", RetryIn = readyAt - now }
	end
	session.LastRoll = math.max(now, readyAt)

	local luck = PlayerState.luck(session.Data)
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
	local ok = PlayerState.setSetting(session.Data, key, value)
	return { Ok = ok, State = snapshot(session) }
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
