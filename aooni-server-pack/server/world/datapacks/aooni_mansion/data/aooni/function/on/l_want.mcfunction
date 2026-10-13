execute if entity @s[tag=aooni.want_oni] run return run function aooni:lobby/want_off
tag @s add aooni.want_oni
playsound minecraft:entity.ravager.roar master @s ~ ~ ~ 0.4 1.2
tellraw @a {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 님이 ","color":"gray"},{"text":"아오오니","color":"red","bold":true},{"text":"에 지원했습니다. (지원자 중 무작위 1명)","color":"gray"}]}
