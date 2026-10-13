execute unless loaded -30 -60 2 run return run schedule function aooni:setup/check_build 1s
execute unless loaded 48 -60 48 run return run schedule function aooni:setup/check_build 1s
execute unless loaded -30 -60 48 run return run schedule function aooni:setup/check_build 1s
execute unless loaded 48 -60 -3 run return run schedule function aooni:setup/check_build 1s
execute unless score #built aooni.var matches 4 run function aooni:build/all
execute if score #state aooni.var matches 0 run function aooni:lobby/show_diff
