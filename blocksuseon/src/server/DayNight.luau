-- 서버 공용 낮밤 (Clock.luau). 한 바퀴 12분.
-- Workspace 속성 CycleOrigin 에 시작 시각을 적어 두면 클라이언트도 같은 시계를 본다.

local Lighting = game:GetService("Lighting")
local Workspace = game:GetService("Workspace")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Shared")

local Clock = require(Shared.Clock)

local DayNight = {}

local origin = 0

function DayNight.start()
	-- 서버가 켜지면 아침 조금 뒤에서 시작한다
	origin = Workspace:GetServerTimeNow() - 60
	Workspace:SetAttribute(Clock.ATTRIBUTE, origin)
	DayNight.tick()
end

-- 한 바퀴 안의 지금 초
function DayNight.time(): number
	return (Workspace:GetServerTimeNow() - origin) % Clock.CYCLE
end

function DayNight.phase(): string
	return Clock.phase(DayNight.time())
end

function DayNight.tick()
	Lighting.ClockTime = Clock.clockTime(DayNight.time())
end

return DayNight
