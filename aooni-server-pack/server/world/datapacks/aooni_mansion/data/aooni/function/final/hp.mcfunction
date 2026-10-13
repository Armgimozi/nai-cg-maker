execute store result score #bh aooni.var run data get entity @s Health 10
execute store result bossbar aooni:boss value run data get entity @s Health
execute if score #bh aooni.var matches ..0 run return run function aooni:oni/defeated
scoreboard players operation #bd aooni.var = #bhp_prev aooni.var
scoreboard players operation #bd aooni.var -= #bh aooni.var
execute if score #bd aooni.var matches 5.. run function aooni:final/hurt
scoreboard players operation #bhp_prev aooni.var = #bh aooni.var
