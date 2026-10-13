kill @e[type=minecraft:block_display,tag=aooni.part]
scoreboard players set #state aooni.var 0
scoreboard players set #cd aooni.var 0
bossbar set aooni:goal visible false
bossbar set aooni:boss visible false
time set 18000
kill @e[type=minecraft:item]
kill @e[type=minecraft:zombie,tag=aooni.dummy]
kill @e[type=minecraft:experience_orb]
scoreboard players set #test aooni.var 0
scoreboard players reset * aooni.kz
# 연습용 아오오니가 남긴 팀 기록 정리(사람은 이 아래에서 모두 다른 팀으로 옮겨진다)
team empty aooni_out
scoreboard objectives setdisplay sidebar
scoreboard players reset * aooni.side
execute as @a[gamemode=!creative] run function aooni:player/to_lobby
execute as @a[gamemode=creative,tag=aooni.player] run effect clear @s
execute as @a[gamemode=creative] run function aooni:player/clear_tags
execute as @a[gamemode=creative] run function aooni:player/reset_attrs
team leave @a[gamemode=creative]
