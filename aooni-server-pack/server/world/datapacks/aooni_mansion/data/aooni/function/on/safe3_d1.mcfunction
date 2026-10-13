execute if score #w3 aooni.var matches 1 run return run tellraw @s {"text":"봉인③는 이미 풀렸다.","color":"gray"}
scoreboard players add #d31 aooni.var 1
execute if score #d31 aooni.var matches 10.. run scoreboard players set #d31 aooni.var 0
execute store result storage aooni:v d31 int 1 run scoreboard players get #d31 aooni.var
function aooni:safe/show3 with storage aooni:v
playsound minecraft:ui.button.click block @a[distance=..8] ~ ~ ~ 0.6 1.6
