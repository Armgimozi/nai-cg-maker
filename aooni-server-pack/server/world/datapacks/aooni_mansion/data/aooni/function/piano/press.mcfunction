scoreboard players add #pstep aooni.var 1
execute if score #pstep aooni.var matches 1 run scoreboard players operation #exp aooni.var = #p1 aooni.var
execute if score #pstep aooni.var matches 2 run scoreboard players operation #exp aooni.var = #p2 aooni.var
execute if score #pstep aooni.var matches 3 run scoreboard players operation #exp aooni.var = #p3 aooni.var
execute if score #pstep aooni.var matches 4 run scoreboard players operation #exp aooni.var = #p4 aooni.var
execute if score #pstep aooni.var matches 5 run scoreboard players operation #exp aooni.var = #p5 aooni.var
execute unless score #key aooni.var = #exp aooni.var run return run function aooni:piano/wrong
execute if score #pstep aooni.var matches 5.. run function aooni:piano/solved
