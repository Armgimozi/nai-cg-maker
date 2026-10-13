playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"작업실 책상 위 설계 메모: '녀석을 벨 수 있는 건 마검뿐… 금고는 창고에.'","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_st_note,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
