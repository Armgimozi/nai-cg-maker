playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"괘종시계가 멈춰 있다. 바늘은 3시 33분.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_liv_clock,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
