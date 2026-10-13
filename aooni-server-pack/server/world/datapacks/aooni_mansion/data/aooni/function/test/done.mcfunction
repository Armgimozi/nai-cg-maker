scoreboard players set #state aooni.var 2
scoreboard players set #end_t aooni.var 10
kill @e[type=minecraft:block_display,tag=aooni.part]
bossbar set aooni:boss visible false
scoreboard players operation #min aooni.var = #sec aooni.var
scoreboard players operation #min aooni.var /= #60 aooni.var
scoreboard players operation #s aooni.var = #sec aooni.var
scoreboard players operation #s aooni.var %= #60 aooni.var
title @a times 10 100 30
title @a title {"text":"마검을 손에 넣었다!","color":"gold","bold":true}
title @a subtitle {"text":"실전이라면 여기서 아오오니와 결전이 시작된다","color":"gray"}
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
tellraw @a {"text":"","extra":[{"text":"\n[혼자 연습] ","color":"aqua","bold":true},{"text":"연습 끝! 10초 뒤 대기실로.","color":"white"}]}
