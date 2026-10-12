tag @s remove aooni.alive
tag @s add aooni.escaped
team join aooni_out @s
title @s times 10 60 20
title @s title {"text":"탈출 성공!","color":"gold","bold":true}
title @s subtitle {"text":"관전 모드로 동료를 지켜보자","color":"gray"}
particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.3 60
playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
tellraw @a {"text":"","extra":[{"text":"✦ ","color":"gold"},{"selector":"@s","color":"aqua"},{"text":" 이(가) 저택에서 탈출했다!","color":"gold"}]}
gamemode spectator @s
