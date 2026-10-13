playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"낡은 상자. 아이 장난감이 가득하다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_sto_box,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
