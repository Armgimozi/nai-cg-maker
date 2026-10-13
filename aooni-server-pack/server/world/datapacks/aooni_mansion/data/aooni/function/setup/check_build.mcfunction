execute unless loaded -30 -60 2 run return run schedule function aooni:setup/check_build 1s
execute unless loaded 48 -60 48 run return run schedule function aooni:setup/check_build 1s
execute unless loaded -30 -60 48 run return run schedule function aooni:setup/check_build 1s
execute unless loaded 48 -60 -3 run return run schedule function aooni:setup/check_build 1s
# 게임 도중에 다시 지으면 숨겨 둔 숫자·모형이 사라진다 → 판이 끝난 뒤에 짓는다
execute unless score #built aooni.var matches 6 unless score #state aooni.var matches 0 run return run schedule function aooni:setup/check_build 10s
execute unless score #built aooni.var matches 6 run function aooni:build/all
execute if score #state aooni.var matches 0 run function aooni:lobby/show_diff
