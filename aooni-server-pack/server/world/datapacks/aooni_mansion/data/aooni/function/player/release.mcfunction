tag @s remove aooni.jailed
tag @s add aooni.alive
team join aooni_alive @s
scoreboard players reset @s aooni.hit
tp @s 5.5 -60 26.5 180 0
tag @s add aooni.safe
scoreboard players set @s aooni.grace 100
title @s actionbar {"text":"풀려났다! 5초간 잡히지 않는다","color":"green"}
