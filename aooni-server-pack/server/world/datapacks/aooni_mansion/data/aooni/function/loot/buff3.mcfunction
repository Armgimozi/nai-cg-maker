tag @e[type=minecraft:marker,tag=aooni.spot,distance=..0.5,limit=1] add aooni.used
effect give @s minecraft:night_vision 120 0 true
playsound minecraft:entity.generic.drink player @s ~ ~ ~ 1 1
tellraw @s {"text":"","extra":[{"text":"[손전등]","color":"light_purple","bold":true},{"text":" 을(를) 찾아 썼다! 어둠 속이 잘 보인다 (2분)","color":"white"}]}
