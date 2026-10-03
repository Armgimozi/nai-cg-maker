-- 검수용 채팅 명령 (shared/Commands.luau). 플레이스 주인과 Studio 에서만 듣는다.
-- TextChatCommand 는 서버에서 만들어야 명령 글이 다른 사람 채팅에 나가지 않는다(클라이언트에서 만든 명령은
-- 메시지를 삼키지 못한다). 주인이 아닌 사람이 쳐도 글은 삼켜지고 아무 일도 없다.
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

function DevCommands.run(player: Player, text: any)
	if not DevCommands.allowed(player) then
		return
	end
	local parsed = Commands.parse(text)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session then
		return
	end
	if not parsed then
		reply(player, "모르는 명령이다. /도움", "bad")
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
	if command == "과업" and not data.root then
		reply(player, "영근부터 고른다. 영근에 따라 과업이 달라진다.", "bad")
		return
	end
	local changes = CHANGES[command] and not (command == "초기화" and not parsed.confirmed)
	if changes and PlayerData.backupOnce(player) then
		reply(player, "원래 기록을 따로 보관했다. /복구 확인 으로 언제든 되돌린다.", "good")
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
			reply(
				player,
				"검수 명령을 처음 쓰기 전의 기록으로 되돌린다. 정말이면 /복구 확인",
				"bad"
			)
			return
		end
		local ok, message = PlayerData.restoreBackup(player)
		if ok then
			Characters.applyStats(player, true)
		end
		reply(player, message, if ok then "good" else "bad")
	elseif command == "도움" then
		reply(player, Commands.HELP)
	end
	Sync.state(player)
end

-- 명령을 서버에 만든다. 예전 채팅이면 Player.Chatted 로 듣는다
function DevCommands.setup()
	local TextChatService = game:GetService("TextChatService")
	if TextChatService.ChatVersion ~= Enum.ChatVersion.TextChatService then
		local function listen(player: Player)
			player.Chatted:Connect(function(message)
				if Commands.parse(message) then
					DevCommands.run(player, message)
				end
			end)
		end
		Players.PlayerAdded:Connect(listen)
		for _, player in Players:GetPlayers() do
			listen(player)
		end
		return
	end
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
				DevCommands.run(player, text)
			end
		end)
		command.Parent = TextChatService
	end
end

return DevCommands
