scoreboard players set #state aooni.var 2
scoreboard players set #end_t aooni.var 12
function aooni:oni/kill_all
scoreboard players operation #min aooni.var = #sec aooni.var
scoreboard players operation #min aooni.var /= #60 aooni.var
scoreboard players operation #s aooni.var = #sec aooni.var
scoreboard players operation #s aooni.var %= #60 aooni.var
title @a times 10 120 30
title @a title {"text":"아오오니를 족쳤다!","color":"gold","bold":true}
title @a subtitle {"text":"","extra":[{"text":"최후의 일격: ","color":"gray"},{"selector":"@a[tag=aooni.lasthit]","color":"aqua"},{"text":" · 걸린 시간 ","color":"gray"},{"score":{"name":"#min","objective":"aooni.var"},"color":"white"},{"text":"분 ","color":"gray"},{"score":{"name":"#s","objective":"aooni.var"},"color":"white"},{"text":"초","color":"gray"}]}
execute as @a at @s run playsound minecraft:entity.ender_dragon.death master @s ~ ~ ~ 0.6 1.2
execute as @a at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
execute as @a[tag=aooni.player,gamemode=adventure] at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 50
fill 33 -60 36 33 -59 36 minecraft:air
setblock 33 -60 36 minecraft:iron_door[half=lower,facing=north,hinge=left,open=true]
setblock 33 -59 36 minecraft:iron_door[half=upper,facing=north,hinge=left,open=true]
fill 34 -60 36 34 -59 36 minecraft:air
setblock 34 -60 36 minecraft:iron_door[half=lower,facing=north,hinge=right,open=true]
setblock 34 -59 36 minecraft:iron_door[half=upper,facing=north,hinge=right,open=true]
time set 1000
tellraw @a {"text":"","extra":[{"text":"\n[아오오니 저택] ","color":"blue"},{"text":"거대 아오오니가 쓰러지자 현관문이 열리고 아침 햇살이 들어온다. ","color":"gold"},{"text":"12초 뒤 대기실로 돌아갑니다.","color":"white"}]}
