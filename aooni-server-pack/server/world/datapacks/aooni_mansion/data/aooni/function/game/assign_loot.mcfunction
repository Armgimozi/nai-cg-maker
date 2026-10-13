# 비밀번호 숫자 4개와 물약 3개를 조사 지점 중 무작위 위치에 숨긴다
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig1
tag @e[type=minecraft:marker,tag=aooni.dig1] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig2
tag @e[type=minecraft:marker,tag=aooni.dig2] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig3
tag @e[type=minecraft:marker,tag=aooni.dig3] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig4
tag @e[type=minecraft:marker,tag=aooni.dig4] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.buff1
tag @e[type=minecraft:marker,tag=aooni.buff1] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.buff2
tag @e[type=minecraft:marker,tag=aooni.buff2] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.buff3
tag @e[type=minecraft:marker,tag=aooni.buff3] add aooni.loot
