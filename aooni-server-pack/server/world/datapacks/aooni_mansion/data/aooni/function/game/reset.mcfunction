kill @e[type=minecraft:block_display,tag=aooni.part]
scoreboard players set #state aooni.var 0
scoreboard players set #cd aooni.var 0
bossbar set aooni:goal visible false
bossbar set aooni:boss visible false
time set 18000
kill @e[type=minecraft:item]
scoreboard players set #test aooni.var 0
scoreboard objectives setdisplay sidebar
scoreboard players reset * aooni.side
execute as @a[gamemode=!creative] run function aooni:player/to_lobby
execute as @a[gamemode=creative,tag=aooni.player] run effect clear @s
execute as @a[gamemode=creative] run function aooni:player/clear_tags
execute as @a[gamemode=creative] run function aooni:player/reset_attrs
team leave @a[gamemode=creative]
