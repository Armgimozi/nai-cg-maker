-- 클라이언트 진입점(src/client/init.client.luau) 스모크 테스트: 가짜 환경에서 init.client 를 그대로 실행하고
-- 원격(RemoteFunction.InvokeServer)은 PlayerState + ParkService 로 흉내. 내 부지 찾기 → HUD [배치] → 공원으로 이동 →
-- 3D 배치 모드 → SetDisplay 원격(자동 꺼짐 · 공원 바뀜 알림) → [완료] · 다른 창 · 도감 [배치] · 이동 버튼 →
-- 상점(카드 6개 · Robux 가격 · 보유 도장 · 구매 원격 BuyPass/BuyProduct · 실패 이유별 알림),
-- AUTO 연출(이미 발견한 명소 = 짧게 · 서버 굴림 간격 · RetryIn, 새 발견·수동 = 원래 길이), 별 상승 딱지(★+1),
-- 별 0(☆) 표시 · 환생 창 행운 ×2 · 자동 발견 알림을 확인.
-- 실행(roblox-rng 폴더에서): luaurun tools/client_smoke/init.luau   (끝 줄 "0 failed")

local E = compile(readfile("tools/client_smoke/env.luau"), "tools/client_smoke/env.luau")()
local Harness, Mock, UIS, camera, INSET = E.Harness, E.Mock, E.UIS, E.camera, E.INSET
local playerGui, root, humanoid = E.playerGui, E.root, E.humanoid
local client = E.client
local PlayerState, Landmarks, ParkGrid, ParkService = E.PlayerState, E.Landmarks, E.ParkGrid, E.ParkService
local serverPlayer, plot, origin, slotsFolder = E.serverPlayer, E.plot, E.origin, E.slotsFolder
local data = E.data
local unlocked = PlayerState.slots(data)
local check, frame, waitReal, settle, slotScreen, input = E.check, E.frame, E.waitReal, E.settle, E.slotScreen, E.input
local mouseTo, click, drag, key, touchDrag, face = E.mouseTo, E.click, E.drag, E.key, E.touchDrag, E.face
local Signal = E.Signal

local Net = Harness.require(E.shared.Net) -- 서버로 먼저 불러서 원격 폴더를 만듦
root.CFrame = CFrame.new(0, 4, 0) -- 광장

local revision = 0
local calls: { string } = {}
local mods = { Passes = {} } -- 가진 게임패스(상점 확인용)
local function snap()
	revision += 1
	return PlayerState.snapshot(data, revision, mods)
end
local buyReply: { [string]: any } = {} -- 상점 구매 원격이 돌려줄 값(상품 키 -> 응답)
local rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst] -- 흔한 명소(연출 짧음)
-- 굴림 응답의 나머지(바꿔 가며 확인) · 굴림 요청을 받은 가짜 시각 · 다음 한 번을 "cooldown" + RetryIn 으로 거절
local rollReply = { IsNew = false, StarUp = false, Stars = 0, Bonus = 0 }
local rollTimes: { number } = {}
local cooldownOnce: number? = nil
local SERVER = {
	GetState = function()
		return snap()
	end,
	Roll = function()
		table.insert(calls, "Roll")
		table.insert(rollTimes, Mock.clock())
		local retry = cooldownOnce
		if retry then
			cooldownOnce = nil
			return { Ok = false, Reason = "cooldown", RetryIn = retry }
		end
		return {
			Ok = true,
			LandmarkId = rollLandmark.Id,
			State = snap(),
			IsNew = rollReply.IsNew,
			StarUp = rollReply.StarUp,
			Stars = rollReply.Stars,
			Bonus = rollReply.Bonus,
		}
	end,
	SetDisplay = function(slot, id, expected, from)
		table.insert(calls, "SetDisplay")
		local done, reason = PlayerState.setDisplay(data, slot, id, expected, from)
		if done then
			ParkService.update(serverPlayer, data)
		end
		return { Ok = done, Reason = reason, State = snap() }
	end,
	SetSetting = function(key, value)
		table.insert(calls, "SetSetting " .. tostring(key))
		local done = PlayerState.setSetting(data, key, value)
		ParkService.update(serverPlayer, data)
		return { Ok = done, State = snap() }
	end,
	BuyPass = function(key)
		table.insert(calls, "BuyPass " .. tostring(key))
		return buyReply[key] or { Ok = true }
	end,
	BuyProduct = function(key)
		table.insert(calls, "BuyProduct " .. tostring(key))
		return buyReply[key] or { Ok = true }
	end,
	Teleport = function(where)
		table.insert(calls, "Teleport " .. tostring(where))
		if where == "Park" then
			root.CFrame = origin * CFrame.new(0, 3.6, -37)
		else
			root.CFrame = CFrame.new(0, 4, 0)
		end
		return { Ok = true }
	end,
}
local remoteFolder = Mock.ReplicatedStorage:FindFirstChild("LandmarkRNGRemotes")
for _, remote in remoteFolder:GetChildren() do
	if remote.ClassName == "RemoteFunction" then
		local name = remote.Name
		remote.__props.InvokeServer = function(_self, ...)
			local handler = SERVER[name]
			if handler then
				return handler(...)
			end
			return { Ok = false }
		end
	else
		remote.__props.OnClientEvent = Signal.new()
	end
end
check(Net ~= nil, "Net")

-- 3) 클라이언트 init.client.luau 그대로 ------------------------------------------------------
game:GetService("RunService").__props.IsServer = function()
	return false
end
local source = readfile("src/client/init.client.luau")
local fn = compile(source, "src/client/init.client.luau")
setfenv(fn, setmetatable({ script = client, require = Harness.require }, { __index = _G }))
local okRun, errRun = Mock.run(fn)
check(okRun, "init.client 실행 " .. tostring(errRun))
Mock.runScheduler(1)
local gui = playerGui:FindFirstChild("LandmarkRNG")
gui.AbsoluteSize = Vector2.new(1280, 684)
local ParkEdit = Harness.require(client.ParkEdit)

local function findNamed(parent, name)
	for _, d in parent:GetDescendants() do
		if d.Name == name then
			return d
		end
	end
	return nil
end
local function hasText(text: string): boolean
	for _, d in gui:GetDescendants() do
		if (d.ClassName == "TextLabel" or d.ClassName == "TextButton") and d.Text == text then
			return true
		end
	end
	return false
end
print("\n[init 연결]")
local arrange = findNamed(gui, "Arrange")
check(arrange and arrange.Visible, "내 부지 있음 -> HUD [배치] 보임")
check(slotsFolder:FindFirstChild("Slot1"):FindFirstChild("ParkClick") ~= nil, "내 받침대에 ClickDetector")
face(arrange).Activated:Fire()
Mock.runScheduler(3)
check(table.find(calls, "Teleport Park") ~= nil, "광장에서 [배치] = 공원으로 이동")
check(ParkEdit.isEditing(), "배치 모드")
local menu = findNamed(gui, "Menu")
check(not menu.Visible and not findNamed(gui, "RollBar").Visible, "HUD 메뉴·굴리기 줄 숨김")
check(findNamed(gui, "Teleport") and hasText("광장"), "이동 버튼 = 광장(지금 공원)")
local tray = findNamed(gui, "Tray")
tray.__props.AbsolutePosition = Vector2.new(109, 684 - 12 - 132 * 0.9)
tray.__props.AbsoluteSize = Vector2.new(1062, 132 * 0.9)

print("\n[SetDisplay 원격]")
local before = PlayerState.parkSlots(data)
local a, b = before[1], before[2]
click(slotScreen(1, 2))
click(slotScreen(2))
settle()
local after = PlayerState.parkSlots(data)
check(after[1] == b and after[2] == a, "원격으로 자리 바꿈")
check(hasText("자동 꺼짐"), "자동 꺼짐 알림")
-- stale
click(slotScreen(3, 2))
PlayerState.setDisplay(data, 4, nil)
ParkService.update(serverPlayer, data)
click(slotScreen(4))
settle()
check(hasText("공원 바뀜"), "stale = 공원 바뀜 알림")

print("\n[완료 · 다른 창]")
face(findNamed(tray, "Done")).Activated:Fire()
frame()
check(not ParkEdit.isEditing() and menu.Visible, "[완료] = 나가기, 메뉴 다시 보임")
ParkEdit.enter(nil)
Mock.runScheduler(5)
check(ParkEdit.isEditing(), "다시 들어감")
face(findNamed(menu, "Collection")).Activated:Fire()
frame()
check(not ParkEdit.isEditing(), "다른 창(도감)을 열면 배치 모드 끝")
local window = findNamed(gui, "Window")
check(window.Visible, "도감 열림")
local docArrange
for _, d in window:GetDescendants() do
	if d.Name == "Arrange" then
		docArrange = d
	end
end
face(docArrange).Activated:Fire()
Mock.runScheduler(7)
check(ParkEdit.isEditing() and not window.Visible, "도감 [배치] = 창 닫고 배치 모드")
face(findNamed(menu, "Teleport")).Activated:Fire()
Mock.runScheduler(9)
check(not ParkEdit.isEditing(), "이동(광장) = 배치 모드 끝")

print("\n[자동 굴리기: 배치 모드 동안 쉼, 나가면 다시]")
do
	local function rolls(): number
		local count = 0
		for _, call in calls do
			if call == "Roll" then
				count += 1
			end
		end
		return count
	end
	local revealFrame = findNamed(gui, "Reveal")
	key("T")
	Mock.runScheduler(Mock.clock() + 4)
	local before = rolls()
	check(before >= 2, "T = 자동 굴리기 (" .. before .. "번)")
	face(arrange).Activated:Fire()
	for _ = 1, 30 do
		if ParkEdit.isEditing() then
			break
		end
		Mock.runScheduler(Mock.clock() + 0.1)
	end
	check(ParkEdit.isEditing(), "배치 모드")
	check(hasText("AUTO 쉬는 중"), "들어가면 AUTO 쉬는 중 알림")
	check(not revealFrame.Visible, "가운데 굴림 연출 없음(공원을 가리지 않음)")
	local paused = rolls()
	Mock.runScheduler(Mock.clock() + 6)
	check(rolls() == paused, "배치 모드 동안 자동 굴리기 쉼 (" .. paused .. " -> " .. rolls() .. ")")
	key("T")
	check(hasText("AUTO OFF"), "배치 모드 T = AUTO 끄기(알림)")
	key("T")
	check(hasText("AUTO ON"), "다시 T = AUTO 켜기(나가면 적용)")
	Mock.runScheduler(Mock.clock() + 3)
	check(rolls() == paused, "배치 모드 동안은 계속 쉼")
	key("R")
	Mock.runScheduler(Mock.clock() + 2)
	check(rolls() == paused + 1, "R = 한 번 굴리기는 됨")
	local result = false
	for _, d in gui:GetDescendants() do
		if d.Name == "RollResult" then
			result = true
		end
	end
	check(
		result and not revealFrame.Visible,
		"배치 모드 굴림 결과 = 알림 줄 딱지(가운데 연출 없음)"
	)
	face(findNamed(findNamed(gui, "ParkEditBar"), "Done")).Activated:Fire()
	Mock.runScheduler(Mock.clock() + 4)
	check(not ParkEdit.isEditing() and rolls() > paused + 1, "나가면 자동 굴리기 다시 (" .. rolls() .. ")")
	key("T")
	Mock.runScheduler(Mock.clock() + 3)
	local stopped = rolls()
	Mock.runScheduler(Mock.clock() + 3)
	check(rolls() == stopped, "T = 자동 굴리기 끔")
end

print("\n[AUTO 연출: 이미 발견 = 짧게(서버 굴림 간격), 새 발견·수동 = 원래 길이]")
do
	local Config = Harness.require(E.shared.Config)
	local Ui = Harness.require(client.Ui)
	local revealFrame = findNamed(gui, "Reveal")
	local nameLabel = findNamed(revealFrame, "LandmarkName")
	check(nameLabel ~= nil, "굴림 연출 명소 이름 글자")
	check(Config.AUTO_KNOWN_REVEAL_RANK == 3, "Config.AUTO_KNOWN_REVEAL_RANK = 3")
	local cooldown = PlayerState.cooldown(data, mods)
	-- 앞 확인에서 돌던 굴림이 끝날 때까지
	Mock.runScheduler(Mock.clock() + 8)

	-- 가짜 시계를 0.05초씩 돌리며 "? ? ?"(불가사의 이상 뜸 들이기)를 봤는지, 굴림 요청 뒤 명소 이름이 보이기까지 걸린 시간
	local function watch(seconds: number, name: string): (boolean, { number })
		local suspense = false
		local shownAfter: { number } = {}
		local lastShown = false
		local stop = Mock.clock() + seconds
		while Mock.clock() < stop do
			Mock.runScheduler(Mock.clock() + 0.05)
			if nameLabel.Text == "? ? ?" then
				suspense = true
			end
			local shown = revealFrame.Visible and nameLabel.Text == name
			if shown and not lastShown then
				table.insert(shownAfter, Mock.clock() - rollTimes[#rollTimes])
			end
			lastShown = shown
		end
		return suspense, shownAfter
	end
	-- from 번째 굴림 요청부터의 간격(초)
	local function gaps(from: number): { number }
		local out = {}
		for i = from + 1, #rollTimes do
			table.insert(out, rollTimes[i] - rollTimes[i - 1])
		end
		return out
	end
	local function range(list: { number }): (number, number)
		local low, high = math.huge, -math.huge
		for _, v in list do
			low, high = math.min(low, v), math.max(high, v)
		end
		return low, high
	end
	local function autoRun(seconds: number, name: string): (boolean, { number }, { number })
		local from = #rollTimes + 1
		key("T")
		local suspense, shownAfter = watch(seconds, name)
		key("T")
		Mock.runScheduler(Mock.clock() + 8) -- 마지막 연출 끝
		local list = gaps(from)
		-- AUTO 를 끈 뒤에 끝난 마지막 굴림 뒤로는 요청이 없어야 함
		return suspense, list, shownAfter
	end

	-- 1) 이미 발견한 전설(세계수, 원래 AUTO 연출 약 6.5초) = 3등급 AUTO 길이: 굴림 간격 ≈ 1.2~1.3초, 뜸 들이기 없음
	local rare = Landmarks.RarestFirst[1]
	check(rare.Tier.Rank == 7, "세계수 = 7등급")
	rollLandmark = rare
	rollReply.IsNew, rollReply.StarUp, rollReply.Stars = false, false, 0
	local suspense, knownGaps, knownShown = autoRun(13, rare.Name)
	local low, high = range(knownGaps)
	check(#knownGaps >= 8, "AUTO 13초 동안 이미 발견한 세계수 " .. (#knownGaps + 1) .. "번")
	check(
		low >= cooldown - 1e-6 and high < 1.45,
		string.format(
			"이미 발견 = 짧은 연출: 굴림 간격 %.2f~%.2f초 (굴림 간격 %.2f초 이상)",
			low,
			high,
			cooldown
		)
	)
	local _, shownHigh = range(knownShown)
	check(#knownShown >= 8 and shownHigh < 1.1, string.format("요청 뒤 %.2f초 안에 이름 공개", shownHigh))
	check(not suspense, '이미 발견 = "? ? ?" 뜸 들이기 없음')

	-- 2) 새 발견(IsNew) = AUTO 여도 원래 길이(회전 3.3 + 착지 0.4 + 뜸 0.9 + 1.8초 보여 주기)
	rollReply.IsNew = true
	local newSuspense, newGaps = autoRun(15, rare.Name)
	local newLow = range(newGaps)
	check(
		#newGaps >= 1 and newLow > 5.5,
		string.format("새 발견 = 원래 연출: 굴림 간격 %.2f초 이상", newLow)
	)
	check(newSuspense, '새 발견 = "? ? ?" 뜸 들이기')

	-- 3) 수동 굴림(AUTO 끔) = 이미 발견해도 원래 길이
	rollReply.IsNew = false
	key("R")
	local manualSuspense, manualShown = watch(8, rare.Name)
	check(
		#manualShown == 1 and manualShown[1] > 4,
		string.format("수동 굴림 = 원래 연출(이름 공개까지 %.2f초)", manualShown[1] or -1)
	)
	check(manualSuspense, '수동 굴림 = "? ? ?" 뜸 들이기')

	-- 4) 흔한 명소는 연출(약 0.9초)이 굴림 간격보다 짧음 -> 다음 굴림은 서버 굴림 간격(1.2초)을 기다림
	rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst]
	local _, commonGaps = autoRun(7, rollLandmark.Name)
	local cLow, cHigh = range(commonGaps)
	check(
		#commonGaps >= 4 and cLow >= cooldown - 1e-6 and cHigh <= cooldown + 0.07,
		string.format("흔한 명소 = 굴림 간격대로 %.2f~%.2f초 (%.2f초)", cLow, cHigh, cooldown)
	)

	-- 5) 서버가 굴림 간격으로 거절하면(RetryIn) 그만큼 기다렸다가 다시 요청
	cooldownOnce = 0.7
	local from = #rollTimes + 1
	key("T")
	Mock.runScheduler(Mock.clock() + 1)
	key("T")
	Mock.runScheduler(Mock.clock() + 4)
	local retryGap = rollTimes[from + 1] and rollTimes[from + 1] - rollTimes[from] or -1
	check(
		retryGap >= 0.7 - 1e-6 and retryGap <= 0.8,
		string.format("RetryIn 0.7초 뒤 다시 요청 (%.2f초)", retryGap)
	)

	-- 6) 또 뽑아 별이 오름(가챠 중복): "★★☆☆☆ +1" 딱지, ★5 가 되면 "MAX". 처음 발견 = 별 딱지 없음
	local starChip = findNamed(revealFrame, "StarUp")
	local function goldStars(text: string): number
		local gold = text:match('^<font color="[^"]*">(.-)</font>') or ""
		return select(2, gold:gsub("★", ""))
	end
	rollReply.StarUp, rollReply.Stars = true, 2
	key("R")
	Mock.runScheduler(Mock.clock() + 3)
	local starLabel = findNamed(starChip, "Label")
	check(
		starChip.Visible and starLabel.Text:find("+1", 1, true) ~= nil and goldStars(starLabel.Text) == 2,
		'2번째 → 3번째 발견 = 별 2개 + "+1" 딱지 (' .. starLabel.Text .. ")"
	)
	rollReply.Stars = PlayerState.MAX_STARS
	key("R")
	Mock.runScheduler(Mock.clock() + 3)
	check(
		starChip.Visible and starLabel.Text:find("MAX", 1, true) ~= nil and goldStars(starLabel.Text) == 5,
		'★5 = "MAX" 딱지'
	)
	rollReply.StarUp, rollReply.Stars, rollReply.IsNew = false, 0, true
	key("R")
	Mock.runScheduler(Mock.clock() + 3)
	check(not starChip.Visible and findNamed(revealFrame, "New").Visible, "처음 발견 = NEW(별 딱지 없음)")
	rollReply.IsNew = false

	-- 7) 별 0(☆) 표시: 도감 카드 — 보유 1개 = 빈 별 5개, 6개 = ★5, 발견했지만 지금 없음 = 별 줄 비움
	local ids = {}
	for _, landmark in Landmarks.RarestFirst do
		if data.Inventory[landmark.Id] and #ids < 3 then
			table.insert(ids, landmark.Id)
		end
	end
	data.Inventory[ids[1]] = 1
	data.Inventory[ids[2]] = 7
	data.Inventory[ids[3]] = nil -- Discovered 에는 남음
	remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
	Mock.runScheduler(Mock.clock() + 0.3)
	face(findNamed(menu, "Collection")).Activated:Fire()
	frame()
	local window = findNamed(gui, "Window")
	local function cardStars(id: string): string?
		local card = findNamed(window, id)
		local label = card and card:FindFirstChild("Stars")
		return label and label.Text
	end
	local one, seven, gone = cardStars(ids[1]) or "?", cardStars(ids[2]) or "?", cardStars(ids[3])
	check(
		goldStars(one) == 0 and select(2, one:gsub("★", "")) == 5,
		"도감: 1개(처음 발견) = 빈 별 5개 ☆0"
	)
	check(goldStars(seven) == 5, "도감: 7개 = ★5 (최대)")
	check(gone == "", "도감: 발견했지만 지금 없음 = 별 줄 없음 (" .. tostring(gone) .. ")")
	face(findNamed(menu, "Collection")).Activated:Fire()
	frame()
	data.Inventory[ids[1]], data.Inventory[ids[2]], data.Inventory[ids[3]] = 5, 5, 5

	-- 8) 환생 창: 행운은 환생마다 ×2(곱), 수입 +50%(더함). 지금 배율 = 3번 ×8 / 10번 ×1,024(콤마)
	local function panelHas(text: string): boolean
		for _, d in window:GetDescendants() do
			if d.ClassName == "TextLabel" and d.Text == text then
				return true
			end
		end
		return false
	end
	data.Rebirths = 3
	remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
	Mock.runScheduler(Mock.clock() + 0.3)
	face(findNamed(menu, "Rebirth")).Activated:Fire()
	frame()
	check(panelHas("×2") and panelHas("+50%"), "환생 창 아래 줄: 행운 ×2 · 수입 +50%")
	check(not panelHas("+20%"), '옛 규칙 "+20%" 없음')
	check(panelHas("×8") and panelHas("×2.5"), "환생 3번: 행운 ×8 · 수입 ×2.5")
	data.Rebirths = Config.MAX_REBIRTHS
	remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
	Mock.runScheduler(Mock.clock() + 0.3)
	check(panelHas("×1,024") and panelHas("×6"), "환생 10번: 행운 ×1,024(콤마) · 수입 ×6")
	local luckChip = findNamed(findNamed(gui, "Stats"), "Luck")
	local luckText = luckChip and findNamed(luckChip, "Label").Text
	check(
		luckText == Ui.times(PlayerState.luck(data, mods)),
		"HUD 행운 = 스냅샷 Luck (" .. tostring(luckText) .. ")"
	)
	check(luckText ~= nil and luckText:match("^×%d[%d,]*$") ~= nil and #luckText > 6, "큰 행운은 콤마 자연수")
	face(findNamed(menu, "Rebirth")).Activated:Fire()
	frame()
	data.Rebirths = 0

	-- 9) 자동 발견(서버가 Discovered 에 넣음): 굴리지 않은 명소가 도감에 들어오면 [도감] "도감 +N". 굴려서 얻은(보유) 명소는 안 셈
	local function lastToast(): string?
		local newest, order = nil, -math.huge
		for _, d in gui:GetDescendants() do
			if d.Name == "Toast" and d.LayoutOrder > order then
				newest, order = d, d.LayoutOrder
			end
		end
		local label = newest and findNamed(newest, "Label")
		return label and label.Text
	end
	local fresh = {}
	for _, landmark in Landmarks.List do
		if not PlayerState.isDiscovered(data, landmark.Id) and #fresh < 4 then
			table.insert(fresh, landmark.Id)
		end
	end
	for i, id in fresh do
		data.Discovered[id] = true
		if i == 4 then
			data.Inventory[id] = 1 -- 굴려서 얻음(연출이 보여 줌)
		end
	end
	remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
	Mock.runScheduler(Mock.clock() + 0.3)
	check(lastToast() == "도감 +3", '자동 발견 3개 = "도감 +3" 알림 (' .. tostring(lastToast()) .. ")")
	local function discoveryToasts(): number
		local count = 0
		for _, d in gui:GetDescendants() do
			local label = d.Name == "Toast" and findNamed(d, "Label")
			if label and label.Text:sub(1, #"도감 +") == "도감 +" then
				count += 1
			end
		end
		return count
	end
	local shown = discoveryToasts()
	remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
	Mock.runScheduler(Mock.clock() + 0.3)
	check(shown == 1 and discoveryToasts() == 1, "새로 들어온 명소가 없으면 알림 없음")
	rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst]
end

print("\n[상점: 카드 6개 · Robux 가격 · 보유 도장 · 구매 원격]")
do
	local Config = Harness.require(E.shared.Config)
	local vip = Config.GamePasses[1]
	-- 로블록스 상품 정보: 행운 VIP 만 받아짐(실제 가격 350 · 그림 777), 나머지는 오류 → Config 가격 그대로
	local infoCalls = 0
	game:GetService("MarketplaceService").__props.GetProductInfo = function(_self, id, infoType)
		infoCalls += 1
		if id == vip.PassId and infoType == Enum.InfoType.GamePass then
			return { PriceInRobux = 350, IconImageAssetId = 777 }
		end
		error("HTTP 500 (가짜)")
	end
	-- 빠른 굴림은 이미 가짐(서버 상태 이벤트로)
	mods.Passes.FastRoll = true
	remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
	Mock.runScheduler(Mock.clock() + 0.5)

	local shopButton = findNamed(gui, "Shop")
	check(shopButton and shopButton.Visible, "HUD 상점 버튼")
	do
		-- 키보드 기기(1280×684): 오른쪽 위 플레이어 목록에 가리지 않게 굴리기 줄 바로 위 높이까지 내려감
		local Hud, Ui = Harness.require(client.Hud), Harness.require(client.Ui)
		Hud.setPlotOwned(false) -- 자리 다시 잡기(가짜 환경은 AbsoluteSize 바뀜 이벤트가 없음)
		Hud.setPlotOwned(true)
		local size, scale = gui.AbsoluteSize, Ui.scale()
		local center = size.Y * shopButton.Position.Y.Scale + shopButton.Position.Y.Offset
		local rollTop = size.Y - 14 - 100 * scale
		check(
			center > size.Y / 2 + 16 and center + 45 * scale <= rollTop,
			string.format(
				"상점 버튼은 오른쪽 아래(굴리기 줄 위) — 가운데 %.0f, 굴리기 줄 위 %.0f",
				center,
				rollTop
			)
		)
		-- 키보드 + 터치 겸용(터치 노트북·키보드 붙인 태블릿): 화면을 만지면 점프 버튼이 오른쪽 아래에 나오므로 그 위까지만
		UIS.__props.TouchEnabled = true
		Hud.setPlotOwned(false)
		Hud.setPlotOwned(true)
		local hybrid = size.Y * shopButton.Position.Y.Scale + shopButton.Position.Y.Offset
		local jumpTop = size.Y - (if math.min(size.X, size.Y) <= 500 then 90 else 210)
		check(
			hybrid + 45 * scale <= jumpTop and hybrid < center,
			string.format(
				"터치 겸용 기기: 상점 버튼은 점프 버튼 위 — 가운데 %.0f, 점프 버튼 위 %.0f",
				hybrid,
				jumpTop
			)
		)
		UIS.__props.TouchEnabled = false
		Hud.setPlotOwned(false)
		Hud.setPlotOwned(true)
		check(
			size.Y * shopButton.Position.Y.Scale + shopButton.Position.Y.Offset == center,
			"터치 없는 키보드 기기로 돌아오면 다시 굴리기 줄 위"
		)
	end
	local shopIcon = findNamed(shopButton, "Icon")
	check(shopIcon and shopIcon:GetAttribute("Icon") == "robux", "상점 버튼 = Robux 표시(코인 아님)")
	face(shopButton).Activated:Fire()
	Mock.runScheduler(Mock.clock() + 0.5)
	local window = findNamed(gui, "Window")
	check(window.Visible and hasText("상점"), "상점 창 열림")

	local KEYS = { "LuckVIP", "FastRoll", "DoubleIncome", "LuckBoost", "ServerLuck", "CoinPack" }
	local cards = {}
	for _, key in KEYS do
		cards[key] = findNamed(window, key)
	end
	local found = 0
	for _, key in KEYS do
		if cards[key] and findNamed(cards[key], "Buy") then
			found += 1
		end
	end
	check(found == 6, "카드 6개 + 구매 버튼 (" .. found .. ")")
	local function price(key: string): string?
		local label = findNamed(findNamed(cards[key], "Buy"), "Label")
		return label and label.Text
	end
	local function buyIcon(key: string): string?
		local icon = findNamed(findNamed(cards[key], "Buy"), "Icon")
		return icon and icon:GetAttribute("Icon")
	end
	-- 처음부터 가격이 있음(빈 버튼·"구매" 없음). 상품 정보는 받는 대로(실패하면 3초 뒤 한 번 더)
	local priced = 0
	for _, key in KEYS do
		local text = price(key)
		if text and text:match("^%d[%d,]*$") then
			priced += 1
		end
	end
	check(priced == 6, "열자마자 버튼 6개 모두 Robux 숫자 (" .. priced .. ")")
	Mock.runScheduler(Mock.clock() + 4)
	check(
		infoCalls == 1 + 5 * 2,
		"상품 정보 요청: 받은 것 1번 + 실패 5개는 한 번씩 더 (" .. infoCalls .. ")"
	)
	check(price("LuckVIP") == "350", "받은 실제 가격으로 바뀜 (" .. tostring(price("LuckVIP")) .. ")")
	local configPrices = true
	for _, key in { "DoubleIncome", "LuckBoost", "ServerLuck", "CoinPack" } do
		local item = PlayerState.PassesById[key] or PlayerState.ProductsById[key]
		if price(key) ~= tostring(item.Price) then
			configPrices = false
			print("       " .. key .. " 가격 " .. tostring(price(key)))
		end
	end
	check(configPrices, "못 받으면 Config 가격(49·99·79·299)")
	local marks = 0
	for _, key in KEYS do
		if buyIcon(key) == "robux" then
			marks += 1
		end
	end
	check(marks == 6, "구매 버튼마다 Robux 표시 (" .. marks .. ")")
	local art = findNamed(findNamed(cards.LuckVIP, "Band"), "Art")
	check(art and art.Image == "rbxassetid://777", "받은 상품 그림을 띠에 (구매 창과 같은 그림)")
	check(findNamed(findNamed(cards.CoinPack, "Band"), "Art") == nil, "그림을 못 받으면 아이콘 그대로")
	local fastBuy, fastOwned = findNamed(cards.FastRoll, "Buy"), findNamed(cards.FastRoll, "Owned")
	check(
		not fastBuy.Visible and fastOwned and fastOwned.Visible,
		"가진 게임패스 = 보유 도장(구매 버튼 숨김)"
	)
	check(findNamed(cards.LuckVIP, "Buy").Visible, "안 가진 게임패스 = 구매 버튼")

	-- 알림 줄의 가장 최근 알림 글자
	local function lastToast(): string?
		local newest, order = nil, -math.huge
		for _, d in gui:GetDescendants() do
			if d.Name == "Toast" and d.LayoutOrder > order then
				newest, order = d, d.LayoutOrder
			end
		end
		local label = newest and findNamed(newest, "Label")
		return label and label.Text
	end
	local function press(key: string)
		face(findNamed(cards[key], "Buy")).Activated:Fire()
		Mock.runScheduler(Mock.clock() + 0.1)
	end
	local before = #calls
	press("LuckVIP")
	check(calls[#calls] == "BuyPass LuckVIP", "행운 VIP = BuyPass(LuckVIP) (" .. tostring(calls[#calls]) .. ")")
	press("FastRoll")
	check(calls[#calls] == "BuyPass LuckVIP", "보유한 패스는 원격을 부르지 않음")
	buyReply.LuckBoost = { Ok = false, Reason = "max" }
	press("LuckBoost")
	check(calls[#calls] == "BuyProduct LuckBoost", "행운 부스트 = BuyProduct(LuckBoost)")
	check(lastToast() == "MAX", "Reason max = MAX 알림 (" .. tostring(lastToast()) .. ")")
	buyReply.ServerLuck = { Ok = false, Reason = "loading" }
	press("ServerLuck")
	check(calls[#calls] == "BuyProduct ServerLuck", "서버 행운 = BuyProduct(ServerLuck)")
	check(lastToast() == "불러오는 중", "Reason loading = MAX 아님 (" .. tostring(lastToast()) .. ")")
	buyReply.CoinPack = { Ok = false }
	press("CoinPack")
	check(calls[#calls] == "BuyProduct CoinPack", "코인 팩 = BuyProduct(CoinPack)")
	check(lastToast() == "구매 실패", "이유 없음 = 구매 실패 (" .. tostring(lastToast()) .. ")")
	buyReply.DoubleIncome = { Ok = false, Reason = "owned" }
	press("DoubleIncome")
	check(calls[#calls] == "BuyPass DoubleIncome", "수입 2배 = BuyPass(DoubleIncome)")
	check(lastToast() == "보유", "Reason owned = 보유 알림 (" .. tostring(lastToast()) .. ")")
	check(#calls - before == 5, "구매 원격 5번 (" .. (#calls - before) .. ")")
	face(shopButton).Activated:Fire()
	frame()
	check(not window.Visible, "상점 버튼 다시 = 닫힘")
end

print("\n[모듈 오류]")
E.finish()
