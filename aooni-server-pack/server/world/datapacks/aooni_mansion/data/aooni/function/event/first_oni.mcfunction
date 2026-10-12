execute unless score #state aooni.var matches 1 run return 0
execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] run function aooni:oni/spawn
execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] as @a[tag=aooni.alive,distance=..24] run title @s times 5 40 15
execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] as @a[tag=aooni.alive,distance=..24] run title @s title {"text":"……!","color":"dark_red","bold":true}
execute at @e[type=minecraft:marker,tag=aooni.first,limit=1] as @a[tag=aooni.alive,distance=..24] run title @s subtitle {"text":"책장 뒤에 무언가가 있다","color":"red"}
execute as @a[tag=aooni.alive] at @s run playsound minecraft:entity.elder_guardian.curse master @s ~ ~ ~ 0.8 0.5
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"쿵… 쿵… 무거운 발소리가 저택을 울린다. ","color":"dark_red","italic":true},{"text":"아오오니가 나타났다!","color":"red","bold":true}]}
function aooni:oni/reset_cd
