title @a[tag=aooni.player] times 5 40 15
title @a[tag=aooni.player] title {"text":"","color":"red"}
title @a[tag=aooni.player,tag=!aooni.oni_p] subtitle {"text":"…아오오니가 깨어났다","color":"dark_red","bold":true}
title @a[tag=aooni.oni_p] subtitle {"text":"사냥 시작!","color":"red","bold":true}
execute as @a[tag=aooni.player] at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 0.8 0.5
bossbar set aooni:goal color red
execute as @e[type=minecraft:zombie,tag=aooni.dummy] run data merge entity @s {NoAI:0b}
