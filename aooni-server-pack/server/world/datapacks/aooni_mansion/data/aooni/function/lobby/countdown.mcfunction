scoreboard players remove #cd aooni.var 1
execute if score #cd aooni.var matches 0 run return run function aooni:game/start
execute store result storage aooni:v sec int 1 run scoreboard players get #cd aooni.var
function aooni:lobby/countdown_show with storage aooni:v
