# 아오오니는 투명(대신 파란 모형이 따라다님), 어둠을 꿰뚫어 보고, 블록을 전혀 만질 수 없다(문·버튼·옷장 불가)
effect give @s minecraft:invisibility infinite 0 true
effect give @s minecraft:saturation infinite 0 true
effect give @s minecraft:night_vision infinite 0 true
execute if score #diff aooni.var matches 2 run effect give @s minecraft:speed infinite 0 true
execute if score #diff aooni.var matches 3 run effect give @s minecraft:speed infinite 1 true
execute if entity @s[tag=aooni.enraged] run effect give @s minecraft:speed infinite 2 true
attribute @s minecraft:block_interaction_range base set 0
attribute @s minecraft:knockback_resistance base set 1
