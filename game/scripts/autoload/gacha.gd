extends Node
## 뽑기 로직 — 등급 확률, 천장(SSR 이상 확정), 10연차 SR 이상 보장.
## 확률은 플레이스토어 정책(확률형 아이템 고지)에 맞춰 화면에도 그대로 표시한다.

const COST_SINGLE := 100
const COST_TEN := 900
const RATES := {5: 1.0, 4: 5.0, 3: 14.0, 2: 30.0, 1: 50.0}  # 퍼센트, 합 100
const PITY_LIMIT := 50           # 50회 안에 SSR 이상 없으면 50회째 확정
const TEN_PULL_MIN_RARITY := 3   # 10연차엔 SR 이상 1장 보장

var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_rng.randomize()


func rates_text() -> String:
	var parts: PackedStringArray = []
	for r in [5, 4, 3, 2, 1]:
		parts.append("%s %.1f%%" % [CharacterDB.rarity_name(r), RATES[r]])
	return " · ".join(parts)


func roll_rarity() -> int:
	var x := _rng.randf() * 100.0
	var acc := 0.0
	for r in [5, 4, 3, 2, 1]:
		acc += float(RATES[r])
		if x < acc:
			return r
	return 1


## 해당 등급 풀에서 무작위 1명. 풀이 비었으면 한 등급씩 내려간다.
func _pick(rarity: int) -> Dictionary:
	var r := rarity
	while r >= 1:
		var pool: Array = CharacterDB.by_rarity.get(r, [])
		if not pool.is_empty():
			return pool[_rng.randi_range(0, pool.size() - 1)]
		r -= 1
	return {}


## 1회 뽑기(젬 차감 없음 — pull() 이 처리). {"char": Dictionary, "is_new": bool}
func pull_one(min_rarity: int = 1) -> Dictionary:
	var r := maxi(roll_rarity(), min_rarity)
	if GameState.pity >= PITY_LIMIT - 1 and r < 4:
		r = 4
	if r >= 4:
		GameState.pity = 0
	else:
		GameState.pity += 1
	GameState.total_pulls += 1
	var ch := _pick(r)
	if ch.is_empty():
		return {}
	var is_new := GameState.add_character(ch["id"], int(ch["rarity"]))
	return {"char": ch, "is_new": is_new}


func cost_for(count: int) -> int:
	return COST_TEN if count >= 10 else COST_SINGLE * count


## n회 뽑기. 젬이 모자라면 빈 배열.
func pull(count: int) -> Array:
	if not GameState.spend_gems(cost_for(count)):
		return []
	var results: Array = []
	var got_sr := false
	for i in count:
		var min_r := 1
		if count >= 10 and i == count - 1 and not got_sr:
			min_r = TEN_PULL_MIN_RARITY
		var res := pull_one(min_r)
		if res.is_empty():
			continue
		if int(res["char"]["rarity"]) >= TEN_PULL_MIN_RARITY:
			got_sr = true
		results.append(res)
	GameState.save_game()
	return results
