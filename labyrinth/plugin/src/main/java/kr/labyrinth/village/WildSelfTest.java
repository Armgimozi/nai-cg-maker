package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Chunk;
import org.bukkit.Difficulty;
import org.bukkit.GameRules;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Cow;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mannequin;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Pig;
import org.bukkit.entity.PigZombie;
import org.bukkit.entity.SpawnCategory;
import org.bukkit.entity.Zombie;
import org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason;
import org.bukkit.event.entity.EntityTransformEvent;

/**
 * {@code /labadmin wild selftest} (0.3.5.1) — 야생 막기 점검. 플레이어 없이:
 * <ul>
 *   <li>inside — 월드 스폰·광장·입구(게이트·config)·NPC(메타·실제 자리)·보호 상자 전부가 마을 경계 안인가</li>
 *   <li>border — wild.border 가 켜져 있으면 지금 바닐라 경계가 마을 경계와 같은가 (관리자 경계면 알림만)</li>
 *   <li>spawns — SpawnReason 전부 × (좀비·소·갑옷 거치대·마네킹) 을 광장에 실제로 소환해 막힘/허용이 규칙({@link WildSpawns})과
 *       같은가. 남은 것은 바로 지운다</li>
 *   <li>plugin_tag — 플러그인 태그가 달린 몹은 NATURAL 이어도 막지 않는가 · existing — 스폰 이유를 제대로 읽는가</li>
 *   <li>sweep — 있던 바닐라 적대 몹(NATURAL)은 치우고, 동물·이름 붙은 몹은 두는가 (태그로 들인 뒤 태그를 떼어 흉내)</li>
 *   <li>dims — 네더·엔드에서는 NATURAL 좀비·소가 막히지 않는가 (막는 것은 주 월드만)</li>
 *   <li>limits — 막는 분류의 자연 스폰 상한이 0 으로 묶였는가 (all = 7분류, monsters = MONSTER, none = 없음)</li>
 *   <li>transform — 광장 40칸 위 공중에 돼지를 띄우고 번개 (좀비 피글린 변신이 막히고 돼지가 남는가 — 번개 소리 한 번).
 *       시험 동안 그 청크에 플러그인 티켓을 걸고 엔티티가 움직이게 된 뒤 번개를 치며, 돼지에게 zap·변신 이벤트가 실제로 왔을 때만 판정한다
 *       (안 왔으면 skip — 번개가 안 맞은 것을 '돼지 그대로'로 잘못 읽지 않게)</li>
 * </ul>
 * 결과 한 줄은 서버 로그에도 남는다.
 */
final class WildSelfTest extends VillageJob {

    private final World world;
    private final WildService wild;
    private final List<String> samples = new ArrayList<>();
    private int exceptions;
    private boolean insideOk, borderOk = true, tagOk, existingOk, sweepOk, dimsOk = true, transformOk = true, limitsOk = true;
    private String inside = "?", border = "?", sweep = "?", dims = "없음", transform = "skip", limits = "?";
    private int spawnChecked, spawnMismatch, spawnBlocked, spawnAllowed;
    private Pig pig;
    private Location pigAt;
    private boolean expectTransformBlocked;
    private Settings.Wild.Spawns transformMode;
    /** 청크가 엔티티를 움직일 때까지 기다린 틱 (-1 = 이미 번개를 침). */
    private int prep = -1;
    private int wait, after;
    private Chunk ticket, pigChunk;

    WildSelfTest(VillageModule module, CommandSender sender, World world) {
        super(module, sender, "야생 자가 진단");
        this.world = world;
        this.wild = module.service().wild();
    }

    private void sample(String s) {
        if (samples.size() < 14) samples.add(s);
    }

    private void error(String where, Throwable t) {
        exceptions++;
        sample("예외 " + where + ": " + t);
        Log.error("[야생 자가 진단] " + where + " 예외", t);
    }

    @Override
    protected void begin() {
        if (wild == null || !wild.active()) {
            exceptions++;
            sample("마을이 없어 야생 막기가 꺼져 있습니다");
            return;
        }
        say("<#c9a2ff>야생 자가 진단 시작</#c9a2ff> <gray>— 경계 · 스폰 " + SpawnReason.values().length + "가지 · 치우기 · 네더·엔드 · 변신");
        try {
            containment();
        } catch (Throwable t) {
            error("경계 안", t);
        }
        wild.selfTest(true);
        try {
            spawns();
        } catch (Throwable t) {
            error("스폰", t);
        }
        try {
            sweep();
        } catch (Throwable t) {
            error("치우기", t);
        }
        try {
            otherDimensions();
        } catch (Throwable t) {
            error("네더·엔드", t);
        } finally {
            wild.selfTest(false);
        }
        try {
            limits();
        } catch (Throwable t) {
            error("스폰 상한", t);
        }
        try {
            startTransform();
        } catch (Throwable t) {
            error("변신", t);
        }
    }

    @Override
    protected String status() { return pig == null ? null : prep >= 0 ? "청크 준비 중" : "번개 기다리는 중"; }

    @Override
    protected boolean tick(Budget b) {
        if (pig != null && prep >= 0) {
            // 티켓을 건 청크가 엔티티를 움직이게 될 때까지 (막 켠 서버는 몇 틱 걸림) — 그래야 번개가 맞는다
            if (pigChunk.getLoadLevel() != Chunk.LoadLevel.ENTITY_TICKING && prep++ < 200) return false;
            prep = -1;
            world.strikeLightning(pigAt);
            return false;
        }
        // 번개가 맞을 때까지 (최대 2초), 맞은 뒤 5틱 더 (좀비 피글린이 생겼는지)
        if (pig != null && !wild.probeHit() && wait++ < 40) return false;
        if (pig != null && wild.probeHit() && after++ < 5) return false;
        if (pig != null) {
            try {
                finishTransform();
            } catch (Throwable t) {
                error("변신 확인", t);
            }
        }
        report();
        return true;
    }

    @Override
    protected void cleanup() {
        if (wild != null) wild.probe(null);
        if (ticket != null) {
            ticket.removePluginChunkTicket(module.plugin());
            ticket = null;
        }
        if (pig != null && pig.isValid()) pig.remove();
        if (pigAt != null) {
            for (Entity e : world.getNearbyEntities(pigAt, 6, 8, 6)) {
                if (e instanceof PigZombie && e.getTicksLived() < 400) e.remove();
            }
        }
    }

    private Location plaza() {
        VillageMeta m = module.service().meta();
        Location at = new Location(world, m.spawn.x(), m.spawn.y(), m.spawn.z());
        world.getChunkAt(at.getBlockX() >> 4, at.getBlockZ() >> 4);
        return at;
    }

    // ── 경계 안 ──────────────────────────────────────────────────────────

    private void containment() {
        VillageMeta m = module.service().meta();
        WildBorder.Square tgt = wild.target();
        Map<String, double[]> pts = new LinkedHashMap<>();
        Location ws = world.getSpawnLocation();
        pts.put("월드 스폰", new double[] {ws.getX(), ws.getZ()});
        if (m.spawn != null) pts.put("광장", new double[] {m.spawn.x(), m.spawn.z()});
        if (m.entrance != null) pts.put("입구 게이트", new double[] {m.entrance.x(), m.entrance.z()});
        Settings.Entrance e = module.services().settings().entrance();
        if (e.isSet() && e.world().equals(world.getName())) pts.put("입구(config)", new double[] {e.x(), e.z()});
        for (Map.Entry<String, VillageMeta.Pos> n : m.npcs.entrySet()) {
            pts.put("NPC " + n.getKey(), new double[] {n.getValue().x(), n.getValue().z()});
        }
        if (module.services().npcs() instanceof kr.labyrinth.mobs.npc.NpcServiceImpl impl) {
            for (Map.Entry<String, Location> n : impl.placed().entrySet()) {
                Location l = n.getValue();
                if (l != null && world.equals(l.getWorld())) pts.put("NPC 자리 " + n.getKey(), new double[] {l.getX(), l.getZ()});
            }
        }
        List<String> out = WildBorder.outside(tgt, pts);
        List<Integer> boxes = WildBorder.boxesOutside(tgt, m.protect);
        insideOk = out.isEmpty() && boxes.isEmpty();
        inside = (insideOk ? "ok" : "bad") + " (점 " + pts.size() + " · 보호 상자 " + m.protect.size() + ")";
        for (String o : out) sample("마을 경계 밖: " + o);
        for (int i : boxes) {
            VillageMeta.Box bx = m.protect.get(i);
            sample("마을 경계 밖 보호 상자 #" + i + " (" + bx.x0() + " " + bx.z0() + " ~ " + bx.x1() + " " + bx.z1() + ")");
        }
        WildBorder.Square cur = wild.current();
        Settings.Wild w = wild.cfg();
        if (!w.border()) {
            border = "off (" + WildBorder.describe(cur) + ")";
            return;
        }
        if (cur.same(tgt)) {
            border = "ours (" + WildBorder.describe(cur) + ")";
            List<String> curOut = WildBorder.outside(cur, pts);
            if (!curOut.isEmpty()) {
                borderOk = false;
                for (String o : curOut) sample("지금 경계 밖: " + o);
            }
        } else if (wild.lastAction() == WildBorder.Action.ADMIN) {
            border = "admin (" + WildBorder.describe(cur) + ")";
            sample("관리자가 정한 경계라 그대로 둠 — 마을 경계로: labadmin wild border apply");
        } else {
            borderOk = false;
            border = "bad (" + WildBorder.describe(cur) + " ≠ " + WildBorder.describe(tgt) + ")";
        }
    }

    // ── 스폰 ─────────────────────────────────────────────────────────────

    private boolean oldBlockAt(Location at) {
        VillageMeta m = module.service().meta();
        double dx = at.getX() - m.center[0], dz = at.getZ() - m.center[2], rr = m.radius + 8;
        return module.blockMobSpawns() && dx * dx + dz * dz <= rr * rr;
    }

    private void spawns() {
        Location at = plaza();
        Settings.Wild.Spawns mode = wild.spawnMode();
        boolean old = oldBlockAt(at);
        List<Class<? extends LivingEntity>> kinds = List.of(Zombie.class, Cow.class, ArmorStand.class, Mannequin.class);
        for (SpawnReason r : SpawnReason.values()) {
            for (Class<? extends LivingEntity> cls : kinds) {
                boolean mob = Mob.class.isAssignableFrom(cls), enemy = Enemy.class.isAssignableFrom(cls);
                boolean expect = WildSpawns.blockSpawn(mode, r, mob, enemy) || old && WildSpawns.oldVillageBlock(r, enemy);
                LivingEntity e;
                try {
                    e = world.spawn(at, cls, r, false, this::quiet);
                } catch (Throwable t) {
                    error("소환 " + cls.getSimpleName() + " " + r, t);
                    continue;
                }
                boolean blocked = e == null || !e.isValid();
                if (e != null && e.isValid()) e.remove();
                spawnChecked++;
                if (blocked) spawnBlocked++;
                else spawnAllowed++;
                if (blocked != expect) {
                    spawnMismatch++;
                    sample(cls.getSimpleName() + " " + r + ": " + (blocked ? "막힘" : "허용") + " / 규칙 " + (expect ? "막음" : "허용"));
                }
            }
        }
        // 플러그인 몹은 NATURAL 이어도 그대로 (마을 둘레 예전 막기도 플러그인 몹은 건드리지 않음)
        Zombie tagged = world.spawn(at, Zombie.class, SpawnReason.NATURAL, false, x -> {
            quiet(x);
            Keys.tagTransient(x, Keys.FX, "wild-selftest");
        });
        tagOk = tagged != null && tagged.isValid();
        if (!tagOk) sample("플러그인 태그 몹이 막힘");
        if (tagged != null && tagged.isValid()) tagged.remove();
        // 이미 있는 몹의 스폰 이유 읽기 (알로 들인 좀비는 치우지 않음)
        Zombie egg = world.spawn(at, Zombie.class, SpawnReason.SPAWNER_EGG, false, this::quiet);
        if (egg != null && egg.isValid()) {
            WildSpawns.Existing x = WildService.existing(egg);
            existingOk = x.reason() == SpawnReason.SPAWNER_EGG && x.enemy() && !x.persistent()
                    && !WildSpawns.removeExisting(Settings.Wild.Spawns.ALL, x);
            if (!existingOk) sample("이미 있는 몹 판정 이상: " + x);
            egg.remove();
        } else {
            sample("알로 들인 좀비가 막힘");
        }
    }

    private void quiet(LivingEntity x) {
        x.setPersistent(false);
        x.setSilent(true);
        x.setAI(false);
        x.setInvulnerable(true);
    }

    /** 플러그인 태그를 달고 NATURAL 로 들인 뒤 태그를 뗀다 — '예전부터 있던 바닐라 몹' 흉내. */
    private <T extends LivingEntity> T fakeNatural(Location at, Class<T> cls, String name) {
        T e = world.spawn(at, cls, SpawnReason.NATURAL, false, x -> {
            quiet(x);
            if (name != null) x.customName(Text.mm(name));
            Keys.tagTransient(x, Keys.FX, "wild-selftest");
        });
        if (e == null || !e.isValid()) return null;
        for (NamespacedKey k : List.copyOf(e.getPersistentDataContainer().getKeys())) {
            if (Keys.NS.equals(k.getNamespace())) e.getPersistentDataContainer().remove(k);
        }
        return e;
    }

    private void sweep() {
        Location at = plaza();
        Settings.Wild.Spawns mode = wild.spawnMode();
        Zombie z = fakeNatural(at, Zombie.class, null);
        Zombie named = fakeNatural(at, Zombie.class, "이름표");
        Cow cow = fakeNatural(at, Cow.class, null);
        List<Entity> all = new ArrayList<>();
        for (Entity e : new Entity[] {z, named, cow}) if (e != null) all.add(e);
        try {
            if (all.size() < 3) {
                sweepOk = false;
                sweep = "bad (시험 몹을 들이지 못함)";
                return;
            }
            int n = wild.sweep(all, false);
            boolean zGone = !z.isValid(), namedKept = named.isValid(), cowKept = cow.isValid();
            boolean expectZ = mode != Settings.Wild.Spawns.NONE;
            sweepOk = zGone == expectZ && namedKept && cowKept && n == (expectZ ? 1 : 0);
            sweep = (sweepOk ? "ok" : "bad") + " (치움 " + n + " · 좀비 " + (zGone ? "치움" : "남음") + " · 이름 붙은 좀비 "
                    + (namedKept ? "남음" : "치움") + " · 소 " + (cowKept ? "남음" : "치움") + ")";
            if (!sweepOk) sample("있던 몹 치우기 이상: " + sweep);
        } finally {
            for (Entity e : all) if (e.isValid()) e.remove();
        }
    }

    // ── 네더 · 엔드 (막지 않음) ───────────────────────────────────────────

    private void otherDimensions() {
        StringBuilder sb = new StringBuilder();
        for (World w : Bukkit.getWorlds()) {
            if (w.equals(world) || module.services().dungeon().isLabyrinthWorld(w)) continue;
            if (w.getEnvironment() != World.Environment.NETHER && w.getEnvironment() != World.Environment.THE_END) continue;
            Location at = w.getSpawnLocation();
            w.getChunkAt(at.getBlockX() >> 4, at.getBlockZ() >> 4);
            int ok = 0, n = 0;
            for (Class<? extends LivingEntity> cls : List.of(Zombie.class, Cow.class)) {
                LivingEntity e = w.spawn(at, cls, SpawnReason.NATURAL, false, this::quiet);
                n++;
                if (e != null && e.isValid()) {
                    ok++;
                    e.remove();
                }
            }
            if (ok != n) {
                dimsOk = false;
                sample(w.getName() + " 에서 NATURAL 스폰이 막힘 (" + ok + "/" + n + " 허용) — 네더·엔드는 막지 않아야 함");
            }
            sb.append(sb.isEmpty() ? "" : " · ").append(w.getName()).append(" 허용 ").append(ok).append('/').append(n);
        }
        dims = (dimsOk ? "ok" : "bad") + " (" + (sb.isEmpty() ? "네더·엔드 월드 없음" : sb) + ")";
    }

    // ── 자연 스폰 상한 ───────────────────────────────────────────────────

    private void limits() {
        Settings.Wild.Spawns mode = wild.spawnMode();
        int want = 0, zero = 0;
        StringBuilder rest = new StringBuilder();
        for (SpawnCategory c : SpawnCategory.values()) {
            if (!WildSpawns.limitCategory(mode, c)) {
                // 막지 않는 분류는 그대로인가 (끈 뒤 되돌렸는가 — 값만 보여 줌, 관리자가 0 으로 정했을 수도 있음)
                if (c != SpawnCategory.MISC) rest.append(' ').append(c.name().toLowerCase(java.util.Locale.ROOT)).append('=').append(world.getSpawnLimit(c));
                continue;
            }
            want++;
            if (world.getSpawnLimit(c) == 0) zero++;
            else sample("자연 스폰 상한이 0 이 아님: " + c + " = " + world.getSpawnLimit(c));
        }
        limitsOk = zero == want;
        limits = (limitsOk ? "ok" : "bad") + " (0 " + zero + "/" + want + (rest.isEmpty() ? "" : " · 나머지" + rest) + ")";
    }

    // ── 변신 (번개) ──────────────────────────────────────────────────────

    private void startTransform() {
        if (world.getDifficulty() == Difficulty.PEACEFUL) {
            transform = "skip (평화로움 — 번개 변신 없음)";
            return;
        }
        Settings.Wild.Spawns mode = wild.spawnMode();
        transformMode = mode;
        expectTransformBlocked = WildSpawns.blockTransform(mode, EntityTransformEvent.TransformReason.LIGHTNING, true, true);
        VillageMeta m = module.service().meta();
        pigAt = new Location(world, m.spawn.x(), Math.min(world.getMaxHeight() - 12, m.spawn.y() + 40), m.spawn.z());
        pig = world.spawn(pigAt, Pig.class, SpawnReason.CUSTOM, false, x -> {
            x.setPersistent(false);
            x.setGravity(false);
            x.setAI(false);
            x.setSilent(true);
        });
        if (pig == null || !pig.isValid()) {
            pig = null;
            transform = "skip (돼지를 소환하지 못함)";
            return;
        }
        // 플레이어가 없으면 청크가 엔티티를 움직이지 않아 번개가 맞지 않는다 — 시험 동안만 플러그인 티켓 (cleanup 에서 뗌).
        // 번개는 청크가 엔티티를 움직이게 된 뒤 tick 에서 친다
        pigChunk = pigAt.getChunk();
        if (pigChunk.addPluginChunkTicket(module.plugin())) ticket = pigChunk;
        wild.probe(pig.getUniqueId());
        prep = 0;
    }

    private void finishTransform() {
        boolean hit = wild.probeHit();
        boolean stillPig = pig.isValid();
        boolean piglin = false;
        for (Entity e : world.getNearbyEntities(pigAt, 6, 8, 6)) if (e instanceof PigZombie && e.getTicksLived() < 400) piglin = true;
        if (!hit) {
            transform = "skip (번개 안 맞음 — 돼지 " + (stillPig ? "그대로" : "사라짐") + ")";
            return;
        }
        if (wild.spawnMode() != transformMode) {
            transform = "skip (시험 중 설정이 바뀜 — reload)";
            return;
        }
        boolean blocked = stillPig && !piglin;
        transformOk = blocked == expectTransformBlocked;
        transform = (transformOk ? "ok" : "bad") + " (번개 → " + (blocked ? "돼지 그대로" : piglin ? "좀비 피글린" : "돼지 사라짐")
                + ", 규칙 " + (expectTransformBlocked ? "막음" : "허용") + ")";
        if (!transformOk) sample("번개 변신이 규칙과 다름");
    }

    // ── 결과 ─────────────────────────────────────────────────────────────

    private void report() {
        Settings.Wild w = wild == null ? Settings.Wild.DEFAULT : wild.cfg();
        String rules = "";
        try {
            rules = " · gamerules spawn_mobs=" + world.getGameRuleValue(GameRules.SPAWN_MOBS) + " spawn_monsters="
                    + world.getGameRuleValue(GameRules.SPAWN_MONSTERS);
        } catch (Throwable t) {
            // 게임 규칙 이름이 다른 판
        }
        String line = "[야생 자가 진단] 결과: 예외 " + exceptions
                + " · inside=" + inside
                + " · border=" + border
                + " · spawns=" + (spawnChecked - spawnMismatch) + "/" + spawnChecked + (spawnMismatch == 0 ? " ok" : " bad")
                + " (막힘 " + spawnBlocked + " · 허용 " + spawnAllowed + ")"
                + " · plugin_tag=" + (tagOk ? "ok" : "bad")
                + " · existing=" + (existingOk ? "ok" : "bad")
                + " · sweep=" + sweep
                + " · dims=" + dims
                + " · limits=" + limits
                + " · transform=" + transform
                + " · 설정 spawns=" + w.spawns().id() + " border=" + w.border() + " margin=" + w.borderMargin()
                + rules;
        boolean pass = exceptions == 0 && insideOk && borderOk && spawnChecked > 0 && spawnMismatch == 0 && tagOk && existingOk
                && sweepOk && dimsOk && transformOk && limitsOk;
        Text.send(sender, (pass ? "<#7fe07f><b>야생 자가 진단 통과</b></#7fe07f>" : "<#ff6b6b><b>야생 자가 진단: 문제 있음</b></#ff6b6b>")
                + " <gray>(" + elapsedSec() + "초)");
        Text.send(sender, "<gray>" + Text.escape(line));
        for (String s : samples) Text.send(sender, "<dark_gray>   - " + Text.escape(s.length() > 200 ? s.substring(0, 200) + "…" : s));
        Log.info(line);
    }
}
