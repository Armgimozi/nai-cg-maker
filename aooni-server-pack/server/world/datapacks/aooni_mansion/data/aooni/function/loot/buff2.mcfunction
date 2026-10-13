tag @e[type=minecraft:marker,tag=aooni.spot,distance=..0.5,limit=1] add aooni.used
effect give @s minecraft:invisibility 25 0 true
playsound minecraft:entity.generic.drink player @s ~ ~ ~ 1 1
tellraw @s {"text":"","extra":[{"text":"[투명 물약]","color":"light_purple","bold":true},{"text":" 을(를) 찾아 썼다! 몸이 투명해졌다… (25초)","color":"white"}]}
