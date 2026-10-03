-- 서버와 클라이언트가 함께 쓰는 RemoteEvent 목록.
--
-- Request  (클라 → 서버) action, arg
--     "Meditate" (boolean)   운기조식 시작/중지
--     "Breakthrough"         돌파
--     "UseSkill" (string)    술법 쓰기
--     "Equip" (string)       공법 장착
--     "Unequip" (string)     공법 해제
--     "AssignSkill" { slot, id }  단축칸에 술법 넣기 (id "" 는 비우기)
--     "BindKey" { slot, key }     단축칸 키 바꾸기
--     "StartTask" (string)        과업 내관(미니게임) 시작
--     "SkipTask" (string)         영력을 더 내고 퍼즐 건너뛰기 (천·진영근)
--     "TrialResult" { id, ok, answer, elapsed }  내관 결과
--     "TrialCancel"               내관 그만두기
--     "Choose" { key, value }     영근·칠수·본명 속성 고르기
--     "Eat" (string)              주머니에서 먹기
--     "Travel" (string)           전송진 id 로 떠나기 (영석 삯을 낸다, Currency.travelFee)
--     "Buy" (string)              마을 상점에서 사기 (Currency.WARES 의 id). 상인 곁에서만
--     "Upgrade" (number)          대장간에서 그 칸 무기를 한 등급 올리기. 대장장이 곁에서만
-- State    (서버 → 클라) 내 상태 스냅숏
-- Notify   (서버 → 클라) text, kind
-- Cinematic(서버 → 클라) 화면 연출 { kind = ... }
-- Skill    (서버 → 클라) 술법이 나갔다 { id, cooldown, duration }
-- Trial    (서버 → 클라) 내관을 연다 { id, mode, seed, params, title } / 닫는다 { close = true }
-- Speak    (서버 → 클라) 마을 사람 말풍선 (머리 파트, 대사)
-- Combat   (서버 → 클라) 싸움 { kind = "hit" | "hurt" | "blocked", ... } (화면 위 대상 창, 맞은 느낌)

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local FOLDER_NAME = "BlockSuseonNet"
local EVENTS = { "Request", "State", "Notify", "Cinematic", "Skill", "Trial", "Speak", "Combat" }

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
