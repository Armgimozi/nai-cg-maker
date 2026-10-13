# 움직일 수 있는 생존자가 모두 옷장에 숨어 버리면 판이 끝나지 않는다 → 60초 뒤 옷장 문이 저절로 열린다
execute store result score #free aooni.var if entity @a[tag=aooni.alive,tag=!aooni.hidden,gamemode=adventure]
execute if score #free aooni.var matches 1.. run scoreboard players set #stall aooni.var 0
execute if score #free aooni.var matches 0 if score #alive aooni.var matches 1.. run scoreboard players add #stall aooni.var 1
execute if score #stall aooni.var matches 40 run tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"모두가 옷장에 숨어 있다… 공기가 희박해진다. ","color":"dark_aqua"},{"text":"20초 뒤 옷장 문이 저절로 열린다!","color":"red"}]}
execute if score #stall aooni.var matches 60.. run function aooni:hide/force_open
