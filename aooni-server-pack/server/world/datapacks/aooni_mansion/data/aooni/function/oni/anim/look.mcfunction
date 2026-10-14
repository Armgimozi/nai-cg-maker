# 아오오니가 위아래를 보면 고개도 따라 든다/숙인다(5단계, 바뀔 때만)
execute if entity @s[x_rotation=..-22] run scoreboard players set #hb aooni.var -2
execute if entity @s[x_rotation=-22..-7] run scoreboard players set #hb aooni.var -1
execute if entity @s[x_rotation=-7..7] run scoreboard players set #hb aooni.var 0
execute if entity @s[x_rotation=7..22] run scoreboard players set #hb aooni.var 1
execute if entity @s[x_rotation=22..] run scoreboard players set #hb aooni.var 2
execute if score #hb aooni.var = #hbl aooni.var run return 0
scoreboard players operation #hbl aooni.var = #hb aooni.var
execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/head_big
function aooni:oni/anim/head
