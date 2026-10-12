execute if score #diff aooni.var matches 1 run data modify entity @e[type=minecraft:text_display,tag=aooni.t_diff,limit=1] text set value {"text":"난이도: 쉬움","color":"green"}
execute if score #diff aooni.var matches 2 run data modify entity @e[type=minecraft:text_display,tag=aooni.t_diff,limit=1] text set value {"text":"난이도: 보통","color":"yellow"}
execute if score #diff aooni.var matches 3 run data modify entity @e[type=minecraft:text_display,tag=aooni.t_diff,limit=1] text set value {"text":"난이도: 어려움","color":"red"}
