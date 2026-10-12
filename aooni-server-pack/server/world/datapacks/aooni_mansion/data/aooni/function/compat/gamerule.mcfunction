# 1.21.11 에서 게임룰 이름이 바뀌었다. 두 이름을 모두 시도하고, 버전에 없는 쪽은 조용히 실패한다.
$function aooni:compat/gamerule_try {r:"$(o)",v:"$(v)"}
$function aooni:compat/gamerule_try {r:"$(n)",v:"$(v)"}
