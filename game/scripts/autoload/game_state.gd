extends Node
## 플레이어 상태(젬·조각·보유 캐릭터·천장)와 저장/불러오기.
## 저장 파일: user://save.json (Android 에서는 앱 내부 저장소).

signal gems_changed(gems: int)
signal shards_changed(shards: int)
signal collection_changed()

const SAVE_PATH := "user://save.json"
const START_GEMS := 1500
const DAILY_GEMS := 300
const IDLE_GEMS_PER_MIN := 10   # 앱을 켜 두거나 꺼 둔 동안 분당 지급
const IDLE_CAP := 600           # 오프라인 누적 상한
const DUP_SHARDS := {1: 5, 2: 10, 3: 30, 4: 100, 5: 300}  # 중복 시 조각

var gems: int = START_GEMS
var shards: int = 0
var owned: Dictionary = {}     # id -> 보유 수
var pity: int = 0              # SSR 이상 없이 뽑은 횟수
var total_pulls: int = 0
var last_daily: String = ""    # YYYY-MM-DD
var last_seen: int = 0         # unix time
var selected_id: String = ""   # 도감/뽑기 → 상세 화면 전달용
var return_scene: String = "res://scenes/collection.tscn"  # 상세 화면 '뒤로' 목적지


func _ready() -> void:
	load_game()
	_grant_idle()
	var t := Timer.new()
	t.wait_time = 60.0
	t.autostart = true
	t.timeout.connect(_on_minute)
	add_child(t)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_APPLICATION_PAUSED \
			or what == NOTIFICATION_WM_GO_BACK_REQUEST:
		save_game()


func _on_minute() -> void:
	add_gems(IDLE_GEMS_PER_MIN)
	save_game()


func _grant_idle() -> void:
	var now := int(Time.get_unix_time_from_system())
	if last_seen > 0 and now > last_seen:
		var mins := (now - last_seen) / 60
		var earned := mini(mins * IDLE_GEMS_PER_MIN, IDLE_CAP)
		if earned > 0:
			add_gems(earned)
	last_seen = now


func today() -> String:
	return Time.get_date_string_from_system()


func can_claim_daily() -> bool:
	return last_daily != today()


func claim_daily() -> bool:
	if not can_claim_daily():
		return false
	last_daily = today()
	add_gems(DAILY_GEMS)
	save_game()
	return true


func add_gems(n: int) -> void:
	gems += n
	gems_changed.emit(gems)


func spend_gems(n: int) -> bool:
	if gems < n:
		return false
	gems -= n
	gems_changed.emit(gems)
	return true


func add_shards(n: int) -> void:
	shards += n
	shards_changed.emit(shards)


## 조각 → 젬 1:1 교환. 성공 여부 반환.
func exchange_shards(n: int) -> bool:
	if n <= 0 or shards < n:
		return false
	shards -= n
	shards_changed.emit(shards)
	add_gems(n)
	save_game()
	return true


func owns(id: String) -> bool:
	return owned.has(id)


func count(id: String) -> int:
	return int(owned.get(id, 0))


func owned_count() -> int:
	return owned.size()


## 캐릭터 획득. 반환: 신규 여부. 중복이면 등급별 조각 지급.
func add_character(id: String, rarity: int) -> bool:
	var is_new := not owned.has(id)
	owned[id] = count(id) + 1
	if not is_new:
		add_shards(int(DUP_SHARDS.get(rarity, 5)))
	collection_changed.emit()
	return is_new


func save_game() -> void:
	last_seen = int(Time.get_unix_time_from_system())
	var data := {
		"version": 1,
		"gems": gems,
		"shards": shards,
		"owned": owned,
		"pity": pity,
		"total_pulls": total_pulls,
		"last_daily": last_daily,
		"last_seen": last_seen,
	}
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		push_error("저장 실패: %s" % FileAccess.get_open_error())
		return
	f.store_string(JSON.stringify(data, "\t"))


func load_game() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		return
	gems = int(data.get("gems", START_GEMS))
	shards = int(data.get("shards", 0))
	pity = int(data.get("pity", 0))
	total_pulls = int(data.get("total_pulls", 0))
	last_daily = str(data.get("last_daily", ""))
	last_seen = int(data.get("last_seen", 0))
	owned = {}
	var raw_owned = data.get("owned", {})
	if typeof(raw_owned) == TYPE_DICTIONARY:
		for k in raw_owned:
			owned[str(k)] = int(raw_owned[k])


func reset_game() -> void:
	gems = START_GEMS
	shards = 0
	owned = {}
	pity = 0
	total_pulls = 0
	last_daily = ""
	last_seen = int(Time.get_unix_time_from_system())
	save_game()
	gems_changed.emit(gems)
	shards_changed.emit(shards)
	collection_changed.emit()
