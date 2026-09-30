-- 3D 공원 배치 모드(src/client/ParkEdit.luau) 스모크 테스트: 가짜 환경에서 진짜 ParkService 부지 + ParkEdit 를 돌려
-- 들어가기 · 집기 · 옮기기 · 자리 바꾸기 · 보관함 · 보관 · stale · 서버가 늦을 때 · 터치 · 시점 · 나가기(Esc·죽음·부지 밖)를 확인.
-- 서버 원격은 바로 PlayerState + ParkService 로 흉내. 끝에 HUD/도감 [배치] 버튼 연결도 봄.
-- 실행(roblox-rng 폴더에서): luaurun tools/client_smoke/parkedit.luau   (약 5초, 끝 줄 "0 failed")

local E = compile(readfile("tools/client_smoke/env.luau"), "tools/client_smoke/env.luau")()
local Harness, Mock, UIS, camera, INSET = E.Harness, E.Mock, E.UIS, E.camera, E.INSET
local playerGui, root, humanoid = E.playerGui, E.root, E.humanoid
local client = E.client
local PlayerState, Landmarks, ParkGrid, ParkService = E.PlayerState, E.Landmarks, E.ParkGrid, E.ParkService
local serverPlayer, plot, origin, slotsFolder = E.serverPlayer, E.plot, E.origin, E.slotsFolder
local data = E.data
local unlocked = PlayerState.slots(data)
local Config = Harness.require(E.shared.Config)
local check, frame, waitReal, settle, slotScreen, input = E.check, E.frame, E.waitReal, E.settle, E.slotScreen, E.input
local mouseTo, click, drag, key, touchDrag, face = E.mouseTo, E.click, E.drag, E.key, E.touchDrag, E.face
local tap = E.tap

print("[부지]")
check(typeof(origin) == "CFrame", "부지 Origin 속성")
check(#slotsFolder:GetChildren() == PlayerState.MAX_SLOTS, "칸 모델 36개(잠긴 칸 포함)")

-- 캐릭터를 부지 입구 안쪽에
local function placeCharacter(cf: CFrame)
	root.CFrame = cf
end
placeCharacter(origin * CFrame.new(0, 3.6, -37))

-- 3) 클라이언트 ------------------------------------------------------------------------
local ParkEdit = Harness.require(client.ParkEdit)
local gui = Instance.new("ScreenGui")
gui.Name = "LandmarkRNG"
gui.AbsoluteSize = Vector2.new(1280, 684)
gui.Parent = playerGui

local revision = 0
local toasts: { string } = {}
local changes: { boolean } = {}
local requests: { string } = {}
local function pushState()
	revision += 1
	local snapshot = PlayerState.snapshot(data, revision)
	ParkEdit.render(snapshot)
	return snapshot
end

local handlers = {
	SetDisplay = function(slot, id, expected, from)
		table.insert(requests, string.format("%d %s %s %s", slot, tostring(id), tostring(expected), tostring(from)))
		local done, reason = PlayerState.setDisplay(data, slot, id, expected, from)
		if done then
			ParkService.update(serverPlayer, data)
		end
		pushState()
		return done, reason == "stale"
	end,
	SetAutoPark = function(on)
		table.insert(requests, "auto " .. tostring(on))
		local done = PlayerState.setSetting(data, "AutoPark", on)
		ParkService.update(serverPlayer, data)
		pushState()
		return done
	end,
	GoToPark = function()
		placeCharacter(origin * CFrame.new(0, 3.6, -37))
		return true
	end,
	Toast = function(text)
		table.insert(toasts, text)
	end,
	Changed = function(editing)
		table.insert(changes, editing)
	end,
}
ParkEdit.init(gui, handlers)
pushState()
ParkEdit.setPlot(plot)

local function container(slot: number)
	for _, child in slotsFolder:GetChildren() do
		if child:GetAttribute("Slot") == slot then
			return child
		end
	end
	return nil
end
local function look(slot: number): string
	return container(slot):GetAttribute("Look")
end
local function localFolder()
	return workspace:FindFirstChild("ParkEditLocal")
end
local function holding(): boolean
	local folder = localFolder()
	return folder ~= nil and folder:FindFirstChild("Held", true) ~= nil
end
-- 내 칸 모델에만 광선(숨김·투명도 상관없이 — 가짜 광선은 파트 상자만 봄): 화면 점이 처음 맞는 것
local function castFirst(at: Vector2): Instance?
	local ray = camera:ViewportPointToRay(at.X, at.Y)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { slotsFolder }
	local hit = workspace:Raycast(ray.Origin, ray.Direction * 1000, params)
	return hit and hit.Instance
end
-- 화면 점에서 부지 바닥 높이 평면이 가리키는 칸(ParkEdit 가 광선이 안 맞을 때 쓰는 것과 같음)
local function groundSlot(at: Vector2): number?
	local ray = camera:ViewportPointToRay(at.X, at.Y)
	if ray.Direction.Y >= 0 then
		return nil
	end
	local t = (origin.Position.Y + ParkGrid.BASE_TOP - ray.Origin.Y) / ray.Direction.Y
	local p = origin:PointToObjectSpace(ray.Origin + ray.Direction * t)
	return ParkGrid.slotAt(p.X, p.Z)
end
local function detectorCount(): number
	local count = 0
	for _, child in slotsFolder:GetChildren() do
		if child:FindFirstChild("ParkClick") then
			count += 1
		end
	end
	return count
end
local function handlerCount(): number
	return #UIS.InputBegan.Handlers + #UIS.InputChanged.Handlers + #UIS.InputEnded.Handlers
end
local function hiddenModel(slot: number): boolean
	local c = container(slot)
	for _, child in c:GetChildren() do
		if child:IsA("Model") then
			for _, part in child:GetDescendants() do
				if part:IsA("BasePart") then
					return part.LocalTransparencyModifier == 1
				end
			end
		end
	end
	return false
end
-- 칸 이름표(받침대의 BillboardGui)가 켜져 있는지. 이름표가 없는 칸(빈 칸·잠긴 칸)은 nil
local function labelOn(slot: number): boolean?
	for _, d in container(slot):GetDescendants() do
		if d:IsA("BillboardGui") then
			return d.Enabled ~= false
		end
	end
	return nil
end
local function labelsOn(): number
	local count = 0
	for slot = 1, PlayerState.MAX_SLOTS do
		if labelOn(slot) then
			count += 1
		end
	end
	return count
end
local function shownSlots(): { [number]: string }
	return (PlayerState.parkSlots(data))
end
local function dump(): string
	local slots = shownSlots()
	local out = {}
	for slot = 1, unlocked do
		table.insert(out, slots[slot] or "-")
	end
	return table.concat(out, ",")
end

print("\n[배치 모드 밖]")
Mock.runScheduler(1)
check(detectorCount() == unlocked, "열린 칸마다 ClickDetector (" .. detectorCount() .. ")")
check(not ParkEdit.isEditing(), "처음엔 배치 모드 아님")

print("\n[들어가기]")
local baseHandlers = handlerCount()
local cameraBefore = camera.CFrame
ParkEdit.enter(nil)
Mock.runScheduler(0.1)
check(ParkEdit.isEditing(), "배치 모드 켜짐")
check(changes[#changes] == true, "Changed(true)")
check(camera.CameraType == Enum.CameraType.Scriptable, "Scriptable 카메라")
local flyIn = E.cameraTweens[1]
check(
	flyIn ~= nil and flyIn.From == cameraBefore and (flyIn.To.Position - cameraBefore.Position).Magnitude > 5,
	"카메라가 원래 자리에서 위에서 보기로 날아감(들어갈 때 순간 이동 없음)"
)
check(localFolder() ~= nil, "로컬 폴더(빛나는 판·강조)")
local function signHidden(): boolean
	local sign = plot:FindFirstChild("Sign")
	for _, d in sign:GetDescendants() do
		if d:IsA("BasePart") and d.LocalTransparencyModifier ~= 1 then
			return false
		elseif d:IsA("SurfaceGui") and d.Enabled ~= false then
			return false
		end
	end
	return true
end
check(
	plot:FindFirstChild("Sign") ~= nil and signHidden(),
	"입구 간판은 이 화면에서만 숨김(띠 위로 삐져나오지 않게)"
)
check(detectorCount() == 0, "배치 모드 동안 ClickDetector 없음")
local barFrame = gui:FindFirstChild("ParkEditBar")
check(barFrame and barFrame.Visible, "아래 띠 보임")
-- 카메라가 맞출 줄(열린 줄 + 잠긴 줄 하나)을 모두 화면 안(상단바 아래 ~ 띠 위)에 담는지
local rows = ParkGrid.topRows(unlocked)
local allInside = true
local lowest, highest = math.huge, -math.huge
for slot = 1, rows * Config.PARK_GRID do
	local p = slotScreen(slot)
	lowest, highest = math.min(lowest, p.Y), math.max(highest, p.Y)
	if p.X < 0 or p.X > 1280 or p.Y < 36 or p.Y > 720 - 12 - 162 * 0.9 then
		allInside = false
		print("    화면 밖 칸", slot, p)
	end
end
check(allInside, string.format("위에서 보기: 앞 %d줄이 화면 안(세로 %.0f~%.0f px)", rows, lowest, highest))
check(highest - lowest > 250, "화면을 넉넉히 씀(명소가 작지 않게)")
local tray = barFrame:FindFirstChild("Tray")
tray.__props.AbsolutePosition = Vector2.new(109, 684 - 12 - 132 * 0.9)
tray.__props.AbsoluteSize = Vector2.new(1062, 132 * 0.9)

print("\n[집어서 빈 칸으로 옮기기]")
local before = shownSlots()
local firstId = before[1]
-- 빈 칸 만들기: 자동 배치라 12칸이 꽉 참 -> 먼저 보관(Delete)으로 하나 비움
click(slotScreen(unlocked))
check(localFolder():FindFirstChild("Held", true) ~= nil, "누르면 집음(노란 강조 복사본)")
check(hiddenModel(unlocked), "집은 칸의 원래 명소는 숨김")
key("Delete")
settle()
check(shownSlots()[unlocked] == nil, "Delete = 보관 (칸 " .. unlocked .. " 비움)")
check(table.find(toasts, "자동 꺼짐") ~= nil, "자동 배치 중 첫 편집 -> 자동 꺼짐 알림")
check(data.Settings.AutoPark == false, "서버 자동 배치 꺼짐")
check(look(unlocked) == ParkGrid.LOOK_EMPTY, "서버가 칸을 빈 받침대로 다시 만듦")
check(not hiddenModel(1), "다른 칸은 그대로 보임")

drag(slotScreen(1, 2), slotScreen(unlocked))
settle()
check(shownSlots()[unlocked] == firstId and shownSlots()[1] == nil, "끌어서 빈 칸으로 옮김: " .. dump())
check(
	requests[#requests] == string.format("%d %s  1", unlocked, firstId),
	"요청 = SetDisplay(칸, Id, '', 원래 칸) " .. tostring(requests[#requests])
)
check(
	#localFolder():GetChildren() == PlayerState.MAX_SLOTS + 1,
	"날아간 모형 정리됨(판 36 + 강조 1): " .. #localFolder():GetChildren()
)
check(not hiddenModel(unlocked), "옮긴 칸 서버 모형 보임")

print("\n[자리 바꾸기: 누르고 → 누르기]")
local a, b = shownSlots()[2], shownSlots()[3]
click(slotScreen(2, 2))
check(localFolder():FindFirstChild("Held", true) ~= nil, "눌러서 집음")
click(slotScreen(3))
settle()
check(shownSlots()[2] == b and shownSlots()[3] == a, "자리 바꿈: " .. dump())

print("\n[숨긴 원래 명소는 광선이 지나감: 그 뒤 받침대에 놓기]")
do
	-- 앞줄 명소 A 가 화면에서 바로 뒤 칸 B 의 받침대를 가리는 점(받침대 앞쪽부터)을 찾음
	local occA, occB, occAt = nil, nil, nil
	for a = 1, Config.PARK_GRID do
		local ax, az = ParkGrid.slotOffset(a)
		local b = ParkGrid.slotAt(ax, az + ParkGrid.SPACING)
		local statue = container(a):FindFirstChildWhichIsA("Model")
		if not occAt and b and b <= unlocked and shownSlots()[a] and shownSlots()[b] and statue then
			local bx, bz = ParkGrid.slotOffset(b)
			for j = -4, 4 do
				for i = -4, 4 do
					local top = ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT
					local at = E.toScreen(origin:PointToWorldSpace(Vector3.new(bx + i, top, bz + j)))
					local first = castFirst(at)
					if not occAt and first and first:IsDescendantOf(statue) then
						occA, occB, occAt = a, b, at
					end
				end
			end
		end
	end
	check(
		occAt ~= nil,
		"앞 명소가 뒤 칸 받침대를 가리는 화면 점 " .. tostring(occA) .. " -> " .. tostring(occB)
	)
	if occA and occB and occAt then
		local ia, ib = shownSlots()[occA], shownSlots()[occB]
		click(slotScreen(occA, 2))
		check(holding() and hiddenModel(occA), "앞 명소를 집음(원래 명소는 숨김)")
		click(occAt)
		settle()
		check(
			shownSlots()[occB] == ia and shownSlots()[occA] == ib,
			"안 보이는 원래 명소 너머 받침대를 누름 = 그 칸과 자리 바꿈(원래 칸으로 되돌아가지 않음): "
				.. dump()
		)
	end
end

print("\n[같은 칸 = 취소, 오른쪽 클릭 = 취소, 잠긴 칸 = 알림]")
local snapshotBefore = dump()
click(slotScreen(4, 2))
click(slotScreen(4))
settle()
check(
	localFolder():FindFirstChild("Held", true) == nil and dump() == snapshotBefore,
	"같은 칸 다시 누름 = 내려놓기"
)
click(slotScreen(4, 2))
local toastCount = #toasts
click(slotScreen(unlocked + 1))
check(toasts[#toasts] == "공원 확장" and #toasts == toastCount + 1, "잠긴 칸 = 공원 확장 알림")
check(localFolder():FindFirstChild("Held", true) ~= nil, "잠긴 칸에 놓아도 계속 들고 있음")
E.rightClick()
settle()
check(localFolder():FindFirstChild("Held", true) == nil and dump() == snapshotBefore, "오른쪽 클릭 = 내려놓기")
click(slotScreen(4, 2))
click(Vector2.new(20, 60)) -- 부지 밖(하늘/먼 바닥)
settle()
check(
	localFolder():FindFirstChild("Held", true) == nil and dump() == snapshotBefore,
	"부지 밖 누름 = 내려놓기"
)

print("\n[띠 위 딱지 줄: 비친 곳을 눌러도 뒤 명소를 안 집음]")
do
	local stripY = tray.AbsolutePosition.Y + INSET.Y - 10 -- 띠 위 딱지 줄(30 × 배율) 안
	local stripAt: Vector2? = nil
	for x = 120, 1160, 8 do
		local at = Vector2.new(x, stripY)
		local slot = groundSlot(at)
		if not stripAt and slot and shownSlots()[slot] then
			stripAt = at
		end
	end
	check(stripAt ~= nil, "딱지 줄 뒤가 명소 있는 앞줄 칸(바닥 평면)인 곳")
	if stripAt then
		local requestCount = #requests
		click(stripAt)
		check(not holding(), "마우스로 눌러도 안 집음")
		tap(stripAt)
		check(not holding(), "터치로 눌러도 안 집음")
		check(#requests == requestCount, "요청 없음")
		mouseTo(Vector2.new(20, 60))
	end
end

print("\n[채팅 입력 중: Esc · Q 는 무시]")
do
	click(slotScreen(4, 2))
	check(holding(), "들고 있음")
	E.focusText({ Name = "ChatBar", ClassName = "TextBox" })
	key("Escape")
	key("Q")
	check(
		holding() and ParkEdit.isEditing(),
		"채팅에 쓰는 중 Esc · Q = 그대로(내려놓지도 나가지도 않음)"
	)
	E.focusText(nil)
	key("Escape")
	check(
		holding() and ParkEdit.isEditing(),
		"채팅에서 빠져나온 바로 뒤 Esc(빠져나오는 키) = 그대로"
	)
	waitReal(0.3)
	key("Escape")
	settle()
	check(not holding() and ParkEdit.isEditing(), "채팅이 끝난 뒤 Esc = 내려놓기(배치 모드는 그대로)")
end

print("\n[보관함 카드 → 칸]")
local storage = ParkGrid.storage(PlayerState.snapshot(data, 0))
local scroller = tray:FindFirstChild("Storage")
local card = scroller and scroller:FindFirstChild(storage[1])
check(card ~= nil, "보관함 카드 (" .. tostring(storage[1]) .. ")")
local order = {}
for _, id in storage do
	local c = scroller:FindFirstChild(id)
	table.insert(order, if c then c.LayoutOrder else -1)
end
local sorted = true
for i = 2, #order do
	sorted = sorted and order[i] > order[i - 1]
end
check(sorted, "카드 순서 = 희귀한 순서")
card.Activated:Fire()
frame()
check(localFolder():FindFirstChild("Held", true) ~= nil, "카드 누름 = 집음")
local emptySlot = 0
for slot = 1, unlocked do
	if not shownSlots()[slot] then
		emptySlot = slot
	end
end
check(emptySlot > 0, "빈 칸 있음 " .. emptySlot)
click(slotScreen(emptySlot))
settle()
check(shownSlots()[emptySlot] == storage[1], "보관함에서 빈 칸에 놓음: " .. dump())
check(
	requests[#requests] == string.format("%d %s  0", emptySlot, storage[1]),
	"expectedFrom 0: " .. tostring(requests[#requests])
)
card = scroller:FindFirstChild(storage[2])
card.Activated:Fire()
frame()
local victim = shownSlots()[5]
click(slotScreen(5))
settle()
check(shownSlots()[5] == storage[2], "보관함에서 명소 칸에 바꿔 넣기")
check(scroller:FindFirstChild(victim) ~= nil, "밀려난 명소는 보관함 카드로")

print("\n[꽉 찬 공원: 보관함 카드 = 가장 약한 명소 칸 위에서 시작]")
do
	local full = true
	for slot = 1, unlocked do
		full = full and shownSlots()[slot] ~= nil
	end
	check(full, "공원 꽉 참")
	local snapshot = PlayerState.snapshot(data, 0)
	local startSlot = ParkGrid.storageStart(snapshot)
	local weakest, weakestSlot = math.huge, 0
	for slot = 1, unlocked do
		local id = shownSlots()[slot]
		local income = PlayerState.landmarkIncome(Landmarks.ById[id], data.Inventory[id] or 0)
		if income < weakest then
			weakest, weakestSlot = income, slot
		end
	end
	check(startSlot == weakestSlot, "시작 칸 = 수입이 가장 적은 전시 명소 칸 (" .. startSlot .. ")")
	tap(Vector2.new(20, 60)) -- 터치 기기처럼: 손가락을 떼면 가리키는 곳 없음
	local incoming = ParkGrid.storage(snapshot)[1]
	scroller:FindFirstChild(incoming).Activated:Fire()
	for _ = 1, 45 do
		frame(1 / 60)
	end
	local ghostModel = localFolder():FindFirstChild("Held", true).Parent
	local at = origin:PointToObjectSpace(ghostModel:GetPivot().Position)
	local sx, sz = ParkGrid.slotOffset(startSlot)
	check(math.abs(at.X - sx) < 0.3 and math.abs(at.Z - sz) < 0.3, "그 칸 위에 떠 있음")
	local statue = container(startSlot):FindFirstChildWhichIsA("Model")
	local statueTop = ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT + statue:GetExtentsSize().Y
	check(
		at.Y > statueTop + 0.5,
		string.format("그 명소 위로 떠서 겹치지 않음 (%.1f > %.1f)", at.Y, statueTop)
	)
	local screen = E.toScreen(ghostModel:GetPivot().Position)
	check(
		screen.X > 0 and screen.X < 1280 and screen.Y > INSET.Y and screen.Y < tray.AbsolutePosition.Y + INSET.Y,
		string.format("화면 안(띠 위) (%.0f, %.0f)", screen.X, screen.Y)
	)
	local hoverLight = localFolder():FindFirstChild("Hover")
	check(hoverLight.Enabled and hoverLight.Adornee == container(startSlot), "그 칸 강조(톡 = 바꿔 넣을 곳)")
	check(localFolder():FindFirstChild("Mark" .. startSlot).Transparency < 0.3, "그 칸 판이 진하게")
	local faint = 0
	for slot = 1, unlocked do
		if slot ~= startSlot and localFolder():FindFirstChild("Mark" .. slot).Transparency > 0.7 then
			faint += 1
		end
	end
	check(faint == 0, "보관함에서 들면 바꿔 넣을 칸 판도 또렷함 (흐린 판 " .. faint .. "개)")
	local weakId = shownSlots()[startSlot]
	tap(slotScreen(startSlot))
	settle()
	check(
		shownSlots()[startSlot] == incoming and scroller:FindFirstChild(weakId) ~= nil,
		"그 자리 톡 = 가장 약한 명소와 바꿔 넣기"
	)
	mouseTo(Vector2.new(20, 60))
end

print("\n[stale: 들고 있는 사이 서버에서 칸이 바뀜]")
click(slotScreen(6, 2))
local heldId = shownSlots()[6]
-- 서버만 바뀜(클라이언트는 아직 모름): 칸 7 과 8 자리 바꿈
local s7, s8 = shownSlots()[7], shownSlots()[8]
PlayerState.setDisplay(data, 7, s8)
ParkService.update(serverPlayer, data)
local staleBefore = dump()
click(slotScreen(7))
settle()
check(dump() == staleBefore, "stale 이면 서버 그대로: " .. dump())
local anyHidden = false
for slot = 1, unlocked do
	anyHidden = anyHidden or hiddenModel(slot)
end
check(not anyHidden, "stale 뒤 숨긴 명소 없음")
check(
	#localFolder():GetChildren() == PlayerState.MAX_SLOTS + 1,
	"stale 뒤 로컬 모형 정리: " .. #localFolder():GetChildren()
)

print("\n[서버가 칸을 다시 만드는 동안(ChildAdded/Removed)]")
click(slotScreen(9, 2))
PlayerState.setDisplay(data, 10, shownSlots()[11])
ParkService.update(serverPlayer, data)
pushState()
frame()
check(hiddenModel(9), "들고 있는 칸은 계속 숨김")
check(localFolder():FindFirstChild("Held", true) ~= nil, "계속 들고 있음")
key("Q")
settle()
check(localFolder():FindFirstChild("Held", true) == nil and not hiddenModel(9), "Q = 내려놓기")

print("\n[강조·따라가기·빛나는 판·이름표]")
mouseTo(slotScreen(4))
local hover = localFolder():FindFirstChild("Hover")
check(hover and hover.Adornee == container(4) and hover.Enabled, "가리키는 칸 강조")
check(labelsOn() == 0, "배치 모드: 칸 이름표(BillboardGui)는 모두 끔 (" .. labelsOn() .. "개)")
local tag = gui:FindFirstChild("ParkEditTag")
local function tagText(): string?
	local chip = tag and tag.Visible and tag:FindFirstChild("Name")
	local text = chip and chip:FindFirstChild("Label", true)
	return text and text.Text or nil
end
check(
	tagText() == Landmarks.ById[shownSlots()[4]].Name,
	"가리키는 명소 = 화면 이름표 (" .. tostring(tagText()) .. ")"
)
mouseTo(Vector2.new(20, 60))
check(hover.Adornee == nil or not hover.Enabled, "빈 곳 = 강조 없음")
check(tagText() == nil, "아무 칸도 안 가리키면 이름표 없음")
local heldId = shownSlots()[4]
click(slotScreen(4, 2))
local heldLight = localFolder():FindFirstChild("Held", true)
local ghost = heldLight.Parent
check(
	ghost:FindFirstChildWhichIsA("BillboardGui", true) == nil,
	"복사본에 BillboardGui 없음(화면 이름표로)"
)
mouseTo(slotScreen(6))
check(labelsOn() == 0, "들고 있어도 칸 이름표 없음")
for _ = 1, 90 do
	frame(1 / 60)
end
local x6, z6 = ParkGrid.slotOffset(6)
local ghostLocal = origin:PointToObjectSpace(ghost:GetPivot().Position)
check(
	math.abs(ghostLocal.X - x6) < 0.3 and math.abs(ghostLocal.Z - z6) < 0.3,
	"들고 있는 명소가 가리키는 칸 위로 붙음"
)
check(ghostLocal.Y > ParkGrid.BASE_TOP + 3, "떠 있음 (높이 " .. string.format("%.2f", ghostLocal.Y) .. ")")
if shownSlots()[6] then
	local statue = container(6):FindFirstChildWhichIsA("Model")
	local top = ParkGrid.BASE_TOP + ParkGrid.PEDESTAL_HEIGHT + statue:GetExtentsSize().Y
	check(
		ghostLocal.Y > top + 0.5,
		string.format("자리 바꿀 명소 위로 뜸 (%.1f > 꼭대기 %.1f)", ghostLocal.Y, top)
	)
end
check(hover.Adornee == container(6) and hover.OutlineColor == Color3.new(1, 1, 1), "놓을 칸 강조 = 흰 테두리")
check(
	tagText() == Landmarks.ById[heldId].Name,
	"들고 있으면 화면 이름표 = 든 명소 (" .. tostring(tagText()) .. ")"
)
-- 이름표 기준점(ParkEdit.tagAnchor)과 복사본은 같은 프레임 값이라 오르내림(진짜 시계)과 상관없이 늘 같은 결과:
-- 기준점이 복사본 꼭대기 바로 위이고, 이름표 자리는 그 점의 화면 자리(화면 안에 가둔 것)
do
	local anchor = ParkEdit.tagAnchor()
	local pivot = ghost:GetPivot().Position
	local ghostTop = pivot.Y + ghost:GetExtentsSize().Y
	check(
		anchor ~= nil
			and math.abs(anchor.X - pivot.X) < 1e-3
			and math.abs(anchor.Z - pivot.Z) < 1e-3
			and anchor.Y > ghostTop - 0.5
			and anchor.Y < ghostTop + 2.5,
		string.format(
			"이름표 기준점이 복사본 꼭대기 바로 위 (높이 %.2f, 꼭대기 %.2f)",
			anchor and anchor.Y or -1,
			ghostTop
		)
	)
	if anchor then
		local scale = Harness.require(client.Ui).scale()
		local half = tag.Size.X.Offset * scale / 2 + 6 -- ParkEdit TAG_EDGE
		local screen = E.toScreen(anchor)
		local wantX = math.clamp(screen.X - INSET.X, half, 1280 - half)
		local wantY = math.max(screen.Y - INSET.Y, tag.Size.Y.Offset * scale + 6)
		check(
			math.abs(tag.Position.X.Offset - wantX) < 0.5 and math.abs(tag.Position.Y.Offset - wantY) < 0.5,
			string.format(
				"이름표가 복사본 바로 위(화면 안에 가둠) (%.1f, %.1f) = (%.1f, %.1f)",
				tag.Position.X.Offset,
				tag.Position.Y.Offset,
				wantX,
				wantY
			)
		)
	end
end
local lockedMark = localFolder():FindFirstChild("Mark" .. (unlocked + 1))
local openMark = localFolder():FindFirstChild("Mark6")
check(lockedMark.Transparency < 1 and lockedMark.Transparency > 0.5, "잠긴 칸 판 = 흐린 빨강")
check(openMark.Transparency < 0.3, "가리키는 놓을 칸 판이 진하게 빛남")
local otherMarks = 0
for slot = 1, unlocked do
	local mark = localFolder():FindFirstChild("Mark" .. slot)
	if slot ~= 6 and slot ~= 4 and mark.Transparency < 0.5 then
		otherMarks += 1
	end
end
check(otherMarks == 0, "다른 놓을 칸 판은 은은하게 (진한 판 " .. otherMarks .. "개)")
mouseTo(Vector2.new(640, 700))
for _ = 1, 30 do
	frame(1 / 60)
end
ghostLocal = origin:PointToObjectSpace(ghost:GetPivot().Position)
check(
	math.abs(ghostLocal.Z) <= ParkGrid.PLOT_DEPTH / 2 + 0.01
		and math.abs(ghostLocal.X) <= ParkGrid.PLOT_WIDTH / 2 + 0.01,
	"부지 밖을 가리켜도 부지 안에 머묾"
)
key("Q")
settle()

-- 화면 가장자리: 이름표가 화면 안에 갇힘
mouseTo(slotScreen(unlocked + 5, 0))
for _ = 1, 60 do
	frame(1 / 60)
end
check(
	tag.Position.X.Offset >= 108 and tag.Position.X.Offset <= 1280 - 108 and tag.Position.Y.Offset >= 52,
	string.format("이름표는 화면 안 (%.0f, %.0f)", tag.Position.X.Offset, tag.Position.Y.Offset)
)

print("\n[서버가 늦을 때: 로컬 모형(proxy)]")
local slowUpdates = {}
local fastSetDisplay = handlers.SetDisplay
handlers.SetDisplay = function(slot, id, expected, from)
	local done, reason = PlayerState.setDisplay(data, slot, id, expected, from)
	pushState()
	if done then
		table.insert(slowUpdates, true)
		task.delay(1, function()
			ParkService.update(serverPlayer, data)
		end)
	end
	return done, reason == "stale"
end
local p4, p5 = shownSlots()[4], shownSlots()[5]
click(slotScreen(4, 2))
click(slotScreen(5))
settle()
check(shownSlots()[4] == p5 and shownSlots()[5] == p4, "서버 데이터는 바뀜")
check(look(4) == p4 and look(5) == p5, "(서버 칸 모델은 아직 옛 모습)")
check(hiddenModel(4) and hiddenModel(5), "옛 칸 명소 숨김")
check(
	#localFolder():GetChildren() == PlayerState.MAX_SLOTS + 1 + 2,
	"두 칸에 로컬 모형: " .. #localFolder():GetChildren()
)
Mock.runScheduler(Mock.clock() + 1.5)
frame()
waitReal(0.3)
frame()
check(look(4) == p5 and look(5) == p4, "서버 칸 모델 새로 만듦")
check(not hiddenModel(4) and not hiddenModel(5), "새 칸 보임")
check(
	#localFolder():GetChildren() == PlayerState.MAX_SLOTS + 1,
	"로컬 모형 치움: " .. #localFolder():GetChildren()
)
-- 서버가 칸을 끝내 안 다시 만들면 3초 뒤 로컬 모형을 치움(서버 모습으로)
handlers.SetDisplay = function(slot, id, expected, from)
	local done, reason = PlayerState.setDisplay(data, slot, id, expected, from)
	pushState()
	return done, reason == "stale"
end
click(slotScreen(4, 2))
click(slotScreen(5))
settle()
check(#localFolder():GetChildren() == PlayerState.MAX_SLOTS + 1 + 2, "로컬 모형 둘")
waitReal(3.1)
frame()
check(#localFolder():GetChildren() == PlayerState.MAX_SLOTS + 1, "3초 넘게 안 맞으면 치움")
check(not hiddenModel(4) and not hiddenModel(5), "서버 모습 보임")
ParkService.update(serverPlayer, data)
frame()
handlers.SetDisplay = fastSetDisplay

print("\n[터치: 톡 집고 톡 놓기]")
local t4, t6 = shownSlots()[4], shownSlots()[6]
local touch1 = input("Touch", slotScreen(4, 2))
UIS.InputBegan:Fire(touch1, false)
frame()
UIS.InputEnded:Fire(touch1, false)
frame()
check(localFolder():FindFirstChild("Held", true) ~= nil, "터치로 집음(손을 떼도 들고 있음)")
local touch2 = input("Touch", slotScreen(6))
UIS.InputBegan:Fire(touch2, false)
frame()
UIS.InputEnded:Fire(touch2, false)
settle()
check(shownSlots()[4] == t6 and shownSlots()[6] == t4, "터치로 놓음(자리 바꿈)")

local d4, d7 = shownSlots()[4], shownSlots()[7]
touchDrag(slotScreen(4, 2), slotScreen(7))
settle()
check(shownSlots()[4] == d7 and shownSlots()[7] == d4, "위에서 보기: 터치로 끌어서 놓기")
touchDrag(slotScreen(7, 2), slotScreen(7, 0.2) + Vector2.new(14, 0))
settle()
check(
	localFolder():FindFirstChild("Held", true) == nil and shownSlots()[7] == d4,
	"터치로 끌었다가 같은 칸에 뗌 = 내려놓기"
)
drag(slotScreen(8, 2), slotScreen(8, 0.2) + Vector2.new(14, 0))
settle()
check(localFolder():FindFirstChild("Held", true) == nil, "마우스로 끌었다가 같은 칸에 뗌 = 내려놓기")

print("\n[두 손가락: 집기 취소 · 벌리기/모으기 = 가까이/멀리 · 다 뗄 때까지 놓기 없음]")
do
	local before = dump()
	local requestCount = #requests
	local autoBefore = data.Settings.AutoPark
	local function distance(): number
		return (camera.CFrame.Position - origin.Position).Magnitude
	end
	local function moveTouch(t: any, at: Vector2)
		t.Position = Vector3.new(at.X - INSET.X, at.Y - INSET.Y, 0)
		UIS.InputChanged:Fire(t, false)
		frame()
	end
	local centre = slotScreen(4, 2)
	local f1 = input("Touch", centre)
	UIS.InputBegan:Fire(f1, false)
	frame()
	check(holding(), "첫 손가락 = 집음")
	local f2 = input("Touch", centre + Vector2.new(120, 0))
	UIS.InputBegan:Fire(f2, false)
	frame()
	settle()
	check(not holding() and not hiddenModel(4), "두 번째 손가락 = 집기 취소(명소는 제자리로)")
	local d0 = distance()
	moveTouch(f2, centre + Vector2.new(180, 0))
	local dNear = distance()
	check(dNear < d0 - 1, string.format("벌리기 = 가까이 (%.1f -> %.1f)", d0, dNear))
	moveTouch(f2, centre + Vector2.new(96, 0))
	local dFar = distance()
	check(dFar > d0 + 1, string.format("모으기 = 멀리 (%.1f -> %.1f)", d0, dFar))
	moveTouch(f2, centre + Vector2.new(20, 0))
	local dMax = distance()
	moveTouch(f2, centre + Vector2.new(10, 0))
	check(math.abs(distance() - dMax) < 1e-6 and dMax > dFar, "더 모아도 가장 먼 배율에서 멈춤")
	moveTouch(f2, centre + Vector2.new(120, 0))
	check(math.abs(distance() - d0) < 1e-3, "처음 간격으로 돌아오면 처음 거리")
	-- 두 번째 손가락을 먼저 떼고, 남은 손가락을 다른 칸으로 끌어서 뗌: 둘 다 무시
	UIS.InputEnded:Fire(f2, false)
	frame()
	moveTouch(f1, slotScreen(7))
	check(math.abs(distance() - d0) < 1e-3, "한 손가락만 남으면 배율 그대로")
	UIS.InputEnded:Fire(f1, false)
	frame()
	settle()
	check(not holding() and dump() == before, "다 뗄 때까지 놓기·집기 없음: " .. dump())
	check(#requests == requestCount and data.Settings.AutoPark == autoBefore, "요청 없음(자동 배치 그대로)")
	tap(slotScreen(4, 2))
	check(holding(), "다 뗀 뒤 한 손가락 톡 = 다시 집음")
	key("Q")
	settle()
	mouseTo(Vector2.new(20, 60))
end

print("\n[시점 · 휠 · 보관 버튼 · 더 좋은 명소 딱지]")
local viewFace = tray:FindFirstChild("View", true)
viewFace = viewFace:FindFirstChild("Face", true) or viewFace
local topCF = camera.CFrame
viewFace.Activated:Fire()
frame()
check(camera.CameraType == Enum.CameraType.Custom and camera.CameraSubject == humanoid, "[시점] = 평소 카메라")
do
	local tap = input("Touch", slotScreen(5, 2))
	UIS.InputBegan:Fire(tap, false)
	frame()
	check(
		localFolder():FindFirstChild("Held", true) == nil,
		"평소 카메라: 터치를 누를 때는 안 집음(끌면 화면 돌리기)"
	)
	UIS.InputEnded:Fire(tap, false)
	frame()
	check(localFolder():FindFirstChild("Held", true) ~= nil, "평소 카메라: 톡 = 집음")
	key("Q")
	settle()
end
viewFace.Activated:Fire()
frame()
check(camera.CameraType == Enum.CameraType.Scriptable, "[시점] 다시 = 위에서 보기")
local d0 = (camera.CFrame.Position - origin.Position).Magnitude
UIS.InputChanged:Fire(
	{ UserInputType = "UserInputType.MouseWheel", KeyCode = "KeyCode.Unknown", Position = Vector3.new(0, 0, -1) },
	false
)
local d1 = (camera.CFrame.Position - origin.Position).Magnitude
check(d1 > d0 + 1, string.format("휠 = 멀리 (%.1f -> %.1f)", d0, d1))
local storeFace = tray:FindFirstChild("Store", true)
storeFace = storeFace:FindFirstChild("Face", true) or storeFace
local s3 = shownSlots()[3]
click(slotScreen(3, 2))
storeFace.Activated:Fire()
settle()
check(
	shownSlots()[3] == nil and scroller:FindFirstChild(s3) ~= nil,
	"[보관] = 들고 있는 명소를 보관함으로"
)
local better = PlayerState.betterHidden(PlayerState.snapshot(data, 0))
local betterShown = #better > 0
for _, id in better do
	local c = scroller:FindFirstChild(id)
	betterShown = betterShown and c ~= nil and c:FindFirstChild("Better").Visible
end
check(betterShown, "더 좋은 명소 카드에 딱지 (" .. #better .. ")")

print("\n[별(가챠식): 처음 발견 ☆0 · 또 뽑을 때마다 ★+1 — 보관함 카드 · 이름표]")
do
	local function goldStars(text: string): number
		local gold = text:match('^<font color="[^"]*">(.-)</font>') or ""
		return select(2, gold:gsub("★", ""))
	end
	local function allStars(text: string): number
		return select(2, text:gsub("★", ""))
	end
	local card = scroller:FindFirstChild(s3)
	local starsLabel = card and card:FindFirstChild("Stars")
	local saved = data.Inventory[s3]
	local seen = {}
	for _, count in { 1, 2, 6, 9 } do
		data.Inventory[s3] = count
		pushState()
		table.insert(seen, string.format("%d개=%d/%d", count, goldStars(starsLabel.Text), allStars(starsLabel.Text)))
	end
	check(
		table.concat(seen, " ") == "1개=0/5 2개=1/5 6개=5/5 9개=5/5",
		"보관함 카드 별 = min(5, 개수 - 1), 빈 별까지 5개 (" .. table.concat(seen, " ") .. ")"
	)
	data.Inventory[s3] = saved
	-- 전시 칸 명소 이름표: 처음 발견(1개) = 빈 별 5개
	local shownId = shownSlots()[4]
	local savedShown = data.Inventory[shownId]
	data.Inventory[shownId] = 1
	pushState()
	mouseTo(slotScreen(4))
	local tagStars = gui:FindFirstChild("ParkEditTag"):FindFirstChild("Stars")
	check(
		tagText() == Landmarks.ById[shownId].Name and goldStars(tagStars.Text) == 0 and allStars(tagStars.Text) == 5,
		"이름표: 처음 발견 = 빈 별 5개 ☆0"
	)
	data.Inventory[shownId] = savedShown
	pushState()
	mouseTo(Vector2.new(20, 60))
end

print("\n[환생: 들고 있던 명소가 없어짐]")
click(slotScreen(2, 2))
check(localFolder():FindFirstChild("Held", true) ~= nil, "들고 있음")
local reborn = PlayerState.new()
reborn.Rebirths = 1
local savedData = data
data = reborn
ParkService.update(serverPlayer, data)
pushState()
frame()
check(localFolder():FindFirstChild("Held", true) == nil, "환생 = 내려놓음")
local anyHidden2 = false
for slot = 1, PlayerState.MAX_SLOTS do
	anyHidden2 = anyHidden2 or hiddenModel(slot)
end
check(not anyHidden2, "숨긴 명소 없음")
check(tray:FindFirstChild("Empty").Visible, "보관함 비었을 때 지구본 + 굴리기")
data = savedData
ParkService.update(serverPlayer, data)
pushState()
frame()

print("\n[자동 배치 버튼: 확인 두 번]")
local autoButton = tray:FindFirstChild("AutoPark", true)
local face = autoButton and (autoButton:FindFirstChild("Face", true) or autoButton)
local activated = face and face.Activated
check(activated ~= nil, "자동 버튼")
local requestCount = #requests
activated:Fire()
frame()
check(#requests == requestCount, "첫 누름 = 확인?(요청 없음)")
activated:Fire()
frame()
settle()
check(requests[#requests] == "auto true" and data.Settings.AutoPark == true, "두 번째 = 자동 켜짐")

print("\n[나가기: Esc]")
key("Escape")
Mock.runScheduler(2)
check(not ParkEdit.isEditing(), "Esc = 나가기")
check(changes[#changes] == false, "Changed(false)")
check(localFolder() == nil, "로컬 폴더 지움")
check(camera.CameraType == Enum.CameraType.Custom, "카메라 되돌림")
check(handlerCount() == baseHandlers, "입력 연결 정리 (" .. handlerCount() .. " / " .. baseHandlers .. ")")
check(detectorCount() == unlocked, "ClickDetector 다시 닮")
check(not barFrame.Visible, "띠 숨김")
check(not signHidden(), "나가면 입구 간판 다시 보임")
local allLabels = true
for slot, _ in shownSlots() do
	if labelOn(slot) == false then
		allLabels = false
	end
end
check(allLabels and labelsOn() > 1, "나가면 전시 칸 이름표 모두 다시 켜짐 (" .. labelsOn() .. "개)")

print("\n[받침대 클릭으로 들어가기 + 바로 집기]")
local clicked = container(2):FindFirstChild("ParkClick")
clicked.MouseClick:Fire()
Mock.runScheduler(3)
check(ParkEdit.isEditing(), "받침대 클릭 = 배치 모드")
check(localFolder():FindFirstChild("Held", true) ~= nil and hiddenModel(2), "그 칸 명소를 바로 집음")

print("\n[죽으면 나감]")
humanoid.Died:Fire()
Mock.runScheduler(4)
check(not ParkEdit.isEditing() and localFolder() == nil, "죽음 = 나가기")
check(not hiddenModel(2), "숨긴 명소 되돌림")

print("\n[부지 밖으로 걸어가면 나감 / 밖에서 들어가면 공원으로 이동]")
ParkEdit.enter(nil)
Mock.runScheduler(5)
check(ParkEdit.isEditing(), "다시 들어감")
placeCharacter(origin * CFrame.new(0, 3.6, -80))
Mock.runScheduler(6)
check(not ParkEdit.isEditing(), "부지 밖 = 나가기")
ParkEdit.enter(1)
Mock.runScheduler(7)
check(ParkEdit.isEditing(), "밖에서 [배치] = 공원으로 이동 후 들어감")
check(localFolder():FindFirstChild("Held", true) ~= nil, "칸 1 명소 집음")

print("\n[부지 잃음]")
ParkEdit.setPlot(nil)
check(not ParkEdit.isEditing() and localFolder() == nil, "부지가 사라지면 나가기")
check(handlerCount() == baseHandlers, "입력 연결 정리")

print("\n[HUD · 도감 [배치] 버튼]")
local Hud = Harness.require(client.Hud)
local Panels = Harness.require(client.Panels)
local arranged = 0
local menus: { string } = {}
local hudGui = Hud.init(playerGui, {
	Roll = function() end,
	ToggleAuto = function() end,
	Menu = function(name)
		table.insert(menus, name)
	end,
	Teleport = function() end,
	Arrange = function()
		arranged += 1
	end,
})
hudGui.AbsoluteSize = Vector2.new(1280, 684)
Panels.init(hudGui, {
	Feature = function() end,
	Buy = function() end,
	ToggleAutoFeature = function() end,
	Rebirth = function() end,
	BuyPass = function() end,
	BuyProduct = function() end,
	Toast = function() end,
	Arrange = function()
		arranged += 10
	end,
})
local state = PlayerState.snapshot(data, 99)
Hud.render(state)
Hud.setPlotOwned(true)
Panels.render(state)
Panels.toggle("Collection")
local arrangeHud = hudGui:FindFirstChild("Arrange", true)
local arrangeFace = arrangeHud:FindFirstChild("Face", true) or arrangeHud
arrangeFace.Activated:Fire()
check(arranged == 1, "HUD [배치] = Arrange 핸들러")
local window = hudGui:FindFirstChild("Window", true)
local collectionArrange
for _, d in window:GetDescendants() do
	if d.Name == "Arrange" then
		collectionArrange = d
	end
end
check(collectionArrange ~= nil, "도감 머리 줄 [배치]")
local cface = collectionArrange:FindFirstChild("Face", true) or collectionArrange
cface.Activated:Fire()
check(arranged == 11, "도감 [배치] = Arrange 핸들러")
local better = collectionArrange:FindFirstChild("Better", true)
check(better ~= nil, "도감 [배치] 배지")
Hud.setEditing(true)
local menuFrame = hudGui:FindFirstChild("Menu", true)
local rollBar = hudGui:FindFirstChild("RollBar", true)
check(not menuFrame.Visible and not rollBar.Visible, "배치 모드: HUD 메뉴·굴리기 줄 숨김")
-- 배치 모드 굴림 결과: 가운데 연출(공원 한가운데를 가림) 없이 알림 줄의 작은 등급 색 딱지(+ 처음이면 NEW)
local revealFrame = hudGui:FindFirstChild("Reveal", true)
local function rollResult(name: string): any
	for _, d in hudGui:GetDescendants() do
		if d.Name == "RollResult" then
			local label = d:FindFirstChild("Label", true)
			if label and label.Text == name then
				return d
			end
		end
	end
	return nil
end
local revealInfo = { Fast = true, IsNew = true, StarUp = false, Stars = 1, Bonus = 0, Luck = 1 }
local first = Landmarks.RarestFirst[1]
local revealDone = false
task.spawn(function()
	Hud.reveal(first, revealInfo)
	revealDone = true
end)
check(revealDone and not revealFrame.Visible, "배치 모드 굴림 = 가운데 연출 없이 바로 끝남")
local chip = rollResult(first.Name)
check(chip ~= nil and chip:FindFirstChild("New", true) ~= nil, "알림 줄에 명소 이름 딱지 + NEW")
-- 또 뽑아 별이 오름 = 작은 "★+1" 딱지
local dupe = Landmarks.RarestFirst[3]
task.spawn(Hud.reveal, dupe, { Fast = true, IsNew = false, StarUp = true, Stars = 2, Bonus = 0, Luck = 1 })
local dupeChip = rollResult(dupe.Name)
local dupeStar = dupeChip and dupeChip:FindFirstChild("StarUp", true)
local dupeLabel = dupeStar and dupeStar:FindFirstChild("Label", true)
check(
	dupeLabel ~= nil and dupeLabel.Text:find("+1", 1, true) ~= nil and dupeChip:FindFirstChild("New", true) == nil,
	'또 뽑음 = 명소 이름 딱지 + "★+1"'
)
local maxed = Landmarks.RarestFirst[4]
task.spawn(Hud.reveal, maxed, { Fast = true, IsNew = false, StarUp = true, Stars = 5, Bonus = 0, Luck = 1 })
local maxedChip = rollResult(maxed.Name)
local maxedStar = maxedChip and maxedChip:FindFirstChild("StarUp", true)
local maxedLabel = maxedStar and maxedStar:FindFirstChild("Label", true)
check(maxedLabel ~= nil and maxedLabel.Text:find("MAX", 1, true) ~= nil, '★5 가 됨 = "★MAX"')
check(
	chip ~= nil
		and (
			(chip:IsA("ImageLabel") and chip.ImageColor3 == first.Tier.Color)
			or chip.BackgroundColor3 == first.Tier.Color
		),
	"딱지 = 등급 색"
)
Hud.setEditing(false)
check(menuFrame.Visible and rollBar.Visible, "나가면 다시 보임")
-- 가운데 연출이 도는 중에 배치 모드에 들어가면 바로 숨기고, 결과는 딱지로(결과를 보인 뒤에 돌아가서 상태 반영 순서 그대로)
local second = Landmarks.RarestFirst[2]
local secondDone = false
task.spawn(function()
	Hud.reveal(second, { Fast = false, IsNew = false, StarUp = false, Stars = 1, Bonus = 0, Luck = 1 })
	secondDone = true
end)
Mock.runScheduler(Mock.clock() + 0.3)
check(revealFrame.Visible and not secondDone, "평소 = 가운데 연출(지구본이 도는 중)")
Hud.setEditing(true)
check(not revealFrame.Visible, "도는 중에 배치 모드에 들어가면 가운데 연출을 바로 숨김")
Mock.runScheduler(Mock.clock() + 0.5)
check(
	secondDone and not revealFrame.Visible,
	"숨긴 연출을 기다리지 않고 바로 끝남(가운데 연출 없이)"
)
check(rollResult(second.Name) ~= nil, "결과는 알림 줄 딱지로")
Hud.setEditing(false)
for _, name in { "Collection", "Upgrade", "Rebirth" } do
	Panels.toggle(name)
end
-- 여권은 도감 대륙 탭으로 합침: 옛 이름은 아무것도 열지 않음, 도감은 대륙 탭으로 바로 열 수 있음
Panels.toggle("Passport")
local openName = Panels.current()
check(openName == "Rebirth", '옛 "Passport" 창 없음(열린 창 그대로)')
for _, region in Landmarks.Regions do
	Panels.open("Collection", region.Id)
	local name, tab = Panels.current()
	check(name == "Collection" and tab == region.Id, "도감 " .. region.Id .. " 탭으로 열기")
end
Panels.close()
local _, reset = Panels.current()
check(Panels.current() == nil and reset == "All", "닫으면 탭은 [전체]로")
check(true, "Panels 창 전부 열고 닫기(오류 없음)")

print("\n[모듈 오류]")
E.finish()
