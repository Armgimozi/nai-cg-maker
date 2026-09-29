--!strict
-- 게임 전체 밸런스/설정 값. 숫자만 바꿔서 난이도를 조절할 수 있습니다.

local Config = {
	-- 굴리기 --------------------------------------------------------------
	ROLL_COOLDOWN = 1.2, -- 굴리기 사이 최소 간격(초). 서버가 강제합니다.
	COOLDOWN_TOLERANCE = 0.15, -- 네트워크 지연을 감안한 허용 오차(초)
	BASE_LUCK = 1,

	-- N번째 굴림마다 행운 보너스 ("행운 굴림")
	LUCKY_ROLL_EVERY = 10,
	LUCKY_ROLL_MULT = 2,

	-- 1/N 이상 희귀한 오라를 뽑으면 서버 전체에 알림
	ANNOUNCE_ONE_IN = 1000,

	-- 굴림 1회당 코인 = ceil(N ^ COIN_EXPONENT)
	COIN_EXPONENT = 0.35,

	-- 저장 ---------------------------------------------------------------
	DATASTORE_NAME = "AuraRNG_v1",
	AUTOSAVE_INTERVAL = 120,

	-- 물약(상점) ------------------------------------------------------------
	-- LuckMult: 행운 배수, CooldownMult: 굴림 간격 배수
	-- 같은 물약을 또 사면 효과는 중첩되지 않고 지속 시간만 늘어납니다(최대 MAX_POTION_SECONDS).
	MAX_POTION_SECONDS = 60 * 60,
	Potions = {
		{
			Id = "Luck",
			Name = "행운 물약",
			Description = "5분 동안 행운 x1.5",
			Price = 300,
			Duration = 300,
			LuckMult = 1.5,
			CooldownMult = 1,
			Color = Color3.fromRGB(90, 220, 120),
		},
		{
			Id = "Speed",
			Name = "신속 물약",
			Description = "5분 동안 굴림 속도 +40%",
			Price = 400,
			Duration = 300,
			LuckMult = 1,
			CooldownMult = 0.6,
			Color = Color3.fromRGB(90, 170, 255),
		},
		{
			Id = "Fortune",
			Name = "대박 물약",
			Description = "3분 동안 행운 x3",
			Price = 2500,
			Duration = 180,
			LuckMult = 3,
			CooldownMult = 1,
			Color = Color3.fromRGB(255, 200, 60),
		},
	},
}

return Config
