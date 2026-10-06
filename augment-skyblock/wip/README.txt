스킬 이펙트 작업(진행 중) 보관용. 빌드에는 쓰이지 않는다.
vfx-src-wip.patch: 14a1d4e 기준 작업 트리의 소스 변경 (pack.zip·dist 제외, gen_pack.py 로 다시 만든다).
적용: git apply augment-skyblock/wip/vfx-src-wip.patch  →  python3 pack/gen_pack.py  →  gradle build
