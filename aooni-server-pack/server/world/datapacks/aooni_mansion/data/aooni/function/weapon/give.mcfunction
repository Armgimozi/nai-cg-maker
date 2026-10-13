# 이름 붙은 검을 먼저 시도하고(아이템 컴포넌트 문법은 버전마다 다를 수 있다), 안 되면 그냥 검을 준다
scoreboard players set #ok aooni.var 0
function aooni:weapon/give_named {nm:"전설의 검"}
execute if score #ok aooni.var matches 0 run give @s minecraft:netherite_sword
function aooni:player/arm_check
