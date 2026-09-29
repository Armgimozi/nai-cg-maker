-- 서버 진입점: 플레이어 데이터 관리, 굴림 판정(서버 권위), 상점, 알림

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Auras = require(Shared.Auras)
local Config = require(Shared.Config)
local Format = require(Shared.Format)
local Net = require(Shared.Net)
local PlayerState = require(Shared.PlayerState)
local RollLogic = require(Shared.RollLogic)

local AuraDisplay = require(script.AuraDisplay)
local DataService = require(script.DataService)

-- 희귀 알림은 굴린 사람의 연출(최대 약 3초)이 끝난 뒤에 나가도록 지연
local ANNOUNCE_DELAY = 3.2

type Session = {
	Data: PlayerState.Data,
	CanSave: boolean,
	LastRoll: number,
	Revision: number,
	Stats: { Rolls: IntValue, Best: StringValue },
}

local sessions: { [Player]: Session } = {}
local rng = Random.new()

local function nextNumber(): number
	return rng:NextNumber()
end

local function snapshot(session: Session): PlayerState.Snapshot
	session.Revision += 1
	return PlayerState.snapshot(session.Data, session.Revision)
end

local function pushState(player: Player)
	local session = sessions[player]
	if session then
		Net.event("State"):FireClient(player, snapshot(session))
	end
end

local function updateStats(session: Session)
	session.Stats.Rolls.Value = session.Data.Rolls
	local best = PlayerState.best(session.Data)
	session.Stats.Best.Value = if best then best.Name else "-"
end

local function refreshAura(player: Player)
	local session = sessions[player]
	local aura = if session and session.Data.Equipped then Auras.ById[session.Data.Equipped] else nil
	AuraDisplay.apply(player.Character, aura)
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
	-- 머리/몸통이 생길 때까지 기다린 뒤 효과를 붙임
	character:WaitForChild("Head", 10)
	character:WaitForChild("HumanoidRootPart", 10)
	if player.Character == character then
		refreshAura(player)
	end
end

-- BindToClose 가 진행 중인 저장을 기다릴 수 있도록 개수를 셈
local savesInFlight = 0

local function trackedSave(player: Player, data: PlayerState.Data, release: boolean)
	savesInFlight += 1
	DataService.save(player, data, release)
	savesInFlight -= 1
end

local function onPlayerAdded(player: Player)
	local data, canSave = DataService.load(player)
	if player.Parent == nil then
		-- 불러오는 동안 나감: 방금 건 세션 잠금을 풀어 둬야 다음 접속이 기다리지 않음
		if data and canSave then
			trackedSave(player, data, true)
		end
		return
	end
	if not data then
		player:Kick("데이터를 불러오지 못했습니다. 잠시 후 다시 접속해 주세요.")
		return
	end

	local session: Session = {
		Data = data,
		CanSave = canSave,
		LastRoll = -math.huge,
		Revision = 0,
		Stats = createLeaderstats(player),
	}
	sessions[player] = session
	updateStats(session)

	player.CharacterAdded:Connect(function(character)
		onCharacter(player, character)
	end)
	if player.Character then
		task.spawn(onCharacter, player, player.Character)
	end
	pushState(player)
end

local function saveAndRelease(player: Player)
	local session = sessions[player]
	if not session then
		return
	end
	sessions[player] = nil
	if session.CanSave then
		trackedSave(player, session.Data, true)
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
			if session.CanSave then
				task.spawn(DataService.save, player, session.Data, false)
			end
		end
	end
end)

-- 물약 시간 감소 (접속 중에만)
task.spawn(function()
	while true do
		local dt = task.wait(1)
		for player, session in sessions do
			if PlayerState.tickPotions(session.Data, dt) then
				pushState(player)
			end
		end
	end
end)

local function announce(player: Player, aura: Auras.Aura, rollNumber: number)
	Net.event("Announce"):FireAllClients({
		Name = player.DisplayName,
		AuraId = aura.Id,
		Rolls = rollNumber,
	})
	print(
		string.format(
			"[AuraRNG] %s 님이 %s (%s) 획득 — %d번째 굴림",
			player.Name,
			aura.Name,
			Format.oneIn(aura.OneIn),
			rollNumber
		)
	)
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

	local luck, lucky = PlayerState.rollLuck(session.Data)
	local aura = RollLogic.roll(Auras.RarestFirst, luck, nextNumber)
	local coins, isNew = PlayerState.applyRoll(session.Data, aura)
	updateStats(session)

	if aura.OneIn >= Config.ANNOUNCE_ONE_IN then
		task.delay(ANNOUNCE_DELAY, announce, player, aura, session.Data.Rolls)
	end

	return {
		Ok = true,
		AuraId = aura.Id,
		Luck = luck,
		Lucky = lucky,
		Coins = coins,
		IsNew = isNew,
		State = snapshot(session),
	}
end

Net.fn("Equip").OnServerInvoke = function(player: Player, auraId: any)
	local session = sessions[player]
	if not session then
		return { Ok = false }
	end
	local ok = PlayerState.equip(session.Data, auraId)
	if ok then
		refreshAura(player)
	end
	return { Ok = ok, State = snapshot(session) }
end

Net.fn("BuyPotion").OnServerInvoke = function(player: Player, potionId: any)
	local session = sessions[player]
	if not session then
		return { Ok = false, Reason = "데이터를 불러오는 중입니다" }
	end
	local ok, reason = PlayerState.buyPotion(session.Data, potionId)
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
