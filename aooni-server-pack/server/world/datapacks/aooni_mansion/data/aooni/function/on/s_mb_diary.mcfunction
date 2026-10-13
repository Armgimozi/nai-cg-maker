playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"부부의 일기장을 넘겼다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_mb_diary,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
