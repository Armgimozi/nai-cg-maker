playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"손님의 여행 가방을 열었다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_gr_bag,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
