package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.util.List;
import java.util.UUID;
import kr.labyrinth.combat.CasterBoltRules.EntityClick;
import kr.labyrinth.combat.CasterBoltRules.Punch;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 시전 무기 마법탄 규칙 · 설정 · 공격 시계 (0.3.6.1). */
class CasterBoltRulesTest {

    // ── 좌클릭 감지 ──────────────────────────────────────────────────────

    @Test
    void airClickWithCasterIsABolt() {
        assertEquals(Punch.BOLT, CasterBoltRules.punch(true, false, false, true, false), "허공·먼 블록·미궁 벽 — 쏘고 벽에서 멈춤");
    }

    @Test
    void otherSwingsAreNotBolts() {
        assertEquals(Punch.NOT_CASTER, CasterBoltRules.punch(false, false, false, true, false), "칼·활·맨손·요구 미달 지팡이");
        assertEquals(Punch.CONSUMED, CasterBoltRules.punch(true, true, false, true, false), "몹 직접 클릭·다른 기능이 쓴 블록 좌클릭과 같은 틱");
        assertEquals(Punch.BUSY, CasterBoltRules.punch(true, false, true, true, false), "관전·죽음·기절·창 열림");
        assertEquals(Punch.HOLD, CasterBoltRules.punch(true, false, false, false, false), "블록을 누르고 있는 동안의 punch");
        assertEquals(Punch.DIG, CasterBoltRules.punch(true, false, false, true, true), "야생 서바이벌에서 손 닿는 블록, 조준선에 적 없음 = 캐기");
    }

    @Test
    void labyrinthIsSurvivalButNeverDigs() {
        // 미궁은 서바이벌(GameModes.onEnter) 이지만 블록이 깨지지 않는다 — 좌클릭은 언제나 마법탄 (리뷰: 3~4.5칸 몹 뒤 벽에서 클릭이 사라짐)
        assertFalse(CasterBoltRules.canDig(false, true, true), "미궁 서바이벌");
        assertTrue(CasterBoltRules.canDig(false, true, false), "야생·마을 서바이벌");
        assertTrue(CasterBoltRules.canDig(true, false, true), "크리에이티브 (관리자)");
        assertFalse(CasterBoltRules.canDig(false, false, false), "어드벤처 광산·관전");
    }

    @Test
    void enemyOnTheLineWinsOverDigging() {
        assertTrue(CasterBoltRules.digs(true, true, false), "손 닿는 블록만 보고 누름 = 캐기");
        assertFalse(CasterBoltRules.digs(true, true, true), "벽 앞 3~4.5칸 몹·작은 몹 뒤 바닥·거미줄 너머 몹 = 마법탄");
        assertFalse(CasterBoltRules.digs(true, false, false), "블록이 손 밖");
        assertFalse(CasterBoltRules.digs(false, true, false), "캘 수 없는 곳");
    }

    @Test
    void holdingABlockDoesNotAutoFire() {
        CasterBoltRules.Press p = new CasterBoltRules.Press();
        p.blockStart(100, true);
        assertTrue(p.punch(100), "블록 좌클릭 시작과 같은 틱 = 새 클릭");
        assertTrue(p.holding());
        int[] gaps = {1, 1, 2, 1, 1, 3, 1, 2, 1, 1, 1, 2}; // 실서버: 틱마다 오지만 네트워크로 1~3틱 끊김 (리뷰 반영 1차 실서버에서 4발 나갔음)
        int t = 100;
        for (int g : gaps) {
            t += g;
            assertFalse(p.punch(t), "누르고 있는 동안의 punch (" + t + ")");
        }
        p.release(); // 놓음 = 클라이언트 ABORT → BlockDamageAbortEvent
        assertTrue(p.punch(t + 2), "놓은 뒤 허공 클릭은 바로 새 클릭");
        p.blockStart(150, true);
        assertTrue(p.punch(151), "블록 시작과 punch 가 틱 경계에 걸려도 새 클릭");
        assertFalse(p.punch(152));
        p.blockStart(160, true); // 누른 채 다른 블록으로 / 다 캐서 다시 시작 — 그 시작은 새 클릭 하나
        assertTrue(p.punch(160));
        assertFalse(p.punch(161));
        assertTrue(p.punch(161 + CasterBoltRules.Press.HOLD_GAP + 1), "놓았다는 알림을 놓쳐도 0.5초 끊기면 새 클릭");
    }

    @Test
    void airClicksAreAlwaysFresh() {
        CasterBoltRules.Press p = new CasterBoltRules.Press();
        // 클라이언트가 몹을 손 밖으로 본 클릭 (블록 시작 없이 punch 만) — 빠르게 마구 눌러도 모두 새 클릭
        for (int t = 0; t < 40; t += 2) assertTrue(p.punch(t), "허공 " + t);
        for (int t = 40; t < 60; t++) assertTrue(p.punch(t), "블록 시작 없는 punch 는 1틱 간격이어도 새 클릭 " + t);
        p.blockStart(70, false); // 어드벤처: 블록을 캐지 않으므로 누르는 중이 되지 않는다
        assertTrue(p.punch(70));
        assertFalse(p.holding());
        assertTrue(p.punch(72), "어드벤처 블록 클릭 뒤 허공 클릭");
        p.blockStart(80, true); // 서바이벌: 바로 깨지는 풀 — 깨짐이 punch 보다 먼저 온다
        p.release();
        assertTrue(p.punch(80));
        assertFalse(p.holding(), "이미 깨진 블록이면 누르는 중이 아님");
        assertTrue(p.punch(82), "그 뒤 허공 연타는 새 클릭");
    }

    @Test
    void consumedWindowIsThisTickAndTheNext() {
        assertTrue(CasterBoltRules.consumed(100, 100));
        assertTrue(CasterBoltRules.consumed(100, 101), "패킷이 틱 경계에 걸려도 한 번으로");
        assertFalse(CasterBoltRules.consumed(100, 102));
        assertFalse(CasterBoltRules.consumed(100, 99));
    }

    @Test
    void entityClickAndMeleeConversion() {
        assertEquals(EntityClick.BOLT_STRIKE, CasterBoltRules.entityClick(true, true));
        assertEquals(EntityClick.VANILLA, CasterBoltRules.entityClick(true, false), "동물·주민·갑옷 거치대·액자·NPC·파티원은 바닐라에 맡김");
        assertEquals(EntityClick.VANILLA, CasterBoltRules.entityClick(false, true), "근접 무기는 그대로 휘두르기");
        assertTrue(CasterBoltRules.cancelMeleeDamage(true, true), "시전 무기 근접 피해가 적에게 → 취소 (마법탄과 두 번 맞지 않게)");
        assertFalse(CasterBoltRules.cancelMeleeDamage(true, false));
        assertFalse(CasterBoltRules.cancelMeleeDamage(false, true));
    }

    @Test
    void allyPlayerInFrontDoesNotEatTheClick() {
        assertTrue(CasterBoltRules.throughPlayer(true, true, false, false), "바로 앞 파티원·안전지대 플레이어 → 휘두름이 마법탄 (지나감)");
        assertFalse(CasterBoltRules.throughPlayer(true, true, false, true), "빙결된 동료 풀기처럼 다른 기능이 쓴 클릭");
        assertFalse(CasterBoltRules.throughPlayer(true, true, true, false), "적 플레이어는 직접 한 발 (AttackClock)");
        assertFalse(CasterBoltRules.throughPlayer(true, false, false, false), "NPC·주민·동물·갑옷 거치대는 바닐라 클릭");
        assertFalse(CasterBoltRules.throughPlayer(false, true, false, false), "근접 무기");
    }

    // ── 색 ────────────────────────────────────────────────────────────────

    @Test
    void trailColorPicksTheGlowingAccent() {
        assertEquals(0xD9F27A, CasterBoltRules.trailColor(List.of("#2d3b1a", "#4e3520", "#7a5a34", "#d9f27a", "#fffbd6"), 0),
                "등불 지팡이 — 연두빛 등불");
        assertEquals(0x9FE07A, CasterBoltRules.trailColor(List.of("#1c140c", "#46321e", "#7a5a34", "#c8a878", "#9fe07a"), 0));
        assertEquals(0x90E0F0, CasterBoltRules.trailColor(List.of("#101a22", "#1e3a4a", "#3a7a9a", "#90e0f0", "#f0ffff"), 0),
                "서리 — 어두운 파랑이 아니라 밝은 하늘색");
        assertEquals(0xFFF4D6, CasterBoltRules.trailColor(List.of("#6a5020", "#d9b25a", "#f0d890", "#fff4d6", "#ffffff"), 0),
                "거의 흰색 둘이면 덜 흰 쪽 (옅은 크림빛은 그대로 — 회색이 아님)");
    }

    @Test
    void greyBoltsGetTheirColourBack() {
        // 리뷰: 은빛·잿빛 팔레트의 마법탄이 연기처럼 보임
        int ore = CasterBoltRules.trailColor(List.of("#1a1c22", "#5a3a26", "#8e9094", "#c9ced6", "#f1f4fa"), 0); // 광석 수정 지팡이
        int rime = CasterBoltRules.trailColor(List.of("#16161c", "#34343e", "#6a6a7a", "#c0c4d0", "#ffffff"), 0); // 서리 종 막대
        int silkknot = CasterBoltRules.trailColor(List.of("#1a1622", "#3a3248", "#7a6e8e", "#cfc6e0", "#fbf8ff"), 0);
        for (int c : new int[] {ore, rime, silkknot}) {
            assertTrue(CasterBoltRules.vividness(c) >= 0.2, Integer.toHexString(c));
            assertTrue(CasterBoltRules.value(c) >= 0.75, "밝기는 그대로 " + Integer.toHexString(c));
        }
        assertTrue((ore & 0xFF) > (ore >> 16 & 0xFF), "빛깔 그대로 — 푸르스름한 은빛은 옅은 하늘빛 " + Integer.toHexString(ore));
        assertTrue((silkknot & 0xFF) > (silkknot >> 8 & 0xFF), "보랏빛 회색은 옅은 보라 " + Integer.toHexString(silkknot));
        assertEquals(0xD9B25A, CasterBoltRules.trailColor(List.of("#2a1e14", "#6a5020", "#d9b25a", "#c8c8cc", "#d0d0d4"), 0),
                "밝은 둘이 회색이면 팔레트의 밝고 짙은 색");
        assertEquals(0x808080, CasterBoltRules.saturate(0x808080, 0.3), "빛깔 없는 완전한 회색은 그대로");
        assertEquals(0x90E0F0, CasterBoltRules.saturate(0x90E0F0, 0.3), "이미 짙으면 그대로");
    }

    @Test
    void trailColorFallsBack() {
        assertEquals(0x123456, CasterBoltRules.trailColor(null, 0x123456));
        assertEquals(0x123456, CasterBoltRules.trailColor(List.of(), 0x123456));
        assertEquals(0x00FF00, CasterBoltRules.trailColor(List.of("#00ff00", "nope", "#12"), 0), "못 읽는 색은 건너뜀");
        assertEquals(0xABCDEF, CasterBoltRules.trailColor(List.of("bad"), 0xABCDEF));
        assertEquals(-1, CasterBoltRules.parse("#12345"));
        assertEquals(0xFF00AA, CasterBoltRules.parse(" ff00aa "));
    }

    // ── 설정 ──────────────────────────────────────────────────────────────

    @Test
    void missingBlockMeansDefaults() {
        assertEquals(CasterBoltConfig.DEFAULT, CasterBoltConfig.from(null));
        YamlConfiguration y = new YamlConfiguration();
        y.set("damage_numbers", true); // 예전 config.yml 의 combat 블록 — caster_bolt 없음
        assertEquals(CasterBoltConfig.DEFAULT, CasterBoltConfig.from(y));
        assertFalse(y.contains("caster_bolt"), "읽기만 하고 빈 블록을 만들지 않는다");
        assertTrue(CasterBoltConfig.DEFAULT.enabled());
        assertEquals(16, CasterBoltConfig.DEFAULT.range());
    }

    @Test
    void booleanShorthandAndPartialBlock() throws Exception {
        YamlConfiguration off = new YamlConfiguration();
        off.loadFromString("caster_bolt: false\n");
        assertFalse(CasterBoltConfig.from(off).enabled());
        YamlConfiguration part = new YamlConfiguration();
        part.loadFromString("caster_bolt:\n  range: 12\n  trail: false\n");
        CasterBoltConfig c = CasterBoltConfig.from(part);
        assertTrue(c.enabled());
        assertEquals(12, c.range());
        assertFalse(c.trail());
        assertEquals(2.5, c.speed(), "없는 키는 기본값");
    }

    @Test
    void valuesAreClamped() {
        CasterBoltConfig c = new CasterBoltConfig(true, 999, 0, -1, 99, 99, true, true);
        assertEquals(32, c.range());
        assertEquals(0.5, c.speed());
        assertEquals(0, c.radius());
        assertEquals(3, c.pvpKnockback());
        assertEquals(2, c.pvpDamage());
        assertEquals(0.1, new CasterBoltConfig(true, 16, 2.5, 0.3, 0.6, 0, true, true).pvpDamage());
        assertEquals(16, new CasterBoltConfig(true, Double.NaN, 2.5, 0.3, 0.6, 0.65, true, true).range());
        assertEquals(0.65, new CasterBoltConfig(true, 16, 2.5, 0.3, 0.6, Double.NaN, true, true).pvpDamage());
    }

    @Test
    void pvpDamageIsBelowOne() throws Exception {
        // 1:1 모의 실험 (리뷰 pv_duel, 0.3.6 대비 직업 평균 승률 차이): 1.0 이면 사제 +29 · 비전술사 +18, 0.65 면 ±6~14 (비전술사 보정 1.2 그대로일 때)
        assertEquals(0.65, CasterBoltConfig.DEFAULT.pvpDamage());
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("caster_bolt:\n  pvp_damage: 1.0\n");
        assertEquals(1.0, CasterBoltConfig.from(y).pvpDamage());
    }

    @Test
    void jarConfigMatchesCodeDefaults() throws Exception {
        YamlConfiguration jar = YamlConfiguration.loadConfiguration(new java.io.File("src/main/resources/config.yml"));
        assertEquals(CasterBoltConfig.DEFAULT, CasterBoltConfig.from(jar.getConfigurationSection("combat")),
                "jar 의 config.yml 값 = 키가 없을 때 쓰는 기본값");
    }

    // ── 공격 시계 (근접·활과 같은 시계) ──────────────────────────────────

    private static final long TOL = 50, BUF = 350;

    @Test
    void airClickSpamFiresOncePerInterval() {
        AttackTiming t = new AttackTiming();
        long interval = 950; // 등불 지팡이 0.95초, 민첩 0
        int fired = 0;
        for (long now = 0; now < 5000; now += 50) { // 1초에 20번 누름
            AttackTiming.Result r = t.click(now, interval, TOL, BUF, AttackTiming.AIR, "0:lantern_staff");
            if (r == AttackTiming.Result.ACCEPT) fired++;
            if (t.bufferReady(now)) {
                t.fireBuffered(now, interval, TOL);
                fired++;
            }
        }
        assertEquals(6, fired, "5초에 0·0.9·1.85·2.8·3.75·4.7초 = 6발 (허용 오차 50ms, 더 눌러도 더 안 나감)");
    }

    @Test
    void airClickBufferedNearTheEndAndFiresAtReady() {
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(0, 800, TOL, BUF, AttackTiming.AIR, "w"));
        assertEquals(AttackTiming.Result.EARLY, t.click(300, 800, TOL, BUF, AttackTiming.AIR, "w"));
        assertEquals(AttackTiming.Result.BUFFER, t.click(600, 800, TOL, BUF, AttackTiming.AIR, "w"), "끝 0.35초 안 → 기억");
        assertEquals(AttackTiming.AIR, t.bufferedTarget());
        assertFalse(t.bufferReady(700));
        assertTrue(t.bufferReady(800));
        t.fireBuffered(800, 800, TOL);
        assertEquals(1600, t.nextReady());
    }

    @Test
    void boltAndDirectClickShareOneClock() {
        AttackTiming t = new AttackTiming();
        UUID mob = UUID.randomUUID();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(0, 900, TOL, BUF, AttackTiming.AIR, "w"), "허공 마법탄");
        assertEquals(AttackTiming.Result.EARLY, t.click(100, 900, TOL, BUF, mob, "w"), "바로 몹 클릭 → 막힘 (두 발 아님)");
        assertEquals(AttackTiming.Result.BUFFER, t.click(700, 900, TOL, BUF, mob, "w"));
        assertEquals(mob, t.bufferedTarget(), "새 클릭은 대상만 바꿈 — 허공·몹 어느 쪽이든 한 번");
        t.swap(750, 700, 0.5);
        assertFalse(t.hasBuffer(), "무기를 바꾸면 기억한 클릭은 버림");
    }

    /** 클라이언트가 허공 클릭을 0.5초마다 보낼 때(마구 누름, missTime 10틱) 틱마다 시계를 돌려 평균 주기 (ms). */
    private static double meanCycleWithClientGap(long interval, long buffer) {
        AttackTiming t = new AttackTiming();
        java.util.List<Long> fires = new java.util.ArrayList<>();
        for (long now = 0; now <= 60_000; now += 50) {
            if (now % CasterBoltRules.CLIENT_AIR_CLICK_GAP_MS == 0
                    && t.click(now, interval, TOL, buffer, AttackTiming.AIR, "w") == AttackTiming.Result.ACCEPT) fires.add(now);
            if (t.bufferReady(now)) {
                t.fireBuffered(now, interval, TOL);
                fires.add(now);
            }
        }
        return (fires.get(fires.size() - 1) - fires.get(0)) / (double) (fires.size() - 1);
    }

    @Test
    void airBufferCoversTheClientMissTime() {
        assertEquals(500, CasterBoltRules.airBufferMs(0.35), "기본 0.35초 → 허공은 0.5초");
        assertEquals(700, CasterBoltRules.airBufferMs(0.7), "설정이 더 길면 설정");
        assertEquals(0, CasterBoltRules.airBufferMs(0), "0 = 기억 끔");
        // 시작 지팡이 0.94초 (민첩 2): 기억창 0.35초면 0.5초 클릭이 '너무 이름'으로 버려져 주기 1.0초 — 0.5초면 제 간격
        assertEquals(1000, meanCycleWithClientGap(940, BUF), 1.0, "0.35초 창: 0.94초 지팡이가 1.0초마다");
        assertEquals(940, meanCycleWithClientGap(940, CasterBoltRules.airBufferMs(0.35)), 15.0);
        for (long iv : new long[] {600, 700, 800, 850, 900, 950}) {
            assertEquals(iv, meanCycleWithClientGap(iv, CasterBoltRules.airBufferMs(0.35)), iv * 0.02, "간격 " + iv + "ms");
        }
    }

    @Test
    void airSentinelIsNotARealEntity() {
        assertEquals(new UUID(0, 0), AttackTiming.AIR);
        assertNotEquals(AttackTiming.AIR, UUID.randomUUID());
    }

    // ── 피해 문맥 ─────────────────────────────────────────────────────────

    @Test
    void boltIsABasicAttackOfMagicType() {
        DamageContext c = DamageContext.basic(null, null, 1.0, DamageType.MAGIC).kind(DamageKind.MAGIC).weaponHit(12.5).casterBolt();
        assertTrue(c.isCasterBolt());
        assertTrue(c.hasWeaponHit());
        assertEquals(12.5, c.weaponHit());
        assertEquals(DamageType.MAGIC, c.type());
        assertEquals(DamageKind.MAGIC, c.effectiveKind());
        assertFalse(c.isSkill(), "스킬이 아님 — 스킬 피해 가산·스킬 위력 기준 없음");
        assertNull(c.sourceId(), "출처 없음 = 기본 공격 (고유 효과 '기본 공격' 발동)");
        assertEquals(DamageContext.Base.PER_HIT, c.base());
        assertTrue(c.canCrit(), "치명타 그대로");
        assertFalse(DamageContext.basic(null, null, 1.0, DamageType.MELEE).isCasterBolt());
        assertFalse(DamageContext.basic(null, null, 1.0, DamageType.MELEE).hasWeaponHit());
    }

    @Test
    void rawAmountWithFixedBaseMatchesHeldWeapon() {
        assertEquals(1.0, DamageService.rawAmount(null, 30.0, DamageKind.MAGIC, 1.0), "능력치 없으면 배율 그대로 (예전과 같음)");
    }
}
