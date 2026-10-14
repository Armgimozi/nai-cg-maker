package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.Collection;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.combat.DamageType;

/**
 * 지하 6층 얼음관의 여제 시린의 순수 규칙 (Bukkit 무관 — 단위 테스트 대상, GDD §7.6).
 * <ul>
 *   <li>빙결 껍질: 직업 역할 → 피해 유형, 인장 규칙(필터·없는 역할 HP ×1.5·솔로 전부 허용), 인장 HP, 시전 시간, 발동 페이즈</li>
 *   <li>동상: 2초 이동 거리 판정</li>
 *   <li>빙창: 3갈래 각도와 방향 회전</li>
 *   <li>영구 동토: 얼릴 타일 수, 얼음판 미끄러짐(이동 관성) 속도 계산</li>
 * </ul>
 * 좌표·방향은 수평 (x, z), 각도는 도.
 */
public final class FrostLogic {

    private FrostLogic() {}

    // ── 빙결 껍질: 역할·인장 ─────────────────────────────────────────────

    /**
     * classes.yml {@code role} → 그 직업이 주로 내는 피해 유형 (GDD §7.6 피해 유형 분류).
     * tank·melee·assassin = 근접, ranged = 원거리, magic·healer = 마법. 직업 없음(null) = 근접(기본 공격).
     * overrides(bosses.yml {@code role_damage}) 가 있으면 그 값이 우선.
     */
    public static DamageType roleDamage(String role, Map<String, String> overrides) {
        String r = role == null ? "" : role.toLowerCase(Locale.ROOT);
        if (overrides != null && overrides.containsKey(r)) {
            DamageType t = DamageType.byId(overrides.get(r), null);
            if (t != null && t != DamageType.TRUE) return t;
        }
        return switch (r) {
            case "ranged" -> DamageType.RANGED;
            case "magic", "healer" -> DamageType.MAGIC;
            default -> DamageType.MELEE;
        };
    }

    /** 파티 직업 역할 목록 → 낼 수 있는 피해 유형 집합. */
    public static Set<DamageType> presentTypes(Collection<String> roles, Map<String, String> overrides) {
        Set<DamageType> out = EnumSet.noneOf(DamageType.class);
        for (String r : roles) out.add(roleDamage(r, overrides));
        return out;
    }

    /**
     * 인장 하나의 규칙.
     * @param type     인장 유형 (근접·원거리·마법)
     * @param filtered true = 그 유형 피해만 받음, false = 모든 피해를 받음
     * @param hpMult   인장 HP 추가 배율 (없는 역할 = missing_role_hp_mult)
     */
    public record SigilRule(DamageType type, boolean filtered, double hpMult) {}

    /**
     * GDD §7.6: 파티에 해당 피해 유형을 낼 직업이 없으면 그 인장은 모든 피해를 받되 HP ×1.5. 솔로는 세 인장 모두 모든 피해 허용
     * (HP 배율 없음). present 가 비어 있으면(직업 정보 없음) 전원 있다고 본다 — 아무도 깰 수 없는 인장이 생기지 않게.
     */
    public static SigilRule sigilRule(DamageType type, Set<DamageType> present, boolean solo, double missingHpMult) {
        if (solo) return new SigilRule(type, false, 1.0);
        if (present == null || present.isEmpty() || present.contains(type)) return new SigilRule(type, true, 1.0);
        return new SigilRule(type, false, Math.max(1.0, missingHpMult));
    }

    /** bosses.yml {@code sigils: [melee, ranged, magic]} → 피해 유형 (잘못된 값·TRUE 는 건너뜀, 비면 기본 3종). */
    public static List<DamageType> sigilTypes(List<String> ids) {
        List<DamageType> out = new ArrayList<>();
        if (ids != null) {
            for (String s : ids) {
                DamageType t = DamageType.byId(s, null);
                if (t != null && t != DamageType.TRUE && !out.contains(t)) out.add(t);
            }
        }
        if (out.isEmpty()) out.addAll(List.of(DamageType.MELEE, DamageType.RANGED, DamageType.MAGIC));
        return out;
    }

    /** 인장 HP = sigil_hp × (1 + sigil_hp_per_member × (n−1)) × 난이도 오브젝트 배율 × 규칙 배율. */
    public static double sigilHp(double base, double perMember, int partySize, double difficultyMult, SigilRule rule) {
        return BossMath.objectHp(base, perMember, partySize) * difficultyMult * (rule == null ? 1.0 : rule.hpMult());
    }

    /** 절대영도 시전 시간(틱): 파티 cast_time, 솔로 solo_cast_time, × 기믹 제한 시간 배율(난이도). 최소 3초. */
    public static int shellCastTicks(double partySeconds, double soloSeconds, boolean solo, double timerMult) {
        double s = (solo ? soloSeconds : partySeconds) * Math.max(0.1, timerMult);
        return (int) Math.max(60, Math.round(s * 20));
    }

    /** trigger_phases 목록에 이 페이즈가 있는가 (YAML 숫자 목록). */
    public static boolean triggersAt(List<?> phases, int phase) {
        if (phases == null) return false;
        for (Object o : phases) {
            if (o instanceof Number n && n.intValue() == phase) return true;
            if (o instanceof String s && s.trim().equals(Integer.toString(phase))) return true;
        }
        return false;
    }

    /** 인장 유형 → 화면 표기 (기호 · 이름 · 받는 공격). */
    public static String sigilName(DamageType t) {
        return switch (t) {
            case MELEE -> "⚔ 붉은 인장";
            case RANGED -> "🏹 초록 인장";
            case MAGIC -> "✦ 보라 인장";
            default -> "인장";
        };
    }

    public static String sigilHint(DamageType t) {
        return switch (t) {
            case MELEE -> "근접 공격·근접 스킬만";
            case RANGED -> "화살·투사체만";
            case MAGIC -> "마법 스킬만";
            default -> "모든 공격";
        };
    }

    // ── 동상 ─────────────────────────────────────────────────────────────

    /** 동상: 지난 판정 이후 수평 이동 거리가 threshold 미만이면 서리 1중첩. 처음(이전 위치 없음 = NaN)은 중첩 없음. */
    public static boolean frostbiteStacks(double movedHorizontal, double threshold) {
        if (Double.isNaN(movedHorizontal)) return false;
        return movedHorizontal < threshold;
    }

    // ── 빙창 ─────────────────────────────────────────────────────────────

    /** count 갈래의 각도 오프셋(도) — 가운데를 0 으로 spread 간격. 1 = [0], 3·35 = [−35, 0, 35], 2·35 = [−17.5, 17.5]. */
    public static double[] spreadOffsets(int count, double spreadDeg) {
        int n = Math.max(1, count);
        double[] out = new double[n];
        for (int i = 0; i < n; i++) out[i] = (i - (n - 1) / 2.0) * spreadDeg;
        return out;
    }

    /** 수평 방향 (x, z) 를 deg 만큼 회전 (x→z 방향이 +). @return {x, z} 정규화 */
    public static double[] rotate(double x, double z, double deg) {
        double a = Math.toRadians(deg);
        double c = Math.cos(a), s = Math.sin(a);
        double rx = x * c - z * s, rz = x * s + z * c;
        double len = Math.hypot(rx, rz);
        return len < 1e-9 ? new double[]{0, 1} : new double[]{rx / len, rz / len};
    }

    // ── 영구 동토 ────────────────────────────────────────────────────────

    /** 얼릴 타일 수 = round(유효 타일 × coverage), 유효 타일이 있으면 최소 1, 최대 전부. */
    public static int tilesToFreeze(int validTiles, double coverage) {
        if (validTiles <= 0) return 0;
        int n = (int) Math.round(validTiles * Math.max(0, Math.min(1, coverage)));
        return Math.max(1, Math.min(validTiles, n));
    }

    /**
     * 얼음판 미끄러짐 (실제 얼음 블록을 못 놓는 곳의 대체 — 관리자 소환 등). 서버가 보낸 속도 v 위에 클라이언트가 입력 가속 a 를
     * 더해 이번 틱 이동 d = v + a 가 되므로 a = d − v. 얼음처럼 "입력은 조금만, 이전 속도는 대부분 유지":
     * {@code v' = retention × (v + input × a)}, 크기는 maxSpeed 로 자름.
     * @param vx,vz  지난 틱에 보낸 속도
     * @param dx,dz  이번 틱 실제 이동
     * @return {vx', vz'}
     */
    public static double[] slide(double vx, double vz, double dx, double dz, double retention, double input, double maxSpeed) {
        double ax = dx - vx, az = dz - vz;
        double r = Math.max(0, Math.min(0.99, retention));
        double k = Math.max(0, Math.min(1, input));
        double nx = r * (vx + k * ax), nz = r * (vz + k * az);
        double len = Math.hypot(nx, nz);
        if (maxSpeed > 0 && len > maxSpeed) {
            nx *= maxSpeed / len;
            nz *= maxSpeed / len;
        }
        if (len < 0.003) return new double[]{0, 0};
        return new double[]{nx, nz};
    }
}
