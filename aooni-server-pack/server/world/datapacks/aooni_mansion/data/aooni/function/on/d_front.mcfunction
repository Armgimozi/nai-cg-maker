execute if score #front aooni.var matches 1 run return run tellraw @s {"text":"현관문은 열려 있다. 어서 정원으로!","color":"gold"}
execute if score #k_front aooni.var matches 0 run return run function aooni:msg/locked_front
fill 33 -60 36 33 -59 36 minecraft:air
setblock 33 -60 36 minecraft:iron_door[half=lower,facing=north,hinge=left,open=true]
setblock 33 -59 36 minecraft:iron_door[half=upper,facing=north,hinge=left,open=true]
fill 34 -60 36 34 -59 36 minecraft:air
setblock 34 -60 36 minecraft:iron_door[half=lower,facing=north,hinge=right,open=true]
setblock 34 -59 36 minecraft:iron_door[half=upper,facing=north,hinge=right,open=true]
scoreboard players set #front aooni.var 1
scoreboard players set #oni_cd aooni.var 0
execute as @e[type=minecraft:zombie,tag=aooni.oni] run function aooni:oni/apply_speed
title @a[tag=aooni.player] times 5 50 15
title @a[tag=aooni.player] title {"text":"현관문이 열렸다!","color":"gold","bold":true}
title @a[tag=aooni.player] subtitle {"text":"아오오니가 미쳐 날뛴다 — 정원 대문으로 달려라!","color":"red"}
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.iron_door.open master @s ~ ~ ~ 1 0.6
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 0.7 1.2
function aooni:game/progress
