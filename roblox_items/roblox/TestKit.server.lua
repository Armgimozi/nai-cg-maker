--[[
	TestKit (Script) — ServerScriptService.TestKit

	가져온 방어구·무기를 Studio 에서 바로 확인하는 테스트용 스크립트. 실제 게임에서는 지워도 된다.
	- 스폰하면 DEFAULT_SET 방어구를 입고, 무기·아티팩트를 전부 가방에 받는다.
	- 채팅 명령:
		/armor leather | iron | knight     세트 통째로 입기
		/armor knight helmet               한 부위만 입기 (helmet / chest / greaves)
		/armor off                         전부 벗기
		/give all | <아이템 id>             아이템 받기 (예: /give battle_axe)
]]

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local ItemSystem = ReplicatedStorage:WaitForChild("ItemSystem")
local ArmorService = require(ItemSystem:WaitForChild("ArmorService"))
local ItemService = require(ItemSystem:WaitForChild("ItemService"))

local DEFAULT_SET = "knight"
local GIVE_ALL_ON_SPAWN = true

local function giveAll(player: Player)
	for _, id in ItemService.List() do
		local tool = ItemService.CreateTool(id)
		if tool then
			tool.Parent = player:WaitForChild("Backpack")
		end
	end
end

local function onCharacter(player: Player, character: Model)
	character:WaitForChild("Humanoid")
	-- 몸 부위가 모두 준비될 때까지 잠깐 대기(외형 로딩)
	if not player:HasAppearanceLoaded() then
		player.CharacterAppearanceLoaded:Wait()
	end
	if DEFAULT_SET then
		ArmorService.EquipSet(character, DEFAULT_SET)
	end
	if GIVE_ALL_ON_SPAWN then
		giveAll(player)
	end
end

local function onChat(player: Player, msg: string)
	local args = string.split(string.lower(msg), " ")
	local character = player.Character
	if args[1] == "/armor" and character then
		if args[2] == "off" then
			ArmorService.UnequipAll(character)
		elseif args[3] then
			ArmorService.Equip(character, args[2], args[3])
		elseif args[2] then
			ArmorService.EquipSet(character, args[2])
		end
	elseif args[1] == "/give" then
		if args[2] == "all" then
			giveAll(player)
		elseif args[2] then
			local tool = ItemService.CreateTool(args[2])
			if tool then
				tool.Parent = player.Backpack
			end
		end
	end
end

local function onPlayer(player: Player)
	player.CharacterAdded:Connect(function(character)
		onCharacter(player, character)
	end)
	if player.Character then
		task.spawn(onCharacter, player, player.Character)
	end
	player.Chatted:Connect(function(msg)
		onChat(player, msg)
	end)
end

Players.PlayerAdded:Connect(onPlayer)
for _, p in Players:GetPlayers() do
	onPlayer(p)
end
