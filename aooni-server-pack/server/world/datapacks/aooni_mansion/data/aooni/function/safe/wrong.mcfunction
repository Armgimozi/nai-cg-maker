playsound minecraft:block.chest.locked block @a[distance=..12] ~ ~ ~ 1 0.6
playsound minecraft:block.anvil.land block @a[distance=..16] ~ ~ ~ 0.4 0.5
tellraw @s {"text":"…비밀번호가 틀렸다. 금속음이 저택에 울렸다!","color":"red"}
tag @s add aooni.me
function aooni:oni/alert
tag @s remove aooni.me
