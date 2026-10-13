playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"욕조에 검푸른 물이 고여 있다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_bath_tub,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
