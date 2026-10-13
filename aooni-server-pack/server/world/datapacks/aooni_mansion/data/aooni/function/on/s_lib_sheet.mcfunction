playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"책장 사이를 더듬었다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_lib_sheet,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
