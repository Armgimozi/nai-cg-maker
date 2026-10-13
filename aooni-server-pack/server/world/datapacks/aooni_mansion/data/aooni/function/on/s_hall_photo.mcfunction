playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"가족사진. 아이의 얼굴만 검게 칠해져 있다…","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_hall_photo,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
