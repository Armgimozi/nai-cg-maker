-- run.sh 가 mock.luau + 모듈들 + 이 파일을 이어 붙여 실행한다. (modules 테이블은 run.sh 가 채움)
local ItemData, ArmorService, ItemService = modules.ItemData, modules.ArmorService, modules.ItemService

local fails, total = 0, 0
local function check(cond, msg)
	total += 1
	if not cond then
		fails += 1
		print("  FAIL: " .. msg)
	end
end
local function near(a, b, eps)
	eps = eps or 1e-4
	return math.abs(a.X - b.X) < eps and math.abs(a.Y - b.Y) < eps and math.abs(a.Z - b.Z) < eps
end

-- ── 에셋 폴더 (임포트 결과 흉내) ──
local RS = game:GetService("ReplicatedStorage")
local assets = Instance.new("Folder")
assets.Name = "ItemAssets"
assets.Parent = RS
local armorF = Instance.new("Folder")
armorF.Name = "Armor"
armorF.Parent = assets
local itemsF = Instance.new("Folder")
itemsF.Name = "Items"
itemsF.Parent = assets

local nPieces = {}
for setName, set in ItemData.Armor do
	for slot, pieces in set do
		if type(pieces) == "table" then
			local m = Instance.new("Model")
			m.Name = setName .. "_" .. slot
			m.Parent = armorF
			local n = 0
			for key, info in pieces do
				local p = Instance.new("MeshPart")
				-- 임포터가 번호를 붙이는 경우도 시험 (UpperTorso → UpperTorso1)
				p.Name = (key == "UpperTorso" and setName == "iron") and "UpperTorso1" or key
				p.Size = info.size * 3.57 -- 단위 환산 등으로 크기가 달라져도 Equip 이 다시 맞춘다
				p.Parent = m
				n += 1
			end
			nPieces[setName .. "_" .. slot] = n
		end
	end
end
for id in ItemData.Items do
	local m = Instance.new("Model") -- 단일 메시도 Model 로 들어오는 경우
	m.Name = id
	m.Parent = itemsF
	local p = Instance.new("MeshPart")
	p.Name = id
	p.Parent = m
end

-- ── 캐릭터 ──
local R15 = {
	Head = { Vector3.new(1.2, 1.2, 1.2), Vector3.new(0, 4.8, 0) },
	UpperTorso = { Vector3.new(2, 1.6, 1), Vector3.new(0, 3.4, 0) },
	LowerTorso = { Vector3.new(2, 0.4, 1), Vector3.new(0, 2.4, 0) },
	RightUpperArm = { Vector3.new(1, 1.169, 1), Vector3.new(1.5, 3.6155, 0) },
	LeftUpperArm = { Vector3.new(1, 1.169, 1), Vector3.new(-1.5, 3.6155, 0) },
	RightUpperLeg = { Vector3.new(1, 1.217, 1), Vector3.new(0.5, 1.9085, 0) },
	LeftUpperLeg = { Vector3.new(1, 1.217, 1), Vector3.new(-0.5, 1.9085, 0) },
	RightLowerLeg = { Vector3.new(1, 1.193, 1), Vector3.new(0.5, 0.8465, 0) },
	LeftLowerLeg = { Vector3.new(1, 1.193, 1), Vector3.new(-0.5, 0.8465, 0) },
	RightFoot = { Vector3.new(1, 0.3, 1), Vector3.new(0.5, 0.15, 0) },
	LeftFoot = { Vector3.new(1, 0.3, 1), Vector3.new(-0.5, 0.15, 0) },
}
local function makeChar(rig, scale)
	local c = Instance.new("Model")
	c.Name = "Char"
	local h = Instance.new("Humanoid")
	h.RigType = rig
	h.Parent = c
	if rig == Enum.HumanoidRigType.R15 then
		for name, sp in R15 do
			local p = Instance.new("MeshPart")
			p.Name = name
			p.Size = name == "Head" and sp[1] or sp[1] * scale
			p.CFrame = CFrame.new(sp[2])
			p.Parent = c
		end
	else
		local defs = {
			Torso = { Vector3.new(2, 2, 1), Vector3.new(0, 3, 0) },
			["Right Arm"] = { Vector3.new(1, 2, 1), Vector3.new(1.5, 3, 0) },
			["Left Arm"] = { Vector3.new(1, 2, 1), Vector3.new(-1.5, 3, 0) },
			["Right Leg"] = { Vector3.new(1, 2, 1), Vector3.new(0.5, 1, 0) },
			["Left Leg"] = { Vector3.new(1, 2, 1), Vector3.new(-0.5, 1, 0) },
			Head = { Vector3.new(2, 1, 1), Vector3.new(0, 4.5, 0) },
		}
		for name, d in defs do
			local p = Instance.new("Part")
			p.Name = name
			p.Size = d[1]
			p.CFrame = CFrame.new(d[2])
			p.Parent = c
		end
		local sm = Instance.new("SpecialMesh")
		sm.Scale = Vector3.new(1.25, 1.25, 1.25)
		sm.Parent = c.Head
	end
	-- 머리카락 액세서리
	local acc = Instance.new("Accessory")
	acc.Parent = c
	local handle = Instance.new("Part")
	handle.Name = "Handle"
	handle.Transparency = 0
	handle.Parent = acc
	local att = Instance.new("Attachment")
	att.Name = "HairAttachment"
	att.Parent = handle
	return c, handle
end

-- 1) R15 기본 체형: 크기·위치가 데이터 그대로
print("[R15] 세트 장착")
for _, setName in { "leather", "iron", "knight" } do
	local char, hair = makeChar(Enum.HumanoidRigType.R15, 1)
	ArmorService.EquipSet(char, setName)
	for _, slot in ArmorService.SLOTS do
		local folder = char:FindFirstChild("Armor_" .. slot)
		check(folder ~= nil, setName .. " " .. slot .. " 폴더 없음")
		if folder then
			check(#folder:GetChildren() == nPieces[setName .. "_" .. slot], setName .. " " .. slot .. " 조각 수")
			for _, piece in folder:GetChildren() do
				local info = ItemData.Armor[setName][slot][piece.Name]
				local part = char:FindFirstChild(piece.Name)
				check(info ~= nil and part ~= nil, "조각 이름 → 부위: " .. piece.Name)
				check(near(piece.Size, info.size), setName .. "/" .. piece.Name .. " 크기")
				check(near(piece.CFrame.Position, part.CFrame.Position + info.offset), setName .. "/" .. piece.Name .. " 위치")
				local weld = piece:FindFirstChildOfClass("Weld")
				check(weld ~= nil and weld.Part0 == part and weld.Part1 == piece, piece.Name .. " Weld")
				check(piece.Massless == true and piece.CanCollide == false and piece.Anchored == false, piece.Name .. " 물리 설정")
			end
		end
	end
	check(hair.Transparency == 1, setName .. " 투구 쓰면 머리카락 숨김")
	local eq = ArmorService.GetEquipped(char)
	check(eq.helmet == setName and eq.chest == setName and eq.greaves == setName, "GetEquipped")
	ArmorService.Unequip(char, "helmet")
	check(char:FindFirstChild("Armor_helmet") == nil, "Unequip helmet")
	check(hair.Transparency == 0, "투구 벗으면 머리카락 복원")
	ArmorService.UnequipAll(char)
	check(char:FindFirstChild("Armor_chest") == nil and char:FindFirstChild("Armor_greaves") == nil, "UnequipAll")
end

-- 2) 체형이 큰 R15 (부위 1.25배): 갑옷도 1.25배
print("[R15 x1.25] 체형 스케일")
do
	local char = makeChar(Enum.HumanoidRigType.R15, 1.25)
	ArmorService.Equip(char, "knight", "chest")
	local up = char.Armor_chest.UpperTorso
	local info = ItemData.Armor.knight.chest.UpperTorso
	check(near(up.Size, info.size * 1.25), "UpperTorso 크기 1.25배")
	check(near(up.CFrame.Position, char.UpperTorso.CFrame.Position + info.offset * 1.25), "UpperTorso 위치 1.25배")
end

-- 3) R6: 모든 조각이 R6 부위에 붙는다
print("[R6] 세트 장착")
do
	local char = makeChar(Enum.HumanoidRigType.R6, 1)
	ArmorService.EquipSet(char, "iron")
	local total, expected = 0, 0
	for _, slot in ArmorService.SLOTS do
		expected += nPieces["iron_" .. slot]
		local folder = char:FindFirstChild("Armor_" .. slot)
		total += folder and #folder:GetChildren() or 0
	end
	check(total == expected, ("R6 조각 수 %d/%d"):format(total, expected))
	local helm = char.Armor_helmet.Head
	local s = 1.25 / 1.2
	check(near(helm.Size, ItemData.Armor.iron.helmet.Head.size * s), "R6 구형 머리(SpecialMesh 1.25) 투구 배율")
	local foot = char.Armor_greaves.RightFoot
	local w = foot:FindFirstChildOfClass("Weld")
	check(w.Part0 == char["Right Leg"], "R6 오른발 조각 → Right Leg")
	check(foot.CFrame.Position.Y < char["Right Leg"].CFrame.Position.Y - 0.6, "R6 발 조각이 다리 아래쪽")
end

-- 4) 없는 세트/부위
print("[예외] 잘못된 입력")
do
	local char = makeChar(Enum.HumanoidRigType.R15, 1)
	check(ArmorService.Equip(char, "gold", "helmet") == false, "없는 세트 → false")
end

-- 5) 아이템
print("[아이템] Tool / 진열")
for id, info in ItemData.Items do
	local tool = ItemService.CreateTool(id)
	check(tool ~= nil and tool.ClassName == "Tool", id .. " Tool 생성")
	if tool then
		local h = tool:FindFirstChild("Handle")
		check(h ~= nil and near(h.Size, info.size), id .. " Handle 크기")
		check(near(tool.Grip.Position, info.grip), id .. " Grip")
		check(tool.Name == info.name, id .. " 이름")
		check((h:FindFirstChildOfClass("PointLight") ~= nil) == (info.glow ~= nil), id .. " 발광")
	end
	local d = ItemService.CreateDisplay(id, CFrame.new(0, 10, 0))
	check(d ~= nil and d.Anchored == true and math.abs(d.CFrame.Position.Y - (10 + info.size.Y / 2)) < 1e-4, id .. " 진열")
end
check(#ItemService.List("weapon") == 6 and #ItemService.List("artifact") == 5, "List")
check(ItemService.CreateTool("nope") == nil, "없는 아이템 → nil")

print(fails == 0 and ("ALL PASS (%d checks)"):format(total) or ("FAILED: %d / %d"):format(fails, total))
