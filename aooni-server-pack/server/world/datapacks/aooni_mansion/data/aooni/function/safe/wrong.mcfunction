playsound minecraft:block.chest.locked block @a[distance=..12] ~ ~ ~ 1 0.6
playsound minecraft:block.anvil.land block @a[distance=..32] ~ ~ ~ 0.5 0.5
effect give @s minecraft:glowing 5 0 true
tellraw @s {"text":"…비밀번호가 틀렸다! 금속음이 울려 5초간 위치가 드러난다.","color":"red"}
execute as @a[tag=aooni.oni_p] run title @s actionbar {"text":"창고 금고 쪽에서 금속음이 났다! (틀린 사람이 빛난다)","color":"red","bold":true}
