scoreboard players set #state aooni.var 2
scoreboard players set #end_t aooni.var 10
function aooni:oni/kill_all
scoreboard players operation #min aooni.var = #sec aooni.var
scoreboard players operation #min aooni.var /= #60 aooni.var
scoreboard players operation #s aooni.var = #sec aooni.var
scoreboard players operation #s aooni.var %= #60 aooni.var
title @a times 10 100 30
execute if score #escaped aooni.var matches 1.. run title @a title {"text":"탈출 성공!","color":"gold","bold":true}
execute if score #escaped aooni.var matches 0 run title @a title {"text":"전멸…","color":"dark_red","bold":true}
title @a subtitle {"text":"","extra":[{"text":"탈출 ","color":"gray"},{"score":{"name":"#escaped","objective":"aooni.var"},"color":"aqua"},{"text":"명 · 걸린 시간 ","color":"gray"},{"score":{"name":"#min","objective":"aooni.var"},"color":"white"},{"text":"분 ","color":"gray"},{"score":{"name":"#s","objective":"aooni.var"},"color":"white"},{"text":"초","color":"gray"}]}
execute if score #escaped aooni.var matches 1.. as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
execute if score #escaped aooni.var matches 0 as @a at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 1 0.6
tellraw @a {"text":"","extra":[{"text":"\n[아오오니 저택] ","color":"blue"},{"text":"게임 종료! 10초 뒤 대기실로 돌아갑니다.","color":"white"}]}
