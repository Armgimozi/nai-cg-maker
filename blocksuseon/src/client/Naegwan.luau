-- 내관(內觀) 창: 운기조식 중에 단전 안을 들여다보며 하는 미니게임.
-- 문제는 서버가 준 seed 로 shared/Trials.luau 가 만든다. 끝나면 답을 서버에 보내고, 서버가 맞춰 본다.
-- 모든 방식은 클릭이나 탭만 쓴다 (숫자 키·이동 키와 겹치지 않는다).

local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Trials = require(Shared.Trials)
local Roots = require(Shared.Roots)
local Ui = require(script.Parent.Ui)

local C = Ui.C
local new, image, text, row = Ui.new, Ui.image, Ui.text, Ui.row

local Naegwan = {}

export type Payload = {
	id: number,
	mode: string,
	seed: number,
	params: { [string]: any },
	title: string,
	hint: string?,
}

local ui: { [string]: any } = {}
local send: (payload: { [string]: any }) -> ()
local cancel: () -> ()
local current: Payload? = nil
local connections: { RBXScriptConnection } = {}
local startedAt = 0

local function disconnectAll()
	for _, connection in connections do
		connection:Disconnect()
	end
	table.clear(connections)
end

-- 연결을 끊은 뒤에도 같은 프레임에 남은 콜백이 지운 창을 건드리지 않게 세대를 센다
local generation = 0

local function clearStage()
	generation += 1
	disconnectAll()
	for _, child in ui.stage:GetChildren() do
		child:Destroy()
	end
end

local function circle(size: number, color: Color3, props: { [string]: any }?): Frame
	local frame = new("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Size = UDim2.fromOffset(size, size),
		BackgroundColor3 = color,
		BorderSizePixel = 0,
	}, { new("UICorner", { CornerRadius = UDim.new(1, 0) }) })
	for key, value in props or {} do
		(frame :: any)[key] = value
	end
	return frame
end

local function setStatus(message: string, color: Color3?)
	ui.status:set(message)
	ui.status:setColor(color or C.cream)
end

local function finish(ok: boolean, answer: any)
	local payload = current
	if not payload then
		return
	end
	current = nil
	clearStage()
	ui.panel.Visible = false
	send({ id = payload.id, ok = ok, answer = answer, elapsed = os.clock() - startedAt })
end

-- 박자: 도는 점이 음·양 자리에 닿을 때 누른다 -----------------------------------------------

local function playRhythm(params: { [string]: any })
	local stage = ui.stage
	local center = Vector2.new(260, 120)
	local radius = 96
	local ring = circle(radius * 2, C.ink, {
		Position = UDim2.fromOffset(center.X, center.Y),
		BackgroundTransparency = 0.4,
		Parent = stage,
	})
	local stroke = new("UIStroke", { Color = C.gold, Thickness = 3, Transparency = 0.2, Parent = ring })

	local function target(angle: number, color: Color3, label: string, labelColor: Color3)
		local position = center + Vector2.new(math.sin(angle), -math.cos(angle)) * radius
		local dot = circle(46, color, { Position = UDim2.fromOffset(position.X, position.Y), Parent = stage })
		new("UIStroke", { Color = C.gold, Thickness = 2, Parent = dot })
		local labelRow = row({ Size = UDim2.new(1, 0, 1, -4), Parent = dot })
		text("title", 24, { color = labelColor, text = label, parent = labelRow })
		local scale = new("UIScale", { Parent = dot })
		return scale
	end
	local yangScale = target(math.pi / 2, Color3.fromRGB(236, 226, 200), "양", C.ink)
	local eumScale = target(math.pi * 1.5, Color3.fromRGB(30, 34, 52), "음", C.cream)

	local mote = circle(22, C.jade, { Parent = stage })
	new("UIStroke", { Color = Color3.new(1, 1, 1), Thickness = 2, Parent = mote })
	local countRow = row({
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset(center.X, center.Y + 14),
		Size = UDim2.fromOffset(160, 50),
		Parent = stage,
	})
	local countText = text("title", 34, { gradient = Ui.GOLD_TEXT, parent = countRow })

	local hitArea = new("TextButton", {
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Text = "",
		ZIndex = 3,
		Parent = stage,
	})

	local beats = params.beats or 12
	local interval = params.interval or 0.9
	local tolerance = 0.45 * (params.band or 1)
	local angle = 0
	local nextAngle = math.pi / 2
	local count = 0
	local flashUntil = 0

	local function refresh()
		countText:set(string.format("%d / %d", count, beats))
	end
	refresh()
	setStatus(
		if params.streak
			then "점이 음과 양에 닿는 순간 누른다. 놓치면 처음부터다."
			else "점이 음과 양에 닿는 순간 누른다."
	)

	local function miss()
		flashUntil = os.clock() + 0.25
		stroke.Color = C.red
		if params.streak then
			count = 0
			refresh()
		end
	end

	table.insert(
		connections,
		hitArea.Activated:Connect(function()
			local diff = angle - nextAngle
			if math.abs(diff) <= tolerance then
				local isYang = math.floor((nextAngle - math.pi / 2) / math.pi + 0.5) % 2 == 0
				local scale = if isYang then yangScale else eumScale
				scale.Scale = 1.25
				Ui.tween(scale, TweenInfo.new(0.25), { Scale = 1 })
				nextAngle += math.pi
				count += 1
				if params.speedUp then
					interval = math.max(0.5, interval * 0.97)
				end
				refresh()
				if count >= beats then
					setStatus("음양이 하나로 돈다.", C.jade)
					task.delay(0.4, finish, true, true)
				end
			elseif diff < -tolerance then
				miss()
			end
		end)
	)

	local mine = generation
	table.insert(
		connections,
		RunService.Heartbeat:Connect(function(dt)
			if count >= beats or mine ~= generation then
				return
			end
			angle += math.pi * dt / interval
			if angle > nextAngle + tolerance then
				nextAngle += math.pi
				miss()
			end
			local position = center + Vector2.new(math.sin(angle), -math.cos(angle)) * radius
			mote.Position = UDim2.fromOffset(position.X, position.Y)
			if os.clock() > flashUntil then
				stroke.Color = C.gold
			end
		end)
	)
end

-- 균형: 농도 막대의 바늘을 금색 띠 안에 붙잡는다 ------------------------------------------------

local function playBalance(params: { [string]: any }, puzzle)
	local stage = ui.stage
	local labels: { string } = params.labels or {}
	local count = math.max(1, params.bars or 1)
	local band = params.band or 1
	local turbulence = params.turbulence or 1
	local target = params.target or 20
	local rand = Trials.rng(current and current.seed or 1)
	local _ = puzzle

	local trackHeight = 190
	local width = 54
	local gap = 26
	local totalWidth = count * width + (count - 1) * gap
	local left = 260 - totalWidth / 2
	local halfBand = math.min(0.24, 0.1 * band)
	local rise = 0.5
	local fall = 0.11 + 0.03 * turbulence

	local bars = {}
	for i = 1, count do
		local x = left + (i - 1) * (width + gap)
		local track = new("Frame", {
			Position = UDim2.fromOffset(x, 18),
			Size = UDim2.fromOffset(width, trackHeight),
			BackgroundColor3 = C.ink,
			BackgroundTransparency = 0.25,
			BorderSizePixel = 0,
			Parent = stage,
		}, {
			new("UICorner", { CornerRadius = UDim.new(0, 10) }),
			new("UIStroke", { Color = C.gold, Thickness = 2, Transparency = 0.4 }),
		})
		local center = 0.35 + rand() * 0.35
		local bandFrame = new("Frame", {
			AnchorPoint = Vector2.new(0, 0.5),
			Position = UDim2.new(0, 3, 1 - center, 0),
			Size = UDim2.new(1, -6, halfBand * 2, 0),
			BackgroundColor3 = Color3.fromRGB(226, 188, 110),
			BackgroundTransparency = 0.45,
			BorderSizePixel = 0,
			Parent = track,
		}, { new("UICorner", { CornerRadius = UDim.new(0, 6) }) })
		local needle = new("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Size = UDim2.new(1, 8, 0, 5),
			BackgroundColor3 = C.jade,
			BorderSizePixel = 0,
			Parent = track,
		}, { new("UICorner", { CornerRadius = UDim.new(1, 0) }) })
		local button = new("TextButton", {
			Size = UDim2.fromScale(1, 1),
			BackgroundTransparency = 1,
			Text = "",
			Parent = track,
		})
		local labelRow = row({
			Position = UDim2.fromOffset(x - 20, trackHeight + 20),
			Size = UDim2.fromOffset(width + 40, 30),
			Parent = stage,
		})
		local label = labels[i]
		text("title", 22, { color = C.cream, text = label or "", parent = labelRow })
		local bar = {
			value = center,
			center = center,
			holding = false,
			phase = rand() * math.pi * 2,
			speed = 1.2 + rand() * 1.4,
			needle = needle,
			band = bandFrame,
		}
		table.insert(
			connections,
			button.MouseButton1Down:Connect(function()
				bar.holding = true
			end)
		)
		table.insert(
			connections,
			button.MouseButton1Up:Connect(function()
				bar.holding = false
			end)
		)
		table.insert(
			connections,
			button.MouseLeave:Connect(function()
				bar.holding = false
			end)
		)
		bars[i] = bar
	end
	table.insert(
		connections,
		UserInputService.InputEnded:Connect(function(input)
			if
				input.UserInputType == Enum.UserInputType.MouseButton1
				or input.UserInputType == Enum.UserInputType.Touch
			then
				for _, bar in bars do
					bar.holding = false
				end
			end
		end)
	)

	local progressTrack = image("barTrack", {
		Position = UDim2.fromOffset(110, trackHeight + 56),
		Size = UDim2.fromOffset(300, 16),
		SliceScale = 0.6,
		Parent = stage,
	})
	local progressFill = image("barGold", {
		Position = UDim2.fromOffset(3, 3),
		Size = UDim2.fromOffset(0, 10),
		SliceScale = 0.5,
		Parent = progressTrack,
	})

	setStatus("막대를 누르고 있으면 바늘이 오른다. 모든 바늘을 금색 띠 안에 둔다.")
	local held = 0
	local clock = 0
	local done = false
	local mine = generation
	table.insert(
		connections,
		RunService.Heartbeat:Connect(function(dt)
			if done or mine ~= generation then
				return
			end
			clock += dt
			local allIn = true
			for _, bar in bars do
				local drift = math.sin(clock * bar.speed + bar.phase) * 0.06 * turbulence
				local push = if bar.holding then rise else -fall
				bar.value = math.clamp(bar.value + (push + drift) * dt, 0, 1)
				bar.needle.Position = UDim2.fromScale(0.5, 1 - bar.value)
				local inside = math.abs(bar.value - bar.center) <= halfBand
				bar.needle.BackgroundColor3 = if inside then C.jade else C.red
				if not inside then
					allIn = false
				end
			end
			if allIn then
				held += dt
			else
				held = math.max(0, held - dt * 0.5)
			end
			progressFill.Size = UDim2.fromOffset(294 * math.clamp(held / target, 0, 1), 10)
			progressFill.Visible = held > 0.2
			if held >= target then
				done = true
				setStatus("농도가 고요히 가라앉았다.", C.jade)
				task.delay(0.4, finish, true, true)
			end
		end)
	)
end

-- 공개 ---------------------------------------------------------------------------------

local PLAYERS = {
	rhythm = playRhythm,
	balance = playBalance,
}

function Naegwan.supports(mode: string): boolean
	return PLAYERS[mode] ~= nil
end

function Naegwan.build(gui: ScreenGui, onResult: (payload: { [string]: any }) -> (), onCancel: () -> ())
	send = onResult
	cancel = onCancel
	local panel = image("panel", {
		Name = "Naegwan",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.46),
		Size = UDim2.fromOffset(600, 470),
		SliceScale = 0.8,
		Visible = false,
		Active = true,
		ZIndex = 6,
		Parent = gui,
	})
	new("UIScale", { Parent = panel })
	ui.panel = panel
	local titleRow = row({ Position = UDim2.fromOffset(0, 20), Size = UDim2.new(1, 0, 0, 52), Parent = panel })
	ui.title = text("title", 34, { gradient = Ui.GOLD_TEXT, parent = titleRow })
	local hintHolder, setHint = Ui.paragraph("body", 14, 520, 2, C.dim, panel)
	hintHolder.Position = UDim2.fromOffset(40, 74)
	ui.setHint = setHint
	ui.stage = new("Frame", {
		Name = "Stage",
		Position = UDim2.fromOffset(40, 120),
		Size = UDim2.fromOffset(520, 270),
		BackgroundTransparency = 1,
		Parent = panel,
	})
	local statusRow = row({ Position = UDim2.fromOffset(0, 392), Size = UDim2.new(1, 0, 0, 26), Parent = panel })
	ui.status = text("body", 15, { color = C.cream, parent = statusRow })

	local stop = Ui.pill("그만두기", 110, 34, 15, panel, function()
		if current then
			current = nil
			clearStage()
			panel.Visible = false
			cancel()
		end
	end)
	stop.AnchorPoint = Vector2.new(1, 1)
	stop.Position = UDim2.new(1, -30, 1, -22)
end

function Naegwan.isOpen(): boolean
	return current ~= nil
end

-- 서버가 내관을 열었다
function Naegwan.open(payload: Payload, root: Roots.Root?)
	clearStage()
	local player = PLAYERS[payload.mode]
	if not player then
		warn("[블록수선전] 아직 없는 내관 방식:", payload.mode)
		cancel()
		return
	end
	current = payload
	startedAt = os.clock()
	ui.title:set(payload.title)
	ui.setHint(payload.hint or "")
	ui.panel.Visible = true
	local params = table.clone(payload.params)
	if payload.mode == "balance" and not params.labels and root then
		params.labels = {}
		for i, element in root.elements do
			params.labels[i] = Roots.ELEMENT[element].name
		end
	end
	player(params, Trials.generate(payload.mode, payload.seed, payload.params))
end

-- 서버가 닫았다 (결과 처리 뒤, 또는 쓰러짐)
function Naegwan.close()
	if current then
		current = nil
	end
	clearStage()
	if ui.panel then
		ui.panel.Visible = false
	end
end

return Naegwan
