-- 클라이언트 진입점(src/client/init.client.luau) 스모크 테스트: 가짜 환경에서 init.client 를 그대로 실행하고
-- 원격(RemoteFunction.InvokeServer)은 PlayerState + ParkService 로 흉내. 내 부지 찾기 → HUD [배치] → 공원으로 이동 →
-- 3D 배치 모드 → SetDisplay 원격(자동 꺼짐 · 공원 바뀜 알림) → [완료] · 다른 창 · 도감 [배치] · 이동 버튼을 확인.
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
local function snap()
	revision += 1
	return PlayerState.snapshot(data, revision)
end
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

print("\n[모듈 오류]")
E.finish()
