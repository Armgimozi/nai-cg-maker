playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"낡은 일기장: '이 집에는 무언가가 산다. 파랗고, 거대하고… 문을 잠가도 소용없다.'","color":"gray","italic":true}
tag @s add aooni.me
execute as @e[type=minecraft:marker,tag=aooni.spot_s_lib_diary,limit=1] at @s run function aooni:loot/open
tag @s remove aooni.me
