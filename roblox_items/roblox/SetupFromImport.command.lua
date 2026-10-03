--[[
	Studio 명령 모음(Command Bar)에 통째로 붙여넣고 Enter.

	3D Importer 로 FBX 들을 Workspace 에 가져온 뒤 실행하면,
	이름을 보고 ReplicatedStorage.ItemAssets.Armor / Items 폴더로 정리해 준다.
	(이미 정리된 것은 건드리지 않음 · 여러 번 실행해도 안전)
]]
local RS = game:GetService("ReplicatedStorage")
local assets = RS:FindFirstChild("ItemAssets") or Instance.new("Folder")
assets.Name = "ItemAssets"
assets.Parent = RS
local armor = assets:FindFirstChild("Armor") or Instance.new("Folder")
armor.Name = "Armor"
armor.Parent = assets
local items = assets:FindFirstChild("Items") or Instance.new("Folder")
items.Name = "Items"
items.Parent = assets

local ARMOR_SETS = { "leather", "iron", "knight" }
local ARMOR_SLOTS = { "helmet", "chest", "greaves" }
local ITEM_IDS = {
	"iron_longsword", "battle_axe", "spear", "longbow", "mage_staff", "dagger",
	"guardian_amulet", "flame_ring", "ancient_runestone", "arcane_orb", "chalice_of_life",
}

local moved = 0
local function take(name, dest)
	local inst = workspace:FindFirstChild(name)
	if inst then
		if dest:FindFirstChild(name) then
			dest[name]:Destroy()
		end
		local parts = inst:GetDescendants()
		table.insert(parts, inst)
		for _, d in parts do
			if d:IsA("BasePart") then
				d.Anchored = true
				d.CanCollide = false
			end
		end
		inst.Parent = dest
		moved += 1
	end
end
for _, s in ARMOR_SETS do
	for _, slot in ARMOR_SLOTS do
		take(s .. "_" .. slot, armor)
	end
end
for _, id in ITEM_IDS do
	take(id, items)
end
print(("[ItemAssets] %d개 정리 완료"):format(moved))
