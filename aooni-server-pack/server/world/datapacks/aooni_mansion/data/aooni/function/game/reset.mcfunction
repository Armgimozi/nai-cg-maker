function aooni:oni/kill_all
scoreboard players set #state aooni.var 0
scoreboard players set #cd aooni.var 0
bossbar set aooni:goal visible false
bossbar set aooni:boss visible false
time set 18000
kill @e[type=minecraft:item]
scoreboard objectives setdisplay sidebar
scoreboard players reset * aooni.side
execute as @a[gamemode=!creative] run function aooni:player/to_lobby
