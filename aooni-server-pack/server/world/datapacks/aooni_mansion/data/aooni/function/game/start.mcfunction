scoreboard players set #state aooni.var 1
scoreboard players add #gid aooni.var 1
function aooni:build/all
scoreboard players set #k_lib aooni.var 0
scoreboard players set #lib aooni.var 0
scoreboard players set #k_din aooni.var 0
scoreboard players set #din aooni.var 0
scoreboard players set #stairs aooni.var 0
scoreboard players set #store aooni.var 0
scoreboard players set #sheet aooni.var 0
scoreboard players set #oni_on aooni.var 0
scoreboard players set #pstep aooni.var 0
scoreboard players set #rescue_cd aooni.var 0
scoreboard players set #sec aooni.var 0
scoreboard players set #sp aooni.var 0
scoreboard players set #cd aooni.var 0
scoreboard players set #weap aooni.var 0
scoreboard players set #wpn aooni.var 0
scoreboard players set #altar aooni.var 0
scoreboard players set #final aooni.var 0
scoreboard players set #boss_up aooni.var 0
scoreboard players set #bhp aooni.var 0
scoreboard players set #bhp_prev aooni.var 0
scoreboard players set #bmax aooni.var 0
scoreboard players set #half10 aooni.var 0
scoreboard players set #pw1 aooni.var 0
scoreboard players set #pw2 aooni.var 0
scoreboard players set #pw3 aooni.var 0
scoreboard players set #pw4 aooni.var 0
scoreboard players set #q1 aooni.var 0
scoreboard players set #q2 aooni.var 0
scoreboard players set #q3 aooni.var 0
scoreboard players set #q4 aooni.var 0
scoreboard players set #w1 aooni.var 0
scoreboard players set #w2 aooni.var 0
scoreboard players set #w3 aooni.var 0
scoreboard players set #w4 aooni.var 0
scoreboard players set #d11 aooni.var 0
scoreboard players set #d12 aooni.var 0
scoreboard players set #d13 aooni.var 0
scoreboard players set #d14 aooni.var 0
scoreboard players set #d21 aooni.var 0
scoreboard players set #d22 aooni.var 0
scoreboard players set #d23 aooni.var 0
scoreboard players set #d24 aooni.var 0
scoreboard players set #d31 aooni.var 0
scoreboard players set #d32 aooni.var 0
scoreboard players set #d33 aooni.var 0
scoreboard players set #d34 aooni.var 0
scoreboard players set #d41 aooni.var 0
scoreboard players set #d42 aooni.var 0
scoreboard players set #d43 aooni.var 0
scoreboard players set #d44 aooni.var 0
scoreboard players set #amb aooni.var 40
scoreboard players set #onis aooni.var 0
scoreboard players set #oni_cd aooni.var 0
time set 18000
bossbar set aooni:boss visible false
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
execute if score #diff aooni.var matches 1 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"쉬움","color":"green","bold":true},{"text":" · 목숨 3개. 비밀번호 4개로 봉인을 풀고, 개쎈 무기로 아오오니를 족쳐라!","color":"gray"}]}
execute if score #diff aooni.var matches 2 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"보통","color":"yellow","bold":true},{"text":" · 목숨 2개. 비밀번호 4개로 봉인을 풀고, 개쎈 무기로 아오오니를 족쳐라!","color":"gray"}]}
execute if score #diff aooni.var matches 3 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"어려움","color":"red","bold":true},{"text":" · 목숨 1개. 비밀번호 4개로 봉인을 풀고, 개쎈 무기로 아오오니를 족쳐라!","color":"gray"}]}
