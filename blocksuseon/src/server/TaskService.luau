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
	if session.trial or session.tribulation then
		Sync.notify(player, "지금은 내관할 수 없다.", "bad")
		return
	end
	if not Characters.humanoid(player) then
		return
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
	end
	local task = trial.taskId and Tasks.find(data, trial.taskId)
	if not task then
		return
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
