execute if score #wpn aooni.var matches 1 run return run tellraw @s {"text":"금고는 이미 비어 있다.","color":"gray"}
scoreboard players add #d1 aooni.var 1
execute if score #d1 aooni.var matches 10.. run scoreboard players set #d1 aooni.var 0
execute store result storage aooni:v d1 int 1 run scoreboard players get #d1 aooni.var
function aooni:safe/show with storage aooni:v
playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6
