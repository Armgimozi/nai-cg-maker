playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"벽난로 재 속을 뒤졌다. 타다 남은 사진 조각… '1999년 여름'","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_liv_fire,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
