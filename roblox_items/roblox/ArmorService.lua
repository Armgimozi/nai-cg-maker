--[[
	ArmorService (ModuleScript) — ReplicatedStorage.ItemSystem.ArmorService

	코드로 모델링한 방어구(투구/갑옷/각반)를 캐릭터 몸에 맞춰 붙인다.
	- 각 방어구 파일(예: knight_chest)은 "붙을 부위 이름"으로 된 MeshPart 들의 묶음이다
	  (UpperTorso, LowerTorso, RightUpperArm, ...).
	- 부위의 실제 크기를 읽어 방어구를 늘이고 줄이므로 체형(키/폭/Rthro)이 달라도 맞는다.
	- R15 기준으로 만들었지만 R6 캐릭터도 지원한다(몸통/팔/다리 안의 가상 구역에 배치).

	사용:
		local ArmorService = require(ReplicatedStorage.ItemSystem.ArmorService)
		ArmorService.Equip(character, "knight", "helmet")   -- 세트: leather / iron / knight
		ArmorService.EquipSet(character, "iron")            -- 투구+갑옷+각반 한 번에
		ArmorService.Unequip(character, "chest")
		ArmorService.UnequipAll(character)
		ArmorService.GetEquipped(character) --> { helmet = "knight", chest = "iron", ... }
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local ItemData = require(script.Parent.ItemData)

local ArmorService = {}

ArmorService.SLOTS = { "helmet", "chest", "greaves" }
-- 투구를 쓰면 머리카락/모자 액세서리를 숨긴다(투구를 뚫고 나오는 것 방지).
ArmorService.HIDE_HAIR_UNDER_HELMET = true

-- 방어구 원본이 들어있는 폴더 (README 의 "가져오기" 참고)
local function armorFolder(): Instance
	return ReplicatedStorage:WaitForChild("ItemAssets"):WaitForChild("Armor")
end

-- 방어구를 설계한 기준 R15 부위 크기(스터드)
local R15_REF = {
	Head = Vector3.new(1.2, 1.2, 1.2),
	UpperTorso = Vector3.new(2, 1.6, 1),
	LowerTorso = Vector3.new(2, 0.4, 1),
	RightUpperArm = Vector3.new(1, 1.169, 1),
	LeftUpperArm = Vector3.new(1, 1.169, 1),
	RightUpperLeg = Vector3.new(1, 1.217, 1),
	LeftUpperLeg = Vector3.new(1, 1.217, 1),
	RightLowerLeg = Vector3.new(1, 1.193, 1),
	LeftLowerLeg = Vector3.new(1, 1.193, 1),
	RightFoot = Vector3.new(1, 0.3, 1),
	LeftFoot = Vector3.new(1, 0.3, 1),
}

-- R6: R15 부위 → (R6 부위, 그 안의 중심, 그 구역 크기) — R6 기본 크기 기준
local R6_BASE = {
	Torso = Vector3.new(2, 2, 1),
	["Right Arm"] = Vector3.new(1, 2, 1),
	["Left Arm"] = Vector3.new(1, 2, 1),
	["Right Leg"] = Vector3.new(1, 2, 1),
	["Left Leg"] = Vector3.new(1, 2, 1),
}
local R6_MAP = {
	UpperTorso = { "Torso", Vector3.new(0, 0.2, 0), Vector3.new(2, 1.6, 1) },
	LowerTorso = { "Torso", Vector3.new(0, -0.8, 0), Vector3.new(2, 0.4, 1) },
	RightUpperArm = { "Right Arm", Vector3.new(0, 0.536, 0), Vector3.new(1, 0.927, 1) },
	LeftUpperArm = { "Left Arm", Vector3.new(0, 0.536, 0), Vector3.new(1, 0.927, 1) },
	RightUpperLeg = { "Right Leg", Vector3.new(0, 0.551, 0), Vector3.new(1, 0.898, 1) },
	LeftUpperLeg = { "Left Leg", Vector3.new(0, 0.551, 0), Vector3.new(1, 0.898, 1) },
	RightLowerLeg = { "Right Leg", Vector3.new(0, -0.338, 0), Vector3.new(1, 0.88, 1) },
	LeftLowerLeg = { "Left Leg", Vector3.new(0, -0.338, 0), Vector3.new(1, 0.88, 1) },
	RightFoot = { "Right Leg", Vector3.new(0, -0.889, 0), Vector3.new(1, 0.221, 1) },
	LeftFoot = { "Left Leg", Vector3.new(0, -0.889, 0), Vector3.new(1, 0.221, 1) },
}

local function headVisualSize(head: BasePart): number
	-- 구형 머리(Part + SpecialMesh)는 메시 배율까지 반영
	local mesh = head:FindFirstChildOfClass("SpecialMesh")
	if mesh then
		return head.Size.Y * mesh.Scale.Y
	end
	return math.min(head.Size.X, head.Size.Y, head.Size.Z)
end

-- 방어구 조각이 붙을 (부위, 부위 기준 구역 CFrame, 배율)
local function resolve(character: Model, key: string): (BasePart?, CFrame, Vector3)
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	local isR6 = humanoid and humanoid.RigType == Enum.HumanoidRigType.R6

	if key == "Head" then
		local head = character:FindFirstChild("Head") :: BasePart?
		if not head then
			return nil, CFrame.identity, Vector3.one
		end
		local s = headVisualSize(head) / R15_REF.Head.Y
		return head, CFrame.identity, Vector3.new(s, s, s)
	end

	if not isR6 then
		local part = character:FindFirstChild(key) :: BasePart?
		if not part then
			return nil, CFrame.identity, Vector3.one
		end
		return part, CFrame.identity, part.Size / R15_REF[key]
	end

	local m = R6_MAP[key]
	local part = m and character:FindFirstChild(m[1]) :: BasePart?
	if not part then
		return nil, CFrame.identity, Vector3.one
	end
	local k = part.Size / R6_BASE[m[1]]
	return part, CFrame.new(m[2] * k), (m[3] * k) / R15_REF[key]
end

local function findPiece(template: Instance, key: string): BasePart?
	local p = template:FindFirstChild(key, true)
	if p and p:IsA("BasePart") then
		return p
	end
	-- 임포터가 이름 뒤에 번호를 붙인 경우 대비
	for _, d in template:GetDescendants() do
		if d:IsA("BasePart") and string.sub(d.Name, 1, #key) == key then
			return d
		end
	end
	return nil
end

local function setHairHidden(character: Model, hidden: boolean)
	for _, acc in character:GetChildren() do
		if acc:IsA("Accessory") then
			local handle = acc:FindFirstChild("Handle")
			local att = handle and handle:FindFirstChildOfClass("Attachment")
			if att and (att.Name == "HatAttachment" or att.Name == "HairAttachment") then
				for _, d in acc:GetDescendants() do
					if d:IsA("BasePart") then
						if hidden then
							if d:GetAttribute("ArmorOrigTransparency") == nil then
								d:SetAttribute("ArmorOrigTransparency", d.Transparency)
							end
							d.Transparency = 1
						else
							local t = d:GetAttribute("ArmorOrigTransparency")
							if t ~= nil then
								d.Transparency = t
								d:SetAttribute("ArmorOrigTransparency", nil)
							end
						end
					end
				end
			end
		end
	end
end

function ArmorService.Unequip(character: Model, slot: string)
	local folder = character:FindFirstChild("Armor_" .. slot)
	if folder then
		folder:Destroy()
	end
	if slot == "helmet" and ArmorService.HIDE_HAIR_UNDER_HELMET then
		setHairHidden(character, false)
	end
end

function ArmorService.UnequipAll(character: Model)
	for _, slot in ArmorService.SLOTS do
		ArmorService.Unequip(character, slot)
	end
end

function ArmorService.Equip(character: Model, setName: string, slot: string): boolean
	local setData = ItemData.Armor[setName]
	local pieces = setData and setData[slot]
	if not pieces then
		warn(("[ArmorService] 데이터 없음: %s / %s"):format(tostring(setName), tostring(slot)))
		return false
	end
	local template = armorFolder():FindFirstChild(setName .. "_" .. slot)
	if not template then
		warn(("[ArmorService] ReplicatedStorage.ItemAssets.Armor 에 '%s_%s' 가 없습니다"):format(setName, slot))
		return false
	end

	ArmorService.Unequip(character, slot)
	local folder = Instance.new("Folder")
	folder.Name = "Armor_" .. slot
	folder:SetAttribute("Set", setName)

	for key, info in pieces do
		local src = findPiece(template, key)
		local part, zone, scale = resolve(character, key)
		if src and part then
			local piece = src:Clone()
			piece.Name = key
			piece.Anchored = false
			piece.CanCollide = false
			piece.CanTouch = false
			piece.CanQuery = false
			piece.Massless = true
			piece.Size = info.size * scale
			local offset = zone * CFrame.new(info.offset * scale)
			piece.CFrame = part.CFrame * offset
			local weld = Instance.new("Weld")
			weld.Part0 = part
			weld.Part1 = piece
			weld.C0 = offset
			weld.Parent = piece
			piece.Parent = folder
		elseif not src then
			warn(("[ArmorService] %s_%s 안에 '%s' 메시가 없습니다"):format(setName, slot, key))
		end
	end

	folder.Parent = character
	if slot == "helmet" and ArmorService.HIDE_HAIR_UNDER_HELMET then
		setHairHidden(character, true)
	end
	return true
end

function ArmorService.EquipSet(character: Model, setName: string)
	for _, slot in ArmorService.SLOTS do
		ArmorService.Equip(character, setName, slot)
	end
end

function ArmorService.GetEquipped(character: Model): { [string]: string }
	local result = {}
	for _, slot in ArmorService.SLOTS do
		local folder = character:FindFirstChild("Armor_" .. slot)
		if folder then
			result[slot] = folder:GetAttribute("Set")
		end
	end
	return result
end

return ArmorService
