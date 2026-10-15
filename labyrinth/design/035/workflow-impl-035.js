export const meta = {
  name: 'impl-035',
  description: '0.3.5 구현: 전투 모델·스탯·난이도 → 무기 종류 제거 → PvP → 고유 효과 → 방어구 겉모습 → 데이터(요구치·층 없는 루팅·무기 245) → 툴팁·도감·문서, 특별 시련·팩은 따로 동시에, 합치기 후 반박 검토·보완',
  phases: [
    { title: 'Implement', detail: '핵심 묶음 차례로 + 특별 시련·팩 동시' },
    { title: 'Integrate', detail: 'P4·P5 합치기 → P6 툴팁·도감·문서' },
  ],
}

const S = '/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad'
const D = S + '/design2'
const INT = '/home/user/w-int35'
const W4 = '/home/user/w-p4'
const W5 = '/home/user/w-p5'
const TRAILER = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01EGrKVS2PqNerVsBEWjdwKU'

const COMMON = (wt, branch) => `
Project: Minecraft Paper 26.3 RPG server pack "미궁 라비린스" (plugin in labyrinth/plugin, Java 25, Gradle 9; procedural resource pack in labyrinth/resourcepack, python /opt/packvenv/bin/python generate.py --no-preview; asset check: cd labyrinth && /opt/packvenv/bin/python tools/check_assets.py). Build+tests: cd ${wt}/labyrinth/plugin && JAVA_HOME=/opt/jdk25 ./gradlew build -q (must pass; report the test count). The released state is 0.3.4.2 (commit 12232f1).
WORK ONLY in git worktree ${wt} (branch ${branch}). Do not touch other worktrees, never push, never switch branches. Commit your work on ${branch} with a Korean message ending with:
${TRAILER}
All player-facing text Korean, plain and short. Keep existing behaviour you are not asked to change.
DESIGN (read what your package needs; it is the source of truth; when two specs disagree, review2.md §1.A says which wins):
- ${D}/review2.md — FINAL review + merged implementation plan (§5.2 lists files/tests/end conditions per package P0…P6, §5.3 migrations, §1 required corrections). READ §0, §1 and your package section first.
- ${D}/combat_spec.md/.json (combat model, intervals, per-hit, stat roles, skill kinds, difficulty, migration), ${D}/pvp_spec.md/.json, ${D}/look_spec.md/.json, ${D}/gear_spec.md/.json (new weapons/armour, requirements, loot, special trial, shapes), ${D}/unique_spec.md/.json + ${D}/unique_assign_all.json (effects for all weapons), ${D}/directions.json, design scripts in ${D}/tools/ (g2_*, ce_*, rv*_* — reuse them, e.g. as generators).
OWNER DECISIONS (final, override anything older):
1) No weapon types/categories anywhere (no 대검/한손검/활/지팡이/홀/단검 labels or type rules; per-weapon attack interval & attack style melee/ranged/caster derived from mechanics).
2) No attack gauge: every landed click = full damage; server enforces each weapon's interval; one early click buffered (combat_spec). Tooltip shows "공격력" = PER-HIT damage + one line "공격 속도 초당 N회".
3) STR = physical attack power for everyone, INT = magic attack power, DEX = attack speed (+0.5%/pt) + crit +0.25%p + evasion +0.1%p, no attack power. ATTACK SPEED CAP: total +75%, of which DEX share at most +45%; interval floor 0.25 s.
4) Requirements AND-only (no requires_any / "… 중 하나"), split over 2–3 stats (60/40 or 50/30/20), sum T = ceil(2.75(L−1)).
5) Gear has no floor labels; non-boss gear drops from level-band pools across neighbouring floors; epic+ weapons have one source KIND.
6) PvP: no one-hit cap; stuns stay stuns but shorter vs players with diminishing returns and short immunity; anti glass-cannon per pvp_spec.
7) Difficulty per combat_spec + review2 fixes (hard HP 1.45, shadow skill 0.70 / crit dmg +0.50, priest early/late fix, fewer floor-3 elite-room summons so it fits 20–90 s).
8) Owner answers to review2 §6: B3 = WEAKEN the two boss legendaries' unique effects (strength 0.6); B2 = ADD 8 NEW WEAPONS (245 total) — design them yourself in P3 following gear_spec rules where review2 has no full entry; D1 = heavy armour unchanged, light 4-piece "구르기" cooldown 5 s; C1 = attack-speed cap as in 3).
9) Free stat reset once (ext stats.role_reset_035, same pattern as 0.3.4 LevelService.grantRequirementReset); existing items' rolls migrate to new ranges keeping their relative position; untouched config values auto-upgrade, edited values kept.
10) Already decided earlier and must stay: titles = 12 unique-owner titles (0.3.4.1 bonuses), no roll-quality %, no recommended-class text, armour shoulder/back 3D cosmetics REMOVED in 0.3.4.2 (dead code/pack models may be deleted), HUD skill chatter off by default (hud.*).
When done, final answer: short Korean report — what changed, test count, commit sha, anything you could not finish or that the next package must know.`

const pkg = (name, body) => `${COMMON(INT, 'int-035')}\nYOUR PACKAGE: ${name}. ${body}\nPrevious packages in this same branch are already committed — build on them (git log). Do not do later packages' work except tiny glue needed to keep the build green.`

const CHAIN = [
  ['P0', 'combat model + stat roles + difficulty (review2 §5.2 P0, combat_spec §2·§3·§7.2·§8.2·§9·§10, review2 C1/C-fixes). Includes free stat reset, item roll migration, config migration, difficulty numbers, shadow/priest/hunter class numbers, floor-3 elite room summons.'],
  ['P0b', 'weapon-type removal (review2 §3 + §5.2 P0b). items.yml attack blocks / new damage ranges / weapon_skill_factor for the 131 existing weapons generated from combat_spec JSON (write a generator under labyrinth/tools/, keep it).'],
  ['P0c', 'PvP (review2 §5.2 P0c + pvp_spec, owner decision 6). Remove the one-hit cap with config migration; CC durations vs players + diminishing returns + immunity; resilience/heal reduction etc.; pvp_mult data.'],
  ['P1', 'unique effect engine (review2 §5.2 P1 + unique_spec §7/§9). Use unique_assign_all.json as test data; data insertion into items.yml happens in P3 (unless trivial to add for the existing 131 now — your call, say which). Apply owner B3 (two boss legendaries strength 0.6) in the assignment data you leave for P3.'],
  ['P2', 'armour look trade-offs (review2 §5.2 P2 + look_spec, owner D1: tumble cooldown 5 s). Includes the 4-piece bonuses, stat-line renames migration.'],
  ['P3', 'data: requirements rewrite (AND-only, split), floor-free band loot pools, new gear (106 + owner B2 = 8 more weapons → 245 weapons; 6 armour sets), sources incl. trial/special/hoard, recipes, enhance.yml via gen_enhance.py 0.3.5 version (review2 §5.2 P3, gear_spec, A1–A13/B1/B2/E*). One generator labyrinth/tools/gen_035_content.py with inputs copied to labyrinth/tools/data/035/ — no hand edits of generated yml. New weapons need models: use model ids that the pack package P5 (separate branch p5-pack, making 15 new shapes + palettes per gear_spec §9/§10) will provide — follow gear_spec model ids exactly; for the 8 extra weapons reuse existing or gear_spec shapes with new palettes and list them clearly in your report so the integrator can add them to the pack. Special-trial loot tables special_trial_fNN must exist (P4, separate branch, wires the room).'],
]

const P4 = `${COMMON(W4, 'p4-trial')}
YOUR PACKAGE: P4 special trial (review2 §5.2 P4 + gear_spec §6). You are on a separate branch from 0.3.4.2 (the main chain is rewriting combat/data in parallel on int-035 and will merge you later), so keep your change self-contained: new SpecialTrial logic, GimmickRoom conditions/boss bar/success chest/xp ×1.5, gimmick noteMistake lines, player-hurt hook, consumable hook, PlayerData special_miss, dungeon.yml/DungeonConfig keys, floors.yml overrides, SelfTest step, SpecialTrialTest. The success chest rolls loot table "special_trial_fNN" (N = floor); P3 on the other branch creates those tables — on your branch add minimal placeholder tables special_trial_f1..f10 in loot.yml pointing at existing tables, clearly marked "P3 가 교체", so your build/tests pass. Avoid touching combat/stat/pvp/items code.`

const P5 = `${COMMON(W5, 'p5-pack')}
YOUR PACKAGE: P5 resource pack (review2 §5.2 P5 + gear_spec §9/§10 + review2 H1/H2). On a separate branch from 0.3.4.2: add the 15 new weapon silhouettes (voxel/weapons.py functions, BOWS/TWO_HANDED/HOLD tables, hold transforms checked with tools/hold_preview.py sheets vs same-weight existing shapes), palettes and item model entries for EVERY new weapon id and the 6 new armour sets in gear_spec.json (equipment textures + helmets via equipment.py/voxel/armor.py; they must be gap-free like 0.3.4 — no skin showing). The pack reads item ids/models from content/items.yml today — the new items do not exist on your branch yet, so make the pack generator able to take the new definitions from ${D}/gear_spec.json (copy it to labyrinth/tools/data/035/ in your branch) or add a small data file the integrator can point at; describe exactly how the integrator wires it after P3 lands. Also delete the dead armour shoulder/back cosmetic generator (src/armor_pieces.py, preview_armor.py, validate/check_assets references) since 0.3.4.2 removed the feature (leave Java alone — P6 deletes the Java side). generate.py --no-preview validation OK and check_assets 0 errors. Write preview sheets for the new shapes to ${S}/weapon_preview/new035_*.png.`

const chainRun = async () => {
  const out = []
  for (const [name, body] of CHAIN) {
    const r = await agent(pkg(name, body), { label: `impl:${name}`, phase: 'Implement' })
    out.push(`${name}: ${r}`)
    log(`${name} 끝`)
  }
  return out
}

const [chain, p4, p5] = await parallel([
  () => chainRun(),
  () => agent(P4, { label: 'impl:P4-trial', phase: 'Implement' }),
  () => agent(P5, { label: 'impl:P5-pack', phase: 'Implement' }),
])

const integ = await agent(`${COMMON(INT, 'int-035')}
YOUR PACKAGE: INTEGRATE. Merge branch p4-trial and branch p5-pack into int-035 (git merge, resolve conflicts keeping both sides' intent; P3's real special_trial_fNN tables replace P4's placeholders). Wire the pack to the final items.yml (all 245 weapons + new armour have models; the 8 extra P3 weapons need pack entries — add palettes/shape reuse as P3 listed). Then: generate.py --no-preview (validation OK), check_assets (0 errors), gen_enhance.py --check, full build+tests. Fix anything broken. Commit.
Reports so far:
CHAIN:\n${(chain || []).join('\n\n')}\n\nP4:\n${p4}\n\nP5:\n${p5}`, { label: 'integrate', phase: 'Integrate' })

const p6 = await agent(pkg('P6', 'tooltips, codex, forge list, docs (review2 §5.2 P6 + §4 tooltip plan): ItemTooltip (공격력 per hit + 공격 속도 line, AND requirements, unique 2 lines/fold order, look line, source line without floor numbers, no roll quality/class text), CodexMenu (tier sort, source groups incl. 시련방·특별 시련·금고·미믹, look filter, skill power detail), forge list; delete the dead Java armour-cosmetic code (ArmorCosmetics, ArmorPieceLayout, their tests, Teleports passenger handling only if now unused) ; GDD.md, ARCHITECTURE.md, release/README.txt "이번 판에서 바뀐 것 (0.3.5)" + update notes (free stat reset, item migration, config upgrades, titles unchanged); version 0.3.5 in plugin/build.gradle.kts. TooltipFitTest/CodexSourceTextTest updated; all tests green.'), { label: 'impl:P6', phase: 'Integrate' })

// 사용자 결정(주간 한도): 검토·보완 단계 뺌 — 마지막 확인은 리드가 직접 (팩·selftest·배포 zip)
return { chain, p4, p5, integ, p6 }
