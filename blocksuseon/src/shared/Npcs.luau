-- 연국 마을 사람들: 생김새(HumanoidDescription), 자리와 동선, 대사.
--
-- 노인 셋은 천인기 "천순과 종심"에서 마지막 부탁을 하는 사람들이고(Tasks.luau 의 elder_*),
-- 마을 사람 넷은 마을을 오가며 말을 걸면 이곳 이야기를 들려준다.
-- 대사는 말을 건 사람에게만 말풍선으로 보인다.

-- 생김새. 카탈로그 아이템 id 는 tools 조사로 고른 것이다 (모두 공개 아이템, 소유하지 않아도 불러온다).
-- rigid 는 HumanoidDescription 의 쉼표 목록 속성(Hat, Hair, Face, Back, Waist 등),
-- layered 는 SetAccessories 로 넣는 레이어드 옷이다.
export type Look = {
	color: { number }, -- 피부 RGB
	scales: { height: number, width: number, head: number, depth: number? },
	face: number?, -- 클래식 얼굴
	shirt: number?,
	pants: number?,
	rigid: { [string]: { number } }?,
	layered: { { id: number, type: string } }?,
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
	lines: { string }, -- 평소 대사 (차례로)
	request: string?, -- 천순 부탁
	thanks: string?, -- 부탁을 들어준 뒤
}

local Npcs = {}

-- 아이템이 지워지거나 못 불러오면 옷만, 그것도 안 되면 맨몸으로라도 선다 (server/Villagers.luau).
local LOOKS: { [string]: Look } = {
	-- 은빛 상투, 흰 수염, 녹색 깃의 흰 도포, 지팡이
	elder_1 = {
		color = { 222, 184, 150 },
		scales = { height = 0.92, width = 0.92, head = 1 },
		face = 7074764,
		pants = 5264002379,
		rigid = { Hair = { 16843588033 }, Face = { 137997589745063 }, Back = { 14175873043 } },
		layered = { { id = 12388431541, type = "DressSkirt" } },
	},
	-- 볕에 그을린 피부, 회색 상투에 흰 머리띠, 흰 저고리와 가죽 앞치마, 허리에 망치
	elder_2 = {
		color = { 176, 124, 92 },
		scales = { height = 0.94, width = 1, head = 1, depth = 1.05 },
		face = 20418658,
		shirt = 5270164430,
		pants = 5816206509,
		rigid = { Hair = { 16843582731 }, Hat = { 6700105307 }, Face = { 98037226875056 }, Waist = { 18621105258 } },
		layered = { { id = 9125090129, type = "Jacket" } },
	},
	-- 삿갓, 성긴 흰 머리, 회색 수염, 짙은 백성 옷, 등에 노
	elder_3 = {
		color = { 196, 146, 108 },
		scales = { height = 0.9, width = 0.9, head = 1 },
		face = 141728790,
		shirt = 5818354343,
		pants = 5816206509,
		rigid = { Hat = { 12314309839 }, Hair = { 7611004838 }, Face = { 82869888420791 }, Back = { 97265279395643 } },
	},
	-- 검은 상투에 갈색 머리띠, 옥색 저고리, 버섯 바구니
	gatherer = {
		color = { 214, 170, 130 },
		scales = { height = 1, width = 0.9, head = 1 },
		face = 144075659,
		shirt = 5233009344,
		pants = 5270166453,
		rigid = { Hair = { 16843559834 }, Hat = { 116337655881795 }, Back = { 84647655628431 } },
	},
	-- 쪽 찐 머리, 흰 저고리와 옥색 치마, 복숭아 바구니
	basket = {
		color = { 236, 200, 168 },
		scales = { height = 0.96, width = 0.85, head = 0.97 },
		face = 209994875,
		pants = 5506847073,
		rigid = { Hair = { 78065844539529 }, Back = { 125502393239229 } },
		layered = { { id = 106138648370585, type = "Jacket" } },
	},
	-- 댕기 머리, 빨간 한복, 탕후루
	child = {
		color = { 242, 206, 172 },
		scales = { height = 0.8, width = 0.85, head = 1.05 },
		face = 12145366,
		shirt = 5563698858,
		pants = 5563702959,
		rigid = { Hair = { 113975653490545 }, Face = { 6377338554 } },
	},
	-- 너울 달린 죽립, 긴 흑발, 흰 도포, 허리에 검
	wanderer = {
		color = { 240, 214, 190 },
		scales = { height = 1.03, width = 0.9, head = 0.97 },
		face = 31117267,
		pants = 5666304603,
		rigid = { Hat = { 16154051877 }, Hair = { 10945619882 }, Waist = { 10070649892 } },
		layered = { { id = 12388422808, type = "DressSkirt" } },
	},
}
Npcs.LOOKS = LOOKS

Npcs.list = {
	{
		id = "elder_1",
		name = "늙은 약초꾼",
		site = "elder_1",
		position = Vector3.new(-26, 0.5, 8),
		facing = 90,
		seated = true,
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
		lines = {
			"저 화덕 불은 사십 년 동안 한 번도 꺼진 적이 없네. 화 기운을 닦는 이들은 동쪽 천색성 용암 화로로 가더군.",
			"수도자들이 쓰는 법기는 내 망치로는 못 벼려. 나는 호미랑 낫이나 두드리는 사람이야.",
			"쇄천봉 기슭 금맥굴 쇠가 금 기운을 머금고 있다더군. 쇠를 오래 만진 나도 그건 모르겠네.",
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
		lines = {
			"다리가 놓이기 전엔 내가 이 강을 건네주었지. 지금은 물소리나 듣고 있네.",
			"남쪽 용소에 밤에 앉아 있으면 달이 물에 비치지. 수도자들이 그걸 보러 오더군.",
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
		lines = {
			"나도 크면 수도자 될 거야! 영근이 있었으면 좋겠다.",
			"동쪽 사막 답천대에 벼락 떨어지는 거 봤어? 엄청 커!",
			"할아버지들이 그러는데, 쇄천봉 꼭대기까지 올라가면 별이 손에 닿는대.",
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
		lines = {
			"축기기까지는 하늘이 조용하지. 원영기부터 금색 천겁이 내리니 각오해 두게.",
			"쇄천봉 꼭대기 상품 영맥이 짙고, 사막 위에 뜬 등선향 극품 영맥은 그보다 더하다네. 누구든 쓸 수 있지.",
			"칠성제의는 시운을 놓치면 다음 밤을 기다려야 하네. 제물은 미리 챙겨 두게.",
			"연기기 6성까지는 범인도 평생 노력하면 닿는다지. 그다음이 진짜 수선이야.",
		},
	},
} :: { Npc }

Npcs.byId = {} :: { [string]: Npc }
for _, npc in Npcs.list do
	Npcs.byId[npc.id] = npc
end

function Npcs.look(id: string): Look?
	return LOOKS[id]
end

return Npcs
