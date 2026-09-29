-- DataStore 저장/불러오기 + 간단한 세션 잠금
--
-- 저장 형식: { Data = PlayerState.Data, Lock = { JobId, Time }? }
-- 세션 잠금: 다른 서버가 아직 이 플레이어를 들고 있으면(서버 이동 직후 등) 잠시 기다렸다가 불러옵니다.
-- 그래야 이전 서버의 마지막 저장이 새 서버 데이터에 덮어써지는 일이 없습니다.

local DataStoreService = game:GetService("DataStoreService")
local RunService = game:GetService("RunService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Config = require(Shared.Config)
local PlayerState = require(Shared.PlayerState)

local LOCK_EXPIRE_SECONDS = Config.AUTOSAVE_INTERVAL * 3
local LOAD_ATTEMPTS = 6
local SAVE_ATTEMPTS = 3

local DataService = {}

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(Config.DATASTORE_NAME)
	end)
	if ok then
		store = result
	else
		warn("[DataService] DataStore 를 열 수 없습니다: " .. tostring(result))
	end
end

local function keyFor(player: Player): string
	return "player_" .. player.UserId
end

-- 반환: data(실패 시 nil), canSave
-- Studio 에서 API 접근이 꺼져 있으면 새 데이터로 플레이만 하고 저장은 하지 않습니다.
function DataService.load(player: Player): (PlayerState.Data?, boolean)
	if not store then
		if RunService:IsStudio() then
			return PlayerState.new(), false
		end
		return nil, false
	end

	for attempt = 1, LOAD_ATTEMPTS do
		local steal = attempt == LOAD_ATTEMPTS
		local blocked = false
		local loaded: any = nil

		local ok, err = pcall(function()
			store:UpdateAsync(keyFor(player), function(record)
				record = if type(record) == "table" then record else {}
				local lock = record.Lock
				if
					not steal
					and type(lock) == "table"
					and lock.JobId ~= game.JobId
					and os.time() - (tonumber(lock.Time) or 0) < LOCK_EXPIRE_SECONDS
				then
					blocked = true
					return nil -- 쓰기 취소
				end
				loaded = record.Data
				record.Lock = { JobId = game.JobId, Time = os.time() }
				return record
			end)
		end)

		if ok and not blocked then
			return PlayerState.reconcile(loaded), true
		end
		if not ok then
			warn(
				string.format(
					"[DataService] %s 불러오기 실패(%d/%d): %s",
					player.Name,
					attempt,
					LOAD_ATTEMPTS,
					tostring(err)
				)
			)
			if RunService:IsStudio() then
				-- 게시 안 된 place 이거나 API 접근이 꺼진 경우: 테스트는 되도록 저장 없이 진행
				warn(
					"[DataService] Studio 에서는 저장 없이 진행합니다. 저장까지 테스트하려면 게임을 게시하고 "
						.. "Game Settings > Security > 'Enable Studio Access to API Services' 를 켜세요."
				)
				return PlayerState.new(), false
			end
		end
		if player.Parent == nil then
			return nil, false
		end
		task.wait(if blocked then 5 else attempt * 1.5)
	end
	return nil, false
end

-- release=true 면 잠금을 풀어 다른 서버가 바로 불러갈 수 있게 합니다(퇴장 시).
function DataService.save(player: Player, data: PlayerState.Data, release: boolean): boolean
	if not store then
		return false
	end
	for attempt = 1, SAVE_ATTEMPTS do
		local takenOver = false
		local ok, err = pcall(function()
			store:UpdateAsync(keyFor(player), function(record)
				record = if type(record) == "table" then record else {}
				local lock = record.Lock
				if type(lock) == "table" and lock.JobId ~= game.JobId then
					-- 잠금 만료 후 다른 서버가 가져갔음: 그쪽 데이터를 덮어쓰지 않음
					takenOver = true
					return nil
				end
				record.Data = data
				record.Lock = if release then nil else { JobId = game.JobId, Time = os.time() }
				return record
			end)
		end)
		if ok then
			if takenOver then
				warn(
					"[DataService] "
						.. player.Name
						.. " 의 데이터를 다른 서버가 사용 중이라 저장을 건너뜁니다."
				)
				return false
			end
			return true
		end
		warn(
			string.format(
				"[DataService] %s 저장 실패(%d/%d): %s",
				player.Name,
				attempt,
				SAVE_ATTEMPTS,
				tostring(err)
			)
		)
		if attempt < SAVE_ATTEMPTS then
			task.wait(attempt * 2)
		end
	end
	return false
end

return DataService
