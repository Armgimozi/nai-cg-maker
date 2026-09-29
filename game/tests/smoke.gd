extends Node
## 헤드리스 스모크 테스트: 자동로드·데이터·뽑기 로직·각 씬 인스턴스화를 검사한다.
##   godot --headless --path game tests/smoke.tscn
## 실패하면 "SMOKE FAIL" 을 출력하고 종료 코드 1.

var _fails: PackedStringArray = []


func _check(cond: bool, msg: String) -> void:
	if not cond:
		_fails.append(msg)
		push_error("SMOKE FAIL: " + msg)


func _ready() -> void:
	# 저장 파일이 있으면 초기 상태로(테스트 격리)
	GameState.reset_game()

	# 데이터
	_check(CharacterDB.characters.size() >= 20, "캐릭터 수 >= 20")
	for r in [1, 2, 3, 4, 5]:
		_check(CharacterDB.by_rarity.has(r), "등급 %d 캐릭터 존재" % r)
	for ch in CharacterDB.characters:
		var tex := CharacterDB.get_sprite(ch["id"])
		_check(tex != null and tex.get_width() > 0, "스프라이트 로드: %s" % ch["id"])
		_check(str(ch.get("name", "")) != "", "이름 존재: %s" % ch["id"])

	# 확률 합 100
	var total := 0.0
	for r in Gacha.RATES:
		total += float(Gacha.RATES[r])
	_check(absf(total - 100.0) < 0.001, "확률 합 100 (=%f)" % total)

	# 뽑기: 젬 차감·결과 수·저장
	var before := GameState.gems
	var res := Gacha.pull(10)
	_check(res.size() == 10, "10연차 결과 10개 (=%d)" % res.size())
	_check(GameState.gems == before - Gacha.COST_TEN, "10연차 젬 차감")
	var has_sr := false
	for x in res:
		if int(x["char"]["rarity"]) >= Gacha.TEN_PULL_MIN_RARITY:
			has_sr = true
	_check(has_sr, "10연차 SR 이상 보장")
	_check(GameState.owned_count() > 0, "보유 캐릭터 생김")
	_check(FileAccess.file_exists(GameState.SAVE_PATH), "저장 파일 생성")

	# 젬 부족 → 빈 결과
	GameState.gems = 0
	_check(Gacha.pull(1).is_empty(), "젬 부족 시 빈 결과")

	# 천장: 49회 연속 저등급이었다고 가정하면 다음은 SSR 이상
	GameState.gems = 100000
	GameState.pity = Gacha.PITY_LIMIT - 1
	var p := Gacha.pull_one()
	_check(int(p["char"]["rarity"]) >= 4, "천장 SSR 이상 확정")
	_check(GameState.pity == 0, "천장 후 pity 리셋")

	# 중복 → 조각
	var first: Dictionary = CharacterDB.characters[0]
	GameState.add_character(first["id"], int(first["rarity"]))
	var s0 := GameState.shards
	GameState.add_character(first["id"], int(first["rarity"]))
	_check(GameState.shards > s0, "중복 획득 시 조각 지급")
	_check(GameState.exchange_shards(GameState.shards), "조각 → 젬 교환")

	# 저장/불러오기 왕복
	var g := GameState.gems
	var oc := GameState.owned_count()
	GameState.save_game()
	GameState.gems = -1
	GameState.owned = {}
	GameState.load_game()
	_check(GameState.gems == g and GameState.owned_count() == oc, "저장/불러오기 왕복")

	# 일일 보상 1회만
	GameState.last_daily = ""
	_check(GameState.claim_daily(), "일일 보상 1회 수령")
	_check(not GameState.claim_daily(), "일일 보상 중복 불가")

	# 씬 인스턴스화(스크립트 _ready 까지 실행)
	GameState.selected_id = first["id"]
	for path in ["res://scenes/main_menu.tscn", "res://scenes/gacha.tscn",
			"res://scenes/collection.tscn", "res://scenes/character_detail.tscn"]:
		var packed: PackedScene = load(path)
		_check(packed != null, "씬 로드: " + path)
		if packed:
			var inst := packed.instantiate()
			add_child(inst)
			await get_tree().process_frame
			inst.queue_free()
	await get_tree().process_frame

	GameState.reset_game()
	if _fails.is_empty():
		print("SMOKE OK")
		get_tree().quit(0)
	else:
		print("SMOKE FAIL (%d): %s" % [_fails.size(), "; ".join(_fails)])
		get_tree().quit(1)
