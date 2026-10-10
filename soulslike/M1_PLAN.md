# M1 계획 (전투 도장 + 바닐라 쥐는 법)

읽기 전용 계획 단계의 결과다 (코드 지도·요구 목록·쥐는 법 조사 → 설계 → 반박 검토 뒤 고친 판). DECISIONS.md 가 이 문서보다 앞선다.

## Part 2: Corrected M1 plan

# M1 implementation plan: vanilla grip (P0) and the combat dojo (PS, P1–P9)

Label: m1-architect, corrected by m1-plan-critic.
- Paths are relative to `/home/user/nai-cg-maker/soulslike/`. Java paths are relative to `plugin/src/main/java/kr/souls/`.
- "(Rn)" marks a correction from Part 1.

**Precedence.** DECISIONS rows dated 2026-10-10 and 2026-10-11 come first, then DESIGN.md, then SPEC.md. Every number here is a starting value. The user sets the real ones in the dojo, so every number lives in `config.yml` or `content/*.yml` and none is hard-coded.

**Start.** P0 may start now. PS and P1 onward start only once the AI-tells workflow has merged (DECISIONS 2026-10-11, user "끝나면"). (R26)

---

## 0. Rules for every package

1. **Story hold.**
   - Test enemy ids are generic: `dummy`, `post`, `mob_bare`, `mob_shield`, `elite`.
   - Visible labels are `[시험용]` lang keys only.
   - Existing weapon ids are used as they are. Add no named items.
2. **Lang.**
   - After the AI-tells merge, a package that needs visible text adds its own keys in both `lang/ko.yml` and `lang/en.yml`, in its own marked block. It also adds `SLOTS` widths in `tools/langcheck.py`.
   - Test output stays as `[T]` ASCII lines with `// lang-machine`.
   - If a package must start before the merge, it adds no keys and touches no `Hud`/`ui/*` text. (R26)
3. **File ownership.**
   - A package running in parallel never edits a file another parallel package owns (map in §1).
   - Shared files are append-only, each package in its own marked block. P1-0 creates the blocks:
     - `Souls.java` wiring;
     - `config.yml`;
     - `lang/*.yml`;
     - `tools/langcheck.py` (`SLOTS`, `CONTENT_KEYS`);
     - `tools/bots/lib.js`;
     - `tools/run_tests.sh`;
     - `Keys.java`.
4. **Config layout.**
   - `combat/CombatTuning.java` holds one record per subsystem, read from `combat.*`. `Config` gets one field, `tuning`.
   - P5a keeps its own settings in `enemy/EnemyTuning` (top-level `enemies.*`). `world/Dojo.Cfg` owns `dojo.*`, including `dojo.offset`. P7 uses `Archery.Cfg` and P8 uses `LockOn.Cfg`.
   - A missing section comes back as an empty section built from jar defaults (Config.java:404-409). Every reader falls back to the jar default, and `ConfigDefaultsTest` covers it.
   - Each value has exactly one source. (R21)
5. **Content files.**
   - `content/moves.yml` and `content/enemies.yml` are created in P1-0, added to `Content.FILES`, reloaded in `Souls.reloadAll()`, and given `CONTENT_KEYS` entries (empty tuple).
   - Readers merge key by key over the jar copy, so a later package that adds fields does **not** bump `CONTENT_VERSION` and the user's tuning survives. Bump only for a breaking rename. (R20)
6. **Ticker order:** `load → stamina → input → moves → roll → tap → brains → queue → poise → lock → hud → titles → rings`.
   - Event handlers only record. The `input` slot decides.
   - Brains create hits with contact tick C = now. The queue resolves hits due at or before now.
7. **Entities.**
   - Every plugin entity carries a `SWEEP_TAGS` tag (`souls_foe`, `souls_mark` added in P1-0).
   - Foes spawn through `Foes.spawn` and teleport through `Foes.teleport` (R6, R8). Never call `world.spawn` or `teleport` on a foe directly.
   - Plugin entities can vanish on chunk unload, so registries listen to `EntityRemoveFromWorldEvent` and owners re-ensure entities on their tick. (R7)
8. **Lifecycle.** Packages register reset handlers with `combat/CombatReset` for quit, death, world change and disable. Nobody edits `DeathFlow` after P1-0. (R33)
9. **Input listeners.**
   - `PlayerInteractEvent`, `PlayerDropItemEvent` and `PrePlayerAttackEntityEvent` listeners use `ignoreCancelled=false`. (R1)
   - Every input path gates on `worlds().ours`, born, `Stamina.fighting` and not dead. (R18)
10. **Gates for every package.**
    - `./gradlew build` (JUnit), `python3 tools/langcheck.py`, `tools/textlint.py`.
    - `pack/gen_pack.py` and `artlint` when the package touches the pack.
    - `tools/run_tests.sh --port <own port>` with the package's new bots plus every earlier suite, at 0 ms.
    - Screenshots go to `dist/screenshots/m1/<pkg>_*` (P0 uses `dist/screenshots/grip/`), and the agent looks at each one.
    - **Host lock:** real-client sessions, lag runs and `/souls perf` take the lock, so parallel lanes never run them at once. (R34)
11. **Timing tests.** Exact tick boundaries go in JUnit with a fake clock. Bots check the rule against server-logged ticks, with sampling and retry, never against intended send times. (R35)
12. **Do not touch `DECISIONS.md`.**

---

## 1. Schedule, lanes, ownership

| Pkg | What | Depends on | Can run alongside | What the user can try after it |
|---|---|---|---|---|
| **P0** | Vanilla grip (pack, shield shell, probe models) | none (starts now) | PS, P1-0, P1b | Weapons, shields and bow held exactly like vanilla |
| **PS** | Input probes and spikes S1–S6, S11–S13 | AI-tells merged | P0, P1-0, P1a, P1b | nothing (spike results only) |
| **P1-0** | Contract commit | AI-tells merged | P0, PS | nothing |
| **P1a** | Moves core: light ×3, heavy, running, input, DEX timing, hits, bridges removed | P1-0, P0's ItemFactory hunk | P1b, PS | (after P1c) |
| **P1b** | Foes, dummies, dojo hall v1, TestRoom doorway | P1-0 | P1a, PS, P0 | (after P1c) |
| **P1c** | Roll integration (deny, cancel-at, roll attack, Tumble reveal), feel pass | P1a, P1b, PS (S3/S4/S11) | P7 | Light ×3, heavy, running and roll attacks on dummies |
| **P2a** | Hit queue, dodge judge, guard, guard break, guard counter, dodge telemetry | P1c, PS (S5) | P2b (after P2a's API commit), P7 | Hits from `/soulstest queue`: roll, block, guard break |
| **P2b** | Enemy move model, post brain, telegraph, dojo v2 post | P2a API commit | P2a, P7 | A post that swings at you |
| **P3** | Parry, riposte, backstab, parry stamina, flash, telemetry | P2a, P2b, PS (S2) | P7 | F parry → collapse → left-click riposte; backstabs |
| **P4** | Poise, stagger, posture, hyper armour, counter hits, knockdown | P3 | P7 | Getting staggered, flinches, elite kneel |
| **P5a** | Enemy brain, senses, deck, tokens, three nameless enemies, hygiene | P4 | P6, P7 | `/soulstest foe spawn` fights |
| **P5b** | Arena, wave lever (block), waves, rest refusal, elite boss bar | P5a | P6, P7 | Real waves from the lever |
| **P6** | Off-hand attack, charged heavy, plunge, off-hand swap lock | P4, PS (S1) | P5a, P5b, P7 | Right-click off-hand strikes, charged heavies, plunges |
| **P7** | Bow: AR, 0.35 draw, stamina, return | P1a, P1b | P1c–P6 | Arrows hurt foes and come back |
| **P8** | Lock-on (Q) | P5a, P6 | none | Q lock, marker, aim and roll assist |
| **P9** | Integration, env damage, lang sweep, docs, full gates, `make_dist` | all | none | The M1 gate build |

**Ownership by package** ("+" means add, "~" means change):

- **P0:** `pack/weapons/*`, `SPEC.md`, +`pack/weapons/gripcheck.py` (and its probe models); ~`item/ItemFactory.weapon()` (the shield shell hunk, landed as P0's first commit); `tools/bots/gear.js`; +`tools/client/grip_shots.sh`; DESIGN.md rows (only after the AI-tells merge).
- **PS:** +`input/InputProbe.java`, +`cmd/test/ProbeTestCommands.java`, +`tools/client/probe_shots.sh`, +`tools/bots/probe.js`.
- **P1-0:**
  - +`combat/{Hit, CombatTuning(skeleton), CombatReset}`;
  - +`enemy/{Foe, Foes(stub)}`;
  - +`vfx/Footprint` (copied as is) with `FootprintTest`;
  - ~`DamageCalc` (`toFoe`, `hit`), ~`Keys`, ~`Content` (FILES and the per-key fallback loader), ~`Config` (`tuning`);
  - +`cmd/CombatTestCommands` (dispatcher);
  - `Souls.java` blocks and ticker slots (no-op), the `SWEEP_TAGS` additions;
  - `DeathFlow` (calls `CombatReset`);
  - stub `content/moves.yml` and `content/enemies.yml`, the langcheck `CONTENT_KEYS`.
- **P1a:**
  - `input/{InputRouter, FakeSwingFilter, InputBuffer}`;
  - `combat/{MoveRunner, Moveset, MoveTiming, HitQuery, CombatState, DamageHook}`, `CombatTuning` (the moves section);
  - `progression/AttributeApplier`, `item/{ItemFactory, WeaponRefresh}`;
  - `content/moves.yml`;
  - +`cmd/test/MoveTestCommands`;
  - `tools/bots/{attacks.js (part 1), stats_fx.js, pvp.js}`.
- **P1b:**
  - `enemy/{Foes, VirtualHealth, EnemyDefs, FoeBody}`;
  - `world/{Dojo, TestRoom, WorldService}`;
  - `combat/FoeScaling`;
  - +`cmd/test/FoeTestCommands`;
  - `content/enemies.yml` (dummy);
  - +`tools/bots/foes.js`.
- **P1c:** `combat/{Roll, Tumble}`, `input/SneakTap`, `combat/MoveRunner` (roll-attack hooks), `tools/bots/attacks.js` (part 2).
- **P2a:**
  - +`combat/{PendingHit, HitJudge, IncomingHitQueue, Guard, Telemetry}`;
  - `combat/{Roll, DamageHook, Stamina, CombatState, MoveRunner}`;
  - `item/ItemFactory` (USE_COOLDOWN, WEAPON_FMT 2);
  - `cmd/TestCommands` (`warn`), +`cmd/test/QueueTestCommands`;
  - `tools/bots/{queue.js, guard_break.js, roll_iframes.js}`.
- **P2b:** +`enemy/{EnemyMove, EnemyBrain}`, +`vfx/Telegraph`, `world/Dojo`, `content/enemies.yml` (post), +`cmd/test/PostTestCommands`, +`tools/bots/post.js`.
- **P3, P4:** sequential owners of `combat/*`, `enemy/EnemyBrain`, `enemy/Foes`. Their own `cmd/test/*` and bots.
- **P5a:** `enemy/*` (except `Foes`' public API), `content/enemies.yml`, `cmd/test/FoeTestCommands`, +`tools/bots/brain.js`.
- **P5b:** `world/Dojo`, +`enemy/Waves`, `bonfire/TestBonfire`, `hud/Hud` (boss-bar call only), +`tools/bots/dojo.js`.
- **P6:** `input/InputRouter`, `combat/MoveRunner`, `progression/Stats`, +`item/OffhandLock`, +`combat/Plunge`, `tools/bots/attacks.js` (part 3).
- **P7:** +`combat/Archery`, +`cmd/test/BowTestCommands`, +`tools/bots/bow.js`, `tools/bots/origins_all.js`.
- **P8:** +`combat/LockOn`, +`cmd/test/LockTestCommands`, the pack marker module, ~`InputRouter`/`HitQuery`/`Roll`, +`tools/bots/lock.js`.

**P1-0 contract** (frozen before the lanes split):

```java
// enemy/Foes (P1b implements; P1a and P7 call)
Foe of(Entity e);                                   // null if not ours
List<Foe> near(Location eye, double r);
HitResult hit(Player by, Foe f, Hit h);             // defense, virtual HP, hit feel; stamps lastCombatTick (R23)
<T extends Mob> T spawn(String id, Location at);    // randomizeData=false, adult, drop chances 0, silent (R8)
boolean teleport(Foe f, Location to);               // always RETAIN_PASSENGERS (R6)
// combat/Hit: immutable, built via Hit.builder() so later fields don't break callers
//   moveId, cls, raw, poise, type, counter, crit, dir, attacker
// Foe: entity(), hp(), max(), def(), inStartupOrActive() (false until P2b), yawDelta() (P3)
// combat/CombatReset.register(String owner, BiConsumer<Player, Why> fn); Why = QUIT|DEATH|WORLD|DISABLE
// DamageCalc.toFoe(raw, def, abs, weak), DamageCalc.hit(ar, mv, counter, crit)
```

---

## 2. Spikes (PS lane unless noted; results feed the listed package)

| # | Question | Feeds | How | Fallback |
|---|---|---|---|---|
| S1 | With a FLINT off-hand item that has no use component, does a right click in the air send `use_item` hand=1 after hand=0? Does holding repeat it every 4 ticks? Do RIGHT_CLICK_BLOCK and RIGHT_CLICK_AIR double up on a floor click? | P6 | `mcclient.py` `mdown:right`, `parrying_dagger off` plus `redin_guard_sword main`. InputProbe logs hand, action, `useItemInHand`, tick | Short CONSUMABLE (animation none, long time) on off-hand weapons, triggered at use start, plus `clearActiveItem()` |
| S2 | Does holding F auto-repeat `PlayerSwapHandItemsEvent`? What are the OS initial delay and the rate? | P3 | `hold:f:1.5`, count and time the events | `combat.parry.repeat-min: 4` measured from the last *received* F (R14) |
| S3 | Does `swingOffHand()` reach the player? Does the half-duration restart rule prevent a double swing with an F straight after a left click? | P1c, P3, P6 | `/tick rate 5`, `burst` with F and clicks | An F gesture that sends no swing when the main swing is under half done |
| S4 | Do the `MOVEMENT_SPEED` −50%/−25% and `MOVEMENT_SPEED`+`JUMP_STRENGTH` −100% transient modifiers slow and root the client cleanly? | P1a, P3 | Vanilla `/attribute ... modifier add`, walking under `burst` | Slowness II/I; Slowness 6 for the root |
| S5 | Does a sneak tap reach the server while guarding, or while drinking a vanilla potion? | P2a | `mdown:right` plus `hold:Shift_L:0.1`; `/give potion` | Document it as unsupported |
| S6 | With the 1.21.11 `attack_range` component at max 4.2 (min 0), is a click on an entity at 4.0 an entity hit, and does `PrePlayerAttackEntityEvent` fire? | P1a | Vanilla `/item replace ... flint[attack_range={max_reach:4.2}]` | Ignore it; only the aim hint is lost |
| S8 | Side effects of the `Material.SHIELD` shell (P0): pose, sound, knockback, durability; whether shift-click moves it to the off hand; name; Tumble copies | P0, P6 | `guard.js` control case plus screenshots | Flint shell plus pre-inverted `_block` values |
| S9 | Does a husk show the shield pose through `startUsingItem(OFF_HAND)`? | P5a | Spawn and screenshot | No pose (expected, R9) |
| S10 | Can the knockdown pose reuse Roll's per-player fake ceiling (crawl)? | P4 | `/soulstest knockdown` | Root only |
| S11 | Is sneak still held while a screen is open? | P1c | `hold:Shift_L` + `key:e` | Record only (SneakTap already filters screens) |
| S12 | What does the client still do locally on a cancelled entity attack: sprint stop and ×0.6 speed, crit particles? | P1a | Sprint-click a dummy and a zombie, watch frames | Document; a running attack still reads sprint at the server |
| S13 | Off-hand swing visual length and type: does it follow the main-hand `swing_animation`? | P6 | Off-hand attack with each main-hand class | Accept vanilla behaviour |

S7 is deleted because USE_COOLDOWN groups are decided by design (R4). S3 is reduced (R3).

---

## P0. Vanilla grip (DECISIONS 2026-10-11; starts now)

**Goal.** Held poses match vanilla 1.21.11 exactly, in all four hand contexts and in 3rd person while blocking or drawing.
- Swords, tools, daggers, axes, hammers, spears, halberds, greatswords, the parrying dagger and catalysts use `item/handheld`.
- Shields use `item/shield` and `item/shield_blocking`.
- The bow uses `item/bow` with vanilla pulling.
- The master key and rings already use `item/generated`, following the vanilla `trial_key` precedent, and are not changed. (R25)
- Only the model and texture are ours. SPEC.md "holds" are dropped.

**Method: compose, do not move geometry.**
- The grip stays at model (8,8,8).
- Each hand context = vanilla display × P, where P(p) = Q·(p − (8,8,8)) + g_v:
  - `rotation = euler(R·Q)`
  - `translation = t + s·R·(g_v − 8)`
  - `scale = s`
- Left contexts are computed in effective form (tx, ry, rz negated) and written back explicitly. Today's missing left entries mirror off-hand items, so the pot hangs upward and axe blades point at the elbow.

**Values to write** (unchanged):

| model set | context | rotation | translation | scale |
|---|---|---|---|---|
| handheld, Q=Rz(−45°), g_v=(3,3,8) | tp_r / tp_l | [-10,-90,0] / [-10,90,0] | [0,-1.919,1.544] | 0.85 |
| | fp_r / fp_l | [20,-90,0] / [20,90,0] | [1.13,-1.318,-0.515] | 0.68 |
| shield `_3d`, Q=I, g_v=(0,0,-2) | tp_r, tp_l | [0,90,0] | [0,-2,4] | 1 |
| | fp_r / fp_l | [-180,0,-175] | [-0.91,-8.834,2.5] / [-0.834,-9.09,2.5] | 1.25 |
| shield `_block` (SHIELD shell) | tp_r / tp_l | [-135,25,-180] / [-135,25,180] | [-0.466,-3.456,1.142] / [0.033,-2.675,0.861] | 1 |
| | fp_r / fp_l | [-180,0,175] | [-4.166,-4.09,1.5] / [-4.09,-5.834,1.5] | 1.25 |
| bow (rest and pulling_0..2 share one display), Q=Rz(−45°), g_v=(6,10,8) | tp_r / tp_l | [100,-80,95] / [-80,80,85] | [-0.961,-1.775,-0.035] | 0.9 |
| | fp_r / fp_l | [20,∓90,0] | [1.13,3.858,-0.677] | 0.68 |

**Files.**
- `pack/weapons/_common.py`:
  - Add `VANILLA` (jar values) and `compose(vanilla, Q, g_v)`, which writes all four hand contexts.
  - `hand_display` becomes composed handheld for every kind and length; `catalyst_display` becomes handheld.
  - `shield_display` and `shield_block_display` take no arguments; `bow_display` returns one display.
  - Delete `TP_ROT_CLASS`, `TP_CLASS_OF`, `FP_AIM`, `ANCHOR`, `HEAD`, `FP_SCALE`, `fp_pose`, `fp_frame`, `_fp_points`, `_extent`, `_anchor_aim`, `GUARD`, `GUARD_AIM`, `guard_group`, `guard_display`, `BOW_TP_ROT`, `BOW_PULL_TP_ROT`, `SHIELD_TP_ROT`, `SHIELD_BLOCK_TP_ROT`.
  - Set `ROLL_TUCK` to scale 0.85 and update `tuck_pre`.
  - Rewrite `HOLD` and `_selfcheck()`.
  - `write_item`: drop the `_guard` branch (`using_item` resolves to `_3d` for weapons), keep `_block` and bow pulling, set `SWAP` 1.0.
- `set_a.py` (`build_one` around lines 76–81).
- `blades_a.py`: remove `PARRY_BLOCK`; parrying dagger `use` none.
- `shields_a.py`: remove `HEATER_FP`, `BUCKLER_FP(_BLOCK)`, `GREAT_FP(_BLOCK)`.
- `bow_a.py`: one display.
- `kiln_pot.py`: handheld.
- `set_b.py`: `display_for`, `use_display_for`, `CATALYST_FP`, `SHIELD_FP`, `SHIELD_BLOCK_FP`.
- `pack/weapons/_views.py`: callers pass the `*_lefthand` entries for side "l". Regenerate `dist/screenshots/weapons/<id>_{fp,tp}.png`.
- **New `pack/weapons/gripcheck.py`.** `gen_pack.py` calls it **after** `roll_figure` wraps the item definitions. (R24) It:
  - reads the vanilla display JSON from `/root/.cache/souls-client/versions/1.21.11.jar` when present, otherwise from the embedded `VANILLA` table;
  - checks independently that every hand model has all four contexts, and that our display maps the model grip (8,8,8) to the same arm-space point as vanilla's g_v, and model +Y to vanilla's sprite diagonal, within 1e-3;
  - fails on any `_guard` model, on bow pulling models with different displays, or on a lost `roll_figure` HIDE/MARK wrap;
  - emits probe models `souls:test_grip_sword` (the vanilla `iron_sword` sprite mounted through P⁻¹), `souls:test_grip_shield` (vanilla `ShieldModel` boxes with `shield_base_nopattern`) and `souls:test_grip_bow`. These are test models only: no lang, no plugin item, given with the vanilla `/item replace ... flint[item_model=souls:test_grip_sword]`.
- `SPEC.md`: §1.1, §1.3, §1.4, §1.9, the "자세" lines in §3, §6.1.
- `item/ItemFactory.java`, P0's only plugin hunk and its first commit:
  - `SHIELD_SHELL = Material.SHIELD` for `use: block` classes;
  - unset `MAX_DAMAGE`, `DAMAGE`, `ENCHANTABLE`, `REPAIRABLE`;
  - keep `guardComponent()`;
  - `refreshed()` already rebuilds when the type changes.
- `pack/roll_figure.py`: no code change; regenerate.
- **New `tools/client/grip_shots.sh`:**
  - probe vs vanilla pairs: `test_grip_sword` vs `iron_sword`, `test_grip_shield` vs `shield`, `test_grip_bow` vs `bow` at rest, ≥0.65 s and ≥0.9 s;
  - plus look shots: `redin_guard_sword`, `levy_hatchet off`, `kiln_pot off`, `redin_guard_shield off`, `wall_shortbow`;
  - views: 1st person, F5 back and front, walking, blocking, each with a difference image.
- **`DESIGN.md`** (§9.2/§10.x shield rows, §3.3 note, 13.4 #6 "vanilla pose"): edit **only after** the AI-tells workflow has merged; until then record the edits for P9. (R25)

**Mechanisms.**
- Proven: the transform chain, the BLOCK use animation for any `blocks_attacks` item, and the BOW shell.
- Spike: S8, which also covers shift-click to the off hand, the name, and Tumble hold copies.

**Tests.**
- Python: `_selfcheck`, `gripcheck`.
- Bots:
  - `gear.js`: shields are `minecraft:shield` with BLOCKS_ATTACKS (no reductions, delay 0), and an old FLINT shield is replaced on join (`WEAPON_REFRESH`);
  - `guard.js` passes with the SHIELD shell.

**Real client** (under the host lock).
- `grip_shots.sh`: probe overlays differ from vanilla by ≤1 px, apart from texture-edge antialiasing.
- `roll_strip.sh ITEMS=1 GEAR=greatsword|halberd|shield`.

**Done when:**
- the probe overlays are about 0 px;
- all 20 items have previews;
- the weapon guard shows vanilla's 1.8-style sword block;
- the off-hand pot and blades point down;
- the gates are green.

**Risks (accepted, list them for the user).**
- Items are 15% smaller in 3rd person.
- Greatsword and polearm heads are off-screen in 1st person.
- The spear and halberd block tip sits near the crosshair.
- Our shields are smaller than vanilla's plate, so they sit lower.
- The roll rig may clip long weapons into the ground.

**Defaults to confirm with the user:**
- spears, halberds and hammers use handheld;
- catalysts use handheld;
- equip animation 1.0;
- shield shell `minecraft:shield`.

---

## PS. Input probes and spikes (after the AI-tells merge)

**Goal.** Answer S1–S6 and S11–S13 before the packages that depend on them.

**Files.**
- `input/InputProbe.java`, test mode only. It prints `[T] PROBE ev=<interact|swing|attack|swap|input|drop|shoot> hand= action= cancelled= useItem= will= t=` (ASCII, `// lang-machine`).
- `cmd/test/ProbeTestCommands` (`probe on|off`).
- `tools/client/probe_shots.sh`.
- `tools/bots/probe.js`: confirms the probe lines for a bot's raw packets.

Vanilla commands (`/attribute`, `/item replace` with components) stand in for unbuilt plugin code.

**Output.** One line of result per spike in the package report. P9 copies them into DESIGN §13.4.

**Done when** every spike has a verdict and the fallback to use, and P1a, P1c, P2a, P3 and P6 are told.

---

## P1-0. Contract commit (before the P1 lanes split)

Lands everything listed under P1-0 in §1 as one small commit:
- the `Hit` builder, `Foe`/`Foes` stubs, `DamageCalc.toFoe`/`hit`;
- `CombatReset`, wired into DeathFlow, quit, world change and `onDisable`;
- `CombatTuning` skeleton, `Keys.WEAPON_FMT`, `Keys.DOJO`;
- `Content.FILES` with the per-key jar fallback (R20), stub `moves.yml` and `enemies.yml`, `CONTENT_KEYS`;
- `vfx/Footprint` copied as is from `augment-skyblock/plugin/src/main/java/kr/augsky/vfx/Footprint.java` (DESIGN §12), with `FootprintTest`;
- the `CombatTestCommands` dispatcher;
- ticker slots, per-package marked blocks, and `SWEEP_TAGS += souls_foe, souls_mark`.

**Gates:** `./gradlew build`, langcheck, and every existing suite unchanged.

---

## P1a. Moves core

**Goal.** Vanilla melee is cancelled and the server runs light combo ×3, heavy (sneak + left click, no charge yet) and the running attack. It includes the 6-tick buffer, DEX speed, stamina, slow and step, and cone or line hits through Footprint. Both bridges are removed.

**New files.**
- `input/InputRouter.java`:
  - **`PrePlayerAttackEntityEvent`** at HIGH, `ignoreCancelled=false`, in our worlds only:
    - always cancel;
    - store the target and tick as the aim hint;
    - create no input (R2);
    - PvpGuard LOW still prints `PVP_BLOCK path=melee`.
  - **`PlayerArmSwingEvent`** (HAND only) is the only light or heavy input:
    - it records `(kind, tick)`;
    - the Ticker `input` slot attaches an aim hint from the same or previous tick, applies FakeSwingFilter and gating (R18), and calls `MoveRunner.input`.
  - **Marks for the fake-swing filter:** `PlayerDropItemEvent`, `PlayerInteractEvent` RIGHT_*, and `PlayerInteractEntityEvent`, all at MONITOR with `ignoreCancelled=false` (R1).
  - **Sneak:** read through `p.getCurrentInput().isSneak()`; sneak + swing = HEAVY.
  - **Drinking or casting started during attack startup or active:** `setUseItemInHand(DENY)` for any consumable, so nothing is spent. Tested with a vanilla potion (R17).
- `input/FakeSwingFilter.java`: pure. A swing within ≤1 tick after a drop, use or interact is fake (skyblock WeaponListener:129-136).
- `input/InputBuffer.java`: pure. Keeps the last light, heavy and roll input for `buffer` ticks, accepted from `recovery − accept-before`.
- `combat/Moveset.java`: reads `content/moves.yml`, all §3.6 classes, per-key fallback.
- `combat/MoveTiming.java`: pure DEX math:
  - startup = max(2, round(s/a));
  - recovery = max(4, r/a) with the fraction carried per player;
  - active ticks unchanged;
  - a light cycle is never under 10 ticks.
- `combat/HitQuery.java`:
  - Footprint cone or line from the eyes, ±1.2 vertical, plus distance to the hitbox edge (`Targets.distToBox`);
  - aims along the crosshair; `AimProvider` is the hook for P8;
  - each target is hit once per move; thrusts hit the first target only.
- `combat/MoveRunner.java`, the per-player state machine (idle → startup → active → recovery). It:
  - snapshots the weapon at start;
  - spends stamina with `actionEnd` = move end;
  - sets `souls:attack_slow` (−50% in startup and active, −25% in recovery; S4);
  - applies the forward step on the first active tick, from the Ticker;
  - runs HitQuery on active ticks, then `Foes.hit` or the PvP path;
  - advances the combo index and resets it when idle;
  - opens `cancel-at` (consumed by P1c).
- **Deny list:**
  - `MOVE_DENY why=weapon` when the main hand is not a souls melee weapon (bow, shield, catalyst, empty);
  - `MOVE_DENY why=state|stamina` in a vehicle, in water, climbing, gliding or dead.
- **The attacker's own moves never call `swingMainHand()`** (R3).
- `content/moves.yml`.

**Changes.**
- `CombatState`: move, phase, end ticks, hit set, DEX carry, combo index, buffer, `rollReadyAt`, `lastCombatTick`, `lastHurtTick`.
- `DamageHook`: delete `onSwing`, `onHitFoe`, `player_melee` and `player_sweep`. PvP melee arrives as `player_skill` through `Combat.damage` (souls units × `pvp.damage-scale`).
- `AttributeApplier.weaponSpeed`: the cycle comes from `Moveset` light 1. The values equal today's `pve.swing-ticks`.
- `ItemFactory.weapon()`:
  - `SWING_ANIMATION` whack (spears stab; Q6), with duration = light-1 startup + active **at the holder's DEX tier**;
  - `ATTACK_RANGE {min 0, max = class reach}`;
  - PDC `WEAPON_FMT=1` and `SWING_TIER=<tier>` (R13).
- `WeaponRefresh`: compares format and tier, and refreshes held stacks on a DEX change (`stat`, level-up, join).
- `Config`: warn on the legacy keys `pve.bridge-scale` and `pve.swing-ticks`.

**Config** (`config.yml`):

```yaml
combat:
  input: {buffer: 6, accept-before: 6, fake-swing-window: 1}
  moves:
    motion: {light: [100, 105, 115], heavy: 160, running: 115, roll: 110}
    cost:   {running: 1.15, roll: 1.0}
    slow:   {startup: 0.5, active: 0.5, recovery: 0.25}
    min-light-cycle: 10
    min-startup: 2
    min-recovery: 4
    cancel-at: 0.4
    vertical: 1.2
    roll-attack: {from: -1, to: 6}
    swing-tiers: [10, 20, 30, 40, 60, 99]   # DEX steps at which the item's swing length is rewritten
```

**`content/moves.yml`**: as in the original plan (straight_sword block plus the class comments; values from DESIGN §3.6). The bow line is removed: bow stamina and poise live only in `combat.bow`. (R21)

**Test lines.**
- `MOVE kind=light1|light2|light3|heavy|running cls= s= a= r= stam= t=`
- `MOVE_BUF kind= at=`
- `MOVE_DENY why=stamina|weapon|state`
- `MOVE_CANCEL why=`
- `HIT foe= move= mv= ar= raw= def= dealt= hp= t=`

**JUnit.**
- `FakeSwingFilterTest`: ≤1-tick window, both packet orders.
- `InputBufferTest`: exact boundaries; recovery−6 accepted, −7 dropped.
- `MoveTimingTest`: dagger 3/1/6 → 2/1/7 from DEX 37; straight sword at DEX 40 averages 10.7; greatsword heavy → 11/3/13.1; floor of 10; fractional carry.
- `HitQueryTest`, `MovesetTest` (per-key fallback; light-1 cycle equals the old `swing-ticks`), `DamageCalcTest` +`toFoe`, `ConfigDefaultsTest`, `SwingTierTest`.

**Bots** (`attacks.js` part 1, with a dummy from P1b; boundaries checked on logged ticks, R35):
- `bot.attack(dummy)` gives exactly one `MOVE light1` and `HIT` at start + startup. Mineflayer sends swing before attack, which checks R2.
- Swinging every tick gives starts spaced ≥ the cycle, MV 100/105/115/100, and at most one buffered.
- A dagger swinging every tick has a cycle of exactly 10.
- Sneak + swing gives `MOVE heavy` and `ROLL_TAP_SKIP why=attack`.
- Sprint + swing gives `MOVE running`.
- Stamina 0 gives `MOVE_DENY`; stamina 1 is allowed and ends at 0.
- After `stat dex 40`, cycle sums match, and the held item's swing tier changes once.
- A hotbar switch mid-swing keeps the weapon.
- **Fake swings, sent as the vanilla pair** (R36): drop + `arm_animation` gives no MOVE; `use_item` + `arm_animation` gives no MOVE.
- A bow in the main hand + swing gives `MOVE_DENY why=weapon`.
- A vanilla potion drunk in startup is denied; drunk in recovery it is allowed.

`stats_fx.js`: `PVE_HIT` becomes `HIT`. `pvp.js`: melee is `DEF from=player_skill`; with PvP off, `PVP_BLOCK path=melee` appears and there is no HIT.

**Real client:** the swing on click, the indicator as recovery bar, and that clicks are lost during `missTime` after an air swing (R12). S6 and S12 results applied.

**Risks.**
- Sluggish feel (DESIGN §15 risk 2).
- Heavy and running moves show the light swing (R13, Q7).
- `missTime` limits buffering after air swings.

---

## P1b. Foes, dummies, dojo hall

**New files.**
- `enemy/Foes.java` (registry, the contract API, `EntityRemoveFromWorldEvent` cleanup) and `Foe`.
- `enemy/VirtualHealth.java`: HP = def.hp × `difficulty.enemyHealth` at spawn.
- `enemy/EnemyDefs.java`: reads `enemies.yml` with per-key fallback.
- `enemy/FoeBody.java`:
  - spawns through `spawn(loc, cls, false, consumer)`;
  - `setAdult`, all equipment drop chances 0, `setSilent(true)`, `removeAllGoals`, `setAware(false)` for dummies;
  - `KNOCKBACK_RESISTANCE` 1, `setCanPickupItems(false)`, raiders `setCanJoinRaid(false)`/`setPatrolLeader(false)`;
  - tags `souls_foe` + `souls_ent`; `setPersistent(false)` + `setRemoveWhenFarAway(false)` (R8);
  - cancels every vanilla damage event to foes;
  - on death: `setHealth(0)`, drops and XP cleared;
  - hit feel: `playHurtAnimation(yaw)`, material sound, blood `DUST`.
- `world/Dojo.java`: the code-built hall v1, plus `Dojo.Cfg` (`dojo.offset`). Its tick re-ensures dummies while a player is within 32 blocks (R7).
- `cmd/test/FoeTestCommands`.
- `content/enemies.yml`: `dummy`.

**Changes.**
- `TestRoom`: VERSION 4, a 3-wide north doorway at x = 0.
- `WorldService`: builds the dojo with a `Keys.DOJO` version.
- `FoeScaling`: skips `souls_foe`.

**Config.**

```yaml
dojo: {offset: {dx: 0, dz: -44}}
```

```yaml
# enemies.yml
dummy: {body: zombie, hp: 1000, def: 20, poise: 0, ai: none, regen-after: 60, respawn: 60}
```

**Test lines.** `FOE spawn|die|gone id= why=`.

**JUnit.** `EnemyDefsTest` (including fallback), `VirtualHealthTest`.

**Bots** (`foes.js`):
- dummies exist at join;
- `dummy clear` then a wait respawns them;
- teleporting 300 blocks away and back gives `FOE gone why=unload`, then re-spawned dummies;
- no baby or equipped dummy across 50 spawns.

---

## P1c. Roll integration and feel (first playable)

**Changes.**
- `Roll.blocked()` denies during attack startup or active (`ROLL_DENY why=attack`).
- A roll in recovery after cancel-at cancels the move (`MOVE_CANCEL why=roll`).
- `rollAttackWindow(p, now)` = [kind.next − 1, kind.next + 6].
- A roll attack reveals Tumble early (`Tumble.java`).
- `SneakTap` reads `CombatState.rollReadyAt`.
- `MoveRunner` gets the roll-attack hooks.

**Bots** (`attacks.js` part 2):
- a sneak tap, then a swing at logged roll ticks 5, 9 and 17: buffered to 9, roll attack, plain light;
- a roll during startup is denied; after cancel-at it cancels the move.

**Real client** (host lock):
- S3, S4 and S11 applied;
- roll-attack visuals;
- the slow and step feel;
- dummy hurt animation and particles;
- `dist/screenshots/m1/p1_*`.

**Done when:** all P1 suites and every earlier suite pass, and the user can walk from the test room into the dojo and fight dummies.

---

## P2a. Hit queue and guard

**New files.**
- `combat/PendingHit.java`: attack, raw, poise, staminaDmg, parryable, type, attacker, C, hitsMax, projectile, knockdown.
  - **The `IncomingHitQueue.add(PendingHit)` API lands as the first commit, so P2b can start.**
- `combat/HitJudge.java`: pure.
  - Dodge when roll i-frames [Rr+1, Rr+I] overlap [C, C+d].
  - Also checks the generic invulnerability windows.
- `combat/IncomingHitQueue.java`:
  - d = min(`max-delay`, ceil(ping / `ping-per-tick`)); resolve at C + d; `setNoDamageTicks(0)`.
  - Deliver with `player.damage(raw×guard, generic, causing=attacker)` inside a `resolving` marker:
    - DamageHook applies difficulty and defense (`DEF from=foe_queue`);
    - Roll's own i-frame listener skips marked hits;
    - **vanilla knockback is cancelled while resolving** (R5).
  - Brains and commands never deliver damage directly.
- `combat/Guard.java`:
  - up = the active item has BLOCKS_ATTACKS and the hand is raised;
  - arc measured to the attacker, or to the shooter for projectiles;
  - break: stamina 0, `clearActiveItem`, `setCooldown(item, lowered)` on the item's own group (R4), 24-tick stagger lock;
  - after a block, guard counter until block tick + 12.
- `combat/Telemetry.java`: async CSV, `dodge.csv`.
- `cmd/test/QueueTestCommands`:
  - `queue d <0..3|auto>`, `queue dump`;
  - `queue hit <k> [raw] [stam] [parryable] [knockdown]` (C = now + k);
  - `queue hit at-move <k> …` (R37).

**Changes.**
- `ItemFactory`: every BLOCKS_ATTACKS item gets `USE_COOLDOWN{seconds 0.05, group souls:guard/<id>}`; `WEAPON_FMT` 2.
- `Roll`: exposes `rollStart` and `iframes`; skips queue hits.
- `DamageHook`: the marker and `from=foe_queue`.
- `Stamina`: guard regen reads `Guard.up`.
- `CombatState`: `guardCounterUntil`, `guardBrokenUntil`, `staggerUntil`, invulnerability windows.
- `MoveRunner`: guard counter (MV 150, poise ×1.5, cost ×1.0 light).
- `TestCommands.warn`: enqueues a PendingHit.

**Config.**

```yaml
combat:
  queue: {max-delay: 3, ping-per-tick: 50, hits-max: 1}
  guard: {arc: 70, counter-window: 12, break: {lowered: 30, stagger: 24, damage: guarded}, cooldown-group-seconds: 0.05}
  moves: {motion: {guard-counter: 150}, guard-counter-poise: 1.5, cost: {guard-counter: 1.0}}
```

**Test lines.** `QUEUE c= d= res=dodge|guard|hit`, `GUARD g= stam= dealt=`, `GUARD_BREAK group=`, `GCOUNTER`.

**JUnit.** `HitJudgeTest` (d = 0–3), `GuardTest` (arc edges, projectile to the shooter, stamina formula and minimum of 4, break condition), `PendingHitOrderTest`.

**Bots.**
- `queue.js`: forced d; dodge, guard and hit at the logged overlap boundaries; no vanilla knockback on a queued hit (bot velocity).
- `guard_break.js`: stamina falls by `guardStamina`, then the break gives `GUARD_BREAK`, a `set_cooldown` for group `souls:guard/<id>` only (other FLINT items have no cooldown), and a 24-tick lock.
- `roll_iframes.js`: `warn` goes through the queue; `SCREENDODGE` at 0/60/120 ms (host lock) stays in one band, at most 10 points apart.

**Real client.** The SHIELD-shell block with no sound or knockback, the lowered shield and cooldown overlay after a break, and S5.

---

## P2b. Training post, brain frame, telegraph

**New files.**
- `enemy/EnemyMove.java`: windup, active, recovery, raw, poise, stamina, parryable, Footprint shape, trackUntil, turnRate, hitsMax, delayPause. Every damaging move must wind up for ≥10 ticks; this is checked at load.
- `enemy/EnemyBrain.java`, scripted "post" mode:
  - faces the target at `turnRate` until `trackUntil`;
  - picks targets only among born, fighting players (R19);
  - hits go through `IncomingHitQueue.add`.
- `vfx/Telegraph.java`, about 200 lines (DESIGN §6.4):
  - sound at windup start;
  - 6-tick ember or blood `DUST`, then bone-white for the last 4 ticks;
  - a −0.15 backward velocity nudge;
  - `setAggressive(true)`, `swingMainHand` on the active tick.
- `cmd/test/PostTestCommands`: `post start <move> [period]`, `post stop`.

**Changes.** `world/Dojo` v2 (post station; the tick re-ensures the post); `enemies.yml` `post`, with the table unchanged from the original plan (range 2.4, arc 90).

**Config.**

```yaml
combat:
  telegraph: {min-windup: 10, flash: 6, bone: 4, lean: 0.15}
```

**Test lines.** `WINDUP post.<move> c=<C>`.

**JUnit.** `EnemyMoveTest` (T5 invariant).

**Bots** (`post.js`): every `WINDUP`-to-contact gap is ≥10 ticks; a post hit lands as `QUEUE` with each result; the post re-appears after a chunk unload.

**Real client.** Telegraph colours in the dark dojo.

**Done when** the user can roll through, block and guard-break against the post, the bots pass at 0 ms, and the lag band holds.

---

## P3. Parry, riposte, backstab

**Changes.**
- `combat/Parry.java`:
  - charges 8 stamina when a window opens;
  - gesture `swingOffHand()` (S3);
  - F is allowed in attack recovery, not in startup, active, stagger or riposting;
  - `repeat-min` is measured from the last **received** F (R14);
  - F while guarding keeps the guard up.
- `IncomingHitQueue` judge step 2: `parryable`, attacker within ±60°, `distToBox` ≤ 4.5. On success:
  - no damage;
  - block sound plus a high-pitched anvil;
  - `Particle.FLASH` with `Color` #e8dcc0, plus sparks (never `setGlowing`);
  - `brain.stun(foe, 30)`: `setAware(false)`, push back 0.25, head pitched back, stars;
  - `Parry.parried(p, foe, now+30)`.
- `combat/Crits.java` (new):
  - **Riposte:** within 3.0 of the hitbox edge, in the enemy's front 180°, facing within ±60°; triggered by a light or heavy input.
  - **Backstab:** ≤2.2; dot < −0.7; enemy not in startup or active; turned ≤30° last tick; not immune.
  - **Sequence:** `lookAt` → 20 ticks of riposting (invulnerable, rooted with `souls:crit_root`) → `Foes.teleport` to 1.4 in front (R6) → on tick 8, `swingMainHand()` and the damage.
  - **Damage:** mob ×3.0, boss ×2.0, backstab ×2.5, times crit; 18 i-frames after a backstab.
  - A crouched heavy input that meets backstab conditions becomes a backstab.
- `MoveRunner` tries `Crits` first.
- `EnemyBrain`: `stunned` and `riposted` states, facing history, `inStartupOrActive`.
- `Telemetry`: `parry.csv`.
- `SoulsCommands`: `telemetry summary`.
- +`cmd/test/CritTestCommands`.

**Config.**

```yaml
combat:
  parry: {cost: 8, arc: 60, reach: 4.5, allow-in-recovery: true, repeat-min: 4, stun: 30, push: 0.25, riposte-window: 30}
  riposte: {reach: 3.0, front: 180, facing: 60, ticks: 20, hit-at: 8, pull: 1.4, mob: 3.0, boss: 2.0, cost: 0}
  backstab: {reach: 2.2, behind-dot: -0.7, max-turn: 30, mult: 2.5, iframes: 18, cost: 0}
  crit: {dagger: 1.3, straight_sword: 1.1, curved_sword: 1.1, spear: 1.1, greatsword: 1.0, ultra_greatsword: 0.9, default: 1.0}
  telemetry: {enabled: true}
```

**Test lines.** `PARRY r= stam=`, `PARRIED`, `STUN foe= until=`, `RIPOSTE foe= dmg=`, `BACKSTAB foe= dmg=`, `CRIT_DENY why=`.

**JUnit.** `ParryJudgeTest` (fake clock; exact boundaries C−7/C−8/C/C+d/C+d+1; lock-miss and lock-hit; 10-tick combo; no PvP bonus; greatshield 0), `ParryRepeatTest`, `CritGeometryTest`, `RiposteTimelineTest`.

**Bots.**
- `parry.js`, the DESIGN 13.2 row: plank shield, forced d.
  - The outcome is checked against the logged R − C, with sampling until each boundary offset has occurred (R35).
  - Riposte ×3 with a main-hand left click.
  - Greatshield F gives `PARRY_NONE`.
- `attacks.js` adds a backstab on the dummy facing away.

**Real client.** S2, the F gesture, the flash, the stunned pose, the riposte snap, the backstab.

**Done when** the parry → riposte loop works on the post and `parry.js` passes at 0 ms.

**Risks.** Vanilla bodies cannot "glow white", so particles stand in until M2. The `lookAt` snap may feel jarring.

---

## P4. Poise, stagger, posture

As in the original plan (goal, `Poise`, `Posture`, config, test lines, JUnit), with these corrections:
- "Cancels the move, drink or cast": in M1 only moves and the vanilla-potion stand-in can be cancelled (R17). Estus arrives in M3.
- `poise.js` aligns hits with `queue hit at-move <k>` (R37).
- Knockback pushes foes by velocity only; any teleport of a foe uses `Foes.teleport`.
- `poise.js` scenarios:
  - a post hit staggers the player (`MOVE_CANCEL why=stagger`, no refund);
  - `queue hit at-move 5` during a greatsword heavy holds (`HYPER`);
  - a flinch interrupts the post's windup with no riposte allowed;
  - a knockdown hit gives 24 + 12 i-frames, and the next queued hit gives `QUEUE res=dodge`.

**Real client.** S10, the stagger push, a flinching mob.

**Risk.** With base 0, every hit staggers you (Q5).

---

## P5a. Enemy brain and the three nameless enemies

**Files.**
- `enemy/EnemyBrain.java`:
  - states idle → alert → engage → windup → active → recovery, plus stagger, riposted, return;
  - path with `getPathfinder().moveTo`, re-pathing every 10 ticks;
  - pathing stops during windup, so facing is not fought by MoveControl;
  - archetypes:
    - melee: strafes at 2.5–4.0;
    - shield: advances guarding and lowers the guard in windup; its plugin guard is −80% damage and ×0.5 poise from the front 70°; S9 decides the pose, expected none;
  - leash 24 blocks, then return through `Foes.teleport` if stuck.
- `enemy/Senses.java` (pure), `enemy/MoveDeck.java`, `enemy/AttackTokens.java`, `enemy/EnemyTuning.java`.
- `enemy/FoeBody.java` hygiene:
  - environment damage goes into virtual HP (× virtual max / 20);
  - void or below the fall limit → `Foes.teleport` home;
  - cancel `EntityTransformEvent`, uncaused `EntityCombustEvent` and vanilla knockback.
  - The elite (vindicator) stays `setAggressive(true)` while engaged, so CROSSED arms do not hide its sword (R9).
- `enemies.yml`: `mob_bare`, `mob_shield`, `elite`, as in the original plan.
- `cmd/test/FoeTestCommands`: `foe spawn <id> [n]`, `foe clear`, `foe dump`.

**Config.**

```yaml
enemies: {sight: 16, fov: 120, hearing: 6, hearing-sneak: 3, repath: 10, leash: 24, strafe: {min: 2.5, max: 4.0}}
```

**Test lines.** `WINDUP <id>.<move> c=`, `TOKEN take|drop foe=`, `SENSE foe= why=sight|sound|hit`.

**JUnit.** `MoveDeckTest`, `AttackTokensTest`, `SensesTest`, `EnemyDefsTest` (T5 for all of `enemies.yml`).

**Bots** (`brain.js`):
- at most 2 simultaneous `WINDUP` against one bot;
- every gap ≥10 ticks;
- foes ignore a bot with no origin;
- the elite holds its sword (equipment packet shows the main-hand item).

**Real client.** S9; the elite's combo; `/souls perf` with 4 foes plus 1 player (host lock, budget 3.5 ms).

---

## P5b. Arena, waves, rest refusal

**Files.**
- `world/Dojo.java` v3:
  - 17×17 arena, 4 spawn markers, a 4-block ledge;
  - **the lever is a lever block**, read from `PlayerInteractEvent RIGHT_CLICK_BLOCK` (main hand, `ignoreCancelled=false`) as TestBonfire does (R7). It overrides DESIGN 2.3.8's Interaction.
- `enemy/Waves.java`:
  - start, next, clear;
  - death resets the wave (through `CombatReset`);
  - foes vanishing on unload give `WAVE_ABORT`.
- `bonfire/TestBonfire.java`: rest refusal when an enemy within 16 blocks is targeting the player, or `now − lastCombatTick|lastHurtTick < recent`. A sound plays and a lang notice appears.
- `hud/Hud.boss` for the elite's HP and posture, with the `[시험용]` lang key added here (R26).

**Config.**

```yaml
dojo:
  waves: [[mob_bare], [mob_bare, mob_bare], [mob_shield, mob_bare], [mob_bare, mob_bare, mob_shield], [elite]]
  reset-on-death: true
rest: {refuse: {foe-range: 16, recent: 100}}
```

**Test lines.** `WAVE n= foes=`, `WAVE_CLEAR n=`, `WAVE_ABORT why=`, `REST_DENY why=foe|recent`.

**Bots** (`dojo.js`): the lever gives `WAVE 1`; killing everything gives `WAVE_CLEAR`; death resets; rest refusal for both reasons.

**Done when** the user can pull the lever and fight the waves.

---

## P6. Off-hand attack, charged heavy, plunge, swap lock

**Files.**
- `input/InputRouter`:
  - **Off-hand attack:**
    - `PlayerInteractEvent` RIGHT_*, hand OFF_HAND, `ignoreCancelled=false` (R1);
    - fires when the off hand is a one-handed weapon or the parrying dagger;
    - at most one OFFHAND per tick (RIGHT_CLICK_BLOCK and RIGHT_CLICK_AIR can both arrive);
    - a held right click repeats every 4 ticks and queues repeats;
    - MAIN_HAND use events are ignored for souls weapons with no use component;
    - uses the S1 verdict.
  - **Charged heavy:**
    - a heavy started with sneak held holds at the end of startup while sneak stays held, up to +16 ticks;
    - releases on sneak-up, never as a roll;
    - under 4 extra ticks it is a plain heavy;
    - sneak already up at click time means light.
- `combat/Plunge.java`:
  - an input while airborne with `fallDistance ≥ 2.5` arms a plunge;
  - it resolves on landing (radius 2, MV 250);
  - on a hit, its own `EntityDamageEvent FALL` listener at HIGH cancels that landing's fall damage. DamageHook is HIGHEST with `ignoreCancelled`, so it needs no edit (R11).
- `combat/MoveRunner`:
  - OFFHAND = off-hand class light 1 with **that weapon's `weapons.yml` attack through `DamageCalc.ar`** (STR applies, one-handed);
  - the parrying dagger uses the dagger move with its `attack: 40` (R22);
  - `swingOffHand()`.
- `progression/Stats`: `offhandWeapon(p)`.
- `item/OffhandLock.java`:
  - when `now − lastCombatTick < 100`, deny `SWAP_OFFHAND`, clicks on slot 40, drags, number keys, and shift-clicks of `hand: off` items (a SHIELD shell may auto-equip to the off hand, S8);
  - `SWAP_DENY why=combat`.
- `ItemFactory`: the fallback use component only if S1 fails.

**Config.**

```yaml
combat:
  moves:
    charge: {max: 16, min: 4, motion: 210, poise: 1.5}
    plunge: {min-fall: 2.5, motion: 250, cost: 1.0, radius: 2.0}
    offhand: {repeat: true, cost: 1.0, motion: 100}
  offhand-swap: {calm: 100}
```

**JUnit.** `ChargeTest`, `PlungeTest`, `OffhandLockTest`.

**Bots** (`attacks.js` part 3):
- `use_item` hand 0, then hand 1, with the parrying dagger off: exactly one `MOVE offhand` and `HIT ar=` equal to `DamageCalc.ar(40, STR)` (R36);
- plunge from the **TestRoom ledge** (6-block drop) onto a dummy: `MOVE plunge`, `HIT mv=250`, no `DEF` fall line (R29);
- sneak held 12 ticks: `MOVE heavy charged=12 mv=197.5`;
- a swap in combat is denied, including shift-click.

**Real client.** S1, S13, the off-hand swing, the charged heavy, the plunge.

**Risks.** S1 fails and the fallback is needed. The charged heavy is on the DESIGN §15.2 cut list.

---

## P7. Bow (runs alongside P1c–P6)

**Files.**
- `combat/Archery.java` (+`Cfg`):
  - `EntityShootBowEvent`: if **`getForce()/3`** < `min-force`, or stamina < 1, cancel, then `p.updateInventory()` on the next tick (R10).
  - Tag the arrow PDC with shooter, AR (`weapons.yml` attack 45 × STR curve), power and DEX power (inverse power curve × a; the pull visual stays vanilla). Set `PickupStatus.DISALLOWED`.
  - `ProjectileHitEvent` on a foe: cancel and remove the arrow, then `Foes.hit` (MV 100, poise 4) (R11).
  - Arrows that hit, land or are removed go back to the shooter after `return-delay`.
  - PvP arrows stay on `DamageHook player_projectile` (M6, R27).
- `cmd/test/BowTestCommands`.

**Config.**

```yaml
combat:
  bow: {min-force: 0.35, cost: 8, poise: 4, motion: 100, dex-draw: true, return: all, return-delay: 40}
```

**JUnit.** `BowCalcTest`: threshold on force/3; inverse power; DEX 40 reaches full power earlier; AR × STR.

**Bots.**
- `bow.js`:
  - a full draw on the dummy gives `ARROW force= ar= dealt=` and stamina −8;
  - a short draw gives `ARROW_DENY why=weak`, with the server arrow count unchanged and a `set_slot` resync;
  - the count returns to 32.
- `origins_all.js`: "returns to 32".

**Real client.** Pulling stages; the arrow count after a weak shot; arrow return.

---

## P8. Lock-on (Q)

As in the original plan (goal, `LockOn`, `LockTestCommands`, pack marker, config, JUnit, `lock.js`), with these corrections:
- The marker is an `ItemDisplay` passenger with `setVisibleByDefault(false)`, shown with `showEntity` to the locker only.
- Every teleport of a foe that carries it goes through `Foes.teleport` (R6). Add a `lock.js` case: riposte a locked foe and confirm `RIPOSTE` lands with `LOCK` still on.
- `InputRouter` handles `PlayerDropItemEvent` with `ignoreCancelled=false`. A Q press causes the vanilla client-side item flicker, as today.
- Q is not a MOVE: `lock.js` sends drop + `arm_animation`.

---

## P9. Integration and M1 gate

**Work.**
- **PvP:**
  - stays on P1's direct path (`player_skill`, × `pvp.damage-scale`), with roll i-frames;
  - queue, guard, parry and crits for PvP are M6 (DESIGN §14 M6 row, R27);
  - remove the leftover `DamageHook` paths only.
- **Environment damage:** a cause-list test for foes (DESIGN §15 risk 11).
- **Lang sweep:**
  - check that each package's keys are in both languages;
  - the difficulty tooltip parry-window line (§5.7/§10.3), shown only when it differs from normal;
  - remove the `test_parry` ring note "아직 적용되지 않는 효과";
  - `SLOTS` widths.
- **Docs:**
  - DESIGN §2.3 and §3.1–3.10 marked [지었다]; §6.1/6.3–6.5 as the M1 frame;
  - §12.4/12.5 (new files, content rows, keys), §12.11, §13.2 rows, §13.4 with the PS verdicts, the §14 M1 row;
  - P0's deferred DESIGN rows;
  - `SPEC.md`;
  - `config.yml` comments as the tuning sheet.
- **Gates** (host lock):
  - full `run_tests.sh`;
  - `parry.js`, `guard_break.js` and `attacks.js` at 0/60/120 ms through `lagproxy`;
  - the `SCREENDODGE` band;
  - sneak taps while guarding at the 1-, 2- and 5-tick boundaries;
  - 13.4 real-client rerun: combat feel, left-hand right click, F, root and slow, off-hand use with no component, F repeat, sneak tap while guarding or drinking a potion, sneak with a screen open, `missTime` feel;
  - `make_dist`;
  - `/souls perf`.

**Done when** every gate is green and the build is handed to the user for the §13.6 dojo session.

---

## 3. Dojo room and `/soulstest`

**Room** (`world/Dojo.java`, `Keys.DOJO` version, placed at room centre + `dojo.offset` (0, 0, −44)).
- A corridor from the TestRoom v4 north doorway.
- **v1 (P1b):** three dummies: one facing the entrance, one facing away, one on the lane.
- **v2 (P2b):** the post on a marked tile.
- **v3 (P5b):** a 17×17 arena, 4 spawn markers, a **lever block**, a 4-block ledge with a dummy below.
- Palette and position-hash mixing from the test room; lanterns only.
- The Dojo tick re-ensures dummies and the post while a player is within 32 blocks (R7).
- Vanilla bodies, no names. Uses the test-room bonfire.

**`/soulstest`** (test mode only; one dispatcher, one sub-file per package):

| Command | Package | Purpose |
|---|---|---|
| `probe on\|off` | PS | `PROBE` lines |
| `dojo tp <entry\|hall\|post\|arena\|ledge>`, `dojo build` | P1b/P5b | Teleport and rebuild |
| `dummy spawn [toward\|away] [hp]`, `dummy clear` | P1b | Training dummies |
| `move <light\|heavy\|running\|roll\|gc\|offhand\|plunge\|charged N>`, `moves`, `state` | P1a+ | Force a move; s/a/r at the player's DEX; state dump |
| `queue d <0..3\|auto>`, `queue dump`, `queue hit <k> …`, `queue hit at-move <k> …`, `warn <k> [amt]` | P2a | Hit queue |
| `guard dump` | P2a | |
| `post start <move> [period]`, `post stop` | P2b | Training post |
| `stun <foe>`, `crit dump`, `telemetry flush` | P3 | |
| `posture <foe> <v>`, `poise dump`, `knockdown` | P4 | |
| `foe spawn <id> [n]`, `foe clear`, `foe dump` | P5a | |
| `wave <n>\|next\|clear`, `lever` | P5b | |
| `bow dump` | P7 | |
| `lock dump` | P8 | |

`/souls telemetry summary` (admin, ASCII machine lines), as in the original plan.

---

## 4. Conflicts: DECISIONS over DESIGN

C1–C12 are as in the original plan: grip, swap scale, bow draw, three-shot, elite posture, collapse in M1, tunables, mob bodies, tokens in M1, F weapon art, swap animation and tint, swing stretch. These rows are new:

| # | DESIGN / plan says | Governing rule | Resolution |
|---|---|---|---|
| C13 | The plan ran M1 alongside the AI-tells workflow | DECISIONS 2026-10-11 "AI 티 고치기가 끝난 뒤", user "끝나면" | P0 now; PS and P1 onward after the merge; the lang freeze ends then |
| C14 | The plan's P9 put PvP through the queue with guard | DESIGN §14 M6 row: PvP guard, parry and crits | M1 PvP = direct path plus roll i-frames |
| C15 | §2.3.8: levers are Interaction entities | Review T20: unsaved entities vanish on chunk unload | Lever block plus `RIGHT_CLICK_BLOCK` (TestBonfire pattern) |
| C16 | "Parrying dagger AR 40" as a constant | DECISIONS 2026-10-10: plain gear, uniform STR | `weapons.yml attack: 40` through `DamageCalc.ar` |

---

## 5. DESIGN gaps decided here (all reversible in config)

U1–U5 and V1–V15, N93 and N96 are as in the original plan, with these changes:

| Gap | Decision |
|---|---|
| N93 PvP hooks | PvP through the queue moves to M6; M1 keeps the direct path |
| V16 swing length vs DEX | A DEX tier is written into the item (`combat.moves.swing-tiers`), and stacks are rewritten only when the tier changes |
| V17 heavy and running swing visual | The light swing plays (one item component); accepted for M1 (Q7) |
| V18 drink and cast during an attack | General rule built now and tested with a vanilla potion; estus M3, spells M5 |
| V19 left click with a non-melee main hand | `MOVE_DENY why=weapon` (bow, shield, catalyst, empty) |
| V20 holding F | `repeat-min` from the last received F; a hold gives one press plus one at the OS delay |
| V21 the attacker's own swing | Never re-swung by the server; the server swings only for off-hand attacks, the parry gesture, riposte and plunge |

---

## 6. Questions for the user (defaults chosen so work does not block)

1. Spears and halberds: handheld (default), or the vanilla 1.21.11 spear pose?
2. Hammers: handheld (default), or the vanilla mace pose?
3. Swing length stretched per weapon (default), or vanilla's fixed 6-tick swing?
4. Shield shell `minecraft:shield` (default), or flint plus correction values?
5. No armour means every enemy hit staggers you. Keep that (default), or set a base poise?
6. Spear swing type: stab (default; vanilla raises the spear arm pose during the swing), or the same whack as swords?
7. Heavy, running and charged attacks show the light swing. Accept for M1 (default), or try rewriting the held item's swing length when sneak goes down?

---

## 7. 사용자에게 (한국어 요약)

- 먼저 바뀐 점:
  - 무기 쥐는 각도(P0)는 지금 바로 시작해.
  - 전투 도장은 말씀하신 대로 AI 티 고치기가 끝난 뒤에 시작해.
  - 큰 묶음은 쪼갰고, 입력 시험(PS)을 맨 앞에 뒀어.
  - PvP 막기와 패링은 설계대로 M6 으로 미뤘어.
- P0 끝나면: 검, 도끼, 방패, 활을 바닐라랑 똑같은 각도로 쥐어 (1인칭, 3인칭, 막기, 활 당기기 포함). 바닐라 철검 그림으로 만든 시험 모형을 겹쳐 보고 어긋남이 없는지 확인해. 3인칭에서는 조금 작아지고, 긴 무기 끝은 1인칭 화면 밖으로 나가.
- P1 끝나면: 시험 방 북쪽 문으로 도장에 들어가서 허수아비한테 약공격 3단, 웅크리기 키 + 좌클릭 강공격, 달리기 공격, 구르기 공격을 해 볼 수 있어. 스태미나, 민첩 속도, 입력 기억도 다 들어가. 강공격도 휘두르는 모습은 약공격 길이로 보여.
- P2 끝나면: 정해진 박자로 때리는 시험 말뚝 상대로 구르기 무적, 막기, 막기 깨짐, 막기 반격을 연습해. 막기가 깨져도 다른 무기나 반지는 잠기지 않아.
- P3 끝나면: F로 패링하면 적이 무너지고 좌클릭으로 치명타가 들어가. 등 뒤 치명타도 돼. F를 꾹 누르고 있어도 계속 패링하지는 않아.
- P4, P5 끝나면: 경직, 강인도, 자세 게이지가 붙어. 레버(블록)를 당기면 이름 없는 시험 적 (맨손 잡몹, 방패 잡몹, 정예) 이 파도처럼 나와. 적이 근처에 있으면 화톳불에서 쉴 수 없어.
- P6~P8 끝나면: 우클릭 왼손 공격, 모은 강공격, 낙하 공격, 활 (화살은 돌아와), Q 표적 고정이 들어가.
- P9 끝나면: 관문판 줄게. 도장에서 직접 해 보고 패링 창이랑 비용을 config.yml 과 moves.yml 에서 맞추면 돼. 나중에 판이 바뀌어도 맞춘 값은 지워지지 않아.
- 정해 주시면 좋은 것 (안 정하셔도 기본값으로 진행해):
  - 창과 미늘창, 망치 쥐는 법;
  - 휘두르기 길이;
  - 방패 껍데기;
  - 갑옷 없을 때 매번 경직되는지;
  - 창 찌르기 모양;
  - 강공격 휘두르는 모습.
---

## 부록: 반박 검토에서 고친 점 (R1~)

## Part 1: Findings and corrections

### A. Mechanisms that are infeasible or wrong as written

**R1. Air and right-click `PlayerInteractEvent`s arrive already cancelled.**
- *Problem:* Bukkit builds every `*_CLICK_AIR` event with `useInteractedBlock=DENY`, and `isCancelled()` reads that flag. Protection.java:146 also sets DENY on every `RIGHT_CLICK_BLOCK`. A listener with `ignoreCancelled=true` therefore never sees an off-hand attack, a lever click or a fake-swing mark. The skyblock code says the same at WeaponListener.java:141.
- *Fix:* every input listener uses `ignoreCancelled=false` and checks `useItemInHand() != DENY` itself.

**R2. Packet order makes "merge same-tick swing and attack" unsafe.**
- *Problem:*
  - The vanilla client sends attack, then swing. Mineflayer's `bot.attack` sends swing, then attack.
  - Drop and use packets are each followed by a swing.
  - Any pair can fall on two different server ticks.
  - So the same-tick merge can count one click twice, and a same-tick fake-swing filter can miss.
- *Fix:*
  - Only `PlayerArmSwingEvent(HAND)` creates a light or heavy input. The client swings on every left click: at an entity, at air, at a block, or at an Interaction.
  - `PrePlayerAttackEntityEvent` only cancels the attack and stores the aim hint.
  - FakeSwingFilter uses a window of ≤1 tick, as skyblock's `isFakeSwing` does (WeaponListener.java:129-136).
  - Event handlers only record. The decision happens in the Ticker `input` slot.

**R3. There is no clean server re-swing.**
- *Problem:* Paper's `swingMainHand()` also reaches the attacker. Cancelling `PlayerArmSwingEvent` hides the swing from others until the server swings. Either way, buffered inputs can double-swing.
- *Fix:* the game is solo (DECISIONS 2026-10-07), so default to this:
  - Never cancel the arm-swing broadcast.
  - Never re-swing a left-click move.
  - The server swings only for moves that have no client swing: off-hand attack, the parry gesture, the riposte hit and the plunge landing.
  - S3 shrinks to "does `swingOffHand()` reach the player and obey the restart rule". The two-client half moves to M6.

**R4. S7 is already known, so it is not a spike.**
- *Problem:* `setCooldown(ItemStack, 30)` uses the stack's cooldown group, and without USE_COOLDOWN the group is the item type. For FLINT that means every melee weapon and every catalyst, plus rings (Rings.java:171) and the master key (MasterKey.java:36). The fallback "clearActiveItem every tick" makes the guard flicker back up every 4 ticks (client `rightClickDelay`).
- *Fix (P2a):*
  - Give every BLOCKS_ATTACKS item `USE_COOLDOWN{seconds 0.05, group souls:guard/<id>}`. The seconds only apply after `finishUsingItem`, which a guard never reaches.
  - Raise `WEAPON_FMT`.
  - `guard_break.js` asserts the group in the `set_cooldown` packet.

**R5. Delivering a queued hit knocks the player back.**
- *Problem:* `player.damage(amt, generic, causing=attacker)` applies vanilla knockback (0.4). Only Roll's i-frames cancel knockback today (Roll.java:583).
- *Fix:* cancel `EntityKnockbackEvent` for the victim while the queue's `resolving` marker is set. Only P4's stagger moves the player.

**R6. Teleporting a foe with a passenger fails silently.**
- *Problem:* Paper refuses to teleport an entity with passengers unless `TeleportFlag.EntityState.RETAIN_PASSENGERS` is passed. P8's marker is a passenger, and P3 (riposte pull) and P5 (void return, leash) teleport foes.
- *Fix:* P1b adds `Foes.teleport(foe, loc)`, which always passes the flag. Nobody calls `teleport` on a foe directly.

**R7. Plugin entities disappear when their chunk unloads.**
- *Problem:* non-persistent entities are dropped on chunk unload and nothing recreates them (TestBonfire.java:20-22, review T20; 1.21.11 has no spawn chunks). Dummies, the post and the Interaction lever from DESIGN §2.3.8 would all silently disappear.
- *Fix:*
  - The lever is a lever block read through `RIGHT_CLICK_BLOCK`, as TestBonfire does.
  - `Foes` drops dead entries on `EntityRemoveFromWorldEvent`.
  - The Dojo tick re-ensures dummies and the post while a player is within 32 blocks.
  - A wave whose foes vanished ends with `WAVE_ABORT`.

**R8. Spawned mobs come out randomised.**
- *Problem:* `world.spawn(loc, cls, consumer)` (as in TestCommands.java:659) runs finalizeSpawn:
  - 5% babies, random armour, chicken jockeys, and a vindicator iron axe;
  - an equipment drop chance of 0.085, so the elite could drop a real `redin_guard_sword`;
  - zombie ambient moans, which act as fake audio cues.
- *Fix:*
  - Spawn with `spawn(loc, cls, false /*randomizeData*/, consumer)`.
  - Call `setAdult()` and set every drop chance to 0.
  - Call `setSilent(true)`; our own sounds replace vanilla ones.
  - For raiders, call `setCanJoinRaid(false)` and `setPatrolLeader(false)`.

**R9. Vanilla body poses hide or override what we need.**
- *Problem:* the vindicator's default CROSSED arm pose hides its held item unless it is aggressive. Zombie and husk models always hold their arms forward, so S9 (shield pose) will most likely fail.
- *Fix:* the elite stays `setAggressive(true)` while engaged. The shield mob's default is "no pose" (S9's fallback).

**R10. The bow threshold compares the wrong number.**
- *Problem:* `EntityShootBowEvent.getForce()` is arrow speed (power × 3, range 0–3). Skyblock divides it by 3 (WeaponListener.java:205). A cancelled shot also leaves the client's predicted arrow count wrong.
- *Fix:* cancel when `getForce()/3 < min-force`, and call `p.updateInventory()` on the next tick, as skyblock does at :213-215.

**R11. Arrows bounce off foes.**
- *Problem:* FoeBody cancels all damage to foes, so a vanilla arrow bounces off.
- *Fix:* in `ProjectileHitEvent` on a foe, cancel the event and remove the arrow, then call `Foes.hit`. Also return arrows that are removed in the world (despawn or void), not only arrows that land.

**R12. The client drops left clicks for 10 ticks after an air swing (`missTime`).**
- *Problem:* `accept-before 6` only applies after an entity or block click. Mineflayer has no `missTime`, so `attacks.js` proves the server rule but not how it feels.
- *Fix:* keep the rule. Add a real-client check, and list it as a known feel limit.

**R13. Heavy, running and charged moves show the light swing.**
- *Problem:* `SWING_ANIMATION` is per item, and the client picks it at click time. DESIGN §3.6 also requires a per-player DEX speed tier in the item fingerprint (§9.8), which the plan leaves out. Without it, every swing stays at DEX-10 length.
- *Fix:* P1a writes a DEX tier into the stack, and WeaponRefresh compares it, so a rewrite happens only on DEX change. The heavy-visual mismatch is accepted for M1 and listed as Q7.

**R14. Holding F is under-specified.**
- *Problem:* OS key repeat starts after about 10–13 ticks, then repeats every 1–2 ticks.
- *Fix:*
  - Measure `repeat-min` from the last *received* F, not the last accepted one.
  - A held F then gives the first press plus one press at the OS delay, and nothing after.
  - Document this. S2 measures the delay.

**R15. DESIGN §12 says to copy skyblock `vfx/Footprint` and `Telegraphable` as they are, and §13 lists a `Footprint` JUnit.**
- *Problem:* the plan writes its own cone and line shapes and has no FootprintTest.
- *Fix:*
  - P1-0 copies `Footprint`. `HitQuery` becomes Footprint plus the hitbox-edge distance, and P2b builds `EnemyMove` shapes on it.
  - Add `FootprintTest`.

### B. Missing requirements

**R16.** The per-DEX swing tier (R13). DESIGN §3.6 asks for it.

**R17. Drinking or casting during attack startup or active (§2.3.6).**
- Estus is M3 (DESIGN §14 M3 row) and spells are M5, so drinking does not exist in M1.
- Implement the general rule in InputRouter now (`setUseItemInHand(DENY)` for consumables during startup or active) and test it with a vanilla potion.
- P4's "cancels drink" and the S5 "while drinking" check use the potion stand-in.

**R18. Input gating is missing.**
- Inputs must be ignored when the player has no origin, is not `Stamina.fighting`, is outside our worlds, or is dead.
- Moves must be refused (`MOVE_DENY why=state`) in a vehicle, in water, while climbing or gliding, staggered, guard-broken or riposting.
- A left click with a non-melee main hand (bow, shield, catalyst, empty) gives `MOVE_DENY why=weapon`.

**R19.** The brain's target filter must skip players with no origin and non-fighting players. `PvpGuard.onTarget` only covers vanilla targeting.

**R20. Content-file upgrades would clobber the user's tuning.**
- *Problem:* `Content` extracts a file only when it is absent, and a `CONTENT_VERSION` bump moves the old file aside (Content.java:17, 53-66). The user tunes `moves.yml` and `enemies.yml` in the dojo, so later packages could either not change those files or would throw away the tuning.
- *Fix:*
  - Both readers fall back key by key to the jar copy, the same way Config.java:404-409 does.
  - Additions never bump the version.

**R21. Several values have two sources of truth.**
- Bow stamina and poise appear in a `moves.yml` comment and in `combat.bow`.
- Dummy respawn appears in `enemies.yml` and `dojo.dummy-respawn`.
- The dojo has both `world.dojo` and a top-level `dojo`.
- Each value gets one owner.

**R22. The parrying dagger AR.**
- "AR 40" must come from `weapons.yml` `attack: 40` through `DamageCalc.ar`: STR applies, one-handed (DECISIONS 2026-10-10, plain gear).

**R23.** `Foes.hit` and queue resolution stamp `lastCombatTick` and `lastHurtTick` in one place. Rest refusal, OffhandLock and P7's arrows then get them for free.

**R24. `gripcheck` as written is a tautology.**
- *Problem:* it checks that the JSON equals `compose(...)`, so a wrong `compose` still passes.
- *Fix:* check invariants against the raw vanilla jar JSON:
  - our grip (8,8,8) lands on the arm-space point of vanilla's g_v;
  - +Y lands on vanilla's sprite diagonal.
  
  Also add probe models built from vanilla sprites through P⁻¹ (P is the grip pre-transform from P0's method). In the real client a probe must overlay vanilla with about 0 px of difference.

**R25.** Master key and rings already use `item/generated`, the vanilla `trial_key` precedent. P0 should list them as "already vanilla" so nobody touches them.

### C. Ordering and scope that contradict DECISIONS or DESIGN

**R26. M1 starts before the AI-tells workflow has finished.**
- *Problem:* DECISIONS 2026-10-11 says "AI 티 고치기가 끝난 뒤 바로 들어간다", and the user said "끝나면".
- *Fix:*
  - Only P0 (grip) may start now. It is pack-only, and its DESIGN.md edits wait for the merge.
  - PS and P1 onward start after the merge.
  - The lang freeze then ends. Each package adds its own ko and en keys in its own block, and P9 only sweeps.

**R27. PvP guard, parry and crits belong to M6.**
- *Problem:* P9 sends PvP through the queue with guard, but the DESIGN §14 M6 row puts "PvP 켬의 막기·패링·치명타" in M6.
- *Fix:* in M1, PvP keeps P1's direct `player_skill` path plus roll i-frames. PvP arrows are unchanged.

**R28. Spikes are scattered across the implementing packages.**
- *Problem:* S1 decides P6, S2 decides P3 and S5 decides P2.
- *Fix:* move them to a PS lane that runs first. S7 is deleted (R4) and S3 is reduced (R3).

**R29. P6's plunge test needs P5's ledge, but P5 runs in parallel.**
- *Fix:* use the existing TestRoom ledge, which has a 6-block drop (TestRoom.java:34).

### D. Packages too big for one agent

**R30. Split these packages.**
- P1a has about 20 files, 8 JUnit classes, an 11-scenario bot and 4 real-client spikes. Split P1 into:
  - P1-0, a contract commit;
  - P1a, the moves core;
  - P1b, foes and the dojo;
  - P1c, roll integration and feel.
- Split P2 into P2a (queue and guard) and P2b (post, brain and telegraph). P2b runs in parallel once P2a's API commit lands.
- Split P5 into P5a (brain and enemies) and P5b (arena, waves and rest refusal).

### E. File-ownership overlaps

**R31.** P1a and P1b both need `Keys`, `Content`, `Config`, `Souls.java`, `DamageCalc.toFoe`, `Hit` and `CombatState`. The P1-0 contract commit lands all of them first.

**R32.** `CombatTestCommands` would be edited in parallel by P5 and P6, and by P7 and P8. Fix: P1-0 makes it a dispatcher, and each package adds its own `cmd/test/*.java`.

**R33. More unlisted files:**
- `DeathFlow` reset is edited by 6 packages. Fix: P1-0 adds `combat/CombatReset` (quit, death, world change, disable), and packages register in their own files.
- `Tumble.java` (P1) and `TestCommands.warn` (P2) were missing from the ownership lists.

**R34. Shared CPU.**
- *Problem:* parallel lanes running llvmpipe clients and timing bots starve the CPU, which makes tick-timing gates and `/souls perf` flaky.
- *Fix:* one host lock covers real-client sessions, lag runs and perf.

### F. Tests that cannot observe the behaviour

**R35. Tick-exact boundaries in bots jitter by ±1 tick.**
- This covers recovery−6/−7, R=C−7/C−8 and C+d+1.
- *Fix:* exact boundaries go in JUnit with a fake clock. Bots check the rule against the server-logged offset (`PARRY r=`, `WINDUP c=`) and retry until each boundary offset has been sampled.

**R36. Fake-swing tests and the off-hand bot pass trivially.**
- *Problem:* the fake-swing tests ("Q and a right click give no MOVE") are trivial because mineflayer sends no swing after a drop or use.
- *Fix:*
  - Fake-swing tests send the vanilla pair: drop or `use_item`, then `arm_animation`.
  - P6's off-hand bot sends `use_item` hand 0, then hand 1, and asserts exactly one MOVE.
  - The P1 "Interaction left click" test is deleted, because the plugin has no Interaction entity.

**R37. Hyper armour and knockdown cannot be timed from a bot.**
- *Fix:* add `/soulstest queue hit at-move <k>`, which lands a PendingHit at move start + k.

---

