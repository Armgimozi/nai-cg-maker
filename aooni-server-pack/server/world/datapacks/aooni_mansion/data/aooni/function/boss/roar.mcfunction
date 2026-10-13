playsound minecraft:entity.ravager.roar hostile @a[distance=..32] ~ ~ ~ 1.5 0.6
particle minecraft:sonic_boom ~ ~1.5 ~ 0 0 0 0 1
effect give @a[tag=aooni.alive,distance=..7] minecraft:slowness 2 1 true
effect give @a[tag=aooni.alive,distance=..7] minecraft:darkness 3 0 true
execute as @a[tag=aooni.alive,distance=..7] run title @s actionbar {"text":"포효에 몸이 굳는다…!","color":"red","bold":true}
