# 생존자 연습: 모험 모드인 사람 모두 생존자, 아오오니 없음(상자·금고·마검까지)
execute as @a run function aooni:player/clear_tags
tag @a[gamemode=!creative,gamemode=!spectator] add aooni.cand_part
scoreboard players set #test aooni.var 1
function aooni:game/begin
