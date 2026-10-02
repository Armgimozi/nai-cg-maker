-- 접속 중에만 있는(저장하지 않는) 플레이어 상태.

export type TribulationState = {
	name: string,
	wave: number,
	waves: number,
	targetStep: number,
}

export type Session = {
	meditating: boolean,
	anchor: Vector3?, -- 운기조식을 시작한 자리
	veinId: string?, -- 지금 서 있는 영맥
	veinMult: number,
	veinBlocked: string?, -- 서 있지만 경지가 모자라 못 쓰는 영맥
	tribulation: TribulationState?,
	lastRequest: number,
	cooldowns: { [string]: number }, -- 술법별로 다시 쓸 수 있는 os.clock() 시각
	shieldUntil: number, -- 호신강기
	formation: { position: Vector3, untilTime: number }?, -- 취령진
	inFormation: boolean,
	dirty: boolean,
}

local Session = {}

local sessions: { [Player]: Session } = {}

function Session.start(player: Player): Session
	local session: Session = {
		meditating = false,
		anchor = nil,
		veinId = nil,
		veinMult = 1,
		veinBlocked = nil,
		tribulation = nil,
		lastRequest = 0,
		cooldowns = {},
		shieldUntil = 0,
		formation = nil,
		inFormation = false,
		dirty = true,
	}
	sessions[player] = session
	return session
end

function Session.get(player: Player): Session?
	return sessions[player]
end

function Session.stop(player: Player)
	sessions[player] = nil
end

function Session.all(): { [Player]: Session }
	return sessions
end

return Session
