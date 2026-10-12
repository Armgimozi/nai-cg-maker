execute store result score #c1 aooni.var run random value 0..9
execute store result score #c2 aooni.var run random value 0..9
execute store result score #c3 aooni.var run random value 0..9
execute store result score #c4 aooni.var run random value 0..9
execute store result storage aooni:v c1 int 1 run scoreboard players get #c1 aooni.var
execute store result storage aooni:v c2 int 1 run scoreboard players get #c2 aooni.var
execute store result storage aooni:v c3 int 1 run scoreboard players get #c3 aooni.var
execute store result storage aooni:v c4 int 1 run scoreboard players get #c4 aooni.var
execute store result score #p1 aooni.var run random value 1..5
execute store result score #p2 aooni.var run random value 1..5
execute store result score #p3 aooni.var run random value 1..5
execute store result score #p4 aooni.var run random value 1..5
execute store result score #p5 aooni.var run random value 1..5
execute if score #p1 aooni.var matches 1 run data modify storage aooni:v n1 set value "도"
execute if score #p1 aooni.var matches 2 run data modify storage aooni:v n1 set value "레"
execute if score #p1 aooni.var matches 3 run data modify storage aooni:v n1 set value "미"
execute if score #p1 aooni.var matches 4 run data modify storage aooni:v n1 set value "파"
execute if score #p1 aooni.var matches 5 run data modify storage aooni:v n1 set value "솔"
execute if score #p2 aooni.var matches 1 run data modify storage aooni:v n2 set value "도"
execute if score #p2 aooni.var matches 2 run data modify storage aooni:v n2 set value "레"
execute if score #p2 aooni.var matches 3 run data modify storage aooni:v n2 set value "미"
execute if score #p2 aooni.var matches 4 run data modify storage aooni:v n2 set value "파"
execute if score #p2 aooni.var matches 5 run data modify storage aooni:v n2 set value "솔"
execute if score #p3 aooni.var matches 1 run data modify storage aooni:v n3 set value "도"
execute if score #p3 aooni.var matches 2 run data modify storage aooni:v n3 set value "레"
execute if score #p3 aooni.var matches 3 run data modify storage aooni:v n3 set value "미"
execute if score #p3 aooni.var matches 4 run data modify storage aooni:v n3 set value "파"
execute if score #p3 aooni.var matches 5 run data modify storage aooni:v n3 set value "솔"
execute if score #p4 aooni.var matches 1 run data modify storage aooni:v n4 set value "도"
execute if score #p4 aooni.var matches 2 run data modify storage aooni:v n4 set value "레"
execute if score #p4 aooni.var matches 3 run data modify storage aooni:v n4 set value "미"
execute if score #p4 aooni.var matches 4 run data modify storage aooni:v n4 set value "파"
execute if score #p4 aooni.var matches 5 run data modify storage aooni:v n4 set value "솔"
execute if score #p5 aooni.var matches 1 run data modify storage aooni:v n5 set value "도"
execute if score #p5 aooni.var matches 2 run data modify storage aooni:v n5 set value "레"
execute if score #p5 aooni.var matches 3 run data modify storage aooni:v n5 set value "미"
execute if score #p5 aooni.var matches 4 run data modify storage aooni:v n5 set value "파"
execute if score #p5 aooni.var matches 5 run data modify storage aooni:v n5 set value "솔"
execute store result storage aooni:v d1 int 1 run scoreboard players get #d1 aooni.var
execute store result storage aooni:v d2 int 1 run scoreboard players get #d2 aooni.var
execute store result storage aooni:v d3 int 1 run scoreboard players get #d3 aooni.var
execute store result storage aooni:v d4 int 1 run scoreboard players get #d4 aooni.var
