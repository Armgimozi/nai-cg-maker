scoreboard players operation #mv aooni.var = @s aooni.mw
scoreboard players operation #mv aooni.var += @s aooni.ms
scoreboard players operation #mv aooni.var += @s aooni.mc
scoreboard players set @s aooni.mw 0
scoreboard players set @s aooni.ms 0
scoreboard players set @s aooni.mc 0
execute if score @s aooni.dd matches 1.. run function aooni:oni/anim/attack
scoreboard players set @s aooni.dd 0
execute if score #atk aooni.var matches 1.. run scoreboard players remove #atk aooni.var 1
execute if score #atk aooni.var matches 3 run function aooni:oni/anim/swing_back_d
execute if score #atk aooni.var matches 1 run function aooni:oni/anim/arm_rest_d
execute if score #mv aooni.var matches 1.. run function aooni:oni/anim/step
execute if score #mv aooni.var matches ..0 run function aooni:oni/anim/still
function aooni:oni/anim/look
