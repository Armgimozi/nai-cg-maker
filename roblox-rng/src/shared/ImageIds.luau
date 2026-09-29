--!strict
-- 그림 에셋 Id 표 (이름 -> "rbxassetid://<숫자>").
-- tools/upload_images.py 가 art/png/*.png 를 올린 뒤 이 파일의 빈 문자열을 채웁니다(손으로 넣어도 됨).
-- 빈 문자열이면 코드로 그린 기본 모양을 씁니다: 아이콘은 3D 미니 모형(Icons.luau), 스킨은 Frame + UICorner + UIStroke.
-- 한 줄에 하나씩 `이름 = "..."`, 형식을 유지해 주세요(도구가 이 줄을 찾아 바꿉니다).

local ImageIds: { [string]: string } = {
	-- 아이콘 (정사각형, 투명 배경)
	coin = "",
	globe = "",
	passport = "",
	album = "",
	hammer = "",
	park = "",
	plaza = "",
	dice = "",
	clover = "",
	star = "",
	star_empty = "",
	news = "",
	lock = "",
	auto = "",
	close = "",
	check = "",
	arrow_up = "",
	stamp_home = "",
	stamp_europe = "",
	stamp_asia = "",
	stamp_africa = "",
	stamp_americas = "",
	stamp_oceania = "",
	stamp_legend = "",
	-- (선택) 업그레이드 아이콘. 비어 있으면 3D 모형
	plane = "",
	ticket = "",

	-- 스킨 (256x256, 9-slice SliceCenter = 64,64,192,192, tag 은 캡슐용 46..210 — Ui.luau SKINS). 회색 바탕 그림을 ImageColor3 로 물들여 씀.
	-- sunburst 는 9-slice 없이 통째로 늘여 씀.
	button_face = "",
	button_shadow = "",
	panel_paper = "",
	pill = "",
	ribbon = "",
	sunburst = "",
	tag = "",
}

return ImageIds
