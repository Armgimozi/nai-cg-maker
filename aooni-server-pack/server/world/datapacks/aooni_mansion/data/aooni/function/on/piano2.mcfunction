playsound minecraft:block.note_block.harp block @a[distance=..16] ~ ~ ~ 1 0.793701
execute if score #stairs aooni.var matches 1 run return 0
scoreboard players set #key aooni.var 2
function aooni:piano/press
