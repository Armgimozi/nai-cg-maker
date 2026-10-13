# 벽 너머의 생존자도 쫓아오게: 가장 가까운(숨지 않은·투명하지 않은) 생존자가 때린 것으로 쳐서 그쪽을 노리게 한다
scoreboard players set #hunt aooni.var 6
execute as @e[type=minecraft:zombie,tag=aooni.dummy] at @s if entity @p[tag=aooni.alive,tag=!aooni.hidden,gamemode=adventure,nbt=!{active_effects:[{id:"minecraft:invisibility"}]}] run damage @s 0.01 minecraft:generic by @p[tag=aooni.alive,tag=!aooni.hidden,gamemode=adventure,nbt=!{active_effects:[{id:"minecraft:invisibility"}]}]
