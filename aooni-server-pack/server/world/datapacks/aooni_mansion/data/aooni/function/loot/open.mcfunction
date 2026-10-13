tag @s add aooni.searched
execute if entity @s[tag=aooni.dig1] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/digit1 with storage aooni:v
execute if entity @s[tag=aooni.dig2] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/digit2 with storage aooni:v
execute if entity @s[tag=aooni.dig3] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/digit3 with storage aooni:v
execute if entity @s[tag=aooni.dig4] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/digit4 with storage aooni:v
execute if entity @s[tag=aooni.buff1,tag=!aooni.used] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/buff1
execute if entity @s[tag=aooni.buff2,tag=!aooni.used] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/buff2
execute if entity @s[tag=aooni.buff3,tag=!aooni.used] as @a[tag=aooni.me,limit=1] run return run function aooni:loot/buff3
execute as @a[tag=aooni.me,limit=1] run function aooni:loot/nothing
