-- DataStore 저장/불러오기.
-- 저장소에 연결하지 못하면(예: Studio 에서 API 접근이 꺼져 있을 때) 이번 접속은
-- 기본값으로 진행하고, 남의 기록을 덮어쓰지 않도록 저장하지 않는다.

local DataStoreService = game:GetService("DataStoreService")
local RunService = game:GetService("RunService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Progression = require(Shared.Progression)

local STORE_NAME = "BlockSuseon_v1"
local AUTOSAVE_INTERVAL = 90

type Profile = {
	data: Progression.Data,
	canSave: boolean,
}

local PlayerData = {}

local profiles: { [Player]: Profile } = {}

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(STORE_NAME)
	end)
	if ok then
		store = result
	else
		warn("[블록수선전] DataStore 를 열지 못했다:", result)
	end
end

local function keyFor(player: Player): string
	return "player_" .. player.UserId
end

function PlayerData.load(player: Player): (Progression.Data, boolean)
	local saved, canSave = nil, false
	if store then
		local attempts = if RunService:IsStudio() then 1 else 3
		for attempt = 1, attempts do
			local ok, result = pcall(function()
				return store:GetAsync(keyFor(player))
			end)
			if ok then
				saved, canSave = result, true
				break
			end
			warn(
				string.format(
					"[블록수선전] %s 불러오기 실패(%d/%d): %s",
					player.Name,
					attempt,
					attempts,
					tostring(result)
				)
			)
			if attempt < attempts then
				task.wait(attempt * 2)
			end
		end
	end

	local data = Progression.reconcile(saved)
	profiles[player] = { data = data, canSave = canSave }
	return data, canSave
end

function PlayerData.get(player: Player): Progression.Data?
	local profile = profiles[player]
	return profile and profile.data
end

function PlayerData.canSave(player: Player): boolean
	local profile = profiles[player]
	return profile ~= nil and profile.canSave
end

function PlayerData.save(player: Player)
	local profile = profiles[player]
	if not profile or not profile.canSave or not store then
		return
	end
	local ok, err = pcall(function()
		store:UpdateAsync(keyFor(player), function()
			return profile.data
		end)
	end)
	if not ok then
		warn(string.format("[블록수선전] %s 저장 실패: %s", player.Name, tostring(err)))
	end
end

function PlayerData.release(player: Player)
	PlayerData.save(player)
	profiles[player] = nil
end

function PlayerData.startAutosave()
	task.spawn(function()
		while true do
			task.wait(AUTOSAVE_INTERVAL)
			for player in profiles do
				task.spawn(PlayerData.save, player)
			end
		end
	end)

	game:BindToClose(function()
		local pending = 0
		for player in profiles do
			pending += 1
			task.spawn(function()
				PlayerData.save(player)
				pending -= 1
			end)
		end
		local deadline = os.clock() + 25
		while pending > 0 and os.clock() < deadline do
			task.wait(0.1)
		end
	end)
end

return PlayerData
