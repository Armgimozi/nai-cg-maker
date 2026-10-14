scoreboard players add #still aooni.var 1
execute unless score #still aooni.var matches 3 run return 0
scoreboard players set #ap aooni.var 0
execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/rest_big
function aooni:oni/anim/rest
