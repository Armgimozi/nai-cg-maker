tag @s add aooni.enraged
function aooni:boss/apply_speed
playsound minecraft:entity.ravager.roar hostile @a[distance=..48] ~ ~ ~ 2 0.4
title @a[tag=aooni.player] times 5 40 10
title @a[tag=aooni.player] title {"text":"","color":"red"}
title @a[tag=aooni.player] subtitle {"text":"거대 아오오니가 격노했다! 더 빨라졌다!","color":"red","bold":true}
