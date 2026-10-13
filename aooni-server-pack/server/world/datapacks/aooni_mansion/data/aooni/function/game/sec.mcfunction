scoreboard players add #sec aooni.var 1
# 게임 도중 크리에이티브로 바뀐 사람은 역할에서 뺀다
execute as @a[tag=aooni.player,gamemode=creative] run function aooni:player/leave_role
execute store result score #alive aooni.var if entity @a[tag=aooni.alive,gamemode=adventure]
execute store result score #jailed aooni.var if entity @a[tag=aooni.jailed]
function aooni:game/sidebar
bossbar set aooni:goal players @a[tag=aooni.player]
execute if score #final aooni.var matches 1 run bossbar set aooni:boss players @a[tag=aooni.player]
# 마지막 생존자가 잠깐 끊긴 경우는 20초 기다린다(모두 접속해 있으면 바로 판정)
execute store result score #son aooni.var if entity @a[tag=aooni.player,tag=!aooni.oni_p]
execute if score #alive aooni.var matches 1.. run scoreboard players set #a0 aooni.var 0
execute if score #alive aooni.var matches 0 run scoreboard players add #a0 aooni.var 1
execute if score #alive aooni.var matches 0 if score #son aooni.var >= #nsurv aooni.var run return run function aooni:game/oni_win
execute if score #a0 aooni.var matches 20.. run return run function aooni:game/oni_win
execute unless entity @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] run scoreboard players add #oni_gone aooni.var 1
execute if entity @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] run scoreboard players set #oni_gone aooni.var 0
execute if score #final aooni.var matches 1 if score #oni_gone aooni.var matches 30.. run return run function aooni:game/victory
execute if score #oni_gone aooni.var matches 30.. run return run function aooni:game/no_oni
execute if score #wpn aooni.var matches 1 run function aooni:weapon/watch
function aooni:hide/stall
execute as @a[tag=aooni.player,tag=!aooni.jailed,gamemode=adventure,x=1,y=-61,z=31,dx=8,dy=5,dz=4] run tp @s 5.5 -60 26.5 180 0
execute if score #freeze aooni.var matches 1.. run function aooni:game/freeze_sec
execute as @a[tag=aooni.alive] run function aooni:player/arm_check
execute as @a[tag=aooni.alive,tag=!aooni.hidden] at @s if entity @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure,distance=..9] run function aooni:player/near_oni
execute as @a[tag=aooni.jailed] unless entity @s[x=1,y=-61,z=31,dx=8,dy=5,dz=4] run tp @s 5.5 -60 33.5 180 0
execute if score #rescue_cd aooni.var matches 1.. run scoreboard players remove #rescue_cd aooni.var 1
execute if score #wmsg aooni.var matches 1.. run scoreboard players remove #wmsg aooni.var 1
execute if score #freeze aooni.var matches 0 as @a[tag=aooni.oni_p,tag=!aooni.oni_dead,gamemode=adventure] run title @s actionbar {"text":"","extra":[{"text":"남은 생존자 ","color":"gray"},{"score":{"name":"#alive","objective":"aooni.var"},"color":"red"},{"text":"명 · 감옥 ","color":"gray"},{"score":{"name":"#jailed","objective":"aooni.var"},"color":"yellow"},{"text":"명","color":"gray"}]}
scoreboard players remove #amb aooni.var 1
execute if score #amb aooni.var matches ..0 run function aooni:fx/ambient
scoreboard players operation #m aooni.var = #sec aooni.var
scoreboard players operation #m aooni.var %= #2 aooni.var
execute if score #m aooni.var matches 0 run function aooni:fx/glimmer
