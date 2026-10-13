execute on passengers run rotate @s ~ 0
execute as @a[tag=aooni.alive,tag=!aooni.hidden,tag=!aooni.safe,gamemode=adventure,distance=..1.6,sort=nearest,limit=1] run function aooni:player/caught
execute if entity @s[tag=aooni.boss] run return run function aooni:boss/tick
execute if entity @s[tag=aooni.got] run return run function aooni:oni/vanish
execute store result score @s aooni.hp run data get entity @s Health
execute if score @s aooni.hp matches ..28 run function aooni:oni/repelled
