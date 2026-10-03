-- 무기 든 자세와 휘두르기. 순수 계산만 있다 (인스턴스를 만들지 않는다. tests/weapons.luau 가 Lune 에서 검사한다).
--
-- 자세는 "오른손에 쥔 손잡이(Handle)가 윗몸(UpperTorso) 기준 어디서 어느 쪽을 보나"로 적는다.
--   손잡이 틀: +Z 가 날 끝, +X 가 날 쪽(도는 날, 부채는 펼친 쪽). 자리는 기본 R15 몸 크기(스터드)로 적고
--   몸이 작으면 팔 길이 비로 줄인다.
--   어깨·팔꿈치·손목은 그 자리에 손이 오도록 두 마디 IK 로 푼다 (R15 어깨 축이 위팔 가운데에서 비켜난 것까지 그대로 푼다).
--   허리·목·뿌리·엉덩이·무릎은 Animator 가 낸 값에 덧곱하는 각도(도)다. 걷기는 다리 애니메이션이 그대로 한다.
-- 공격은 젖힘(windup) → 벰(strike) → 따라감(follow) → 멈춤(hold) → 거둠(recover).
-- 서버는 휘두르기 요청을 받자마자 피해를 주므로 벰은 0.1초 안팎에 닿는다 (Attack.hit).
--
-- 관절 방향 (엔진에서 잰 값, CFrame.Angles 의 양의 각):
--   어깨 X  팔을 앞으로 든다        어깨 Z  오른팔을 바깥(오른쪽)으로, 왼팔은 안쪽으로
--   팔꿈치 X 아래팔을 앞으로 굽힌다   허리 X  윗몸이 뒤로 젖는다 (앞으로 숙이면 음)
--   허리 Y  윗몸이 왼쪽으로 돈다      허리 Z  윗몸이 왼쪽으로 기운다
--   엉덩이 X 다리를 앞으로 든다      무릎 X  음이면 정강이가 뒤로 접힌다

local WeaponPoses = {}

local rad = math.rad

export type Arm = {
	s0: CFrame, -- 어깨: 윗몸 쪽 붙이개 (Motor6D C0)
	s1: CFrame, -- 어깨: 위팔 쪽 (C1)
	e0: CFrame, -- 팔꿈치: 위팔 쪽
	e1: CFrame, -- 팔꿈치: 아래팔 쪽
	w0: CFrame, -- 손목: 아래팔 쪽
	w1: CFrame, -- 손목: 손 쪽
	grip: CFrame, -- 손의 GripAttachment
}

export type Rig = {
	right: Arm,
	left: Arm,
	scale: number, -- 기본 R15 에 견준 팔 길이
}

-- 한 순간의 자세. 모든 칸이 다 있어야 섞을 수 있다 (WeaponPoses.pose 가 빈 칸을 채운다)
export type Pose = {
	grip: CFrame, -- 오른손 손잡이 틀 (윗몸 기준, 기본 몸 크기)
	pole: Vector3, -- 오른 팔꿈치가 나갈 쪽 (윗몸 기준)
	left: CFrame, -- 왼손이 자루를 잡지 않을 때 왼손 틀 (윗몸 기준, 손 가운데)
	lpole: Vector3,
	hold: number, -- 왼손이 자루를 잡는 자리: 손잡이에서 +Z 로 몇 스터드
	holdRoll: number, -- 그때 왼손을 자루 둘레로 돌린 각(도)
	holdW: number, -- 1 이면 왼손이 자루를 잡는다, 0 이면 left 틀
	waist: Vector3, -- 허리 덧각 (도)
	neck: Vector3,
	root: Vector3, -- 몸 전체를 미는 거리 (스터드, 뿌리 기준. 앞이 -Z)
	rootTurn: Vector3, -- 몸 전체 덧각 (도)
	hipR: Vector3,
	hipL: Vector3,
	kneeR: number,
	kneeL: number,
}

export type Attack = {
	windup: number,
	strike: number,
	follow: number,
	hold: number,
	recover: number,
	duration: number, -- 다 합친 길이
	hit: number, -- 벰이 닿는 때 (초)
	keys: { windup: Pose, path: { Pose }, follow: Pose },
}

-- 기본 R15 (엔진에서 잰 붙이개 자리). 실제 몸은 WeaponAnim 이 관절에서 다시 잰다
local GA = CFrame.new(0, -0.158, 0) * CFrame.Angles(-math.pi / 2, 0, 0)
local function arm(side: number): Arm
	return {
		s0 = CFrame.new(0.972 * side, 0.598, 0),
		s1 = CFrame.new(-0.501 * side, 0.419, 0),
		e0 = CFrame.new(0, -0.355, 0),
		e1 = CFrame.new(0, 0.275, 0),
		w0 = CFrame.new(0, -0.532, 0),
		w1 = CFrame.new(0, 0.132, 0),
		grip = GA,
	}
end
WeaponPoses.DEFAULT_RIG = { right = arm(1), left = arm(-1), scale = 1 } :: Rig
-- 기본 R15 의 뿌리·허리·목·엉덩이·무릎 붙이개 (테스트의 FK 와 몸 크기 재기에 쓴다)
WeaponPoses.DEFAULT_BODY = {
	Root = { CFrame.new(0, -1, 0), CFrame.new(0, -0.2, 0) },
	Waist = { CFrame.new(0, 0.2, 0), CFrame.new(0, -0.849, 0) },
	Neck = { CFrame.new(0, 0.849, 0), CFrame.new(0, -0.576, 0) },
	RightHip = { CFrame.new(0.5, -0.2, 0), CFrame.new(0, 0.471, 0) },
	LeftHip = { CFrame.new(-0.5, -0.2, 0), CFrame.new(0, 0.471, 0) },
	RightKnee = { CFrame.new(0, -0.449, 0), CFrame.new(0, 0.413, 0) },
	LeftKnee = { CFrame.new(0, -0.449, 0), CFrame.new(0, 0.413, 0) },
}
local DEFAULT_REACH = 0.922 + 0.807 -- 어깨 축→팔꿈치, 팔꿈치→손목

-- 도구 Grip. 손잡이 +Z(날)가 주먹 엄지 쪽(손 -Z)으로, +X(날 쪽)가 손가락 끝 쪽(손 -Y)으로 나온다.
-- 팔을 내리면 날이 앞을 보고, 기본 도구 자세(팔을 앞으로 듦)에서는 날이 위로 서고 날 쪽이 앞을 본다
local HANDLE_IN_HAND = CFrame.fromMatrix(Vector3.zero, Vector3.new(0, -1, 0), Vector3.new(-1, 0, 0))
WeaponPoses.GRIP = (HANDLE_IN_HAND:Inverse() * GA).Rotation :: CFrame

-- 무기마다 이어치기 수 (서버 CombatService 도 같은 수로 돈다)
WeaponPoses.COMBO = { sword = 3, saber = 2, spear = 2, fan = 1 } :: { [string]: number }
WeaponPoses.COMBO_RESET = 1.2 -- 이만큼 쉬면 첫 수부터

-- 붙이개 CFrame 으로 몸을 잰다 (WeaponAnim 이 실제 관절의 C0/C1 을 넣는다)
function WeaponPoses.rig(right: Arm, left: Arm): Rig
	local reach = (right.e0.Position - right.s1.Position).Magnitude + (right.w0.Position - right.e1.Position).Magnitude
	return { right = right, left = left, scale = math.clamp(reach / DEFAULT_REACH, 0.3, 2) }
end

-- 도움 함수 --------------------------------------------------------------------------

-- 방향: az 는 앞(-Z)에서 오른쪽(+X)으로 돈 각, el 은 위로 든 각 (도)
local function dir(az: number, el: number): Vector3
	local a, e = rad(az), rad(el)
	return Vector3.new(math.sin(a) * math.cos(e), math.sin(e), -math.cos(a) * math.cos(e))
end
WeaponPoses.dir = dir

-- 손잡이 틀: 자리, 날 끝 쪽, 날 쪽(대충이면 된다. 날에 수직으로 바로잡는다)
local function grip(at: Vector3, blade: Vector3, edge: Vector3): CFrame
	local z = blade.Unit
	local x = edge - z * edge:Dot(z)
	if x.Magnitude < 1e-4 then
		x = Vector3.new(0, 1, 0):Cross(z)
	end
	x = x.Unit
	return CFrame.fromMatrix(at, x, z:Cross(x))
end
WeaponPoses.grip = grip

-- 손 틀: 손 가운데 자리, 손가락이 뻗는 쪽(손 -Y), 손바닥이 보는 쪽(왼손 +X, 오른손 -X)
local function hand(at: Vector3, fingers: Vector3, palm: Vector3, side: number): CFrame
	local y = -fingers.Unit
	local x = palm * side
	x = x - y * x:Dot(y)
	x = x.Unit
	return CFrame.fromMatrix(at, x, y)
end
WeaponPoses.hand = hand

local function v(x: number, y: number, z: number): Vector3
	return Vector3.new(x, y, z)
end

-- 두 벡터 사이 가장 짧게 돌리기
local function between(a: Vector3, b: Vector3): CFrame
	a, b = a.Unit, b.Unit
	local dot = math.clamp(a:Dot(b), -1, 1)
	local axis = a:Cross(b)
	if axis.Magnitude < 1e-6 then
		if dot > 0 then
			return CFrame.identity
		end
		local other = if math.abs(a.X) < 0.9 then Vector3.xAxis else Vector3.yAxis
		return CFrame.fromAxisAngle(a:Cross(other).Unit, math.pi)
	end
	return CFrame.fromAxisAngle(axis.Unit, math.acos(dot))
end

-- 팔 IK ------------------------------------------------------------------------------

-- 팔꿈치 X 각에 따라 어깨 축에서 손목 축까지 (위팔 s1 틀 기준)
local function wristOffset(a: Arm, theta: number): Vector3
	return (a.s1:Inverse() * a.e0 * CFrame.Angles(theta, 0, 0) * a.e1:Inverse() * a.w0).Position
end

-- 손 틀(윗몸 기준)에 손이 오도록 어깨·팔꿈치·손목 Transform 을 푼다. 닿지 않으면 그쪽으로 팔을 뻗는다
local function solveArm(a: Arm, handCF: CFrame, pole: Vector3): (CFrame, CFrame, CFrame)
	local shoulder = a.s0.Position
	local wrist = (handCF * a.w1).Position
	local want = wrist - shoulder
	-- 팔꿈치 각: |v_u + Rx(θ) v_l| = 거리 를 푼다
	local vu = (a.s1:Inverse() * a.e0).Position
	local vl = (a.e1:Inverse() * a.w0).Position
	local eRot = (a.s1:Inverse() * a.e0).Rotation
	local vuE = eRot:Inverse() * vu -- 팔꿈치 틀에서 본 위팔 벡터
	local A = vuE.Y * vl.Y + vuE.Z * vl.Z
	local B = vuE.Z * vl.Y - vuE.Y * vl.Z
	local K = vuE.X * vl.X
	local R = math.sqrt(A * A + B * B)
	local base = vu.Magnitude ^ 2 + vl.Magnitude ^ 2
	local far = math.sqrt(math.max(0, base + 2 * (K + R)))
	local near = math.sqrt(math.max(0, base + 2 * (K - R)))
	local c = math.clamp(want.Magnitude, near + 0.02, far - 0.002)
	local D = (c * c - base) / 2 - K
	local phi = math.atan2(B, A)
	local spread = math.acos(math.clamp(D / math.max(R, 1e-6), -1, 1))
	local theta = phi + spread
	if theta < -0.05 or theta > math.pi + 0.05 then
		theta = phi - spread
	end
	theta = (theta + math.pi) % (2 * math.pi) - math.pi
	-- 어깨: 손목 벡터를 목표 쪽으로 돌리고, 팔꿈치가 pole 쪽으로 가게 그 축으로 돌린다
	local wLocal = wristOffset(a, theta)
	local u = if want.Magnitude > 1e-4 then want.Unit else Vector3.new(0, -1, 0)
	local q = between(wLocal, u)
	local elbow = q * vu
	local e = elbow - u * elbow:Dot(u)
	local p = pole - u * pole:Dot(u)
	local swing = CFrame.identity
	if e.Magnitude > 1e-4 and p.Magnitude > 1e-4 then
		e, p = e.Unit, p.Unit
		local angle = math.atan2(e:Cross(p):Dot(u), e:Dot(p))
		swing = CFrame.fromAxisAngle(u, angle)
	end
	local joint = swing * q -- 위팔 s1 틀의 회전 (윗몸 기준)
	local shoulderT = (a.s0.Rotation:Inverse() * joint).Rotation
	local elbowT = CFrame.Angles(theta, 0, 0)
	-- 손목: 아래팔 끝 틀에서 손 틀까지 남은 회전
	local upper = CFrame.new(shoulder) * joint * a.s1:Inverse()
	local lowerEnd = upper * a.e0 * elbowT * a.e1:Inverse() * a.w0
	local wristT = (lowerEnd:Inverse() * handCF * a.w1).Rotation
	return shoulderT, elbowT, wristT
end
WeaponPoses.solveArm = solveArm

-- 자세 하나를 관절 Transform 으로. arms 는 덮어쓰고(override), body 는 Animator 값에 곱한다(additive)
function WeaponPoses.solve(rig: Rig, pose: Pose): ({ [string]: CFrame }, { [string]: CFrame })
	local s = rig.scale
	local g = pose.grip
	local handle = CFrame.new(g.Position * s) * g.Rotation
	local rightHand = handle * WeaponPoses.GRIP * rig.right.grip:Inverse()
	local rs, re, rw = solveArm(rig.right, rightHand, pose.pole)
	local free = CFrame.new(pose.left.Position * s) * pose.left.Rotation
	local onShaft = handle
		* CFrame.new(0, 0, pose.hold * s)
		* CFrame.Angles(0, 0, rad(pose.holdRoll))
		* WeaponPoses.GRIP
		* rig.left.grip:Inverse()
	local leftHand = if pose.holdW <= 0 then free elseif pose.holdW >= 1 then onShaft else free:Lerp(onShaft, pose.holdW)
	local ls, le, lw = solveArm(rig.left, leftHand, pose.lpole)
	local arms = {
		RightShoulder = rs,
		RightElbow = re,
		RightWrist = rw,
		LeftShoulder = ls,
		LeftElbow = le,
		LeftWrist = lw,
	}
	local function angles(a: Vector3): CFrame
		return CFrame.Angles(rad(a.X), rad(a.Y), rad(a.Z))
	end
	local body = {
		Waist = angles(pose.waist),
		Neck = angles(pose.neck),
		Root = CFrame.new(pose.root * s) * angles(pose.rootTurn),
		RightHip = angles(pose.hipR),
		LeftHip = angles(pose.hipL),
		RightKnee = CFrame.Angles(rad(pose.kneeR), 0, 0),
		LeftKnee = CFrame.Angles(rad(pose.kneeL), 0, 0),
	}
	return arms, body
end

-- 섞기 -------------------------------------------------------------------------------

function WeaponPoses.lerp(a: Pose, b: Pose, t: number): Pose
	if t <= 0 then
		return a
	elseif t >= 1 then
		return b
	end
	return {
		grip = a.grip:Lerp(b.grip, t),
		pole = a.pole:Lerp(b.pole, t),
		left = a.left:Lerp(b.left, t),
		lpole = a.lpole:Lerp(b.lpole, t),
		hold = a.hold + (b.hold - a.hold) * t,
		holdRoll = a.holdRoll + (b.holdRoll - a.holdRoll) * t,
		holdW = a.holdW + (b.holdW - a.holdW) * t,
		waist = a.waist:Lerp(b.waist, t),
		neck = a.neck:Lerp(b.neck, t),
		root = a.root:Lerp(b.root, t),
		rootTurn = a.rootTurn:Lerp(b.rootTurn, t),
		hipR = a.hipR:Lerp(b.hipR, t),
		hipL = a.hipL:Lerp(b.hipL, t),
		kneeR = a.kneeR + (b.kneeR - a.kneeR) * t,
		kneeL = a.kneeL + (b.kneeL - a.kneeL) * t,
	}
end

local EASE = {
	linear = function(t: number): number
		return t
	end,
	-- 빨라지며 들어간다 (벰)
	["in"] = function(t: number): number
		return t * t
	end,
	-- 빠르게 나가 멈춘다 (젖힘, 따라감)
	out = function(t: number): number
		local u = 1 - t
		return 1 - u * u * u
	end,
	inOut = function(t: number): number
		return if t < 0.5 then 4 * t * t * t else 1 - (-2 * t + 2) ^ 3 / 2
	end,
}
WeaponPoses.EASE = EASE

-- 자세 적기 ---------------------------------------------------------------------------

local ZERO = Vector3.zero

-- 빈 칸을 base 에서 채운다
local function pose(base: Pose?, fields: { [string]: any }): Pose
	local out = table.clone(base or {} :: any)
	for key, value in fields do
		out[key] = value
	end
	out.pole = out.pole or v(1, -0.6, 0.4)
	out.lpole = out.lpole or v(-1, -0.6, 0.4)
	out.hold = out.hold or 1.2
	out.holdRoll = out.holdRoll or 0
	out.holdW = out.holdW or 0
	out.waist = out.waist or ZERO
	out.neck = out.neck or ZERO
	out.root = out.root or ZERO
	out.rootTurn = out.rootTurn or ZERO
	out.hipR = out.hipR or ZERO
	out.hipL = out.hipL or ZERO
	out.kneeR = out.kneeR or 0
	out.kneeL = out.kneeL or 0
	out.left = out.left or hand(v(-1.45, -1.15, 0.05), v(0, -1, 0), v(1, 0, 0), 1)
	assert(out.grip, "grip 이 없다")
	return out :: Pose
end
WeaponPoses.pose = pose

-- 무기마다: 든 자세(idle)와 이어치기 ----------------------------------------------------------

type Def = { idle: Pose, attacks: { Attack } }
local DEFS: { [string]: Def } = {}

local function attack(timing: { number }, keys: { windup: Pose, path: { Pose }, follow: Pose }, hitAt: number?): Attack
	local windup, strike, follow, hold, recover = timing[1], timing[2], timing[3], timing[4], timing[5]
	return {
		windup = windup,
		strike = strike,
		follow = follow,
		hold = hold,
		recover = recover,
		duration = windup + strike + follow + hold + recover,
		hit = windup + strike * (hitAt or 0.7),
		keys = keys,
	}
end

-- 검: 한 손 중단세. 칼끝이 앞 위를 보고, 왼손은 검결(손가락 둘을 세운 손)
do
	local idle = pose(nil, {
		grip = grip(v(0.62, -0.95, -1.05), dir(-8, 38), v(0, -1, -0.3)),
		pole = v(1, -0.5, 0.5),
		left = hand(v(-0.95, 0.2, -0.95), dir(30, 70), v(1, 0, 0.3), 1),
		lpole = v(-1, -0.4, 0.2),
		waist = v(0, 8, 0),
		neck = v(0, -6, 0),
	})
	local swing1 = attack({ 0.05, 0.07, 0.08, 0.06, 0.22 }, {
		-- 오른 어깨 위로 젖혔다가 왼 허리로 비스듬히 벤다
		windup = pose(idle, {
			grip = grip(v(1.15, 1.15, -0.25), dir(130, 55), v(0.5, 1, 0.3)),
			pole = v(1, 0.2, 0.6),
			waist = v(0, 22, -4),
			neck = v(0, -18, 0),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.55, 0.5, -1.35), dir(15, 40), v(1, 0.3, 0)),
				pole = v(1, 0, 0.5),
				waist = v(0, 0, 0),
				neck = v(0, 0, 0),
			}),
			pose(idle, {
				grip = grip(v(-0.45, -0.85, -1.2), dir(-95, -30), v(0, -1, -0.5)),
				pole = v(1, -0.3, 0.3),
				waist = v(-6, -25, 4),
				neck = v(0, 20, 0),
			}),
		},
		follow = pose(idle, {
			grip = grip(v(-0.75, -1.1, -0.6), dir(-140, -35), v(0, -1, 0.3)),
			pole = v(1, -0.2, 0.2),
			waist = v(-8, -32, 5),
			neck = v(0, 26, 0),
		}),
	})
	local swing2 = attack({ 0.05, 0.07, 0.08, 0.06, 0.22 }, {
		-- 왼쪽으로 감았다가 가슴 높이로 가로 벤다 (왼→오)
		windup = pose(idle, {
			grip = grip(v(-0.7, -0.2, -0.8), dir(-150, 5), v(0, 0.2, -1)),
			pole = v(1, -0.6, -0.2),
			waist = v(0, -30, 0),
			neck = v(0, 24, 0),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.2, -0.1, -1.55), dir(-10, 8), v(1, 0, 0)),
				pole = v(1, -0.5, 0.3),
				waist = v(0, -5, 0),
				neck = v(0, 4, 0),
			}),
			pose(idle, {
				grip = grip(v(1.25, -0.15, -1.2), dir(80, 5), v(0.2, 0, 1)),
				pole = v(1, -0.3, 0.5),
				waist = v(0, 20, 0),
				neck = v(0, -16, 0),
			}),
		},
		follow = pose(idle, {
			grip = grip(v(1.55, -0.2, -0.5), dir(125, 0), v(-0.3, 0, 1)),
			pole = v(1, -0.2, 0.6),
			waist = v(0, 28, 0),
			neck = v(0, -22, 0),
		}),
	})
	local swing3 = attack({ 0.05, 0.07, 0.1, 0.08, 0.24 }, {
		-- 오른 아래에서 왼 위로 올려 벤다
		windup = pose(idle, {
			grip = grip(v(1.15, -1.2, -0.2), dir(150, -25), v(0, -1, 0.4)),
			pole = v(1, -0.3, 0.6),
			waist = v(4, 26, -4),
			neck = v(0, -20, 0),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.5, -0.7, -1.4), dir(20, -5), v(-0.4, 1, 0)),
				pole = v(1, -0.4, 0.4),
				waist = v(0, 5, 0),
				neck = v(0, -4, 0),
			}),
			pose(idle, {
				grip = grip(v(-0.5, 0.6, -1.15), dir(-60, 50), v(-1, 0.6, 0)),
				pole = v(0.6, -0.8, 0.2),
				waist = v(-4, -22, -3),
				neck = v(0, 18, 0),
			}),
		},
		follow = pose(idle, {
			grip = grip(v(-0.7, 1.1, -0.7), dir(-90, 70), v(-1, 0.2, 0.5)),
			pole = v(0.6, -0.8, 0),
			waist = v(-6, -28, -4),
			neck = v(0, 22, 0),
		}),
	})
	DEFS.sword = { idle = idle, attacks = { swing1, swing2, swing3 } }
end

-- 도: 오른 허리에 비껴 들고 왼손은 칼등 곁. 머리 위로 크게 들어 비스듬히 내리찍는다
do
	local idle = pose(nil, {
		grip = grip(v(0.75, -1.05, -0.85), dir(15, 30), v(0, -0.6, -1)),
		pole = v(1, -0.6, 0.4),
		left = hand(v(-0.55, -0.35, -1.0), dir(40, 30), v(1, 0, 0), 1),
		lpole = v(-1, -0.6, 0.2),
		waist = v(0, 12, 0),
		neck = v(0, -10, 0),
	})
	local chop = attack({ 0.07, 0.07, 0.12, 0.12, 0.35 }, {
		windup = pose(idle, {
			grip = grip(v(0.7, 1.55, 0.1), dir(160, 40), v(0, 1, -0.6)),
			pole = v(1, 0.6, 0.3),
			holdW = 1,
			hold = -0.55,
			holdRoll = 0,
			lpole = v(-1, 0.2, 0.3),
			waist = v(10, 18, -6),
			neck = v(-8, -14, 0),
			root = v(0, 0.05, 0.25),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.35, 1.0, -1.35), dir(5, 45), v(0, 0.3, -1)),
				pole = v(1, 0.1, 0.3),
				holdW = 1,
				hold = -0.55,
				lpole = v(-1, -0.2, 0.3),
				waist = v(-6, 5, 0),
				neck = v(0, -4, 0),
				root = v(0, -0.05, -0.2),
			}),
			pose(idle, {
				grip = grip(v(-0.2, -1.05, -1.3), dir(-40, -35), v(0, -1, -0.4)),
				pole = v(1, -0.4, 0.2),
				holdW = 1,
				hold = -0.55,
				lpole = v(-1, -0.6, 0.2),
				waist = v(-22, -12, 6),
				neck = v(16, 8, 0),
				root = v(0, -0.35, -0.55),
				hipR = v(-12, 0, 0),
				hipL = v(30, 0, 0),
				kneeL = -25,
				kneeR = -12,
			}),
		},
		follow = pose(idle, {
			grip = grip(v(-0.5, -1.35, -0.95), dir(-70, -50), v(0, -1, 0.2)),
			pole = v(1, -0.5, 0.1),
			holdW = 1,
			hold = -0.55,
			lpole = v(-1, -0.6, 0.2),
			waist = v(-26, -16, 8),
			neck = v(20, 10, 0),
			root = v(0, -0.45, -0.6),
			hipR = v(-14, 0, 0),
			hipL = v(34, 0, 0),
			kneeL = -30,
			kneeR = -15,
		}),
	})
	local sweep = attack({ 0.07, 0.07, 0.12, 0.12, 0.35 }, {
		-- 왼쪽으로 감아 허리 높이로 크게 가로 벤다 (왼→오)
		windup = pose(idle, {
			grip = grip(v(-0.9, 0.1, 0.2), dir(-170, 15), v(0, 0, -1)),
			pole = v(1, -0.4, -0.3),
			waist = v(0, -40, 0),
			neck = v(0, 32, 0),
			root = v(0, -0.15, 0),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0, -0.6, -1.5), dir(-15, 0), v(1, -0.2, 0)),
				pole = v(1, -0.6, 0.3),
				waist = v(-6, -8, 0),
				neck = v(0, 6, 0),
				root = v(0, -0.3, -0.3),
			}),
			pose(idle, {
				grip = grip(v(1.3, -0.5, -1.05), dir(85, -5), v(0, 0, 1)),
				pole = v(1, -0.4, 0.5),
				waist = v(-8, 25, 0),
				neck = v(0, -20, 0),
				root = v(0, -0.3, -0.35),
			}),
		},
		follow = pose(idle, {
			grip = grip(v(1.5, -0.5, -0.3), dir(140, -10), v(-0.4, 0, 1)),
			pole = v(1, -0.3, 0.6),
			waist = v(-8, 38, 0),
			neck = v(0, -30, 0),
			root = v(0, -0.3, -0.3),
		}),
	})
	DEFS.saber = { idle = idle, attacks = { chop, sweep } }
end

-- 창: 허리 높이에 수평으로 앞을 겨누고 두 손으로 쥔다 (오른손 뒤, 왼손 앞)
do
	local idle = pose(nil, {
		grip = grip(v(0.55, -1.05, -0.35), dir(-6, 3), v(0, -1, 0)),
		pole = v(1, -0.5, 0.6),
		holdW = 1,
		hold = 1.6,
		holdRoll = 0,
		lpole = v(-1, -0.8, 0),
		waist = v(0, 18, 0),
		neck = v(0, -14, 0),
	})
	local thrust = attack({ 0.05, 0.06, 0.1, 0.1, 0.25 }, {
		windup = pose(idle, {
			grip = grip(v(0.65, -0.95, 0.25), dir(-4, 4), v(0, -1, 0)),
			hold = 1.5,
			waist = v(4, 26, 0),
			neck = v(0, -22, 0),
			root = v(0, 0, 0.2),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.2, -0.9, -1.9), dir(-2, 2), v(0, -1, 0)),
				hold = 1.0,
				pole = v(1, -0.6, 0.2),
				lpole = v(-1, -0.6, -0.2),
				waist = v(-8, 2, 0),
				neck = v(6, -2, 0),
				root = v(0, -0.3, -1.0),
				hipL = v(35, 0, 0),
				hipR = v(-20, 0, 0),
				kneeL = -30,
				kneeR = -10,
			}),
		},
		follow = pose(idle, {
			grip = grip(v(0.1, -0.85, -2.2), dir(-1, 1), v(0, -1, 0)),
			hold = 0.9,
			pole = v(1, -0.6, 0.1),
			lpole = v(-1, -0.6, -0.2),
			waist = v(-10, 0, 0),
			neck = v(8, 0, 0),
			root = v(0, -0.35, -1.2),
			hipL = v(38, 0, 0),
			hipR = v(-22, 0, 0),
			kneeL = -34,
			kneeR = -12,
		}),
	}, 1)
	local sweep = attack({ 0.05, 0.07, 0.1, 0.1, 0.25 }, {
		-- 창끝으로 앞을 오른쪽에서 왼쪽으로 크게 쓸어 벤다
		windup = pose(idle, {
			grip = grip(v(-0.1, -0.85, 0.1), dir(60, 8), v(0, -1, 0)),
			hold = 1.4,
			waist = v(0, 35, 0),
			neck = v(0, -28, 0),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.4, -0.9, -0.7), dir(0, 2), v(0, -1, 0)),
				hold = 1.4,
				waist = v(-4, 5, 0),
				neck = v(0, -4, 0),
				root = v(0, -0.15, -0.4),
			}),
			pose(idle, {
				grip = grip(v(0.9, -0.8, -0.6), dir(-65, 0), v(0, -1, 0)),
				hold = 1.4,
				pole = v(1, -0.3, 0.6),
				waist = v(-4, -28, 0),
				neck = v(0, 22, 0),
				root = v(0, -0.2, -0.5),
			}),
		},
		follow = pose(idle, {
			grip = grip(v(1.1, -0.75, -0.3), dir(-95, 0), v(0, -1, 0)),
			hold = 1.4,
			pole = v(1, -0.2, 0.6),
			waist = v(-4, -38, 0),
			neck = v(0, 30, 0),
			root = v(0, -0.2, -0.5),
		}),
	})
	DEFS.spear = { idle = idle, attacks = { thrust, sweep } }
end

-- 부채: 펼친 부채를 가슴 앞 오른쪽에 세워 든다. 왼쪽으로 감았다가 크게 펼쳐 쳐서 바람칼을 날린다
do
	local idle = pose(nil, {
		grip = grip(v(0.7, -0.15, -1.0), dir(-20, 62), v(-1, 0.2, -0.3)),
		pole = v(1, -0.8, 0.3),
		left = hand(v(-0.8, -0.85, -0.55), dir(20, -40), v(1, 0, 0), 1),
		lpole = v(-1, -0.6, 0.2),
		waist = v(0, 10, 0),
		neck = v(0, -8, 0),
	})
	local flick = attack({ 0.06, 0.07, 0.12, 0.12, 0.35 }, {
		windup = pose(idle, {
			grip = grip(v(-0.55, 0.45, -0.75), dir(-120, 30), v(0, 0.4, -1)),
			pole = v(1, -0.2, -0.4),
			waist = v(0, -32, 0),
			neck = v(0, 26, 0),
		}),
		path = {
			pose(idle, {
				grip = grip(v(0.3, 0.2, -1.55), dir(-15, 20), v(1, 0, 0)),
				pole = v(1, -0.5, 0.2),
				waist = v(-4, -4, 0),
				neck = v(0, 4, 0),
				root = v(0, 0, -0.2),
			}),
			pose(idle, {
				grip = grip(v(1.4, 0.05, -1.05), dir(70, 15), v(0, 0, 1)),
				pole = v(1, -0.4, 0.4),
				waist = v(-4, 24, 0),
				neck = v(0, -18, 0),
				root = v(0, 0, -0.25),
			}),
		},
		follow = pose(idle, {
			grip = grip(v(1.6, 0, -0.55), dir(105, 10), v(-0.4, 0, 1)),
			pole = v(1, -0.3, 0.6),
			waist = v(-4, 32, 0),
			neck = v(0, -24, 0),
			root = v(0, 0, -0.25),
		}),
	})
	DEFS.fan = { idle = idle, attacks = { flick } }
end

WeaponPoses.DEFS = DEFS

-- 든 자세 (숨 쉬듯 조금 오르내린다)
function WeaponPoses.idle(kind: string, t: number): Pose
	local def = DEFS[kind] or DEFS.sword
	local base = def.idle
	local breathe = math.sin(t * 2.1)
	local out = table.clone(base)
	out.grip = CFrame.new(0, 0.035 * breathe, 0) * base.grip
	out.left = CFrame.new(0, 0.03 * breathe, 0) * base.left
	out.waist = base.waist + Vector3.new(-1.2 * breathe, 0, 0)
	return out
end

-- 이어치기 n 번째 (1 부터, 수를 넘으면 돌아간다)
function WeaponPoses.attack(kind: string, combo: number): Attack
	local def = DEFS[kind] or DEFS.sword
	local n = #def.attacks
	return def.attacks[((math.max(1, combo) - 1) % n) + 1]
end

-- 공격 t 초 째 자세. from 은 공격을 시작할 때 자세, idle 은 돌아갈 자세
function WeaponPoses.sample(a: Attack, from: Pose, idle: Pose, t: number): Pose
	local keys = a.keys
	if t <= 0 then
		return from
	end
	if t < a.windup then
		return WeaponPoses.lerp(from, keys.windup, EASE.out(t / a.windup))
	end
	t -= a.windup
	if t < a.strike then
		-- 벰: 젖힌 자리에서 길을 따라 빨라지며 간다
		local u = EASE["in"](t / a.strike) * #keys.path
		local i = math.min(math.floor(u), #keys.path - 1)
		local prev = if i == 0 then keys.windup else keys.path[i]
		return WeaponPoses.lerp(prev, keys.path[i + 1], u - i)
	end
	t -= a.strike
	local last = keys.path[#keys.path]
	if t < a.follow then
		return WeaponPoses.lerp(last, keys.follow, EASE.out(t / a.follow))
	end
	t -= a.follow
	if t < a.hold then
		return keys.follow
	end
	t -= a.hold
	if t < a.recover then
		return WeaponPoses.lerp(keys.follow, idle, EASE.inOut(t / a.recover))
	end
	return idle
end

-- 공격의 어느 마디인가: "windup" | "strike" | "follow" | "hold" | "recover" | "done"
function WeaponPoses.phase(a: Attack, t: number): string
	if t < a.windup then
		return "windup"
	elseif t < a.windup + a.strike then
		return "strike"
	elseif t < a.windup + a.strike + a.follow then
		return "follow"
	elseif t < a.windup + a.strike + a.follow + a.hold then
		return "hold"
	elseif t < a.duration then
		return "recover"
	end
	return "done"
end

return WeaponPoses
