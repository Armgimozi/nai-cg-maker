tag @e[type=minecraft:marker,tag=aooni.spot,distance=..0.5,limit=1] add aooni.used
effect give @s minecraft:speed 20 1 true
playsound minecraft:entity.generic.drink player @s ~ ~ ~ 1 1
tellraw @s {"text":"","extra":[{"text":"[신속 물약]","color":"light_purple","bold":true},{"text":" 을(를) 찾아 썼다! 몸이 가벼워졌다! (20초)","color":"white"}]}
