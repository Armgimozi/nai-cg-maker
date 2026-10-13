scoreboard players set #t aooni.var 0
execute if score #state aooni.var matches 2 run return run function aooni:game/ending_sec
execute if score #state aooni.var matches 1 run return run function aooni:game/sec
execute if score #state aooni.var matches 0 run function aooni:lobby/sec
