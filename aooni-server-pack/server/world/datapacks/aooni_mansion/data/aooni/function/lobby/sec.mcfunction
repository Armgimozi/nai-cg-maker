execute store result storage aooni:v n int 1 if entity @a[gamemode=!spectator]
function aooni:lobby/count with storage aooni:v
execute if score #cd aooni.var matches 1.. run function aooni:lobby/countdown
