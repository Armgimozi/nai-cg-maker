# 상자를 모두 비우고 → 상자마다 잡동사니를 0~2개 → 특수 아이템(쪽지·회복·도망/방해·가짜 쪽지)을 서로 다른 상자에 하나씩
execute at @e[type=minecraft:marker,tag=aooni.spot] run data modify block ~ ~ ~ Items set value []
execute as @e[type=minecraft:marker,tag=aooni.spot] at @s run function aooni:loot/junk_roll
execute as @e[type=minecraft:marker,tag=aooni.spot] at @s run function aooni:loot/junk_roll
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/dig1 with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/dig2 with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/dig3 with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/dig4 with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/bread with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/bread with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/bread with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/steak with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/steak with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/heal with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/heal with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/gapple with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/pearl with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/pearl with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/slow with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/slow with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/blind with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/speed with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/speed with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/invis with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/nightv with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/fake1 with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/fake2 with storage aooni:v
execute store result storage aooni:v slot int 1 run random value 0..26
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] at @s run function aooni:loot/put/fake3 with storage aooni:v
