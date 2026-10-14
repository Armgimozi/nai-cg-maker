# 생존자가 비밀번호 쪽지(또는 가짜 쪽지)를 처음 손에 넣었는지(1초마다)
execute if score #f1 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:1}] run function aooni:loot/found1
execute if score #f1 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s weapon.offhand minecraft:paper[minecraft:custom_data={aooni_dig:1}] run function aooni:loot/found1
execute if score #f2 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:2}] run function aooni:loot/found2
execute if score #f2 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s weapon.offhand minecraft:paper[minecraft:custom_data={aooni_dig:2}] run function aooni:loot/found2
execute if score #f3 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:3}] run function aooni:loot/found3
execute if score #f3 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s weapon.offhand minecraft:paper[minecraft:custom_data={aooni_dig:3}] run function aooni:loot/found3
execute if score #f4 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_dig:4}] run function aooni:loot/found4
execute if score #f4 aooni.var matches 0 as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s weapon.offhand minecraft:paper[minecraft:custom_data={aooni_dig:4}] run function aooni:loot/found4
execute as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s container.* minecraft:paper[minecraft:custom_data={aooni_fake:1b}] run function aooni:loot/fake
execute as @a[tag=aooni.player,tag=!aooni.oni_p] if items entity @s weapon.offhand minecraft:paper[minecraft:custom_data={aooni_fake:1b}] run function aooni:loot/fake
