-- 과업 진행: 자리에서 운기하기, 고르기, 먹기, 내관(미니게임).
--
-- 과업 정의는 shared/Tasks.luau 에 있다. 여기서는 위치·시각·진 안 여부를 보고 진행값을 올리고,
-- 내관은 seed 를 정해 클라이언트에 열어 준 뒤 돌아온 답을 Trials.check 로 맞춰 본다.
-- 단계를 올리는 일(영력과 함께 판정)은 Cultivation 이 settle 로 넘겨받는다.

local CollectionService = game:GetService("CollectionService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Tasks = require(Shared.Tasks)
local Trials = require(Shared.Trials)
local Roots = require(Shared.Roots)
local Progression = require(Shared.Progression)
local Balance = require(Shared.Balance)
local Josa = require(Shared.Josa)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)
local DayNight = require(script.Parent.DayNight)
local Ritual = require(script.Parent.Ritual)

local TaskService = {}

-- Cultivation 이 채워 넣는다 (서로 require 하지 않으려고)
TaskService.settle = function(_player: Player) end
TaskService.setMeditating = function(_player: Player, _on: boolean) end
TaskService.onEntryTrial = function(_player: Player, _success: boolean) end

-- 영맥 등급에 따른 농도 흔들림 (하품은 잔잔하고 상품일수록 거세다)
local TURBULENCE = { low = 0.8, mid = 1.3, high = 1.7 }

local rng = Random.new()

-- 자리 ------------------------------------------------------------------------------

local sites: { [string]: BasePart } = {}

local function refreshSites()
	table.clear(sites)
	for _, part in CollectionService:GetTagged("Site") do
		local id = part:GetAttribute("Site")
		if type(id) == "string" and part:IsA("BasePart") then
			sites[id] = part
		end
	end
end

function TaskService.site(id: string): BasePart?
	local part = sites[id]
	if not part or not part.Parent then
		refreshSites()
		part = sites[id]
	end
	return part
end

local function isAt(position: Vector3, id: string): boolean
	local part = TaskService.site(id)
	if not part then
		return false
	end
	local radius = part:GetAttribute("Radius")
	radius = if type(radius) == "number" then radius else 8
	local offset = position - part.Position
	return Vector3.new(offset.X, 0, offset.Z).Magnitude <= radius and offset.Y > -6 and offset.Y < 12
end

local function siteName(id: string): string
	local part = TaskService.site(id)
	local name = part and part.Parent and part.Parent.Name
	return if name then name else id
end

-- 진행 ------------------------------------------------------------------------------

local function finished(player: Player, task: Tasks.Task)
	Sync.notify(player, string.format("%s 마쳤다.", Josa.eul(task.label)), "good")
	if task.id == "sense" then
		-- 영기 감지: 오행의 다섯 빛이 몸을 돈다
		for _, element in Roots.ELEMENTS do
			local c = Roots.ELEMENT[element].color
			Fx.burst(player.Character, Color3.fromRGB(c[1], c[2], c[3]), 16)
		end
		Sync.notify(
			player,
			"천지의 영기가 느껴진다. 몸에 반응하는 기운을 골라 영근을 깨운다.",
			"good"
		)
	end
	TaskService.settle(player)
end

-- 운기조식 중인 플레이어의 자리·시각 과업을 올린다 (Cultivation.tick 에서 부른다)
function TaskService.meditateTick(player: Player, data, session, position: Vector3, dt: number)
	local phase = DayNight.phase()
	TaskService.counter(player, "meditate", dt * 0.5)
	if session.inFormation then
		TaskService.counter(player, "formation", dt)
	end
	if phase == "night" then
		TaskService.counter(player, "stargaze", dt)
	end
	for _, task in (Tasks.list(data)) do
		if task.kind ~= "meditate" or Tasks.isDone(data, task) or not Tasks.isOpen(data, task) then
			continue
		end
		if task.when and task.when ~= phase then
			continue
		end
		if task.formation and not session.inFormation then
			continue
		end
		if not task.sites then
			if Tasks.add(data, task, dt) then
				finished(player, task)
			end
			session.dirty = true
			continue
		end
		local prog = Tasks.ensure(data)
		for _, site in Tasks.pendingSites(data, task) do
			if isAt(position, site) then
				local key = Tasks.siteKey(task, site)
				prog.t[key] = (prog.t[key] or 0) + dt
				session.dirty = true
				if prog.t[key] >= (task.seconds or 1) then
					local done = Tasks.finishSite(data, task, site)
					Sync.notify(
						player,
						string.format(
							"%s에서 %s 닦았다. (%d / %d)",
							siteName(site),
							Josa.eul(task.label),
							Tasks.value(data, task),
							task.max
						),
						"good"
					)
					if done then
						finished(player, task)
					end
				end
				break
			end
		end
	end
end

-- 광기: 천인기 도심에 맞는 일을 할 때 오른다 (event: herb, formation, craft, stargaze, meditate)
function TaskService.counter(player: Player, event: string, amount: number)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	for _, task in (Tasks.list(data)) do
		if
			task.kind == "counter"
			and task.event == event
			and Tasks.isOpen(data, task)
			and not Tasks.isDone(data, task)
		then
			if Tasks.add(data, task, amount) then
				Sync.notify(player, "광기가 무르익었다. 자아가 한 겹 벗겨진다.", "good")
				finished(player, task)
			end
			Sync.markDirty(player)
		end
	end
end

-- 고르기 ------------------------------------------------------------------------------

function TaskService.choose(player: Player, key: any, value: any)
	local data = PlayerData.get(player)
	if not data then
		return
	end
	local ok, message = Progression.choose(data, key, value)
	Sync.notify(player, message, if ok then "good" else "bad")
	if ok and key == "root" and data.root then
		for _, element in data.root.elements do
			local c = Roots.ELEMENT[element].color
			Fx.burst(player.Character, Color3.fromRGB(c[1], c[2], c[3]), 30)
		end
		Sync.broadcast(
			string.format("%s님의 영근이 깨어났다. %s", player.DisplayName, Roots.describe(data.root)),
			"world"
		)
	end
	if ok then
		TaskService.settle(player)
	end
	Sync.state(player)
end

-- 먹기 ------------------------------------------------------------------------------

-- 먹고 나서 eat 과업을 올린다. 영력 지급은 Cultivation 이 grantQi 로 한다 (돌려준 양)
function TaskService.eat(player: Player, item: any): number?
	local data = PlayerData.get(player)
	if not data then
		return nil
	end
	local result = Progression.eat(data, item)
	if not result.ok then
		Sync.notify(player, result.message, "bad")
		Sync.state(player)
		return nil
	end
	Sync.notify(player, result.message, "good")
	if result.rootChanged then
		Fx.burst(player.Character, Color3.fromRGB(255, 120, 110), 50)
		Sync.broadcast(
			string.format("%s님이 홍령삼을 먹고 홍령수지체가 되었다.", player.DisplayName),
			"world"
		)
	end
	for _, task in (Tasks.list(data)) do
		if task.kind == "eat" and task.item == item and Tasks.add(data, task, 1) then
			finished(player, task)
		end
	end
	Sync.markDirty(player)
	return result.qi
end

-- 건너뛰기 ------------------------------------------------------------------------------

function TaskService.skip(player: Player, id: any)
	local data = PlayerData.get(player)
	if not data or type(id) ~= "string" then
		return
	end
	local ok, message = Progression.skipTask(data, id)
	Sync.notify(player, message, if ok then "good" else "bad")
	if ok then
		TaskService.settle(player)
	end
	Sync.state(player)
end

-- 내관 ------------------------------------------------------------------------------

local function openTrial(player: Player, session, trial: Session.Trial, title: string, hint: string?)
	session.trial = trial
	Sync.remotes.Trial:FireClient(player, {
		id = trial.id,
		mode = trial.mode,
		seed = trial.seed,
		params = trial.params,
		title = title,
		hint = hint,
	})
	Sync.markDirty(player)
end

local function closeTrial(player: Player, session)
	session.trial = nil
	Sync.remotes.Trial:FireClient(player, { close = true })
	Sync.markDirty(player)
end

-- 미니게임 조건: 판정 폭(영근·청심결), 영맥 흔들림
local function tuned(data, session, mode: string, params: { [string]: any }): { [string]: any }
	local out = table.clone(params)
	out.band = Progression.trialBand(data)
	if mode == "balance" then
		out.turbulence = TURBULENCE[session.veinId or ""] or 1
	end
	return out
end

local function newTrial(session, mode: string, purpose: string, params): Session.Trial
	session.trialCount += 1
	return {
		id = session.trialCount,
		mode = mode,
		purpose = purpose,
		seed = rng:NextInteger(1, 2 ^ 30),
		params = params,
		startedAt = os.clock(),
	}
end

-- 과업 내관을 연다. 운기조식 중이 아니면 자리에 앉힌다
function TaskService.startTask(player: Player, id: any)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session or type(id) ~= "string" then
		return
	end
	local task = Tasks.find(data, id)
	if not task or task.kind ~= "trial" or not task.mode then
		return
	end
	if Tasks.isDone(data, task) then
		Sync.notify(player, "이미 끝낸 과업이다.", "bad")
		return
	end
	if not Tasks.isOpen(data, task) then
		Sync.notify(player, "앞의 과업부터 끝내야 한다.", "bad")
		return
	end
	if session.trial or session.tribulation or session.ritual then
		Sync.notify(player, "지금은 내관할 수 없다.", "bad")
		return
	end
	if not Characters.humanoid(player) then
		return
	end
	for item, count in task.cost or {} do
		if Progression.itemCount(data, item) < count then
			Sync.notify(
				player,
				if item == "starSeed"
					then "별씨가 없다. 밤에 내리는 영성우에서 별씨를 줍는다."
					else string.format("%s 모자라다.", Josa.i(Balance.ITEMS[item].name)),
				"bad"
			)
			return
		end
	end
	TaskService.setMeditating(player, true)
	if not session.meditating then
		return
	end
	local trial = newTrial(session, task.mode, "task", tuned(data, session, task.mode, task.params or {}))
	trial.taskId = task.id
	openTrial(player, session, trial, task.label, task.hint)
end

-- 돌파 내관(무극영운)을 연다. Cultivation.breakthrough 에서 부른다
function TaskService.startEntry(player: Player, mode: string, title: string, params: { [string]: any })
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session or session.trial then
		return
	end
	TaskService.setMeditating(player, true)
	local trial = newTrial(session, mode, "entry", tuned(data, session, mode, params))
	openTrial(player, session, trial, title, nil)
end

function TaskService.trialResult(player: Player, payload: any)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	local trial = session and session.trial
	if not data or not session or not trial or type(payload) ~= "table" or payload.id ~= trial.id then
		return
	end
	local elapsed = os.clock() - trial.startedAt
	local puzzle = Trials.generate(trial.mode, trial.seed, trial.params)
	local success = payload.ok == true
		and elapsed >= Trials.minTime(trial.mode, trial.params)
		and Trials.check(trial.mode, puzzle, payload.answer)
	closeTrial(player, session)

	if trial.purpose == "entry" then
		TaskService.onEntryTrial(player, success)
		return
	elseif trial.purpose == "craft" then
		if success and Progression.takeItems(data, Balance.PILL_RECIPE) then
			Progression.addItem(data, "pill")
			Fx.burst(player.Character, Color3.fromRGB(255, 200, 120), 40)
			Sync.notify(player, "축기단을 빚었다! 무극영운을 시작할 때 저절로 삼킨다.", "good")
			TaskService.counter(player, "craft", 40)
			TaskService.settle(player)
		elseif not success then
			Sync.notify(
				player,
				"불이 고르지 않아 약이 엉겼다. 재료는 그대로다. 다시 달여 본다.",
				"bad"
			)
		end
		Sync.state(player)
		return
	end
	local task = trial.taskId and Tasks.find(data, trial.taskId)
	if not task then
		return
	end
	if success and task.cost and not Progression.takeItems(data, task.cost) then
		Sync.notify(player, "쓸 물건이 주머니에 없다.", "bad")
		success = false
	end
	if success then
		Tasks.set(data, task.id, task.max)
		Fx.burst(player.Character, Color3.fromRGB(150, 235, 255), 30)
		finished(player, task)
	else
		Sync.notify(player, "기운이 흐트러졌다. 숨을 고르고 다시 해 본다.", "bad")
	end
	Sync.state(player)
end

-- 그만두기. 돌파 내관을 도중에 그만두면 실패로 친다
function TaskService.cancelTrial(player: Player)
	local session = Session.get(player)
	local trial = session and session.trial
	if not session or not trial then
		return
	end
	closeTrial(player, session)
	if trial.purpose == "entry" then
		TaskService.onEntryTrial(player, false)
	end
end

function TaskService.hasTrial(player: Player): boolean
	local session = Session.get(player)
	return session ~= nil and session.trial ~= nil
end

-- 만지는 자리 (팔괘 기둥, 칠성단, 연단로) -------------------------------------------------

local function findTask(data, kind: string): Tasks.Task?
	for _, task in (Tasks.list(data)) do
		if task.kind == kind and Tasks.isOpen(data, task) and not Tasks.isDone(data, task) then
			return task
		end
	end
	return nil
end

local function touchTrigram(player: Player, data, id: string)
	local task = findTask(data, "touch")
	if not task then
		Sync.notify(player, "팔괘가 새겨진 기둥이다. 연기기 6성 팔괘완로에서 쓴다.", "info")
		return
	end
	local expected = Tasks.pendingSites(data, task)[1]
	local name = siteName(id)
	if id == expected then
		local done = Tasks.finishSite(data, task, id)
		Fx.burst(player.Character, Color3.fromRGB(255, 225, 160), 14)
		Sync.notify(
			player,
			string.format("%s 영맥에 새겼다. (%d / %d)", Josa.eul(name), Tasks.value(data, task), task.max),
			"good"
		)
		if done then
			Sync.notify(
				player,
				"여덟 괘가 원을 그렸다. 전신 영맥이 하나의 길로 이어진다.",
				"good"
			)
			finished(player, task)
		end
	else
		Tasks.set(data, task.id, 0)
		Sync.notify(player, "순서가 어긋나 진도가 흩어졌다. 건부터 다시 새긴다.", "bad")
	end
	Sync.markDirty(player)
end

-- 바치기: 이 자리가 남은 offer 과업 (칠성단 제물, 노인 부탁, 종심)
local function offerAt(data, id: string): Tasks.Task?
	for _, task in (Tasks.list(data)) do
		if
			task.kind == "offer"
			and Tasks.isOpen(data, task)
			and not Tasks.isDone(data, task)
			and table.find(Tasks.pendingSites(data, task), id)
		then
			return task
		end
	end
	return nil
end

local ELDER_WORDS = {
	elder_1 = "약초꾼이 영초 향을 맡고 웃는다. 젊을 적 숲에서 길을 잃었던 이야기를 하다 조용히 눈을 감는다.",
	elder_2 = "대장장이가 영초를 쥐고 화덕을 바라본다. 끝내 못 벼린 칼 이야기를 남기고 숨을 거둔다.",
	elder_3 = "뱃사공이 개울 소리를 들으며 영초를 받는다. 강 건너 고향 이야기를 하다 잠든다.",
}

local function useOffer(player: Player, data, task: Tasks.Task, id: string)
	local item = task.item or "herb"
	local count = task.count or 1
	local have = Progression.itemCount(data, item)
	if not Progression.takeItems(data, { [item] = count }) then
		Sync.notify(
			player,
			string.format("%s %d개가 든다. 지금 %d개다.", Balance.ITEMS[item].name, count, have),
			"bad"
		)
		return
	end
	local done = Tasks.finishSite(data, task, id)
	if ELDER_WORDS[id] then
		Sync.notify(player, ELDER_WORDS[id], "info")
	elseif task.id == "offer" then
		Sync.notify(
			player,
			"칠성단에 영초 일곱 뿌리를 바쳤다. 밤의 시운을 기다려 제의를 올린다.",
			"good"
		)
	else
		Sync.notify(player, string.format("%s 내려놓았다.", Josa.eul(Balance.ITEMS[item].name)), "good")
	end
	if done then
		finished(player, task)
	end
	Sync.markDirty(player)
end

local function useAltar(player: Player, data, part: BasePart)
	local rite = findTask(data, "ritual")
	if rite then
		local anyNight = rite.params ~= nil and rite.params.anyNight == true
		Ritual.start(player, part.Position, anyNight, function(success, caught)
			local current = PlayerData.get(player)
			if not current or current.step ~= data.step then
				return
			end
			if success then
				Tasks.set(current, rite.id, rite.max)
				Progression.addLog(current, rite.id)
				if anyNight then
					Sync.notify(player, "3원과 스물여덟 별이 금단에 새겨졌다.", "good")
				else
					Sync.notify(
						player,
						"일곱 별이 제의를 받아들였다. 이제 자신의 명을 읽을 수 있다.",
						"good"
					)
				end
				Sync.broadcast(
					string.format("%s님이 %s 마쳤다.", player.DisplayName, Josa.eul(rite.label)),
					"world"
				)
				finished(player, rite)
			else
				local offerTask = Tasks.find(current, "offer")
				if offerTask then
					Tasks.set(current, offerTask.id, 0)
					Tasks.set(current, Tasks.siteKey(offerTask, "altar"), 0)
				end
				Sync.notify(
					player,
					string.format(
						"별빛을 %d줄기밖에 받지 못했다. 제물이 흩어졌다. 다시 바치고 다음 시운에 올린다.",
						caught
					),
					"bad"
				)
			end
			Sync.state(player)
		end)
		return
	end
	Sync.notify(player, "칠성단이다. 칠성제의와 결단기 제의에서 쓴다.", "info")
end

local function useFurnace(player: Player, data, session)
	if not Progression.canCraftPill(data) then
		Sync.notify(
			player,
			string.format(
				"축기단을 빚으려면 영초 6뿌리와 천년영지 1개가 든다. 지금 영초 %d, 천년영지 %d.",
				Progression.itemCount(data, "herb"),
				Progression.itemCount(data, "lingzhi")
			),
			"bad"
		)
		return
	end
	if session.trial or session.tribulation then
		return
	end
	local trial = newTrial(session, "balance", "craft", {
		bars = 1,
		target = 10,
		labels = { "불" },
		band = Progression.trialBand(data),
		turbulence = 1,
	})
	openTrial(
		player,
		session,
		trial,
		"축기단 빚기",
		"불 세기를 금색 띠 안에 맞춰 영초와 천년영지를 달인다."
	)
end

function TaskService.onPrompt(player: Player, id: string)
	local data = PlayerData.get(player)
	local session = Session.get(player)
	local part = TaskService.site(id)
	if not data or not session or not part or not Characters.humanoid(player) then
		return
	end
	local offer = offerAt(data, id)
	if offer then
		useOffer(player, data, offer, id)
	elseif string.sub(id, 1, 4) == "tri_" then
		touchTrigram(player, data, id)
	elseif id == "altar" then
		useAltar(player, data, part)
	elseif id == "furnace" then
		useFurnace(player, data, session)
	elseif string.sub(id, 1, 6) == "elder_" then
		Sync.notify(player, "노인이 볕을 쬐며 꾸벅꾸벅 존다.", "info")
	end
	Sync.state(player)
end

-- Prompt 속성이 있는 자리에 F 버튼을 단다. 누가 볼지는 클라이언트가 과업을 보고 정한다
function TaskService.setupPrompts()
	refreshSites()
	for id, part in sites do
		local label = part:GetAttribute("Prompt")
		if type(label) == "string" and not part:FindFirstChildOfClass("ProximityPrompt") then
			local prompt = Instance.new("ProximityPrompt")
			prompt.ObjectText = label
			prompt.ActionText = if id == "furnace"
				then "축기단 빚기"
				elseif id == "altar" then "제의"
				elseif string.sub(id, 1, 6) == "elder_" then "말 걸기"
				else "괘 새기기"
			prompt.KeyboardKeyCode = Enum.KeyCode.F
			prompt.HoldDuration = 0.4
			prompt.MaxActivationDistance = if id == "altar" then 14 else 10
			prompt.RequiresLineOfSight = false
			prompt:SetAttribute("Site", id)
			prompt:AddTag("TaskPrompt")
			prompt.Parent = part
			prompt.Triggered:Connect(function(player)
				TaskService.onPrompt(player, id)
			end)
		end
	end
end

-- 주머니에 넣는다 (영초 채집 등)
function TaskService.giveItem(player: Player, item: string, count: number?)
	local data = PlayerData.get(player)
	if not data or not Balance.ITEMS[item] then
		return
	end
	Progression.addItem(data, item, count)
	Sync.markDirty(player)
end

return TaskService
