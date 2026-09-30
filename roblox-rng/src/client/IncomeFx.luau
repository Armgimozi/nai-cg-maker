-- 돈 버는 게 보이게(타이쿤·"steal a …" 게임처럼) — 이 화면에서만 그리는 효과. 수입 규칙·코인·서버 통신은 그대로
-- (DESIGN.md "수입 보이기"). 서버(ParkService)가 칸 모델에 붙인 복제 속성만 읽음: Look(명소 Id) · Income(그 명소의 초당 수입,
-- PlayerState.slotIncomes) · Stars · Top(모형 높이). 값이 바뀔 때만 오고, 초마다 오가는 통신은 없음.
--
--  1) 동전 퐁: 카메라 가까이(POP_DISTANCE) 화면에 보이는 전시 명소마다 가끔 [동전] "+N" 이 모형 옆에서 솟았다 사라짐.
--     N = 그 명소가 지난 퐁 뒤로 번 돈(Income × 간격), 간격은 등급이 높을수록 짧음(POP_EVERY). 화면 전체 초당 POP_RATE 개까지
--     (넘치면 그 퐁은 건너뜀), 빌보드는 POP_POOL 개를 돌려 씀(새로 만들지 않음 — 몇 시간을 켜 둬도 인스턴스가 늘지 않음).
--  2) 내 공원 → 코인: FLY_EVERY 초마다 화면에 보이는 내 명소에서 동전 몇 개가 곡선을 그리며 HUD 코인 알약으로 날아가고, 닿으면
--     알약이 톡(Handlers.Bump). 코인 숫자는 원래처럼 매 프레임 부드럽게 오름. 동전은 HUD 아래 층 ScreenGui 라 알약 "안으로"
--     들어가고 버튼·창을 가리지 않음(입력도 안 막음). 배치 모드(Editing)·창이 열림·굴림 연출 중(Covered)엔 날리지 않고 날던 것도 바로 치움.
--  3) 별이 오르면(칸 Stars 속성이 커짐) 그 칸 이름표(ParkService 이름표 "Body" 의 UIScale "Pop")가 잠깐 커졌다 제자리.
-- 배치 모드 동안은 퐁도 쉼(Editing — 위에서 보기 화면을 깔끔하게. ParkEdit 가 이름표도 끔).
-- 화면 글자는 아이콘 + 숫자뿐, 이모지 없음 — DESIGN.md UI 스타일 가이드 v2.

local GuiService = game:GetService("GuiService")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local ParkGrid = require(Shared.ParkGrid)

local Ui = require(script.Parent.Ui)
local Theme = Ui.Theme

export type Handlers = {
	CoinTarget: () -> Vector2?, -- HUD 코인 아이콘 가운데(메인 ScreenGui 좌표 = 뷰포트 - 상단바). nil 이면 날리지 않음
	Bump: () -> (), -- 날아간 동전이 코인 알약에 닿음
	Editing: () -> boolean, -- 3D 배치 모드: 퐁·날리기 모두 쉼
	Covered: () -> boolean, -- 창이 열림·굴림 연출 중: 날리기만 쉼(월드 퐁은 창 아래라 그대로)
}

-- 동전 퐁 -----------------------------------------------------------------------------
local POP_POOL = 14 -- 빌보드 수(동시에 보이는 퐁 최대)
local POP_RATE = 10 -- 화면 전체 초당 퐁 최대(토큰 통)
local POP_BURST = 6 -- 토큰 통 크기(한꺼번에 몰려 나오지 않게)
local POP_DISTANCE = 70 -- 카메라에서 이보다 먼 명소는 퐁 없음(스터드). 이름표 MaxDistance(60)보다 조금 멀리
-- 등급(Rank 1~7)별 퐁 간격(초): 희귀할수록 자주. 처음 간격은 무작위로 흩어서 같이 터지지 않게
local POP_EVERY = { 4.2, 3.8, 3.3, 2.8, 2.3, 1.9, 1.5 }
local POP_RETRY = 0.35 -- 토큰·빌보드가 없어서 건너뛰면 이만큼 뒤에 다시
local POP_LIFE = 1.15 -- 솟았다 사라지는 시간(초)
-- 퐁은 모형 몸통(높이 20~45%)에서 솟아 모형 꼭대기 아래(최대 90%)에서 사라짐 — 모형 위 이름표를 가리지 않게
local POP_START = { 0.2, 0.45 }
local POP_RISE = { 1.2, 3 } -- 솟는 높이(스터드, 모형 높이 × 0.45 를 이 범위로)
-- 크기: 이름표처럼 월드 크기(높이 POP_STUDS 스터드)로 보이게 띄울 때 한 번 정함(TextScaled·매 프레임 크기 바꾸기 없음).
-- 너무 멀면 읽을 수 있게 최소, 너무 가까우면 화면을 덮지 않게 최대(px)
local POP_STUDS = 2.2 -- 이름표 수입 알약(1.1 스터드)의 두 배쯤 — 돈이 먼저 눈에 띄게
local POP_MIN_PX, POP_MAX_PX = 20, 46
local POP_ASPECT = 3.1 -- 가로 = 세로 × 이 값(동전 + "+12.5K")
local PEDESTAL_TOP = ParkGrid.PEDESTAL_HEIGHT / 2 -- 받침대 가운데 → 윗면

-- 내 공원 → 코인 --------------------------------------------------------------------
local FLY_EVERY = 1.6 -- 몇 초마다 한 번 몰아서
local FLY_POOL = 10
local FLY_MAX = 5 -- 한 번에 날리는 동전 수 최대
local FLY_DISTANCE = 130 -- 이보다 먼 내 명소는 출발점으로 안 씀
local FLY_SECONDS = 0.7
local FLY_STAGGER = 0.07
local FLY_SIZE = 34 -- px(배율 1)
local FLASH_TWEEN = TweenInfo.new(0.16, Enum.EasingStyle.Back, Enum.EasingDirection.Out, 0, true)
local FLASH_SCALE = 1.35 -- 별이 오르면 이름표가 이만큼 커졌다 제자리
local FLASH_DISTANCE = 64 -- 이름표가 보이는 거리 안에서만(이름표 MaxDistance 60 + 여유)

local POP_TEXT = Ui.colorPair("Sun").Face

local IncomeFx = {}

local handlers: Handlers
local clock = 0 -- RenderStepped 로 흐르는 이 모듈의 시계(초)
local random = Random.new()

-- 전시 명소(모든 부지의 명소 칸)
type Statue = {
	Container: Instance,
	Rank: number,
	Income: number,
	Stars: number?,
	Next: number, -- 다음 퐁 시각(clock)
	Connections: { RBXScriptConnection },
}
local statues: { [Instance]: Statue } = {}
local folderConnections: { [Instance]: { RBXScriptConnection } } = {} -- 부지 Slots 폴더마다
local myPlot: Instance? = nil

-- 퐁 빌보드
type Pop = {
	Gui: BillboardGui,
	Coin: ImageLabel,
	Text: TextLabel,
	Stroke: UIStroke,
	Scale: UIScale,
	Busy: boolean,
	Start: number,
	Base: Vector3, -- 받침대 기준 시작 자리(StudsOffsetWorldSpace)
	Rise: number, -- 솟는 높이(스터드)
}
local pops: { Pop } = {}
local popTokens = POP_BURST
local popsSpawned = 0
local popsSkipped = 0
local fxFolder: Folder

-- 날아가는 동전
type Flight = {
	Sprite: ImageLabel,
	Scale: UIScale,
	Busy: boolean,
	Start: number,
	Seconds: number,
	From: Vector2,
	Via: Vector2,
	To: Vector2,
	First: boolean, -- 이 묶음에서 가장 먼저 닿는 동전(닿으면 알약 톡)
}
local flights: { Flight } = {}
local flyGui: ScreenGui
local flyTimer = 0
local flightsSpawned = 0
local bursts = 0

-- 도우미 ----------------------------------------------------------------------------

local function guiInset(): Vector2
	local ok, inset = pcall(function()
		return (GuiService:GetGuiInset())
	end)
	return if ok and typeof(inset) == "Vector2" then inset else Vector2.zero
end

-- 초당 수입·퐁 금액 짧게: "1.8", "12.5K"
local function amountText(amount: number): string
	if amount < 100 then
		local text = string.format("%.1f", math.floor(amount * 10) / 10):gsub("%.0$", "")
		return text
	end
	return Format.short(amount)
end

local function pedestalOf(container: Instance): BasePart?
	local pedestal = container:FindFirstChild("Pedestal")
	return if pedestal and pedestal:IsA("BasePart") then pedestal else nil
end

local function isMine(container: Instance): boolean
	local plot = myPlot
	return plot ~= nil and container:IsDescendantOf(plot)
end

-- 이름표 몸통의 UIScale "Pop"(ParkService addLabel)
local function labelPop(container: Instance): UIScale?
	local pedestal = pedestalOf(container)
	local body = pedestal and pedestal:FindFirstChild("Body", true)
	local pop = body and body:FindFirstChild("Pop")
	return if pop and pop:IsA("UIScale") then pop else nil
end

-- 명소 칸 따라가기 ------------------------------------------------------------------

local function readIncome(container: Instance): number
	local value = container:GetAttribute("Income")
	return if type(value) == "number" and value > 0 then value else 0
end

local function readStars(container: Instance): number?
	local value = container:GetAttribute("Stars")
	return if type(value) == "number" then value else nil
end

local function flashLabel(container: Instance)
	local pedestal = pedestalOf(container)
	local camera = workspace.CurrentCamera
	if not pedestal or not camera then
		return
	end
	if (pedestal.Position - camera.CFrame.Position).Magnitude > FLASH_DISTANCE then
		return -- 이름표가 안 보이는 거리: 트윈을 만들지 않음
	end
	local pop = labelPop(container)
	if pop then
		pop.Scale = 1
		TweenService:Create(pop, FLASH_TWEEN, { Scale = FLASH_SCALE }):Play()
	end
end

local function untrack(container: Instance)
	local statue = statues[container]
	if statue then
		for _, connection in statue.Connections do
			connection:Disconnect()
		end
		statues[container] = nil
	end
end

local function track(container: Instance)
	if statues[container] then
		return
	end
	local look = container:GetAttribute("Look")
	local landmark = if type(look) == "string" then Landmarks.ById[look] else nil
	if not landmark then
		return -- 빈 칸·잠긴 칸(명소 칸 모델은 모습이 바뀌면 새 모델이라 Look 은 그대로)
	end
	local rank = math.clamp(landmark.Tier.Rank, 1, #POP_EVERY)
	local statue: Statue = {
		Container = container,
		Rank = rank,
		Income = readIncome(container),
		Stars = readStars(container),
		Next = clock + random:NextNumber(0.2, POP_EVERY[rank]),
		Connections = {},
	}
	statues[container] = statue
	table.insert(
		statue.Connections,
		container:GetAttributeChangedSignal("Income"):Connect(function()
			statue.Income = readIncome(container)
		end)
	)
	table.insert(
		statue.Connections,
		container:GetAttributeChangedSignal("Stars"):Connect(function()
			local stars = readStars(container)
			local before = statue.Stars
			statue.Stars = stars
			if stars and before and stars > before then
				flashLabel(container) -- 별 +1: 이름표가 톡
			end
		end)
	)
end

local function watchSlots(folder: Instance)
	if folderConnections[folder] then
		return
	end
	folderConnections[folder] = {
		folder.ChildAdded:Connect(track),
		folder.ChildRemoved:Connect(untrack),
	}
	for _, container in folder:GetChildren() do
		track(container)
	end
end

local function watchPlot(plot: Instance)
	local folder = plot:FindFirstChild("Slots")
	if folder then
		watchSlots(folder)
		return
	end
	task.spawn(function()
		local found = plot:WaitForChild("Slots", 30)
		if found and plot.Parent then
			watchSlots(found)
		end
	end)
end

-- 동전 퐁 -----------------------------------------------------------------------------

local function newPop(index: number): Pop
	local gui = Ui.new("BillboardGui", {
		Name = "Pop" .. index,
		Size = UDim2.fromOffset(POP_MAX_PX * POP_ASPECT, POP_MAX_PX),
		AlwaysOnTop = true,
		LightInfluence = 0,
		MaxDistance = POP_DISTANCE + 10,
		Enabled = false,
		Active = false,
		Parent = fxFolder,
	})
	local body = Ui.new("Frame", {
		Name = "Body",
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		Parent = gui,
	})
	local scale = Ui.new("UIScale", { Parent = body })
	local coin = Ui.new("ImageLabel", {
		Name = "Coin",
		BackgroundTransparency = 1,
		Image = Ui.imageId("coin") or "",
		BackgroundColor3 = POP_TEXT,
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.fromScale(0, 0.5),
		Size = UDim2.fromScale(0.3, 0.9),
		SizeConstraint = Enum.SizeConstraint.RelativeYY,
		Parent = body,
	})
	if coin.Image == "" then
		-- 그림이 없으면 해 색 동그라미
		coin.BackgroundTransparency = 0
		Ui.round().Parent = coin
		Ui.stroke(Theme.Ink, 2).Parent = coin
	end
	local text = Ui.new("TextLabel", {
		Name = "Amount",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.fromScale(0.3, 0.5),
		Size = UDim2.fromScale(0.7, 1),
		Font = Theme.Font,
		TextSize = 24,
		TextColor3 = POP_TEXT,
		TextXAlignment = Enum.TextXAlignment.Left,
		Text = "",
		Parent = body,
	})
	local stroke = Ui.outline(text, 2.5)
	return {
		Gui = gui,
		Coin = coin,
		Text = text,
		Stroke = stroke,
		Scale = scale,
		Busy = false,
		Start = 0,
		Base = Vector3.zero,
		Rise = 0,
	}
end

local function freePop(): Pop?
	for _, pop in pops do
		if not pop.Busy then
			return pop
		end
	end
	return nil
end

local function setPopFade(pop: Pop, alpha: number)
	pop.Text.TextTransparency = alpha
	pop.Stroke.Transparency = alpha
	pop.Coin.ImageTransparency = alpha
	if pop.Coin.Image == "" then
		pop.Coin.BackgroundTransparency = alpha
	end
end

-- 명소 하나에서 퐁. 반환: 띄웠는지. 크기는 이름표처럼 월드 크기(POP_STUDS)로 보이게 이 거리에서 한 번 정함
local function spawnPop(statue: Statue, pedestal: BasePart, camera: Camera, distance: number, amount: number): boolean
	local pop = freePop()
	if not pop or popTokens < 1 then
		return false
	end
	popTokens -= 1
	popsSpawned += 1
	local top = statue.Container:GetAttribute("Top")
	local height = if type(top) == "number" and top > 0 then top else 4
	-- 화면에서 모형 왼쪽·오른쪽 옆(카메라 오른쪽 방향)에서 솟음 — 모형 앞·위를 덮지 않게
	local right = camera.CFrame.RightVector
	local flat = Vector3.new(right.X, 0, right.Z)
	flat = if flat.Magnitude > 1e-3 then flat.Unit else Vector3.new(1, 0, 0)
	local side = random:NextNumber(1.6, 2.6) * (if random:NextNumber() < 0.5 then -1 else 1)
	pop.Base = flat * side + Vector3.new(0, PEDESTAL_TOP + height * random:NextNumber(POP_START[1], POP_START[2]), 0)
	pop.Rise = math.clamp(height * 0.45, POP_RISE[1], POP_RISE[2])
	pop.Busy = true
	pop.Start = clock
	local perStud = camera.ViewportSize.Y / (2 * math.tan(math.rad(camera.FieldOfView) / 2) * math.max(distance, 1))
	local h = math.clamp(POP_STUDS * perStud, POP_MIN_PX, POP_MAX_PX)
	pop.Gui.Size = UDim2.fromOffset(h * POP_ASPECT, h)
	pop.Text.TextSize = math.floor(h * 0.62 + 0.5)
	pop.Text.Text = "+" .. amountText(amount)
	pop.Gui.Adornee = pedestal
	pop.Gui.StudsOffsetWorldSpace = pop.Base
	pop.Scale.Scale = 0.6
	setPopFade(pop, 0)
	pop.Gui.Enabled = true
	return true
end

local function stepPops(dt: number)
	popTokens = math.min(POP_BURST, popTokens + POP_RATE * dt)
	for _, pop in pops do
		if pop.Busy then
			local t = (clock - pop.Start) / POP_LIFE
			local adornee = pop.Gui.Adornee
			if t >= 1 or not adornee or not adornee.Parent then
				pop.Busy = false
				pop.Gui.Enabled = false
				pop.Gui.Adornee = nil
			else
				local rise = 1 - (1 - t) ^ 2
				pop.Gui.StudsOffsetWorldSpace = pop.Base + Vector3.new(0, pop.Rise * rise, 0)
				pop.Scale.Scale = if t < 0.14
					then 0.6 + 0.55 * (t / 0.14)
					elseif t < 0.26 then 1.15 - 0.15 * ((t - 0.14) / 0.12)
					else 1
				setPopFade(pop, if t < 0.55 then 0 else (t - 0.55) / 0.45)
			end
		end
	end
end

local function stopPops()
	for _, pop in pops do
		if pop.Busy then
			pop.Busy = false
			pop.Gui.Enabled = false
			pop.Gui.Adornee = nil
		end
	end
end

-- 때가 된 명소마다: 가까이·화면 안이면 퐁(토큰·빌보드가 없으면 조금 뒤에 다시), 아니면 다음 차례로
local function schedulePops(camera: Camera, editing: boolean)
	local eye = camera.CFrame.Position
	for container, statue in statues do
		if clock >= statue.Next then
			local every = POP_EVERY[statue.Rank]
			local pedestal = pedestalOf(container)
			if editing or statue.Income <= 0 or not pedestal or not container.Parent then
				statue.Next = clock + every
			else
				local distance = (pedestal.Position - eye).Magnitude
				local _, inside = camera:WorldToViewportPoint(pedestal.Position + Vector3.new(0, PEDESTAL_TOP + 2, 0))
				if distance > POP_DISTANCE or not inside then
					statue.Next = clock + every
				elseif spawnPop(statue, pedestal, camera, distance, statue.Income * every) then
					statue.Next = clock + every
				else
					popsSkipped += 1
					statue.Next = clock + POP_RETRY + random:NextNumber(0, POP_RETRY)
				end
			end
		end
	end
end

-- 날아가는 동전 -------------------------------------------------------------------

local function newFlight(index: number): Flight
	local sprite = Ui.new("ImageLabel", {
		Name = "Coin" .. index,
		BackgroundTransparency = 1,
		BackgroundColor3 = POP_TEXT,
		Image = Ui.imageId("coin") or "",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Size = UDim2.fromOffset(FLY_SIZE, FLY_SIZE),
		Active = false,
		Visible = false,
		Parent = flyGui,
	})
	if sprite.Image == "" then
		sprite.BackgroundTransparency = 0
		Ui.round().Parent = sprite
		Ui.stroke(Theme.Ink, 2).Parent = sprite
	end
	local scale = Ui.new("UIScale", { Parent = sprite })
	return {
		Sprite = sprite,
		Scale = scale,
		Busy = false,
		Start = 0,
		Seconds = FLY_SECONDS,
		From = Vector2.zero,
		Via = Vector2.zero,
		To = Vector2.zero,
		First = false,
	}
end

local function stopFlights()
	for _, flight in flights do
		if flight.Busy then
			flight.Busy = false
			flight.Sprite.Visible = false
		end
	end
end

local function bezier(a: Vector2, b: Vector2, c: Vector2, t: number): Vector2
	local u = 1 - t
	return a * (u * u) + b * (2 * u * t) + c * (t * t)
end

-- 곡선 가운데 점: 두 점 가운데에서 위로(화면 위쪽 = 코인 알약 쪽) 부풀림 — IncomeFx.curveVia(목업도 같은 식)
function IncomeFx.curveVia(from: Vector2, to: Vector2, bend: number): Vector2
	local mid = (from + to) / 2
	local lift = math.min(220, (to - from).Magnitude * 0.35)
	return mid + Vector2.new(bend * lift * 0.5, -lift)
end

-- 화면에 보이는 내 명소 출발점(메인 ScreenGui 좌표, 수입 큰 순서)
local function flySources(camera: Camera): { Vector2 }
	local eye = camera.CFrame.Position
	local inset = guiInset()
	local found: { { At: Vector2, Income: number } } = {}
	for container, statue in statues do
		if statue.Income > 0 and isMine(container) then
			local pedestal = pedestalOf(container)
			if pedestal and (pedestal.Position - eye).Magnitude <= FLY_DISTANCE then
				local top = container:GetAttribute("Top")
				local height = if type(top) == "number" then top else 4
				local point = pedestal.Position + Vector3.new(0, PEDESTAL_TOP + height * 0.6, 0)
				local screen, inside = camera:WorldToViewportPoint(point)
				if inside and screen.Z > 0 then
					table.insert(found, { At = Vector2.new(screen.X, screen.Y) - inset, Income = statue.Income })
				end
			end
		end
	end
	table.sort(found, function(a, b)
		return a.Income > b.Income
	end)
	local list = {}
	for _, entry in found do
		table.insert(list, entry.At)
	end
	return list
end

local function launch(camera: Camera): boolean
	local target = handlers.CoinTarget()
	if not target then
		return false
	end
	local sources = flySources(camera)
	if #sources == 0 then
		return false -- 내 공원이 화면에 없음
	end
	local count = math.clamp(#sources, 2, FLY_MAX)
	local launched = 0
	bursts += 1
	for index = 1, count do
		local flight: Flight? = nil
		for _, candidate in flights do
			if not candidate.Busy then
				flight = candidate
				break
			end
		end
		if not flight then
			break
		end
		local from = sources[(index - 1) % #sources + 1]
			+ Vector2.new(random:NextNumber(-10, 10), random:NextNumber(-8, 8))
		flight.Busy = true
		flight.Start = clock + (index - 1) * FLY_STAGGER
		flight.Seconds = FLY_SECONDS + random:NextNumber(-0.08, 0.12)
		flight.From = from
		flight.To = target
		flight.Via = IncomeFx.curveVia(from, target, random:NextNumber(-1, 1))
		flight.First = index == 1
		flight.Sprite.Position = UDim2.fromOffset(from.X, from.Y)
		flight.Sprite.Size = UDim2.fromOffset(FLY_SIZE * Ui.scale(), FLY_SIZE * Ui.scale())
		flight.Sprite.Visible = false -- 차례가 오면 보임
		flight.Scale.Scale = 1
		launched += 1
		flightsSpawned += 1
	end
	return launched > 0
end

local function stepFlights()
	for _, flight in flights do
		if flight.Busy and clock >= flight.Start then
			local t = (clock - flight.Start) / flight.Seconds
			if t >= 1 then
				flight.Busy = false
				flight.Sprite.Visible = false
				if flight.First then
					handlers.Bump()
				end
			else
				local eased = t * t * (3 - 2 * t)
				local at = bezier(flight.From, flight.Via, flight.To, eased)
				flight.Sprite.Position = UDim2.fromOffset(at.X, at.Y)
				flight.Scale.Scale = if t < 0.15 then 0.5 + t / 0.15 * 0.7 else 1.2 - 0.45 * t
				flight.Sprite.Visible = true
			end
		end
	end
end

-- 매 프레임 --------------------------------------------------------------------------

local function step(dt: number)
	clock += dt
	local camera = workspace.CurrentCamera
	if not camera then
		return
	end
	local editing = handlers.Editing()
	if editing then
		stopPops()
	end
	stepPops(dt)
	schedulePops(camera, editing)

	local quiet = editing or handlers.Covered()
	if quiet then
		stopFlights()
		flyTimer = 0
	else
		flyTimer += dt
		if flyTimer >= FLY_EVERY then
			flyTimer = 0
			launch(camera)
		end
		stepFlights()
	end
end

-- 공개 -------------------------------------------------------------------------------

-- 내 부지(OwnerUserId = 내 UserId 인 부지 모델, 없으면 nil) — 날아가는 동전의 출발점
function IncomeFx.setPlot(model: Instance?)
	myPlot = model
	if model then
		watchPlot(model)
	end
end

-- 스모크 테스트용 숫자: 보이는 퐁·날아가는 동전, 지금까지 띄운 수, 따라가는 명소 수, 만든 인스턴스 수
function IncomeFx.stats(): { [string]: number }
	local activePops, activeFlights = 0, 0
	for _, pop in pops do
		if pop.Busy then
			activePops += 1
		end
	end
	for _, flight in flights do
		if flight.Busy then
			activeFlights += 1
		end
	end
	local tracked = 0
	for _ in statues do
		tracked += 1
	end
	return {
		Pops = activePops,
		PopsSpawned = popsSpawned,
		PopsSkipped = popsSkipped,
		Flights = activeFlights,
		FlightsSpawned = flightsSpawned,
		Bursts = bursts,
		Statues = tracked,
		Instances = #fxFolder:GetDescendants() + #flyGui:GetDescendants(),
	}
end

-- 이 명소 칸이 지금 버는 초당 수입(따라가는 명소가 아니면 nil) — 스모크 테스트용
function IncomeFx.statueIncome(container: Instance): number?
	local statue = statues[container]
	return if statue then statue.Income else nil
end

function IncomeFx.init(playerGui: PlayerGui, callbacks: Handlers)
	handlers = callbacks
	fxFolder = Ui.new("Folder", { Name = "IncomeFx", Parent = workspace })
	for index = 1, POP_POOL do
		table.insert(pops, newPop(index))
	end
	-- 날아가는 동전: HUD(DisplayOrder 0)보다 아래 층 — 알약·버튼·창 뒤로 들어가고 입력을 막지 않음
	flyGui = Ui.new("ScreenGui", {
		Name = "IncomeFx",
		ResetOnSpawn = false,
		DisplayOrder = -1,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = playerGui,
	})
	for index = 1, FLY_POOL do
		table.insert(flights, newFlight(index))
	end
	task.spawn(function()
		local parks = workspace:FindFirstChild("Parks") or workspace:WaitForChild("Parks", 60)
		if not parks then
			return
		end
		parks.ChildAdded:Connect(watchPlot)
		for _, plot in parks:GetChildren() do
			watchPlot(plot)
		end
	end)
	RunService.RenderStepped:Connect(step)
end

return IncomeFx
