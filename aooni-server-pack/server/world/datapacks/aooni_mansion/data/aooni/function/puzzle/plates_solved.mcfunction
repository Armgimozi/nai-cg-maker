scoreboard players set #store aooni.var 1
fill 41 -55 12 41 -54 12 minecraft:air
setblock 41 -55 12 minecraft:iron_door[half=lower,facing=north,hinge=left,open=true]
setblock 41 -54 12 minecraft:iron_door[half=upper,facing=north,hinge=left,open=true]
tag @e[type=minecraft:marker,tag=aooni.z5] add aooni.on
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.iron_door.open master @s ~ ~ ~ 1 0.7
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.6 0.8
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"철컥! 2층 ","color":"white"},{"text":"창고","color":"gold"},{"text":" 문이 열렸다!","color":"white"}]}
function aooni:game/progress
