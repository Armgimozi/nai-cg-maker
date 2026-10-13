# 아오오니와 24칸 넘게 떨어진 조사 지점 중 무작위 한 곳(없으면 창고 금고 앞)에 마검을 놓는다
tag @e[type=minecraft:marker,tag=aooni.wcand] remove aooni.wcand
execute as @e[type=minecraft:marker,tag=aooni.spot] at @s unless entity @a[tag=aooni.oni_p,distance=..24] run tag @s add aooni.wcand
execute at @e[type=minecraft:marker,tag=aooni.wcand,sort=random,limit=1] run summon minecraft:item ~ ~0.5 ~ {Item:{id:"minecraft:netherite_sword",count:1},PickupDelay:10s,Age:-32768s,Glowing:1b,Invulnerable:1b,Motion:[0.0d,0.0d,0.0d]}
execute unless entity @e[type=minecraft:marker,tag=aooni.wcand] run summon minecraft:item 41.5 -54 3.5 {Item:{id:"minecraft:netherite_sword",count:1},PickupDelay:10s,Age:-32768s,Glowing:1b,Invulnerable:1b,Motion:[0.0d,0.0d,0.0d]}
