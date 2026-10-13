execute as @a run function aooni:player/clear_tags
tag @a[gamemode=!creative,gamemode=!spectator] add aooni.cand_part
scoreboard players set #test aooni.var 0
function aooni:game/begin
