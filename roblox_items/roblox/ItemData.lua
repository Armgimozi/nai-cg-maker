-- 자동 생성 파일 (roblox_items/tools/make_luau.py) — 직접 고치지 말 것
-- 방어구: 부위(R15) 중심 기준 offset / size  (기준 체형 = R15 기본, 스터드)
-- 아이템: size = 실제 크기(스터드), grip = Handle 중심 기준 손잡이 위치

local ItemData = {}

ItemData.Armor = {
	leather = {
		name = "가죽",
		helmet = { -- 가죽 투구
			Head = { offset = Vector3.new(-0.0000, 0.1838, 0.0000), size = Vector3.new(1.5799, 1.3476, 1.5800) },
		},
		chest = { -- 가죽 갑옷
			UpperTorso = { offset = Vector3.new(-0.0000, 0.0273, -0.0059), size = Vector3.new(2.3400, 1.9147, 1.4419) },
			LowerTorso = { offset = Vector3.new(-0.0000, -0.2114, 0.0000), size = Vector3.new(2.4680, 0.7328, 1.5490) },
			RightUpperArm = { offset = Vector3.new(0.2348, 0.2510, 0.0000), size = Vector3.new(1.5337, 1.3861, 1.7240) },
			LeftUpperArm = { offset = Vector3.new(-0.2348, 0.2510, 0.0000), size = Vector3.new(1.5337, 1.3861, 1.7240) },
		},
		greaves = { -- 가죽 각반
			RightUpperLeg = { offset = Vector3.new(0.0093, 0.0137, -0.0624), size = Vector3.new(1.4103, 1.0722, 1.3047) },
			LeftUpperLeg = { offset = Vector3.new(-0.0093, 0.0137, -0.0624), size = Vector3.new(1.4103, 1.0722, 1.3047) },
			RightLowerLeg = { offset = Vector3.new(-0.0000, 0.0544, -0.0640), size = Vector3.new(1.4100, 1.4681, 1.5379) },
			LeftLowerLeg = { offset = Vector3.new(-0.0000, 0.0544, -0.0640), size = Vector3.new(1.4100, 1.4681, 1.5379) },
			RightFoot = { offset = Vector3.new(-0.0000, 0.0791, -0.0384), size = Vector3.new(1.2192, 0.5526, 1.3264) },
			LeftFoot = { offset = Vector3.new(-0.0000, 0.0791, -0.0384), size = Vector3.new(1.2192, 0.5526, 1.3264) },
		},
	},
	iron = {
		name = "철",
		helmet = { -- 철 투구
			Head = { offset = Vector3.new(-0.0000, 0.1686, 0.0099), size = Vector3.new(1.6478, 1.6973, 1.6278) },
		},
		chest = { -- 철 갑옷
			UpperTorso = { offset = Vector3.new(-0.0000, 0.0248, -0.0264), size = Vector3.new(2.3007, 1.9197, 1.4928) },
			LowerTorso = { offset = Vector3.new(-0.0000, -0.2325, 0.0000), size = Vector3.new(2.5000, 0.7750, 1.5800) },
			RightUpperArm = { offset = Vector3.new(0.2348, 0.2510, 0.0000), size = Vector3.new(1.5337, 1.3861, 1.7240) },
			LeftUpperArm = { offset = Vector3.new(-0.2348, 0.2510, 0.0000), size = Vector3.new(1.5337, 1.3861, 1.7240) },
		},
		greaves = { -- 철 각반
			RightUpperLeg = { offset = Vector3.new(0.0082, 0.0150, -0.0704), size = Vector3.new(1.4356, 1.1220, 1.3108) },
			LeftUpperLeg = { offset = Vector3.new(-0.0082, 0.0150, -0.0704), size = Vector3.new(1.4356, 1.1220, 1.3108) },
			RightLowerLeg = { offset = Vector3.new(0.0478, 0.1020, -0.0460), size = Vector3.new(1.4815, 1.5800, 1.6636) },
			LeftLowerLeg = { offset = Vector3.new(-0.0478, 0.1020, -0.0460), size = Vector3.new(1.4815, 1.5800, 1.6636) },
			RightFoot = { offset = Vector3.new(-0.0000, 0.0791, -0.0384), size = Vector3.new(1.2498, 0.5526, 1.3264) },
			LeftFoot = { offset = Vector3.new(-0.0000, 0.0791, -0.0384), size = Vector3.new(1.2498, 0.5526, 1.3264) },
		},
	},
	knight = {
		name = "기사",
		helmet = { -- 기사 투구
			Head = { offset = Vector3.new(-0.0000, 0.1721, -0.0259), size = Vector3.new(1.6600, 1.8142, 1.7644) },
		},
		chest = { -- 기사 갑옷
			UpperTorso = { offset = Vector3.new(-0.0000, 0.0225, -0.0536), size = Vector3.new(2.3006, 1.9250, 1.5571) },
			LowerTorso = { offset = Vector3.new(-0.0000, -0.1835, 0.0000), size = Vector3.new(2.6040, 0.6770, 1.6840) },
			RightUpperArm = { offset = Vector3.new(0.2703, 0.1661, 0.0000), size = Vector3.new(1.6936, 1.5562, 1.9152) },
			LeftUpperArm = { offset = Vector3.new(-0.2703, 0.1661, 0.0000), size = Vector3.new(1.6936, 1.5562, 1.9152) },
		},
		greaves = { -- 기사 각반
			RightUpperLeg = { offset = Vector3.new(0.0082, 0.0150, -0.0704), size = Vector3.new(1.4356, 1.1220, 1.3108) },
			LeftUpperLeg = { offset = Vector3.new(-0.0082, 0.0150, -0.0704), size = Vector3.new(1.4356, 1.1220, 1.3108) },
			RightLowerLeg = { offset = Vector3.new(0.0478, 0.1020, -0.0460), size = Vector3.new(1.4815, 1.5800, 1.6636) },
			LeftLowerLeg = { offset = Vector3.new(-0.0478, 0.1020, -0.0460), size = Vector3.new(1.4815, 1.5800, 1.6636) },
			RightFoot = { offset = Vector3.new(-0.0000, 0.0791, -0.0384), size = Vector3.new(1.2498, 0.5526, 1.3264) },
			LeftFoot = { offset = Vector3.new(-0.0000, 0.0791, -0.0384), size = Vector3.new(1.2498, 0.5526, 1.3264) },
		},
	},
}

ItemData.Items = {
	iron_longsword = { kind = "weapon", name = "철 롱소드", size = Vector3.new(0.3320, 4.4000, 0.8109), grip = Vector3.new(0.0002, -1.7160, 0.0004) },
	battle_axe = { kind = "weapon", name = "전투 도끼", size = Vector3.new(0.2675, 4.0000, 1.3531), grip = Vector3.new(0.0019, -1.2000, 0.1918) },
	spear = { kind = "weapon", name = "창", size = Vector3.new(0.4663, 7.0000, 0.4687), grip = Vector3.new(-0.0242, -0.8400, 0.0007) },
	longbow = { kind = "weapon", name = "장궁", size = Vector3.new(0.2740, 4.8000, 0.3811), grip = Vector3.new(0.0030, 0.0000, -0.0631) },
	mage_staff = { kind = "weapon", name = "마법 지팡이", size = Vector3.new(2.9326, 5.6000, 0.7995), grip = Vector3.new(0.3421, -0.2800, 0.0146), glow = Color3.new(0.45, 0.75, 1.00) },
	dagger = { kind = "weapon", name = "단검", size = Vector3.new(0.1059, 1.9000, 0.3877), grip = Vector3.new(0.0103, -0.7030, 0.0271) },
	guardian_amulet = { kind = "artifact", name = "수호의 부적", size = Vector3.new(0.6558, 0.9000, 0.2045), grip = Vector3.new(0.0000, -0.4000, 0.0000), glow = Color3.new(0.35, 0.55, 1.00) },
	flame_ring = { kind = "artifact", name = "화염의 반지", size = Vector3.new(0.5742, 0.7000, 0.4770), grip = Vector3.new(0.0000, -0.3000, 0.0000), glow = Color3.new(1.00, 0.40, 0.20) },
	arcane_orb = { kind = "artifact", name = "비전 오브", size = Vector3.new(1.0274, 1.2000, 0.8492), grip = Vector3.new(0.0000, -0.5500, 0.0000), glow = Color3.new(0.70, 0.40, 1.00) },
	chalice_of_life = { kind = "artifact", name = "생명의 성배", size = Vector3.new(0.8264, 1.2000, 0.8258), grip = Vector3.new(0.0000, -0.5500, 0.0000) },
	ancient_runestone = { kind = "artifact", name = "고대 룬석", size = Vector3.new(0.5871, 1.3000, 0.4098), grip = Vector3.new(0.0000, -0.6000, 0.0000), glow = Color3.new(0.35, 0.95, 1.00) },
}

return ItemData
