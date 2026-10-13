execute if score #w3 aooni.var matches 1 run return run tellraw @s {"text":"봉인③는 이미 풀렸다.","color":"gray"}
execute unless score #d31 aooni.var = #k31 aooni.var run return run function aooni:safe/wrong
execute unless score #d32 aooni.var = #k32 aooni.var run return run function aooni:safe/wrong
execute unless score #d33 aooni.var = #k33 aooni.var run return run function aooni:safe/wrong
execute unless score #d34 aooni.var = #k34 aooni.var run return run function aooni:safe/wrong
scoreboard players set #w3 aooni.var 1
playsound minecraft:block.iron_door.open block @a[distance=..12] ~ ~ ~ 1 1.4
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.amethyst_block.chime master @s ~ ~ ~ 1 0.8
particle minecraft:enchant ~ ~1 ~ 0.4 0.6 0.4 0.5 40
function aooni:game/progress
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 봉인③를 풀었다! ","color":"light_purple"},{"text":"(","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4)","color":"gray"}]}
data modify entity @e[type=minecraft:text_display,tag=aooni.safe3,limit=1] text set value {"text":"봉인③ · 풀림","color":"green"}
function aooni:altar/show
function aooni:altar/check
