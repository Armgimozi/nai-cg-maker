playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"크레파스로 그린 파란 괴물 그림.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_kid_draw,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
