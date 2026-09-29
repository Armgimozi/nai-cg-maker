-- 원격 통신 객체. 서버가 처음 require 할 때 만들고, 클라이언트는 생길 때까지 기다립니다.
-- (Rojo 없이 Studio 에 직접 복사해도 따로 RemoteEvent 를 만들 필요가 없도록)

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local FOLDER_NAME = "LandmarkRNGRemotes"

local FUNCTIONS = {
	"GetState", -- () -> Snapshot?
	"Roll", -- () -> RollResponse (DESIGN.md 참고)
	"Feature", -- (landmarkId?) -> { Ok, State }
	"BuyUpgrade", -- (upgradeId) -> { Ok, Reason?, State }
	"SetSetting", -- (key, value) -> { Ok, State }
	"Teleport", -- ("Park" | "Plaza") -> { Ok }
}

local EVENTS = {
	"State", -- 서버 -> 클라: Snapshot (관광 수입 등 서버 쪽 변화)
	"Announce", -- 서버 -> 모두: 희귀 명소 발견 "뉴스 속보"
}

local folder: Folder
if RunService:IsServer() then
	folder = Instance.new("Folder")
	folder.Name = FOLDER_NAME
	for _, name in FUNCTIONS do
		local remote = Instance.new("RemoteFunction")
		remote.Name = name
		remote.Parent = folder
	end
	for _, name in EVENTS do
		local remote = Instance.new("RemoteEvent")
		remote.Name = name
		remote.Parent = folder
	end
	folder.Parent = ReplicatedStorage
else
	folder = ReplicatedStorage:WaitForChild(FOLDER_NAME) :: Folder
end

local Net = {}

function Net.fn(name: string): RemoteFunction
	return folder:WaitForChild(name) :: RemoteFunction
end

function Net.event(name: string): RemoteEvent
	return folder:WaitForChild(name) :: RemoteEvent
end

return Net
