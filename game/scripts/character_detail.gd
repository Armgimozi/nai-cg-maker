extends Control
## 캐릭터 상세 — NAI 일러스트(있으면) + 도트 스프라이트 + 이름·등급·설명·보유 수.
## 미보유 캐릭터는 실루엣과 ??? 로만 보인다.


func _ready() -> void:
	%BackBtn.pressed.connect(func() -> void: get_tree().change_scene_to_file(GameState.return_scene))
	var ch := CharacterDB.get_char(GameState.selected_id)
	if ch.is_empty():
		%Name.text = "캐릭터를 찾을 수 없습니다"
		return
	var id := str(ch["id"])
	var r := int(ch.get("rarity", 1))
	var owned := GameState.owns(id)
	var illust := CharacterDB.get_illust(id)

	%Sprite.texture = CharacterDB.get_sprite(id)
	%Illust.texture = illust
	%Illust.visible = illust != null
	%NoIllust.visible = illust == null
	# 일러스트는 부드럽게(선형), 도트는 또렷하게(최근접)
	%Illust.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	%Sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

	var shade := Color.WHITE if owned else Color(0, 0, 0, 0.85)
	%Sprite.modulate = shade
	%Illust.modulate = shade

	%Name.text = str(ch.get("name", id)) if owned else "???"
	%Title.text = str(ch.get("title", "")) if owned else ""
	%Rarity.text = "%s  %s" % [CharacterDB.stars(r), CharacterDB.rarity_name(r)]
	%Rarity.add_theme_color_override("font_color", CharacterDB.rarity_color(r))
	%Desc.text = str(ch.get("description", "")) if owned else "아직 만나지 못한 캐릭터입니다."
	%Count.text = ("보유 x%d" % GameState.count(id)) if owned else "미보유"
