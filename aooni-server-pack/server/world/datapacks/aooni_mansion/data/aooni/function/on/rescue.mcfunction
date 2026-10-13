execute unless entity @a[tag=aooni.jailed] run return run tellraw @s {"text":"감옥은 비어 있다.","color":"gray"}
execute if score #rescue_cd aooni.var matches 1.. run return run tellraw @s {"text":"자물쇠가 아직 돌아가지 않는다… 잠시 후 다시.","color":"gray"}
fill 5 -60 30 5 -59 30 minecraft:air
setblock 5 -60 30 minecraft:iron_door[half=lower,facing=north,hinge=left,open=true]
setblock 5 -59 30 minecraft:iron_door[half=upper,facing=north,hinge=left,open=true]
schedule function aooni:jail/close 60t
playsound minecraft:block.iron_door.open block @a[distance=..20] ~ ~ ~ 1 0.7
tellraw @a[tag=aooni.player] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 감옥 문을 열었다!","color":"green"}]}
execute as @a[tag=aooni.jailed] run function aooni:player/release
scoreboard players set #rescue_cd aooni.var 20
execute as @a[tag=aooni.oni_p] run title @s actionbar {"text":"감옥 문이 열리는 소리가 났다!","color":"red","bold":true}
