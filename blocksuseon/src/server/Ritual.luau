-- 칠성제의(七星祭儀): 연기기 7성. 밤, 고른 칠수가 하늘 가운데 오는 시운에 칠성단에서 제의를 올리면
-- 일곱 줄기 별빛이 차례로 내려온다. 천겁의 붉은 원과 반대로, 푸른 원 안으로 들어가 받아야 한다.
-- 다섯 줄기 이상 받으면 성공이다. 실패하면 바친 제물만 잃고 다음 시운에 다시 한다.

local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Progression = require(Shared.Progression)
local Clock = require(Shared.Clock)
local Roots = require(Shared.Roots)
local Tasks = require(Shared.Tasks)
local PlayerData = require(script.Parent.PlayerData)
local Session = require(script.Parent.Session)
local Sync = require(script.Parent.Sync)
local Characters = require(script.Parent.Characters)
local Fx = require(script.Parent.Fx)
local Tribulation = require(script.Parent.Tribulation)
local DayNight = require(script.Parent.DayNight)

local BEAMS = 7
local NEED = 5
local RADIUS = 4.5
local TELEGRAPH = 2.2
local INTERVAL = 0.9
local STAR_COLOR = Color3.fromRGB(140, 190, 255)

local Ritual = {}

local rng = Random.new()

-- 지금 시운인가. 반환: 시운이면 true, 아니면 false 와 기다릴 초
function Ritual.inWindow(data): (boolean, number)
	local chilsu = data.choice.chilsu
	if not chilsu then
		return false, 0
	end
	return Clock.sigunState(DayNight.time(), chilsu, Roots.window(data.root))
end

-- onDone(success, caught)
function Ritual.start(player: Player, altar: Vector3, onDone: (boolean, number) -> ())
	local data = PlayerData.get(player)
	local session = Session.get(player)
	if not data or not session or session.ritual or session.tribulation or session.trial then
		return
	end
	local inside, wait = Ritual.inWindow(data)
	if not inside then
		local name = Tasks.CHILSU[data.choice.chilsu or "cheong"].name
		Sync.notify(
			player,
			string.format("아직 %s의 시운이 아니다. 시운까지 %s 남았다.", name, Clock.format(wait)),
			"bad"
		)
		return
	end
	session.ritual = true
	Sync.notify(
		player,
		"제의를 올렸다. 하늘에서 내리는 별빛을 푸른 원 안으로 들어가 받는다. 일곱 줄기 가운데 다섯.",
		"good"
	)
	Sync.markDirty(player)

	task.spawn(function()
		local telegraph = Progression.telegraphTime(data, TELEGRAPH)
		local caught = 0
		for beam = 1, BEAMS do
			local root = Characters.root(player)
			if Session.get(player) ~= session or not root or not Characters.humanoid(player) then
				break
			end
			-- 플레이어에게서 조금 떨어진 곳, 칠성단 마당 안
			local angle = rng:NextNumber(0, math.pi * 2)
			local distance = rng:NextNumber(6, 12)
			local point = root.Position + Vector3.new(math.cos(angle), 0, math.sin(angle)) * distance
			local offset = point - altar
			local flat = Vector3.new(offset.X, 0, offset.Z)
			if flat.Magnitude > 26 then
				point = altar + flat.Unit * 26
			end
			local ground = Tribulation.groundAt(point)
			Tribulation.mark(ground, RADIUS, telegraph, STAR_COLOR)
			task.wait(telegraph)
			root = Characters.root(player)
			Tribulation.strike(ground, RADIUS, STAR_COLOR)
			if root then
				local d = root.Position - ground
				if Vector3.new(d.X, 0, d.Z).Magnitude <= RADIUS and d.Y > -4 and d.Y < 14 then
					caught += 1
					Fx.burst(player.Character, STAR_COLOR, 20)
					Sync.notify(player, string.format("별빛을 받았다. (%d / %d)", caught, beam), "good")
				end
			end
			task.wait(INTERVAL)
		end
		if Session.get(player) == session then
			session.ritual = false
			Sync.markDirty(player)
		end
		onDone(caught >= NEED, caught)
	end)
end

return Ritual
