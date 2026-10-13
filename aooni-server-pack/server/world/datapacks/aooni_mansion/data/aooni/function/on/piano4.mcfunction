playsound minecraft:block.note_block.harp block @a[distance=..16] ~ ~ ~ 1 0.943874
execute if score #stairs aooni.var matches 1 run return run function aooni:clue/pw3 with storage aooni:v
scoreboard players set #key aooni.var 4
function aooni:piano/press
