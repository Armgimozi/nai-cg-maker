execute if score #store aooni.var matches 1 run return run tellraw @s {"text":"창고 문은 열려 있다.","color":"gray"}
playsound minecraft:block.chest.locked block @s ~ ~ ~ 1 0.8
tellraw @s {"text":"","extra":[{"text":"창고 철문. 문 옆에 네 개의 작은 등불이 꺼져 있다… ","color":"gray"},{"text":"(네 방의 발판을 동시에 밟아야 한다)","color":"dark_aqua"}]}
