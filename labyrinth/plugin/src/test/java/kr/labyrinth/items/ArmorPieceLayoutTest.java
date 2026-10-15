package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import kr.labyrinth.items.ArmorPieceLayout.BodyState;
import kr.labyrinth.items.ArmorPieceLayout.Part;
import kr.labyrinth.items.ArmorPieceLayout.Placement;
import kr.labyrinth.items.ArmorPieceLayout.Stance;
import org.junit.jupiter.api.Test;

/** 어깨·등 장식 배치: 자세 판정 · 표 값이 플레이어 모델 치수에서 나온 값과 같은지 · 숨김 · 토글 인자. */
class ArmorPieceLayoutTest {

    private static final double EPS = 1e-6;
    private static final double PX = 0.9375 / 16.0;

    private static BodyState state(boolean dead, boolean spec, boolean invis, boolean vehicle, boolean sleep, boolean glide,
                                   boolean swim, boolean riptide, boolean crouch, boolean other) {
        return new BodyState(dead, spec, invis, vehicle, sleep, glide, swim, riptide, crouch, other);
    }

    @Test
    void stanceFromBodyState() {
        assertEquals(Stance.STAND, ArmorPieceLayout.stance(BodyState.STANDING));
        assertEquals(Stance.SNEAK, ArmorPieceLayout.stance(state(false, false, false, false, false, false, false, false, true, false)));
        // 사망·관전 = 제거
        assertEquals(Stance.NONE, ArmorPieceLayout.stance(state(true, false, false, false, false, false, false, false, false, false)));
        assertEquals(Stance.NONE, ArmorPieceLayout.stance(state(false, true, false, false, false, false, false, false, true, false)));
        assertEquals(Stance.NONE, ArmorPieceLayout.stance(null));
        // 숨김: 투명 · 탈것 · 잠 · 활공 · 헤엄 · 급류 · 그 밖의 자세 (웅크림보다 우선)
        boolean[][] hidden = {
                {false, false, true, false, false, false, false, false, true, false},
                {false, false, false, true, false, false, false, false, false, false},
                {false, false, false, false, true, false, false, false, false, false},
                {false, false, false, false, false, true, false, false, false, false},
                {false, false, false, false, false, false, true, false, false, false},
                {false, false, false, false, false, false, false, true, false, false},
                {false, false, false, false, false, false, false, false, false, true},
        };
        for (boolean[] h : hidden) {
            assertEquals(Stance.HIDDEN, ArmorPieceLayout.stance(state(h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], h[8], h[9])));
        }
    }

    @Test
    void tableMatchesPlayerModelGeometry() {
        // 서기: 좌석 1.8, 어깨 = 팔 회전축 y 22px · x ±6px, 등 = 목 y 24px
        Placement l = ArmorPieceLayout.place(Part.SHOULDER_L, Stance.STAND, 1.0);
        Placement r = ArmorPieceLayout.place(Part.SHOULDER_R, Stance.STAND, 1.0);
        Placement b = ArmorPieceLayout.place(Part.BACK, Stance.STAND, 1.0);
        assertEquals(6 * PX, l.x(), EPS);
        assertEquals(-6 * PX, r.x(), EPS);
        assertEquals(22 * PX - 1.8, l.y(), EPS);
        assertEquals(l.y(), r.y(), EPS);
        assertEquals(24 * PX - 1.8, b.y(), EPS);
        assertEquals(0, b.x(), EPS);
        for (Placement p : new Placement[] {l, r, b}) {
            assertEquals(0, p.z(), EPS);
            assertEquals(0, p.pitch(), EPS);
            assertEquals(ArmorPieceLayout.PIXEL, p.scale(), EPS);
            assertTrue(p.visible());
        }
        // 웅크리기: 좌석 1.5, 피벗 3.2px 내려감 + 렌더 오프셋 −2/16, 팔 0.4 rad · 몸통 0.5 rad
        Placement sl = ArmorPieceLayout.place(Part.SHOULDER_L, Stance.SNEAK, 1.0);
        Placement sb = ArmorPieceLayout.place(Part.BACK, Stance.SNEAK, 1.0);
        assertEquals((22 - 3.2) * PX - 2.0 / 16 - 1.5, sl.y(), EPS);
        assertEquals((24 - 3.2) * PX - 2.0 / 16 - 1.5, sb.y(), EPS);
        assertEquals(6 * PX, sl.x(), EPS);
        assertEquals(ArmorPieceLayout.CROUCH_ARM_PITCH, sl.pitch(), EPS);
        assertEquals(ArmorPieceLayout.CROUCH_BODY_PITCH, sb.pitch(), EPS);
        assertEquals(ArmorPieceLayout.place(Part.SHOULDER_R, Stance.SNEAK, 1.0).pitch(), sl.pitch(), EPS);
        // 웅크리는 순간(좌석은 클라이언트에서 바로 0.3 내려가고 서버 Transformation 은 1~2틱 늦게 온다) 장식 높이 차 < 0.02 블록
        assertTrue(Math.abs(l.y() - sl.y()) < 0.02);
        assertTrue(Math.abs(b.y() - sb.y()) < 0.02);
    }

    @Test
    void hiddenAndNoneHaveZeroScale() {
        for (Part part : Part.values()) {
            for (Stance s : new Stance[] {Stance.HIDDEN, Stance.NONE}) {
                Placement p = ArmorPieceLayout.place(part, s, 1.0);
                assertFalse(p.visible(), part + " " + s);
                assertEquals(0, p.pitch(), EPS);
                Placement stand = ArmorPieceLayout.place(part, Stance.STAND, 1.0);
                assertEquals(stand.y(), p.y(), EPS, "숨겨도 자리는 그대로 (다시 보일 때 튀지 않게)");
            }
        }
    }

    @Test
    void bodyScaleMultipliesOffsetsAndSize() {
        Placement one = ArmorPieceLayout.place(Part.BACK, Stance.SNEAK, 1.0);
        Placement two = ArmorPieceLayout.place(Part.BACK, Stance.SNEAK, 2.0);
        assertEquals(one.y() * 2, two.y(), EPS);
        assertEquals(one.scale() * 2, two.scale(), EPS);
        assertEquals(one.pitch(), two.pitch(), EPS);
        // 이상한 배율은 1 로
        assertEquals(one.y(), ArmorPieceLayout.place(Part.BACK, Stance.SNEAK, Double.NaN).y(), EPS);
        assertEquals(one.y(), ArmorPieceLayout.place(Part.BACK, Stance.SNEAK, 0).y(), EPS);
    }

    @Test
    void yawWrapAndThreshold() {
        assertEquals(20f, ArmorPieceLayout.yawDelta(350f, 10f), 1e-4);
        assertEquals(-20f, ArmorPieceLayout.yawDelta(10f, -10f), 1e-4);
        assertEquals(-20f, ArmorPieceLayout.yawDelta(-170f, 170f), 1e-4);
        assertFalse(ArmorPieceLayout.yawChanged(90f, 90.3f));
        assertTrue(ArmorPieceLayout.yawChanged(179.5f, -179.0f));
        assertTrue(ArmorPieceLayout.yawChanged(0f, 45f));
    }

    // ── 몸 yaw (BodyYaw) ── MC yaw: 0 = +Z(남) 를 봄, 90 = −X(서). 보는 방향 이동 = (−sin yaw, cos yaw), 왼쪽 = +X (yaw 0 일 때).

    private static double[] step(double x, double z, float yawDeg, double dist) {
        double a = Math.toRadians(yawDeg);
        return new double[] {x - Math.sin(a) * dist, z + Math.cos(a) * dist};
    }

    @Test
    void bodyStaysPutWhileStandingAndOnlyFollowsTheHeadPast50() {
        ArmorPieceLayout.BodyYaw b = new ArmorPieceLayout.BodyYaw(0f);
        for (int i = 0; i < 20; i++) b.tick(0, 0, 40f, false);
        assertEquals(0f, b.body(), 1e-4, "제자리에서 머리 40° — 몸은 그대로");
        for (int i = 0; i < 20; i++) b.tick(0, 0, 80f, false);
        assertEquals(30f, b.body(), 1e-3, "머리 80° — 몸이 50° 차이까지만 끌려온다");
        b = new ArmorPieceLayout.BodyYaw(0f);
        b.tick(0, 0, 30f, true);
        assertEquals(15f, b.body(), 1e-3, "막는 중에는 15°");
    }

    @Test
    void headTurned40ThenWalkingForwardConvergesToTheLookDirection() {
        ArmorPieceLayout.BodyYaw b = new ArmorPieceLayout.BodyYaw(0f);
        double x = 0, z = 0;
        b.tick(x, z, 40f, false);
        assertEquals(0f, b.body(), 1e-4);
        for (int i = 0; i < 10; i++) {
            double[] n = step(x, z, 40f, 0.216);     // 걷기 0.216 블록/틱
            x = n[0];
            z = n[1];
            b.tick(x, z, 40f, false);
        }
        assertEquals(40f, b.body(), 1.5f, "10틱 걸으면 몸이 보는 방향으로 (0.7^10 ≈ 3%)");
        // 서버 getBodyYaw 처럼 이동을 무시하면 0° 에 멈춰 있었을 것 → 장식이 몸통보다 40° 틀어졌다
    }

    @Test
    void strafingTwistsTheBodyToTheHeadLimit() {
        ArmorPieceLayout.BodyYaw b = new ArmorPieceLayout.BodyYaw(0f);
        double x = 0;
        for (int i = 0; i < 20; i++) b.tick(x += 0.2, 0, 0f, false);     // yaw 0 에서 왼쪽(+X)으로 옆걸음
        assertEquals(-50f, b.body(), 1e-3, "왼쪽 옆걸음 → 몸 = yaw − 50");
        b = new ArmorPieceLayout.BodyYaw(0f);
        x = 0;
        for (int i = 0; i < 20; i++) b.tick(x -= 0.2, 0, 0f, false);     // 오른쪽(−X)
        assertEquals(50f, b.body(), 1e-3, "오른쪽 옆걸음 → 몸 = yaw + 50");
        // 앞으로 대각선(왼쪽 앞) → 몸 = 이동 방향 (yaw − 45)
        b = new ArmorPieceLayout.BodyYaw(0f);
        x = 0;
        double z = 0;
        for (int i = 0; i < 30; i++) b.tick(x += 0.15, z += 0.15, 0f, false);
        assertEquals(-45f, b.body(), 0.5f);
    }

    @Test
    void walkingBackwardsKeepsFacingForwardAndSwingSnapsToTheLook() {
        ArmorPieceLayout.BodyYaw b = new ArmorPieceLayout.BodyYaw(10f);
        double z = 0;
        for (int i = 0; i < 20; i++) b.tick(0, z -= 0.2, 0f, false);     // yaw 0 에서 뒷걸음(−Z)
        assertEquals(0f, b.body(), 0.1f, "뒷걸음: 몸은 반대 방향(=앞)을 본다");
        b = new ArmorPieceLayout.BodyYaw(0f);
        b.tick(0, 0, 40f, false);
        b.swing();
        for (int i = 0; i < ArmorPieceLayout.BodyYaw.SWING_TICKS; i++) b.tick(0, 0, 40f, false);
        assertEquals(40f, b.body(), 40f * 0.13f, "휘두르는 동안 보는 방향으로");
        float after = b.body();
        for (int i = 0; i < 10; i++) b.tick(0, 0, 40f, false);
        assertEquals(after, b.body(), 1e-4, "휘두르기가 끝나면 그 자리에 멈춤");
    }

    @Test
    void teleportResetsToTheLookDirectionAndYawWraps() {
        ArmorPieceLayout.BodyYaw b = new ArmorPieceLayout.BodyYaw(0f);
        b.tick(0, 0, 30f, false);
        b.tick(100, 50, 170f, false);
        assertEquals(170f, b.body(), 1e-4, "한 틱에 4블록 넘게 = 순간이동 → 몸 = 보는 방향");
        // −180/180 경계를 넘어 걸어도 반대로 한 바퀴 돌지 않는다
        b = new ArmorPieceLayout.BodyYaw(175f);
        double x = 100, z = 50;
        b.tick(x, z, -175f, false);
        for (int i = 0; i < 15; i++) {
            double[] n = step(x, z, -175f, 0.2);
            x = n[0];
            z = n[1];
            b.tick(x, z, -175f, false);
        }
        assertEquals(0f, ArmorPieceLayout.yawDelta(-175f, b.body()), 0.5f);
        assertTrue(b.body() >= -180f && b.body() < 180f);
    }

    @Test
    void toggleArgumentsAndStoredValue() {
        assertEquals(Boolean.TRUE, ArmorPieceLayout.parseToggle("켜기"));
        assertEquals(Boolean.FALSE, ArmorPieceLayout.parseToggle("끄기"));
        assertEquals(Boolean.TRUE, ArmorPieceLayout.parseToggle(" ON "));
        assertEquals(Boolean.FALSE, ArmorPieceLayout.parseToggle("off"));
        assertNull(ArmorPieceLayout.parseToggle("뭐"));
        assertNull(ArmorPieceLayout.parseToggle(null));
        assertTrue(ArmorPieceLayout.enabledFor(null), "기록이 없으면 켜짐");
        assertTrue(ArmorPieceLayout.enabledFor(true));
        assertFalse(ArmorPieceLayout.enabledFor(false));
        assertFalse(ArmorPieceLayout.enabledFor("false"));
        assertTrue(ArmorPieceLayout.enabledFor(3));
        // 내화면: 기록이 없으면 꺼짐
        assertFalse(ArmorPieceLayout.selfViewFor(null));
        assertTrue(ArmorPieceLayout.selfViewFor(true));
        assertTrue(ArmorPieceLayout.selfViewFor("true"));
        assertFalse(ArmorPieceLayout.selfViewFor("off"));
        assertFalse(ArmorPieceLayout.selfViewFor(1));
    }

    @Test
    void modelPathsAreLowercaseIds() {
        assertEquals("armor_piece/emberforged/shoulder_l", ArmorPieceLayout.modelPath("Emberforged", Part.SHOULDER_L));
        assertEquals("armor_piece/silkweaver/back", ArmorPieceLayout.modelPath("silkweaver", Part.BACK));
        for (Part p : Part.values()) assertTrue(p.id().matches("[a-z_]+"));
    }

    /** 리소스팩 미리보기가 읽는 @layout-table 줄이 6개(부위 3 × 서기·웅크리기) 그대로 있는가. */
    @Test
    void layoutTableStaysParseableForThePackPreview() throws Exception {
        String src = Files.readString(Path.of("src/main/java/kr/labyrinth/items/ArmorPieceLayout.java"));
        int a = src.indexOf("// @layout-table");
        int b = src.indexOf("// @layout-end");
        assertTrue(a > 0 && b > a, "@layout-table … @layout-end 표시");
        Matcher m = Pattern.compile("row\\(Part\\.(\\w+), Stance\\.(\\w+), (-?[\\d.]+)f, (-?[\\d.]+)f, (-?[\\d.]+)f, (-?[\\d.]+)f\\)")
                .matcher(src.substring(a, b));
        int n = 0;
        while (m.find()) {
            Placement p = ArmorPieceLayout.place(Part.valueOf(m.group(1)), Stance.valueOf(m.group(2)), 1.0);
            assertEquals(Float.parseFloat(m.group(3)), p.x(), EPS);
            assertEquals(Float.parseFloat(m.group(4)), p.y(), EPS);
            assertEquals(Float.parseFloat(m.group(6)), p.pitch(), EPS);
            n++;
        }
        assertEquals(Part.values().length * 2, n);
    }
}
