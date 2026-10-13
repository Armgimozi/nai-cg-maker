scoreboard players set #state aooni.var 2
scoreboard players set #end_t aooni.var 5
kill @e[type=minecraft:block_display,tag=aooni.part]
bossbar set aooni:boss visible false
scoreboard players operation #min aooni.var = #sec aooni.var
scoreboard players operation #min aooni.var /= #60 aooni.var
scoreboard players operation #s aooni.var = #sec aooni.var
scoreboard players operation #s aooni.var %= #60 aooni.var
title @a times 10 100 30
title @a title {"text":"게임 중단","color":"gray"}
title @a subtitle {"text":"아오오니가 자리를 비웠다","color":"gray"}
tellraw @a {"text":"[아오오니 저택] 아오오니가 30초 동안 없어서 게임을 끝냅니다.","color":"gray"}
