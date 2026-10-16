package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 기존 월드 구역 자리 검사 (0.3.6, CONTRACT §2.13 2·4 · review036 §2-5) — 순수 로직. 사람 손을 보면 막는다.
 * <ol>
 *   <li>지문 (배포 월드면): 열마다 정규화 블록 해시가 같으면 그대로. 다르면 — 땅 높이가 2칸 넘게 다름, 땅속 10칸에 없던 공기·물
 *       (판 구덩이·굴) → 막음. 없던 원목 (심은 나무·원목 건물)은 해시와 상관없이 본다 (원목은 정규화에서 공기라).
 *       잔디↔흙·꽃·풀·눈 층·잎은 정규화가 지워 허용, 베어 낸 나무도 허용.</li>
 *   <li>비자연 블록 ({@link Nature} 화이트리스트 밖 — 땅 위 전부 + 땅속 10칸, 지속 잎 포함) → 막음 (지문이 없어도).</li>
 *   <li>엔티티 ({@link #entityBlocks}) — 서버 쪽이 주 스레드에서 모아 넘긴다.</li>
 * </ol>
 * 얼린 칸(마을)은 보지 않는다 — 부르는 쪽이 넘기지 않는다.
 */
public final class DistrictCheck {

    private DistrictCheck() {}

    /** 지금 월드 (스냅샷·시험용 가짜). block = 소문자 id (네임스페이스·속성 없이), 월드 밖 = "void". */
    public interface Live {
        boolean has(int x, int z);

        /** 땅 높이 (Nature GROUND 맨 위 — Scan.columns 와 같은 규칙). */
        int ground(int x, int z);

        String block(int x, int y, int z);

        /** Terrain 플래그 (UNNATURAL 등). */
        int flags(int x, int z);

        /** 비자연 블록 이유 (없으면 null). */
        String note(int x, int z);
    }

    public record Problem(int x, int y, int z, String why) {
        public String line() { return why + " (" + x + " " + y + " " + z + ")"; }
    }

    /** checked = 본 열, same = 지문과 같음, allowed = 다르지만 허용(풀·잔디 등), uncovered = 지문 없는 열, problems = 막는 이유. */
    public record Result(int checked, int same, int allowed, int uncovered, List<Problem> problems) {
        public boolean ok() { return problems.isEmpty(); }
    }

    /** 지문 정규화 이름 (월드 범위 밖 = void). */
    static String normAt(Live live, int x, int y, int z) {
        String id = live.block(x, y, z);
        return id == null || id.equals("void") ? "void" : DistrictFingerprint.norm(id);
    }

    /** 지금 열을 지문의 h 기준으로 정규화해 해시. */
    public static long liveHash(Live live, int x, int z, int h, int under, int above) {
        List<String> names = new ArrayList<>(under + above + 1);
        for (int y = h - under; y <= h + above; y++) names.add(normAt(live, x, y, z));
        return DistrictFingerprint.hash(names);
    }

    /**
     * 열들 검사.
     * @param fp 이 월드의 지문 (배포 월드가 아니면 null → 비자연 검사만)
     * @param columns 볼 열 [x, z] (영역 안, 얼린 칸 뺀 것)
     * @param maxProblems 이유를 이만큼까지 모음 (그 뒤는 세기만)
     */
    public static Result check(DistrictFingerprint.World fp, int under, int above, Live live, Iterable<int[]> columns, int maxProblems) {
        List<Problem> out = new ArrayList<>();
        int checked = 0, same = 0, allowed = 0, uncovered = 0, more = 0;
        for (int[] c : columns) {
            int x = c[0], z = c[1];
            if (!live.has(x, z)) continue;
            checked++;
            List<Problem> col = new ArrayList<>(2);
            if ((live.flags(x, z) & Terrain.UNNATURAL) != 0) {
                String n = live.note(x, z);
                col.add(new Problem(x, yOf(n, live.ground(x, z)), z, "사람이 놓은 블록 " + (n == null ? "" : n.replaceAll("@.*", ""))));
            }
            DistrictFingerprint.Column f = fp == null ? null : fp.at(x, z);
            if (f != null) {
                // 새 원목 (심은 나무·원목 건물): 원목은 정규화에서 공기라 해시가 같아도 따로 본다 (베어 낸 나무는 허용)
                for (int dy = 1; dy <= above; dy++) {
                    int y = f.h() + dy;
                    String id = live.block(x, y, z);
                    if (id == null || Nature.kind(id) != Nature.Kind.LOG || f.hasLogAt(dy)) continue;
                    col.add(new Problem(x, y, z, "새 원목 " + Nature.key(id) + " (심은 나무·원목 건물)"));
                    break;
                }
            }
            long hash = f == null ? 0 : liveHash(live, x, z, f.h(), under, above);
            if (f == null) {
                uncovered++;
            } else if (hash == f.hash()) {
                if (col.isEmpty()) same++;
            } else {
                int g = live.ground(x, z);
                if (Math.abs(g - f.h()) > 2) {
                    col.add(new Problem(x, g, z, (g > f.h() ? "쌓은 땅" : "판 땅") + " — 높이 " + f.h() + " → " + g));
                }
                for (int k = 1; k <= under; k++) {
                    if ((f.under() & (1 << (k - 1))) == 0) continue;
                    int y = f.h() - k;
                    String n = normAt(live, x, y, z);
                    if (!DistrictFingerprint.solidNorm(n) && !n.equals("void")) {
                        col.add(new Problem(x, y, z, "땅속에 새 " + (n.equals("air") ? "빈칸" : "물") + " (구덩이·굴)"));
                        break;
                    }
                }
                if (col.isEmpty()) allowed++;
            }
            for (Problem p : col) {
                if (out.size() < maxProblems) out.add(p);
                else more++;
            }
        }
        if (more > 0) out.add(new Problem(0, 0, 0, "그 밖 " + more + "건"));
        return new Result(checked, same, allowed, uncovered, out);
    }

    /**
     * 큰길과 만나는 얼린 칸 (마을이 다듬은 칸 — 위 {@link #check} 는 보지 않는다) 위 구역 길 칸 [x, z, y] 검사 (0.3.6.1 리뷰):
     * 구역 길은 겉 블록(y)을 깔고 그 위 두 칸의 풀을 치운다. 지문과 열이 같으면 그대로(마을이 놓은 블록뿐), 다르면 y ~ y+2 에
     * 비자연 블록이 있으면 사람 손으로 보고 막는다. 지문이 없는 월드도 같은 비자연 검사.
     */
    public static List<Problem> junction(DistrictFingerprint.World fp, int under, int above, Live live, Iterable<int[]> cells, int maxProblems) {
        List<Problem> out = new ArrayList<>();
        for (int[] c : cells) {
            int x = c[0], z = c[1], y = c[2];
            if (!live.has(x, z)) continue;
            DistrictFingerprint.Column f = fp == null ? null : fp.at(x, z);
            if (f != null && liveHash(live, x, z, f.h(), under, above) == f.hash()) continue;
            for (int dy = 0; dy <= 2; dy++) {
                String id = live.block(x, y + dy, z);
                if (id == null || id.equals("void") || Nature.kind(id) != Nature.Kind.UNNATURAL) continue;
                out.add(new Problem(x, y + dy, z, "큰길과 만나는 자리에 사람이 놓은 블록 " + Nature.key(id)));
                break;
            }
            if (out.size() >= maxProblems) break;
        }
        return out;
    }

    private static int yOf(String note, int def) {
        if (note == null) return def;
        int at = note.indexOf('@');
        if (at < 0) return def;
        String num = note.substring(at + 1).replaceAll("[^0-9-].*$", "");
        try {
            return Integer.parseInt(num);
        } catch (NumberFormatException e) {
            return def;
        }
    }

    // ── 엔티티 ───────────────────────────────────────────────────────────

    /**
     * 사람 손을 뜻하는 엔티티인가 (CONTRACT §2.13 4): 갑옷 거치대·액자·그림·수레·보트·끈 매듭·엔드 수정·마네킹·디스플레이·
     * 상호작용, 이름표가 붙었거나 길들인 동물, 주민·떠돌이 상인. 그냥 다니는 동물은 아님 (조각 상자 밖으로 옮김).
     * @param type EntityType 이름 (ARMOR_STAND …), named = 이름표, tamed = 길들임, leashed = 끈에 묶임
     */
    public static String entityBlocks(String type, boolean named, boolean tamed, boolean leashed, boolean pluginTagged) {
        if (pluginTagged) return null; // 이 플러그인의 NPC·연출
        String t = type.toUpperCase(Locale.ROOT);
        if (t.equals("ARMOR_STAND")) return "갑옷 거치대";
        if (t.equals("ITEM_FRAME") || t.equals("GLOW_ITEM_FRAME")) return "액자";
        if (t.equals("PAINTING")) return "그림";
        if (t.equals("LEASH_KNOT")) return "끈 매듭";
        if (t.equals("END_CRYSTAL")) return "엔드 수정";
        if (t.equals("MANNEQUIN")) return "마네킹";
        if (t.endsWith("_DISPLAY") || t.equals("INTERACTION")) return "디스플레이 엔티티";
        if (t.contains("MINECART")) return "수레";
        if (t.endsWith("BOAT") || t.endsWith("RAFT")) return "보트";
        if (t.equals("VILLAGER") || t.equals("WANDERING_TRADER")) return "주민";
        if (tamed) return "길들인 동물";
        if (named) return "이름표 붙은 동물";
        if (leashed) return "끈에 묶인 동물";
        return null;
    }
}
