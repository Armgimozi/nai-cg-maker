playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"식탁 위 빈 접시를 들춰 봤다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_din_plate,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
