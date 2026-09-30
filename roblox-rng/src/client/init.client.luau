-- 클라이언트 진입점: 상태 동기화, 굴리기/자동 굴리기, 메뉴 연결, 뉴스 속보, 회전 모형,
-- 환생 · Robux 상품 구매 요청 · 서버 행운 알림 (DESIGN.md v3), 3D 공원 배치 모드(ParkEdit: 내 공원에서 명소를
-- 직접 집어 옮김 — 여기서는 서버 요청·알림·HUD 연결만), 수입 보이기(IncomeFx: 동전 퐁 · 내 공원 → 코인 알약 동전, 서버 속성만 읽음)
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
local IncomeFx = require(script.IncomeFx)
local Panels = require(script.Panels)
local ParkEdit = require(script.ParkEdit)
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
local autoRoll = false -- AUTO 켬(플레이어가 고른 것 — 굴리기 줄 [AUTO] · T 키)
-- 3D 배치 모드 동안 자동 굴리기는 쉼(나가면 AUTO 가 켜져 있으면 다시 돎): 배치 띠에는 이미 [자동](자동 배치)이 있어서
-- 자동 굴리기 스위치를 하나 더 두면 아이들이 헷갈리고, 쉬는 동안은 새 명소가 빈 칸에 들어와 들고 있는 칸이 바뀌지도 않음
local autoPaused = false
-- 마지막 굴림을 보낸 시각(다음 굴림은 이 시각 + 굴림 간격부터). 굴림 간격을 기다렸다 보냈으면 "원래 보낼 수 있던 시각"
-- (task.wait 는 다음 프레임에 깨서 조금 늦음 — 그 늦음이 굴림마다 쌓여 AUTO 가 굴림 간격보다 느려지지 않게)
local lastRollSentAt = -math.huge
local SEND_SLACK = 0.05 -- 기다림이 이만큼(프레임 몇 개) 늦게 끝난 것까지는 원래 시각으로 침
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

-- 자동 발견으로 도감에 새로 들어온 명소 수: 서버는 확률(1/N)이 영구 행운 이하인 명소를 발견으로 침(PlayerState.autoDiscover —
-- 환생·지구본·도장으로 행운이 오르면 그보다 흔한 명소는 굴림에서 다시 안 나옴). 클라이언트는 직접 계산하지 않고 서버가 보낸
-- Discovered 를 그대로 씀(도감·도장 숫자가 서버와 같음). 굴려서 얻은 명소(보유)는 연출이 이미 보여 줬으니 뺌
local function autoDiscovered(before: PlayerState.Snapshot, after: PlayerState.Snapshot): number
	local count = 0
	for _, landmark in Landmarks.List do
		local id = landmark.Id
		if
			PlayerState.isDiscovered(after, id)
			and not PlayerState.isDiscovered(before, id)
			and (after.Inventory[id] or 0) <= 0
		then
			count += 1
		end
	end
	return count
end

-- 새로 받은 대륙 도장(Landmarks.Regions 순서). 도장 규칙은 PlayerState.completedRegions 그대로(서버 Discovered 기준)
local function newStamps(before: PlayerState.Snapshot, after: PlayerState.Snapshot): { Landmarks.Region }
	local had = {}
	for _, id in PlayerState.completedRegions(before) do
		had[id] = true
	end
	local added = {}
	for _, id in PlayerState.completedRegions(after) do
		local region = Landmarks.RegionById[id]
		if region and not had[id] then
			table.insert(added, region)
		end
	end
	return added
end

-- 도감을 그 대륙 탭으로 열기(도장 알림을 눌렀을 때). 배치 모드면 먼저 나감(다른 창을 열 때와 같게)
local function openStampRegion(regionId: string)
	ParkEdit.exit()
	Panels.open("Collection", regionId)
	Hud.clearStampToasts()
	trackOpened()
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
	local previous = state
	state = snapshot
	stateReceivedAt = receivedAt or time()
	Hud.render(snapshot, stateReceivedAt)
	Hud.setCoins(currentCoins())
	Panels.render(snapshot)
	ParkEdit.render(snapshot)
	-- 자동 발견: [도감] "도감 +12" (환생 직후처럼 행운이 크게 오를 때 도감 숫자가 왜 늘었는지)
	local added = if previous then autoDiscovered(previous, snapshot) else 0
	if added > 0 then
		Hud.toast("도감 +" .. added, Ui.colorPair("Sky").Face, 3, "album")
	end
	-- 대륙 도장을 새로 받음(굴림 연출이 끝난 뒤 · 자동 발견): 행운 소리 +
	--   도감이 열려 있으면 알림 없이 그 대륙 탭 체크가 톡(Panels.stampEarned — 알림이 탭 줄·제목 리본을 가리지 않게)
	--   아니면 [도장 그림] "도장 +25%" 알림(누르면 도감의 그 대륙 탭) + 다음에 도감을 열면 그 탭으로 한 번(도장 쾅)
	if previous then
		for _, region in newStamps(previous, snapshot) do
			if Panels.stampEarned(region.Id) then
				Hud.stampEarned(region, nil)
			else
				Hud.stampEarned(region, function()
					openStampRegion(region.Id)
				end)
			end
		end
	end
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

-- 분석: 화면에서만 알 수 있는 일을 서버에 알림(kind: "ShopOpened" | "CollectionOpened" | "AutoOn" | "TapEdit" — 서버 Analytics 가
-- 이름·간격을 거르고 AnalyticsService 로 보냄, 이벤트는 서버에서만 보낼 수 있음). 기다리지 않고, 실패해도 게임은 그대로
local function track(kind: string)
	task.spawn(function()
		local remote = findRemote("Track", 5)
		if remote and remote:IsA("RemoteEvent") then
			pcall(function()
				(remote :: RemoteEvent):FireServer(kind)
			end)
		end
	end)
end
-- 창을 열었을 때 알릴 것(메뉴 · 도장 알림)
local OPEN_EVENTS = { Shop = "ShopOpened", Collection = "CollectionOpened" }
local function trackOpened()
	local kind = OPEN_EVENTS[Panels.current() or ""]
	if kind then
		track(kind)
	end
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

-- 직접 배치 중 이번 판에 처음 얻은 명소가 공원이 꽉 차서 전시되지 못했으면 연출이 끝난 뒤 "공원 꽉 참" 알림
-- (더 좋은 명소면 [공원] 버튼 숫자 배지도 늘어 있음)
local function parkFullNotice(landmark: Landmarks.Landmark)
	local current = state
	if current and PlayerState.missedByFullPark(current, landmark.Id) then
		Hud.toast("공원 꽉 참", Ui.Theme.Gold, 3, "park")
	end
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

-- fromAuto: 자동 굴리기가 부른 굴림(자동 루프 · AUTO 켜기). 굴림 간격을 기다리는 동안 AUTO 를 끄거나 배치 모드에
-- 들어가면 요청을 보내지 않고 그만둠(끈 뒤에 굴림이 하나 더 나가 원래 길이 연출이 뜨지 않게). 그 사이 [굴리기]·R 을
-- 눌렀으면(manualAsked) 그만두지 않고 그 굴림으로 보냄
local manualAsked = false
local function roll(fromAuto: boolean?)
	if rolling or not state then
		if rolling and not fromAuto then
			manualAsked = true
		end
		return
	end
	rolling = true
	manualAsked = false
	Hud.setRolling(true)

	-- 쿨타임이 남았으면 기다렸다가 요청. 자동 굴림은 연출이 끝나면 바로 여기로 돌아와 남은 굴림 간격(Cooldown)만 기다림
	-- (서버가 거절하면 RetryIn). 이미 발견한 명소는 AUTO 에서 결과 카드만 퐁 하고 기다리지 않으므로(Hud.reveal 빠른 결과 —
	-- Config.AUTO_QUICK_REVEAL) AUTO 속도 = 서버 굴림 간격(여행사·빠른 굴림). 기다렸으면 기준은 원래 보낼 수 있던 시각이라
	-- 평균 간격이 굴림 간격 그대로(프레임 늦음이 쌓이지 않음). 서버는 허용 오차 안에서 받음(RollLogic.cooldownGate)
	local readyAt = lastRollSentAt + (state :: PlayerState.Snapshot).Cooldown
	local waitFor = readyAt - time()
	if waitFor > 0 then
		task.wait(waitFor)
	end
	if fromAuto and not manualAsked and (not autoRoll or autoPaused) then
		rolling = false
		Hud.setRolling(false)
		return
	end
	local now = time()
	lastRollSentAt = if waitFor > 0 then math.max(readyAt, now - SEND_SLACK) else now
	-- 빠른 결과(AUTO)인지는 보낼 때 정함: 응답을 기다리는 사이 AUTO 를 꺼도 이 결과는 AUTO 결과(이미 발견 = 카드만 퐁)
	local fast = autoRoll and not autoPaused
	local response = invoke("Roll")
	local receivedAt = time()

	local landmark = if type(response) == "table" and response.Ok then Landmarks.ById[response.LandmarkId] else nil
	if landmark then
		if type(response.State) == "table" then
			Hud.startCooldown(response.State.Cooldown)
		end
		revealing = true
		local ok, err = pcall(Hud.reveal, landmark, {
			Fast = fast,
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

		parkFullNotice(landmark)
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
	-- AUTO 가 계속 굴리면 굴리기 버튼의 지구본은 계속 돎(굴림마다 멈췄다 0° 로 돌아가는 떨림 없이). 끄면 toggleAuto 가 멈춤
	if not (autoRoll and not autoPaused) then
		Hud.setRolling(false)
	end
end

local function toggleAuto()
	autoRoll = not autoRoll
	Hud.setAuto(autoRoll)
	if autoRoll then
		track("AutoOn")
	end
	if not autoRoll then
		Hud.setRolling(rolling)
	end
	if autoPaused then
		-- 배치 모드(T 키): 굴리기 줄이 숨어 있으니 알림으로. 나가면 적용
		Hud.toast(if autoRoll then "AUTO ON" else "AUTO OFF", Ui.Theme.Ink, 2, "auto")
		return
	end
	if autoRoll and not rolling then
		task.spawn(roll, true)
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

-- 공원 배치 ----------------------------------------------------------------------
-- 3D 배치 모드(ParkEdit)가 누르는 즉시 미리 보여 주고, 여기서 서버에 요청(기다림)한 뒤 응답 상태를 반영하고 결과를 돌려줌

-- 서버가 준 실패 이유 -> 짧은 알림 ("stale" 은 따로: 중립 알림 "공원 바뀜" + 새 상태로 다시 그림)
local function parkFailure(reason: any): (string, string)
	local text = string.lower(tostring(reason or ""))
	if text:find("잠긴") then
		return "잠긴 칸", "lock"
	elseif text:find("busy") then
		return "잠시 후", "auto"
	elseif text:find("불러") or text:find("load") then
		return "로딩 중", "globe"
	end
	return "배치 실패", "close"
end

-- expected: 화면에서 그 칸에 보이던 명소 Id(빈 칸 ""), expectedFrom: 옮기는 명소가 있던 칸(0 = 보관함).
-- 그사이 서버에서 그 칸이 바뀌었으면(예: 자동 굴림이 빈 칸에 새 명소를 놓음) 서버가 Reason "stale" + 새 상태로 거절
-- -> 배치 모드가 미리 보기를 버리고 새 상태로 다시 그림. 반환: 받아들였는지, stale 인지
local function setDisplay(
	slot: number,
	landmarkId: string?,
	expected: string,
	expectedFrom: number?
): (boolean, boolean)
	local response = invoke("SetDisplay", slot, landmarkId, expected, expectedFrom)
	local stale = false
	if type(response) == "table" then
		stale = response.Reason == "stale"
		if stale then
			-- 굴림 연출 중이면(자동 굴림이 방금 놓은 명소가 이유) 새 상태는 연출이 끝난 뒤 반영 — 결과가 미리 보이지 않게
			onStateEvent(response.State)
			Hud.toast("공원 바뀜", Ui.Theme.Ink, 2, "park")
		else
			applyState(response.State)
		end
		if not stale and not response.Ok then
			local text, icon = parkFailure(response.Reason)
			Hud.toast(text, Ui.Theme.Bad, 2, icon)
		end
	end
	return type(response) == "table" and response.Ok == true, stale
end

local function setAutoPark(on: boolean): boolean
	local response = invoke("SetSetting", "AutoPark", on)
	if type(response) ~= "table" then
		return false
	end
	applyState(response.State)
	if not response.Ok then
		Hud.toast("잠시 후", Ui.Theme.Bad, 2, "auto")
	end
	return response.Ok == true
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
		-- 서버가 구매 창을 안 띄운 이유: "max" 시간 부스트가 최대(3시간)까지 참, "owned" 이미 가진 게임패스
		-- (서버가 방금 확인해서 상태도 보냄), "loading" 데이터를 불러오는 중, 그 밖 = 실패
		local item = Perks.item(key)
		local icon = if item then item.Icon else "close"
		if response.Reason == "max" then
			Hud.toast("MAX", Ui.Theme.Bad, 2, icon)
		elseif response.Reason == "owned" then
			Hud.toast("보유", Ui.Theme.Good, 2, icon)
		elseif response.Reason == "loading" then
			Hud.toast("불러오는 중", Ui.Theme.Bad, 2, "auto")
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

-- 광장 / 내 공원으로 이동(기다림). 성공하면 true
local function travel(target: string): boolean
	if teleporting then
		return false
	end
	teleporting = true
	local response = invoke("Teleport", target)
	local ok = type(response) == "table" and response.Ok == true
	if ok then
		location = target
		Hud.setLocation(location)
	elseif response ~= nil then
		Hud.toast("이동 실패", Ui.Theme.Bad, 2, "close")
	end
	teleporting = false
	return ok
end

-- 광장 <-> 내 공원 이동 버튼
local function teleport()
	if location == "Park" then
		ParkEdit.exit() -- 공원을 떠나면 배치 모드도 끝(부지 밖 감지보다 먼저)
	end
	travel(if location == "Plaza" then "Park" else "Plaza")
end

-- 화면 만들기 ---------------------------------------------------------------

local gui = Hud.init(playerGui, {
	Roll = function()
		task.spawn(roll)
	end,
	ToggleAuto = toggleAuto,
	Menu = function(name: string)
		ParkEdit.exit() -- 다른 창을 열면 배치 모드 끝
		Panels.toggle(name)
		if Panels.current() == "Collection" then
			Hud.clearStampToasts() -- 도감을 열었으면 도장 알림은 할 일을 다 함(탭 줄을 가리지 않게)
		end
		if Panels.current() == name then
			trackOpened() -- 닫을 때는 안 알림
		end
	end,
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
	Toast = function(text: string, icon: string?, color: Color3?)
		Hud.toast(text, color or Ui.Theme.Bad, 2, icon)
	end,
})
ParkEdit.init(gui, {
	SetDisplay = setDisplay,
	SetAutoPark = setAutoPark,
	GoToPark = function(): boolean
		return travel("Park")
	end,
	Toast = function(text: string, icon: string?, color: Color3?)
		Hud.toast(text, color or Ui.Theme.Bad, 2, icon)
	end,
	Changed = function(editing: boolean)
		if editing then
			Panels.close()
		end
		Hud.setEditing(editing)
		autoPaused = editing
		if editing then
			track("TapEdit") -- 배치 버튼이 없어서 들어오는 길은 내 공원을 톡 누르는 것뿐
		end
		if editing then
			Hud.setRolling(rolling) -- AUTO 가 쉬는 동안 지구본 아이콘도 멈춤(굴리던 것이 끝나면 roll 이 멈춤)
		end
		if editing and autoRoll then
			Hud.toast("AUTO 쉬는 중", Ui.Theme.Ink, 2, "auto") -- 나가면 다시 돎
		end
	end,
	-- 창(도감 등)이 열려 있거나 굴림 연출 중이면 뒤 공원을 눌러도 배치 모드로 안 들어감(창 바탕·결과 카드는 입력을 막지
	-- 않음). 연출이 끝나고 카드만 남아 있을 때(AUTO 중엔 거의 늘)는 카드가 덮은 곳만 안 받음(at = 뷰포트 px)
	CanTap = function(at: Vector2?): boolean
		if Panels.current() ~= nil or revealing then
			return false
		end
		return at == nil or not Hud.revealCovers(at)
	end,
})
-- 수입 보이기: 전시 명소 동전 퐁 + 내 공원에서 코인 알약으로 날아가는 동전. 배치 모드면 모두 쉬고, 창이 열렸거나
-- 굴림 연출 중이면 날아가는 동전만 쉼(창·연출을 가리지 않게)
IncomeFx.init(playerGui, {
	CoinTarget = Hud.coinTarget,
	Bump = Hud.bumpCoins,
	Editing = ParkEdit.isEditing,
	Covered = function(): boolean
		return Panels.current() ~= nil or revealing
	end,
})

-- 다시 태어나면 광장(스폰 지점)에서 시작
player.CharacterAdded:Connect(function()
	location = "Plaza"
	Hud.setLocation(location)
end)

-- 키보드: R = 굴리기, T = 자동 굴리기(배치 모드 동안은 켜고 끄기만 — 나가면 적용)
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

-- 내 공원 ---------------------------------------------------------------------
-- 서버(ParkService)가 부지 모델에 OwnerUserId(주인)·Origin(부지 CFrame), 칸 모델에 Slot·Look 속성을 붙여 둠.
-- 내 부지를 찾으면 ParkEdit 에 넘기고 HUD [공원] 버튼 배지를 켤 수 있게 함. 배치 버튼은 없음: 내 공원에서 내 명소·빈 받침대를
-- 톡 누르면(끌기 = 화면 돌리기는 아님) 서버를 거치지 않고 바로 배치 모드 + 그 명소를 집음 / 그 빈 칸을 채울 준비(ParkEdit).
-- 남의 공원은 눌러도 아무 일 없음. 창이 열려 있으면 누르기를 받지 않음(CanTap — 창 바탕은 입력을 막지 않음)
local myPlot: Instance? = nil

local function setMyPlot(plot: Instance?)
	if plot == myPlot then
		return
	end
	myPlot = plot
	Hud.setPlotOwned(plot ~= nil)
	ParkEdit.setPlot(plot)
	IncomeFx.setPlot(plot)
end

task.spawn(function()
	local parks = workspace:WaitForChild("Parks", 60)
	if not parks then
		return
	end
	local function check()
		local found: Instance? = nil
		for _, plot in parks:GetChildren() do
			if plot:GetAttribute("OwnerUserId") == player.UserId then
				found = plot
				break
			end
		end
		setMyPlot(found)
	end
	local function watchPlot(plot: Instance)
		plot:GetAttributeChangedSignal("OwnerUserId"):Connect(check)
	end
	for _, plot in parks:GetChildren() do
		watchPlot(plot)
	end
	parks.ChildAdded:Connect(function(plot)
		watchPlot(plot)
		check()
	end)
	parks.ChildRemoved:Connect(check)
	check()
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

-- 자동 굴리기(배치 모드 동안은 쉼)
task.spawn(function()
	while true do
		if autoRoll and not autoPaused and not rolling then
			roll(true)
		end
		task.wait(0.05)
	end
end)

-- 처음 상태 받아오기 (서버 데이터 로드가 끝날 때까지 서버 쪽에서 기다려 줌)
applyState(invoke("GetState"))
