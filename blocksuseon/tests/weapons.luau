-- 무기 자세·휘두르기 테스트.   실행: lune run tests/weapons   (blocksuseon 폴더에서)
--
-- shared/WeaponPoses 의 자세를 기본 R15 붙이개로 FK 해서 날 끝·손 자리를 숫자로 따진다.
-- 기준 숫자는 엔진(Open Cloud Luau 실행)에서 R15 인형에 같은 Transform 을 넣고 잰 값과 맞춘 것이다.
-- 좌표는 HumanoidRootPart 기준 (앞이 -Z, 오른쪽이 +X). 기본 R15 의 땅은 뿌리 아래 3.19.

local roblox = require("@lune/roblox")
local Harness = require("./harness")

local CFrame, Vector3 = roblox.CFrame, roblox.Vector3

local passed, failed = 0, 0

local function check(name: string, fn: () -> ())
	local ok, err = pcall(fn)
	if ok then
		passed += 1
	else
		failed += 1
		print(`  ✗ {name}\n      {err}`)
	end
end

local function near(actual: number, lo: number, hi: number, what: string)
	if actual ~= actual or actual < lo or actual > hi then
		error(string.format("%s: %.3f 가 %.3f ~ %.3f 밖", what, actual, lo, hi), 2)
	end
end

local env = Harness.robloxGlobals(roblox.Instance.new("DataModel"))
local loader = Harness.new(env)
local shared = loader.folder("src/shared")
local WeaponPoses = loader.require(shared.WeaponPoses)
local Combat = loader.require(shared.Combat)

local GROUND = -(1 + 2.192) -- 기본 R15: 뿌리 반 높이 + HipHeight
local TIP = { sword = 4.9, saber = 4.8, spear = 6.1, fan = 2.8 } -- 블록 무기 날 끝 (Weapons BLOCK_SPAN 과 같다)
local BODY = WeaponPoses.DEFAULT_BODY
local RIG = WeaponPoses.DEFAULT_RIG

-- 기본 R15 FK. 팔은 Transform 을 덮어쓰고 몸은 Animator 값(여기서는 쉼 자세 = 단위)에 곱한다
type Frame = { [string]: CFrame }
local function fk(rig: any, pose: any): (Frame, CFrame)
	local arms, body = WeaponPoses.solve(rig, pose)
	local parts: Frame = { Root = CFrame.identity }
	local function joint(_name: string, from: CFrame, c0: CFrame, c1: CFrame, t: CFrame?): CFrame
		return from * c0 * (t or CFrame.identity) * c1:Inverse()
	end
	parts.LowerTorso = joint("Root", parts.Root, BODY.Root[1], BODY.Root[2], body.Root)
	parts.UpperTorso = joint("Waist", parts.LowerTorso, BODY.Waist[1], BODY.Waist[2], body.Waist)
	parts.Head = joint("Neck", parts.UpperTorso, BODY.Neck[1], BODY.Neck[2], body.Neck)
	for _, side in { "Right", "Left" } do
		local arm = if side == "Right" then rig.right else rig.left
		local upper = joint("Shoulder", parts.UpperTorso, arm.s0, arm.s1, arms[side .. "Shoulder"])
		local lower = joint("Elbow", upper, arm.e0, arm.e1, arms[side .. "Elbow"])
		parts[side .. "UpperArm"] = upper
		parts[side .. "LowerArm"] = lower
		parts[side .. "Hand"] = joint("Wrist", lower, arm.w0, arm.w1, arms[side .. "Wrist"])
		local thigh =
			joint("Hip", parts.LowerTorso, BODY[side .. "Hip"][1], BODY[side .. "Hip"][2], body[side .. "Hip"])
		local shin = joint("Knee", thigh, BODY[side .. "Knee"][1], BODY[side .. "Knee"][2], body[side .. "Knee"])
		parts[side .. "Foot"] = joint("Ankle", shin, BODY[side .. "Ankle"][1], BODY[side .. "Ankle"][2], nil)
	end
	local handle = parts.RightHand * rig.right.grip * WeaponPoses.GRIP:Inverse()
	return parts, handle
end

-- 날 끝 자리, 날 방향의 방위각(앞 0, 오른쪽 +)과 앙각
local function blade(kind: string, pose: any, rig: any?): (Vector3, number, number, Frame, CFrame)
	rig = rig or RIG
	local parts, handle = fk(rig, pose)
	local tip = handle * Vector3.new(0, 0, TIP[kind] * rig.scale)
	local z = handle.ZVector
	local el = math.deg(math.asin(math.clamp(z.Y, -1, 1)))
	local az = math.deg(math.atan2(z.X, -z.Z))
	return tip, az, el, parts, handle
end

-- 손목이 아래팔에서 꺾인 각 (도)
local function bend(parts: Frame, side: string): number
	local a, b = parts[side .. "LowerArm"].UpVector, parts[side .. "Hand"].UpVector
	return math.deg(math.acos(math.clamp(a:Dot(b), -1, 1)))
end

-- 공격을 촘촘히 훑는다
local function sweep(kind: string, combo: number, from: number?, to: number?, step: number?)
	local attack = WeaponPoses.attack(kind, combo)
	local idle = WeaponPoses.idle(kind, 0)
	local out = {}
	local t = from or 0
	local stop = to or attack.duration
	while t <= stop + 1e-9 do
		local tip, az, el, parts, handle = blade(kind, WeaponPoses.sample(attack, idle, idle, t))
		table.insert(out, { t = t, tip = tip, az = az, el = el, parts = parts, handle = handle })
		t += step or 0.005
	end
	return out, attack
end

print("손잡이")
check("Grip: 날이 주먹 엄지 쪽으로 나와 손가락 쪽으로 30도 기운다", function()
	-- 손 틀에서 본 손잡이 (Handle = Hand * GripAttachment * Grip^-1)
	local inHand = RIG.right.grip * WeaponPoses.GRIP:Inverse()
	local z = inHand.ZVector
	near(z.Z, -0.87, -0.85, "날이 손 앞(-Z)으로")
	near(z.Y, -0.51, -0.49, "손가락 쪽(-Y)으로 기욺")
	near(inHand.Position.Magnitude - 0.158, -0.001, 0.001, "쥐는 자리는 GripAttachment")
	-- 기본 도구 자세(팔을 앞으로 90도 듦): 날이 위로 서되 앞으로 기운다
	local raised = CFrame.Angles(math.rad(90), 0, 0) * inHand
	near(raised.ZVector.Y, 0.85, 0.88, "기본 자세에서 날이 위로")
	near(raised.ZVector.Z, -0.51, -0.49, "기본 자세에서 날이 앞으로 기욺")
end)

check("IK: 닿는 자리면 손이 그 틀에 정확히 온다", function()
	for _, kind in Combat.KIND_ORDER do
		local pose = WeaponPoses.idle(kind, 0)
		local parts, handle = fk(RIG, pose)
		local _, _, want = WeaponPoses.solve(RIG, pose)
		local ut = parts.UpperTorso
		local got = ut:ToObjectSpace(handle)
		near((got.Position - want.Position).Magnitude, 0, 0.02, kind .. " 손잡이 자리")
		near(got.ZVector:Dot(want.ZVector), 0.999, 1.001, kind .. " 날 방향")
		near(bend(parts, "Right"), 0, 55, kind .. " 오른 손목")
		near(bend(parts, "Left"), 0, 62, kind .. " 왼 손목")
	end
end)

print("든 자세")
check(
	"숨쉬기: 든 자세가 떨리지 않는다 (팔을 다 뻗은 자세면 IK 가 크게 흔들린다)",
	function()
		for _, kind in Combat.KIND_ORDER do
			local first = WeaponPoses.solve(RIG, WeaponPoses.idle(kind, 0)).RightShoulder
			local widest = 0
			for i = 1, 180 do
				local shoulder = WeaponPoses.solve(RIG, WeaponPoses.idle(kind, i / 60)).RightShoulder
				local _, angle = (first:Inverse() * shoulder):ToAxisAngle()
				widest = math.max(widest, math.deg(math.abs(angle)))
			end
			near(widest, 0, 4, kind .. " 숨쉬는 동안 어깨가 도는 폭")
		end
	end
)

check("검: 칼끝이 몸 앞에서 30~55도로 선다 (머리 곁에 세우지 않는다)", function()
	local tip, az, el, parts = blade("sword", WeaponPoses.idle("sword", 0))
	near(el, 30, 55, "앙각")
	near(az, -20, 20, "방위")
	near(-tip.Z, 3, 6, "칼끝이 앞으로")
	local head = parts.Head.Position
	near((tip - head).Magnitude, 3, 10, "칼끝이 머리에서 멀다")
	near(parts.RightHand.Position.Y, -1.2, 0.2, "손은 허리~명치 높이")
	near(-parts.RightHand.Position.Z, 0.4, 1.6, "손이 몸 앞")
end)

check("도: 오른 허리에 비껴 들고 칼끝이 앞을 본다", function()
	local tip, az, el, parts = blade("saber", WeaponPoses.idle("saber", 0))
	near(el, 15, 45, "앙각")
	near(az, 0, 45, "방위 (오른 앞)")
	near(-tip.Z, 2.5, 6, "칼끝이 앞으로")
	near(parts.RightHand.Position.X, 0.4, 1.4, "손이 오른쪽")
end)

check("창: 허리 높이에 수평으로 앞을 겨누고 두 손으로 쥔다", function()
	local tip, az, el, parts, handle = blade("spear", WeaponPoses.idle("spear", 0))
	near(el, -20, 20, "앙각 (수평)")
	near(az, -15, 15, "방위 (앞)")
	near(-tip.Z, 4.5, 8, "창끝이 앞으로")
	near(tip.Y, -1.4, 0.3, "창끝 높이 (허리)")
	near(parts.RightHand.Position.Y, -1.3, -0.2, "오른손 허리 높이")
	-- 왼손이 자루 위에 있다
	local left = handle:PointToObjectSpace(parts.LeftHand.Position)
	near(math.sqrt(left.X ^ 2 + left.Y ^ 2), 0, 0.45, "왼손이 자루 곁")
	near(left.Z, 1, 2.4, "왼손이 오른손보다 앞")
end)

check("부채: 펼친 부채를 가슴 앞 오른쪽에 든다", function()
	local tip, _, el, parts, handle = blade("fan", WeaponPoses.idle("fan", 0))
	local grip = handle.Position
	near(grip.Y, -0.5, 0.8, "부채 손잡이가 가슴 높이")
	near(-grip.Z, 0.5, 1.6, "몸 앞")
	near(grip.X, 0.2, 1.4, "오른쪽")
	near(el, 40, 85, "부채 살이 위로")
	near(tip.Y, 0.5, 3.5, "부채 끝이 어깨 위")
	near(bend(parts, "Right"), 0, 55, "손목")
end)

-- Open Cloud Luau 실행으로 엔진의 기본 R15 인형(관절을 Motor6D 로 바꿔 C0 * Transform 을 넣음)에 실제 도구를 쥐여
-- 잰 값 (오른손·왼손 가운데, 날 방위·앙각). 도구 RightGrip 용접이 놓은 손잡이와 IK 손잡이 차이는 0.000 이었다.
-- 자세를 고치면 엔진에서 다시 재어 여기를 고친다
local ENGINE = {
	{ kind = "sword", combo = 0, t = 0, hand = { 0.84, -0.19, -0.69 }, az = -2.0, el = 38.0 },
	{ kind = "sword", combo = 1, t = 0.1, hand = { 0.50, 0.64, -1.56 }, az = 9.7, el = 3.2 },
	{ kind = "sword", combo = 2, t = 0.1, hand = { 0.29, 0.18, -1.46 }, az = -2.1, el = 0.2 },
	{ kind = "saber", combo = 0, t = 0, hand = { 0.92, -0.37, -0.48 }, az = 32.0, el = 28.0 },
	{ kind = "saber", combo = 1, t = 0.123, hand = { 0.38, 0.85, -2.02 }, az = 7.3, el = 12.4 },
	{
		kind = "spear",
		combo = 0,
		t = 0,
		hand = { 0.45, -0.45, 0.52 },
		left = { 0.25, -0.45, -0.63 },
		az = 0,
		el = 2.0,
	},
	{ kind = "spear", combo = 1, t = 0.21, hand = { 0.48, -0.70, -2.64 }, az = 0, el = -10.0 },
	{ kind = "fan", combo = 0, t = 0, hand = { 1.14, -0.04, -0.75 }, az = -5.0, el = 65.0 },
	{ kind = "fan", combo = 1, t = 0.113, hand = { 0.70, 0.03, -1.59 }, az = 21.9, el = -6.1 },
}
check("엔진에서 잰 손 자리·날 방향과 같다", function()
	for _, case in ENGINE do
		local idle = WeaponPoses.idle(case.kind, 0)
		local pose = if case.combo == 0
			then idle
			else WeaponPoses.sample(WeaponPoses.attack(case.kind, case.combo), idle, idle, case.t)
		local _, az, el, parts = blade(case.kind, pose)
		local tag = `{case.kind} {case.combo} t={case.t}`
		local hand = parts.RightHand.Position
		near((hand - Vector3.new(table.unpack(case.hand))).Magnitude, 0, 0.03, tag .. " 오른손")
		if case.left then
			near((parts.LeftHand.Position - Vector3.new(table.unpack(case.left))).Magnitude, 0, 0.03, tag .. " 왼손")
		end
		near(math.abs((az - case.az + 180) % 360 - 180), 0, 1, tag .. " 방위")
		near(el, case.el - 1, case.el + 1, tag .. " 앙각")
	end
	-- 엔진: 목창(모델 날 끝 4.96 × 1.049) 끝이 찌르기로 4.76 → 7.83 스터드 앞 (3.07 나감)
end)

print("휘두르기")
check("때: 벰이 0.08~0.13초에 닿고, 다음 수는 쿨타임 안에 이어진다", function()
	for _, kind in Combat.KIND_ORDER do
		local cooldown = Combat.KINDS[kind].cooldown
		for combo = 1, WeaponPoses.COMBO[kind] do
			local a = WeaponPoses.attack(kind, combo)
			near(a.hit, 0.08, 0.13, `{kind} {combo} 닿는 때`)
			near(a.windup, 0.03, 0.08, `{kind} {combo} 젖힘`)
			near(a.duration, cooldown * 0.9, cooldown + 0.15, `{kind} {combo} 길이`)
			local phase = WeaponPoses.phase(a, a.hit)
			assert(phase == "strike", `{kind} {combo} 닿는 때가 벰 마디 ({phase})`)
		end
		assert(
			WeaponPoses.attack(kind, WeaponPoses.COMBO[kind] + 1) == WeaponPoses.attack(kind, 1),
			kind .. " 이어치기 돌기"
		)
	end
end)

-- 벰과 따라감 동안 날 끝이 몸 앞을 크게 가로지른다
local function arcCheck(kind: string, combo: number, minArc: number)
	local a = WeaponPoses.attack(kind, combo)
	local samples = sweep(kind, combo, a.windup, a.windup + a.strike + a.follow, 0.002)
	local lo, hi = math.huge, -math.huge
	local front = false
	local prev = nil
	local turned = 0
	for _, s in samples do
		local flat = Vector3.new(s.tip.X, 0, s.tip.Z)
		local az = math.deg(math.atan2(flat.X, -flat.Z))
		if prev then
			turned += math.abs((az - prev + 180) % 360 - 180)
		end
		prev = az
		lo, hi = math.min(lo, s.tip.X), math.max(hi, s.tip.X)
		if -s.tip.Z > 2.5 and math.abs(s.tip.X) < 2 then
			front = true
		end
	end
	assert(front, `{kind} {combo}: 날 끝이 몸 바로 앞을 지나야 한다`)
	near(turned, minArc, 400, `{kind} {combo}: 날 끝이 돈 각`)
	near(hi - lo, 4, 20, `{kind} {combo}: 날 끝이 좌우로 쓴 폭`)
end

check("검: 세 수 모두 몸 앞을 크게 벤다 (비스듬히 / 가로 / 올려)", function()
	arcCheck("sword", 1, 150)
	arcCheck("sword", 2, 150)
	arcCheck("sword", 3, 150)
	-- 1 은 오른 위에서 왼 아래로, 2 는 왼에서 오른으로, 3 은 오른 아래에서 왼 위로
	local function ends(combo: number)
		local a = WeaponPoses.attack("sword", combo)
		local s = sweep("sword", combo, a.windup, a.windup + a.strike, a.strike)
		return s[1].tip, s[#s].tip
	end
	local a1, b1 = ends(1)
	assert(a1.X > 1 and a1.Y > 1.5 and b1.X < -1 and b1.Y < -1, "1: 오른 위 → 왼 아래")
	local a2, b2 = ends(2)
	assert(a2.X < -2 and b2.X > 2 and math.abs(b2.Y - a2.Y) < 2, "2: 왼 → 오른 가로")
	local a3, b3 = ends(3)
	assert(a3.X > 1 and a3.Y < 0 and b3.X < 0 and b3.Y > 2, "3: 오른 아래 → 왼 위")
end)

check("도: 머리 위로 들어 두 손으로 내리찍고, 둘째 수는 허리 높이 가로 베기", function()
	arcCheck("saber", 1, 140)
	arcCheck("saber", 2, 150)
	local a = WeaponPoses.attack("saber", 1)
	local raised = sweep("saber", 1, a.windup, a.windup, 1)[1]
	near(raised.tip.Y, 2.5, 6, "젖힘: 칼끝이 머리 위")
	near(raised.parts.RightHand.Position.Y, 0.8, 2, "젖힘: 손이 머리께")
	-- 내리찍는 동안 왼손이 손잡이를 함께 쥔다
	local hit = sweep("saber", 1, a.hit, a.hit, 1)[1]
	local left = hit.handle:PointToObjectSpace(hit.parts.LeftHand.Position)
	near(math.sqrt(left.X ^ 2 + left.Y ^ 2), 0, 0.45, "두 손으로 쥔다")
	-- 몸이 앞으로 숙는다
	local after = sweep("saber", 1, a.windup + a.strike + a.follow, a.windup + a.strike + a.follow, 1)[1]
	near(after.parts.Head.Position.Z, -1.2, -0.25, "따라감: 머리가 앞으로")
end)

check("창: 찌르기는 날 끝이 2.5 스터드 넘게 앞으로 나가고 몸이 따라 들어간다", function()
	local idleTip = blade("spear", WeaponPoses.idle("spear", 0))
	local a = WeaponPoses.attack("spear", 1)
	local samples = sweep("spear", 1, 0, a.windup + a.strike + a.follow, 0.002)
	local far = math.huge
	local back = -math.huge
	for _, s in samples do
		far = math.min(far, s.tip.Z)
		back = math.max(back, s.tip.Z)
		near(s.el, -20, 20, "찌르는 동안 수평")
		near(s.az, -15, 15, "찌르는 동안 앞")
	end
	near(idleTip.Z - far, 2.5, 6, "찌른 거리")
	near(back - idleTip.Z, 0.3, 2, "찌르기 전에 당긴다")
	local hit = sweep("spear", 1, a.hit, a.hit, 1)[1]
	near(hit.parts.LowerTorso.Position.Z, -1.5, -0.6, "몸이 앞으로 들어간다")
	arcCheck("spear", 2, 120)
end)

check("부채: 왼쪽으로 감았다가 앞을 크게 쓸어 친다", function()
	arcCheck("fan", 1, 140)
	local a = WeaponPoses.attack("fan", 1)
	local hit = sweep("fan", 1, a.hit, a.hit, 1)[1]
	near(-hit.handle.Position.Z, 0.8, 2.2, "바람칼을 날릴 때 부채가 몸 앞")
end)

check("날 끝과 발이 땅에 박히지 않는다", function()
	for _, kind in Combat.KIND_ORDER do
		for combo = 1, WeaponPoses.COMBO[kind] do
			for _, s in sweep(kind, combo, 0, nil, 0.01) do
				near(s.tip.Y, GROUND + 0.05, 10, `{kind} {combo} t={s.t} 날 끝`)
				for _, foot in { "RightFoot", "LeftFoot" } do
					near(s.parts[foot].Position.Y - 0.156, GROUND - 0.45, GROUND + 1, `{kind} {combo} t={s.t} {foot}`)
				end
			end
		end
	end
end)

check("거둔 뒤에는 든 자세로 돌아온다", function()
	for _, kind in Combat.KIND_ORDER do
		local idle = WeaponPoses.idle(kind, 0)
		for combo = 1, WeaponPoses.COMBO[kind] do
			local a = WeaponPoses.attack(kind, combo)
			local last = WeaponPoses.sample(a, idle, idle, a.duration + 0.01)
			assert(last == idle, `{kind} {combo} 끝 자세`)
			local from = WeaponPoses.sample(a, idle, idle, 0)
			assert(from == idle, `{kind} {combo} 시작 자세`)
		end
	end
end)

print("몸 크기")
check("작은 아바타: 팔 길이 비로 줄여도 손이 닿는다", function()
	local function scaled(arm: any, k: number): any
		local out = {}
		for key, value in arm do
			out[key] = CFrame.new(value.Position * k) * value.Rotation
		end
		return out
	end
	local small = WeaponPoses.rig(scaled(RIG.right, 0.65), scaled(RIG.left, 0.65))
	near(small.scale, 0.64, 0.66, "팔 길이 비")
	for _, kind in Combat.KIND_ORDER do
		local pose = WeaponPoses.idle(kind, 0)
		local arms = WeaponPoses.solve(small, pose)
		local _, _, want = WeaponPoses.solve(small, pose)
		-- FK (작은 몸: 윗몸 기준만 본다)
		local a = small.right
		local upper = a.s0 * arms.RightShoulder * a.s1:Inverse()
		local lower = upper * a.e0 * arms.RightElbow * a.e1:Inverse()
		local handPart = lower * a.w0 * arms.RightWrist * a.w1:Inverse()
		local handle = handPart * a.grip * WeaponPoses.GRIP:Inverse()
		near((handle.Position - want.Position).Magnitude, 0, 0.02, kind .. " 작은 몸 손잡이 자리")
	end
end)

check("Weapons: 칼자취 붙이개와 아바타 크기", function()
	local fakeGame = {
		GetService = function(_, name: string)
			if name == "ReplicatedStorage" then
				return {
					WaitForChild = function()
						return shared
					end,
				}
			elseif name == "DataStoreService" then
				return {
					GetDataStore = function()
						error("테스트에는 DataStore 가 없다")
					end,
				}
			end
			return {}
		end,
	}
	local serverEnv = table.clone(env)
	serverEnv.game = fakeGame
	serverEnv.warn = function() end
	local serverLoader = Harness.new(serverEnv)
	local Weapons = serverLoader.require(serverLoader.folder("src/server").Weapons)
	near(Weapons.scaleFor(5.457), 1.04, 1.06, "기본 R15 (키 5.46)")
	near(Weapons.scaleFor(3.4), 0.64, 0.66, "작은 아바타")
	near(Weapons.scaleFor(2), 0.6, 0.6, "아주 작은 아바타")
	near(Weapons.scaleFor(9), 1.1, 1.1, "큰 아바타")
	for _, kind in Combat.KIND_ORDER do
		local block = Weapons.span(kind, nil)
		near(block.tip, TIP[kind] - 0.01, TIP[kind] + 0.01, kind .. " 블록 날 끝")
		assert(block.base > 0 and block.base < block.tip and block.butt < 0, kind .. " 블록 밑동")
		for grade = 1, #Combat.GRADES do
			local spec = Combat.meshFor({ kind = kind, grade = grade })
			if spec then
				local span = Weapons.span(kind, spec)
				near(span.tip - span.butt, spec.length - 0.001, spec.length + 0.001, `{kind} {grade} 모델 길이`)
				assert(span.base > 0 and span.base < span.tip, `{kind} {grade} 모델 밑동`)
				near(span.tip, spec.length * 0.4, spec.length * 0.95, `{kind} {grade} 날 끝이 손 앞`)
			end
		end
	end
end)

print("WeaponAnim (가짜 캐릭터)")
-- 클라이언트를 띄울 수 없으므로 가짜 서비스·캐릭터·관절로 PreSimulation 을 돌려 본다.
-- WeaponEffects 는 불러온 뒤 함수를 기록용으로 바꾼다
check("든 자세 섞기, 내 휘두르기, 남의 휘두르기, 부채 바람칼, 멈춤, 내려놓기", function()
	local Enum = roblox.Enum
	local clock = 100
	local function signal()
		local list = {}
		return {
			Connect = function(_, fn)
				table.insert(list, fn)
				return {
					Disconnect = function()
						table.remove(list, table.find(list, fn))
					end,
				}
			end,
			fire = function(...)
				for _, fn in table.clone(list) do
					fn(...)
				end
			end,
		}
	end
	local function fake(className: string, fields: { [string]: any }): any
		local object = fields
		object.__fake = className
		object.ClassName = className
		object.IsA = function(_, name)
			return name == className or (name == "BasePart" and className == "Part") or (name == "Instance")
		end
		object.FindFirstChild = function(self, name)
			local child = rawget(self, "children") and self.children[name]
			return child
		end
		object.FindFirstChildOfClass = function(self, name)
			for _, child in rawget(self, "children") or {} do
				if child.ClassName == name then
					return child
				end
			end
			return nil
		end
		object.GetAttribute = function(self, name)
			return (rawget(self, "attributes") or {})[name]
		end
		object.HasTag = function(self, name)
			return (rawget(self, "tags") or {})[name] == true
		end
		return object
	end
	local world = fake("Workspace", {})
	-- R15 몸: 기본 붙이개 그대로
	local function character(name: string, rigType: any): any
		local model = fake("Model", { Name = name, Parent = world, children = {} })
		local function addPart(partName: string, cf: CFrame?)
			local part =
				fake("Part", { Name = partName, Parent = model, children = {}, CFrame = cf or CFrame.identity })
			part.Position = part.CFrame.Position
			model.children[partName] = part
			return part
		end
		local root = addPart("HumanoidRootPart", CFrame.new(0, 3, 0))
		local function joint(partName: string, jointName: string, c0: CFrame, c1: CFrame)
			local part = model.children[partName] or addPart(partName)
			part.children[jointName] =
				fake("Motor6D", { Name = jointName, Parent = part, C0 = c0, C1 = c1, Transform = CFrame.identity })
		end
		for jointName, partName in
			{
				Root = "LowerTorso",
				Waist = "UpperTorso",
				Neck = "Head",
				RightHip = "RightUpperLeg",
				LeftHip = "LeftUpperLeg",
				RightKnee = "RightLowerLeg",
				LeftKnee = "LeftLowerLeg",
			}
		do
			joint(partName, jointName, BODY[jointName][1], BODY[jointName][2])
		end
		for _, side in { "Right", "Left" } do
			local arm = if side == "Right" then RIG.right else RIG.left
			joint(side .. "UpperArm", side .. "Shoulder", arm.s0, arm.s1)
			joint(side .. "LowerArm", side .. "Elbow", arm.e0, arm.e1)
			joint(side .. "Hand", side .. "Wrist", arm.w0, arm.w1)
			model.children[side .. "Hand"].children[side .. "GripAttachment"] =
				fake("Attachment", { Name = side .. "GripAttachment", CFrame = arm.grip })
		end
		local humanoid = fake("Humanoid", { RigType = rigType, Health = 100, Sit = false, Parent = model })
		humanoid.GetState = function()
			return Enum.HumanoidStateType.Running
		end
		model.children.Humanoid = humanoid
		return model, root
	end
	local function tool(kind: string, grade: number): any
		local tip = fake("Attachment", { Name = "TrailTip", WorldPosition = Vector3.new(1, 4, -3) })
		local handle = fake("Part", { Name = "Handle", children = { TrailTip = tip } })
		return fake("Tool", {
			Name = kind,
			children = { Handle = handle },
			attributes = { Weapon = kind, Grade = grade },
			tags = { Weapon = true },
			Activated = signal(),
		})
	end
	local function hold(model: any, item: any?)
		for key, child in model.children do
			if child.ClassName == "Tool" then
				model.children[key] = nil
				child.Parent = nil
			end
		end
		if item then
			model.children.Tool = item
			item.Parent = model
		end
	end

	local me = fake("Player", { Name = "나" })
	local other = fake("Player", { Name = "남" })
	local r6 = fake("Player", { Name = "R6" })
	me.Character = character("나", Enum.HumanoidRigType.R15)
	other.Character = character("남", Enum.HumanoidRigType.R15)
	r6.Character = character("R6", Enum.HumanoidRigType.R6)
	local preSimulation = signal()
	local services = {
		CollectionService = {
			GetTagged = function()
				return {}
			end,
		},
		Players = {
			LocalPlayer = me,
			GetPlayers = function()
				return { me, other, r6 }
			end,
		},
		RunService = { PreSimulation = preSimulation },
		Workspace = { CurrentCamera = { CFrame = CFrame.new(0, 6, 12) } },
		ReplicatedStorage = {
			WaitForChild = function()
				return shared
			end,
			FindFirstChild = function()
				return nil
			end,
		},
	}
	local clientEnv = table.clone(env)
	clientEnv.game = {
		GetService = function(_, name)
			return services[name] or {}
		end,
	}
	clientEnv.os = setmetatable({
		clock = function()
			return clock
		end,
	}, { __index = os })
	clientEnv.typeof = function(value)
		if type(value) == "table" and rawget(value, "__fake") then
			return "Instance"
		end
		return typeof(value)
	end
	local clientLoader = Harness.new(clientEnv)
	local client = clientLoader.folder("src/client")
	local WeaponEffects = clientLoader.require(client.WeaponEffects)
	local calls = { swing = {}, wave = {} }
	local stop = 0
	WeaponEffects.swing = function(...)
		table.insert(calls.swing, { ... })
	end
	WeaponEffects.wave = function(...)
		table.insert(calls.wave, { ... })
	end
	WeaponEffects.hitstop = function()
		return stop
	end
	local WeaponAnim = clientLoader.require(client.WeaponAnim)
	WeaponAnim.start()

	local mine = me.Character
	local function jointOf(model: any, partName: string, jointName: string): any
		return model.children[partName].children[jointName]
	end
	local shoulder = jointOf(mine, "RightUpperArm", "RightShoulder")
	local waist = jointOf(mine, "UpperTorso", "Waist")
	local animated = CFrame.Angles(0, 0.1, 0) -- Animator 가 허리에 쓴 값이라 친다
	local function frame(dt: number, animator: boolean?)
		clock += dt
		if animator ~= false then
			waist.Transform = animated
			shoulder.Transform = CFrame.Angles(math.rad(90), 0, 0) -- 기본 toolnone 자세
		end
		preSimulation.fire(dt)
	end
	local function run(seconds: number, animator: boolean?)
		local t = 0
		while t < seconds - 1e-9 do
			frame(1 / 60, animator)
			t += 1 / 60
		end
	end
	local function turned(a: CFrame, b: CFrame): number
		local _, angle = (a:Inverse() * b):ToAxisAngle()
		return math.deg(math.abs(angle))
	end
	local function close(a: CFrame, b: CFrame, what: string)
		near((a.Position - b.Position).Magnitude, 0, 1e-3, what .. " 자리")
		near(a.LookVector:Dot(b.LookVector), 0.9999, 1.0001, what .. " 앞")
		near(a.UpVector:Dot(b.UpVector), 0.9999, 1.0001, what .. " 위")
	end

	-- 무기를 안 들면 건드리지 않는다
	run(0.1)
	close(shoulder.Transform, CFrame.Angles(math.rad(90), 0, 0), "무기 없을 때 어깨")

	-- 검을 든다: 0.1초 동안 섞여 들어가 든 자세가 된다
	local sword = tool("sword", 3)
	hold(mine, sword)
	frame(1 / 60)
	local arms, body = WeaponPoses.solve(RIG, WeaponPoses.idle("sword", clock))
	local half = shoulder.Transform
	assert(not (half.LookVector:Dot(arms.RightShoulder.LookVector) > 0.9999), "첫 프레임은 아직 섞이는 중")
	run(0.2)
	-- 숨쉬기 위상은 캐릭터마다 다르므로 같은 자세 계열인지만 본다 (든 자세와 몇 도 안)
	arms, body = WeaponPoses.solve(RIG, WeaponPoses.idle("sword", 0))
	near(turned(shoulder.Transform, arms.RightShoulder), 0, 6, "든 자세 어깨")
	-- 허리는 Animator 값 앞에 곱한다. Animator 가 한 프레임 쉬어도 겹쳐 곱하지 않는다
	local withAnimator = waist.Transform
	near((withAnimator * animated:Inverse()).LookVector:Dot(body.Waist.LookVector), 0.995, 1.001, "허리 덧곱")
	frame(1 / 60, false)
	frame(1 / 60, false)
	near(
		waist.Transform.LookVector:Dot(withAnimator.LookVector),
		0.9995,
		1.0001,
		"Animator 가 쉬어도 허리가 돌아가지 않는다"
	)

	-- 내 휘두르기: Activated → 바로 몸짓, WeaponEffects.swing (젖힘~따라감 길이)
	sword.Activated.fire()
	assert(#calls.swing == 1, "swing 을 불러야 한다")
	local call = calls.swing[1]
	local a1 = WeaponPoses.attack("sword", 1)
	assert(
		call[1] == mine and call[2] == sword and call[3] == "sword" and call[4] == 3 and call[5] == 1,
		"swing 인자"
	)
	near(call[6], a1.windup + a1.strike + a1.follow - 1e-6, a1.windup + a1.strike + a1.follow + 1e-6, "swing 길이")
	local before = shoulder.Transform
	run(a1.hit)
	near(turned(shoulder.Transform, before), 30, 180, "벨 때 어깨가 크게 돈다")
	-- 쿨타임 안에 다시 누르면 넘긴다
	sword.Activated.fire()
	assert(#calls.swing == 1, "쿨타임 안 클릭은 넘긴다")
	-- 맞힘 멈춤: hitstop 이 남은 동안 몸짓이 멈춘다
	stop = 0.06
	frame(1 / 60)
	local frozen = shoulder.Transform
	frame(1 / 60)
	close(shoulder.Transform, frozen, "멈춘 동안 어깨")
	stop = 0
	clock += 0.2
	frame(1 / 60)
	run(0.6)
	-- 쿨타임이 지나 1.2 초 안이면 다음 수
	sword.Activated.fire()
	assert(#calls.swing == 2 and calls.swing[2][5] == 2, "둘째 수")
	run(0.5)
	clock += 2
	sword.Activated.fire()
	assert(#calls.swing == 3 and calls.swing[3][5] == 1, "오래 쉬면 첫 수")
	run(0.6)

	-- 부채: 벰이 닿을 때 내 바람칼을 TrailTip 에서 날리고, 서버 "wave" 는 한 번 넘긴다
	local fan = tool("fan", 4)
	hold(mine, fan)
	run(0.2)
	fan.Activated.fire()
	local fanAttack = WeaponPoses.attack("fan", 1)
	run(fanAttack.hit + 0.02)
	assert(#calls.wave == 1, "바람칼 하나")
	local wave = calls.wave[1]
	close(CFrame.new(wave[1]), CFrame.new(1, 4, -3), "바람칼 시작은 TrailTip")
	assert(wave[3] == 4 and wave[4] == false, "등급과 hit")
	near(
		(wave[2] - wave[1]).Magnitude,
		Combat.KINDS.fan.range - 0.01,
		Combat.KINDS.fan.range + 0.01,
		"빗나가면 닿는 끝까지"
	)
	assert(WeaponAnim.consumeWave() == true, "내 바람칼은 이미 그렸다")
	assert(WeaponAnim.consumeWave() == false, "한 번만 넘긴다")
	run(1)

	-- 남의 휘두르기: 서버 swing 소식으로. 내 것은 넘긴다
	local spear = tool("spear", 2)
	hold(other.Character, spear)
	run(0.2)
	local count = #calls.swing
	WeaponAnim.remoteSwing({ kind = "swing", player = me, weapon = "fan", grade = 4, combo = 1 })
	assert(#calls.swing == count, "내 swing 소식은 넘긴다")
	local otherShoulder = jointOf(other.Character, "RightUpperArm", "RightShoulder")
	local otherBefore = otherShoulder.Transform
	WeaponAnim.remoteSwing({ kind = "swing", player = other, weapon = "spear", grade = 2, combo = 1 })
	assert(#calls.swing == count + 1 and calls.swing[count + 1][1] == other.Character, "남의 swing")
	run(WeaponPoses.attack("spear", 1).hit)
	assert(not (otherShoulder.Transform.LookVector:Dot(otherBefore.LookVector) > 0.9999), "남의 몸이 찌른다")

	-- R6 는 건드리지 않는다
	local r6Shoulder = jointOf(r6.Character, "RightUpperArm", "RightShoulder")
	hold(r6.Character, tool("sword", 1))
	run(0.2)
	close(r6Shoulder.Transform, CFrame.identity, "R6 어깨")

	-- 내려놓으면 0.1초 동안 풀리고 Animator 값으로 돌아간다
	hold(mine, nil)
	run(0.2)
	close(shoulder.Transform, CFrame.Angles(math.rad(90), 0, 0), "내려놓은 뒤 어깨")
	close(waist.Transform, animated, "내려놓은 뒤 허리")
	-- 앉으면(운기조식) 푼다
	hold(mine, sword)
	run(0.2)
	mine.children.Humanoid.Sit = true
	run(0.2)
	close(shoulder.Transform, CFrame.Angles(math.rad(90), 0, 0), "앉으면 어깨")
end)

print(`\n통과 {passed} · 실패 {failed}`)
if failed > 0 then
	error("테스트 실패")
end
