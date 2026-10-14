execute store result score #r aooni.var run random value 1..16
execute store result storage aooni:v slot int 1 run random value 0..26
execute if score #r aooni.var matches 1 run function aooni:loot/junk/1 with storage aooni:v
execute if score #r aooni.var matches 2 run function aooni:loot/junk/2 with storage aooni:v
execute if score #r aooni.var matches 3 run function aooni:loot/junk/3 with storage aooni:v
execute if score #r aooni.var matches 4 run function aooni:loot/junk/4 with storage aooni:v
execute if score #r aooni.var matches 5 run function aooni:loot/junk/5 with storage aooni:v
execute if score #r aooni.var matches 6 run function aooni:loot/junk/6 with storage aooni:v
execute if score #r aooni.var matches 7 run function aooni:loot/junk/7 with storage aooni:v
execute if score #r aooni.var matches 8 run function aooni:loot/junk/8 with storage aooni:v
execute if score #r aooni.var matches 9 run function aooni:loot/junk/9 with storage aooni:v
execute if score #r aooni.var matches 10 run function aooni:loot/junk/10 with storage aooni:v
