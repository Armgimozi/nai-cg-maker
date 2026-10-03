-- 검수용 채팅 명령 (shared/Commands.luau). 플레이스 주인과 Studio 에서만 듣는다.
-- TextChatCommand 는 서버에서 만들어야 명령 글이 다른 사람 채팅에 나가지 않는다(클라이언트에서 만든 명령은
-- 메시지를 삼키지 못한다). 주인이 아닌 사람이 치면 글은 삼켜지고 "주인만 쓴다"는 알림만 간다.
-- 기록을 바꾸는 명령은 처음 쓸 때 원래 기록을 따로 보관한다(PlayerData.backupOnce, /복구 확인).

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Commands = require(Shared.Commands)
local Progression = require(Shared.Progression)
local Tasks = require(Shared.Tasks)
local Realms = require(Shared.Realms)
local Balance = require(Shared.Balance)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Cultivation = require(script.Parent.Cultivation)
local DayNight = require(script.Parent.DayNight)
local TaskService = require(script.Parent.TaskService)

local DevCommands = {}

function DevCommands.allowed(player: Player): boolean
	if RunService:IsStudio() then
		return true
	end
	return game.CreatorType == Enum.CreatorType.User and player.UserId == game.CreatorId
end

-- 기록을 바꾸는 명령 (처음 쓸 때 원래 기록을 보관한다)
local CHANGES = {
	["경지"] = true,
	["단계"] = true,
	["영력"] = true,
	["과업"] = true,
	["주머니"] = true,
	["초기화"] = true,
}

local function reply(player: Player, text: string, kind: string?)
	Sync.notify(player, "[검수] " .. text, kind or "info")
end

-- 명령은 한 사람에 하나씩 (보관 중에 다음 명령이 먼저 끝나지 않게)
local busy: { [Player]: boolean } = {}

local function formatAge(savedAt: number?): string
	if not savedAt then
		return "보관한 때는 모른다"
	end
	local minutes = math.max(0, os.time() - savedAt) // 60
	if minutes < 60 then
		return string.format("%d분 전에 보관", minutes)
	elseif minutes < 60 * 24 then
		return string.format("%d시간 전에 보관", minutes // 60)
	end
	return string.format("%d일 전에 보관", minutes // (60 * 24))
end

local function runCommand(player: Player, text: any)
	local parsed = Commands.parse(text)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session then
		return
	end
	if not parsed then
		reply(player, "모르는 명령이다. /검수 로 목록을 본다.", "bad")
		return
	end
	if parsed.error then
		reply(player, parsed.error, "bad")
		return
	end
	if session.tribulation or session.trial or session.ritual then
		reply(player, "천겁, 내관, 제의가 끝난 뒤에 쓴다.", "bad")
		return
	end

	local command = parsed.command
	if command == "과업" and not data.root and data.step > 1 then
		reply(player, "영근부터 고른다. 영근에 따라 과업이 달라진다.", "bad")
		return
	end
	local changes = CHANGES[command] and not (command == "초기화" and not parsed.confirmed)
	if changes then
		local status = PlayerData.backupOnce(player)
		if status == "failed" then
			reply(player, "원래 기록을 보관하지 못해 명령을 멈췄다. 잠시 뒤 다시.", "bad")
			return
		elseif status == "created" then
			reply(player, "원래 기록을 따로 보관했다. /복구 확인 으로 언제든 되돌린다.", "good")
		end
		-- 보관하는 동안 상황이 바뀌었을 수 있다
		if PlayerData.get(player) ~= data or Session.get(player) ~= session then
			return
		end
		if session.tribulation or session.trial or session.ritual then
			reply(player, "그사이 천겁, 내관, 제의가 시작됐다. 끝난 뒤에 다시.", "bad")
			return
		end
	end

	if command == "경지" or command == "단계" then
		local slotsBefore = Progression.slots(data)
		local notes = Progression.jumpTo(data, parsed.step :: number)
		Characters.applyStats(player, true)
		Sync.announceSlots(player, slotsBefore)
		for _, note in notes do
			Sync.notify(player, note, "good")
		end
		reply(player, string.format("%s(%d단계)로 옮겼다.", Realms.label(data.step), data.step), "good")
	elseif command == "영력" then
		data.qi = Progression.requiredQi(data)
		reply(player, "영력을 채웠다.", "good")
		Cultivation.settle(player)
	elseif command == "과업" then
		local skipped = {}
		for _, task in (Tasks.list(data)) do
			if task.kind == "choose" then
				if not Tasks.isDone(data, task) then
					table.insert(skipped, task.label)
				end
			elseif task.kind == "have" then
				if not Tasks.isDone(data, task) then
					Progression.addItem(data, task.item or "pill", task.max)
				end
			else
				Tasks.set(data, task.id, task.max)
			end
		end
		reply(
			player,
			if #skipped > 0
				then "과업을 끝냈다. 고르기는 직접 한다: " .. table.concat(skipped, ", ")
				else "과업을 끝냈다.",
			"good"
		)
		Cultivation.settle(player)
	elseif command == "주머니" then
		TaskService.giveItem(player, parsed.item :: string, parsed.count)
		reply(
			player,
			string.format("%s %d개를 넣었다.", Balance.ITEMS[parsed.item :: string].name, parsed.count or 1),
			"good"
		)
	elseif command == "시간" then
		DayNight.setPhase(parsed.phase :: string)
		reply(player, "시간을 옮겼다.", "good")
	elseif command == "초기화" then
		if not parsed.confirmed then
			reply(player, "기록을 모두 지우고 범인부터 시작한다. 정말이면 /초기화 확인", "bad")
			return
		end
		local fresh = Progression.newData()
		for key in data do
			(data :: any)[key] = nil
		end
		for key, value in fresh do
			(data :: any)[key] = value
		end
		Characters.applyStats(player, true)
		reply(player, "기록을 지웠다. 범인부터 다시 시작한다.", "good")
	elseif command == "복구" then
		if not parsed.confirmed then
			local step, savedAt, err = PlayerData.describeBackup(player)
			if not step then
				reply(player, err or "보관본이 없다.", "bad")
			else
				reply(
					player,
					string.format(
						"보관본: %s, %s. 지금 기록을 버리고 되돌리려면 /복구 확인",
						Realms.label(step),
						formatAge(savedAt)
					)
				)
			end
			return
		end
		local ok, message = PlayerData.restoreBackup(player, function()
			return PlayerData.get(player) == data
				and Session.get(player) == session
				and not session.tribulation
				and not session.trial
				and not session.ritual
		end)
		if ok then
			Characters.applyStats(player, true)
		end
		reply(player, message, if ok then "good" else "bad")
	elseif command == "검수" then
		reply(player, Commands.HELP)
	end
	Sync.state(player)
end

function DevCommands.run(player: Player, text: any)
	if not DevCommands.allowed(player) then
		-- 서버에 만든 명령이라 누가 쳐도 글이 삼켜진다. 아무 일 없이 사라지지 않게 알린다
		Sync.notify(player, "그 명령은 플레이스 주인만 쓴다.", "bad")
		return
	end
	if busy[player] then
		reply(player, "앞 명령을 처리하는 중이다. 잠시 뒤 다시.", "bad")
		return
	end
	busy[player] = true
	local ok, err = pcall(runCommand, player, text)
	busy[player] = nil
	if not ok then
		warn("[블록수선전] 검수 명령 오류:", err)
		reply(player, "명령을 처리하다 오류가 났다.", "bad")
	end
end

-- 명령을 서버에 만든다. 지금 Roblox 는 TextChatService 만 쓰므로 ChatVersion 값과 상관없이 만든다.
-- 한글 별칭이 채팅 명령으로 잡히지 않을 때를 대비해 Player.Chatted 로도 듣는다(잡힌 명령은 글이 삼켜져
-- Chatted 가 오지 않는다). 같은 글이 두 길로 오면 한 번만 실행한다.
local recent: { [Player]: { text: string, at: number } } = {}

local function handle(player: Player, text: string)
	local last = recent[player]
	if last and last.text == text and os.clock() - last.at < 1 then
		return
	end
	recent[player] = { text = text, at = os.clock() }
	DevCommands.run(player, text)
end

function DevCommands.setup()
	local TextChatService = game:GetService("TextChatService")
	for _, alias in Commands.ALIASES do
		local command = Instance.new("TextChatCommand")
		command.Name = "BlockSuseon_" .. alias[2]
		command.PrimaryAlias = "/" .. alias[1]
		command.SecondaryAlias = "/" .. alias[2]
		pcall(function()
			-- 다른 사람의 자동 완성에 검수 명령이 뜨지 않게
			(command :: any).AutocompleteVisible = false
		end)
		command.Triggered:Connect(function(source: TextSource, text: string)
			local player = Players:GetPlayerByUserId(source.UserId)
			if player then
				handle(player, text)
			end
		end)
		command.Parent = TextChatService
	end

	local function listen(player: Player)
		player.Chatted:Connect(function(message)
			if Commands.parse(message) then
				handle(player, message)
			end
		end)
	end
	Players.PlayerAdded:Connect(listen)
	for _, player in Players:GetPlayers() do
		listen(player)
	end
	Players.PlayerRemoving:Connect(function(player)
		recent[player] = nil
	end)
end

return DevCommands
