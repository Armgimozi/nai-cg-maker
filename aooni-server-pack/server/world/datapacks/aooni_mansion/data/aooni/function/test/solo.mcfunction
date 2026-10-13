# 생존자 연습: 모험 모드인 사람 모두 생존자, 아오오니는 연습용 AI
execute as @a run function aooni:player/clear_tags
tag @a[gamemode=!creative,gamemode=!spectator] add aooni.cand_part
scoreboard players set #test aooni.var 1
function aooni:game/begin
