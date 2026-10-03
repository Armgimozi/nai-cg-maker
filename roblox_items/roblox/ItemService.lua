--[[
	ItemService (ModuleScript) — ReplicatedStorage.ItemSystem.ItemService

	Meshy 로 만든 무기·아티팩트를 손에 드는 Tool 이나 바닥/진열용 모델로 만든다.
	- 모든 모델은 "날/머리가 위(+Y), 날 끝이 앞(-Z)" 으로 정리돼 있고,
	  손잡이 위치(Grip)와 실제 크기(스터드)가 ItemData 에 들어있다.
	- 빛나는 아이템(지팡이 수정, 오브, 룬석, 반지, 부적)은 PointLight 를 자동으로 단다.

	사용:
		local ItemService = require(ReplicatedStorage.ItemSystem.ItemService)
		local tool = ItemService.CreateTool("iron_longsword")
		tool.Parent = player.Backpack

		local relic = ItemService.CreateDisplay("arcane_orb", CFrame.new(0, 5, 0))
		relic.Parent = workspace

		ItemService.List("weapon")   --> { "iron_longsword", "battle_axe", ... }

	공격 판정·애니메이션 등 게임 로직은 넣지 않았다 — Tool.Activated 에 연결해서 쓰면 된다.
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local ItemData = require(script.Parent.ItemData)

local ItemService = {}

local function itemsFolder(): Instance
	return ReplicatedStorage:WaitForChild("ItemAssets"):WaitForChild("Items")
end

local function findMesh(id: string): BasePart?
	local found = itemsFolder():FindFirstChild(id, true)
	if found and found:IsA("BasePart") then
		return found
	end
	if found then
		return found:FindFirstChildWhichIsA("BasePart", true)
	end
	return nil
end

local function makePart(id: string): (BasePart?, any)
	local info = ItemData.Items[id]
	if not info then
		warn("[ItemService] ItemData 에 없는 아이템: " .. tostring(id))
		return nil, nil
	end
	local src = findMesh(id)
	if not src then
		warn(("[ItemService] ReplicatedStorage.ItemAssets.Items 에 '%s' 가 없습니다"):format(id))
		return nil, nil
	end
	local part = src:Clone()
	part.Size = info.size
	part.CanCollide = false
	part.CanQuery = true
	part.CanTouch = true
	part.Massless = true
	if info.glow then
		local light = Instance.new("PointLight")
		light.Color = info.glow
		light.Range = info.kind == "weapon" and 9 or 7
		light.Brightness = 1.4
		light.Shadows = false
		light.Parent = part
	end
	return part, info
end

function ItemService.CreateTool(id: string): Tool?
	local handle, info = makePart(id)
	if not handle then
		return nil
	end
	handle.Name = "Handle"
	handle.Anchored = false

	local tool = Instance.new("Tool")
	tool.Name = info.name
	tool.ToolTip = info.name
	tool.RequiresHandle = true
	tool.CanBeDropped = false
	-- Handle 안의 손잡이 지점이 손(RightGripAttachment)에 오도록
	tool.Grip = CFrame.new(info.grip)
	tool:SetAttribute("ItemId", id)
	tool:SetAttribute("ItemKind", info.kind)
	handle.Parent = tool
	return tool
end

function ItemService.CreateDisplay(id: string, cframe: CFrame?): BasePart?
	local part, info = makePart(id)
	if not part then
		return nil
	end
	part.Name = info.name
	part.Anchored = true
	part.CanCollide = true
	part.Massless = false
	part:SetAttribute("ItemId", id)
	-- 바닥에 세워 두기: 기준 CFrame 이 바닥 높이가 되도록
	part.CFrame = (cframe or CFrame.identity) * CFrame.new(0, info.size.Y / 2, 0)
	return part
end

function ItemService.List(kind: string?): { string }
	local ids = {}
	for id, info in ItemData.Items do
		if kind == nil or info.kind == kind then
			table.insert(ids, id)
		end
	end
	table.sort(ids)
	return ids
end

return ItemService
