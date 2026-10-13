# 피해를 줄 수 있는 건 마검을 든 사람뿐 → 최후의 일격은 마검 소지자
execute if entity @a[tag=aooni.armed] run tag @a remove aooni.lasthit
tag @a[tag=aooni.armed] add aooni.lasthit
function aooni:game/victory
