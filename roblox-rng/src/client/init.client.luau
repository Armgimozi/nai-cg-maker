-- 클라이언트 진입점: 상태 동기화, 굴리기/자동 굴리기, 메뉴 연결, 뉴스 속보, 회전 모형,
-- 환생 · Robux 상품 구매 요청 · 서버 행운 알림 (DESIGN.md v3)
-- (화면 글자에는 이모지를 쓰지 않음 — DESIGN.md UI 스타일 가이드 v2)
-- 알림은 [아이콘] + 8글자 안팎 ("구매 완료", "코인 부족", "대표 지정"), 문장은 쓰지 않음

local CollectionService = game:GetService("CollectionService")
local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TextChatService = game:GetService("TextChatService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Format = require(Shared.Format)
local Landmarks = require(Shared.Landmarks)
local Net = require(Shared.Net)
local PlayerState = require(Shared.PlayerState)

local Hud = require(script.Hud)
local Icons = require(script.Icons)
local Panels = require(script.Panels)
local Perks = require(script.Perks)
local Ui = require(script.Ui)

local SPIN_TAG = "LandmarkSpin"
local SPIN_SPEED = math.rad(20) -- 태그 붙은 모형(광장 지구본, 홀로그램)의 초당 회전 각도

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local state: PlayerState.Snapshot? = nil -- 서버에서 받은 최신 Snapshot
local stateReceivedAt = 0
local deferredState: { Snapshot: any, ReceivedAt: number }? = nil -- 연출 중에 도착한 재동기화 상태
local rolling = false
local revealing = false
local autoRoll = false
local lastRollSentAt = -math.huge
local heldAnnouncements = {} -- 내 굴림 연출 중에 도착한 "내" 속보 (연출이 끝나면 표시)
local location = "Plaza" -- 지금 있는 곳: "Plaza" | "Park"
local teleporting = false
local rebirthing = false

local function currentCoins(): number
	if not state then
		return 0
	end
	return state.Coins + state.Income * math.max(0, time() - stateReceivedAt)
end

-- 서버 상태 반영. Revision 이 더 큰 것만 받아서 늦게 도착한 옛 상태가 덮어쓰지 않게 함.
-- receivedAt: 스냅샷을 실제로 받은 시각(코인 표시 기준). 늦게 반영할 때 넘겨줌.
local function applyState(snapshot: any, receivedAt: number?)
	if type(snapshot) ~= "table" or type(snapshot.Revision) ~= "number" then
		return
	end
	if state and snapshot.Revision <= state.Revision then
		return
	end
	state = snapshot
	stateReceivedAt = receivedAt or time()
	Hud.render(snapshot, stateReceivedAt)
	Hud.setCoins(currentCoins())
	Panels.render(snapshot)
end

-- 서버가 보내는 재동기화. 내 굴림 연출 중이면 결과가 미리 보이지 않게 연출이 끝난 뒤 반영
local function onStateEvent(snapshot: any)
	if type(snapshot) ~= "table" or type(snapshot.Revision) ~= "number" then
		return
	end
	if revealing then
		if not deferredState or snapshot.Revision > deferredState.Snapshot.Revision then
			deferredState = { Snapshot = snapshot, ReceivedAt = time() }
		end
		return
	end
	applyState(snapshot)
end

-- 원격 찾기. 서버가 아직 모르는 원격(예: 옛 서버에 Rebirth 가 없음)이면 영원히 기다리지 않고 nil
local remoteFolder: Instance? = nil
local function findRemote(name: string, seconds: number): Instance?
	if not remoteFolder then
		remoteFolder = Net.fn("GetState").Parent
	end
	local folder = remoteFolder
	if not folder then
		return nil
	end
	return folder:FindFirstChild(name) or folder:WaitForChild(name, seconds)
end

local function invoke(name: string, ...: any): any
	local remote = findRemote(name, 5)
	if not remote or not remote:IsA("RemoteFunction") then
		warn("[LandmarkRNG] 원격 없음: " .. name)
		Hud.toast("연결 오류", Ui.Theme.Bad, nil, "close")
		return nil
	end
	local ok, result = pcall(remote.InvokeServer, remote, ...)
	if not ok then
		warn("[LandmarkRNG] " .. name .. " 실패: " .. tostring(result))
		Hud.toast("연결 오류", Ui.Theme.Bad, nil, "close")
		return nil
	end
	return result
end

local function feature(landmarkId: string?)
	local response = invoke("Feature", landmarkId)
	if type(response) ~= "table" then
		return
	end
	applyState(response.State)
	if not response.Ok then
		Hud.toast("지정 실패", Ui.Theme.Bad, 2, "close")
	elseif landmarkId then
		local landmark = Landmarks.ById[landmarkId]
		if landmark then
			Hud.toast("대표 지정", landmark.Tier.Color, 2, "star")
		end
	else
		Hud.toast("대표 해제", Ui.Theme.Ink, 2, "star_empty")
	end
end

local function showAnnouncement(info: any, landmark: Landmarks.Landmark)
	local name = tostring(info.Name)
	Hud.news(name, landmark, tonumber(info.Rolls) or 0)

	-- 채팅창에도 시스템 메시지 (새 TextChatService 를 쓰는 경우)
	pcall(function()
		local channels = TextChatService:FindFirstChild("TextChannels")
		local general = channels and channels:FindFirstChild("RBXGeneral")
		if general then
			general:DisplaySystemMessage(
				string.format(
					'[속보] %s · <font color="%s"><b>%s</b></font> · %s · #%s',
					Format.escape(name),
					Format.hex(landmark.Tier.Color),
					Format.escape(landmark.Name),
					Format.oneIn(landmark.OneIn),
					Format.commas(tonumber(info.Rolls) or 0)
				)
			)
		end
	end)
end

-- 더 희귀한 명소를 발견했으면 자동으로 대표 지정 (설정이 켜져 있을 때)
local function autoFeature(landmark: Landmarks.Landmark)
	local current = state
	if not current or not current.Settings.AutoFeature then
		return
	end
	local featured = if current.Featured then Landmarks.ById[current.Featured] else nil
	if not featured or landmark.OneIn > featured.OneIn then
		feature(landmark.Id)
	end
end

local function roll()
	if rolling or not state then
		return
	end
	rolling = true
	Hud.setRolling(true)

	-- 쿨타임이 남았으면 기다렸다가 요청
	local waitFor = lastRollSentAt + (state :: PlayerState.Snapshot).Cooldown - time()
	if waitFor > 0 then
		task.wait(waitFor)
	end
	lastRollSentAt = time()
	local response = invoke("Roll")
	local receivedAt = time()

	local landmark = if type(response) == "table" and response.Ok then Landmarks.ById[response.LandmarkId] else nil
	if landmark then
		if type(response.State) == "table" then
			Hud.startCooldown(response.State.Cooldown)
		end
		revealing = true
		local ok, err = pcall(Hud.reveal, landmark, {
			Fast = autoRoll,
			IsNew = response.IsNew == true,
			StarUp = response.StarUp == true,
			Stars = tonumber(response.Stars) or 0,
			Bonus = tonumber(response.Bonus) or 0,
			Luck = tonumber(response.Luck) or 1,
		})
		if not ok then
			warn("[LandmarkRNG] 굴림 연출 오류: " .. tostring(err))
		end
		revealing = false

		-- 연출이 끝난 뒤에 숫자 갱신(스포일러 방지)
		applyState(response.State, receivedAt)
		local deferred = deferredState
		deferredState = nil
		if deferred then
			applyState(deferred.Snapshot, deferred.ReceivedAt)
		end
		for _, held in heldAnnouncements do
			showAnnouncement(held.Info, held.Landmark)
		end
		table.clear(heldAnnouncements)

		autoFeature(landmark)
	elseif type(response) == "table" and response.Ok then
		applyState(response.State, receivedAt) -- 모르는 명소 Id (클라가 옛 버전일 때)
	elseif type(response) == "table" and response.Reason == "cooldown" then
		task.wait(tonumber(response.RetryIn) or 0.2)
		lastRollSentAt = -math.huge -- 이미 RetryIn 만큼 기다렸으니 다음 요청에서 또 기다리지 않음
	else
		task.wait(1) -- 데이터 불러오는 중이거나 통신 실패: 자동 굴리기가 요청을 퍼붓지 않게
	end

	rolling = false
	Hud.setRolling(false)
end

local function toggleAuto()
	autoRoll = not autoRoll
	Hud.setAuto(autoRoll)
	if autoRoll and not rolling then
		task.spawn(roll)
	end
end

-- 서버가 준 실패 이유(문장 또는 코드) -> 짧은 알림 글자 + 아이콘
local function buyFailure(reason: any): (string, string)
	local text = string.lower(tostring(reason or ""))
	if text:find("코인") or text:find("coin") then
		return "코인 부족", "coin"
	elseif text:find("최대") or text:find("max") then
		return "MAX", "check"
	elseif text:find("불러") or text:find("load") then
		return "로딩 중", "globe"
	end
	return "구매 실패", "close"
end

local function buy(upgradeId: string)
	local response = invoke("BuyUpgrade", upgradeId)
	if type(response) ~= "table" then
		return
	end
	applyState(response.State)
	if response.Ok then
		-- 성공: 업그레이드 아이콘 + "Lv 3"
		local level = if state then PlayerState.upgradeLevel(state, upgradeId) else nil
		local icon = Icons.UPGRADE[upgradeId] or "check"
		Hud.toast(if level then "Lv " .. level else "구매 완료", Ui.Theme.Good, 2, icon)
	else
		local text, icon = buyFailure(response.Reason)
		Hud.toast(text, Ui.Theme.Bad, 2, icon)
	end
end

local function toggleAutoFeature()
	if not state then
		return
	end
	local response = invoke("SetSetting", "AutoFeature", not (state :: PlayerState.Snapshot).Settings.AutoFeature)
	if type(response) == "table" then
		applyState(response.State)
	end
end

-- 환생 -------------------------------------------------------------------------

-- 서버가 준 실패 이유 -> 짧은 알림. 이유가 애매하면 지금 상태로 판단
local function rebirthFailure(reason: any): (string, string)
	local text = string.lower(tostring(reason or ""))
	if text:find("코인") or text:find("coin") then
		return "코인 부족", "coin"
	elseif text:find("명소") or text:find("landmark") or text:find("missing") then
		return "명소 부족", "lock"
	elseif text:find("불러") or text:find("load") then
		return "로딩 중", "globe"
	end
	if state then
		local _, missing, short = Perks.rebirthCheck(state, currentCoins())
		if #missing > 0 then
			return "명소 부족", "lock"
		elseif short > 0 then
			return "코인 부족", "coin"
		end
	end
	return "환생 실패", "close"
end

local function rebirth()
	if rebirthing then
		return
	end
	rebirthing = true
	local response = invoke("Rebirth")
	rebirthing = false
	if type(response) ~= "table" then
		return
	end
	applyState(response.State)
	if response.Ok then
		Hud.flash(Ui.colorPair("Coral").Face, 0.55)
		Hud.toast("환생!", Ui.colorPair("Coral").Face, 3, "rebirth")
	else
		local text, icon = rebirthFailure(response.Reason)
		Hud.toast(text, Ui.Theme.Bad, 2, icon)
	end
end

-- Robux 상품 --------------------------------------------------------------------
-- 서버가 구매 창을 띄움. 지급 결과는 State(부스트·패스·코인) / ServerLuck 이벤트로 들어옴

local function buyRobux(remoteName: string, key: string)
	local response = invoke(remoteName, key)
	if type(response) ~= "table" then
		return
	end
	if type(response.State) == "table" then
		applyState(response.State)
	end
	if response.Ok == false then
		-- 시간 부스트는 최대 시간(3시간)이 차 있으면 서버가 구매 창을 안 띄움
		local item = Perks.item(key)
		if item and item.Seconds then
			Hud.toast("MAX", Ui.Theme.Bad, 2, item.Icon)
		else
			Hud.toast("구매 실패", Ui.Theme.Bad, 2, "close")
		end
	end
end

-- 구매 창에서 실제로 샀을 때: [상품 아이콘] "구매 완료"
local function purchased(kind: string, id: any)
	local item = Perks.itemById(kind, tonumber(id) or 0)
	Hud.toast("구매 완료", Ui.Theme.Good, 3, if item then item.Icon else "check")
end

-- 광장 <-> 내 공원 이동
local function teleport()
	if teleporting then
		return
	end
	teleporting = true
	local target = if location == "Plaza" then "Park" else "Plaza"
	local response = invoke("Teleport", target)
	if type(response) == "table" and response.Ok then
		location = target
		Hud.setLocation(location)
	elseif response ~= nil then
		Hud.toast("이동 실패", Ui.Theme.Bad, 2, "close")
	end
	teleporting = false
end

-- 화면 만들기 ---------------------------------------------------------------

local gui = Hud.init(playerGui, {
	Roll = function()
		task.spawn(roll)
	end,
	ToggleAuto = toggleAuto,
	Menu = Panels.toggle,
	Teleport = function()
		task.spawn(teleport)
	end,
})
Panels.init(gui, {
	Feature = function(landmarkId: string?)
		task.spawn(feature, landmarkId)
	end,
	Buy = function(upgradeId: string)
		task.spawn(buy, upgradeId)
	end,
	ToggleAutoFeature = function()
		task.spawn(toggleAutoFeature)
	end,
	Rebirth = function()
		task.spawn(rebirth)
	end,
	BuyPass = function(key: string)
		task.spawn(buyRobux, "BuyPass", key)
	end,
	BuyProduct = function(key: string)
		task.spawn(buyRobux, "BuyProduct", key)
	end,
	Toast = function(text: string, icon: string?)
		Hud.toast(text, Ui.Theme.Bad, 2, icon)
	end,
})

-- 다시 태어나면 광장(스폰 지점)에서 시작
player.CharacterAdded:Connect(function()
	location = "Plaza"
	Hud.setLocation(location)
end)

-- 키보드: R = 굴리기, T = 자동 굴리기
UserInputService.InputBegan:Connect(function(input, processed)
	if processed then
		return
	end
	if input.KeyCode == Enum.KeyCode.R then
		task.spawn(roll)
	elseif input.KeyCode == Enum.KeyCode.T then
		toggleAuto()
	end
end)

-- 서버 이벤트 ---------------------------------------------------------------

Net.event("State").OnClientEvent:Connect(onStateEvent)

Net.event("Announce").OnClientEvent:Connect(function(info)
	local landmark = if type(info) == "table" then Landmarks.ById[info.LandmarkId] else nil
	if not landmark then
		return
	end
	-- 내가 발견한 속보가 내 연출보다 먼저 오면 결과가 미리 보이므로 연출이 끝날 때까지 보류
	if info.UserId == player.UserId and revealing then
		table.insert(heldAnnouncements, { Info = info, Landmark = landmark })
		return
	end
	showAnnouncement(info, landmark)
end)

-- 서버 행운 { Name, Until, Left }: 위쪽 띠 + "<이름> 서버 행운!"
-- (남은 초 Left 를 먼저 씀: 시계 동기화 오차가 없음. 옛 서버에 이벤트가 없어도 멈추지 않게 따로 기다림)
task.spawn(function()
	local remote = findRemote("ServerLuck", 30)
	if not remote or not remote:IsA("RemoteEvent") then
		return
	end
	remote.OnClientEvent:Connect(function(info)
		if type(info) ~= "table" then
			return
		end
		local left = tonumber(info.Left)
		local untilTime = if left and left > 0 then left else tonumber(info.Until)
		if untilTime then
			Hud.serverLuck(tostring(info.Name or ""), untilTime)
		end
	end)
end)

-- 구매 창이 닫힐 때 알림만 (지급은 서버의 ProcessReceipt). 연결에 실패해도 아래 루프는 돌아야 하므로 pcall
pcall(function()
	MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(who, passId, wasPurchased)
		if who == player and wasPurchased then
			purchased("Pass", passId)
		end
	end)
	MarketplaceService.PromptProductPurchaseFinished:Connect(function(userId, productId, isPurchased)
		if userId == player.UserId and isPurchased then
			purchased("Product", productId)
		end
	end)
end)

-- 루프 ---------------------------------------------------------------------

-- "LandmarkSpin" 태그 모형 목록 (태그가 붙고 떨어질 때만 갱신 → 매 프레임 목록을 새로 만들지 않음)
local spinModels: { [Instance]: boolean } = {}
for _, instance in CollectionService:GetTagged(SPIN_TAG) do
	spinModels[instance] = true
end
CollectionService:GetInstanceAddedSignal(SPIN_TAG):Connect(function(instance)
	spinModels[instance] = true
end)
CollectionService:GetInstanceRemovedSignal(SPIN_TAG):Connect(function(instance)
	spinModels[instance] = nil
end)

RunService.RenderStepped:Connect(function(dt)
	-- 태그 모형을 제자리에서 수직축으로 회전 (이 화면에서만 보이는 효과)
	local turn = CFrame.Angles(0, SPIN_SPEED * dt, 0)
	for model in spinModels do
		if model:IsA("Model") and model:IsDescendantOf(workspace) then
			local pivot = model:GetPivot()
			model:PivotTo(CFrame.new(pivot.Position) * turn * (pivot - pivot.Position))
		end
	end

	-- 코인: 받은 값 + 초당 수입 × 지난 시간 (부드럽게 올라감)
	if state then
		Hud.setCoins(currentCoins())
	end
end)

-- 업그레이드 버튼 "살 수 있음" 색, 환생 조건, 부스트·서버 행운 타이머 (가벼운 갱신)
task.spawn(function()
	while true do
		if state then
			local coins = currentCoins()
			Panels.refreshCoins(coins)
			Hud.tick(coins)
		else
			Hud.tick(nil)
		end
		task.wait(0.25)
	end
end)

-- 자동 굴리기
task.spawn(function()
	while true do
		if autoRoll and not rolling then
			roll()
		end
		task.wait(0.05)
	end
end)

-- 처음 상태 받아오기 (서버 데이터 로드가 끝날 때까지 서버 쪽에서 기다려 줌)
applyState(invoke("GetState"))
