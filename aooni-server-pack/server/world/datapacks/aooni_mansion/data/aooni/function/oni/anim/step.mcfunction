scoreboard players set #still aooni.var 0
scoreboard players add #ap aooni.var 1
scoreboard players operation #am aooni.var = #ap aooni.var
scoreboard players operation #am aooni.var %= #2t aooni.var
execute unless score #am aooni.var matches 0 run return 0
scoreboard players operation #af aooni.var = #ap aooni.var
scoreboard players operation #af aooni.var /= #2t aooni.var
scoreboard players operation #af aooni.var %= #8 aooni.var
execute if score #final aooni.var matches 1 run return run function aooni:oni/anim/frame_big
function aooni:oni/anim/frame
