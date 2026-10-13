playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"꽃병 속을 들여다봤다. 장미는 오래전에 시들었다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_hall_vase,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
