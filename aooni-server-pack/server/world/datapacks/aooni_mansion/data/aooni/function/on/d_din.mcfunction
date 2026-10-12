execute if score #din aooni.var matches 1 run return run tellraw @s {"text":"식당 문은 열려 있다.","color":"gray"}
execute if score #k_din aooni.var matches 0 run return run function aooni:msg/locked_din
fill 29 -60 12 29 -59 12 minecraft:air
setblock 29 -60 12 minecraft:iron_door[half=lower,facing=north,hinge=left,open=true]
setblock 29 -59 12 minecraft:iron_door[half=upper,facing=north,hinge=left,open=true]
playsound minecraft:block.iron_door.open block @a[distance=..16] ~ ~ ~ 1 0.8
scoreboard players set #din aooni.var 1
tag @e[type=minecraft:marker,tag=aooni.z3] add aooni.on
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) ","color":"white"},{"text":"식당","color":"gold"},{"text":" 문을 열었다. 안쪽에서 피아노가 보인다…","color":"white"}]}
function aooni:game/progress
