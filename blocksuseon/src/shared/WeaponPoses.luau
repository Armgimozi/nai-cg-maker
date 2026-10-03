-- 무기 든 자세와 휘두르기. 순수 계산만 있다 (인스턴스를 만들지 않는다. tests/weapons.luau 가 Lune 에서 검사한다).
--
-- 자세는 "오른손에 쥔 손잡이(Handle)가 윗몸(UpperTorso) 기준 어디서 어느 쪽을 보나"로 적는다.
--   at     손잡이 자리 (윗몸 가운데 기준, 기본 R15 몸 크기 스터드. 몸이 작으면 팔 길이 비로 줄인다)
--   blade  날 끝이 향한 쪽 (손잡이 +Z)
--   edge   날 쪽(손잡이 +X)이 보았으면 하는 쪽. 손목이 꺾이지 않는 데까지만 따른다 (0 이면 손목을 곧게)
--   어깨·팔꿈치·손목은 그 자리에 손이 오도록 두 마디 IK 로 푼다 (R15 어깨 축이 위팔 가운데에서 비켜난 것까지 그대로)
--   허리·목·뿌리·엉덩이·무릎은 Animator 가 낸 값에 덧곱하는 각도(도)다. 걷기는 다리 애니메이션이 그대로 한다.
-- 공격은 젖힘(windup) → 벰(strike) → 따라감(follow) → 멈춤(hold) → 거둠(recover).
-- 서버는 휘두르기 요청을 받자마자 피해를 주므로 벰은 0.1초 안팎에 닿는다 (Attack.hit).
--
-- 관절 방향 (엔진의 R15 붙이개로 잰 값, CFrame.Angles 의 양의 각):
--   어깨 X  팔을 앞으로 든다          팔꿈치 X 아래팔을 앞으로 굽힌다
--   허리 X  윗몸이 뒤로 젖는다 (숙이면 음)  허리 Y  윗몸이 왼쪽으로 돈다   허리 Z  윗몸이 왼쪽으로 기운다
--   엉덩이 X 다리를 앞으로 든다        무릎 X  음이면 정강이가 뒤로 접힌다   뿌리 -Z 몸이 앞으로 나간다

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

-- 한 순간의 자세. 모든 칸이 있어야 섞을 수 있다 (WeaponPoses.pose 가 빈 칸을 채운다)
export type Pose = {
	at: Vector3, -- 오른손 손잡이 자리 (윗몸 기준)
	blade: Vector3, -- 날 끝 쪽
	edge: Vector3, -- 날 쪽 (0 이면 손목을 곧게)
	pole: Vector3, -- 오른 팔꿈치가 나갈 쪽
	left: CFrame, -- 왼손이 자루를 잡지 않을 때 왼손 틀 (윗몸 기준, 손 가운데)
	lpole: Vector3,
	hold: number, -- 왼손이 자루를 잡는 자리: 손잡이에서 날 쪽으로 몇 스터드 (음이면 손잡이 끝 쪽)
	holdW: number, -- 1 이면 왼손이 자루를 잡는다, 0 이면 left 틀
	waist: Vector3, -- 허리 덧각 (도)
	neck: Vector3,
	root: Vector3, -- 몸 전체를 미는 거리 (스터드, 앞이 -Z)
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
local function defaultArm(side: number): Arm
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
WeaponPoses.DEFAULT_RIG = { right = defaultArm(1), left = defaultArm(-1), scale = 1 } :: Rig
-- 기본 R15 의 몸 관절 붙이개 (C0, C1). 테스트의 FK 에 쓴다
WeaponPoses.DEFAULT_BODY = {
	Root = { CFrame.new(0, -1, 0), CFrame.new(0, -0.2, 0) },
	Waist = { CFrame.new(0, 0.2, 0), CFrame.new(0, -0.849, 0) },
	Neck = { CFrame.new(0, 0.849, 0), CFrame.new(0, -0.576, 0) },
	RightHip = { CFrame.new(0.5, -0.2, 0), CFrame.new(0, 0.471, 0) },
	LeftHip = { CFrame.new(-0.5, -0.2, 0), CFrame.new(0, 0.471, 0) },
	RightKnee = { CFrame.new(0, -0.449, 0), CFrame.new(0, 0.413, 0) },
	LeftKnee = { CFrame.new(0, -0.449, 0), CFrame.new(0, 0.413, 0) },
	RightAnkle = { CFrame.new(0, -0.596, 0), CFrame.new(0, 0.106, 0) },
	LeftAnkle = { CFrame.new(0, -0.596, 0), CFrame.new(0, 0.106, 0) },
}
local DEFAULT_REACH = 0.922 + 0.807 -- 어깨 축→팔꿈치, 팔꿈치→손목
local MAX_BEND = rad(50) -- 손목이 아래팔에서 꺾이는 데까지

-- 도구 Grip. 손잡이 +Z(날)가 주먹 엄지 쪽(손 -Z)으로 나오되 손가락 쪽(손 -Y)으로 TILT 만큼 기운다
-- (주먹 속에서 자루가 비스듬히 놓이는 그대로). +X(날 쪽)는 손가락 끝 쪽을 본다.
-- 기본 도구 자세(팔을 앞으로 듦)에서는 날이 위로 서되 앞으로 30도 기운다
local TILT = rad(30)
local HANDLE_IN_HAND = CFrame.fromMatrix(
	Vector3.zero,
	Vector3.new(0, -math.cos(TILT), math.sin(TILT)),
	Vector3.new(-1, 0, 0)
)
WeaponPoses.GRIP = (HANDLE_IN_HAND:Inverse() * GA).Rotation :: CFrame
-- 손가락 쪽(손 -Y)을 손잡이 틀로 보면 날 쪽(+X)으로 cos, 날 끝(+Z)으로 sin
local FINGER_EDGE, FINGER_BLADE = math.cos(TILT), math.sin(TILT)

-- 무기마다 이어치기 수 (서버 CombatService 도 같은 수로 돈다)
WeaponPoses.COMBO = { sword = 3, saber = 2, spear = 2, fan = 1 } :: { [string]: number }
WeaponPoses.COMBO_RESET = 1.2 -- 이만큼 쉬면 첫 수부터

-- 붙이개 CFrame 으로 몸을 잰다 (WeaponAnim 이 실제 관절의 C0/C1 을 넣는다)
function WeaponPoses.rig(right: Arm, left: Arm): Rig
	local reach = (right.e0.Position - right.s1.Position).Magnitude + (right.w0.Position - right.e1.Position).Magnitude
	return { right = right, left = left, scale = math.clamp(reach / DEFAULT_REACH, 0.3, 2) }
end

-- 도움 함수 --------------------------------------------------------------------------

local function v(x: number, y: number, z: number): Vector3
	return Vector3.new(x, y, z)
end

-- 방향: az 는 앞(-Z)에서 오른쪽(+X)으로 돈 각, el 은 위로 든 각 (도)
local function dir(az: number, el: number): Vector3
	local a, e = rad(az), rad(el)
	return Vector3.new(math.sin(a) * math.cos(e), math.sin(e), -math.cos(a) * math.cos(e))
end
WeaponPoses.dir = dir

-- 손 틀: 손 가운데 자리, 손가락이 뻗는 쪽(손 -Y), 손바닥이 보는 쪽 (왼손 기준. 왼손 손바닥은 +X)
local function hand(at: Vector3, fingers: Vector3, palm: Vector3): CFrame
	local y = -fingers.Unit
	local x = palm - y * palm:Dot(y)
	return CFrame.fromMatrix(at, x.Unit, y)
end
WeaponPoses.hand = hand

-- a 에서 b 로 가장 짧게 돌리는 축과 각
local function axisAngle(a: Vector3, b: Vector3): (Vector3, number)
	a, b = a.Unit, b.Unit
	local dot = math.clamp(a:Dot(b), -1, 1)
	local axis = a:Cross(b)
	if axis.Magnitude < 1e-6 then
		if dot > 0 then
			return Vector3.xAxis, 0
		end
		local other = if math.abs(a.X) < 0.9 then Vector3.xAxis else Vector3.yAxis
		return a:Cross(other).Unit, math.pi
	end
	return axis.Unit, math.acos(dot)
end

local function between(a: Vector3, b: Vector3): CFrame
	local axis, angle = axisAngle(a, b)
	return CFrame.fromAxisAngle(axis, angle)
end

local function slerp(a: Vector3, b: Vector3, t: number): Vector3
	local axis, angle = axisAngle(a, b)
	return CFrame.fromAxisAngle(axis, angle * t) * a.Unit
end

local function flat(a: Vector3, n: Vector3): Vector3
	return a - n * a:Dot(n)
end

-- 팔 IK ------------------------------------------------------------------------------

-- 손 틀(윗몸 기준)에 손이 오도록 어깨·팔꿈치·손목 Transform 을 푼다. 닿지 않으면 그쪽으로 팔을 뻗는다.
-- 넷째 값은 아래팔이 뻗은 쪽 (팔꿈치→손목)
local function solveArm(a: Arm, handCF: CFrame, pole: Vector3): (CFrame, CFrame, CFrame, Vector3)
	local shoulder = a.s0.Position
	local wrist = (handCF * a.w1).Position
	local want = wrist - shoulder
	-- 팔꿈치 각 θ: |vu + Rx(θ)·vl| = 어깨→손목 거리. 팔꿈치 틀에서 A cosθ + B sinθ = D 를 푼다
	local s1e0 = a.s1:Inverse() * a.e0
	local vu = s1e0.Position -- 위팔 s1 틀에서 어깨 축→팔꿈치 축
	local vl = (a.e1:Inverse() * a.w0).Position -- 아래팔: 팔꿈치 축→손목 축
	local vuE = s1e0.Rotation:Inverse() * vu
	local A = vuE.Y * vl.Y + vuE.Z * vl.Z
	local B = vuE.Z * vl.Y - vuE.Y * vl.Z
	local K = vuE.X * vl.X
	local R = math.sqrt(A * A + B * B)
	local base = vu.Magnitude ^ 2 + vl.Magnitude ^ 2
	local far = math.sqrt(math.max(0, base + 2 * (K + R)))
	local near = math.sqrt(math.max(0, base + 2 * (K - R)))
	local c = math.clamp(want.Magnitude, near + 0.05, far - 0.002)
	local D = (c * c - base) / 2 - K
	local phi = math.atan2(B, A)
	local spread = math.acos(math.clamp(D / math.max(R, 1e-6), -1, 1))
	local theta = (phi + spread + math.pi) % (2 * math.pi) - math.pi
	if theta < -0.05 then
		theta = (phi - spread + math.pi) % (2 * math.pi) - math.pi
	end
	local elbowT = CFrame.Angles(theta, 0, 0)
	-- 어깨: 손목 쪽을 목표로 돌리고, 팔꿈치가 pole 쪽으로 가게 그 축으로 돌린다
	local wLocal = (s1e0 * elbowT * a.e1:Inverse() * a.w0).Position
	local u = if want.Magnitude > 1e-4 then want.Unit else Vector3.new(0, -1, 0)
	local q = between(wLocal, u)
	local e = flat(q * vu, u)
	local p = flat(pole, u)
	local joint = q
	if e.Magnitude > 1e-4 and p.Magnitude > 1e-4 then
		e, p = e.Unit, p.Unit
		joint = CFrame.fromAxisAngle(u, math.atan2(e:Cross(p):Dot(u), e:Dot(p))) * q
	end
	local shoulderT = (a.s0.Rotation:Inverse() * joint).Rotation
	-- 손목: 아래팔 끝 틀에서 손 틀까지 남은 회전
	local upper = CFrame.new(shoulder) * joint * a.s1:Inverse()
	local elbowAt = upper * a.e0
	local lowerEnd = elbowAt * elbowT * a.e1:Inverse() * a.w0
	local wristT = (lowerEnd:Inverse() * handCF * a.w1).Rotation
	return shoulderT, elbowT, wristT, (lowerEnd.Position - elbowAt.Position).Unit
end
WeaponPoses.solveArm = solveArm

-- 날 쪽을 고른다: 손목이 가장 곧은 쪽(아래팔을 날에 수직으로 내린 쪽)에서 want 쪽으로,
-- 손목이 MAX_BEND 넘게 꺾이지 않는 데까지만 돌린다
local function edgeFor(blade: Vector3, forearm: Vector3, want: Vector3, extra: number): Vector3
	local straight = flat(forearm, blade)
	if straight.Magnitude < 1e-3 then
		straight = flat(Vector3.new(0, -1, 0), blade)
		if straight.Magnitude < 1e-3 then
			straight = flat(Vector3.new(0, 0, -1), blade)
		end
	end
	local reach = straight.Magnitude
	straight = straight.Unit
	local side = blade:Cross(straight)
	local psi = extra
	local w = flat(want, blade)
	if w.Magnitude > 1e-3 then
		psi += math.atan2(w:Dot(side), w:Dot(straight)) * math.min(1, w.Magnitude)
	end
	-- 손가락 쪽과 아래팔 사이: cos = FINGER_BLADE·(아래팔·날) + FINGER_EDGE·reach·cos ψ
	local need = (math.cos(MAX_BEND) - FINGER_BLADE * forearm:Dot(blade)) / math.max(FINGER_EDGE * reach, 1e-3)
	local limit = if need >= 1 then 0 else math.acos(math.max(need, -1))
	psi = math.clamp(psi, -limit, limit)
	return straight * math.cos(psi) + side * math.sin(psi)
end

-- 손잡이 틀: 자리, 날 끝 쪽, 날 쪽
local function handleFrame(at: Vector3, blade: Vector3, edge: Vector3): CFrame
	local z = blade.Unit
	local x = flat(edge, z).Unit
	return CFrame.fromMatrix(at, x, z:Cross(x))
end
WeaponPoses.handleFrame = handleFrame

-- 한 손으로 손잡이 틀을 잡는다. 손목 자리가 손 방향에 따라 바뀌므로 몇 번 되풀이해 푼다
local PASSES = 3
local function grasp(a: Arm, at: Vector3, blade: Vector3, edge: Vector3, extra: number, pole: Vector3)
	local forearm = (at - a.s0.Position).Unit
	local handle, s, e, w
	for _ = 1, PASSES do
		handle = handleFrame(at, blade, edgeFor(blade, forearm, edge, extra))
		s, e, w, forearm = solveArm(a, handle * WeaponPoses.GRIP * a.grip:Inverse(), pole)
	end
	return s, e, w, handle
end

-- 자세 하나를 관절 Transform 으로. arms 는 Animator 값을 덮어쓰고, body 는 Animator 값 앞에 곱한다.
-- 셋째 값은 오른손 손잡이 틀 (윗몸 기준)
function WeaponPoses.solve(rig: Rig, pose: Pose): ({ [string]: CFrame }, { [string]: CFrame }, CFrame)
	local s = rig.scale
	local at = pose.at * s
	local rs, re, rw, handle = grasp(rig.right, at, pose.blade, pose.edge, 0, pose.pole)
	local ls, le, lw
	if pose.holdW >= 0.999 then
		ls, le, lw = grasp(rig.left, (handle * v(0, 0, pose.hold * s)), pose.blade, Vector3.zero, 0, pose.lpole)
	else
		local free = CFrame.new(pose.left.Position * s) * pose.left.Rotation
		ls, le, lw = solveArm(rig.left, free, pose.lpole)
		if pose.holdW > 0.001 then
			local hs, he, hw = grasp(rig.left, (handle * v(0, 0, pose.hold * s)), pose.blade, Vector3.zero, 0, pose.lpole)
			ls, le, lw = ls:Lerp(hs, pose.holdW), le:Lerp(he, pose.holdW), lw:Lerp(hw, pose.holdW)
		end
	end
	local function angles(a: Vector3): CFrame
		return CFrame.Angles(rad(a.X), rad(a.Y), rad(a.Z))
	end
	local arms = {
		RightShoulder = rs,
		RightElbow = re,
		RightWrist = rw,
		LeftShoulder = ls,
		LeftElbow = le,
		LeftWrist = lw,
	}
	local body = {
		Waist = angles(pose.waist),
		Neck = angles(pose.neck),
		Root = CFrame.new(pose.root * s) * angles(pose.rootTurn),
		RightHip = angles(pose.hipR),
		LeftHip = angles(pose.hipL),
		RightKnee = CFrame.Angles(rad(pose.kneeR), 0, 0),
		LeftKnee = CFrame.Angles(rad(pose.kneeL), 0, 0),
	}
	return arms, body, handle
end

-- 섞기 -------------------------------------------------------------------------------

function WeaponPoses.lerp(a: Pose, b: Pose, t: number): Pose
	if t <= 0 then
		return a
	elseif t >= 1 then
		return b
	end
	return {
		at = a.at:Lerp(b.at, t),
		blade = slerp(a.blade, b.blade, t),
		edge = a.edge:Lerp(b.edge, t),
		pole = a.pole:Lerp(b.pole, t),
		left = a.left:Lerp(b.left, t),
		lpole = a.lpole:Lerp(b.lpole, t),
		hold = a.hold + (b.hold - a.hold) * t,
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
	out.edge = out.edge or ZERO
	out.pole = out.pole or v(1, -0.6, 0.4)
	out.lpole = out.lpole or v(-1, -0.6, 0.4)
	out.hold = out.hold or 1.2
	out.holdW = out.holdW or 0
	out.waist = out.waist or ZERO
	out.neck = out.neck or ZERO
	out.root = out.root or ZERO
	out.rootTurn = out.rootTurn or ZERO
	out.hipR = out.hipR or ZERO
	out.hipL = out.hipL or ZERO
	out.kneeR = out.kneeR or 0
	out.kneeL = out.kneeL or 0
	out.left = out.left or hand(v(-1.45, -1.15, 0.05), v(0, -1, 0), v(1, 0, 0))
	assert(out.at and out.blade, "at, blade 가 없다")
	out.blade = out.blade.Unit
	return out :: Pose
end
WeaponPoses.pose = pose

-- 벰 길 위의 자세들: 가운데 c 에서 f(0도)→d(90도) 평면으로, 손은 반지름 r 의 phi 도 자리, 날은 phi + lag 도.
-- 날 쪽은 휘두르는 쪽(phi 가 줄어드는 쪽)을 본다. extra[i] 는 그 자리 자세에 덧붙일 칸 (blade 를 주면 그 쪽으로)
local function arc(
	base: Pose,
	c: Vector3,
	f: Vector3,
	d: Vector3,
	r: number,
	marks: { { number } }, -- { 손 phi, 날 phi }
	extra: { { [string]: any } }
): { Pose }
	local out = {}
	local fu, du = f.Unit, d.Unit
	for i, mark in marks do
		local a, b = rad(mark[1]), rad(mark[2])
		local radial = fu * math.cos(a) + du * math.sin(a)
		local blade = fu * math.cos(b) + du * math.sin(b)
		local motion = fu * math.sin(b) - du * math.cos(b)
		local fields = table.clone(extra[i] or {})
		fields.at = c + radial * r
		fields.blade = fields.blade or blade
		fields.edge = fields.edge or motion
		out[i] = pose(base, fields)
	end
	return out
end

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
		hit = windup + strike * (hitAt or 0.75),
		keys = keys,
	}
end

-- 길(windup, path..., follow)을 attack 의 keys 로
local function keysOf(list: { Pose }): { windup: Pose, path: { Pose }, follow: Pose }
	local path = {}
	for i = 2, #list - 1 do
		table.insert(path, list[i])
	end
	return { windup = list[1], path = path, follow = list[#list] }
end

-- 검: 한 손 중단세. 칼끝이 앞 위를 보고, 왼손은 검결(손가락 둘을 세운 손)을 가슴 앞에 둔다
do
	local idle = pose(nil, {
		at = v(0.75, -0.95, -1.0),
		blade = dir(-10, 38),
		edge = v(0, -1, -0.4),
		pole = v(1, -0.7, 0.4),
		left = hand(v(-0.45, 0.2, -1.05), dir(15, 80), v(1, 0, 0.3)),
		lpole = v(-0.5, -1, 0.3),
		waist = v(0, -8, 0),
		neck = v(0, 6, 0),
	})
	local timing = { 0.05, 0.07, 0.08, 0.06, 0.22 }
	-- 1: 오른 어깨 위에서 왼 허리로 비스듬히 내려 벤다
	local slash1 = arc(idle, v(0.3, 0.35, -0.55), v(0, 0, -1), v(0.82, 0.57, 0), 1.05, {
		{ 100, 125 },
		{ 60, 80 },
		{ 10, 15 },
		{ -40, -45 },
		{ -75, -85 },
		{ -95, -110 },
	}, {
		{ waist = v(4, -24, -4), neck = v(0, 18, 0), pole = v(1, 0.3, 0.6), blade = dir(150, 55) },
		{ waist = v(0, -14, -2), neck = v(0, 10, 0), pole = v(1, 0, 0.5) },
		{ waist = v(-4, 0, 0), neck = v(0, 0, 0), pole = v(1, -0.3, 0.4) },
		{ waist = v(-5, 14, 3), neck = v(3, -10, 0), pole = v(1, -0.5, 0.2) },
		{ waist = v(-5, 24, 5), neck = v(3, -18, 0), pole = v(1, -0.4, 0) },
		{ waist = v(-5, 30, 6), neck = v(3, -22, 0), pole = v(1, -0.3, -0.1) },
	})
	-- 2: 왼쪽으로 감았다가 가슴 높이로 가로 벤다 (왼→오, 손등 쪽)
	local slash2 = arc(idle, v(0.2, -0.2, -0.45), v(0, 0, -1), v(-1, 0.08, 0), 1.1, {
		{ 75, 120 },
		{ 40, 60 },
		{ 0, 5 },
		{ -40, -50 },
		{ -75, -95 },
		{ -95, -125 },
	}, {
		{ waist = v(0, 30, 0), neck = v(0, -24, 0), pole = v(0.6, -0.8, -0.3) },
		{ waist = v(0, 18, 0), neck = v(0, -14, 0), pole = v(0.8, -0.6, 0) },
		{ waist = v(0, 0, 0), neck = v(0, 0, 0), pole = v(1, -0.5, 0.3) },
		{ waist = v(0, -16, 0), neck = v(0, 12, 0), pole = v(1, -0.4, 0.5) },
		{ waist = v(0, -26, 0), neck = v(0, 20, 0), pole = v(1, -0.3, 0.6) },
		{ waist = v(0, -30, 0), neck = v(0, 24, 0), pole = v(1, -0.2, 0.7) },
	})
	-- 3: 오른 아래에서 왼 위로 올려 벤다 (마무리, 몸을 크게 쓴다)
	local slash3 = arc(idle, v(0.15, 0.15, -0.55), v(0, 0, -1), v(0.75, -0.66, 0), 1.1, {
		{ 100, 120 },
		{ 60, 80 },
		{ 10, 15 },
		{ -40, -50 },
		{ -85, -105 },
		{ -105, -135 },
	}, {
		{ waist = v(6, -26, 6), neck = v(-4, 20, 0), pole = v(1, -0.5, 0.6), root = v(0, -0.2, 0.1), blade = dir(140, -18) },
		{ waist = v(2, -16, 4), neck = v(-2, 12, 0), pole = v(1, -0.6, 0.4), root = v(0, -0.15, -0.1) },
		{ waist = v(-2, 0, 0), neck = v(0, 0, 0), pole = v(1, -0.6, 0.2), root = v(0, -0.05, -0.3) },
		{ waist = v(-6, 16, -4), neck = v(2, -12, 0), pole = v(0.6, -0.8, 0), root = v(0, 0, -0.35) },
		{ waist = v(-8, 26, -6), neck = v(4, -20, 0), pole = v(0.4, -0.9, -0.1), root = v(0, 0, -0.35) },
		{ waist = v(-8, 30, -6), neck = v(4, -24, 0), pole = v(0.4, -0.9, -0.2), root = v(0, 0, -0.3) },
	})
	DEFS.sword = {
		idle = idle,
		attacks = { attack(timing, keysOf(slash1)), attack(timing, keysOf(slash2)), attack({ 0.05, 0.07, 0.1, 0.08, 0.24 }, keysOf(slash3)) },
	}
end

-- 도: 오른 허리에 비껴 들고 왼손은 칼등 곁. 1: 머리 위로 크게 들어 두 손으로 비스듬히 내리찍는다 2: 허리 높이 가로 베기
do
	local idle = pose(nil, {
		at = v(0.8, -1.0, -0.8),
		blade = dir(20, 28),
		edge = v(0, -0.6, -1),
		pole = v(1, -0.6, 0.4),
		left = hand(v(-0.5, -0.45, -1.05), dir(40, 25), v(1, 0, 0)),
		lpole = v(-1, -0.6, 0.2),
		waist = v(0, -12, 0),
		neck = v(0, 10, 0),
	})
	local chop = arc(idle, v(0.25, 0.6, -0.5), v(0, 0, -1), v(0.45, 0.89, 0), 1.15, {
		{ 105, 125 },
		{ 70, 85 },
		{ 30, 35 },
		{ -5, -5 },
		{ -25, -15 },
		{ -35, -22 },
	}, {
		{ holdW = 1, hold = -0.55, waist = v(12, -20, -6), neck = v(-8, 16, 0), root = v(0, 0.05, 0.3), pole = v(1, 0.6, 0.3), lpole = v(-1, 0.3, 0.3) },
		{ holdW = 1, hold = -0.55, waist = v(4, -12, -3), neck = v(-4, 10, 0), root = v(0, 0, 0.1), pole = v(1, 0.3, 0.3), lpole = v(-1, 0, 0.3) },
		{ holdW = 1, hold = -0.55, waist = v(-8, 0, 0), neck = v(4, 0, 0), root = v(0, -0.15, -0.25), pole = v(1, -0.2, 0.3), lpole = v(-1, -0.3, 0.3) },
		{ holdW = 1, hold = -0.55, waist = v(-10, 10, 4), neck = v(12, -6, 0), root = v(0, -0.25, -0.5), pole = v(1, -0.5, 0.2), lpole = v(-1, -0.5, 0.2), hipL = v(25, 0, 0), hipR = v(-12, 0, 0), kneeL = -20, kneeR = -14 },
		{ holdW = 1, hold = -0.55, waist = v(-14, 16, 6), neck = v(18, -10, 0), root = v(0, -0.26, -0.65), pole = v(1, -0.5, 0.1), lpole = v(-1, -0.6, 0.2), hipL = v(34, 0, 0), hipR = v(-16, 0, 0), kneeL = -32, kneeR = -20 },
		{ holdW = 1, hold = -0.55, waist = v(-14, 18, 6), neck = v(20, -12, 0), root = v(0, -0.28, -0.7), pole = v(1, -0.4, 0), lpole = v(-1, -0.6, 0.2), hipL = v(36, 0, 0), hipR = v(-18, 0, 0), kneeL = -36, kneeR = -22 },
	})
	local sweep = arc(idle, v(0.15, -0.55, -0.4), v(0, 0, -1), v(-1, 0.1, 0), 1.2, {
		{ 80, 135 },
		{ 45, 65 },
		{ 0, 0 },
		{ -45, -55 },
		{ -80, -100 },
		{ -100, -130 },
	}, {
		{ waist = v(0, 42, 0), neck = v(0, -32, 0), root = v(0, -0.15, 0), pole = v(0.6, -0.8, -0.3) },
		{ waist = v(-2, 26, 0), neck = v(0, -20, 0), root = v(0, -0.25, -0.1), pole = v(0.8, -0.6, 0) },
		{ waist = v(-6, 0, 0), neck = v(0, 0, 0), root = v(0, -0.3, -0.3), pole = v(1, -0.5, 0.3) },
		{ waist = v(-8, -22, 0), neck = v(0, 18, 0), root = v(0, -0.3, -0.35), pole = v(1, -0.4, 0.5) },
		{ waist = v(-8, -36, 0), neck = v(0, 28, 0), root = v(0, -0.3, -0.35), pole = v(1, -0.3, 0.6) },
		{ waist = v(-8, -42, 0), neck = v(0, 32, 0), root = v(0, -0.3, -0.3), pole = v(1, -0.2, 0.7) },
	})
	local heavy = { 0.07, 0.07, 0.12, 0.12, 0.35 }
	DEFS.saber = { idle = idle, attacks = { attack(heavy, keysOf(chop)), attack(heavy, keysOf(sweep)) } }
end

-- 창: 허리 높이에 수평으로 앞을 겨누고 두 손으로 쥔다 (오른손 뒤 허리께, 왼손 앞)
do
	local idle = pose(nil, {
		at = v(0.6, -1.05, -0.1),
		blade = dir(-24, 2),
		pole = v(1, -0.6, 0.6),
		holdW = 1,
		hold = 1.7,
		lpole = v(-1, -0.8, 0),
		waist = v(0, -20, 0),
		neck = v(0, 16, 0),
	})
	local thrust = attack({ 0.05, 0.06, 0.1, 0.1, 0.25 }, {
		windup = pose(idle, {
			at = v(0.65, -0.95, 0.35),
			blade = dir(-4, 3),
			hold = 1.55,
			waist = v(4, -28, 0),
			neck = v(0, 22, 0),
			root = v(0, 0, 0.2),
		}),
		path = {
			pose(idle, {
				at = v(0.2, -0.9, -1.8),
				blade = dir(-1, 1),
				hold = 1.05,
				pole = v(1, -0.6, 0.2),
				lpole = v(-1, -0.6, -0.2),
				waist = v(-8, -2, 0),
				neck = v(6, 2, 0),
				root = v(0, -0.3, -1.0),
				hipL = v(35, 0, 0),
				hipR = v(-20, 0, 0),
				kneeL = -30,
				kneeR = -10,
			}),
		},
		follow = pose(idle, {
			at = v(0.1, -0.85, -2.1),
			blade = dir(0, 1),
			hold = 0.95,
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
	-- 2: 창끝으로 앞을 오른쪽에서 왼쪽으로 크게 쓸어 벤다
	local sweep = arc(idle, v(0.3, -0.95, -0.2), v(0, 0, -1), v(1, 0, 0), 0.6, {
		{ 50, 65 },
		{ 25, 30 },
		{ 0, 0 },
		{ -25, -35 },
		{ -50, -70 },
		{ -60, -90 },
	}, {
		{ waist = v(0, -35, 0), neck = v(0, 28, 0), hold = 1.5 },
		{ waist = v(-2, -18, 0), neck = v(0, 14, 0), hold = 1.5, root = v(0, -0.1, -0.2) },
		{ waist = v(-4, 0, 0), neck = v(0, 0, 0), hold = 1.5, root = v(0, -0.2, -0.4) },
		{ waist = v(-4, 18, 0), neck = v(0, -14, 0), hold = 1.5, root = v(0, -0.2, -0.5) },
		{ waist = v(-4, 32, 0), neck = v(0, -26, 0), hold = 1.5, root = v(0, -0.2, -0.5) },
		{ waist = v(-4, 38, 0), neck = v(0, -30, 0), hold = 1.5, root = v(0, -0.2, -0.45) },
	})
	DEFS.spear = { idle = idle, attacks = { thrust, attack({ 0.05, 0.07, 0.1, 0.1, 0.25 }, keysOf(sweep)) } }
end

-- 부채: 펼친 부채를 가슴 앞 오른쪽에 세워 든다. 왼쪽으로 감았다가 크게 펼쳐 쳐서 바람칼을 날린다
do
	local idle = pose(nil, {
		at = v(0.85, -0.25, -1.0),
		blade = dir(-15, 65),
		edge = v(-1, 0, 0),
		pole = v(1, -0.9, 0.2),
		left = hand(v(-0.8, -0.85, -0.55), dir(20, -40), v(1, 0, 0)),
		lpole = v(-1, -0.6, 0.2),
		waist = v(0, -10, 0),
		neck = v(0, 8, 0),
	})
	local flick = arc(idle, v(0.25, 0, -0.45), v(0, 0, -1), v(-1, 0.15, 0), 1.15, {
		{ 80, 110 },
		{ 45, 55 },
		{ 0, 0 },
		{ -45, -55 },
		{ -80, -95 },
		{ -95, -115 },
	}, {
		{ waist = v(0, 34, 0), neck = v(0, -26, 0), pole = v(0.6, -0.8, -0.3), edge = v(0, 1, 0) },
		{ waist = v(0, 20, 0), neck = v(0, -16, 0), pole = v(0.8, -0.6, 0), edge = v(0, 1, 0) },
		{ waist = v(-4, 0, 0), neck = v(0, 0, 0), pole = v(1, -0.5, 0.3), edge = v(0, 1, 0), root = v(0, 0, -0.2) },
		{ waist = v(-4, -20, 0), neck = v(0, 16, 0), pole = v(1, -0.4, 0.5), edge = v(0, 1, 0), root = v(0, 0, -0.25) },
		{ waist = v(-4, -30, 0), neck = v(0, 24, 0), pole = v(1, -0.3, 0.6), edge = v(0, 1, 0), root = v(0, 0, -0.25) },
		{ waist = v(-4, -34, 0), neck = v(0, 26, 0), pole = v(1, -0.2, 0.7), edge = v(0, 1, 0), root = v(0, 0, -0.2) },
	})
	DEFS.fan = { idle = idle, attacks = { attack({ 0.06, 0.07, 0.12, 0.12, 0.35 }, keysOf(flick)) } }
end

WeaponPoses.DEFS = DEFS

-- 든 자세 (숨 쉬듯 조금 오르내린다)
function WeaponPoses.idle(kind: string, t: number): Pose
	local def = DEFS[kind] or DEFS.sword
	local base = def.idle
	local breathe = math.sin(t * 2.1)
	local out = table.clone(base)
	out.at = base.at + Vector3.new(0, 0.035 * breathe, 0)
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
