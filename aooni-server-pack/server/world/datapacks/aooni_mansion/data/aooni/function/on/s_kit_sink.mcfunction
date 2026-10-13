playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"싱크대를 뒤졌다. 식칼꽂이에 칼 하나가 비어 있다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_kit_sink,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
