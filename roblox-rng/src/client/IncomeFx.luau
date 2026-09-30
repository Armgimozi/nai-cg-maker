-- 돈 버는 게 보이게(타이쿤·"steal a …" 게임처럼) — 이 화면에서만 그리는 효과. 수입 규칙·코인·서버 통신은 그대로
-- (DESIGN.md "수입 보이기"). 서버(ParkService)가 칸 모델에 붙인 복제 속성만 읽음: Look(명소 Id) · Income(그 명소의 초당 수입,
-- PlayerState.slotIncomes) · Stars · Top(모형 높이). 값이 바뀔 때만 오고, 초마다 오가는 통신은 없음.
--
--  1) 동전 퐁: 카메라 가까이(POP_DISTANCE) 화면에 보이는(가려지지 않은 — 광선 하나) 전시 명소마다 가끔 [동전] "+N" 이 모형
--     가장자리 바깥쪽에서 솟았다 사라짐(모형·이름표를 안 덮음). N = 그 명소가 지난 퐁(또는 보이기 시작한 때) 뒤로 번 돈
--     (Income × 지난 시간, 간격 × POP_CATCHUP 까지), 간격은 등급이 높을수록 짧음(POP_EVERY). 화면 전체 초당 10개까지 — 내 공원
--     몫 6 + 남의 공원 몫 4(토큰 통 둘, 내 퐁은 내 몫이 비면 남의 몫도 씀, 남의 공원은 간격 두 배). 넘치면 그 퐁은 건너뛰고,
--     빌보드는 POP_POOL 개를 돌려 씀(새로 만들지 않음 — 몇 시간을 켜 둬도 인스턴스가 늘지 않음).
--  2) 내 공원 → 코인: FLY_EVERY 초마다 화면에 보이는 내 명소에서 동전 몇 개가 곡선을 그리며 HUD 코인 알약의 동전 아이콘으로
--     날아가 작아지며 스며들고, 닿을 때마다 아이콘이 톡(Handlers.Bump). 코인 숫자는 원래처럼 매 프레임 부드럽게 오름. 동전은 HUD
--     바로 위 층 ScreenGui(입력은 안 막음 — Active 없는 그림). 배치 모드(Editing)·창이 열림·굴림 연출 중(Covered)엔 날리지 않고
--     날던 것도 바로 치움 — 창·배치 화면을 가리지 않음.
--  3) 별이 오르면(칸 Stars 속성이 커짐) 그 칸 이름표(ParkService 이름표 "Body" 의 UIScale "Pop")가 잠깐 커졌다 제자리.
--  4) 이름표 거리 단계: LOD_FAR 보다 먼 이름표는 이름·별("Head")을 끄고 수입 알약만 — 여러 공원이 한 화면에 있어도 덜 복잡하고
--     TextScaled 도 덜 셈(0.25초마다, 바뀔 때만 씀).
-- 배치 모드 동안은 퐁도 쉼(Editing — 위에서 보기 화면을 깔끔하게. ParkEdit 가 이름표도 끔).
-- 화면 글자는 아이콘 + 숫자뿐, 이모지 없음 — DESIGN.md UI 스타일 가이드 v2.

local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
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
-- 토큰 통(초당 개수, 한꺼번에): 내 공원 몫 + 남의 공원 몫 = 화면 전체 초당 10개까지
local POP_RATE_MINE, POP_BURST_MINE = 6, 4
local POP_RATE_OTHERS, POP_BURST_OTHERS = 4, 3
local POP_OTHERS_SLOWER = 2 -- 남의 공원 명소는 간격 × 이만큼(반만 자주)
local POP_DISTANCE = 70 -- 카메라에서 이보다 먼 명소는 퐁 없음(스터드). 이름표 MaxDistance(60)보다 조금 멀리
-- 등급(Rank 1~7)별 퐁 간격(초): 희귀할수록 자주, 가장 잦아도 2.2초(퐁 1.15초 — 모형 옆이 반 넘게 비어 있게).
-- 처음 간격은 무작위로 흩어서 같이 터지지 않게
local POP_EVERY = { 4.4, 4, 3.6, 3.2, 2.8, 2.5, 2.2 }
local POP_CATCHUP = 3 -- 퐁 금액은 지난 퐁 뒤로 번 돈, 간격 × 이만큼까지(건너뛴 만큼 쌓임)
local POP_RETRY = 0.35 -- 토큰·빌보드가 없어서 건너뛰면 이만큼 뒤에 다시
local POP_LIFE = 1.15 -- 솟았다 사라지는 시간(초)
-- 퐁 자리: 모형 가장자리(카메라 오른쪽 방향 ± POP_EDGE)에서 바깥쪽으로 뻗음 — 모형을 안 덮음. 높이는 모형 몸통(20~45%)에서
-- 솟아 퐁 위 끝이 모형 꼭대기 - POP_TOP_GAP 을 넘지 않음(모형 위 이름표·수입 알약을 안 가림)
local POP_EDGE = ParkGrid.MINIATURE_SIZE / 2
local POP_START = { 0.2, 0.45 }
local POP_RISE = { 0.4, 3 } -- 솟는 높이(스터드): 모형 높이 × 0.45, 이 범위 안
local POP_TOP_GAP = 0.2
-- 크기: 이름표처럼 월드 크기(높이 POP_STUDS 스터드)로 보이게 띄울 때 한 번 정함(TextScaled·매 프레임 크기 바꾸기 없음).
-- 너무 멀면 읽을 수 있게 최소, 너무 가까우면 화면을 덮지 않게 최대(px). 폭은 글자 수에 맞춤(동전 + "+144")
local POP_STUDS = 2.2
local POP_MIN_PX, POP_MAX_PX = 20, 46
local PEDESTAL_TOP = ParkGrid.PEDESTAL_HEIGHT / 2 -- 받침대 가운데 → 윗면

-- 이름표 거리 단계: 이보다 멀면 이름·별(Head)을 끄고 수입 알약만, LOD_NEAR 안으로 오면 다시 켬(경계에서 깜빡이지 않게)
local LOD_FAR, LOD_NEAR = 30, 27
local LOD_EVERY = 0.25

-- 내 공원 → 코인 --------------------------------------------------------------------
local FLY_EVERY = 1.6 -- 몇 초마다 한 번 몰아서
local FLY_POOL = 10
local FLY_MAX = 5 -- 한 번에 날리는 동전 수 최대
local FLY_DISTANCE = 130 -- 이보다 먼 내 명소는 출발점으로 안 씀
local FLY_SECONDS = 0.7
local FLY_STAGGER = 0.07
local FLY_SIZE = 34 -- px(배율 1)
local FLY_SINK = 0.85 -- 이 뒤(비행 비율)로는 아이콘 속으로 작아지며(0.4 배) 흐려짐
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
	Since: number, -- 지난 퐁(또는 보이기 시작한 때) 시각 — 퐁 금액 = Income × (지금 - Since)
	Head: GuiObject?, -- 이름표 "Head"(이름·별) — 거리 단계로 켜고 끔
	Far: boolean?, -- 지금 Head 를 끈 상태인지(nil = 아직 모름)
	Connections: { RBXScriptConnection },
}
local statues: { [Instance]: Statue } = {}
local folderConnections: { [Instance]: { RBXScriptConnection } } = {} -- 부지 Slots 폴더마다
local myPlot: Instance? = nil

-- 퐁 빌보드: 폭은 퐁 몸통의 두 배, 몸통은 바깥쪽 절반 — 빌보드 가운데(모형 가장자리)에서 바깥으로 뻗음
type Pop = {
	Gui: BillboardGui,
	Body: Frame,
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
local tokensMine, tokensOthers = POP_BURST_MINE, POP_BURST_OTHERS
local popsSpawned = 0
local popsMine = 0
local popsSkipped = 0
local popsHidden = 0
local popAmount = 0 -- 지금까지 퐁으로 보인 금액 합(스모크 테스트: 상한에 걸려도 번 돈만큼 보이는지)
local fxFolder: Folder
local sight = RaycastParams.new() -- 퐁 자리가 카메라에서 보이는지(가려지면 안 띄움)
sight.FilterType = Enum.RaycastFilterType.Exclude
local lodTimer = 0

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
}
local flights: { Flight } = {}
local flyGui: ScreenGui
local flyTimer = 0
local flightsSpawned = 0
local flightsLanded = 0
local bursts = 0

-- 도우미 ----------------------------------------------------------------------------

local function guiInset(): Vector2
	local ok, inset = pcall(function()
		return (GuiService:GetGuiInset())
	end)
	return if ok and typeof(inset) == "Vector2" then inset else Vector2.zero
end

-- 퐁 금액 짧게: 10 미만은 소수 한 자리("7.5", "3"), 그 위는 정수("144"), 1000 부터 Format.short("1.2K")
function IncomeFx.amountText(amount: number): string
	if amount < 9.95 then
		local text = string.format("%.1f", math.floor(amount * 10 + 0.5) / 10):gsub("%.0$", "")
		return text
	elseif amount < 999.5 then
		return tostring(math.floor(amount + 0.5))
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

-- 이름표 "Head"(이름 딱지·별). 한 번 찾으면 기억(칸 모델이 바뀌면 새 Statue)
local function labelHead(statue: Statue): GuiObject?
	local head = statue.Head
	if head and head.Parent then
		return head
	end
	local pedestal = pedestalOf(statue.Container)
	local body = pedestal and pedestal:FindFirstChild("Body", true)
	local found = body and body:FindFirstChild("Head")
	statue.Head = if found and found:IsA("GuiObject") then found else nil
	statue.Far = nil
	return statue.Head
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
		Since = clock,
		Head = nil,
		Far = nil,
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

-- 이름표 거리 단계: 멀면 Head(이름·별) 끔 = 수입 알약만. 거리는 이름표 아래 끝(모형 꼭대기 — 이름표 MaxDistance 와 같은 기준)까지.
-- 바뀔 때만 씀
local function stepLod(camera: Camera)
	local eye = camera.CFrame.Position
	for container, statue in statues do
		local head = labelHead(statue)
		local pedestal = pedestalOf(container)
		if head and pedestal then
			local top = container:GetAttribute("Top")
			local tagAt = pedestal.Position
				+ Vector3.new(0, PEDESTAL_TOP + (if type(top) == "number" then top else 4), 0)
			local distance = (tagAt - eye).Magnitude
			local far = if statue.Far then distance > LOD_NEAR else distance > LOD_FAR
			if far ~= statue.Far then
				statue.Far = far
				head.Visible = not far
			end
		end
	end
end

-- 동전 퐁 -----------------------------------------------------------------------------

local function newPop(index: number): Pop
	local gui = Ui.new("BillboardGui", {
		Name = "Pop" .. index,
		Size = UDim2.fromOffset(POP_MAX_PX * 6, POP_MAX_PX),
		AlwaysOnTop = true,
		LightInfluence = 0,
		MaxDistance = POP_DISTANCE + 10,
		Enabled = false,
		Active = false,
		Parent = fxFolder,
	})
	-- 몸통: 빌보드의 바깥쪽 절반(띄울 때 왼쪽/오른쪽을 정함). 커졌다 제자리(UIScale)는 몸통 가운데 기준
	local body = Ui.new("Frame", {
		Name = "Body",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.75, 0.5),
		Size = UDim2.fromScale(0.5, 1),
		Parent = gui,
	})
	local scale = Ui.new("UIScale", { Parent = body })
	local coin = Ui.new("ImageLabel", {
		Name = "Coin",
		BackgroundTransparency = 1,
		Image = Ui.imageId("coin") or "",
		ScaleType = Enum.ScaleType.Fit,
		BackgroundColor3 = POP_TEXT,
		AnchorPoint = Vector2.new(0, 0.5),
		Position = UDim2.fromScale(0, 0.5),
		Size = UDim2.fromScale(0.9, 0.9), -- 높이 기준 정사각(RelativeYY: 두 값 모두 몸통 높이 비율)
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
		Position = UDim2.new(0, POP_MAX_PX, 0.5, 0),
		Size = UDim2.new(1, -POP_MAX_PX, 1, 0),
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
		Body = body,
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

-- 토큰: 내 퐁은 내 몫 → 남의 몫, 남의 퐁은 남의 몫만
local function hasToken(mine: boolean): boolean
	return (mine and tokensMine >= 1) or tokensOthers >= 1
end

local function takeToken(mine: boolean)
	if mine and tokensMine >= 1 then
		tokensMine -= 1
	else
		tokensOthers -= 1
	end
end

-- 카메라에서 point 까지 막는 것이 없는지(그 명소 칸 자신·캐릭터·거의 투명한 파트는 안 막음)
local function inSight(eye: Vector3, point: Vector3, container: Instance): boolean
	local character = Players.LocalPlayer and Players.LocalPlayer.Character
	sight.FilterDescendantsInstances = if character then { character } else {}
	local hit = workspace:Raycast(eye, point - eye, sight)
	if not hit then
		return true
	end
	local part = hit.Instance
	return part:IsDescendantOf(container) or (part:IsA("BasePart") and part.Transparency > 0.9)
end

-- 명소 하나에서 퐁. 반환: "shown"(띄움) | "hidden"(가려져서 안 띄움) | "busy"(토큰·빌보드가 없음).
-- (부르는 쪽 scheduleOne 은 멀거나 화면 밖이면 "away" 로 셈)
-- 크기는 이름표처럼 월드 크기(POP_STUDS)로 보이게 이 거리에서 한 번 정함
local function spawnPop(
	statue: Statue,
	pedestal: BasePart,
	camera: Camera,
	distance: number,
	every: number,
	mine: boolean
): string
	local pop = freePop()
	if not pop or not hasToken(mine) then
		return "busy"
	end
	local top = statue.Container:GetAttribute("Top")
	local height = if type(top) == "number" and top > 0 then top else 4
	local perStud = camera.ViewportSize.Y / (2 * math.tan(math.rad(camera.FieldOfView) / 2) * math.max(distance, 1))
	local h = math.clamp(POP_STUDS * perStud, POP_MIN_PX, POP_MAX_PX)
	local hStuds = h / perStud
	-- 화면에서 모형 왼쪽·오른쪽 가장자리(카메라 오른쪽 방향)에서 바깥쪽으로
	local right = camera.CFrame.RightVector
	local flat = Vector3.new(right.X, 0, right.Z)
	flat = if flat.Magnitude > 1e-3 then flat.Unit else Vector3.new(1, 0, 0)
	local side = if random:NextNumber() < 0.5 then -1 else 1
	-- 높이(받침대 윗면 기준): 퐁 위 끝이 모형 꼭대기 - POP_TOP_GAP 을 넘지 않게. 낮은 모형이면 더 아래에서 조금만 솟음
	local highest = height - POP_TOP_GAP - hStuds / 2
	local start = height * random:NextNumber(POP_START[1], POP_START[2])
	start = math.max(0, math.min(start, highest - POP_RISE[1]))
	local rise = math.clamp(math.min(height * 0.45, highest - start), POP_RISE[1], POP_RISE[2])
	local base = flat * (side * POP_EDGE) + Vector3.new(0, PEDESTAL_TOP + start, 0)
	if not inSight(camera.CFrame.Position, pedestal.Position + base, statue.Container) then
		return "hidden"
	end
	takeToken(mine)
	popsSpawned += 1
	if mine then
		popsMine += 1
	end
	local amount = statue.Income * math.min(clock - statue.Since, every * POP_CATCHUP)
	popAmount += amount
	local text = "+" .. IncomeFx.amountText(amount)
	local chars = utf8.len(text) or #text
	local w = math.floor(h * (1.05 + 0.4 * chars) + 0.5) -- 동전(0.9h) + 사이 + 글자
	pop.Base = base
	pop.Rise = rise
	pop.Busy = true
	pop.Start = clock
	pop.Gui.Size = UDim2.fromOffset(2 * w, h)
	pop.Body.Position = UDim2.fromScale(if side > 0 then 0.75 else 0.25, 0.5)
	pop.Text.TextSize = math.floor(h * 0.62 + 0.5)
	pop.Text.Position = UDim2.new(0, math.floor(h * 0.98), 0.5, 0)
	pop.Text.Size = UDim2.new(1, -math.floor(h * 0.98), 1, 0)
	pop.Text.Text = text
	pop.Gui.Adornee = pedestal
	pop.Gui.StudsOffsetWorldSpace = base
	pop.Scale.Scale = 0.6
	setPopFade(pop, 0)
	pop.Gui.Enabled = true
	return "shown"
end

local function stepPops(dt: number)
	tokensMine = math.min(POP_BURST_MINE, tokensMine + POP_RATE_MINE * dt)
	tokensOthers = math.min(POP_BURST_OTHERS, tokensOthers + POP_RATE_OTHERS * dt)
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

-- 때가 된 명소 하나: 가까이·화면 안·안 가려짐이면 퐁(토큰·빌보드가 없으면 조금 뒤에 다시), 아니면 다음 차례로
-- (안 보이는 동안은 Since 를 지금으로 — 퐁 금액은 보이기 시작한 뒤로 번 돈)
local function scheduleOne(container: Instance, statue: Statue, camera: Camera, editing: boolean, mine: boolean)
	local every = POP_EVERY[statue.Rank] * (if mine then 1 else POP_OTHERS_SLOWER)
	local pedestal = pedestalOf(container)
	if editing or statue.Income <= 0 or not pedestal or not container.Parent then
		statue.Next = clock + every
		statue.Since = clock
		return
	end
	local distance = (pedestal.Position - camera.CFrame.Position).Magnitude
	local _, inside = camera:WorldToViewportPoint(pedestal.Position + Vector3.new(0, PEDESTAL_TOP + 2, 0))
	local result = if distance > POP_DISTANCE or not inside
		then "away"
		else spawnPop(statue, pedestal, camera, distance, every, mine)
	if result == "busy" then
		popsSkipped += 1
		statue.Next = clock + POP_RETRY + random:NextNumber(0, POP_RETRY)
		return
	end
	if result == "hidden" then
		popsHidden += 1
	end
	statue.Next = clock + every
	statue.Since = clock
end

-- 때가 된 명소마다. 내 공원 명소 먼저(화면 전체 상한 안에서 내 퐁이 밀리지 않게)
local function schedulePops(camera: Camera, editing: boolean)
	for pass = 1, 2 do
		local wantMine = pass == 1
		for container, statue in statues do
			if clock >= statue.Next and isMine(container) == wantMine then
				scheduleOne(container, statue, camera, editing, wantMine)
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
		ScaleType = Enum.ScaleType.Fit,
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
	}
end

local function setFlightFade(flight: Flight, alpha: number)
	local sprite = flight.Sprite
	if sprite.Image == "" then
		sprite.BackgroundTransparency = alpha
		local stroke = sprite:FindFirstChildOfClass("UIStroke")
		if stroke then
			stroke.Transparency = alpha
		end
	else
		sprite.ImageTransparency = alpha
	end
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

-- 날아가는 동전 크기 배율·투명도(비행 비율 t): 작게 떠서 커졌다가 조금씩 작아지고, 끝 FLY_SINK 뒤로는 0.4 배까지 작아지며
-- 사라짐 = 코인 아이콘 속으로 스며듦(목업도 같은 식)
function IncomeFx.flightLook(t: number): (number, number)
	if t < 0.15 then
		return 0.5 + t / 0.15 * 0.7, 0
	elseif t < FLY_SINK then
		return 1.2 - 0.3 * (t - 0.15) / (FLY_SINK - 0.15), 0
	end
	local k = math.min(1, (t - FLY_SINK) / (1 - FLY_SINK))
	return 0.9 - 0.5 * k, k
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
		flight.Sprite.Position = UDim2.fromOffset(from.X, from.Y)
		flight.Sprite.Size = UDim2.fromOffset(FLY_SIZE * Ui.scale(), FLY_SIZE * Ui.scale())
		flight.Sprite.Visible = false -- 차례가 오면 보임
		flight.Scale.Scale = 1
		setFlightFade(flight, 0)
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
				flightsLanded += 1
				handlers.Bump() -- 닿을 때마다(Hud 가 0.25초에 한 번까지로 묶음)
			else
				local eased = t * t * (3 - 2 * t)
				local at = bezier(flight.From, flight.Via, flight.To, eased)
				local scale, alpha = IncomeFx.flightLook(t)
				flight.Sprite.Position = UDim2.fromOffset(at.X, at.Y)
				flight.Scale.Scale = scale
				setFlightFade(flight, alpha)
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
	lodTimer += dt
	if lodTimer >= LOD_EVERY then
		lodTimer = 0
		stepLod(camera)
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

-- 내 부지(OwnerUserId = 내 UserId 인 부지 모델, 없으면 nil) — 날아가는 동전의 출발점, 퐁 몫
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
	local tracked, far = 0, 0
	for _, statue in statues do
		tracked += 1
		if statue.Far then
			far += 1
		end
	end
	return {
		Pops = activePops,
		PopsSpawned = popsSpawned,
		PopsMine = popsMine,
		PopsSkipped = popsSkipped,
		PopsHidden = popsHidden,
		PopAmount = popAmount,
		Flights = activeFlights,
		FlightsSpawned = flightsSpawned,
		FlightsLanded = flightsLanded,
		Bursts = bursts,
		Statues = tracked,
		Far = far,
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
	-- 날아가는 동전: HUD(DisplayOrder 0) 바로 위 층(번쩍임 5 아래) — 코인 알약 위로 날아와 아이콘 속으로 스며듦.
	-- Active 없는 그림이라 입력을 막지 않고, 창·굴림 연출·배치 모드 동안은 날리지 않음(Covered · Editing)
	flyGui = Ui.new("ScreenGui", {
		Name = "IncomeFx",
		ResetOnSpawn = false,
		DisplayOrder = 1,
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
