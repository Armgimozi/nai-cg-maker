scoreboard players add @s aooni.life 1
scoreboard players add @s aooni.tgt 1
execute if score @s aooni.tgt matches 2.. run function aooni:oni/retarget
playsound minecraft:entity.iron_golem.step hostile @a[distance=..24] ~ ~ ~ 1.2 0.4
scoreboard players operation #m aooni.var = @s aooni.life
scoreboard players operation #m aooni.var %= #12 aooni.var
execute if score #m aooni.var matches 0 run function aooni:boss/roar
