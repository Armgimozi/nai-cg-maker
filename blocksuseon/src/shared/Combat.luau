-- 전투 공식과 무기. 순수 계산만 있다 (서버 CombatService 와 화면이 같이 쓴다).
-- 숫자는 게임 밸런스 값이다.

local Races = require(script.Parent.Races)

local Combat = {}

-- 무기 종류
--   damage   피해 배율
--   cooldown 휘두르는 간격(초)
--   range    닿는 거리 (스터드)
--   arc      앞쪽 몇 도 안을 벨 수 있나 (양쪽 합)
--   ranged   true 면 앞으로 기운을 날린다 (range 까지 처음 맞는 것 하나)
export type WeaponKind = {
	id: string,
	suffix: string,
	damage: number,
	cooldown: number,
	range: number,
	arc: number,
	ranged: boolean?,
	summary: string,
}

Combat.KINDS = {
	sword = {
		id = "sword",
		suffix = "검",
		damage = 1,
		cooldown = 0.45,
		range = 8,
		arc = 100,
		summary = "빠르고 넓게 벤다.",
	},
	saber = {
		id = "saber",
		suffix = "도",
		damage = 1.5,
		cooldown = 0.75,
		range = 8,
		arc = 120,
		summary = "느리지만 무겁다.",
	},
	spear = {
		id = "spear",
		suffix = "창",
		damage = 1.15,
		cooldown = 0.6,
		range = 12,
		arc = 40,
		summary = "멀리 찌른다.",
	},
	fan = {
		id = "fan",
		suffix = "선",
		damage = 0.85,
		cooldown = 0.8,
		range = 36,
		arc = 0,
		ranged = true,
		summary = "부채질로 기운을 날린다.",
	},
} :: { [string]: WeaponKind }
Combat.KIND_ORDER = { "sword", "saber", "spear", "fan" }

-- Meshy 로 만든 무기 모델 (tools/meshy/specs.json → manifest.json). 종류마다, 등급마다 하나씩.
--   length 모델 가장 긴 변(스터드). 긴 변이 모델의 세로(Y)다
--   tip    날 끝이 +Y 쪽(1)인지 -Y 쪽(-1)인지
--   grip   손이 쥐는 자리. 모델 가운데에서 세로로 떨어진 거리를 가장 긴 변으로 나눈 값
export type MeshSpec = { asset: number, length: number, tip: number, grip: number }
Combat.MESH = {
	sword = {
		[1] = { asset = 104142329142830, length = 4.5, tip = -1, grip = 0.351 }, -- 목검: 결이 보이는 연한 나무, 쇠붙이 없음
		[2] = { asset = 73087619795995, length = 4.5, tip = -1, grip = 0.334 }, -- 철검: 검은 쇠날, 가죽 손잡이
		[3] = { asset = 117737538022358, length = 4.5, tip = -1, grip = 0.281 }, -- 청강검: 은빛 날, 옥 등줄
		[4] = { asset = 128296069136061, length = 4.5, tip = 1, grip = -0.246 }, -- 영검: 비취 수정 날, 흰 옥 코등이
		[5] = { asset = 91449203543147, length = 4.5, tip = -1, grip = 0.334 }, -- 천검: 흰 금빛 날, 금 코등이
	},
	saber = {
		[1] = { asset = 120663707114268, length = 4.2, tip = 1, grip = -0.281 }, -- 목도: 나무 휜 날, 둥근 나무 코등이
		[2] = { asset = 80885908489967, length = 4.2, tip = -1, grip = 0.281 }, -- 철도: 쇠 날, 놋쇠 코등이
		[3] = { asset = 73538137552824, length = 4.2, tip = -1, grip = 0.334 }, -- 청강도: 푸른 강철 날, 은 코등이
		[4] = { asset = 73365262422346, length = 4.2, tip = 1, grip = -0.334 }, -- 영도: 넓은 비취 날, 흰 옥 코등이
		[5] = { asset = 97821682414639, length = 4.2, tip = -1, grip = 0.385 }, -- 천도: 흰 금빛 날, 구름무늬 금 코등이
	},
	spear = {
		[1] = { asset = 115297038342490, length = 8, tip = 1, grip = -0.12 }, -- 목창: 나무 자루, 나무 잎날
		[2] = { asset = 87579725321424, length = 8, tip = 1, grip = -0.12 }, -- 철창: 붉은 옻 자루, 쇠 날, 붉은 술
		[3] = { asset = 123876479650138, length = 8, tip = 1, grip = -0.12 }, -- 청강창: 남색 자루, 푸른 강철 날
		[4] = { asset = 98483663850535, length = 8, tip = 1, grip = -0.12 }, -- 영창: 흰 옥 자루, 비취 수정 날
		[5] = { asset = 108593917905308, length = 8, tip = 1, grip = -0.12 }, -- 천창: 흰 자루, 흰 연꽃 금 날
	},
	fan = {
		[1] = { asset = 125930421375492, length = 3, tip = 1, grip = -0.235 }, -- 죽선: 대나무 살, 흰 종이
		[2] = { asset = 73743642074002, length = 3, tip = 1, grip = -0.21 }, -- 철선: 쇠 살, 잿빛 천
		[3] = { asset = 90072943116000, length = 3, tip = 1, grip = -0.27 }, -- 청강선: 쇠 살, 학 그린 비취 비단
		[4] = { asset = 78530076214418, length = 3, tip = 1, grip = -0.15 }, -- 영선: 흰 옥 살, 비취빛 비단
		[5] = { asset = 98897519397317, length = 3, tip = 1, grip = -0.1 }, -- 천선: 금 살, 금 구름무늬 흰 비단
	},
} :: { [string]: { [number]: MeshSpec } }

-- 이 무기의 모델. 그 등급 모델이 없으면 가장 가까운 등급 모델
function Combat.meshFor(weapon: Weapon): MeshSpec?
	local byGrade = Combat.MESH[weapon.kind]
	if not byGrade then
		return nil
	end
	for offset = 0, #Combat.GRADES do
		local spec = byGrade[weapon.grade - offset] or byGrade[weapon.grade + offset]
		if spec and spec.asset > 0 then
			return spec
		end
	end
	return nil
end

-- 등급: 이름 앞말과 피해 배율. 요수 위험도(1~5)와 같은 등급이 떨어진다
Combat.GRADES = {
	{ prefix = "목", mult = 1 },
	{ prefix = "철", mult = 1.3 },
	{ prefix = "청강", mult = 1.7 },
	{ prefix = "영", mult = 2.2 },
	{ prefix = "천", mult = 2.9 },
}
-- 부채는 첫 등급만 이름이 다르다 (목선 대신 죽선)
local FAN_FIRST = "죽"

Combat.MAX_WEAPONS = 9 -- 숫자 키 1~9

export type Weapon = { kind: string, grade: number }

function Combat.isWeapon(value: any): boolean
	return type(value) == "table"
		and Combat.KINDS[value.kind] ~= nil
		and type(value.grade) == "number"
		and value.grade % 1 == 0
		and value.grade >= 1
		and value.grade <= #Combat.GRADES
end

function Combat.weaponName(weapon: Weapon): string
	local kind = Combat.KINDS[weapon.kind]
	local prefix = if weapon.kind == "fan" and weapon.grade == 1 then FAN_FIRST else Combat.GRADES[weapon.grade].prefix
	return prefix .. kind.suffix
end

-- 경지 단계에 따른 맨 공격력 (단계마다 9%씩)
function Combat.basePower(step: number): number
	return 12 * 1.09 ^ (step - 1)
end

-- 한 번 휘두를 때 피해
function Combat.damage(step: number, weapon: Weapon, race: string?): number
	local kind = Combat.KINDS[weapon.kind]
	return Combat.basePower(step) * kind.damage * Combat.GRADES[weapon.grade].mult * Races.mult(race, "attack")
end

-- 요수가 앞에 있나: 내 위치, 보는 방향(수평 단위), 요수 위치와 몸 반지름
function Combat.inReach(
	fromX: number,
	fromZ: number,
	lookX: number,
	lookZ: number,
	toX: number,
	toZ: number,
	radius: number,
	weapon: Weapon
): boolean
	local kind = Combat.KINDS[weapon.kind]
	local dx, dz = toX - fromX, toZ - fromZ
	local distance = math.sqrt(dx * dx + dz * dz)
	if distance > kind.range + radius then
		return false
	end
	if distance < radius + 1.5 then
		return true -- 붙어 있으면 방향과 상관없이
	end
	if kind.ranged then
		-- 날리는 기운: 앞쪽 줄 위에 있나 (줄에서 비켜난 거리가 몸 반지름 + 2 안)
		local along = dx * lookX + dz * lookZ
		local side = math.abs(dx * lookZ - dz * lookX)
		return along > 0 and side <= radius + 2
	end
	local cos = (dx * lookX + dz * lookZ) / distance
	return cos >= math.cos(math.rad(kind.arc / 2))
end

return Combat
