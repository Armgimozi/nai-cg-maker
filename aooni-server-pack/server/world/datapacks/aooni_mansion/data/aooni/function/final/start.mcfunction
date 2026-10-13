execute unless score #state aooni.var matches 1 run return 0
execute as @e[type=minecraft:zombie,tag=aooni.oni,tag=!aooni.boss] at @s run function aooni:oni/vanish
execute store result score #n aooni.var if entity @a[tag=aooni.player]
scoreboard players set #k aooni.var 50
scoreboard players operation #bhp aooni.var = #n aooni.var
scoreboard players operation #bhp aooni.var *= #k aooni.var
scoreboard players add #bhp aooni.var 200
execute if score #bhp aooni.var matches 801.. run scoreboard players set #bhp aooni.var 800
scoreboard players operation #bmax aooni.var = #bhp aooni.var
scoreboard players set #k aooni.var 5
scoreboard players operation #half10 aooni.var = #bmax aooni.var
scoreboard players operation #half10 aooni.var *= #k aooni.var
tag @e[type=minecraft:marker,tag=aooni.cand] remove aooni.cand
execute as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s if entity @a[tag=aooni.alive,distance=..30] unless entity @a[tag=aooni.alive,distance=..12] run tag @s add aooni.cand
execute unless entity @e[type=minecraft:marker,tag=aooni.cand] as @e[type=minecraft:marker,tag=aooni.spawn,tag=aooni.on] at @s unless entity @a[tag=aooni.alive,distance=..6] run tag @s add aooni.cand
execute at @e[type=minecraft:marker,tag=aooni.cand,sort=random,limit=1] run function aooni:boss/spawn
execute unless entity @e[type=minecraft:zombie,tag=aooni.boss] positioned 23.5 -60 14.5 run function aooni:boss/spawn
execute store result bossbar aooni:boss max run scoreboard players get #bmax aooni.var
execute store result bossbar aooni:boss value run scoreboard players get #bmax aooni.var
bossbar set aooni:boss players @a[tag=aooni.player]
bossbar set aooni:boss visible true
scoreboard players set #boss_up aooni.var 1
title @a[tag=aooni.player] times 5 60 20
title @a[tag=aooni.player] title {"text":"거대 아오오니","color":"dark_red","bold":true}
title @a[tag=aooni.player] subtitle {"text":"무기로 족쳐라!","color":"gold"}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.wither.spawn master @s ~ ~ ~ 0.5 0.7
function aooni:game/progress
