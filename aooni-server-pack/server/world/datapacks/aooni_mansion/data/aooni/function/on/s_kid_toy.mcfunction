playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"장난감 상자를 뒤지자 오르골이 저절로 울린다…","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_kid_toy,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
