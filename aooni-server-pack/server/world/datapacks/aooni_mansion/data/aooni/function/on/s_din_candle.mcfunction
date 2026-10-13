playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"촛불이 흔들린다. 누군가 방금 옆을 지나간 것처럼…","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_din_candle,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
