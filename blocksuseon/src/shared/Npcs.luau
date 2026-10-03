-- 연국 마을 사람들: 생김새(HumanoidDescription), 자리와 동선, 대사.
--
-- 노인 셋은 천인기 "천순과 종심"에서 마지막 부탁을 하는 사람들이고(Tasks.luau 의 elder_*),
-- 마을 사람 넷은 마을을 오가며 말을 걸면 이곳 이야기를 들려준다.
-- 대사는 말을 건 사람에게만 말풍선으로 보인다.

export type Look = {
	bodyColor: { number }, -- RGB
	scales: { height: number, width: number, head: number, proportion: number, bodyType: number },
	assets: { number }, -- 카탈로그 아이템 id (옷, 머리, 수염, 모자 등)
	face: number?, -- 얼굴 데칼 id
}

export type Npc = {
	id: string,
	name: string,
	site: string?, -- 과업 자리 id (노인)
	position: Vector3,
	facing: number, -- 바라보는 방향(도, y축)
	seated: boolean?,
	route: { Vector3 }?, -- 오가는 길 (마을 사람)
	walkSpeed: number?,
	look: Look,
	lines: { string }, -- 평소 대사 (차례로)
	request: string?, -- 천순 부탁
	thanks: string?, -- 부탁을 들어준 뒤
}

local Npcs = {}

-- 생김새는 tools 로 고른 카탈로그 아이템이다. 아이템이 지워지거나 못 불러오면 맨몸으로라도 선다.
local SKIN = { 226, 196, 164 }
local SKIN_OLD = { 214, 182, 150 }
local ELDER_SCALES = { height = 0.95, width = 0.95, head = 1, proportion = 0, bodyType = 0 }
local ADULT_SCALES = { height = 1, width = 1, head = 1, proportion = 0, bodyType = 0 }
local CHILD_SCALES = { height = 0.8, width = 0.85, head = 1, proportion = 0, bodyType = 0 }

Npcs.list = {
	{
		id = "elder_1",
		name = "늙은 약초꾼",
		site = "elder_1",
		position = Vector3.new(-26, 0.5, 8),
		facing = 90,
		seated = true,
		look = { bodyColor = SKIN_OLD, scales = ELDER_SCALES, assets = {} },
		lines = {
			"숲 서쪽 고목 아래가 목 기운이 제일 짙다네. 영초도 거기서 잘 돋지.",
			"천년영지는 붉은빛이 아니라 금빛이 돈다네. 붉은 건 홍령삼이고, 그건 평생 한 번 볼까 말까지.",
			"영초는 캐자마자 먹지 말게. 모아 두면 제물로도 쓰고 축기단 재료도 된다네.",
			"젊을 땐 나도 영근이 있나 싶어 숲에서 밤을 새웠지. 아무것도 느끼지 못했어.",
		},
		request = "이보게, 영초 두 뿌리만 가져다주겠나. 마지막으로 그 향을 한 번 맡고 싶네.",
		thanks = "아, 이 향이야. 젊을 적 숲에서 길을 잃었을 때도 이 냄새를 따라 나왔지. 고맙네.",
	},
	{
		id = "elder_2",
		name = "늙은 대장장이",
		site = "elder_2",
		position = Vector3.new(42, 0, 14),
		facing = 200,
		seated = true,
		look = { bodyColor = SKIN_OLD, scales = ELDER_SCALES, assets = {} },
		lines = {
			"저 화덕 불은 사십 년 동안 한 번도 꺼진 적이 없네. 화 기운을 닦는 이들이 자주 와서 앉아 있지.",
			"수도자들이 쓰는 법기는 내 망치로는 못 벼려. 나는 호미랑 낫이나 두드리는 사람이야.",
			"천겁대 쇠기둥이 금 기운을 머금고 있다더군. 쇠를 오래 만진 나도 그건 모르겠네.",
			"손이 떨려서 이제 망치를 못 들어. 그래도 불 앞에 앉아 있으면 마음이 편해.",
		},
		request = "영초 두 뿌리만 구해다 주게. 약으로 쓰려는 게 아니야. 손에 쥐고 불을 보고 싶을 뿐이네.",
		thanks = "끝내 못 벼린 칼이 하나 있었지. 이제 아무래도 좋아. 고맙네, 젊은이.",
	},
	{
		id = "elder_3",
		name = "늙은 뱃사공",
		site = "elder_3",
		position = Vector3.new(-82, 0, 20),
		facing = 270,
		seated = true,
		look = { bodyColor = SKIN_OLD, scales = ELDER_SCALES, assets = {} },
		lines = {
			"다리가 놓이기 전엔 내가 이 개울을 건네주었지. 지금은 물소리나 듣고 있네.",
			"밤에 개울 바닥에 앉아 있으면 달이 물에 비치지. 수도자들이 그걸 보러 오더군.",
			"물은 낮은 데로만 흘러. 땅의 기운도 그렇다고, 젊은 수도자 하나가 그러더군.",
			"강 건너가 내 고향이야. 이 나이에 건너가 봐야 아는 얼굴도 없지.",
		},
		request = "영초 두 뿌리만 주겠나. 고향 강가에도 이 풀이 자랐거든.",
		thanks = "이걸 쥐니 강 건너 고향이 보이는 것 같네. 이제 좀 쉬어야겠어.",
	},
	{
		id = "gatherer",
		name = "약초 캐는 청년",
		position = Vector3.new(-122, 0, -20),
		facing = 0,
		route = {
			Vector3.new(-122, 0, -20),
			Vector3.new(-150, 0, -62),
			Vector3.new(-176, 0, -18),
			Vector3.new(-138, 0, 30),
		},
		walkSpeed = 7,
		look = { bodyColor = SKIN, scales = ADULT_SCALES, assets = {} },
		lines = {
			"영초는 숲 바닥에 아무렇게나 돋아. 빛나는 구슬 같은 게 보이면 그거야.",
			"영안을 쓰는 수도자는 벽 너머 영초까지 본다더라. 부럽지.",
			"아까 누가 붉게 빛나는 풀을 봤다고 난리였어. 홍령삼이면 대박인데.",
		},
	},
	{
		id = "basket",
		name = "바구니 든 아낙",
		position = Vector3.new(20, 0.5, -14),
		facing = 0,
		route = {
			Vector3.new(20, 0.5, -14),
			Vector3.new(16, 0.5, 18),
			Vector3.new(-16, 0.5, 16),
			Vector3.new(-18, 0.5, -12),
		},
		walkSpeed = 5,
		look = { bodyColor = SKIN, scales = ADULT_SCALES, assets = {} },
		lines = {
			"광장 가운데 웅덩이에 앉아 있는 사람들, 하루 종일 꼼짝도 안 해. 저게 운기조식이래.",
			"밤이 되면 하늘에서 별똥이 떨어진다고 수도자들이 우르르 몰려나가더라.",
			"연단로 근처는 지나가기만 해도 쓴 냄새가 나.",
		},
	},
	{
		id = "child",
		name = "마을 아이",
		position = Vector3.new(6, 0.5, 32),
		facing = 0,
		route = {
			Vector3.new(6, 0.5, 32),
			Vector3.new(-10, 0.5, 27),
			Vector3.new(-4, 0.5, 38),
		},
		walkSpeed = 10,
		look = { bodyColor = SKIN, scales = CHILD_SCALES, assets = {} },
		lines = {
			"나도 크면 수도자 될 거야! 영근이 있었으면 좋겠다.",
			"천겁대에 벼락 떨어지는 거 봤어? 엄청 커!",
			"할아버지들이 그러는데, 영산 꼭대기까지 올라가면 별이 손에 닿는대.",
		},
	},
	{
		id = "wanderer",
		name = "떠돌이 수도자",
		position = Vector3.new(70, 0, -58),
		facing = 140,
		route = {
			Vector3.new(70, 0, -58),
			Vector3.new(118, 0, -98),
		},
		walkSpeed = 6,
		look = { bodyColor = SKIN, scales = ADULT_SCALES, assets = {} },
		lines = {
			"축기기까지는 하늘이 조용하지. 원영기부터 금색 천겁이 내리니 각오해 두게.",
			"영산 꼭대기 상품 영맥은 금단을 맺은 몸이라야 버틴다네.",
			"칠성제의는 시운을 놓치면 다음 밤을 기다려야 하네. 제물은 미리 챙겨 두게.",
			"연기기 6성까지는 범인도 평생 노력하면 닿는다지. 그다음이 진짜 수선이야.",
		},
	},
} :: { Npc }

Npcs.byId = {} :: { [string]: Npc }
for _, npc in Npcs.list do
	Npcs.byId[npc.id] = npc
end

return Npcs
