-- 클라이언트 진입점: 상태 동기화, 굴리기/자동 굴리기, 메뉴 연결, 알림

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TextChatService = game:GetService("TextChatService")
local UserInputService = game:GetService("UserInputService")

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")
local Auras = require(Shared.Auras)
local Format = require(Shared.Format)
local Net = require(Shared.Net)

local Hud = require(script.Hud)
local Panels = require(script.Panels)
local Ui = require(script.Ui)

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local state = nil -- 서버에서 받은 최신 Snapshot
local stateReceivedAt = 0
local rolling = false
local autoRoll = false
local lastRollSentAt = -math.huge

-- 서버 상태 반영. Revision 이 더 큰 것만 받아서 늦게 도착한 옛 상태가 덮어쓰지 않게 함.
local function applyState(snapshot: any)
	if type(snapshot) ~= "table" then
		return
	end
	if state and snapshot.Revision <= state.Revision then
		return
	end
	state = snapshot
	stateReceivedAt = time()
	Hud.render(state)
	Panels.render(state)
end

local function invoke(name: string, ...: any): any
	local ok, result = pcall(Net.fn(name).InvokeServer, Net.fn(name), ...)
	if not ok then
		warn("[AuraRNG] " .. name .. " 실패: " .. tostring(result))
		Hud.toast("서버와 통신하지 못했어요. 잠시 후 다시 시도해 주세요.", Ui.Theme.Bad)
		return nil
	end
	return result
end

local function equip(auraId: string?)
	local response = invoke("Equip", auraId)
	if response then
		applyState(response.State)
		if response.Ok and auraId then
			local aura = Auras.ById[auraId]
			Hud.toast(aura.Name .. " 장착!", aura.Color, 2)
		end
	end
end

local function roll()
	if rolling or not state then
		return
	end
	rolling = true
	Hud.setRolling(true)

	-- 쿨타임이 남았으면 기다렸다가 요청
	local waitFor = lastRollSentAt + state.Cooldown - time()
	if waitFor > 0 then
		task.wait(waitFor)
	end
	lastRollSentAt = time()
	local response = invoke("Roll")

	if response and response.Ok then
		Hud.startCooldown(response.State.Cooldown)
		local aura = Auras.ById[response.AuraId]
		Hud.reveal(aura, {
			Fast = autoRoll,
			Lucky = response.Lucky,
			IsNew = response.IsNew,
			Coins = response.Coins,
			Luck = response.Luck,
		})
		applyState(response.State) -- 연출이 끝난 뒤에 숫자 갱신(스포일러 방지)

		-- 더 희귀하면 자동 장착
		if state.Settings.AutoEquip then
			local current = if state.Equipped then Auras.ById[state.Equipped] else nil
			if not current or aura.OneIn > current.OneIn then
				equip(aura.Id)
			end
		end
	elseif response and response.Reason == "cooldown" then
		task.wait(response.RetryIn or 0.2)
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

local function buy(potionId: string)
	local response = invoke("BuyPotion", potionId)
	if not response then
		return
	end
	applyState(response.State)
	if response.Ok then
		Hud.toast("구매 완료!", Ui.Theme.Good, 2)
	else
		Hud.toast(response.Reason or "구매하지 못했어요", Ui.Theme.Bad, 2)
	end
end

local function toggleAutoEquip()
	if not state then
		return
	end
	local response = invoke("SetSetting", "AutoEquip", not state.Settings.AutoEquip)
	if response then
		applyState(response.State)
	end
end

-- 화면 만들기 ---------------------------------------------------------------

local gui = Hud.init(playerGui, {
	Roll = function()
		task.spawn(roll)
	end,
	ToggleAuto = toggleAuto,
	Menu = Panels.toggle,
})
Panels.init(gui, {
	Equip = equip,
	Buy = buy,
	ToggleAutoEquip = toggleAutoEquip,
})

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

Net.event("State").OnClientEvent:Connect(applyState)

Net.event("Announce").OnClientEvent:Connect(function(info)
	local aura = type(info) == "table" and Auras.ById[info.AuraId]
	if not aura then
		return
	end
	Hud.banner(tostring(info.Name), aura, tonumber(info.Rolls) or 0)

	-- 채팅창에도 시스템 메시지 (새 TextChatService 를 쓰는 경우)
	pcall(function()
		local channels = TextChatService:FindFirstChild("TextChannels")
		local general = channels and channels:FindFirstChild("RBXGeneral")
		if general then
			general:DisplaySystemMessage(
				string.format(
					'[AuraRNG] %s 님이 <font color="%s"><b>%s</b></font> (%s) 획득!',
					Format.escape(tostring(info.Name)),
					Format.hex(aura.Color),
					aura.Name,
					Format.oneIn(aura.OneIn)
				)
			)
		end
	end)
end)

-- 루프 ---------------------------------------------------------------------

-- 그라데이션 오라 이름표 회전 애니메이션 (서버/클라가 붙인 "AuraGradient" 태그 대상)
RunService.RenderStepped:Connect(function()
	local rotation = (os.clock() * 90) % 360
	for _, gradient in CollectionService:GetTagged("AuraGradient") do
		if gradient:IsA("UIGradient") then
			gradient.Rotation = rotation
		end
	end
end)

-- 물약 타이머 표시
task.spawn(function()
	while true do
		Hud.updateTimers(state, time() - stateReceivedAt)
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
