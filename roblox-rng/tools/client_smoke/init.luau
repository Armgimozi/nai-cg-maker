-- 클라이언트 진입점(src/client/init.client.luau) 스모크 테스트: 가짜 환경에서 init.client 를 그대로 실행하고
-- 원격(RemoteFunction.InvokeServer)은 PlayerState + ParkService 로 흉내. 내 부지 찾기 → HUD [배치] → 공원으로 이동 →
-- 3D 배치 모드 → SetDisplay 원격(자동 꺼짐 · 공원 바뀜 알림) → [완료] · 다른 창 · 도감 [배치] · 이동 버튼 →
-- 상점(카드 6개 · Robux 가격 · 보유 도장 · 구매 원격 BuyPass/BuyProduct · 실패 이유별 알림)을 확인.
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
local SERVER = {
	GetState = function()
		return snap()
	end,
	Roll = function()
		table.insert(calls, "Roll")
		return { Ok = true, LandmarkId = rollLandmark.Id, State = snap(), IsNew = false, Stars = 1, Bonus = 0 }
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
