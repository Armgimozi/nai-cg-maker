-- 무기 효과 (클라이언트). 날을 따라 남는 칼자취, 맞은 자리의 불꽃·번쩍임·충격 고리, 부채가 날리는 초승달 바람칼,
-- 휘두르는 소리와 맞는 소리. 몸짓은 client/WeaponAnim.luau 가 맡고, 휘두를 때 여기 swing 을 부른다.
-- 서버(server/CombatService.luau)가 remotes.Combat 로 "swing"·"impact"·"wave" 를 모두에게 보내므로
-- 남의 칼질도 모든 클라이언트에서 보인다 (CombatHud.event 가 나눠 준다).
--
--   swing(character, tool, kind, grade, combo, duration)  duration 동안 날이 빠르게 움직일 때만 자취를 켜고 바람 소리를 낸다
--   impact(position, kind, grade, isLocalAttacker)          맞은 자리. 내가 맞혔으면 카메라가 살짝 튀고 몸짓이 잠깐 멈춘다
--   wave(from, to, grade, hit)                              초승달 바람칼이 from 에서 to 로 날아간다
--   hitstop()                                               몸짓을 멈출 남은 시간(초). 매 프레임 불러도 된다 (0 이면 멈추지 않는다)
--
-- 공중 글자나 BillboardGui 는 쓰지 않는다. 카메라에서 FAR 보다 먼 효과는 그리지 않는다.
-- 무기 도구 손잡이(Handle)에는 server/Weapons.luau 가 붙인 TrailBase(날 밑동)·TrailTip(날 끝) 붙이개가 있다.
-- 없으면 자취만 건너뛴다.

local ContentProvider = game:GetService("ContentProvider")
local Debris = game:GetService("Debris")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local WeaponEffects = {}

local FAR = 200 -- 카메라에서 이보다 먼 효과는 그리지 않는다
local WAVE_SPEED = 150 -- 바람칼 빠르기(스터드/초). server/CombatService.luau 의 WAVE_SPEED 와 같아야 맞는 때가 맞는다
local WAVE_TIME_MIN, WAVE_TIME_MAX = 0.1, 0.28
local WAVE_END = 0.2 -- 닿은 뒤 흩어지는 시간
local KICK_TIME = 0.14 -- 내가 맞혔을 때 카메라가 튀는 시간
local POOL = 8 -- 맞은 자리 효과 묶음을 이만큼 만들어 돌려 쓴다

-- 클라이언트 콘텐츠 폴더에 있는 것만 쓴다 (엔진에서 PreloadAsync 로 확인한 것: swoosh.wav 는 없다)
local SOUND = {
	slash = "rbxasset://sounds/swordslash.wav",
	lunge = "rbxasset://sounds/swordlunge.wav",
	hit = "rbxasset://sounds/hit.wav",
	wind = "rbxasset://sounds/Rocket whoosh 01.wav",
}
local TEXTURE = {
	spark = "rbxasset://textures/particles/sparkles_main.dds",
	ring = "rbxasset://textures/particles/explosion01_shockwave_main.dds",
	smoke = "rbxasset://textures/particles/smoke_main.dds",
}

-- 등급마다 빛깔: core 가운데(밝은 빛), edge 가장자리
type Palette = { core: Color3, edge: Color3 }
local PALETTE: { Palette } = {
	{ core = Color3.fromRGB(255, 222, 160), edge = Color3.fromRGB(214, 132, 58) }, -- 목: 따뜻한 갈색·호박빛
	{ core = Color3.fromRGB(240, 245, 255), edge = Color3.fromRGB(150, 166, 192) }, -- 철: 옅은 강철빛
	{ core = Color3.fromRGB(212, 252, 255), edge = Color3.fromRGB(56, 192, 236) }, -- 청강: 푸른 강철빛
	{ core = Color3.fromRGB(222, 255, 236), edge = Color3.fromRGB(64, 220, 156) }, -- 영: 옥빛
	{ core = Color3.fromRGB(255, 252, 232), edge = Color3.fromRGB(255, 200, 84) }, -- 천: 금빛 도는 흰빛
}

-- 종류마다 손맛
--   lifetime 칼자취가 남는 시간      window  자취를 켤 수 있는 가장 긴 시간
--   pitch    휘두르는 소리 빠르기 (낮을수록 무겁다)   hitPitch 맞는 소리 빠르기
--   sparks   불꽃 수   flash 번쩍임 크기   streak 베인 빛줄기 길이 (0 이면 없다)
--   kick     카메라가 튀는 각(도)   hitstop 몸짓이 멈추는 시간(초)
type Style = {
	lifetime: number,
	window: number,
	sound: string,
	pitch: { number },
	volume: number,
	hitPitch: { number },
	sparks: number,
	flash: number,
	streak: number,
	kick: number,
	hitstop: number,
	finisher: number, -- 이 번째 연속 공격이 마무리 (더 무겁다)
}
local STYLE: { [string]: Style } = {
	sword = {
		lifetime = 0.16,
		window = 0.3,
		sound = SOUND.slash,
		pitch = { 1.1, 1.26 },
		volume = 0.5,
		hitPitch = { 1.05, 1.2 },
		sparks = 16,
		flash = 3,
		streak = 4.5,
		kick = 0.5,
		hitstop = 0.06,
		finisher = 3,
	},
	saber = {
		lifetime = 0.22,
		window = 0.42,
		sound = SOUND.slash,
		pitch = { 0.74, 0.84 },
		volume = 0.65,
		hitPitch = { 0.78, 0.88 },
		sparks = 24,
		flash = 4.2,
		streak = 6.5,
		kick = 0.9,
		hitstop = 0.08,
		finisher = 2,
	},
	spear = {
		lifetime = 0.14,
		window = 0.32,
		sound = SOUND.lunge,
		pitch = { 1.15, 1.3 },
		volume = 0.5,
		hitPitch = { 1.2, 1.35 },
		sparks = 14,
		flash = 3,
		streak = 5,
		kick = 0.6,
		hitstop = 0.06,
		finisher = 2,
	},
	fan = {
		lifetime = 0.18,
		window = 0.32,
		sound = SOUND.slash,
		pitch = { 1.45, 1.6 },
		volume = 0.3,
		hitPitch = { 1.3, 1.45 },
		sparks = 12,
		flash = 3,
		streak = 0,
		kick = 0.3,
		hitstop = 0,
		finisher = 0,
	},
}

local started = false
local folder: Folder? = nil
local hitstopUntil = 0
local kickUntil, kickPower, kickYaw = 0, 0, 0

local function kp(t: number, value: number): NumberSequenceKeypoint
	return NumberSequenceKeypoint.new(t, value)
end

local function between(range: { number }): number
	return range[1] + math.random() * (range[2] - range[1])
end

local function palette(grade: number?): Palette
	return PALETTE[math.clamp(math.floor(tonumber(grade) or 1), 1, #PALETTE)]
end

local function styleOf(kind: string?): Style
	return STYLE[kind or ""] or STYLE.sword
end

local function near(position: Vector3, extra: number?): boolean
	local camera = Workspace.CurrentCamera
	return camera == nil or (camera.CFrame.Position - position).Magnitude <= FAR + (extra or 0)
end

local function effectsFolder(): Folder
	local current = folder
	if current and current.Parent then
		return current
	end
	local created = Instance.new("Folder")
	created.Name = "무기효과"
	created.Parent = Workspace
	folder = created
	return created
end

local function play(id: string, parent: Instance, volume: number, speed: number)
	local sound = Instance.new("Sound")
	sound.SoundId = id
	sound.Volume = volume
	sound.PlaybackSpeed = speed
	sound.RollOffMode = Enum.RollOffMode.InverseTapered
	sound.RollOffMinDistance = 10
	sound.RollOffMaxDistance = 140
	sound.Parent = parent
	sound:Play()
	Debris:AddItem(sound, 2.5)
end

-- 빛나는 타원체 (Neon 파트 + 공 모양 메시. 메시 Scale 로 키우고 줄인다)
local function glow(name: string, size: Vector3, color: Color3, transparency: number): (Part, SpecialMesh)
	local part = Instance.new("Part")
	part.Name = name
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.CastShadow = false
	part.Material = Enum.Material.Neon
	part.Color = color
	part.Transparency = transparency
	part.Size = size
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = part
	return part, mesh
end

---------------------------------------------------------------------------------------------------
-- 칼자취

-- 도구마다 한 번 만들어 둔다: 날 전체가 쓸고 지나간 넓은 자취(main)와 날 끝을 따라가는 가는 빛줄기(edge)
type Rig = {
	handle: BasePart,
	base: Attachment,
	tip: Attachment,
	main: Trail,
	edge: Trail,
	length: number,
	swing: Swing?,
}
type Swing = {
	rig: Rig,
	kind: string,
	combo: number,
	colors: Palette,
	untilAt: number,
	threshold: number,
	last: Vector3?,
	on: boolean,
	speed: number,
	pierced: boolean,
}

local rigs: { [Tool]: Rig } = setmetatable({}, { __mode = "k" }) :: any
local swings: { Swing } = {}

local function trailRig(tool: Tool): Rig?
	local rig = rigs[tool]
	if rig and rig.main.Parent and rig.base.Parent and rig.tip.Parent then
		return rig
	end
	local handle = tool:FindFirstChild("Handle")
	local base = handle and handle:FindFirstChild("TrailBase")
	local tip = handle and handle:FindFirstChild("TrailTip")
	if
		not handle
		or not handle:IsA("BasePart")
		or not base
		or not base:IsA("Attachment")
		or not tip
		or not tip:IsA("Attachment")
	then
		return nil
	end
	local length = (tip.Position - base.Position).Magnitude
	if length < 0.2 then
		return nil
	end
	-- 날 끝 가까이의 붙이개 (가는 빛줄기의 다른 한쪽)
	local inner = Instance.new("Attachment")
	inner.Name = "TrailEdge"
	inner.Position = base.Position:Lerp(tip.Position, 0.86)
	inner.Parent = handle

	local main = Instance.new("Trail")
	main.Name = "칼자취"
	main.Attachment0 = base
	main.Attachment1 = tip
	main.LightEmission = 1
	main.LightInfluence = 0
	main.MinLength = 0.05
	main.FaceCamera = false -- 날이 쓸고 간 면 그대로
	main.WidthScale = NumberSequence.new({ kp(0, 1), kp(0.6, 0.75), kp(1, 0.25) })
	main.Transparency = NumberSequence.new({ kp(0, 0.2), kp(0.4, 0.55), kp(1, 1) })
	main.Enabled = false
	main.Parent = handle

	local edge = Instance.new("Trail")
	edge.Name = "칼끝빛"
	edge.Attachment0 = inner
	edge.Attachment1 = tip
	edge.LightEmission = 1
	edge.LightInfluence = 0
	edge.MinLength = 0.05
	edge.FaceCamera = true -- 옆에서 봐도 사라지지 않는다
	edge.WidthScale = NumberSequence.new({ kp(0, 1), kp(1, 0.15) })
	edge.Transparency = NumberSequence.new({ kp(0, 0), kp(0.5, 0.35), kp(1, 1) })
	edge.Enabled = false
	edge.Parent = handle

	rig = { handle = handle, base = base, tip = tip, main = main, edge = edge, length = length }
	rigs[tool] = rig
	return rig
end

local function setTrails(rig: Rig, on: boolean)
	rig.main.Enabled = on
	rig.edge.Enabled = on
end

-- 창: 다 뻗은 순간 창끝에서 공기가 꿰뚫린다 (앞으로 뻗는 빛 바늘과 작은 고리)
local nextBurst: () -> any

local function pierce(at: Vector3, direction: Vector3, colors: Palette)
	if direction.Magnitude < 0.01 or not near(at) then
		return
	end
	local needle = glow("꿰뚫음", Vector3.new(0.22, 0.22, 2.4), colors.core, 0.05)
	needle.CFrame = CFrame.lookAt(at, at + direction) * CFrame.new(0, 0, -1)
	needle.Parent = effectsFolder()
	local info = TweenInfo.new(0.14, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	TweenService:Create(needle, info, {
		Size = Vector3.new(0.04, 0.04, 5),
		CFrame = needle.CFrame * CFrame.new(0, 0, -1.6),
		Transparency = 1,
	}):Play()
	Debris:AddItem(needle, 0.2)
	local burst = nextBurst()
	burst.spot.WorldCFrame = CFrame.new(at)
	burst.ring.Color = ColorSequence.new(colors.core, colors.edge)
	burst.ring.Size = NumberSequence.new({ kp(0, 0.3), kp(1, 2.6) })
	burst.ring:Emit(1)
end

-- 휘두르기: duration 동안, 날 끝이 빠르게 움직일 때만 자취를 켠다 (늘어지는 준비·거두는 몸짓에는 자취가 없다)
function WeaponEffects.swing(
	character: Model,
	tool: Tool?,
	weaponKind: string,
	grade: number,
	combo: number,
	duration: number
)
	local style = styleOf(weaponKind)
	local colors = palette(grade)
	local root = character and character:FindFirstChild("HumanoidRootPart")
	local rig = if tool and typeof(tool) == "Instance" and tool:IsA("Tool") then trailRig(tool) else nil
	local at: BasePart? = if rig then rig.handle elseif root and root:IsA("BasePart") then root else nil
	if not at or not near(at.Position) then
		return
	end
	combo = tonumber(combo) or 1
	local finisher = style.finisher > 0 and combo == style.finisher

	-- 바람 소리: 무거운 마무리는 낮고 크게. 창의 둘째 수는 휘두르므로 베는 소리
	local sound = if weaponKind == "spear" and combo == 2 then SOUND.slash else style.sound
	local speed = between(style.pitch) * (if finisher then 0.9 else 1)
	play(sound, at, style.volume * (if finisher then 1.2 else 1), speed)

	if not rig then
		return
	end
	rig.main.Color = ColorSequence.new({
		ColorSequenceKeypoint.new(0, colors.core),
		ColorSequenceKeypoint.new(0.35, colors.edge),
		ColorSequenceKeypoint.new(1, colors.edge),
	})
	rig.edge.Color = ColorSequence.new(colors.core, colors.edge)
	rig.main.Lifetime = style.lifetime * (if finisher then 1.3 else 1)
	rig.edge.Lifetime = style.lifetime * 1.4
	-- 날 길이(아바타 크기에 맞춘 길이)에 비례한 빠르기를 넘을 때만 켠다
	local entry: Swing = {
		rig = rig,
		kind = weaponKind,
		combo = combo,
		colors = colors,
		untilAt = os.clock() + math.clamp(tonumber(duration) or style.window, 0.08, style.window),
		threshold = rig.length * 4,
		last = nil,
		on = false,
		speed = 0,
		pierced = false,
	}
	rig.swing = entry
	table.insert(swings, entry)
end

local function stepSwings(dt: number)
	if #swings == 0 then
		return
	end
	local now = os.clock()
	for i = #swings, 1, -1 do
		local entry = swings[i]
		local rig = entry.rig
		local alive = rig.swing == entry and now < entry.untilAt and rig.handle:IsDescendantOf(Workspace)
		if not alive then
			if rig.swing == entry then
				rig.swing = nil
				setTrails(rig, false)
			end
			table.remove(swings, i)
		else
			local tip = rig.tip.WorldPosition
			local speed = if entry.last and dt > 0 then (tip - entry.last).Magnitude / dt else 0
			entry.last = tip
			-- 켜기와 끄기 사이에 틈을 두어 깜빡이지 않게
			local on = if entry.on then speed > entry.threshold * 0.5 else speed > entry.threshold
			if on ~= entry.on then
				entry.on = on
				setTrails(rig, on)
			end
			-- 창 찌르기: 가장 빨랐다가 느려지기 시작하는 순간이 다 뻗은 때
			if entry.kind == "spear" and entry.combo ~= 2 and not entry.pierced then
				if entry.on and speed < entry.speed * 0.7 then
					entry.pierced = true
					local direction = tip - rig.base.WorldPosition
					pierce(tip, if direction.Magnitude > 0 then direction.Unit else direction, entry.colors)
				end
			end
			entry.speed = math.max(entry.speed, speed)
		end
	end
end

---------------------------------------------------------------------------------------------------
-- 맞은 자리

type Burst = {
	spot: Attachment,
	sparks: ParticleEmitter,
	star: ParticleEmitter,
	ring: ParticleEmitter,
	light: PointLight,
}
local bursts: { Burst } = {}
local burstIndex = 0

local function makeBurst(): Burst
	local spot = Instance.new("Attachment")
	spot.Name = "무기효과"
	spot.Parent = Workspace.Terrain

	-- 튀는 불꽃: 날아가는 쪽으로 길게 늘어진 빛 조각, 카메라 쪽으로 퍼진다
	local sparks = Instance.new("ParticleEmitter")
	sparks.Texture = TEXTURE.spark
	sparks.Orientation = Enum.ParticleOrientation.VelocityParallel
	sparks.Rate = 0
	sparks.Lifetime = NumberRange.new(0.16, 0.36)
	sparks.Speed = NumberRange.new(16, 34)
	sparks.SpreadAngle = Vector2.new(75, 75)
	sparks.Drag = 7
	sparks.Acceleration = Vector3.new(0, -34, 0)
	sparks.Size = NumberSequence.new({ kp(0, 0.34), kp(1, 0) })
	sparks.Squash = NumberSequence.new({ kp(0, 2.2), kp(1, 0.8) })
	sparks.LightEmission = 1
	sparks.LightInfluence = 0
	sparks.Brightness = 2
	sparks.ZOffset = 1
	sparks.Parent = spot

	-- 가운데 번쩍임 (별 모양 한 장)
	local star = Instance.new("ParticleEmitter")
	star.Texture = TEXTURE.spark
	star.Rate = 0
	star.Lifetime = NumberRange.new(0.1, 0.14)
	star.Speed = NumberRange.new(0)
	star.Rotation = NumberRange.new(0, 360)
	star.Transparency = NumberSequence.new({ kp(0, 0), kp(1, 0.7) })
	star.LightEmission = 1
	star.LightInfluence = 0
	star.Brightness = 3
	star.ZOffset = 2
	star.Parent = spot

	-- 충격 고리 (카메라를 보고 퍼지며 옅어진다)
	local ring = Instance.new("ParticleEmitter")
	ring.Texture = TEXTURE.ring
	ring.Rate = 0
	ring.Lifetime = NumberRange.new(0.2, 0.22)
	ring.Speed = NumberRange.new(0)
	ring.Rotation = NumberRange.new(0, 360)
	ring.Transparency = NumberSequence.new({ kp(0, 0.05), kp(1, 1) })
	ring.LightEmission = 1
	ring.LightInfluence = 0
	ring.Brightness = 2
	ring.ZOffset = 1.5
	ring.Parent = spot

	local light = Instance.new("PointLight")
	light.Brightness = 0
	light.Range = 14
	light.Shadows = false
	light.Parent = spot

	return { spot = spot, sparks = sparks, star = star, ring = ring, light = light }
end

nextBurst = function(): Burst
	burstIndex = burstIndex % POOL + 1
	local burst = bursts[burstIndex]
	if not burst or not burst.spot.Parent then
		burst = makeBurst()
		bursts[burstIndex] = burst
	end
	return burst
end

-- 베인 빛줄기: 맞은 자리에 카메라를 보고 그어지는 가는 빛 (길어지며 가늘어지고 사라진다)
local function streak(position: Vector3, color: Color3, length: number, roll: number, delay: number?)
	local camera = Workspace.CurrentCamera
	if not camera or (camera.CFrame.Position - position).Magnitude < 0.5 then
		return
	end
	local part = glow("베인빛", Vector3.new(length * 0.3, 0.3, 0.05), color, 0)
	part.CFrame = CFrame.lookAt(position, camera.CFrame.Position) * CFrame.new(0, 0, -1.2) * CFrame.Angles(0, 0, roll)
	local function go()
		part.Parent = effectsFolder()
		TweenService:Create(part, TweenInfo.new(0.16, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
			Size = Vector3.new(length, 0.03, 0.05),
			Transparency = 1,
		}):Play()
		Debris:AddItem(part, 0.22)
	end
	if delay and delay > 0 then
		task.delay(delay, go)
	else
		go()
	end
end

function WeaponEffects.impact(position: Vector3, weaponKind: string, grade: number, isLocalAttacker: boolean)
	if typeof(position) ~= "Vector3" or not near(position) then
		return
	end
	local style = styleOf(weaponKind)
	local colors = palette(grade)
	local camera = Workspace.CurrentCamera
	local eye = if camera then camera.CFrame.Position else position + Vector3.new(0, 0, 10)

	local burst = nextBurst()
	-- 붙이개의 위(+Y)가 카메라를 보게: 불꽃이 보는 쪽으로 튄다
	local facing = if (eye - position).Magnitude > 0.1 then CFrame.lookAt(position, eye) else CFrame.new(position)
	burst.spot.WorldCFrame = facing * CFrame.Angles(-math.pi / 2, 0, 0)

	burst.sparks.Color = ColorSequence.new(colors.core, colors.edge)
	burst.sparks:Emit(style.sparks + math.random(0, 4))
	burst.star.Color = ColorSequence.new(colors.core)
	burst.star.Size = NumberSequence.new({ kp(0, style.flash * 0.4), kp(0.3, style.flash), kp(1, 0) })
	burst.star:Emit(1)
	burst.ring.Color = ColorSequence.new(colors.core, colors.edge)
	burst.ring.Size = NumberSequence.new({ kp(0, 0.4), kp(1, style.flash * 1.6) })
	burst.ring:Emit(1)

	burst.light.Color = colors.edge
	burst.light.Brightness = 6
	burst.light.Range = 10 + style.flash * 2
	TweenService
		:Create(burst.light, TweenInfo.new(0.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Brightness = 0 })
		:Play()

	if style.streak > 0 then
		local tilt = math.rad(math.random(22, 52)) * (if math.random() < 0.5 then 1 else -1)
		if weaponKind == "spear" then
			tilt = math.rad(math.random(-10, 10)) -- 찌르기는 거의 가로로
		end
		streak(position, colors.core, style.streak, tilt)
		if weaponKind == "saber" then
			streak(position, colors.edge, style.streak * 0.7, tilt + math.rad(math.random(70, 100)), 0.04) -- 엇갈린 둘째 획
		end
	end

	play(SOUND.hit, burst.spot, 0.55, between(style.hitPitch))

	if isLocalAttacker then
		local now = os.clock()
		-- 한 번에 여럿을 베도 멈춤은 한 번만 (길어지지 않는다)
		if style.hitstop > 0 and hitstopUntil < now then
			hitstopUntil = now + style.hitstop
		end
		kickPower = math.max(style.kick, if now < kickUntil then kickPower else 0)
		kickUntil = now + KICK_TIME
		kickYaw = (math.random() - 0.5) * 1.2
	end
end

function WeaponEffects.hitstop(): number
	return math.max(0, hitstopUntil - os.clock())
end

---------------------------------------------------------------------------------------------------
-- 바람칼 (부채)
--
-- 초승달 모양: 앞(-Z)으로 볼록하고 두 뿔이 뒤(+Z)로 휜다. 뾰족한 뿔, 두꺼운 가운데.
-- 세 겹의 빛나는 타원체를 호를 따라 늘어놓는다: 옅은 겉빛(halo), 몸(body), 앞날의 흰빛(edge).

local ARC = math.rad(68) -- 가운데에서 뿔까지 벌어진 각
local RADIUS = 3.1
local WIDTH = 1.45 -- 가운데의 안팎 두께
local TAPER = 0.9 -- 뿔로 갈수록 가늘어지는 정도
local TILT = math.rad(30) -- 앞으로 숙인 각: 뒤·위에서 보는 카메라에 초승달 면이 보인다
local ROLL_MIN, ROLL_MAX = 12, 26 -- 비스듬히 기운 각(도). 매번 좌우를 바꿔 가며 조금씩 다르게
local LAYERS = {
	{ name = "겉빛", count = 8, width = 1.3, length = 2.3, thick = 0.5, forward = 0, mix = 0, alpha = 0.76 },
	{ name = "몸", count = 10, width = 1, length = 2, thick = 0.2, forward = 0, mix = 0.35, alpha = 0.18 },
	{ name = "앞날", count = 10, width = 0.34, length = 1.9, thick = 0.12, forward = 0.33, mix = 1, alpha = 0 },
}

local function arcPoint(theta: number): Vector3
	return Vector3.new(RADIUS * math.sin(theta), 0, RADIUS * (1 - math.cos(theta)))
end

local function arcWidth(theta: number): number
	local u = theta / ARC
	return WIDTH * math.max(0, 1 - u * u) ^ TAPER
end

-- 바람칼 한 조각: 바람칼 기준(꼭지점, -Z 가 나아가는 쪽)에서의 자리
export type Piece = {
	offset: CFrame,
	size: Vector3,
	color: Color3,
	alpha: number,
	normal: Vector3,
	layer: string,
}

-- 바람칼 모양 (순수 계산. 미리 보기 그림에서도 쓴다)
function WeaponEffects.crescent(grade: number): { Piece }
	local colors = palette(grade)
	local pieces = {}
	for _, layer in LAYERS do
		local step = 2 * ARC / layer.count
		local chord = 2 * RADIUS * math.sin(step / 2)
		for i = 1, layer.count do
			local theta = -ARC + (i - 0.5) * step
			local normal = Vector3.new(math.sin(theta), 0, -math.cos(theta))
			local tangent = Vector3.new(math.cos(theta), 0, math.sin(theta))
			local width = math.max(arcWidth(theta) * layer.width, 0.08)
			-- 뿔 쪽 조각은 가늘고 길게 (뾰족하게)
			local edgeness = math.abs(theta) / ARC
			local length = chord * layer.length * (1 + edgeness * 0.2)
			local position = arcPoint(theta) + normal * (width * layer.forward)
			table.insert(pieces, {
				offset = CFrame.fromMatrix(position, tangent, Vector3.yAxis),
				size = Vector3.new(length, layer.thick * (1 - edgeness * 0.4), width),
				color = colors.edge:Lerp(colors.core, layer.mix),
				alpha = layer.alpha,
				normal = normal,
				layer = layer.name,
			})
		end
	end
	return pieces
end

type Wave = {
	age: number,
	travel: number,
	from: Vector3,
	to: Vector3,
	turn: CFrame,
	hit: boolean,
	model: Folder,
	carrier: Part,
	horns: { Attachment },
	hornAt: { Vector3 },
	parts: { Part },
	meshes: { SpecialMesh },
	pieces: { Piece },
	wisps: ParticleEmitter,
	motes: ParticleEmitter,
	ended: boolean,
}
local waves: { Wave } = {}
local rollSide = 1

local CARRIER_Z = RADIUS * (1 - math.cos(ARC)) / 2 -- 바람칼 가운데 (꼭지점에서 뒤로)

-- 바람칼 한 프레임: 날아가는 동안 조금씩 커지고, 닿으면 맞았을 때는 조각이 사방으로 터지고 아니면 퍼지며 흩어진다
local function placeWave(wave: Wave): boolean
	local direction = (wave.to - wave.from).Unit
	local u = math.clamp(wave.age / wave.travel, 0, 1)
	local e = math.clamp((wave.age - wave.travel) / WAVE_END, 0, 1) -- 끝난 뒤 흐름
	local position = wave.from:Lerp(wave.to, u)
	local scale = 0.7 + 0.45 * (1 - (1 - u) ^ 2)
	local flutter = math.sin(wave.age * 40) * math.rad(3) * (1 - e)
	local spread, fade, thin = 0, 0, 1
	if e > 0 then
		local ease = 1 - (1 - e) ^ 2
		if wave.hit then
			spread = ease * 2.2
			scale *= 1 - ease * 0.45
		else
			position += direction * 3 * ease
			scale *= 1 + ease * 0.45
			thin = 1 - ease * 0.8
		end
		fade = e ^ 1.3
	end
	local base = CFrame.lookAt(position, position + direction) * wave.turn * CFrame.Angles(0, 0, flutter)
	wave.carrier.CFrame = base * CFrame.new(0, 0, CARRIER_Z * scale)
	for i, attachment in wave.horns do
		attachment.Position = (wave.hornAt[i] - Vector3.new(0, 0, CARRIER_Z)) * scale
	end
	for i, piece in wave.pieces do
		local part = wave.parts[i]
		local offset = piece.offset
		part.CFrame = base
			* CFrame.new(offset.Position * scale + piece.normal * spread * (0.6 + (i % 3) * 0.3))
			* offset.Rotation
		wave.meshes[i].Scale = Vector3.new(scale, scale * thin, scale)
		part.Transparency = piece.alpha + (1 - piece.alpha) * fade
	end
	return e >= 1
end

function WeaponEffects.wave(from: Vector3, to: Vector3, grade: number, hit: boolean)
	if typeof(from) ~= "Vector3" or typeof(to) ~= "Vector3" then
		return
	end
	local distance = (to - from).Magnitude
	if distance < 0.5 or not near((from + to) / 2, distance / 2) then
		return
	end
	local colors = palette(grade)
	local model = Instance.new("Folder")
	model.Name = "바람칼"

	-- 가운데의 보이지 않는 파트: 바람 입자, 꼬리 자취, 소리를 단다
	local carrier = Instance.new("Part")
	carrier.Name = "바람칼심"
	carrier.Anchored = true
	carrier.CanCollide = false
	carrier.CanQuery = false
	carrier.CanTouch = false
	carrier.CastShadow = false
	carrier.Transparency = 1
	carrier.Size = Vector3.new(2 * RADIUS * math.sin(ARC), 0.3, CARRIER_Z * 2 + WIDTH)
	carrier.CFrame = CFrame.lookAt(from, to)
	carrier.Parent = model

	local parts, meshes = {}, {}
	local pieces = WeaponEffects.crescent(grade)
	for _, piece in pieces do
		local part, mesh = glow(piece.layer, piece.size, piece.color, piece.alpha)
		part.CFrame = carrier.CFrame * piece.offset
		part.Parent = model
		table.insert(parts, part)
		table.insert(meshes, mesh)
	end

	-- 꼬리 자취: 두 뿔 끝의 가는 빛줄기, 꼭지점 뒤로 남는 옅은 바람 막
	local horns, hornAt = {}, {}
	local function trail(a: Vector3, b: Vector3, lifetime: number, faceCamera: boolean, alpha: number, width: number)
		local a0 = Instance.new("Attachment")
		local a1 = Instance.new("Attachment")
		a0.Parent = carrier
		a1.Parent = carrier
		table.insert(horns, a0)
		table.insert(hornAt, a)
		table.insert(horns, a1)
		table.insert(hornAt, b)
		local tail = Instance.new("Trail")
		tail.Attachment0 = a0
		tail.Attachment1 = a1
		tail.Color = ColorSequence.new(colors.core, colors.edge)
		tail.Transparency = NumberSequence.new({ kp(0, alpha), kp(1, 1) })
		tail.WidthScale = NumberSequence.new({ kp(0, 1), kp(1, width) })
		tail.LightEmission = 1
		tail.LightInfluence = 0
		tail.Lifetime = lifetime
		tail.MinLength = 0.05
		tail.FaceCamera = faceCamera
		tail.Parent = carrier
	end
	for _, side in { -1, 1 } do
		local horn = arcPoint(side * ARC * 0.97)
		trail(horn + Vector3.new(0, 0.13, 0), horn - Vector3.new(0, 0.13, 0), 0.16, true, 0.1, 0.2)
	end
	trail(Vector3.new(0, 0, -WIDTH * 0.45), Vector3.new(0, 0, WIDTH * 0.45), 0.12, false, 0.55, 0.4)

	-- 바람 입자: 옅은 바람 결과 등급 빛깔의 작은 잎·빛 조각
	local wisps = Instance.new("ParticleEmitter")
	wisps.Texture = TEXTURE.smoke
	wisps.Color = ColorSequence.new(colors.core:Lerp(Color3.new(1, 1, 1), 0.4), colors.edge)
	wisps.LightEmission = 0.6
	wisps.LightInfluence = 0
	wisps.Rate = 70
	wisps.Lifetime = NumberRange.new(0.25, 0.45)
	wisps.Speed = NumberRange.new(1, 3)
	wisps.SpreadAngle = Vector2.new(180, 180)
	wisps.Drag = 3
	wisps.Rotation = NumberRange.new(0, 360)
	wisps.RotSpeed = NumberRange.new(-90, 90)
	wisps.Size = NumberSequence.new({ kp(0, 0.6), kp(1, 2) })
	wisps.Transparency = NumberSequence.new({ kp(0, 0.65), kp(1, 1) })
	wisps.Shape = Enum.ParticleEmitterShape.Box
	wisps.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
	wisps.Parent = carrier

	local motes = Instance.new("ParticleEmitter")
	motes.Texture = TEXTURE.spark
	motes.Color = ColorSequence.new(colors.core, colors.edge)
	motes.LightEmission = 1
	motes.LightInfluence = 0
	motes.Rate = 45
	motes.Lifetime = NumberRange.new(0.3, 0.6)
	motes.Speed = NumberRange.new(3, 8)
	motes.SpreadAngle = Vector2.new(180, 180)
	motes.Drag = 4
	motes.Rotation = NumberRange.new(0, 360)
	motes.RotSpeed = NumberRange.new(-260, 260)
	motes.Squash = NumberSequence.new(0.7) -- 잎처럼 납작하게
	motes.Size = NumberSequence.new({ kp(0, 0.24), kp(1, 0) })
	motes.Shape = Enum.ParticleEmitterShape.Box
	motes.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
	motes.Parent = carrier

	-- 기울기: 부채를 비스듬히 휘두른 결 (매번 조금 다르게)
	rollSide = -rollSide
	local roll = math.rad(ROLL_MIN + math.random() * (ROLL_MAX - ROLL_MIN)) * rollSide
	local travel = math.clamp(distance / WAVE_SPEED, WAVE_TIME_MIN, WAVE_TIME_MAX)
	local wave: Wave = {
		age = 0,
		travel = travel,
		from = from,
		to = to,
		turn = CFrame.Angles(0, 0, roll) * CFrame.Angles(TILT, 0, 0),
		hit = hit == true,
		model = model,
		carrier = carrier,
		horns = horns,
		hornAt = hornAt,
		parts = parts,
		meshes = meshes,
		pieces = pieces,
		wisps = wisps,
		motes = motes,
		ended = false,
	}
	-- 첫 프레임 전에 자리를 잡아 두어야 꼬리 자취가 엉뚱한 데서 시작하지 않는다
	placeWave(wave)
	model.Parent = effectsFolder()
	play(SOUND.wind, carrier, 0.4, 1.45 + math.random() * 0.15)
	table.insert(waves, wave)
	Debris:AddItem(model, travel + WAVE_END + 0.7)
end

local function stepWaves(dt: number)
	for i = #waves, 1, -1 do
		local wave = waves[i]
		wave.age += dt
		if not wave.model.Parent then
			table.remove(waves, i)
			continue
		end
		if not wave.ended and wave.age >= wave.travel then
			wave.ended = true
			wave.wisps.Enabled = false
			wave.motes.Enabled = false
			-- 닿은 자리에서 바람이 한 번 터진다
			wave.wisps:Emit(if wave.hit then 14 else 8)
			wave.motes:Emit(if wave.hit then 22 else 10)
		end
		if placeWave(wave) then
			for _, part in wave.parts do
				part.Transparency = 1
			end
			for _, child in wave.carrier:GetChildren() do
				if child:IsA("Trail") then
					child.Enabled = false
				end
			end
			table.remove(waves, i)
		end
	end
end

---------------------------------------------------------------------------------------------------

function WeaponEffects.start()
	if started then
		return
	end
	started = true
	task.spawn(function()
		local list = {}
		for _, id in SOUND do
			table.insert(list, id)
		end
		for _, id in TEXTURE do
			table.insert(list, id)
		end
		pcall(function()
			ContentProvider:PreloadAsync(list)
		end)
	end)
	RunService.RenderStepped:Connect(function(dt)
		stepSwings(dt)
		stepWaves(dt)
	end)
	-- 내가 맞혔을 때 카메라가 살짝 튄다 (카메라 스크립트가 자리를 잡은 바로 뒤에)
	RunService:BindToRenderStep("무기타격", Enum.RenderPriority.Camera.Value + 1, function()
		local now = os.clock()
		local camera = Workspace.CurrentCamera
		if camera and now < kickUntil then
			local k = (kickUntil - now) / KICK_TIME
			local angle = math.rad(kickPower) * k * k
			camera.CFrame *= CFrame.Angles(angle, angle * kickYaw, 0)
		end
	end)
end

return WeaponEffects
