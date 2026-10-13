execute if score #w4 aooni.var matches 1 run return run tellraw @s {"text":"봉인④는 이미 풀렸다.","color":"gray"}
scoreboard players add #d44 aooni.var 1
execute if score #d44 aooni.var matches 10.. run scoreboard players set #d44 aooni.var 0
execute store result storage aooni:v d44 int 1 run scoreboard players get #d44 aooni.var
function aooni:safe/show4 with storage aooni:v
playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6
