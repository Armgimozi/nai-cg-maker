execute on attacker run tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 무기로 아오오니를 후려쳤다! ","color":"gold"},{"text":"아오오니가 비명을 지르며 달아난다!","color":"yellow"}]}
playsound minecraft:entity.zombie.hurt hostile @a[distance=..24] ~ ~ ~ 1.2 0.5
particle minecraft:crit ~ ~1.5 ~ 0.4 0.6 0.4 0.3 30
tag @s add aooni.repel
function aooni:oni/vanish
scoreboard players add #oni_cd aooni.var 10
