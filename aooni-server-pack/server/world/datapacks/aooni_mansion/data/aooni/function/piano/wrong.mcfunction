scoreboard players set #pstep aooni.var 0
execute if score #key aooni.var = #p1 aooni.var run scoreboard players set #pstep aooni.var 1
playsound minecraft:block.note_block.bass block @a[distance=..16] ~ ~ ~ 1 0.5
execute store result score #r aooni.var run random value 1..4
execute if score #r aooni.var matches 1 run tellraw @s {"text":"불협화음이 저택에 울려 퍼졌다…","color":"dark_red","italic":true}
execute if score #r aooni.var matches 1 run tag @s add aooni.me
execute if score #r aooni.var matches 1 run function aooni:oni/alert
tag @s remove aooni.me
