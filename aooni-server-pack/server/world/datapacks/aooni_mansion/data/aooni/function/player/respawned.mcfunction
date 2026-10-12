scoreboard players set @s aooni.deaths 0
execute unless score #state aooni.var matches 1 run return run function aooni:player/to_lobby
execute unless entity @s[tag=aooni.player] run return run function aooni:player/watch
effect give @s minecraft:resistance infinite 4 true
effect give @s minecraft:saturation infinite 0 true
effect give @s minecraft:weakness infinite 9 true
execute if entity @s[tag=aooni.jailed] run tp @s 5.5 -60 33.5 180 0
execute if entity @s[tag=aooni.out] run gamemode spectator @s
execute if entity @s[tag=aooni.escaped] run gamemode spectator @s
