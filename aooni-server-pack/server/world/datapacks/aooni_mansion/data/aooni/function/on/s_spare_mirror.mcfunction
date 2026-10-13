playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"거울 속, 내 어깨 너머로 파란 무언가가… 돌아보니 아무도 없다.","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_spare_mirror,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
