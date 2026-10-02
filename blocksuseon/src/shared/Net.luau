-- 서버와 클라이언트가 함께 쓰는 RemoteEvent 목록.
--
-- Request  (클라 → 서버) action, arg
--     "Meditate" (boolean)   운기조식 시작/중지
--     "Breakthrough"         돌파
--     "BuyInsight" (string)  깨달음 강화
-- State    (서버 → 클라) 내 상태 스냅숏
-- Notify   (서버 → 클라) text, kind
-- Cinematic(서버 → 클라) 화면 연출 { kind = ... }

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local FOLDER_NAME = "BlockSuseonNet"
local EVENTS = { "Request", "State", "Notify", "Cinematic" }

local Net = {}

function Net.get(): { [string]: RemoteEvent }
	local remotes = {}
	if RunService:IsServer() then
		local folder = ReplicatedStorage:FindFirstChild(FOLDER_NAME)
		if not folder then
			folder = Instance.new("Folder")
			folder.Name = FOLDER_NAME
			folder.Parent = ReplicatedStorage
		end
		for _, name in EVENTS do
			local event = folder:FindFirstChild(name)
			if not event then
				event = Instance.new("RemoteEvent")
				event.Name = name
				event.Parent = folder
			end
			remotes[name] = event
		end
	else
		local folder = ReplicatedStorage:WaitForChild(FOLDER_NAME)
		for _, name in EVENTS do
			remotes[name] = folder:WaitForChild(name)
		end
	end
	return remotes
end

return Net
