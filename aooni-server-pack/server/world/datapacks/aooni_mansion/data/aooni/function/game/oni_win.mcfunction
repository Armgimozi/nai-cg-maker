scoreboard players set #state aooni.var 2
scoreboard players set #end_t aooni.var 10
kill @e[type=minecraft:block_display,tag=aooni.part]
bossbar set aooni:boss visible false
scoreboard players operation #min aooni.var = #sec aooni.var
scoreboard players operation #min aooni.var /= #60 aooni.var
scoreboard players operation #s aooni.var = #sec aooni.var
scoreboard players operation #s aooni.var %= #60 aooni.var
title @a times 10 100 30
title @a title {"text":"아오오니의 승리","color":"dark_red","bold":true}
title @a subtitle {"text":"","extra":[{"text":"생존자가 모두 붙잡혔다","color":"gray"},{"text":" · 걸린 시간 ","color":"gray"},{"score":{"name":"#min","objective":"aooni.var"},"color":"white"},{"text":"분 ","color":"gray"},{"score":{"name":"#s","objective":"aooni.var"},"color":"white"},{"text":"초","color":"gray"}]}
execute as @a at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 1 0.6
tellraw @a {"text":"","extra":[{"text":"\n[아오오니 저택] ","color":"blue"},{"text":"아오오니 ","color":"dark_red","bold":true},{"selector":"@a[tag=aooni.oni_p]","color":"dark_red"},{"text":" 의 승리! 10초 뒤 대기실로.","color":"white"}]}
