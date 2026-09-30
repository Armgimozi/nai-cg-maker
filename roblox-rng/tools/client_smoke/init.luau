-- 클라이언트 진입점(src/client/init.client.luau) 스모크 테스트: 가짜 환경에서 init.client 를 그대로 실행하고
-- 원격(RemoteFunction.InvokeServer)은 PlayerState + ParkService 로 흉내. 내 부지 찾기 → [배치] 버튼 없음 · 배지는 [공원] →
-- 광장에서 내 명소를 눌러도 안 들어감 → [공원] 으로 이동 → 내 명소를 톡 = 3D 배치 모드 + 집음 → SetDisplay 원격(자동 꺼짐 ·
-- 공원 바뀜 알림) → [완료] · 다른 창(창이 열려 있으면 공원을 눌러도 안 들어감) · 이동 버튼 →
-- 상점(카드 6개 · Robux 가격 · 보유 도장 · 구매 원격 BuyPass/BuyProduct · 실패 이유별 알림),
-- AUTO 빠른 결과(이미 발견한 명소 = 결과 카드만 퐁, 네트워크 왕복 0.12초 + 60fps 프레임 흉내에서도 평균 굴림 간격대로 — 빠른 굴림
-- ×0.7 · 여행사 최대 + 빠른 굴림 0.42초 · 서버 굴림 간격 거절 없음(들쭉날쭉한 지연 포함, RollLogic.cooldownGate) · 기다리는 동안
-- AUTO 끄면 안 보냄 · 가는 중에 끄면 카드만 · 지구본 아이콘 계속 돎 · 6등급 햇살은 행운 대비 · RetryIn, 새 발견·수동 = 원래 길이),
-- 별 상승 딱지(★+1 — AUTO 는 알림 줄에도 한 칸),
-- 별 0(☆) 표시 · 환생 창 행운 ×2 · 자동 발견 알림,
-- 도감 대륙 탭(여권 버튼 없음 · 도감 버튼 도장 배지 · [전체]/대륙 거르기와 순서 · 대륙 머리 줄 숫자 = PlayerState.regionProgress ·
-- 탭을 바꿔도 카드·3D 사진 그대로 · 열려 있는 동안 탭 기억 · 도장 알림을 누르면 그 대륙 탭)을 확인.
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
local Config = Harness.require(E.shared.Config)
local RollLogic = Harness.require(E.shared.RollLogic)
local rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst] -- 흔한 명소(연출 짧음)
-- 굴림 응답의 나머지(바꿔 가며 확인) · 굴림 요청을 보낸 가짜 시각 · 다음 한 번을 "cooldown" + RetryIn 으로 거절
local rollReply = { IsNew = false, StarUp = false, Stars = 0, Bonus = 0, Luck = 1 }
local rollCycle: { any }? = nil -- 있으면 굴릴 때마다 이 명소들을 돌아가며(같은 이름이 계속 보이지 않게)
local rollTimes: { number } = {}
local cooldownOnce: number? = nil
-- 흉내 네트워크 왕복(초): 절반은 요청이 서버에 닿기까지, 절반은 응답이 돌아오기까지(0 이면 바로).
-- rollLatency 가 있으면 굴림마다 (요청, 응답) 지연을 따로 받음(들쭉날쭉한 네트워크)
local rollDelay = 0
local rollLatency: (() -> (number, number))? = nil
-- 서버 굴림 간격 규칙: init.server.luau Roll 과 같은 RollLogic.cooldownGate(허용 오차만큼 일찍 와도 받음)
local serverLastRoll = -math.huge
local serverRejects = 0
local SERVER = {
	GetState = function()
		return snap()
	end,
	Roll = function()
		table.insert(calls, "Roll")
		table.insert(rollTimes, Mock.clock())
		local up, down = rollDelay / 2, rollDelay / 2
		local latency = rollLatency
		if latency then
			up, down = latency()
		end
		if up > 0 then
			task.wait(up)
		end
		local retry = cooldownOnce
		if retry then
			cooldownOnce = nil
			return { Ok = false, Reason = "cooldown", RetryIn = retry }
		end
		local ok, value = RollLogic.cooldownGate(
			serverLastRoll,
			Mock.clock(),
			PlayerState.cooldown(data, mods),
			Config.COOLDOWN_TOLERANCE
		)
		if not ok then
			serverRejects += 1
			if down > 0 then
				task.wait(down)
			end
			return { Ok = false, Reason = "cooldown", RetryIn = value }
		end
		serverLastRoll = value
		local landmark = rollLandmark
		local cycle = rollCycle
		if cycle then
			landmark = cycle[(#rollTimes - 1) % #cycle + 1]
		end
		local reply = {
			Ok = true,
			LandmarkId = landmark.Id,
			State = snap(),
			IsNew = rollReply.IsNew,
			StarUp = rollReply.StarUp,
			Stars = rollReply.Stars,
			Bonus = rollReply.Bonus,
			Luck = rollReply.Luck,
		}
		if down > 0 then
			task.wait(down)
		end
		return reply
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
check(findNamed(gui, "Arrange") == nil, "HUD 에 [배치] 버튼 없음")
check(
	E.plot:FindFirstChildWhichIsA("ClickDetector", true) == nil,
	"내 받침대에 ClickDetector 없음(직접 누름)"
)
local teleportButton = findNamed(gui, "Teleport")
check(teleportButton and findNamed(teleportButton, "Better") ~= nil, "더 좋은 명소 배지는 [공원] 버튼에")
-- 평소 카메라처럼: 내 공원 입구 뒤 위에서 공원 안을 봄. 내 명소를 누를 화면 점(처음 맞는 것이 그 칸 모델)
local function lookIntoPark()
	camera.CFrame = CFrame.lookAt(
		origin:PointToWorldSpace(Vector3.new(0, 46, -64)),
		origin:PointToWorldSpace(Vector3.new(0, 0, -4))
	)
end
local function statuePoint(slot: number): Vector2?
	local x, z = ParkGrid.slotOffset(slot)
	for _, height in { 2.5, 1.5, 3.5, 0.9, 5 } do
		local at = E.toScreen(
			origin:PointToWorldSpace(Vector3.new(x, ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT + height, z))
		)
		local ray = camera:ViewportPointToRay(at.X, at.Y)
		local params = RaycastParams.new()
		params.FilterType = Enum.RaycastFilterType.Exclude
		params.FilterDescendantsInstances = { E.character }
		local hit = workspace:Raycast(ray.Origin, ray.Direction * 1000, params)
		local node = hit and hit.Instance
		while node and node.Parent ~= slotsFolder do
			node = node.Parent
		end
		if node and node:GetAttribute("Slot") == slot then
			return at
		end
	end
	return nil
end
lookIntoPark()
local parkTap = statuePoint(1) :: Vector2
check(parkTap ~= nil, "누를 수 있는 내 명소(칸 1)")
E.tap(parkTap)
Mock.runScheduler(Mock.clock() + 2)
check(not ParkEdit.isEditing(), "광장에 있으면 내 명소를 눌러도 안 들어감")
face(teleportButton).Activated:Fire()
Mock.runScheduler(Mock.clock() + 2)
check(
	table.find(calls, "Teleport Park") ~= nil and hasText("광장"),
	"[공원] = 내 공원으로 이동(버튼은 [광장])"
)
check(not ParkEdit.isEditing(), "이동만 해서는 배치 모드 아님")
lookIntoPark()
E.tap(parkTap)
Mock.runScheduler(Mock.clock() + 2)
check(ParkEdit.isEditing(), "내 공원에서 내 명소를 톡 = 배치 모드")
check(workspace:FindFirstChild("ParkEditLocal"):FindFirstChild("Held", true) ~= nil, "그 명소를 바로 집음")
key("Escape")
settle()
local menu = findNamed(gui, "Menu")
check(not menu.Visible and not findNamed(gui, "RollBar").Visible, "HUD 메뉴·굴리기 줄 숨김")
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
lookIntoPark()
E.tap(parkTap)
Mock.runScheduler(Mock.clock() + 2)
check(ParkEdit.isEditing(), "다시 톡 = 배치 모드")
face(findNamed(menu, "Collection")).Activated:Fire()
frame()
check(not ParkEdit.isEditing(), "다른 창(도감)을 열면 배치 모드 끝")
local window = findNamed(gui, "Window")
check(window.Visible, "도감 열림")
-- 창이 열려 있으면 뒤 공원을 눌러도 안 들어감(창 바탕 Frame 은 입력을 막지 않음 — init 의 CanTap)
lookIntoPark()
E.tap(parkTap)
Mock.runScheduler(Mock.clock() + 2)
check(not ParkEdit.isEditing() and window.Visible, "창이 열려 있으면 공원을 눌러도 안 들어감")
face(findNamed(menu, "Collection")).Activated:Fire()
frame()
check(not window.Visible, "도감 닫힘")
-- 굴림 결과 카드(가운데)는 입력을 막지 않음(Active 아님 — 카드 위에서 끌어도 화면이 돎): 카드가 덮은 내 명소를 눌러도
-- 안 들어가고(init CanTap 이 카드 자리를 봄), 카드 밖은 그대로. 굴림 연출 중이면 어디를 눌러도 안 들어감
do
	local reveal = findNamed(gui, "Reveal")
	local disc = findNamed(reveal, "Disc")
	local inset = game:GetService("GuiService"):GetGuiInset()
	local cardParts = { "Ribbon", "Region", "LandmarkName", "Odds", "TagRow" }
	for _, name in cardParts do
		local part = findNamed(reveal, name)
		if part then
			part.__props.AbsolutePosition = Vector2.new(-1000, -1000) -- 카드의 다른 딱지는 명소 점 밖
			part.__props.AbsoluteSize = Vector2.new(10, 10)
		end
	end
	reveal.Visible = true
	disc.__props.AbsolutePosition = parkTap - inset - Vector2.new(60, 60)
	disc.__props.AbsoluteSize = Vector2.new(120, 120)
	E.tap(parkTap)
	Mock.runScheduler(Mock.clock() + 2)
	check(not ParkEdit.isEditing(), "굴림 결과 카드가 덮은 내 명소를 눌러도 안 들어감")
	disc.__props.AbsolutePosition = parkTap - inset + Vector2.new(200, 200)
	E.tap(parkTap)
	Mock.runScheduler(Mock.clock() + 2)
	check(ParkEdit.isEditing(), "카드 밖 내 명소를 톡 = 배치 모드")
	key("Escape")
	settle()
	ParkEdit.exit()
	settle()
	lookIntoPark() -- (가짜 환경 카메라는 배치 모드 위에서 보기 자리에 남음)
	reveal.Visible = false
	-- 굴림 연출 중(수동 굴림 = 원래 길이): 카드 밖이어도 안 들어감
	key("R")
	Mock.runScheduler(Mock.clock() + 0.1)
	check(reveal.Visible, "굴림 연출 중")
	E.tap(parkTap)
	Mock.runScheduler(Mock.clock() + 0.1)
	check(not ParkEdit.isEditing(), "굴림 연출 중에는 내 명소를 눌러도 안 들어감")
	Mock.runScheduler(Mock.clock() + 12)
	check(not reveal.Visible, "연출·카드 끝")
	for _, name in cardParts do
		local part = findNamed(reveal, name)
		if part then
			part.__props.AbsolutePosition = nil
			part.__props.AbsoluteSize = nil
		end
	end
	disc.__props.AbsolutePosition = nil
	disc.__props.AbsoluteSize = nil
end
E.tap(parkTap)
Mock.runScheduler(Mock.clock() + 2)
check(ParkEdit.isEditing(), "창을 닫으면 다시 톡 = 배치 모드")
face(findNamed(menu, "Teleport")).Activated:Fire()
Mock.runScheduler(Mock.clock() + 2)
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
	face(findNamed(menu, "Teleport")).Activated:Fire() -- 내 공원으로
	for _ = 1, 30 do
		if hasText("광장") then
			break
		end
		Mock.runScheduler(Mock.clock() + 0.1)
	end
	lookIntoPark()
	E.tap(parkTap) -- 내 명소를 톡
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

print(
	"\n[AUTO 빠른 결과: 이미 발견 = 결과 카드만 퐁 · 굴림 간격대로(빠른 굴림·여행사), 새 발견·수동 = 원래 길이]"
)
do
	local Ui = Harness.require(client.Ui)
	local revealFrame = findNamed(gui, "Reveal")
	local nameLabel = findNamed(revealFrame, "LandmarkName")
	check(nameLabel ~= nil, "굴림 연출 명소 이름 글자")
	check(Config.AUTO_QUICK_REVEAL == true, "Config.AUTO_QUICK_REVEAL = true")
	local stateEvent = remoteFolder:FindFirstChild("State")
	-- 게임패스·여행사를 바꾼 뒤 클라이언트에 새 굴림 간격을 알림(서버가 상태를 보내는 것처럼)
	local function cooldownNow(): number
		stateEvent.OnClientEvent:Fire(snap())
		return PlayerState.cooldown(data, mods)
	end
	local cooldown = cooldownNow()
	-- 앞 확인에서 돌던 굴림이 끝날 때까지
	Mock.runScheduler(Mock.clock() + 8)
	-- 프레임 흉내(60fps): Roblox 처럼 task.wait 가 기다린 뒤 첫 프레임에 깸 — 늦음이 굴림마다 쌓이면 AUTO 가 굴림
	-- 간격보다 느려짐(0.42초 → 26프레임 0.433초). 클라이언트는 원래 보낼 수 있던 시각을 기준으로 해서 평균이 굴림 간격 그대로
	local FRAME = 1 / 60
	Mock.frameSeconds = FRAME
	-- 굴리기 버튼 지구본 아이콘의 회전 속도(Icons.setSpin — 180 이상이면 돎, 60 은 멈춰서 0°)
	local rollIcon: Instance? = nil
	for _, d in findNamed(findNamed(gui, "RollBar"), "Roll"):GetDescendants() do
		if d:GetAttribute("Spin") ~= nil then
			rollIcon = d
			break
		end
	end
	check(rollIcon ~= nil, "굴리기 버튼 지구본 아이콘")
	local function rollSpin(): number
		return if rollIcon then tonumber(rollIcon:GetAttribute("Spin")) or 0 else 0
	end

	-- n 번째 굴림 요청의 결과 이름(rollCycle 이면 돌아가며)
	local function nameFor(n: number): string
		local cycle = rollCycle
		return if cycle then cycle[(n - 1) % #cycle + 1].Name else rollLandmark.Name
	end
	-- 가짜 시계를 0.05초씩 돌리며 "? ? ?"(불가사의 이상 뜸 들이기)를 봤는지, 굴림 요청마다 그 결과 이름이 가운데 카드에
	-- 보이기까지 걸린 시간
	local function watch(seconds: number, probe: (() -> ())?): (boolean, { number })
		local suspense = false
		local shownAfter: { number } = {}
		local seen: { [number]: boolean } = {}
		local stop = Mock.clock() + seconds
		while Mock.clock() < stop do
			Mock.runScheduler(Mock.clock() + 0.05)
			if probe then
				probe()
			end
			if nameLabel.Text == "? ? ?" then
				suspense = true
			end
			local n = #rollTimes
			if n > 0 and not seen[n] and revealFrame.Visible and nameLabel.Text == nameFor(n) then
				seen[n] = true
				table.insert(shownAfter, Mock.clock() - rollTimes[n])
			end
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
	local function mean(list: { number }): number
		local sum = 0
		for _, v in list do
			sum += v
		end
		return if #list > 0 then sum / #list else 0
	end
	local function autoRun(seconds: number, probe: (() -> ())?): (boolean, { number }, { number })
		local from = #rollTimes + 1
		key("T")
		local suspense, shownAfter = watch(seconds, probe)
		key("T")
		Mock.runScheduler(Mock.clock() + 8) -- 마지막 연출 끝
		return suspense, gaps(from), shownAfter
	end
	-- 굴림 간격대로인지: 한 번 한 번은 프레임 하나 안(task.wait 는 다음 프레임에 깸), 평균은 굴림 간격 그대로
	-- (보낸 시각 합 = n × 굴림 간격 + 마지막·처음 프레임 늦음 차이 → 평균 오차 ≤ 프레임 / n)
	local function onSchedule(list: { number }, period: number, minCount: number, label: string)
		local low, high = range(list)
		local average = mean(list)
		check(
			#list >= minCount
				and low >= period - FRAME - 1e-6
				and high <= period + FRAME + 1e-6
				and math.abs(average - period) <= FRAME / #list + 1e-6,
			string.format(
				"%s = 굴림 간격대로 평균 %.4f초 (%.3f~%.3f, 굴림 간격 %.2f초, %d번)",
				label,
				average,
				low,
				high,
				period,
				#list
			)
		)
	end
	local SHOWN_WITHIN = 2 * FRAME + 0.051 -- 응답이 온 뒤 카드가 보이기까지(프레임 2개 + 확인 간격 0.05초)

	-- 네트워크 왕복 0.12초 흉내(요청이 서버에 닿기까지 0.06 + 응답 0.06), 결과는 이미 발견한 전설 둘을 번갈아
	-- (세계수 ↔ 샹그릴라 — 이름이 바뀌어야 "새 결과가 보였다"를 셀 수 있음)
	rollDelay = 0.12
	local rejectsBefore = serverRejects
	local legends = { Landmarks.RarestFirst[1], Landmarks.RarestFirst[2] }
	check(legends[1].Tier.Rank == 7 and legends[2].Tier.Rank == 7, "세계수·샹그릴라 = 7등급")
	rollCycle = legends
	rollReply.IsNew, rollReply.StarUp, rollReply.Stars = false, false, 0

	-- 1) 게임패스·여행사 없음: 이미 발견한 전설도 굴림 간격(1.2초)대로, 결과 카드는 응답이 오자마자.
	-- 6등급 이상은 햇살(희귀 퐁), 흔한 명소는 햇살 없음(7번)
	local burst = findNamed(revealFrame, "Burst")
	local rareBurst = false
	local lowestSpin = math.huge
	local suspense, baseGaps, baseShown = autoRun(12, function()
		rareBurst = rareBurst or (revealFrame.Visible and burst.Visible)
		lowestSpin = math.min(lowestSpin, rollSpin())
	end)
	onSchedule(baseGaps, cooldown, 8, "이미 발견한 전설(왕복 " .. rollDelay .. "초)")
	check(
		lowestSpin >= 180,
		string.format(
			"AUTO 동안 굴리기 버튼 지구본이 계속 돎(굴림마다 0°로 안 튐, 가장 느릴 때 %d)",
			lowestSpin
		)
	)
	check(rollSpin() < 180, "AUTO 끄면 지구본 아이콘 멈춤 (" .. rollSpin() .. ")")
	local _, shownHigh = range(baseShown)
	check(
		#baseShown >= #baseGaps and shownHigh <= rollDelay + SHOWN_WITHIN,
		string.format(
			"결과마다 응답이 오자마자 카드(요청 뒤 %.2f초 안, %d번)",
			shownHigh,
			#baseShown
		)
	)
	check(not suspense, '이미 발견 = "? ? ?" 뜸 들이기 없음')
	check(rareBurst, "이미 발견한 전설 = 빠른 결과에도 햇살(희귀 퐁)")

	-- 2) 빠른 굴림(굴림 간격 ×0.7): AUTO 간격도 ×0.7
	mods.Passes.FastRoll = true
	local fast = cooldownNow()
	check(
		math.abs(fast - cooldown * 0.7) < 1e-9,
		string.format("빠른 굴림 굴림 간격 %.2f초 = %.2f × 0.7", fast, cooldown)
	)
	local _, fastGaps, fastShown = autoRun(10)
	onSchedule(fastGaps, fast, 10, "빠른 굴림 AUTO")
	check(
		math.abs(mean(fastGaps) / mean(baseGaps) - 0.7) < 0.005,
		string.format("빠른 굴림 AUTO 간격 = 없을 때 × %.3f (0.7)", mean(fastGaps) / mean(baseGaps))
	)
	check(#fastShown >= #fastGaps, "빠른 굴림: 결과마다 카드 (" .. #fastShown .. "번)")

	-- 3) 여행사 최대(-50%) + 빠른 굴림: 1.2 × 0.5 × 0.7 = 0.42초, 서버 굴림 간격 거절 없음
	local agencyMax = 0
	for _, upgrade in Config.Upgrades do
		if upgrade.Id == "Agency" then
			agencyMax = upgrade.MaxLevel
		end
	end
	local agencyBefore = data.Upgrades.Agency
	data.Upgrades.Agency = agencyMax
	local both = cooldownNow()
	local bothSuspense, bothGaps, bothShown = autoRun(8)
	onSchedule(bothGaps, both, 15, "여행사 최대 + 빠른 굴림 AUTO")
	check(
		math.abs(mean(bothGaps) / mean(baseGaps) - 0.35) < 0.005,
		string.format(
			"여행사 최대 + 빠른 굴림 AUTO 간격 = 없을 때 × %.3f (0.5 × 0.7)",
			mean(bothGaps) / mean(baseGaps)
		)
	)
	local _, bothShownHigh = range(bothShown)
	check(
		#bothShown >= #bothGaps and bothShownHigh <= rollDelay + SHOWN_WITHIN and not bothSuspense,
		string.format("0.42초 간격에도 결과마다 카드(요청 뒤 %.2f초 안)", bothShownHigh)
	)
	check(
		serverRejects == rejectsBefore,
		"서버 굴림 간격 거절 없음 (" .. serverRejects - rejectsBefore .. "번)"
	)

	-- 4) 새 발견(IsNew) = AUTO·빠른 굴림이어도 원래 길이(회전 3.3 + 착지 0.4 + 뜸 0.9 + 1.8초 보여 주기)
	rollReply.IsNew = true
	local newSuspense, newGaps = autoRun(15)
	local newLow = range(newGaps)
	check(
		#newGaps >= 1 and newLow > 5.5,
		string.format("새 발견 = 원래 연출: 굴림 간격 %.2f초 이상", newLow)
	)
	check(newSuspense, '새 발견 = "? ? ?" 뜸 들이기')
	rollReply.IsNew = false

	-- 5) 수동 굴림(AUTO 끔) = 이미 발견해도 원래 길이
	key("R")
	local manualSuspense, manualShown = watch(8)
	check(
		#manualShown == 1 and manualShown[1] > 4,
		string.format("수동 굴림 = 원래 연출(이름 공개까지 %.2f초)", manualShown[1] or -1)
	)
	check(manualSuspense, '수동 굴림 = "? ? ?" 뜸 들이기')

	-- 6) 굴림 간격을 기다리는 동안 AUTO 를 끄면 그 굴림은 보내지 않음(끈 뒤 원래 길이 연출이 하나 더 뜨지 않음),
	-- 마지막 카드는 잠시 뒤 숨음. 기다리는 동안 R 을 누르면 그 굴림은 수동으로 나감
	Mock.runScheduler(Mock.clock() + 3)
	key("T")
	Mock.runScheduler(Mock.clock() + 0.3) -- 첫 결과(0.12초) 뒤 다음 굴림이 0.42초를 기다리는 중
	local sent = #rollTimes
	key("T")
	local offSuspense = watch(3)
	check(#rollTimes == sent, "AUTO 끄면 기다리던 굴림은 안 보냄 (" .. #rollTimes - sent .. "번 더)")
	check(
		not offSuspense and not revealFrame.Visible,
		"끈 뒤 원래 길이 연출 없음, 카드는 잠시 뒤 숨음"
	)
	key("T")
	Mock.runScheduler(Mock.clock() + 0.3)
	sent = #rollTimes
	key("T")
	key("R")
	local keptSuspense, keptShown = watch(8) -- 앞 결과(이미 보인 카드) + 수동 굴림 결과
	check(
		#rollTimes == sent + 1 and keptSuspense and (keptShown[#keptShown] or 0) > 4,
		string.format(
			"기다리는 동안 AUTO 끄고 R = 그 굴림은 수동(원래 연출, 이름까지 %.2f초)으로 나감",
			keptShown[#keptShown] or -1
		)
	)

	-- 6c) 요청이 서버로 가는 중(응답을 기다리는 중)에 AUTO 를 꺼도 그 결과는 AUTO 결과: 이미 발견 = 카드만 퐁(원래 길이
	-- 연출·"? ? ?" 없음). 빠른 결과인지는 보낼 때 정함. 그 뒤로는 안 보냄
	Mock.runScheduler(Mock.clock() + 8)
	rollDelay = 0.3
	key("T")
	Mock.runScheduler(Mock.clock() + 0.1) -- 첫 굴림(바로 나감)이 서버로 가는 중(요청 0.15초)
	sent = #rollTimes
	key("T")
	local flightSuspense, flightShown = watch(3)
	check(
		#rollTimes == sent and #flightShown == 1 and flightShown[1] <= rollDelay + SHOWN_WITHIN and not flightSuspense,
		string.format(
			'가는 중에 AUTO 끄면 그 결과는 카드만 퐁(요청 뒤 %.2f초, "? ? ?" 없음, %d번 더 보냄)',
			flightShown[1] or -1,
			#rollTimes - sent
		)
	)
	check(rollSpin() < 180, "응답이 온 뒤 지구본 아이콘 멈춤")
	rollDelay = 0.12

	-- 7) 흔한 명소(이미 발견)도 굴림 간격대로
	rollCycle = nil
	rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst]
	local commonBurst = false
	local _, commonGaps = autoRun(5, function()
		-- (앞 수동 굴림의 세계수 카드가 아직 남아 있을 수 있어 흔한 명소 카드일 때만)
		local common = revealFrame.Visible and nameLabel.Text == rollLandmark.Name
		commonBurst = commonBurst or (common and burst.Visible)
	end)
	check(not commonBurst, "흔한 명소 빠른 결과 = 햇살 없음(작은 퐁)")
	onSchedule(commonGaps, both, 8, "흔한 명소 AUTO")
	check(serverRejects == rejectsBefore, "서버 굴림 간격 거절 없음")

	-- 7b) 들쭉날쭉한 네트워크: 요청 지연이 굴림마다 바뀌어도(늦게 닿은 요청 뒤에 제때 보낸 요청이 일찍 닿음) 서버 거절
	-- 없이 굴림 간격대로 — RollLogic.cooldownGate 가 기준을 "닿은 시각 - 허용 오차"까지만 늦춤(늦게 닿은 시각 그대로면
	-- 지연이 허용 오차 0.15초보다 줄어든 다음 굴림이 거절됨)
	rollCycle = legends
	-- (1) 0.42초: 요청 지연 0.03 ↔ 0.25초 번갈아(0.22초 줄어듦), 응답 0.03초
	local flip = false
	rollLatency = function()
		flip = not flip
		return if flip then 0.25 else 0.03, 0.03
	end
	local _, altGaps = autoRun(8)
	onSchedule(altGaps, both, 15, "요청 지연 0.03↔0.25초 번갈아(여행사 최대 + 빠른 굴림)")
	-- (2) 0.84초(빠른 굴림만): 요청 0.02~0.28초 · 응답 0.02~0.12초 무작위(고정 씨앗)
	data.Upgrades.Agency = agencyBefore
	cooldownNow()
	local seed = 12345
	local function nextRandom(): number
		seed = (seed * 1103515245 + 12345) % 2147483648
		return seed / 2147483648
	end
	rollLatency = function()
		return 0.02 + 0.26 * nextRandom(), 0.02 + 0.1 * nextRandom()
	end
	local _, randomGaps = autoRun(20)
	onSchedule(randomGaps, fast, 20, "요청 0.02~0.28 · 응답 0.02~0.12초 무작위(빠른 굴림)")
	-- (3) 1.2초(없음): 왕복 0.05 ↔ 0.45초 번갈아 → 결과 사이가 1.6초로 벌어져도 카드가 숨었다 다시 뜨지 않음
	-- (숨기는 시각 = max(1.5초, 굴림 간격 + 0.8초))
	mods.Passes.FastRoll = nil
	cooldownNow()
	rollLatency = function()
		flip = not flip
		local oneWay = if flip then 0.225 else 0.025
		return oneWay, oneWay
	end
	local cardShown, cardHidden = false, false
	local _, slowGaps = autoRun(12, function()
		if revealFrame.Visible then
			cardShown = true
		elseif cardShown then
			cardHidden = true
		end
	end)
	onSchedule(slowGaps, cooldown, 8, "왕복 0.05↔0.45초 번갈아(게임패스 없음)")
	check(
		cardShown and not cardHidden,
		"결과 사이가 굴림 간격보다 벌어져도 카드가 숨었다 뜨지 않음"
	)
	check(
		serverRejects == rejectsBefore,
		"들쭉날쭉한 네트워크에서도 서버 굴림 간격 거절 없음 ("
			.. serverRejects - rejectsBefore
			.. "번)"
	)
	rollLatency = nil

	-- 7c) 6등급(잃어버린 유산)은 지금 행운으로도 드물 때만 햇살(1/N ≥ 100 × 굴림 행운): 후반 행운 55,296 이면 6등급이
	-- 굴림의 절반이라 햇살이 굴림마다 켜졌다 꺼지지 않게. 전설은 행운과 상관없이 햇살
	local lost: any = nil
	for _, landmark in Landmarks.RarestFirst do
		if landmark.Tier.Rank == 6 and landmark.OneIn < 1000000 then
			lost = landmark
			break
		end
	end
	local function burstSeen(luck: number, names: { [string]: boolean }): boolean
		rollReply.Luck = luck
		local seen = false
		autoRun(3, function()
			seen = seen or (revealFrame.Visible and names[nameLabel.Text] == true and burst.Visible)
		end)
		return seen
	end
	rollCycle = nil
	rollLandmark = lost
	check(
		not burstSeen(55296, { [lost.Name] = true }),
		string.format("6등급 %s(1/%d) · 행운 55,296 = 햇살 없음(작은 퐁)", lost.Name, lost.OneIn)
	)
	burst.Rotation = 123 -- 햇살이 꺼진 동안의 각도: 다시 켜지면 여기서 이어서 돎(0° 로 튀지 않음)
	check(burstSeen(1000, { [lost.Name] = true }), "같은 6등급 · 행운 1,000 = 햇살(희귀 퐁)")
	check(
		math.abs(burst.Rotation % 360 - 123) < 1e-6,
		string.format("햇살이 다시 켜지면 멈췄던 각도에서 이어서 돎 (%.0f°)", burst.Rotation % 360)
	)
	rollCycle = legends
	check(
		burstSeen(55296, { [legends[1].Name] = true, [legends[2].Name] = true }),
		"전설 · 행운 55,296 = 햇살(행운과 상관없이)"
	)
	rollReply.Luck = 1

	-- 되돌리기(아래 확인은 게임패스·여행사 없이, 네트워크 지연·프레임 흉내 없이)
	Mock.frameSeconds = 0
	mods.Passes.FastRoll = nil
	data.Upgrades.Agency = agencyBefore
	rollDelay = 0
	rollCycle = nil
	rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst]
	cooldown = cooldownNow()

	-- 8) 서버가 굴림 간격으로 거절하면(RetryIn) 그만큼 기다렸다가 다시 요청
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

	-- 6b) AUTO 중 별 상승: 이미 발견한 명소는 빠른 결과라 가운데 딱지는 다음 굴림(굴림 간격)에 곧 덮임 → 알림 줄에 결과 딱지 +
	-- "★+1"(★5 = "★MAX")을 2.5초 남김. 별 알림은 한 칸만(새 것이 옛 것을 바꿈 — 다른 알림을 밀어내지 않음), AUTO 속도 그대로
	do
		local Hud = Harness.require(client.Hud)
		local function starToasts(): { any }
			local list = {}
			for _, d in gui:GetDescendants() do
				if d.Name == "StarUpToast" then
					table.insert(list, d)
				end
			end
			return list
		end
		local function badge(toast: any): string
			local chip = findNamed(toast, "StarUp")
			local label = chip and findNamed(chip, "Label")
			return if label then label.Text else ""
		end
		Hud.toast("다른 알림", nil, 30)
		rollLandmark = Landmarks.RarestFirst[1] -- 이미 발견한 전설 = 빠른 결과
		rollReply.IsNew, rollReply.StarUp, rollReply.Stars = false, true, 2
		local from = #rollTimes + 1
		local born: { [any]: number } = {}
		local died: { [any]: number } = {}
		local most, plusOne, named = 0, true, true
		local function step()
			Mock.runScheduler(Mock.clock() + 0.05)
			local list = starToasts()
			most = math.max(most, #list)
			for _, toast in list do
				if not born[toast] then
					born[toast] = Mock.clock()
					plusOne = plusOne and badge(toast):find("+1", 1, true) ~= nil
					named = named and findNamed(toast, "Label").Text == rollLandmark.Name
				end
			end
			for toast in born do
				if not died[toast] and not table.find(list, toast) then
					died[toast] = Mock.clock()
				end
			end
		end
		key("T")
		local stop = Mock.clock() + 8
		while Mock.clock() < stop do
			step()
		end
		key("T") -- 돌던 굴림은 끝까지(그 결과가 마지막 별 알림)
		for _ = 1, 100 do
			step()
		end
		local list = gaps(from)
		local made, last, lastBorn = 0, nil, -math.huge
		for toast, at in born do
			made += 1
			if at > lastBorn then
				last, lastBorn = toast, at
			end
		end
		local _, high = range(list)
		check(
			made >= 5 and made == #list + 1,
			string.format("AUTO 별 상승마다 알림 줄 딱지 (%d개, 굴림 %d번)", made, #list + 1)
		)
		check(plusOne and named, '알림 딱지 = 명소 이름 + "★+1"')
		check(most == 1, "별 알림은 한 칸만 (동시에 최대 " .. most .. "개)")
		local lastFor = (died[last] or Mock.clock()) - lastBorn
		check(
			lastFor >= 2.4,
			string.format("마지막 별 알림은 다음 굴림이 없어도 %.2f초 보임", lastFor)
		)
		check(hasText("다른 알림"), "별 알림이 다른 알림을 밀어내지 않음")
		check(
			high <= cooldown + 0.02,
			string.format("AUTO 속도 그대로 (굴림 간격 최대 %.2f초, 굴림 간격 %.2f초)", high, cooldown)
		)
		-- ★5 = "★MAX" · 수동 굴림은 가운데 딱지가 오래 보이므로 알림 줄 딱지 없음
		rollReply.Stars = PlayerState.MAX_STARS
		key("T")
		Mock.runScheduler(Mock.clock() + 1.5)
		key("T")
		local maxToast = starToasts()[1]
		check(maxToast ~= nil and badge(maxToast):find("MAX", 1, true) ~= nil, '★5 알림 딱지 = "★MAX"')
		Mock.runScheduler(Mock.clock() + 8)
		key("R")
		Mock.runScheduler(Mock.clock() + 8)
		check(#starToasts() == 0, "수동 굴림 별 상승 = 가운데 딱지만(알림 줄 딱지 없음)")
		rollReply.StarUp, rollReply.Stars = false, 0
		rollLandmark = Landmarks.RarestFirst[#Landmarks.RarestFirst]
	end

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

print(
	"\n[도감 대륙 탭: 여권을 합침 · 대륙 거르기 · 도장 머리 줄 · 도장 알림 · 탭을 바꿔도 3D 사진 그대로]"
)
do
	local Panels = Harness.require(client.Panels)
	local Ui = Harness.require(client.Ui)
	local stateEvent = remoteFolder:FindFirstChild("State")
	local function refresh()
		stateEvent.OnClientEvent:Fire(snap())
		Mock.runScheduler(Mock.clock() + 0.3)
	end
	local function openMenu(name: string)
		face(findNamed(menu, name)).Activated:Fire()
		frame()
	end
	local function badgeText(parent: Instance?, name: string): string?
		local chip = parent and findNamed(parent, name)
		local label = chip and findNamed(chip, "Label")
		return label and label.Text
	end

	-- 메뉴: 여권 버튼 없음, 도장 수 배지는 도감 버튼에
	check(findNamed(menu, "Passport") == nil, "메뉴에 여권 버튼 없음")
	local stampBadge = findNamed(findNamed(menu, "Collection"), "Stamps")
	local stamps = #PlayerState.completedRegions(data)
	check(
		stampBadge ~= nil
			and stampBadge.Visible
			and badgeText(findNamed(menu, "Collection"), "Stamps")
				== string.format("%d/%d", stamps, #Landmarks.Regions),
		"도감 버튼 배지 = 받은 도장 수 ("
			.. tostring(badgeText(findNamed(menu, "Collection"), "Stamps"))
			.. ")"
	)

	-- 탭: [전체] + 대륙마다 하나, 처음은 전체
	Panels.close()
	openMenu("Collection")
	local window = findNamed(gui, "Window")
	local tabs = findNamed(window, "Tabs")
	local tabIds = { "All" }
	for _, region in Landmarks.Regions do
		table.insert(tabIds, region.Id)
	end
	local tabCount = 0
	for _, id in tabIds do
		if tabs and findNamed(tabs, "Tab" .. id) then
			tabCount += 1
		end
	end
	check(tabs ~= nil and tabs.Visible and tabCount == #tabIds, "탭 " .. tabCount .. "개 ([전체] + 대륙)")
	local _, firstTab = Panels.current()
	check(firstTab == "All", "처음 열면 [전체] 탭")
	check(window.Size.Y.Offset > 500, "도감 창은 탭 줄만큼 더 높음 (" .. window.Size.Y.Offset .. ")")

	local scroller = findNamed(window, "Collection")
	local function visibleCards(): { any }
		local cards = {}
		for _, child in scroller:GetChildren() do
			if Landmarks.ById[child.Name] and child.Visible then
				table.insert(cards, child)
			end
		end
		table.sort(cards, function(a, b)
			return a.LayoutOrder < b.LayoutOrder
		end)
		return cards
	end
	local function viewports(): number
		local count = 0
		for _, d in window:GetDescendants() do
			if d.ClassName == "ViewportFrame" then
				count += 1
			end
		end
		return count
	end
	local function pickTab(id: string)
		face(findNamed(tabs, "Tab" .. id)).Activated:Fire()
		frame()
	end

	-- [전체] = 발견한 명소만, 희귀한 순서
	local all = visibleCards()
	local discovered = 0
	for _, landmark in Landmarks.List do
		if PlayerState.isDiscovered(data, landmark.Id) then
			discovered += 1
		end
	end
	local rarestFirst = true
	for i = 2, #all do
		if Landmarks.ById[all[i].Name].OneIn > Landmarks.ById[all[i - 1].Name].OneIn then
			rarestFirst = false
		end
	end
	check(#all == discovered and rarestFirst, "[전체] = 발견한 명소 " .. #all .. "개, 희귀한 순서")
	local allHeader = findNamed(findNamed(window, "CollectionHeader"), "All")
	check(
		allHeader.Visible
			and badgeText(allHeader, "Count") == string.format("%d/%d", discovered, #Landmarks.List)
			and badgeText(allHeader, "Stamps") == string.format("%d/%d", stamps, #Landmarks.Regions),
		"[전체] 머리 줄: 발견 수 · 도장 수 ("
			.. tostring(badgeText(allHeader, "Count"))
			.. " · "
			.. tostring(badgeText(allHeader, "Stamps"))
			.. ")"
	)
	check(
		findNamed(allHeader, "Arrange") == nil and findNamed(allHeader, "AutoFeature") ~= nil,
		"[전체] 머리 줄 [자동](배치 버튼 없음)"
	)

	-- 대륙 탭: 그 대륙 명소 전부(흔한 순서), 못 찾은 명소는 자물쇠 카드. 3D 사진은 다시 만들지 않음
	local before = viewports()
	local keep = all[1]
	local region = Landmarks.Regions[1]
	for _, candidate in Landmarks.Regions do
		if candidate.Id == Landmarks.ById[keep.Name].Region then
			region = candidate -- 첫 카드가 있는 대륙(대륙 탭에서도 같은 카드가 보이는지)
		end
	end
	pickTab(region.Id)
	local _, selected = Panels.current()
	check(selected == region.Id, "탭 누름 = 그 대륙 (" .. tostring(selected) .. ")")
	local cards = visibleCards()
	local expected = Landmarks.ByRegion[region.Id]
	local sameOrder = #cards == #expected
	local lockedRight = true
	for i, card in cards do
		if not expected[i] or card.Name ~= expected[i].Id then
			sameOrder = false
		end
		local known = PlayerState.isDiscovered(data, card.Name)
		if (card:GetAttribute("Unknown") == true) == known then
			lockedRight = false
		end
	end
	check(sameOrder, region.Id .. " 탭 = 그 대륙 명소 " .. #cards .. "/" .. #expected .. "개, 흔한 순서")
	check(lockedRight, "못 찾은 명소만 자물쇠 카드(3D 없음), 찾은 명소는 도감 카드")
	check(keep.Parent == scroller and keep.Visible, "같은 카드를 그대로 씀(새로 만들지 않음)")
	check(
		viewports() == before,
		"탭을 바꿔도 3D 사진(ViewportFrame) 수 그대로 (" .. before .. " -> " .. viewports() .. ")"
	)
	local headerFrame = findNamed(findNamed(window, "CollectionHeader"), region.Id)
	local found, required = PlayerState.regionProgress(data, region.Id)
	check(headerFrame.Visible and not allHeader.Visible, "대륙 머리 줄만 보임([자동]은 전체 탭에)")
	check(
		findNamed(headerFrame, "Count").Text == string.format("%d/%d", found, required),
		"발견 막대 숫자 = PlayerState.regionProgress (" .. findNamed(headerFrame, "Count").Text .. ")"
	)
	local fill = findNamed(headerFrame, "Fill")
	check(
		math.abs(fill.Size.X.Scale - found / required) < 1e-6,
		string.format("막대 채움 = %d/%d", found, required)
	)
	-- 탭을 오가도 같은 카드 · 같은 3D 사진 수
	for _, other in Landmarks.Regions do
		pickTab(other.Id)
	end
	pickTab("All")
	check(
		keep.Parent == scroller and keep.Visible and viewports() == before and #visibleCards() == #all,
		"여러 탭을 돌고 [전체]로 와도 카드·3D 사진 그대로"
	)

	-- 창이 열려 있는 동안 탭 기억(상태가 바뀌어도), 닫으면 다음엔 [전체]
	pickTab(region.Id)
	refresh()
	local _, kept = Panels.current()
	check(kept == region.Id, "상태가 바뀌어도 고른 탭 유지")
	openMenu("Upgrade")
	check(
		window.Visible and not tabs.Visible and not findNamed(window, "CollectionHeader").Visible,
		"강화 창에는 도감 탭 줄·머리 줄 안 보임"
	)
	openMenu("Collection")
	local _, back = Panels.current()
	check(back == region.Id, "다른 창에 갔다 와도(창은 열린 채) 탭 유지")
	openMenu("Collection") -- 닫기
	check(not window.Visible, "도감 버튼 다시 = 닫힘")
	openMenu("Collection")
	local _, reopened = Panels.current()
	check(reopened == "All" and visibleCards()[1] == all[1], "닫았다 열면 [전체]부터")
	Panels.close()

	-- 도장 머리 줄 도장 그림: 받으면 진하게(투명 0), 아직이면 회색 + 흐리게(Panels FADED_STAMP_TRANSPARENCY 0.4 — 크림 바탕에서도 보임)
	local function stampArt(regionId: string): any
		local header = findNamed(findNamed(window, "CollectionHeader"), regionId)
		local stamp = header and findNamed(header, "Stamp")
		return stamp and findNamed(stamp, "Icon")
	end
	-- 대륙 탭: 도장이 아직이면 아래 발견 막대(regionProgress), 받았으면 막대 대신 체크
	local function tabLooksRight(regionId: string): (boolean, string)
		local button = findNamed(tabs, "Tab" .. regionId)
		local strip, mark = findNamed(button, "Strip"), findNamed(button, "Stamped")
		local got, need = PlayerState.regionProgress(data, regionId)
		if got >= need then
			return mark.Visible and not strip.Visible, "체크"
		end
		local fill = findNamed(strip, "Fill")
		local ratio = fill.Size.X.Scale
		return strip.Visible and not mark.Visible and math.abs(ratio - got / need) < 1e-6,
			string.format("막대 %d/%d", got, need)
	end
	local function stampToasts(regionId: string?): { any }
		local list = {}
		for _, d in gui:GetDescendants() do
			if d.Name == "StampToast" and (regionId == nil or d:GetAttribute("Region") == regionId) then
				table.insert(list, d)
			end
		end
		return list
	end
	-- 도장이 아직인 대륙 하나를 다 모음(도장 조건 명소만 Discovered — 자동 발견과 같음)
	local added = {}
	local function complete(regionId: string)
		for _, landmark in Landmarks.ByRegion[regionId] do
			if PlayerState.countsForStamp(landmark) and not PlayerState.isDiscovered(data, landmark.Id) then
				data.Discovered[landmark.Id] = true
				table.insert(added, landmark.Id)
			end
		end
	end
	local open = {}
	for _, candidate in Landmarks.Regions do
		local got, need = PlayerState.regionProgress(data, candidate.Id)
		if got < need then
			table.insert(open, candidate)
		end
	end
	check(#open >= 3, "도장이 아직인 대륙 3개 이상 (" .. #open .. ")")
	local target, second, third = open[1], open[2], open[3]

	-- 탭 줄 발견 막대 · 도장 그림(아직) · 전체 탭 도장 행운 딱지
	openMenu("Collection")
	local stripsRight = true
	local stripNotes = {}
	for _, region in Landmarks.Regions do
		local ok, note = tabLooksRight(region.Id)
		stripsRight = stripsRight and ok
		table.insert(stripNotes, region.Id .. " " .. note)
	end
	check(
		stripsRight,
		"대륙 탭 = 도장 아직이면 발견 막대(regionProgress), 받았으면 체크 ("
			.. table.concat(stripNotes, " · ")
			.. ")"
	)
	local bonusText = badgeText(allHeader, "StampBonus")
	check(
		bonusText == string.format("+%d%%", math.max(stamps, 1) * math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)),
		"[전체] 도장 행운 = 도장 수 × 25% (도장 없으면 회색 +25%, +0% 아님) ("
			.. tostring(bonusText)
			.. ")"
	)
	pickTab(target.Id)
	local faded = stampArt(target.Id)
	check(
		faded ~= nil and faded:GetAttribute("Transparency") == 0.4,
		"도장 아직 = 머리 줄 도장 흐리게 0.4 ("
			.. tostring(faded and faded:GetAttribute("Transparency"))
			.. ")"
	)
	-- 도장에 안 세는 못 찾은 명소(불가사의보다 희귀) = 자물쇠 대신 전설 도장 그림, 세는 명소 = 자물쇠.
	-- 가짜 데이터는 희귀 명소를 다 가지고 시작해서, 대표가 아닌 보너스 명소 하나를 잠깐 못 찾은 것으로
	local hidden
	for _, landmark in Landmarks.List do
		if not PlayerState.countsForStamp(landmark) and data.Featured ~= landmark.Id then
			hidden = landmark
		end
	end
	local wasDiscovered = hidden and data.Discovered[hidden.Id]
	local wasOwned = hidden and data.Inventory[hidden.Id]
	if hidden then
		data.Discovered[hidden.Id] = nil
		data.Inventory[hidden.Id] = nil
		pickTab(hidden.Region)
		refresh()
	end
	local bonusRight, bonusCards = true, 0
	for _, card in visibleCards() do
		if card:GetAttribute("Unknown") == true then
			local counts = PlayerState.countsForStamp(Landmarks.ById[card.Name])
			if (card:GetAttribute("Bonus") == true) == counts then
				bonusRight = false
			end
			if not counts then
				bonusCards += 1
			end
		end
	end
	check(
		bonusRight and bonusCards > 0,
		"못 찾은 보너스 명소(" .. bonusCards .. "개)만 전설 도장 그림, 나머지는 자물쇠"
	)
	if hidden then
		data.Discovered[hidden.Id] = wasDiscovered
		data.Inventory[hidden.Id] = wasOwned
		refresh()
	end
	Panels.close()

	-- 도장 알림: 대륙 하나를 다 모으면(자동 발견 포함) [도장] "도장 +25%" — 누르면 도감이 그 대륙 탭으로 열림
	complete(target.Id)
	refresh()
	local toast = stampToasts(target.Id)[1]
	check(
		toast ~= nil
			and findNamed(toast, "Label").Text
				== string.format("도장 +%d%%", math.floor(Config.REGION_LUCK_BONUS * 100 + 0.5)),
		target.Id .. " 도장 = 알림 [도장] 도장 +25%"
	)
	check(
		toast ~= nil and findNamed(toast, "Go") ~= nil,
		"도장 알림 끝에 가기 화살표(누를 수 있는 알림)"
	)
	local badgeAfter = badgeText(findNamed(menu, "Collection"), "Stamps")
	check(
		badgeAfter == string.format("%d/%d", stamps + 1, #Landmarks.Regions),
		"도감 버튼 배지 +1 (" .. tostring(badgeAfter) .. ")"
	)
	-- 상태가 또 와도(AUTO 면 굴릴 때마다) 이미 받은 도장은 다시 알리지 않음
	refresh()
	refresh()
	check(
		#stampToasts(nil) == 1 and badgeText(findNamed(menu, "Collection"), "Stamps") == badgeAfter,
		"같은 도장은 한 번만 알림 (" .. #stampToasts(nil) .. "개)"
	)

	-- 누름 = 알림 위에서 눌렀다 알림 안에서 뗌(버튼처럼). 밖에서 떼거나(끌기) 뗌만 오면 안 열림
	if toast then
		toast.__props.AbsolutePosition = Vector2.new(520, 60)
		toast.__props.AbsoluteSize = Vector2.new(240, 40)
		local onToast, offToast = Vector2.new(600, 36 + 80), Vector2.new(900, 36 + 400)
		toast.InputBegan:Fire(input("MouseButton1", onToast), false)
		frame()
		check(not window.Visible, "누르는 순간에는 안 열림")
		toast.InputEnded:Fire(input("MouseButton1", offToast), false)
		frame()
		check(not window.Visible, "알림에서 누르고 밖에서 떼면 안 열림(끌기)")
		toast.InputEnded:Fire(input("Touch", onToast), false)
		frame()
		check(not window.Visible, "누르지 않고 뗌만 오면 안 열림")
	end
	-- 배치 모드 중에 눌러도: 배치 모드를 끝내고 도감을 그 대륙 탭으로, 알림은 바로 쪼그라들어 사라짐
	ParkEdit.enter(nil)
	Mock.runScheduler(Mock.clock() + 3)
	local wasEditing = ParkEdit.isEditing()
	if toast then
		local at = Vector2.new(600, 36 + 80)
		toast.InputBegan:Fire(input("Touch", at), false)
		frame()
		toast.InputEnded:Fire(input("Touch", at), false)
		frame()
	end
	local openName, stampTab = Panels.current()
	check(
		openName == "Collection" and stampTab == target.Id and window.Visible,
		"도장 알림을 누르면 도감 "
			.. target.Id
			.. " 탭 ("
			.. tostring(openName)
			.. " · "
			.. tostring(stampTab)
			.. ")"
	)
	check(wasEditing and not ParkEdit.isEditing(), "배치 모드 중이면 먼저 나감")
	check(toast ~= nil and toast:GetAttribute("Leaving") == true, "누른 알림은 바로 치움(쪼그라듦)")
	Mock.runScheduler(Mock.clock() + 0.3)
	check(
		#stampToasts(nil) == 0,
		"도감이 열린 뒤 도장 알림이 탭 줄을 가리지 않음 (" .. #stampToasts(nil) .. "개)"
	)
	local stampHeader = findNamed(findNamed(window, "CollectionHeader"), target.Id)
	local got, need = PlayerState.regionProgress(data, target.Id)
	check(
		stampHeader.Visible
			and got == need
			and findNamed(stampHeader, "Count").Text == string.format("%d/%d", got, need)
			and findNamed(stampHeader, "Check").Visible,
		"그 대륙 머리 줄: 막대 가득 + 체크 (" .. findNamed(stampHeader, "Count").Text .. ")"
	)
	local bonus = findNamed(stampHeader, "Bonus")
	local grass = Ui.colorPair("Grass").Face
	check(bonus.ImageColor3 == grass or bonus.BackgroundColor3 == grass, "받은 도장 = +25% 초록")
	local inked = stampArt(target.Id)
	check(
		inked ~= nil and inked:GetAttribute("Transparency") == 0,
		"받은 도장 = 머리 줄 도장 진하게(투명 0) ("
			.. tostring(inked and inked:GetAttribute("Transparency"))
			.. ")"
	)
	local slam = findNamed(stampHeader, "Slam")
	check(slam ~= nil and slam.Scale == 1, "알림으로 열면 도장 쾅(크게 → 제자리)")
	local tabButton = findNamed(tabs, "Tab" .. target.Id)
	local stampedOk, stampedNote = tabLooksRight(target.Id)
	check(
		tabButton:GetAttribute("Selected") == true and stampedOk,
		"그 대륙 탭 = 고름 + 막대 대신 체크 (" .. stampedNote .. ")"
	)
	Panels.close()
	openMenu("Collection")
	local _, afterStamp = Panels.current()
	check(afterStamp == "All", "알림으로 한 번 연 뒤에는 다시 [전체]부터")
	Panels.close()

	-- 알림을 안 눌러도(게임패드 · 놓침): 도장을 받은 뒤 처음 도감을 열면 그 대륙 탭으로 한 번 + 도장 쾅, 알림은 치움
	complete(second.Id)
	refresh()
	check(#stampToasts(second.Id) == 1, second.Id .. " 도장 알림")
	openMenu("Collection")
	local _, pendingTab = Panels.current()
	local secondHeader = findNamed(findNamed(window, "CollectionHeader"), second.Id)
	check(
		pendingTab == second.Id and findNamed(secondHeader, "Slam") ~= nil,
		"도장 받은 뒤 처음 연 도감 = " .. second.Id .. " 탭 + 도장 쾅 (" .. tostring(pendingTab) .. ")"
	)
	Mock.runScheduler(Mock.clock() + 0.3)
	check(#stampToasts(nil) == 0, "메뉴로 도감을 열어도 도장 알림 치움")
	openMenu("Collection") -- 닫기
	openMenu("Collection")
	local _, onceTab = Panels.current()
	check(onceTab == "All", "그 탭으로는 한 번만(다음엔 [전체])")

	-- 도감이 열려 있을 때 받으면: 알림 없이(탭 줄·리본을 가리지 않게) 그 대륙 탭 체크가 톡, 보던 탭은 그대로
	complete(third.Id)
	refresh()
	local _, stayTab = Panels.current()
	local pop = findNamed(findNamed(tabs, "Tab" .. third.Id), "Pop")
	check(#stampToasts(nil) == 0, "도감이 열려 있으면 도장 알림 없음 (" .. #stampToasts(nil) .. "개)")
	check(
		pop ~= nil and pop.Scale == 1 and stayTab == "All",
		third.Id .. " 탭 체크가 톡(보던 [전체] 탭 그대로)"
	)
	check(
		badgeText(findNamed(menu, "Collection"), "Stamps") == string.format("%d/%d", stamps + 3, #Landmarks.Regions),
		"도감 버튼 배지 = 도장 3개 더"
	)
	Panels.close()
	openMenu("Collection")
	local _, noPending = Panels.current()
	check(noPending == "All", "열려 있을 때 받은 도장은 다음 열기에 끌고 가지 않음")
	Panels.close()

	for _, id in added do
		data.Discovered[id] = nil
	end
	refresh()
	check(#stampToasts(nil) == 0, "도장이 줄어도 알림 없음")
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
		Hud.relayout() -- 자리 다시 잡기(가짜 환경은 AbsoluteSize 바뀜 이벤트가 없음)
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
		Hud.relayout()
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
		Hud.relayout()
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

print(
	"\n[수입 보이기: 이름표 수입 알약 · 간판 합 · 별 오르면 톡 · 동전 퐁(돌려 씀·상한) · 내 공원 → 코인 알약]"
)
do
	local IncomeFx = Harness.require(client.IncomeFx)
	local Panels = Harness.require(client.Panels)
	local Format = Harness.require(E.shared.Format)
	ParkEdit.exit()
	Panels.close()
	Mock.runScheduler(Mock.clock() + 0.5)
	-- 꽉 찬 큰 공원(36칸, 희귀한 명소 많음 = 퐁이 자주 → 상한이 걸림)
	data.Upgrades.Park = 10
	data.Upgrades.Ticket = 2
	for index, landmark in Landmarks.RarestFirst do
		if index > 40 then
			break
		end
		data.Inventory[landmark.Id] = math.max(data.Inventory[landmark.Id] or 0, index % 5 + 1)
		data.Discovered[landmark.Id] = true
	end
	PlayerState.setSetting(data, "AutoPark", true)
	mods.Passes.DoubleIncome = nil
	local function pushServer()
		ParkService.update(serverPlayer, data, mods)
		remoteFolder:FindFirstChild("State").OnClientEvent:Fire(snap())
		Mock.runScheduler(Mock.clock() + 0.1)
	end
	pushServer()
	root.CFrame = origin * CFrame.new(0, 3.6, -37) -- 내 공원 입구 안쪽
	camera.CameraType = Enum.CameraType.Custom
	camera.FieldOfView = 70
	lookIntoPark()
	Mock.runScheduler(Mock.clock() + 0.5)

	local function incomeText(n: number): string
		if n < 100 then
			return "+" .. string.format("%.1f", math.floor(n * 10) / 10):gsub("%.0$", "") .. "/s"
		end
		return "+" .. Format.short(n) .. "/s"
	end
	local function container(slot: number): any
		for _, c in slotsFolder:GetChildren() do
			if c:GetAttribute("Slot") == slot then
				return c
			end
		end
		return nil
	end
	local function checkTags(what: string)
		local incomes = PlayerState.slotIncomes(data, mods)
		local slots, unlocked = PlayerState.parkSlots(data)
		local ok, sum, count = true, 0, 0
		for slot = 1, unlocked do
			if slots[slot] then
				local c = container(slot)
				local amount = findNamed(c, "Amount")
				local want = incomeText(incomes[slot])
				if not amount or amount.Text ~= want or IncomeFx.statueIncome(c) ~= c:GetAttribute("Income") then
					ok = false
					print("    칸", slot, amount and amount.Text, want, IncomeFx.statueIncome(c))
				end
				sum += c:GetAttribute("Income")
				count += 1
			end
		end
		check(
			ok and count == unlocked,
			what .. ": 전시 명소 " .. count .. "개 이름표 = [동전] +N/s (명소 수입 × 배율)"
		)
		local hudText = findNamed(findNamed(gui, "Stats"), "Income"):FindFirstChild("Label", true).Text
		local total = PlayerState.incomePerSecond(data, mods)
		check(
			math.abs(sum - total) <= 1e-9 * math.max(1, total) and hudText == incomeText(total),
			string.format("%s: 이름표 합 = HUD %s", what, hudText)
		)
		local sign = findNamed(plot:FindFirstChild("Sign"), "Income")
		check(sign and sign.Text == incomeText(total), what .. ": 입구 간판 = 합 " .. tostring(sign and sign.Text))
	end
	checkTags("처음")

	-- 별이 오름: 그 칸 수입·글자가 오르고 이름표가 잠깐 커짐(UIScale "Pop")
	local starContainer = container(3)
	local starId = starContainer:GetAttribute("Look")
	local pop = findNamed(starContainer, "Pop")
	local beforeIncome = starContainer:GetAttribute("Income")
	check(pop ~= nil and pop:IsA("UIScale"), "이름표 몸통 UIScale Pop")
	pop.Scale = 1 -- (가짜 트윈은 끝 값에 멈춤 — 앞선 별 상승이 남긴 값을 되돌림)
	data.Inventory[starId] += 1 -- 또 뽑음 = ★+1
	pushServer()
	check(starContainer:GetAttribute("Income") > beforeIncome, "별 +1 = 그 칸 수입 오름")
	check(pop.Scale > 1.2, "별 +1 = 이름표가 톡 커짐(" .. pop.Scale .. ")")
	checkTags("별 +1")
	-- 입장료 업그레이드 · 수입 2배 게임패스
	data.Upgrades.Ticket = 5
	pushServer()
	checkTags("입장료 5")
	mods.Passes.DoubleIncome = true
	pushServer()
	checkTags("수입 2배")

	-- 동전 퐁: 공원을 보고 30초 — 돌려 쓰는 빌보드, 초당 10개 상한, 인스턴스가 늘지 않음
	local fxFolder = workspace:FindFirstChild("IncomeFx")
	local flyGui = playerGui:FindFirstChild("IncomeFx")
	check(fxFolder ~= nil and flyGui ~= nil, "IncomeFx 폴더(퐁 빌보드) + ScreenGui(날아가는 동전)")
	check(
		(flyGui.DisplayOrder or 0) > (gui.DisplayOrder or 0) and flyGui.DisplayOrder < 5,
		"날아가는 동전은 HUD 바로 위 층, 번쩍임(5) 아래 (DisplayOrder "
			.. tostring(flyGui.DisplayOrder)
			.. ")"
	)
	-- 퐁 금액 글자: 10 미만 소수 한 자리, 그 위 정수, 1000 부터 짧게
	check(
		IncomeFx.amountText(74.2) == "74"
			and IncomeFx.amountText(7.46) == "7.5"
			and IncomeFx.amountText(3) == "3"
			and IncomeFx.amountText(999.4) == "999"
			and IncomeFx.amountText(1234) == "1.2K",
		"퐁 금액 = 정수(10 미만만 소수 한 자리, 1000 부터 1.2K)"
	)
	-- 퐁 동전은 정사각(RelativeYY = 두 값 모두 높이 비율, 늘이지 않고 맞춤)
	local squareCoins = true
	for _, d in fxFolder:GetDescendants() do
		if d.Name == "Coin" then
			squareCoins = squareCoins
				and d.SizeConstraint == Enum.SizeConstraint.RelativeYY
				and d.Size.X.Scale == d.Size.Y.Scale
				and d.Size.X.Offset == d.Size.Y.Offset
				and d.ScaleType == Enum.ScaleType.Fit
		end
	end
	check(squareCoins, "퐁 동전 정사각(RelativeYY 0.9 × 0.9, Fit)")
	local startStats = IncomeFx.stats()
	local instancesBefore = #fxFolder:GetDescendants() + #flyGui:GetDescendants()
	local maxPops, maxFlights = 0, 0
	local bumpScale = 0
	local bump = findNamed(findNamed(gui, "Stats"), "Bump")
	check(
		bump and bump.Parent and bump.Parent.Name == "Icon" and bump.Parent.AnchorPoint == Vector2.new(0.5, 0.5),
		"코인 알약 톡은 동전 아이콘(가운데 기준)에"
	)
	bump.Scale = 1
	-- 퐁 자리: 모형 가장자리(± 4.5 스터드)에서 바깥쪽으로(몸통이 바깥쪽 절반), 퐁 위 끝 ≤ 모형 꼭대기 - 0.2
	local placedPops, badSide, badTop = 0, 0, 0
	local sinkScale, sinkFade = math.huge, 0
	local eyeRight = camera.CFrame.RightVector
	local SECONDS = 30
	for _ = 1, SECONDS * 30 do
		frame(1 / 30)
		local stats = IncomeFx.stats()
		maxPops = math.max(maxPops, stats.Pops)
		maxFlights = math.max(maxFlights, stats.Flights)
		bumpScale = math.max(bumpScale, bump.Scale)
		for _, g in fxFolder:GetChildren() do
			local pedestal = g.Enabled and g.Adornee
			if pedestal then
				placedPops += 1
				local offset = g.StudsOffsetWorldSpace
				local flat = Vector3.new(offset.X, 0, offset.Z)
				local outward = flat:Dot(Vector3.new(eyeRight.X, 0, eyeRight.Z))
				local body = g:FindFirstChild("Body")
				if
					math.abs(flat.Magnitude - ParkGrid.MINIATURE_SIZE / 2) > 1e-3
					or body.Position.X.Scale ~= (if outward > 0 then 0.75 else 0.25)
				then
					badSide += 1
				end
				local distance = (pedestal.Position - camera.CFrame.Position).Magnitude
				local perStud = camera.ViewportSize.Y
					/ (2 * math.tan(math.rad(camera.FieldOfView) / 2) * math.max(distance, 1))
				local top = pedestal.Parent:GetAttribute("Top") or 4
				local popTop = offset.Y + g.Size.Y.Offset / perStud / 2
				if popTop > ParkGrid.PEDESTAL_HEIGHT / 2 + top - 0.2 + 1e-3 then
					badTop += 1
				end
			end
		end
		for _, sprite in flyGui:GetChildren() do
			if sprite:IsA("GuiObject") and sprite.Visible then
				local scale = sprite:FindFirstChildOfClass("UIScale")
				local fade = if sprite.Image ~= "" then sprite.ImageTransparency else sprite.BackgroundTransparency
				if fade > 0.3 then
					sinkFade = math.max(sinkFade, fade)
					sinkScale = math.min(sinkScale, scale.Scale)
				end
			end
		end
	end
	check(
		placedPops > 100 and badSide == 0,
		string.format("퐁은 모형 가장자리에서 바깥쪽으로 (%d번 봄, 어긋남 %d)", placedPops, badSide)
	)
	check(
		badTop == 0,
		"퐁 위 끝 ≤ 모형 꼭대기 - 0.2(이름표·수입 알약을 안 가림) — 넘은 적 " .. badTop
	)
	check(
		sinkFade > 0.5 and sinkScale < 0.7,
		string.format("동전은 코인 아이콘 속으로 작아지며(%.2f배) 흐려짐(%.2f)", sinkScale, sinkFade)
	)
	local stats = IncomeFx.stats()
	local spawned = stats.PopsSpawned - startStats.PopsSpawned
	check(stats.Statues >= 36, "따라가는 전시 명소 " .. stats.Statues .. "개")
	check(spawned > 60, "동전 퐁이 뜸 (" .. spawned .. "개 / " .. SECONDS .. "초)")
	check(
		spawned <= SECONDS * 10 + 6,
		string.format(
			"초당 10개 상한 (%.1f/초, 건너뜀 %d)",
			spawned / SECONDS,
			stats.PopsSkipped - startStats.PopsSkipped
		)
	)
	check(maxPops <= 14, "동시에 보이는 퐁 ≤ 빌보드 14개 (" .. maxPops .. ")")
	-- 공원 36칸이 모두 가까이 보이게(바로 위에서 넓게): 퐁이 초당 10개를 넘으려 해도 상한에서 멈추고 나머지는 건너뜀
	do
		local center = origin.Position + Vector3.new(0, ParkGrid.BASE_TOP, 0)
		local savedFov = camera.FieldOfView
		camera.FieldOfView = 100
		camera.CFrame = CFrame.lookAt(center + Vector3.new(0, 40, -1), center)
		local capStart = IncomeFx.stats()
		local capMax = 0
		local CAP_SECONDS = 20
		for _ = 1, CAP_SECONDS * 30 do
			frame(1 / 30)
			capMax = math.max(capMax, IncomeFx.stats().Pops)
		end
		local capStats = IncomeFx.stats()
		local capSpawned = capStats.PopsSpawned - capStart.PopsSpawned
		check(
			capSpawned <= CAP_SECONDS * 10 + 6 and capSpawned >= CAP_SECONDS * 8,
			string.format("많이 보여도 초당 10개 상한 (%.1f/초)", capSpawned / CAP_SECONDS)
		)
		check(
			capStats.PopsSkipped > capStart.PopsSkipped,
			"상한에 걸린 퐁은 건너뜀 (" .. (capStats.PopsSkipped - capStart.PopsSkipped) .. "번)"
		)
		check(capMax <= 14, "동시에 보이는 퐁 ≤ 빌보드 14개 (" .. capMax .. ")")
		-- 남의 공원 몫: 같은 36칸이 "남의 공원"이면(내 부지를 빈 부지로 바꿔 끼움) 초당 4개까지 — 내 퐁 몫 6개가 남음.
		-- 상한에 걸려 건너뛰어도 퐁 금액은 그 사이 번 돈(보이는 명소 수입 × 시간과 거의 같음)
		local emptyPlot = nil
		for _, model in workspace.Parks:GetChildren() do
			if model ~= plot and model:GetAttribute("OwnerUserId") == nil then
				emptyPlot = model
			end
		end
		IncomeFx.setPlot(emptyPlot)
		for _ = 1, 3 * 30 do
			frame(1 / 30)
		end
		local eye = camera.CFrame.Position
		local visibleIncome = 0
		for _, c in slotsFolder:GetChildren() do
			local pedestal = c:FindFirstChild("Pedestal")
			local income = c:GetAttribute("Income")
			if pedestal and type(income) == "number" then
				local _, inside =
					camera:WorldToViewportPoint(pedestal.Position + Vector3.new(0, ParkGrid.PEDESTAL_HEIGHT / 2 + 2, 0))
				if inside and (pedestal.Position - eye).Magnitude <= 70 then
					visibleIncome += income
				end
			end
		end
		local otherStart = IncomeFx.stats()
		local OTHER_SECONDS = 40
		for _ = 1, OTHER_SECONDS * 30 do
			frame(1 / 30)
		end
		local otherStats = IncomeFx.stats()
		local otherSpawned = otherStats.PopsSpawned - otherStart.PopsSpawned
		check(
			otherSpawned <= OTHER_SECONDS * 4 + 3
				and otherSpawned >= OTHER_SECONDS * 3
				and otherStats.PopsMine == otherStart.PopsMine,
			string.format(
				"남의 공원 퐁은 초당 4개까지(%.1f/초) — 내 몫 6개는 남음",
				otherSpawned / OTHER_SECONDS
			)
		)
		local shownAmount = otherStats.PopAmount - otherStart.PopAmount
		local ratio = shownAmount / (visibleIncome * OTHER_SECONDS)
		check(
			otherStats.PopsSkipped > otherStart.PopsSkipped and ratio > 0.85 and ratio < 1.15,
			string.format(
				"상한에 걸려 건너뛰어도 퐁 금액 합 = 번 돈 × %.2f (건너뜀 %d, 가려짐 %d)",
				ratio,
				otherStats.PopsSkipped - otherStart.PopsSkipped,
				otherStats.PopsHidden - otherStart.PopsHidden
			)
		)
		IncomeFx.setPlot(plot)
		camera.FieldOfView = savedFov
		lookIntoPark()
	end
	-- 가려진 명소(벽 뒤)는 퐁 없음(광선 하나 — 퐁이 벽·간판 위에 그려지지 않게)
	do
		local wall = Instance.new("Part")
		wall.Name = "SmokeWall"
		wall.Anchored = true
		wall.Size = Vector3.new(400, 400, 1)
		wall.CFrame = camera.CFrame * CFrame.new(0, 0, -6)
		wall.Parent = workspace
		for _ = 1, 30 do
			frame(1 / 30)
		end
		local wallStart = IncomeFx.stats()
		for _ = 1, 5 * 30 do
			frame(1 / 30)
		end
		local wallStats = IncomeFx.stats()
		check(
			wallStats.PopsSpawned == wallStart.PopsSpawned and wallStats.PopsHidden > wallStart.PopsHidden,
			"벽에 가려진 명소는 퐁 없음 (가려짐 "
				.. (wallStats.PopsHidden - wallStart.PopsHidden)
				.. "번)"
		)
		wall:Destroy()
		frame(1 / 30)
	end
	-- 이름표 거리 단계: 멀면(30 스터드 넘게) 이름·별(Head)을 끄고 수입 알약만, 가까이 오면 다시 켬
	do
		local function head(slot: number): any
			return findNamed(container(slot), "Head")
		end
		for _ = 1, 10 do
			frame(1 / 30)
		end
		local far, nearShown = 0, true
		for _, c in slotsFolder:GetChildren() do
			local h = findNamed(c, "Head")
			local pedestal = c:FindFirstChild("Pedestal")
			local tagAt = pedestal
				and pedestal.Position
					+ Vector3.new(0, ParkGrid.PEDESTAL_HEIGHT / 2 + (c:GetAttribute("Top") or 4), 0)
			if h and tagAt and (tagAt - camera.CFrame.Position).Magnitude > 31 then
				if h.Visible then
					nearShown = false
				else
					far += 1
				end
			end
		end
		local pill = findNamed(container(1), "Income")
		check(
			far > 0 and nearShown and pill and pill.Visible,
			"먼 이름표는 이름·별을 끄고 수입 알약만 (" .. far .. "개)"
		)
		local pedestal = container(1):FindFirstChild("Pedestal")
		camera.CFrame = CFrame.lookAt(pedestal.Position + Vector3.new(0, 8, -14), pedestal.Position)
		for _ = 1, 10 do
			frame(1 / 30)
		end
		check(head(1).Visible, "가까이 오면 이름·별 다시 켬")
		lookIntoPark()
		for _ = 1, 10 do
			frame(1 / 30)
		end
		check(not head(1).Visible, "멀어지면 다시 끔")
	end
	local popTexts = 0
	for _, d in fxFolder:GetDescendants() do
		if
			d.Name == "Amount"
			and (d.Text:match("^%+%d+$") or d.Text:match("^%+%d%.%d$") or d.Text:match("^%+[%d%.]+[KMBT]$"))
		then
			popTexts += 1
		end
	end
	check(popTexts > 0, '퐁 글자 = "+N"(아이콘 + 숫자)')
	local instancesAfter = #fxFolder:GetDescendants() + #flyGui:GetDescendants()
	check(
		instancesAfter == instancesBefore and stats.Instances == instancesBefore,
		"30초 뒤에도 인스턴스 수 그대로 (" .. instancesBefore .. " -> " .. instancesAfter .. ")"
	)
	-- 내 공원이 화면에 있으면: 몰아서 날아가는 동전 + 닿으면 코인 알약 톡
	local bursts = stats.Bursts - startStats.Bursts
	check(bursts >= 15, "내 공원이 보이면 약 1.6초마다 동전을 날림 (" .. bursts .. "번)")
	check(
		maxFlights >= 2 and maxFlights <= 10,
		"한 번에 날아가는 동전 2~5개(풀 10) — 최대 " .. maxFlights
	)
	check(bumpScale > 1.2, "동전이 닿으면 코인 아이콘이 톡 (" .. bumpScale .. ")")
	local landed = stats.FlightsLanded - startStats.FlightsLanded
	check(
		landed >= 2 * bursts,
		"동전마다 닿음(닿을 때마다 톡 — " .. landed .. "개 / " .. bursts .. "번)"
	)
	local activeInput = false
	for _, d in flyGui:GetDescendants() do
		if d:IsA("GuiObject") and d.Active then
			activeInput = true
		end
	end
	check(not activeInput, "날아가는 동전은 입력을 막지 않음(Active 없음)")

	-- 내 공원이 화면에 없으면(하늘을 봄) 날리지 않음
	camera.CFrame = CFrame.lookAt(root.Position + Vector3.new(0, 5, 0), root.Position + Vector3.new(0, 60, 5))
	for _ = 1, 30 do
		frame(1 / 30) -- 날던 동전은 마저 닿음
	end
	local awayStart = IncomeFx.stats()
	for _ = 1, 8 * 30 do
		frame(1 / 30)
	end
	local away = IncomeFx.stats()
	check(away.Bursts == awayStart.Bursts, "내 공원이 화면에 없으면 동전을 안 날림")
	check(away.PopsSpawned == awayStart.PopsSpawned, "화면 밖 명소는 퐁 없음")

	-- 창이 열림: 날아가는 동전을 쉬고 날던 것도 치움(월드 퐁은 창 아래라 그대로)
	lookIntoPark()
	for _ = 1, 2 * 30 do
		frame(1 / 30)
	end
	Panels.open("Collection")
	frame(1 / 30)
	check(IncomeFx.stats().Flights == 0, "창을 열면 날던 동전을 바로 치움")
	local panelStart = IncomeFx.stats()
	for _ = 1, 5 * 30 do
		frame(1 / 30)
	end
	check(IncomeFx.stats().Bursts == panelStart.Bursts, "창이 열려 있으면 동전을 안 날림")
	Panels.close()

	-- 배치 모드: 퐁·날리기 모두 쉼, 배치 모드 입력은 그대로
	E.tap(parkTap)
	Mock.runScheduler(Mock.clock() + 2)
	check(ParkEdit.isEditing(), "배치 모드")
	frame(1 / 30)
	local editStart = IncomeFx.stats()
	check(editStart.Pops == 0 and editStart.Flights == 0, "배치 모드에 들어가면 퐁·동전을 바로 치움")
	for _ = 1, 5 * 30 do
		frame(1 / 30)
	end
	local editStats = IncomeFx.stats()
	check(
		editStats.PopsSpawned == editStart.PopsSpawned and editStats.Bursts == editStart.Bursts,
		"배치 모드 동안 퐁·동전 없음(위에서 보기 화면을 가리지 않음)"
	)
	local shown = 0
	for _, d in fxFolder:GetDescendants() do
		if d:IsA("BillboardGui") and d.Enabled then
			shown += 1
		end
	end
	for _, d in flyGui:GetChildren() do
		if d:IsA("GuiObject") and d.Visible then
			shown += 1
		end
	end
	check(shown == 0, "배치 모드: 보이는 효과 없음 (" .. shown .. ")")
	if workspace:FindFirstChild("ParkEditLocal"):FindFirstChild("Held", true) then
		key("Escape")
		settle()
	end
	click(slotScreen(1, 2))
	check(
		workspace:FindFirstChild("ParkEditLocal"):FindFirstChild("Held", true) ~= nil,
		"효과가 돌아도 배치 모드 누르기는 그대로(집음)"
	)
	key("Escape")
	settle()
	ParkEdit.exit()
	mods.Passes.DoubleIncome = nil
end

print("\n[모듈 오류]")
E.finish()
