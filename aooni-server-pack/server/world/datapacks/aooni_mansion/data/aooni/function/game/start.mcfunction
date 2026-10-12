scoreboard players set #state aooni.var 1
scoreboard players add #gid aooni.var 1
function aooni:build/all
scoreboard players set #k_lib aooni.var 0
scoreboard players set #lib aooni.var 0
scoreboard players set #k_din aooni.var 0
scoreboard players set #din aooni.var 0
scoreboard players set #stairs aooni.var 0
scoreboard players set #store aooni.var 0
scoreboard players set #k_front aooni.var 0
scoreboard players set #front aooni.var 0
scoreboard players set #sheet aooni.var 0
scoreboard players set #f1 aooni.var 0
scoreboard players set #f2 aooni.var 0
scoreboard players set #f3 aooni.var 0
scoreboard players set #f4 aooni.var 0
scoreboard players set #oni_on aooni.var 0
scoreboard players set #pstep aooni.var 0
scoreboard players set #d1 aooni.var 0
scoreboard players set #d2 aooni.var 0
scoreboard players set #d3 aooni.var 0
scoreboard players set #d4 aooni.var 0
scoreboard players set #rescue_cd aooni.var 0
scoreboard players set #sec aooni.var 0
scoreboard players set #prog aooni.var 0
scoreboard players set #sp aooni.var 0
scoreboard players set #cd aooni.var 0
scoreboard players set #amb aooni.var 40
scoreboard players set #onis aooni.var 0
scoreboard players set #oni_cd aooni.var 0
function aooni:game/randomize
tag @e[type=minecraft:marker,tag=aooni.z1] add aooni.on
execute as @a[gamemode=!creative,gamemode=!spectator] run function aooni:player/enter
execute as @a[tag=aooni.player] run function aooni:player/spawn_pos
bossbar set aooni:goal players @a[tag=aooni.player]
bossbar set aooni:goal visible true
scoreboard objectives setdisplay sidebar aooni.side
function aooni:game/progress
function aooni:game/sidebar
title @a[tag=aooni.player] times 10 70 20
title @a[tag=aooni.player] title {"text":"아오오니 저택","color":"blue","bold":true}
title @a[tag=aooni.player] subtitle {"text":"…쾅! 등 뒤에서 현관문이 잠겼다","color":"gray","italic":true}
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.iron_door.close master @s ~ ~ ~ 1 0.6
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.zombie.attack_iron_door master @s ~ ~ ~ 0.6 0.5
execute if score #diff aooni.var matches 1 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"쉬움","color":"green","bold":true},{"text":" · 목숨 3개. 모두 함께 탈출하자!","color":"gray"}]}
execute if score #diff aooni.var matches 2 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"보통","color":"yellow","bold":true},{"text":" · 목숨 2개. 모두 함께 탈출하자!","color":"gray"}]}
execute if score #diff aooni.var matches 3 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"어려움","color":"red","bold":true},{"text":" · 목숨 1개. 모두 함께 탈출하자!","color":"gray"}]}
