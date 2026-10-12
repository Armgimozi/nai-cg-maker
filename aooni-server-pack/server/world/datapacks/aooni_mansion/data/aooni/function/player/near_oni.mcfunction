playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1
execute if entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..6] run playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1.3
title @s actionbar {"text":"…아오오니가 가까이 있다!","color":"red","bold":true}
