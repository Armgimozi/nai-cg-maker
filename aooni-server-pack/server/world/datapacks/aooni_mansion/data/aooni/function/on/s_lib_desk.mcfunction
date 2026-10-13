playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"서재 책상 서랍을 뒤졌다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_lib_desk,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
