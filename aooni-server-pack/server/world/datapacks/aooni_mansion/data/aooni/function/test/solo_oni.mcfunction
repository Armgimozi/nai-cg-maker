# 아오오니 연습: 부른 사람이 아오오니, 생존자 없음(승패 없음)
execute as @a run function aooni:player/clear_tags
tag @s add aooni.cand_part
tag @s add aooni.oni_p
scoreboard players set #test aooni.var 2
function aooni:game/begin
