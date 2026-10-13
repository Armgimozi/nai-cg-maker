scoreboard players set #state aooni.var 2
scoreboard players set #end_t aooni.var 10
function aooni:oni/kill_all
scoreboard players operation #min aooni.var = #sec aooni.var
scoreboard players operation #min aooni.var /= #60 aooni.var
scoreboard players operation #s aooni.var = #sec aooni.var
scoreboard players operation #s aooni.var %= #60 aooni.var
title @a times 10 100 30
title @a title {"text":"전멸…","color":"dark_red","bold":true}
title @a subtitle {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · 버틴 시간 ","color":"gray"},{"score":{"name":"#min","objective":"aooni.var"},"color":"white"},{"text":"분 ","color":"gray"},{"score":{"name":"#s","objective":"aooni.var"},"color":"white"},{"text":"초","color":"gray"}]}
execute as @a at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 1 0.6
tellraw @a {"text":"","extra":[{"text":"\n[아오오니 저택] ","color":"blue"},{"text":"모두 아오오니에게 당했다… 10초 뒤 대기실로 돌아갑니다.","color":"white"}]}
