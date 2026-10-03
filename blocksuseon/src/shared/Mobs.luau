-- 요수(妖獸). 땅의 위험도(1~5)에 맞춰 나오는 적대 짐승들. 게임에서 만든 짐승이다.
-- 모습은 Meshy 로 만든 모델(asset)을 쓰고, 없거나 못 불러오면 아래 블록 모양(parts)으로 짓는다.
-- 숫자는 게임 밸런스 값이다.

export type Part = {
	name: string,
	size: { number }, -- x, y, z
	at: { number }, -- 몸 가운데(뿌리)에서 떨어진 자리 x, y, z (앞이 -z)
	color: { number },
	material: string?,
	shape: string?, -- "Ball" | "Cylinder"
	neon: boolean?,
}

export type Mob = {
	id: string,
	name: string,
	tier: number,
	places: { string }, -- 잘 나오는 땅 (Places.luau 의 id). 비면 그 위험도 어디서나
	hp: number,
	damage: number,
	speed: number, -- 쫓을 때 걸음
	aggro: number, -- 알아채는 거리
	reach: number, -- 무는 거리
	windup: number, -- 덤비기 전 뜸(초). 이때 발밑에 붉은 원이 보인다
	cooldown: number,
	radius: number, -- 몸 반지름 (맞는 판정)
	height: number, -- 뿌리 높이 (땅에서 몸 가운데까지)
	color: { number }, -- 맞았을 때 번쩍이는 빛
	asset: number?, -- Meshy 모델 에셋 id (InsertService)
	assetSize: number?, -- 모델 가장 긴 변을 이 길이로 맞춘다
	anim: string?, -- 움직임 꼴: quad(네 발) serpent bird biped crawler (client/MobAnimator.luau)
	fly: boolean?, -- 땅에서 떠서 난다
	parts: { Part },
}

local Mobs = {}

Mobs.TIER_NAMES = { "약한 요수", "요수", "사나운 요수", "대요수", "요왕" }

-- 위험도마다 잡으면 나오는 요단 개수와 무기가 떨어질 확률
Mobs.LOOT = {
	{ cores = 1, weapon = 0.06 },
	{ cores = 1, weapon = 0.07 },
	{ cores = 2, weapon = 0.08 },
	{ cores = 2, weapon = 0.08 },
	{ cores = 3, weapon = 0.1 },
}

local GREY = { 120, 118, 116 }

Mobs.list = {
	{
		id = "ashwolf",
		name = "잿빛이리",
		tier = 1,
		places = { "forest", "fields", "steppe" },
		hp = 60,
		damage = 8,
		speed = 15,
		aggro = 30,
		reach = 5,
		windup = 0.35,
		cooldown = 1.4,
		radius = 2.2,
		height = 2.4,
		color = { 200, 200, 210 },
		parts = {
			{ name = "Body", size = { 2.2, 2, 5 }, at = { 0, 0.4, 0 }, color = GREY },
			{ name = "Head", size = { 1.8, 1.6, 2 }, at = { 0, 1.2, -3 }, color = GREY },
			{ name = "Snout", size = { 1, 0.8, 1.2 }, at = { 0, 0.9, -4.4 }, color = { 90, 88, 86 } },
			{ name = "EarL", size = { 0.4, 0.8, 0.3 }, at = { -0.55, 2.3, -2.8 }, color = { 90, 88, 86 } },
			{ name = "EarR", size = { 0.4, 0.8, 0.3 }, at = { 0.55, 2.3, -2.8 }, color = { 90, 88, 86 } },
			{ name = "Leg", size = { 0.6, 1.8, 0.6 }, at = { -0.7, -1.3, -1.8 }, color = { 90, 88, 86 } },
			{ name = "Leg", size = { 0.6, 1.8, 0.6 }, at = { 0.7, -1.3, -1.8 }, color = { 90, 88, 86 } },
			{ name = "Leg", size = { 0.6, 1.8, 0.6 }, at = { -0.7, -1.3, 1.8 }, color = { 90, 88, 86 } },
			{ name = "Leg", size = { 0.6, 1.8, 0.6 }, at = { 0.7, -1.3, 1.8 }, color = { 90, 88, 86 } },
			{ name = "Tail", size = { 0.6, 0.6, 2.2 }, at = { 0, 0.9, 3.4 }, color = GREY },
			{ name = "Eye", size = { 0.3, 0.3, 0.2 }, at = { -0.45, 1.5, -4 }, color = { 255, 200, 90 }, neon = true },
			{ name = "Eye", size = { 0.3, 0.3, 0.2 }, at = { 0.45, 1.5, -4 }, color = { 255, 200, 90 }, neon = true },
		},
	},
	{
		id = "thornboar",
		name = "가시멧돼지",
		tier = 1,
		places = { "forest", "fields" },
		hp = 85,
		damage = 10,
		speed = 13,
		aggro = 22,
		reach = 5,
		windup = 0.5,
		cooldown = 1.8,
		radius = 2.6,
		height = 2.6,
		color = { 220, 160, 120 },
		parts = {
			{ name = "Body", size = { 3, 2.6, 5 }, at = { 0, 0.4, 0 }, color = { 96, 70, 54 } },
			{ name = "Head", size = { 2.2, 2, 1.8 }, at = { 0, 0.4, -3.2 }, color = { 86, 62, 48 } },
			{ name = "Tusk", size = { 0.3, 0.3, 1.2 }, at = { -0.7, 0, -4.3 }, color = { 240, 230, 210 } },
			{ name = "Tusk", size = { 0.3, 0.3, 1.2 }, at = { 0.7, 0, -4.3 }, color = { 240, 230, 210 } },
			{ name = "Spine", size = { 0.4, 1.2, 4 }, at = { 0, 2.2, 0 }, color = { 60, 44, 34 } },
			{ name = "Leg", size = { 0.8, 1.6, 0.8 }, at = { -1, -1.4, -1.6 }, color = { 70, 52, 40 } },
			{ name = "Leg", size = { 0.8, 1.6, 0.8 }, at = { 1, -1.4, -1.6 }, color = { 70, 52, 40 } },
			{ name = "Leg", size = { 0.8, 1.6, 0.8 }, at = { -1, -1.4, 1.6 }, color = { 70, 52, 40 } },
			{ name = "Leg", size = { 0.8, 1.6, 0.8 }, at = { 1, -1.4, 1.6 }, color = { 70, 52, 40 } },
		},
	},
	{
		id = "bluescale",
		name = "청린사",
		tier = 2,
		places = { "gorge", "pool", "haeryong", "sea" },
		hp = 180,
		damage = 16,
		speed = 14,
		aggro = 32,
		reach = 7,
		windup = 0.45,
		cooldown = 1.6,
		radius = 2.4,
		height = 1.6,
		color = { 120, 200, 255 },
		parts = {
			{ name = "Head", size = { 1.8, 1.4, 2.4 }, at = { 0, 1.4, -4.6 }, color = { 40, 110, 140 } },
			{ name = "Neck", size = { 1.4, 2.6, 1.4 }, at = { 0, 0.6, -3.4 }, color = { 50, 130, 160 } },
			{ name = "Coil", size = { 1.6, 1.6, 4 }, at = { 0, -0.6, -0.8 }, color = { 50, 130, 160 } },
			{ name = "Coil", size = { 1.4, 1.4, 4 }, at = { 1.2, -0.7, 2.4 }, color = { 40, 110, 140 } },
			{ name = "Tail", size = { 1, 1, 3.4 }, at = { -0.6, -0.8, 5 }, color = { 40, 110, 140 } },
			{
				name = "Eye",
				size = { 0.3, 0.3, 0.2 },
				at = { -0.5, 1.8, -5.8 },
				color = { 255, 255, 120 },
				neon = true,
			},
			{ name = "Eye", size = { 0.3, 0.3, 0.2 }, at = { 0.5, 1.8, -5.8 }, color = { 255, 255, 120 }, neon = true },
		},
	},
	{
		id = "rockbear",
		name = "바위곰",
		tier = 3,
		places = { "swaecheon", "seoak", "summit" },
		hp = 1200,
		damage = 30,
		speed = 12,
		aggro = 28,
		reach = 7,
		windup = 0.7,
		cooldown = 2.2,
		radius = 3.4,
		height = 3.6,
		color = { 220, 200, 160 },
		parts = {
			{ name = "Body", size = { 4.4, 4, 6 }, at = { 0, 0.6, 0 }, color = { 88, 74, 64 } },
			{ name = "Head", size = { 2.8, 2.6, 2.6 }, at = { 0, 1.8, -3.8 }, color = { 80, 66, 58 } },
			{ name = "Rock", size = { 3, 1.4, 3 }, at = { 0, 3.2, 0.6 }, color = GREY, material = "Slate" },
			{ name = "Leg", size = { 1.4, 2.4, 1.4 }, at = { -1.5, -2.2, -2 }, color = { 70, 58, 50 } },
			{ name = "Leg", size = { 1.4, 2.4, 1.4 }, at = { 1.5, -2.2, -2 }, color = { 70, 58, 50 } },
			{ name = "Leg", size = { 1.4, 2.4, 1.4 }, at = { -1.5, -2.2, 2 }, color = { 70, 58, 50 } },
			{ name = "Leg", size = { 1.4, 2.4, 1.4 }, at = { 1.5, -2.2, 2 }, color = { 70, 58, 50 } },
		},
	},
	{
		id = "emberbird",
		name = "적염조",
		tier = 3,
		places = { "volcano", "byeokra" },
		hp = 900,
		damage = 26,
		speed = 18,
		aggro = 36,
		reach = 6,
		windup = 0.5,
		cooldown = 1.7,
		radius = 2.6,
		height = 4,
		color = { 255, 150, 80 },
		parts = {
			{ name = "Body", size = { 2.4, 2.4, 3.6 }, at = { 0, 0, 0 }, color = { 200, 70, 40 } },
			{ name = "Head", size = { 1.6, 1.6, 1.6 }, at = { 0, 1.4, -2.2 }, color = { 220, 90, 40 } },
			{ name = "Beak", size = { 0.5, 0.5, 1.2 }, at = { 0, 1.2, -3.3 }, color = { 240, 200, 80 } },
			{ name = "Wing", size = { 4.4, 0.3, 2.4 }, at = { -3, 0.6, 0 }, color = { 240, 120, 50 }, neon = true },
			{ name = "Wing", size = { 4.4, 0.3, 2.4 }, at = { 3, 0.6, 0 }, color = { 240, 120, 50 }, neon = true },
			{ name = "Tail", size = { 1.2, 0.3, 3.6 }, at = { 0, 0.2, 3.2 }, color = { 255, 170, 60 }, neon = true },
		},
	},
	{
		id = "sandstinger",
		name = "황사갈",
		tier = 3,
		places = { "desert", "dapcheondae" },
		hp = 1000,
		damage = 28,
		speed = 14,
		aggro = 26,
		reach = 8,
		windup = 0.6,
		cooldown = 1.9,
		radius = 3,
		height = 1.6,
		color = { 255, 220, 120 },
		parts = {
			{ name = "Body", size = { 3, 1.4, 5 }, at = { 0, 0, 0 }, color = { 170, 130, 70 } },
			{ name = "Claw", size = { 1.2, 0.8, 2.4 }, at = { -2, 0, -3.6 }, color = { 150, 110, 60 } },
			{ name = "Claw", size = { 1.2, 0.8, 2.4 }, at = { 2, 0, -3.6 }, color = { 150, 110, 60 } },
			{ name = "Tail", size = { 0.8, 0.8, 3 }, at = { 0, 1.2, 3.2 }, color = { 150, 110, 60 } },
			{ name = "Tail", size = { 0.7, 2.6, 0.7 }, at = { 0, 2.8, 4.4 }, color = { 150, 110, 60 } },
			{ name = "Sting", size = { 0.5, 1.2, 0.5 }, at = { 0, 4, 3.6 }, color = { 255, 210, 90 }, neon = true },
			{ name = "Leg", size = { 2.6, 0.4, 0.4 }, at = { -2, -0.6, -1 }, color = { 140, 100, 56 } },
			{ name = "Leg", size = { 2.6, 0.4, 0.4 }, at = { 2, -0.6, -1 }, color = { 140, 100, 56 } },
			{ name = "Leg", size = { 2.6, 0.4, 0.4 }, at = { -2, -0.6, 1 }, color = { 140, 100, 56 } },
			{ name = "Leg", size = { 2.6, 0.4, 0.4 }, at = { 2, -0.6, 1 }, color = { 140, 100, 56 } },
		},
	},
	{
		id = "stonegeneral",
		name = "석장군",
		tier = 4,
		places = { "ruins", "dapcheondae", "summit", "snowfield" },
		hp = 5000,
		damage = 55,
		speed = 11,
		aggro = 30,
		reach = 9,
		windup = 0.9,
		cooldown = 2.6,
		radius = 3.6,
		height = 5.5,
		color = { 200, 240, 220 },
		parts = {
			{ name = "Torso", size = { 5, 5, 3 }, at = { 0, 1.5, 0 }, color = { 150, 140, 126 }, material = "Slate" },
			{
				name = "Head",
				size = { 2.4, 2.4, 2.4 },
				at = { 0, 5.2, 0 },
				color = { 140, 130, 118 },
				material = "Slate",
			},
			{ name = "Eye", size = { 1.6, 0.4, 0.2 }, at = { 0, 5.4, -1.3 }, color = { 120, 255, 200 }, neon = true },
			{
				name = "Arm",
				size = { 1.6, 5, 1.6 },
				at = { -3.4, 0.6, 0 },
				color = { 130, 122, 110 },
				material = "Slate",
			},
			{
				name = "Arm",
				size = { 1.6, 5, 1.6 },
				at = { 3.4, 0.6, 0 },
				color = { 130, 122, 110 },
				material = "Slate",
			},
			{
				name = "Leg",
				size = { 1.8, 3, 1.8 },
				at = { -1.3, -2.6, 0 },
				color = { 120, 112, 100 },
				material = "Slate",
			},
			{
				name = "Leg",
				size = { 1.8, 3, 1.8 },
				at = { 1.3, -2.6, 0 },
				color = { 120, 112, 100 },
				material = "Slate",
			},
		},
	},
	{
		id = "silverfox",
		name = "은미호",
		tier = 5,
		places = { "deungseon" },
		hp = 15000,
		damage = 90,
		speed = 20,
		aggro = 40,
		reach = 7,
		windup = 0.5,
		cooldown = 1.6,
		radius = 2.6,
		height = 2.8,
		color = { 220, 220, 255 },
		parts = {
			{ name = "Body", size = { 2, 2, 5 }, at = { 0, 0.4, 0 }, color = { 230, 232, 240 } },
			{ name = "Head", size = { 1.8, 1.6, 2 }, at = { 0, 1.3, -3 }, color = { 236, 238, 246 } },
			{ name = "Snout", size = { 0.8, 0.7, 1.2 }, at = { 0, 1, -4.4 }, color = { 236, 238, 246 } },
			{ name = "EarL", size = { 0.5, 1.2, 0.3 }, at = { -0.55, 2.6, -2.8 }, color = { 200, 200, 220 } },
			{ name = "EarR", size = { 0.5, 1.2, 0.3 }, at = { 0.55, 2.6, -2.8 }, color = { 200, 200, 220 } },
			{ name = "Leg", size = { 0.5, 1.8, 0.5 }, at = { -0.6, -1.4, -1.8 }, color = { 210, 212, 224 } },
			{ name = "Leg", size = { 0.5, 1.8, 0.5 }, at = { 0.6, -1.4, -1.8 }, color = { 210, 212, 224 } },
			{ name = "Leg", size = { 0.5, 1.8, 0.5 }, at = { -0.6, -1.4, 1.8 }, color = { 210, 212, 224 } },
			{ name = "Leg", size = { 0.5, 1.8, 0.5 }, at = { 0.6, -1.4, 1.8 }, color = { 210, 212, 224 } },
			{ name = "Tail", size = { 0.9, 0.9, 3.4 }, at = { -1, 1.4, 4 }, color = { 180, 200, 255 }, neon = true },
			{ name = "Tail", size = { 0.9, 0.9, 3.4 }, at = { 0, 1.8, 4.2 }, color = { 180, 200, 255 }, neon = true },
			{ name = "Tail", size = { 0.9, 0.9, 3.4 }, at = { 1, 1.4, 4 }, color = { 180, 200, 255 }, neon = true },
		},
	},
} :: { Mob }

Mobs.byId = {} :: { [string]: Mob }
Mobs.byTier = {} :: { [number]: { Mob } }
for _, mob in Mobs.list do
	Mobs.byId[mob.id] = mob
	Mobs.byTier[mob.tier] = Mobs.byTier[mob.tier] or {}
	table.insert(Mobs.byTier[mob.tier], mob)
end

-- 이 땅(Places 의 id, 위험도)에 나올 요수 하나 (roll: 0~1). 그 땅을 좋아하는 짐승을 먼저 고른다
function Mobs.pick(placeId: string, tier: number, roll: number): Mob?
	local pool = Mobs.byTier[tier]
	if not pool then
		-- 그 위험도 짐승이 없으면 한 단계 아래
		for t = tier - 1, 1, -1 do
			if Mobs.byTier[t] then
				pool = Mobs.byTier[t]
				break
			end
		end
	end
	if not pool then
		return nil
	end
	local liked = {}
	for _, mob in pool do
		if table.find(mob.places, placeId) then
			table.insert(liked, mob)
		end
	end
	local from = if #liked > 0 then liked else pool
	return from[math.clamp(math.floor(roll * #from) + 1, 1, #from)]
end

-- Meshy 로 만든 모델 (tools/meshy/specs.json → manifest.json). size 는 가장 긴 변(스터드)
local MESH = {
	ashwolf = { asset = 100330875981043, size = 6.5, anim = "quad" },
	thornboar = { asset = 108172341813179, size = 6.5, anim = "quad" },
	bluescale = { asset = 125917193136983, size = 8, anim = "serpent" },
	rockbear = { asset = 139436529541504, size = 9, anim = "quad" },
	emberbird = { asset = 107319776790840, size = 8, anim = "bird", fly = true },
	sandstinger = { asset = 110919573822521, size = 8, anim = "crawler" },
	stonegeneral = { asset = 99975372220787, size = 11, anim = "biped" },
	silverfox = { asset = 77529898167579, size = 7, anim = "quad" },
}
for _, mob in Mobs.list do
	local mesh = MESH[mob.id]
	if mesh then
		mob.anim = mesh.anim
		mob.fly = mesh.fly
		if mesh.asset > 0 then
			mob.asset = mesh.asset
			mob.assetSize = mesh.size
		end
	end
end

return Mobs
