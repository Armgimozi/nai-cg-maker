extends Control
## 메인 메뉴 — 재화 표시, 일일 보상, 조각 교환, 뽑기/도감 이동, 초기화.


func _ready() -> void:
	GameState.gems_changed.connect(func(_v: int) -> void: _refresh())
	GameState.shards_changed.connect(func(_v: int) -> void: _refresh())
	GameState.collection_changed.connect(_refresh)
	%GachaBtn.pressed.connect(func() -> void: _go("res://scenes/gacha.tscn"))
	%CollectionBtn.pressed.connect(func() -> void: _go("res://scenes/collection.tscn"))
	%DailyBtn.pressed.connect(_on_daily)
	%ExchangeBtn.pressed.connect(_on_exchange)
	%ResetBtn.pressed.connect(func() -> void: %ResetDialog.popup_centered())
	%ResetDialog.confirmed.connect(_on_reset)
	_refresh()


func _refresh() -> void:
	%Gems.text = "젬 %d" % GameState.gems
	%Shards.text = "조각 %d" % GameState.shards
	%Progress.text = "도감 %d / %d" % [GameState.owned_count(), CharacterDB.characters.size()]
	var daily_ok := GameState.can_claim_daily()
	%DailyBtn.disabled = not daily_ok
	%DailyBtn.text = ("일일 보상 +%d젬" % GameState.DAILY_GEMS) if daily_ok else "일일 보상 받음"
	%ExchangeBtn.disabled = GameState.shards <= 0
	%ExchangeBtn.text = "조각 → 젬 교환 (%d)" % GameState.shards


func _on_daily() -> void:
	if GameState.claim_daily():
		%Msg.text = "일일 보상으로 젬 %d개를 받았습니다!" % GameState.DAILY_GEMS
	_refresh()


func _on_exchange() -> void:
	var n := GameState.shards
	if GameState.exchange_shards(n):
		%Msg.text = "조각 %d개를 젬으로 바꿨습니다." % n
	_refresh()


func _on_reset() -> void:
	GameState.reset_game()
	%Msg.text = "데이터를 초기화했습니다."
	_refresh()


func _go(path: String) -> void:
	get_tree().change_scene_to_file(path)
