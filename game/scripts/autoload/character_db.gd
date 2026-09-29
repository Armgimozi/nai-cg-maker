extends Node
## 캐릭터 데이터베이스.
## data/characters.json 을 읽어 메모리에 올리고, 도트 스프라이트·NAI 일러스트를
## 경로 규칙(assets/characters/<id>.png · assets/illust/<id>.png)으로 찾아준다.

const DATA_PATH := "res://data/characters.json"
const SPRITE_DIR := "res://assets/characters/"   # 도트 스프라이트(직접 제작)
const ILLUST_DIR := "res://assets/illust/"       # NAI 일러스트(tools/gen_characters.py)

const RARITY_NAMES := {1: "N", 2: "R", 3: "SR", 4: "SSR", 5: "UR"}
const RARITY_COLORS := {
	1: Color("#9aa0a6"),
	2: Color("#4fc3f7"),
	3: Color("#b98bff"),
	4: Color("#ffd54f"),
	5: Color("#ff7a93"),
}

var characters: Array = []       # Array[Dictionary] — JSON 순서 그대로
var by_id: Dictionary = {}       # id -> Dictionary
var by_rarity: Dictionary = {}   # rarity(int) -> Array[Dictionary]
var _tex_cache: Dictionary = {}


func _ready() -> void:
	_load()


func _load() -> void:
	var f := FileAccess.open(DATA_PATH, FileAccess.READ)
	if f == null:
		push_error("characters.json 을 열 수 없습니다: %s" % DATA_PATH)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("characters"):
		push_error("characters.json 형식 오류: 최상위에 characters 배열이 필요합니다")
		return
	characters = parsed["characters"]
	for ch in characters:
		by_id[ch["id"]] = ch
		var r := int(ch.get("rarity", 1))
		if not by_rarity.has(r):
			by_rarity[r] = []
		by_rarity[r].append(ch)


func get_char(id: String) -> Dictionary:
	return by_id.get(id, {})


func rarity_name(r: int) -> String:
	return RARITY_NAMES.get(r, "?")


func rarity_color(r: int) -> Color:
	return RARITY_COLORS.get(r, Color.WHITE)


func stars(r: int) -> String:
	return "★".repeat(r)


## 도트 스프라이트. 없으면 등급색 반투명 사각형으로 대체한다.
func get_sprite(id: String) -> Texture2D:
	var key := "s:" + id
	if _tex_cache.has(key):
		return _tex_cache[key]
	var tex := _load_tex(SPRITE_DIR + id + ".png")
	if tex == null:
		tex = _fallback_texture(id)
	_tex_cache[key] = tex
	return tex


## NAI 일러스트. 아직 생성 안 했으면 null.
func get_illust(id: String) -> Texture2D:
	var key := "i:" + id
	if _tex_cache.has(key):
		return _tex_cache[key]
	var tex := _load_tex(ILLUST_DIR + id + ".png")
	if tex == null:
		tex = _load_tex(ILLUST_DIR + id + ".webp")
	_tex_cache[key] = tex
	return tex


func has_illust(id: String) -> bool:
	return get_illust(id) != null


func _load_tex(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		return load(path) as Texture2D
	return null


func _fallback_texture(id: String) -> Texture2D:
	var img := Image.create(16, 24, false, Image.FORMAT_RGBA8)
	var c := rarity_color(int(get_char(id).get("rarity", 1)))
	img.fill(Color(c.r, c.g, c.b, 0.35))
	return ImageTexture.create_from_image(img)
