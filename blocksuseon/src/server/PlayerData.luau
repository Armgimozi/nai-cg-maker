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

-- 저장했으면 true
function PlayerData.save(player: Player): boolean
	local profile = profiles[player]
	if not profile or not profile.canSave or not store then
		return false
	end
	local ok, err = pcall(function()
		store:UpdateAsync(keyFor(player), function()
			return profile.data
		end)
	end)
	if not ok then
		warn(string.format("[블록수선전] %s 저장 실패: %s", player.Name, tostring(err)))
	end
	return ok
end

-- 검수 명령 ------------------------------------------------------------------------------
-- 검수 명령으로 기록을 처음 바꾸기 전에 지금 기록을 따로 한 번 보관한다. 저장소에 보관본이 이미 있으면
-- 덮어쓰지 않는다 (가장 처음 검수하기 전의 기록이 남는다). /복구 확인 으로 되돌린다.

local BACKUP_SUFFIX = "_before_dev"

local function deepCopy(value: any): any
	if type(value) ~= "table" then
		return value
	end
	local out = {}
	for key, item in value do
		out[key] = deepCopy(item)
	end
	return out
end

-- 반환: "created"(새로 보관) | "exists"(이미 있음) | "failed"(저장소 오류) | "unavailable"(저장하지 않는 접속)
function PlayerData.backupOnce(player: Player): string
	local profile = profiles[player] :: any
	if not profile or not profile.canSave or not store then
		return "unavailable"
	end
	if profile.backedUp then
		return "exists"
	end
	local snapshot = { data = deepCopy(profile.data), savedAt = os.time() }
	local created = false
	local ok, err = pcall(function()
		store:UpdateAsync(keyFor(player) .. BACKUP_SUFFIX, function(old)
			if old ~= nil then
				return nil -- 이미 있으면 그대로 둔다
			end
			created = true
			return snapshot
		end)
	end)
	if not ok then
		warn(string.format("[블록수선전] %s 보관 실패: %s", player.Name, tostring(err)))
		return "failed"
	end
	profile.backedUp = true
	return if created then "created" else "exists"
end

-- 보관본 읽기. 반환: 보관본 기록, 보관한 시각(os.time, 모르면 nil), 오류 문구
local function readBackup(player: Player): (any, number?, string?)
	local ok, saved = pcall(function()
		return store and store:GetAsync(keyFor(player) .. BACKUP_SUFFIX)
	end)
	if not ok then
		return nil, nil, "보관본을 읽지 못했다: " .. tostring(saved)
	end
	if saved == nil then
		return nil, nil, "보관본이 없다. 검수 명령으로 기록을 바꾼 적이 없다."
	end
	if type(saved) == "table" and type(saved.data) == "table" then
		return saved.data, saved.savedAt, nil
	end
	return saved, nil, nil
end

-- /복구 확인 전에 보여 줄 보관본 설명. 반환: 있으면 (단계, 보관 시각)
function PlayerData.describeBackup(player: Player): (number?, number?, string?)
	local profile = profiles[player]
	if not profile or not profile.canSave or not store then
		return nil, nil, "저장소에 연결하지 못했다."
	end
	local saved, savedAt, err = readBackup(player)
	if not saved then
		return nil, nil, err
	end
	return Progression.reconcile(saved).step, savedAt, nil
end

-- 보관본으로 되돌린다. 되돌린 기록을 먼저 저장하고, 저장에 성공했을 때만 보관본을 지운다.
-- canApply 는 보관본을 읽은 뒤(기다린 뒤) 바꿔도 되는지 다시 묻는다. 반환: 성공했는가, 알릴 문구
function PlayerData.restoreBackup(player: Player, canApply: () -> boolean): (boolean, string)
	local profile = profiles[player] :: any
	if not profile or not profile.canSave or not store then
		return false, "저장소에 연결하지 못해 되돌릴 수 없다."
	end
	local saved, _, err = readBackup(player)
	if not saved then
		return false, err or "보관본이 없다."
	end
	if profiles[player] ~= profile or not canApply() then
		return false, "그사이 상태가 바뀌어 되돌리지 않았다. 다시 친다."
	end
	local restored = Progression.reconcile(saved)
	local data = profile.data :: any
	for key in data do
		data[key] = nil
	end
	for key, value in restored :: any do
		data[key] = value
	end
	local ok, saveErr = pcall(function()
		store:UpdateAsync(keyFor(player), function()
			return profile.data
		end)
	end)
	if not ok then
		warn(string.format("[블록수선전] %s 복구 저장 실패: %s", player.Name, tostring(saveErr)))
		return true, "검수하기 전의 기록으로 되돌렸다. 저장이 늦어 보관본은 남겨 두었다."
	end
	local removed = pcall(function()
		store:RemoveAsync(keyFor(player) .. BACKUP_SUFFIX)
	end)
	if removed then
		profile.backedUp = false
		return true, "검수하기 전의 기록으로 되돌렸다. 보관본은 지웠다."
	end
	return true, "검수하기 전의 기록으로 되돌렸다. 보관본은 남아 있다."
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
