scoreboard players set #final aooni.var 1
execute store result score #n aooni.var if entity @a[tag=aooni.player,tag=!aooni.oni_p]
scoreboard players set #k aooni.var 20
scoreboard players operation #hp aooni.var = #n aooni.var
scoreboard players operation #hp aooni.var *= #k aooni.var
scoreboard players add #hp aooni.var 60
execute store result storage aooni:v hp int 1 run scoreboard players get #hp aooni.var
scoreboard players set #k aooni.var 5
scoreboard players operation #half10 aooni.var = #hp aooni.var
scoreboard players operation #half10 aooni.var *= #k aooni.var
execute as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] at @s run function aooni:oni/giant with storage aooni:v
execute as @e[type=minecraft:zombie,tag=aooni.dummy] at @s run function aooni:test/dummy_giant with storage aooni:v
execute store result bossbar aooni:boss max run scoreboard players get #hp aooni.var
execute store result bossbar aooni:boss value run scoreboard players get #hp aooni.var
bossbar set aooni:boss name {"text":"","extra":[{"text":"거대 아오오니 ","color":"dark_red","bold":true},{"selector":"@a[tag=aooni.oni_p]","color":"red"}]}
execute if score #test aooni.var matches 1 run bossbar set aooni:boss name {"text":"거대 아오오니 (연습용)","color":"dark_red","bold":true}
bossbar set aooni:boss players @a[tag=aooni.player]
bossbar set aooni:boss visible true
title @a[tag=aooni.player] times 5 60 20
title @a[tag=aooni.player] title {"text":"마검이 뽑혔다!","color":"gold","bold":true}
title @a[tag=aooni.player,tag=!aooni.oni_p] subtitle {"text":"거대해진 아오오니를 족쳐라!","color":"yellow"}
title @a[tag=aooni.oni_p] subtitle {"text":"몸이 거대해졌다 — 마검을 든 자부터 잡아라!","color":"red"}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.wither.spawn master @s ~ ~ ~ 0.5 0.7
function aooni:game/progress
