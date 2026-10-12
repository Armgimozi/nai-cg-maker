execute if score #stairs aooni.var matches 1 run return run tellraw @s {"text":"계단 철문은 열려 있다.","color":"gray"}
playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 0.8
tellraw @s {"text":"","extra":[{"text":"굳게 닫힌 철문이다. 열쇠 구멍이 없다…","color":"gray"},{"text":" 어디선가 피아노 소리가 나면 열릴 것 같다.","color":"dark_aqua"}]}
