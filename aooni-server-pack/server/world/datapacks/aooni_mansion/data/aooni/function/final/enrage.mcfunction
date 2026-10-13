tag @s add aooni.enraged
execute if entity @s[type=minecraft:player] run effect give @s minecraft:speed infinite 2 true
# 좀비는 같은 신속에도 훨씬 빨라지므로 한 단계만
execute unless entity @s[type=minecraft:player] run effect give @s minecraft:speed infinite 0 true
playsound minecraft:entity.ravager.roar master @a[distance=..48] ~ ~ ~ 2 0.4
title @a[tag=aooni.player] times 5 40 10
title @a[tag=aooni.player] title {"text":"","color":"red"}
title @a[tag=aooni.player] subtitle {"text":"아오오니가 격노했다! 더 빨라졌다!","color":"red","bold":true}
