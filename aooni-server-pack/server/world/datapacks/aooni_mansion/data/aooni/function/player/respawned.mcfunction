scoreboard players set @s aooni.deaths 0
execute if score #state aooni.var matches 2 run return run gamemode spectator @s
execute unless score #state aooni.var matches 1 run return run function aooni:player/to_lobby
execute unless entity @s[tag=aooni.player] run return run function aooni:player/watch
execute if entity @s[tag=aooni.oni_p] run return run function aooni:oni/died
function aooni:player/survivor_effects
execute if entity @s[tag=aooni.jailed] run tp @s 5.5 -60 33.5 180 0
execute if entity @s[tag=aooni.out] run gamemode spectator @s
