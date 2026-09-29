extends Button
## 도감·뽑기 결과에 쓰는 캐릭터 카드. 도트 스프라이트 + 이름 + 등급.
## 미보유는 실루엣(검정)으로, 신규 획득은 NEW 뱃지로 표시한다.

signal selected(id: String)

var char_id := ""


func setup(ch: Dictionary, count: int, is_new: bool = false) -> void:
	char_id = str(ch.get("id", ""))
	var r := int(ch.get("rarity", 1))
	var owned := count > 0
	%Sprite.texture = CharacterDB.get_sprite(char_id)
	%Sprite.modulate = Color.WHITE if owned else Color(0, 0, 0, 0.7)
	%Name.text = str(ch.get("name", char_id)) if owned else "???"
	%Rarity.text = CharacterDB.stars(r)
	%Rarity.add_theme_color_override("font_color", CharacterDB.rarity_color(r))
	%Badge.visible = is_new
	%Count.text = ("x%d" % count) if count > 1 else ""
	_apply_style(r, owned)


func _apply_style(r: int, owned: bool) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color("#1e1828")
	sb.border_color = CharacterDB.rarity_color(r) if owned else Color("#3a3346")
	sb.set_border_width_all(3)
	sb.set_corner_radius_all(10)
	sb.set_content_margin_all(0)
	var hover := sb.duplicate() as StyleBoxFlat
	hover.bg_color = Color("#2a2238")
	add_theme_stylebox_override("normal", sb)
	add_theme_stylebox_override("hover", hover)
	add_theme_stylebox_override("pressed", hover)
	add_theme_stylebox_override("focus", StyleBoxEmpty.new())


func _pressed() -> void:
	selected.emit(char_id)
