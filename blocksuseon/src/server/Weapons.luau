-- 무기 도구. 지닌 무기(data.weapons)마다 가방에 Roblox 도구를 넣는다 (숫자 키 1~9).
-- 모양은 Meshy 로 만든 모델(Combat.meshFor)을 쓰고, 없으면 블록으로 짓는다. 날은 손잡이(Handle) +Z 로 뻗는다.
-- 도구를 쓰면 onSwing(player, 칸) 을 부른다 (CombatService 가 채운다).
--
-- 든 자세와 휘두르는 몸짓은 클라이언트(client/WeaponAnim.luau)가 관절을 직접 움직여 그린다. 그래서
--   기본 Animate 의 toolanim(Slash/Lunge)은 쓰지 않고, 소리도 client/WeaponEffects.luau 가 낸다.
--   Grip 은 shared/WeaponPoses.GRIP (주먹 엄지 쪽으로 날이 나온다. 기본 자세가 보여도 날이 앞 위로 선다)
-- 도구 속성: Weapon(종류 id), Grade(등급), Length(줄인 뒤 무기 길이), Scale(아바타 키에 맞춘 비)
-- 손잡이 붙이개: TrailBase(날 밑동, 코등이 바로 위 / 부채 살이 펼쳐지는 곳), TrailTip(날 끝). 칼자취와 바람칼이 쓴다.
-- 아바타 키에 맞춰 무기를 줄인다 (작은 아바타는 작은 무기): clamp(키 / 5.2, 0.6, 1.1)

local InsertService = game:GetService("InsertService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Combat = require(Shared.Combat)
local WeaponPoses = require(Shared.WeaponPoses)
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

-- 블록 무기의 날 밑동·끝 (손잡이 가운데에서 +Z 로 몇 스터드, 줄이기 전), 손잡이 끝(-Z)
local BLOCK_SPAN = {
	sword = { base = 0.95, tip = 4.9, butt = -0.7 },
	saber = { base = 0.95, tip = 4.8, butt = -0.7 },
	spear = { base = 4.1, tip = 6.1, butt = -1.4 },
	fan = { base = 1.0, tip = 2.8, butt = -0.7 },
}
local HEIGHT = 5.2 -- 이 키의 아바타가 무기를 제 크기로 든다

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

-- 블록으로 지은 무기 모양 (k 배로 줄여서)
local function buildBlocks(tool: Tool, handle: BasePart, weapon: Combat.Weapon, k: number)
	local look = GRADE_LOOK[weapon.grade]
	local function piece(name: string, size: Vector3, color: Color3, material: Enum.Material?, offset: CFrame)
		attach(handle, part(tool, name, size * k, color, material), CFrame.new(offset.Position * k) * offset.Rotation)
	end
	if weapon.kind == "sword" then
		piece("Guard", Vector3.new(1.3, 0.22, 0.26), GOLD, Enum.Material.Metal, CFrame.new(0, 0, 0.8))
		piece("Blade", Vector3.new(0.36, 0.1, 3.6), look.blade, look.material, CFrame.new(0, 0, 2.75))
		piece(
			"Tip",
			Vector3.new(0.26, 0.1, 0.4),
			look.blade,
			look.material,
			CFrame.new(0, 0, 4.7) * CFrame.Angles(0, math.rad(45), 0)
		)
	elseif weapon.kind == "saber" then
		piece("Guard", Vector3.new(0.9, 0.3, 0.3), GOLD, Enum.Material.Metal, CFrame.new(0, 0, 0.8))
		piece("Blade", Vector3.new(0.6, 0.12, 3.4), look.blade, look.material, CFrame.new(0.12, 0, 2.6))
		piece("Spine", Vector3.new(0.1, 0.16, 3.4), HILT, Enum.Material.Metal, CFrame.new(-0.18, 0, 2.6))
		piece(
			"Tip",
			Vector3.new(0.5, 0.12, 0.6),
			look.blade,
			look.material,
			CFrame.new(0.05, 0, 4.5) * CFrame.Angles(0, math.rad(25), 0)
		)
	elseif weapon.kind == "spear" then
		piece(
			"Shaft",
			Vector3.new(0.26, 0.26, 6),
			Color3.fromRGB(110, 74, 50),
			Enum.Material.Wood,
			CFrame.new(0, 0, 1.6)
		)
		piece(
			"Tassel",
			Vector3.new(0.4, 0.4, 0.5),
			Color3.fromRGB(180, 40, 40),
			Enum.Material.Fabric,
			CFrame.new(0, 0, 4.5)
		)
		piece("Head", Vector3.new(0.5, 0.1, 1.4), look.blade, look.material, CFrame.new(0, 0, 5.4))
	elseif weapon.kind == "fan" then
		for i = -2, 2 do
			piece(
				"Leaf",
				Vector3.new(0.5, 0.06, 1.8),
				look.blade,
				look.material,
				CFrame.new(0, 0, 0.9) * CFrame.Angles(0, math.rad(i * 16), 0) * CFrame.new(0, 0, 1)
			)
		end
	end
end

-- 모델 무기의 날 밑동·끝·손잡이 끝 (손잡이 가운데에서 +Z, 줄이기 전). Combat.MESH 의 length·tip·grip 으로 셈한다
local function meshSpan(kind: string, spec: Combat.MeshSpec): { base: number, tip: number, butt: number }
	local L = spec.length
	local tip = L * (0.5 - spec.tip * spec.grip)
	local butt = -L * (0.5 + spec.tip * spec.grip)
	local base
	if kind == "spear" then
		base = tip - 0.22 * L -- 창날 뒤 자루
	elseif kind == "fan" then
		base = math.max(tip - 0.55 * L, 0.15 * L) -- 살이 펼쳐지기 시작하는 곳
	else
		base = math.min(0.13 * L, tip * 0.5) -- 코등이 바로 위
	end
	return { base = base, tip = tip, butt = butt }
end

-- 아바타 키 (머리 꼭대기에서 발바닥까지). 움직이는 자세와 상관없이 뿌리 기준으로 잰다
local function bodyHeight(character: Model?): number
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local root = character and character:FindFirstChild("HumanoidRootPart")
	local head = character and character:FindFirstChild("Head")
	if
		not humanoid
		or humanoid.RigType ~= Enum.HumanoidRigType.R15
		or not root
		or not root:IsA("BasePart")
		or not head
		or not head:IsA("BasePart")
	then
		return HEIGHT
	end
	local top = root.CFrame:PointToObjectSpace(head.Position).Y + head.Size.Y / 2
	local bottom = -root.Size.Y / 2 - humanoid.HipHeight
	local height = top - bottom
	return if height > 1 and height < 30 then height else HEIGHT
end

function Weapons.scaleFor(height: number): number
	return math.clamp(height / HEIGHT, 0.6, 1.1)
end

local function buildTool(weapon: Combat.Weapon, index: number, player: Player): Tool
	local kind = Combat.KINDS[weapon.kind]
	local tool = Instance.new("Tool")
	tool.Name = Combat.weaponName(weapon)
	tool.ToolTip = kind.summary
	tool.CanBeDropped = false
	tool.RequiresHandle = true
	tool:SetAttribute("WeaponIndex", index)
	tool:SetAttribute("Weapon", weapon.kind)
	tool:SetAttribute("Grade", weapon.grade)
	tool:AddTag("Weapon")
	tool.Grip = WeaponPoses.GRIP
	local k = Weapons.scaleFor(bodyHeight(player.Character))
	tool:SetAttribute("Scale", k)

	local handle = part(tool, "Handle", Vector3.new(0.3, 0.3, 1.4) * k, HILT, Enum.Material.Wood)
	local spec = Combat.meshFor(weapon)
	local mesh = if spec then loadMesh(spec.asset) else nil
	local body: BasePart? = nil
	local copy = mesh and mesh:Clone()
	if copy then
		for _, piece in copy:GetDescendants() do
			if piece:IsA("BasePart") and (not body or piece.Size.Magnitude > body.Size.Magnitude) then
				body = piece
			end
		end
	end
	if copy and body and spec then
		handle.Transparency = 1
		local box, size = copy:GetBoundingBox()
		copy.WorldPivot = CFrame.new(box.Position) * body.CFrame.Rotation
		local longest = math.max(size.X, size.Y, size.Z)
		if longest > 0 then
			copy:ScaleTo(copy:GetScale() * spec.length * k / longest)
		end
		-- 날 끝(±Y)이 손잡이 +Z 로 가게 돌리고, 쥐는 자리를 손잡이 가운데에 둔다
		copy:PivotTo(
			handle.CFrame * CFrame.Angles(spec.tip * math.pi / 2, 0, 0) * CFrame.new(0, -spec.grip * spec.length * k, 0)
		)
		for _, piece in copy:GetDescendants() do
			if piece:IsA("BasePart") then
				piece.CanCollide = false
				piece.CanQuery = false
				piece.CanTouch = false
				piece.Massless = true
				piece.Anchored = false
				local weld = Instance.new("WeldConstraint")
				weld.Part0 = handle
				weld.Part1 = piece
				weld.Parent = piece
			end
		end
		copy.Parent = tool
		-- 영·천 등급은 빛이 돈다
		if weapon.grade >= 4 then
			local light = Instance.new("PointLight")
			light.Color = GRADE_LOOK[weapon.grade].blade
			light.Range = 6 * k
			light.Brightness = 1.2
			light.Parent = body
		end
	else
		buildBlocks(tool, handle, weapon, k)
	end

	-- 칼자취 붙이개와 길이
	local span = if copy and body and spec then meshSpan(weapon.kind, spec) else BLOCK_SPAN[weapon.kind]
	local function mark(name: string, z: number)
		local attachment = Instance.new("Attachment")
		attachment.Name = name
		attachment.Position = Vector3.new(0, 0, z * k)
		attachment.Parent = handle
	end
	mark("TrailBase", span.base)
	mark("TrailTip", span.tip)
	tool:SetAttribute("Length", (span.tip - span.butt) * k)

	tool.Activated:Connect(function()
		if Weapons.onSwing then
			Weapons.onSwing(player, index)
		end
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
