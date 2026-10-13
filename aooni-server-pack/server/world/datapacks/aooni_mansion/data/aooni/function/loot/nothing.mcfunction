execute store result score #r aooni.var run random value 1..4
execute if score #r aooni.var matches 1 run tellraw @s {"text":"아무것도 없었다.","color":"dark_gray"}
execute if score #r aooni.var matches 2 run tellraw @s {"text":"종이인 줄 알았는데… 그냥 영수증이다.","color":"dark_gray"}
execute if score #r aooni.var matches 3 run tellraw @s {"text":"돌멩이 하나. 비밀번호가 아니다.","color":"dark_gray"}
execute if score #r aooni.var matches 4 run tellraw @s {"text":"먼지만 풀썩 날린다.","color":"dark_gray"}
