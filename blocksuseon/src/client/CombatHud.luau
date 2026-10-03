-- 싸움 화면: 위 가운데의 대상 창(맞힌 요수 이름과 체력), 내 체력 막대, 맞았을 때의 붉은 번쩍임과 흔들림.
-- 공중에 피해 숫자나 이름표를 띄우지 않는다.
-- 무기 몸짓(WeaponAnim)과 효과(WeaponEffects)도 여기서 켜고, 서버가 모두에게 보내는 싸움 소식을 나눠 준다:
--   "swing" 남이 휘둘렀다 → WeaponAnim.remoteSwing (내 것은 이미 그렸다)
--   "impact" 요수가 맞은 자리 → WeaponEffects.impact
--   "wave" 부채 바람칼 → WeaponEffects.wave (내 것은 이미 그렸으면 넘긴다)

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Lighting = game:GetService("Lighting")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Mobs = require(Shared.Mobs)
local Ui = require(script.Parent.Ui)
local WeaponAnim = require(script.Parent.WeaponAnim)
local WeaponEffects = require(script.Parent.WeaponEffects)

local C = Ui.C
local new, image, text, row = Ui.new, Ui.image, Ui.text, Ui.row

local CombatHud = {}

local player = Players.LocalPlayer
local ui: { [string]: any } = {}
local target: Model? = nil
local targetUntil = 0
local targetConnection: RBXScriptConnection? = nil
local shakeUntil, shakePower = 0, 0
local HP_COLOR = Color3.fromRGB(230, 90, 70)
local BAR_W = 300

local function setBar(fill: ImageLabel, ratio: number, width: number)
	ratio = math.clamp(ratio, 0, 1)
	fill.Visible = ratio > 0.01
	fill.Size = UDim2.fromOffset(math.max(6, (width - 6) * ratio), fill.Size.Y.Offset)
end

local function refreshTarget()
	local model = target
	if not model or not model.Parent then
		return
	end
	local hp = model:GetAttribute("Hp") or 0
	local maxHp = model:GetAttribute("MaxHp") or 1
	setBar(ui.targetFill, hp / maxHp, BAR_W)
	ui.targetHp:set(string.format("%d / %d", math.max(0, math.floor(hp)), maxHp))
end

local function showTarget(model: Model, name: string, tier: number)
	if targetConnection then
		targetConnection:Disconnect()
	end
	target = model
	targetUntil = os.clock() + 6
	ui.targetName:set(name)
	ui.targetTier:set(Mobs.TIER_NAMES[tier] or "")
	targetConnection = model:GetAttributeChangedSignal("Hp"):Connect(refreshTarget)
	refreshTarget()
	ui.target.Visible = true
end

local function flash(model: Model)
	local glow = Instance.new("Highlight")
	glow.FillColor = Color3.new(1, 1, 1)
	glow.FillTransparency = 0.4
	glow.OutlineTransparency = 1
	glow.DepthMode = Enum.HighlightDepthMode.Occluded
	glow.Parent = model
	task.delay(0.12, function()
		glow:Destroy()
	end)
end

function CombatHud.build(gui: ScreenGui)
	-- 대상 창
	local frame = image("notice", {
		Name = "Target",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 8),
		Size = UDim2.fromOffset(BAR_W + 60, 66),
		SliceScale = 0.8,
		Visible = false,
		ZIndex = 7,
		Parent = gui,
	})
	new("UIScale", { Parent = frame })
	local nameRow = row({ Position = UDim2.fromOffset(0, 4), Size = UDim2.new(1, 0, 0, 28), Parent = frame }, nil, 10)
	ui.targetName = text("title", 22, { gradient = Ui.GOLD_TEXT, parent = nameRow })
	ui.targetTier = text("body", 13, { color = C.dim, parent = nameRow })
	local track = image("barTrack", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 34),
		Size = UDim2.fromOffset(BAR_W, 18),
		SliceScale = 0.6,
		Parent = frame,
	})
	ui.targetFill = image("barGold", {
		Position = UDim2.fromOffset(3, 3),
		Size = UDim2.fromOffset(BAR_W - 6, 12),
		SliceScale = 0.55,
		ImageColor3 = HP_COLOR,
		Parent = track,
	})
	local hpRow = row({ Size = UDim2.fromScale(1, 1), Parent = track })
	ui.targetHp = text("body", 12, { color = C.cream, parent = hpRow })
	ui.target = frame

	-- 내 체력 (술법 칸 위)
	local mine = new("Frame", {
		Name = "MyHealth",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -182),
		Size = UDim2.fromOffset(BAR_W, 30),
		BackgroundTransparency = 1,
		Parent = gui,
	})
	new("UIScale", { Parent = mine })
	local myTrack = image("barTrack", {
		Position = UDim2.fromOffset(0, 12),
		Size = UDim2.fromOffset(BAR_W, 16),
		SliceScale = 0.55,
		Parent = mine,
	})
	ui.myFill = image("barGold", {
		Position = UDim2.fromOffset(3, 3),
		Size = UDim2.fromOffset(BAR_W - 6, 10),
		SliceScale = 0.5,
		ImageColor3 = HP_COLOR,
		Parent = myTrack,
	})
	local myRow = row({ Size = UDim2.new(1, 0, 0, 14), Parent = mine })
	ui.myHp = text("body", 12, { color = C.cream, parent = myRow })
	ui.mine = mine

	ui.hurtTint = new("ColorCorrectionEffect", { Name = "맞음", TintColor = Color3.new(1, 1, 1), Parent = Lighting })

	RunService.RenderStepped:Connect(function()
		local now = os.clock()
		if ui.target.Visible and (now > targetUntil or not target or not target.Parent) then
			ui.target.Visible = false
			target = nil
		end
		-- 내 체력: 다쳤을 때만 보인다
		local character = player.Character
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		if humanoid then
			local ratio = humanoid.Health / math.max(1, humanoid.MaxHealth)
			ui.mine.Visible = ratio < 0.999 and humanoid.Health > 0
			setBar(ui.myFill, ratio, BAR_W)
			ui.myHp:set(string.format("체력 %d / %d", math.floor(humanoid.Health + 0.5), humanoid.MaxHealth))
		else
			ui.mine.Visible = false
		end
		-- 맞으면 화면이 잠깐 흔들린다
		local camera = Workspace.CurrentCamera
		if camera and now < shakeUntil then
			local k = (shakeUntil - now) * shakePower
			camera.CFrame = camera.CFrame * CFrame.new(math.random() * k - k / 2, math.random() * k - k / 2, 0)
		end
	end)

	WeaponEffects.start()
	WeaponAnim.start()
	return frame
end

-- 서버가 보낸 싸움 소식
function CombatHud.event(payload: { [string]: any }, toast: (string, string?) -> ())
	if payload.kind == "hit" then
		local model = payload.mob
		if typeof(model) == "Instance" and model:IsA("Model") then
			flash(model)
			if payload.killed then
				ui.target.Visible = false
				target = nil
			else
				showTarget(model, payload.name, payload.tier)
			end
		end
	elseif payload.kind == "hurt" then
		local model = payload.mob
		if typeof(model) == "Instance" and model:IsA("Model") and model.Parent and not payload.killed then
			showTarget(model, payload.name, model:GetAttribute("Tier") or 1)
		end
		shakeUntil = os.clock() + 0.25
		shakePower = 1.6
		ui.hurtTint.TintColor = Color3.fromRGB(255, 170, 160)
		Ui.tween(ui.hurtTint, TweenInfo.new(0.4), { TintColor = Color3.new(1, 1, 1) })
	elseif payload.kind == "blocked" then
		toast(string.format("호신강기가 %s의 이빨을 막았다.", payload.name), "good")
	elseif payload.kind == "swing" then
		WeaponAnim.remoteSwing(payload)
	elseif payload.kind == "impact" then
		if typeof(payload.position) == "Vector3" then
			WeaponEffects.impact(
				payload.position,
				payload.weapon,
				tonumber(payload.grade) or 1,
				payload.player == player
			)
		end
	elseif payload.kind == "wave" then
		if typeof(payload.from) ~= "Vector3" or typeof(payload.to) ~= "Vector3" then
			return
		end
		if payload.player == player and WeaponAnim.consumeWave() then
			return -- 내가 휘두를 때 이미 날렸다
		end
		WeaponEffects.wave(payload.from, payload.to, tonumber(payload.grade) or 1, payload.hit == true)
	end
end

return CombatHud
