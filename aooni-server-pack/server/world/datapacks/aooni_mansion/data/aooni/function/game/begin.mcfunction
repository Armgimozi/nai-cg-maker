# 참가자(aooni.cand_part)와 #test(0 실전 · 1 생존자 연습 · 2 아오오니 연습)는 부르는 쪽에서 정한다
scoreboard players set #state aooni.var 1
scoreboard players add #gid aooni.var 1
function aooni:build/all
scoreboard players set #sec aooni.var 0
scoreboard players set #sp aooni.var 0
scoreboard players set #cd aooni.var 0
scoreboard players set #found aooni.var 0
scoreboard players set #wpn aooni.var 0
scoreboard players set #final aooni.var 0
scoreboard players set #rescue_cd aooni.var 0
scoreboard players set #freeze aooni.var 0
scoreboard players set #oni_gone aooni.var 0
scoreboard players set #bh aooni.var 0
scoreboard players set #bhp_prev aooni.var 0
scoreboard players set #half10 aooni.var 0
scoreboard players set #hp aooni.var 0
scoreboard players set #amb aooni.var 0
scoreboard players set #stall aooni.var 0
scoreboard players set #a0 aooni.var 0
scoreboard players set #swlost aooni.var 0
scoreboard players set #wmsg aooni.var 0
scoreboard players set #f1 aooni.var 0
scoreboard players set #f2 aooni.var 0
scoreboard players set #f3 aooni.var 0
scoreboard players set #f4 aooni.var 0
scoreboard players set #ap aooni.var 0
scoreboard players set #atk aooni.var 0
scoreboard players set #still aooni.var 0
scoreboard players set #hbl aooni.var 0
scoreboard players set #d1 aooni.var 0
scoreboard players set #d2 aooni.var 0
scoreboard players set #d3 aooni.var 0
scoreboard players set #d4 aooni.var 0
scoreboard players set #amb aooni.var 40
scoreboard players set #freeze aooni.var 20
execute if score #test aooni.var matches 1 run scoreboard players set #freeze aooni.var 0
time set 18000
bossbar set aooni:boss visible false
execute store result score #k1 aooni.var run random value 0..9
execute store result score #k2 aooni.var run random value 0..9
execute store result score #k3 aooni.var run random value 0..9
execute store result score #k4 aooni.var run random value 0..9
execute store result storage aooni:v k1 int 1 run scoreboard players get #k1 aooni.var
execute store result storage aooni:v k2 int 1 run scoreboard players get #k2 aooni.var
execute store result storage aooni:v k3 int 1 run scoreboard players get #k3 aooni.var
execute store result storage aooni:v k4 int 1 run scoreboard players get #k4 aooni.var
execute store result storage aooni:v d1 int 1 run scoreboard players get #d1 aooni.var
execute store result storage aooni:v d2 int 1 run scoreboard players get #d2 aooni.var
execute store result storage aooni:v d3 int 1 run scoreboard players get #d3 aooni.var
execute store result storage aooni:v d4 int 1 run scoreboard players get #d4 aooni.var
# 아오오니 1명: 지원자 중 무작위, 지원자가 없으면 전체 중 무작위 (연습은 부르는 쪽에서 정함)
execute if score #test aooni.var matches 0 as @r[tag=aooni.cand_part,tag=aooni.want_oni] run tag @s add aooni.oni_p
execute if score #test aooni.var matches 0 unless entity @a[tag=aooni.oni_p] as @r[tag=aooni.cand_part] run tag @s add aooni.oni_p
execute as @a[tag=aooni.cand_part,tag=!aooni.oni_p] run function aooni:player/enter
execute as @a[tag=aooni.cand_part,tag=!aooni.oni_p] run function aooni:player/spawn_pos
execute as @a[tag=aooni.oni_p,tag=aooni.cand_part,limit=1] run function aooni:oni/enter
execute store result score #nsurv aooni.var if entity @a[tag=aooni.player,tag=!aooni.oni_p]
tag @a remove aooni.cand_part
execute if score #test aooni.var matches 1.. run scoreboard players enable @a aooni.quit
function aooni:game/assign_loot
bossbar set aooni:goal players @a[tag=aooni.player]
bossbar set aooni:goal color blue
bossbar set aooni:goal visible true
scoreboard objectives setdisplay sidebar aooni.side
function aooni:game/progress
function aooni:game/sidebar
title @a[tag=aooni.player] times 10 70 20
title @a[tag=aooni.player,tag=!aooni.oni_p] title {"text":"아오오니 저택","color":"blue","bold":true}
title @a[tag=aooni.player,tag=!aooni.oni_p] subtitle {"text":"비밀번호 숫자 4개를 찾아 마검을 손에 넣어라","color":"gray"}
title @a[tag=aooni.oni_p] title {"text":"당신은 아오오니","color":"dark_red","bold":true}
title @a[tag=aooni.oni_p] subtitle {"text":"20초 뒤 깨어난다 — 생존자를 모두 잡아라","color":"red"}
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.iron_door.close master @s ~ ~ ~ 1 0.6
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.zombie.attack_iron_door master @s ~ ~ ~ 0.6 0.5
execute if score #test aooni.var matches 0 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"이번 판의 아오오니: ","color":"gray"},{"selector":"@a[tag=aooni.oni_p]","color":"dark_red","bold":true}]}
execute if score #test aooni.var matches 1 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"\n[혼자 연습 · 생존자] ","color":"aqua","bold":true},{"text":"아오오니 없이 저택을 둘러보며 상자를 열고 금고를 풀어 볼 수 있다. 마검을 꺼내면 연습 끝.\n","color":"white"},{"text":"끝내기: 채팅에 ","color":"gray"},{"text":"/trigger aooni.quit","color":"yellow"}]}
execute if score #test aooni.var matches 2 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"\n[혼자 연습 · 아오오니] ","color":"light_purple","bold":true},{"text":"생존자가 없어서 승패가 나지 않는다. 20초 뒤 움직일 수 있다. 문·버튼·옷장을 못 만지는지 확인해 보자.\n","color":"white"},{"text":"끝내기: 채팅에 ","color":"gray"},{"text":"/trigger aooni.quit","color":"yellow"}]}
execute if score #diff aooni.var matches 1 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"쉬움","color":"green","bold":true},{"text":" · 생존자 목숨 4개 · 5대 맞으면 쓰러짐 · 아오오니 기본 속도","color":"gray"}]}
execute if score #diff aooni.var matches 2 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"보통","color":"yellow","bold":true},{"text":" · 생존자 목숨 3개 · 4대 맞으면 쓰러짐 · 아오오니 신속 I","color":"gray"}]}
execute if score #diff aooni.var matches 3 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"난이도 ","color":"gray"},{"text":"어려움","color":"red","bold":true},{"text":" · 생존자 목숨 2개 · 3대 맞으면 쓰러짐 · 아오오니 신속 II","color":"gray"}]}
