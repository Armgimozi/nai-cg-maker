execute as @a[tag=!aooni.seen] run function aooni:player/first_join
execute as @a[scores={aooni.leave=1..}] run function aooni:player/rejoin
execute as @e[type=minecraft:player,scores={aooni.deaths=1..}] run function aooni:player/respawned
function aooni:act/poll
scoreboard players add #t aooni.var 1
execute if score #t aooni.var matches 20.. run function aooni:sec
execute if score #state aooni.var matches 1 run function aooni:game/tick
