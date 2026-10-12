execute on passengers run rotate @s ~ 0
execute as @a[tag=aooni.alive,tag=!aooni.hidden,tag=!aooni.safe,gamemode=adventure,distance=..1.6,sort=nearest,limit=1] run function aooni:player/caught
execute if entity @s[tag=aooni.got] run function aooni:oni/vanish
