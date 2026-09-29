extends Control
## 뽑기 화면 — 1회/10회 뽑기, 결과 카드가 순서대로 나타나는 연출, 확률 고지.

const CARD := preload("res://scenes/ui/character_card.tscn")

var _busy := false


func _ready() -> void:
	GameState.gems_changed.connect(func(_v: int) -> void: _refresh())
	%BackBtn.pressed.connect(func() -> void: get_tree().change_scene_to_file("res://scenes/main_menu.tscn"))
	%SingleBtn.pressed.connect(func() -> void: _do_pull(1))
	%TenBtn.pressed.connect(func() -> void: _do_pull(10))
	%SingleBtn.text = "1회 뽑기 (%d젬)" % Gacha.COST_SINGLE
	%TenBtn.text = "10회 뽑기 (%d젬)" % Gacha.COST_TEN
	_refresh()


func _refresh() -> void:
	%Gems.text = "젬 %d" % GameState.gems
	%Rates.text = "확률: %s\nSSR 이상 확정까지 %d회 · 10연차는 SR 이상 1장 보장" % [
		Gacha.rates_text(), Gacha.PITY_LIMIT - GameState.pity]
	%SingleBtn.disabled = _busy or GameState.gems < Gacha.COST_SINGLE
	%TenBtn.disabled = _busy or GameState.gems < Gacha.COST_TEN


func _do_pull(n: int) -> void:
	if _busy:
		return
	var results := Gacha.pull(n)
	if results.is_empty():
		%Msg.text = "젬이 부족합니다."
		return
	_busy = true
	_refresh()
	for c in %Grid.get_children():
		c.queue_free()
	var best := 0
	var new_count := 0
	var tw := create_tween().set_parallel(true)
	for i in results.size():
		var res: Dictionary = results[i]
		var ch: Dictionary = res["char"]
		var r := int(ch["rarity"])
		best = maxi(best, r)
		if res["is_new"]:
			new_count += 1
		var card := CARD.instantiate()
		%Grid.add_child(card)
		card.setup(ch, GameState.count(ch["id"]), res["is_new"])
		card.selected.connect(_on_card)
		card.modulate = Color(1, 1, 1, 0)
		tw.tween_property(card, "modulate", Color.WHITE, 0.25).set_delay(i * 0.12)
		if r >= 4:
			# 고등급은 등급색으로 번쩍였다가 돌아온다
			var flash := CharacterDB.rarity_color(r)
			tw.tween_property(card, "modulate", flash, 0.15).set_delay(i * 0.12 + 0.25)
			tw.tween_property(card, "modulate", Color.WHITE, 0.4).set_delay(i * 0.12 + 0.4)
	await tw.finished
	_busy = false
	var summary := "최고 등급 %s" % CharacterDB.rarity_name(best)
	if new_count > 0:
		summary += " · 신규 %d명!" % new_count
	%Msg.text = summary
	_refresh()


func _on_card(id: String) -> void:
	GameState.selected_id = id
	GameState.return_scene = "res://scenes/gacha.tscn"
	get_tree().change_scene_to_file("res://scenes/character_detail.tscn")
