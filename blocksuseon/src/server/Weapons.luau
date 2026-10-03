-- 무기 도구. 지닌 무기(data.weapons)마다 가방에 Roblox 도구를 넣는다 (숫자 키 1~9).
-- 모양은 Meshy 로 만든 모델(Combat.KINDS[종류].asset)을 쓰고, 없으면 블록으로 짓는다.
-- 도구를 쓰면 onSwing(player, 칸) 을 부른다 (CombatService 가 채운다).

local InsertService = game:GetService("InsertService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Combat = require(Shared.Combat)
local PlayerData = require(script.Parent.PlayerData)

local Weapons = {}

Weapons.onSwing = nil :: ((player: Player, index: number) -> ())?

-- 등급마다 날 빛깔
local GRADE_LOOK = {
	{ blade = Color3.fromRGB(150, 110, 70), material = Enum.Material.Wood },
	{ blade = Color3.fromRGB(170, 172, 178), material = Enum.Material.Metal },
	{ blade = Color3.fromRGB(110, 170, 175), material = Enum.Material.Metal },
	{ blade = Color3.fromRGB(140, 230, 190), material = Enum.Material.Neon },
	{ blade = Color3.fromRGB(255, 220, 130), material = Enum.Material.Neon },
}
local HILT = Color3.fromRGB(60, 34, 26)
local GOLD = Color3.fromRGB(214, 170, 80)

local meshCache: { [number]: Model | false } = {}

local function part(parent: Instance, name: string, size: Vector3, color: Color3, material: Enum.Material?): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
	p.CastShadow = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
	return p
end

-- 손잡이(Handle)에서 z 만큼 떨어진 곳에 붙인다 (날은 손잡이 +Z 쪽으로 뻗는다)
local function attach(handle: BasePart, piece: BasePart, offset: CFrame)
	piece.CFrame = handle.CFrame * offset
	local weld = Instance.new("WeldConstraint")
	weld.Part0 = handle
	weld.Part1 = piece
	weld.Parent = piece
end

local function loadMesh(asset: number): Model?
	local cached = meshCache[asset]
	if cached ~= nil then
		return cached or nil
	end
	local ok, result = pcall(function()
		return InsertService:LoadAsset(asset)
	end)
	local found: Model? = nil
	if ok and result then
		found = result:FindFirstChildWhichIsA("Model")
		if not found then
			local wrap = Instance.new("Model")
			for _, child in result:GetChildren() do
				if child:IsA("BasePart") then
					child.Parent = wrap
				end
			end
			found = if #wrap:GetChildren() > 0 then wrap else nil
		end
	end
	meshCache[asset] = found or false
	return found
end

-- 블록으로 지은 무기 모양
local function buildBlocks(tool: Tool, handle: BasePart, weapon: Combat.Weapon)
	local look = GRADE_LOOK[weapon.grade]
	if weapon.kind == "sword" then
		attach(
			handle,
			part(tool, "Guard", Vector3.new(1.3, 0.22, 0.26), GOLD, Enum.Material.Metal),
			CFrame.new(0, 0, 0.8)
		)
		attach(
			handle,
			part(tool, "Blade", Vector3.new(0.36, 0.1, 3.6), look.blade, look.material),
			CFrame.new(0, 0, 2.75)
		)
		attach(
			handle,
			part(tool, "Tip", Vector3.new(0.26, 0.1, 0.4), look.blade, look.material),
			CFrame.new(0, 0, 4.7) * CFrame.Angles(0, math.rad(45), 0)
		)
	elseif weapon.kind == "saber" then
		attach(
			handle,
			part(tool, "Guard", Vector3.new(0.9, 0.3, 0.3), GOLD, Enum.Material.Metal),
			CFrame.new(0, 0, 0.8)
		)
		attach(
			handle,
			part(tool, "Blade", Vector3.new(0.6, 0.12, 3.4), look.blade, look.material),
			CFrame.new(0.12, 0, 2.6)
		)
		attach(
			handle,
			part(tool, "Spine", Vector3.new(0.1, 0.16, 3.4), HILT, Enum.Material.Metal),
			CFrame.new(-0.18, 0, 2.6)
		)
		attach(
			handle,
			part(tool, "Tip", Vector3.new(0.5, 0.12, 0.6), look.blade, look.material),
			CFrame.new(0.05, 0, 4.5) * CFrame.Angles(0, math.rad(25), 0)
		)
	elseif weapon.kind == "spear" then
		attach(
			handle,
			part(tool, "Shaft", Vector3.new(0.26, 0.26, 6), Color3.fromRGB(110, 74, 50), Enum.Material.Wood),
			CFrame.new(0, 0, 1.6)
		)
		attach(
			handle,
			part(tool, "Tassel", Vector3.new(0.4, 0.4, 0.5), Color3.fromRGB(180, 40, 40), Enum.Material.Fabric),
			CFrame.new(0, 0, 4.5)
		)
		attach(handle, part(tool, "Head", Vector3.new(0.5, 0.1, 1.4), look.blade, look.material), CFrame.new(0, 0, 5.4))
	elseif weapon.kind == "fan" then
		for k = -2, 2 do
			attach(
				handle,
				part(tool, "Leaf", Vector3.new(0.5, 0.06, 1.8), look.blade, look.material),
				CFrame.new(0, 0, 0.9) * CFrame.Angles(0, math.rad(k * 16), 0) * CFrame.new(0, 0, 1)
			)
		end
	end
end

local function buildTool(weapon: Combat.Weapon, index: number, player: Player): Tool
	local kind = Combat.KINDS[weapon.kind]
	local tool = Instance.new("Tool")
	tool.Name = Combat.weaponName(weapon)
	tool.ToolTip = kind.summary
	tool.CanBeDropped = false
	tool.RequiresHandle = true
	tool:SetAttribute("WeaponIndex", index)
	tool:AddTag("Weapon")
	-- 손잡이 +Z 쪽이 위를 보게 쥔다
	tool.GripPos = Vector3.new(0, 0, 0)
	tool.GripForward = Vector3.new(-1, 0, 0)
	tool.GripRight = Vector3.new(0, 1, 0)
	tool.GripUp = Vector3.new(0, 0, 1)

	local handle = part(tool, "Handle", Vector3.new(0.3, 0.3, 1.4), HILT, Enum.Material.Wood)
	local asset = (kind :: any).asset
	local mesh = if type(asset) == "number" and asset > 0 then loadMesh(asset) else nil
	if mesh then
		handle.Transparency = 1
		local copy = mesh:Clone()
		local _, size = copy:GetBoundingBox()
		local longest = math.max(size.X, size.Y, size.Z)
		if longest > 0 then
			copy:ScaleTo(copy:GetScale() * 5 / longest)
		end
		copy:PivotTo(handle.CFrame * CFrame.new(0, 0, 1.8))
		for _, piece in copy:GetDescendants() do
			if piece:IsA("BasePart") then
				piece.CanCollide = false
				piece.CanQuery = false
				piece.Massless = true
				piece.Anchored = false
				local weld = Instance.new("WeldConstraint")
				weld.Part0 = handle
				weld.Part1 = piece
				weld.Parent = piece
			end
		end
		copy.Parent = tool
	else
		buildBlocks(tool, handle, weapon)
	end

	local swing = Instance.new("Sound")
	swing.Name = "Swing"
	swing.SoundId = if weapon.kind == "fan" then "rbxasset://sounds/swoosh.wav" else "rbxasset://sounds/swordslash.wav"
	swing.Volume = 0.6
	swing.Parent = handle

	tool.Activated:Connect(function()
		if Weapons.onSwing then
			Weapons.onSwing(player, index)
		end
		swing:Play()
		-- 기본 Animate 가 이 값을 보고 휘두르는 몸짓을 한다
		local anim = Instance.new("StringValue")
		anim.Name = "toolanim"
		anim.Value = if weapon.kind == "spear" then "Lunge" else "Slash"
		anim.Parent = tool
		task.delay(0.3, function()
			anim:Destroy()
		end)
	end)
	return tool
end

-- 가방의 무기를 지닌 무기에 맞춘다 (캐릭터가 새로 나거나 무기가 바뀌면)
function Weapons.give(player: Player)
	local data = PlayerData.get(player)
	local backpack = player:FindFirstChildOfClass("Backpack") or player:WaitForChild("Backpack", 5)
	if not data or not backpack or not backpack:IsA("Backpack") then
		return
	end
	local holding: number? = nil
	for _, container in { backpack, player.Character } do
		if container then
			for _, child in container:GetChildren() do
				if child:IsA("Tool") and child:HasTag("Weapon") then
					if container == player.Character then
						holding = child:GetAttribute("WeaponIndex")
					end
					child:Destroy()
				end
			end
		end
	end
	for index, weapon in data.weapons do
		local tool = buildTool(weapon, index, player)
		tool.Parent = backpack
		local humanoid = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
		if holding == index and humanoid then
			humanoid:EquipTool(tool)
		end
	end
end

return Weapons
