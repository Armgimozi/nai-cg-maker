-- 검수용 채팅 명령 (shared/Commands.luau). 플레이스 주인과 Studio 에서만 듣는다.
-- 클라이언트가 TextChatCommand 로 받은 글을 Request "Dev" 로 넘기고, 서버가 주인인지 다시 확인한다.

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
	if not parsed or not data or not session then
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
	elseif command == "도움" then
		reply(player, Commands.HELP)
	end
	Sync.state(player)
end

return DevCommands
