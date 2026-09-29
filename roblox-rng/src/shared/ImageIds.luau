--!strict
-- 그림 에셋 Id 표 (이름 -> "rbxassetid://<숫자>").
-- tools/upload_images.py 가 art/png/*.png 를 올린 뒤 이 파일의 빈 문자열을 채웁니다(손으로 넣어도 됨).
-- 빈 문자열이면 코드로 그린 기본 모양을 씁니다: 아이콘은 3D 미니 모형(Icons.luau), 스킨은 Frame + UICorner + UIStroke.
-- 한 줄에 하나씩 `이름 = "..."`, 형식을 유지해 주세요(도구가 이 줄을 찾아 바꿉니다).

local ImageIds: { [string]: string } = {
	-- 아이콘 (정사각형, 투명 배경)
	coin = "rbxassetid://92735606856597",
	globe = "rbxassetid://120346838245612",
	passport = "rbxassetid://87589831804856",
	album = "rbxassetid://119409643400403",
	hammer = "rbxassetid://140249077514315",
	park = "rbxassetid://107569372693886",
	plaza = "rbxassetid://72077343461516",
	dice = "rbxassetid://134549464858003",
	clover = "rbxassetid://114594000848516",
	star = "rbxassetid://81395542088665",
	star_empty = "rbxassetid://140275366426879",
	news = "rbxassetid://106558405094559",
	lock = "rbxassetid://88755806602020",
	auto = "rbxassetid://74061414150372",
	close = "rbxassetid://93895182737016",
	check = "rbxassetid://72676469391845",
	arrow_up = "rbxassetid://115996354535723",
	stamp_home = "rbxassetid://126314844348937",
	stamp_europe = "rbxassetid://128003629180266",
	stamp_asia = "rbxassetid://85954883217288",
	stamp_africa = "rbxassetid://85590245416189",
	stamp_americas = "rbxassetid://77122062692820",
	stamp_oceania = "rbxassetid://138424553067781",
	stamp_legend = "rbxassetid://93435199901514",
	-- (선택) 업그레이드 아이콘. 비어 있으면 3D 모형
	plane = "",
	ticket = "",

	-- 스킨 (256x256, 9-slice SliceCenter = 64,64,192,192, tag 은 캡슐용 46..210 — Ui.luau SKINS). 회색 바탕 그림을 ImageColor3 로 물들여 씀.
	-- sunburst 는 9-slice 없이 통째로 늘여 씀.
	button_face = "rbxassetid://114337261704107",
	button_shadow = "rbxassetid://131795792663906",
	panel_paper = "rbxassetid://135177337416974",
	pill = "rbxassetid://76337661510619",
	sunburst = "rbxassetid://103053283018731",
	tag = "rbxassetid://111522354097064",

	-- 리본 꼬리 (늘이지 않는 그림, 56:50). 회색 바탕 그림을 ImageColor3 로 물들여 씀. 비어 있으면 둥근 네모 Frame 꼬리 (Ui.ribbon)
	ribbon_tail_l = "",
	ribbon_tail_r = "",
}

return ImageIds
