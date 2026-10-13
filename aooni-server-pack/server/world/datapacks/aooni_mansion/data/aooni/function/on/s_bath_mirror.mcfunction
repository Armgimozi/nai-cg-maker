playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"김 서린 거울을 손으로 닦았다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_bath_mirror,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
