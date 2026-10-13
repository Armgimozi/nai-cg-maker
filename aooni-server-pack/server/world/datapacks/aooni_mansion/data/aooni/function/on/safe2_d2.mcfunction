execute if score #w2 aooni.var matches 1 run return run tellraw @s {"text":"봉인②는 이미 풀렸다.","color":"gray"}
scoreboard players add #d22 aooni.var 1
execute if score #d22 aooni.var matches 10.. run scoreboard players set #d22 aooni.var 0
execute store result storage aooni:v d22 int 1 run scoreboard players get #d22 aooni.var
function aooni:safe/show2 with storage aooni:v
playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6
