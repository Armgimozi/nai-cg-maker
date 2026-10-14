tag @s remove aooni.jailed
tag @s add aooni.alive
team join aooni_alive @s
tp @s 6.5 -60 15.5 180 0
effect clear @s minecraft:resistance
effect give @s minecraft:resistance 5 4 true
title @s actionbar {"text":"풀려났다! 5초간 다치지 않는다","color":"green"}
