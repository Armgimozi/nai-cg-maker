-- 서버 공용 낮밤. 한 바퀴 12분: 낮 7분, 해질녘 30초, 밤 4분, 새벽 30초.
-- 서버가 Workspace 속성 "CycleOrigin"(서버 시각)을 정하면 모두 같은 시계를 본다.

local Clock = {}

Clock.CYCLE = 720
Clock.ATTRIBUTE = "CycleOrigin"

-- 한 바퀴 안의 구간: 시작 초, 길이, Lighting.ClockTime 시작·끝
local SEGMENTS = {
	{ phase = "day", start = 0, length = 420, from = 6, to = 18 },
	{ phase = "dusk", start = 420, length = 30, from = 18, to = 20 },
	{ phase = "night", start = 450, length = 240, from = 20, to = 28 },
	{ phase = "dawn", start = 690, length = 30, from = 4, to = 6 },
}
Clock.SEGMENTS = SEGMENTS

Clock.PHASE_NAME = { day = "낮", dusk = "해질녘", night = "밤", dawn = "새벽" }

local function wrap(t: number): number
	return t % Clock.CYCLE
end

local function segmentAt(t: number)
	t = wrap(t)
	for _, segment in SEGMENTS do
		if t < segment.start + segment.length then
			return segment, t - segment.start
		end
	end
	return SEGMENTS[1], 0
end

function Clock.phase(t: number): string
	return (segmentAt(t)).phase
end

-- Lighting.ClockTime 값
function Clock.clockTime(t: number): number
	local segment, into = segmentAt(t)
	local value = segment.from + (segment.to - segment.from) * (into / segment.length)
	return value % 24
end

-- 지금부터 phase 가 시작할 때까지 남은 초 (이미 그 구간이면 0)
function Clock.untilPhase(t: number, phase: string): number
	t = wrap(t)
	local current, _ = segmentAt(t)
	if current.phase == phase then
		return 0
	end
	for _, segment in SEGMENTS do
		if segment.phase == phase then
			return (segment.start - t) % Clock.CYCLE
		end
	end
	return 0
end

-- 지금 구간이 끝날 때까지 남은 초
function Clock.remaining(t: number): number
	local segment, into = segmentAt(t)
	return segment.length - into
end

-- 칠성제의 시운: 고른 칠수가 밤하늘 천정에 오는 동안. 칠수마다 밤의 다른 때에 온다.
-- 시운 길이는 영근에 따라 다르다(Roots.window). 반환: 밤 시작부터 센 시작 초, 끝 초
local SIGUN_CENTER = { cheong = 0.2, eum = 0.4, baek = 0.6, yang = 0.8 }

function Clock.sigun(chilsu: string, window: number): (number, number)
	local night = SEGMENTS[3]
	local center = night.length * (SIGUN_CENTER[chilsu] or 0.5)
	local from = math.max(0, center - window / 2)
	local to = math.min(night.length, center + window / 2)
	return night.start + from, night.start + to
end

-- 시운 안인가, 아니면 다음 시운까지 몇 초인가. 반환: 안이면 true 와 남은 초, 밖이면 false 와 기다릴 초
function Clock.sigunState(t: number, chilsu: string, window: number): (boolean, number)
	t = wrap(t)
	local from, to = Clock.sigun(chilsu, window)
	if t >= from and t < to then
		return true, to - t
	end
	return false, (from - t) % Clock.CYCLE
end

-- "3분 12초", "40초"
function Clock.format(seconds: number): string
	seconds = math.max(0, math.floor(seconds))
	local minutes = seconds // 60
	local rest = seconds % 60
	if minutes > 0 and rest > 0 then
		return string.format("%d분 %d초", minutes, rest)
	elseif minutes > 0 then
		return string.format("%d분", minutes)
	end
	return string.format("%d초", rest)
end

return Clock
