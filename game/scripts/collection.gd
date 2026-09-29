extends Control
## 도감 — 전체 캐릭터를 등급순으로 나열. 미보유는 실루엣.

const CARD := preload("res://scenes/ui/character_card.tscn")


func _ready() -> void:
	%BackBtn.pressed.connect(func() -> void: get_tree().change_scene_to_file("res://scenes/main_menu.tscn"))
	_build()


func _build() -> void:
	var total := CharacterDB.characters.size()
	%Header.text = "도감 %d / %d" % [GameState.owned_count(), total]
	var list: Array = CharacterDB.characters.duplicate()
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ra := int(a["rarity"])
		var rb := int(b["rarity"])
		if ra != rb:
			return ra > rb
		return str(a["id"]) < str(b["id"])
	)
	for ch in list:
		var card := CARD.instantiate()
		%Grid.add_child(card)
		card.setup(ch, GameState.count(ch["id"]))
		card.selected.connect(_on_card)


func _on_card(id: String) -> void:
	GameState.selected_id = id
	GameState.return_scene = "res://scenes/collection.tscn"
	get_tree().change_scene_to_file("res://scenes/character_detail.tscn")
