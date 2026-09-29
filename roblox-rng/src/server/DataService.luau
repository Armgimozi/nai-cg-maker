-- DataStore 저장/불러오기 + 세션 잠금
--
-- 저장 형식: { Data = PlayerState.Data, Lock = { Id, JobId, Time }? }
-- 세션 잠금: 불러올 때마다 새 잠금 Id 를 발급하고, 저장은 그 Id 가 기록에 그대로 있을 때만 합니다.
--   · 이전 세션(다른 서버든 같은 서버 재접속이든)이 아직 저장 중이면 잠시 기다렸다가 불러옴
--   · 퇴장 저장으로 잠금이 풀린 뒤 늦게 도착한 자동 저장은 무시됨(잠금을 다시 걸지 않음)
--   · 잠금이 만료되어 다른 세션이 가져갔으면 그쪽 데이터를 덮어쓰지 않음

local DataStoreService = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")
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

local function newLock(lockId: string)
	return { Id = lockId, JobId = game.JobId, Time = os.time() }
end

-- 반환: data(실패 시 nil), lockId(nil 이면 저장하지 않음)
-- Studio 에서 API 접근이 꺼져 있으면 새 데이터로 플레이만 하고 저장은 하지 않습니다.
function DataService.load(player: Player): (PlayerState.Data?, string?)
	if not store then
		if RunService:IsStudio() then
			return PlayerState.new(), nil
		end
		return nil, nil
	end

	local lockId = HttpService:GenerateGUID(false)
	for attempt = 1, LOAD_ATTEMPTS do
		local steal = attempt == LOAD_ATTEMPTS
		local blocked = false
		local loaded: any = nil

		local ok, err = pcall(function()
			store:UpdateAsync(keyFor(player), function(record)
				-- UpdateAsync 는 충돌 시 이 함수를 다시 부를 수 있으므로 결과 변수는 매번 초기화
				blocked = false
				loaded = nil
				record = if type(record) == "table" then record else {}
				local lock = record.Lock
				if
					not steal
					and type(lock) == "table"
					and lock.Id ~= lockId
					and os.time() - (tonumber(lock.Time) or 0) < LOCK_EXPIRE_SECONDS
				then
					blocked = true
					return nil -- 쓰기 취소
				end
				loaded = record.Data
				record.Lock = newLock(lockId)
				return record
			end)
		end)

		if ok and not blocked then
			return PlayerState.reconcile(loaded), lockId
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
				return PlayerState.new(), nil
			end
		end
		if player.Parent == nil then
			return nil, nil
		end
		task.wait(if blocked then 5 else attempt * 1.5)
	end
	return nil, nil
end

-- lockId: load 가 돌려준 값. release=true 면 잠금을 풀어 다음 세션이 바로 불러갈 수 있게 합니다(퇴장 시).
function DataService.save(player: Player, data: PlayerState.Data, lockId: string, release: boolean): boolean
	if not store then
		return false
	end
	for attempt = 1, SAVE_ATTEMPTS do
		local stale = false
		local ok, err = pcall(function()
			store:UpdateAsync(keyFor(player), function(record)
				stale = false
				record = if type(record) == "table" then record else {}
				local lock = record.Lock
				if type(lock) ~= "table" or lock.Id ~= lockId then
					-- 이미 풀린 잠금(퇴장 저장 완료)이거나 다른 세션이 가져간 경우: 덮어쓰지 않음
					stale = true
					return nil
				end
				record.Data = data
				record.Lock = if release then nil else newLock(lockId)
				return record
			end)
		end)
		if ok then
			if stale then
				warn(
					"[DataService] "
						.. player.Name
						.. " 의 세션이 이미 끝났거나 다른 세션이 데이터를 사용 중이라 저장을 건너뜁니다."
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
