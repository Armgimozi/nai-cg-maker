scoreboard players set #stall aooni.var 0
fill 12 -60 10 12 -59 10 minecraft:air
setblock 12 -60 10 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 12 -59 10 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
fill 34 -60 10 34 -59 10 minecraft:air
setblock 34 -60 10 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 34 -59 10 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
fill 44 -60 10 44 -59 10 minecraft:air
setblock 44 -60 10 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 44 -59 10 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
fill 12 -60 24 12 -59 24 minecraft:air
setblock 12 -60 24 minecraft:spruce_door[half=lower,facing=west,hinge=left,open=true]
setblock 12 -59 24 minecraft:spruce_door[half=upper,facing=west,hinge=left,open=true]
fill 20 -60 20 20 -59 20 minecraft:air
setblock 20 -60 20 minecraft:spruce_door[half=lower,facing=west,hinge=left,open=true]
setblock 20 -59 20 minecraft:spruce_door[half=upper,facing=west,hinge=left,open=true]
fill 39 -60 34 39 -59 34 minecraft:air
setblock 39 -60 34 minecraft:spruce_door[half=lower,facing=west,hinge=left,open=true]
setblock 39 -59 34 minecraft:spruce_door[half=upper,facing=west,hinge=left,open=true]
fill 12 -55 8 12 -54 8 minecraft:air
setblock 12 -55 8 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 12 -54 8 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
fill 34 -55 2 34 -54 2 minecraft:air
setblock 34 -55 2 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 34 -54 2 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
fill 38 -55 10 38 -54 10 minecraft:air
setblock 38 -55 10 minecraft:spruce_door[half=lower,facing=west,hinge=left,open=true]
setblock 38 -54 10 minecraft:spruce_door[half=upper,facing=west,hinge=left,open=true]
fill 12 -55 33 12 -54 33 minecraft:air
setblock 12 -55 33 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 12 -54 33 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
fill 16 -55 21 16 -54 21 minecraft:air
setblock 16 -55 21 minecraft:spruce_door[half=lower,facing=west,hinge=left,open=true]
setblock 16 -54 21 minecraft:spruce_door[half=upper,facing=west,hinge=left,open=true]
fill 44 -55 27 44 -54 27 minecraft:air
setblock 44 -55 27 minecraft:spruce_door[half=lower,facing=east,hinge=left,open=true]
setblock 44 -54 27 minecraft:spruce_door[half=upper,facing=east,hinge=left,open=true]
execute as @a[tag=aooni.player] at @s run playsound minecraft:block.wooden_door.open master @s ~ ~ ~ 1 0.6
tellraw @a[tag=aooni.player] {"text":"끼이익… 저택의 모든 옷장 문이 열렸다!","color":"red","bold":true}
