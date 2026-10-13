execute if score #w1 aooni.var matches 1 run return run tellraw @s {"text":"봉인①는 이미 풀렸다.","color":"gray"}
scoreboard players add #d13 aooni.var 1
execute if score #d13 aooni.var matches 10.. run scoreboard players set #d13 aooni.var 0
execute store result storage aooni:v d13 int 1 run scoreboard players get #d13 aooni.var
function aooni:safe/show1 with storage aooni:v
playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6
