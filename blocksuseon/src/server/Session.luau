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
