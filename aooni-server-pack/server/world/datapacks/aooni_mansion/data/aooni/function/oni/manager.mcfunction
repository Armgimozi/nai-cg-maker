execute if score #final aooni.var matches 1 run return 0
execute if score #diff aooni.var matches 1 run scoreboard players set #oni_max aooni.var 1
execute if score #diff aooni.var matches 2 run scoreboard players set #oni_max aooni.var 1
execute if score #diff aooni.var matches 3 run scoreboard players set #oni_max aooni.var 2
execute store result score #n aooni.var if entity @a[tag=aooni.player]
execute if score #stairs aooni.var matches 1 if score #n aooni.var matches 5.. run scoreboard players add #oni_max aooni.var 1
execute if score #oni_max aooni.var matches 4.. run scoreboard players set #oni_max aooni.var 3
execute if score #onis aooni.var >= #oni_max aooni.var run return 0
scoreboard players remove #oni_cd aooni.var 1
execute if score #oni_cd aooni.var matches ..0 run function aooni:oni/spawn_auto
