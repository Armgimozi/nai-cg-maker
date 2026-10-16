package kr.labyrinth.combat;

import java.util.List;

/**
 * 시전 무기 마법탄의 순수 규칙 (0.3.6.1, Bukkit 무관 — 단위 테스트 대상). 런타임은 {@code CasterBolts} · {@code AttackClock} · {@code CombatListener}.
 * <ul>
 *   <li><b>좌클릭 감지</b> ({@link #punch}): Paper 26.3 의 좌클릭 패킷(punch)이 부르는 {@code PlayerArmSwingEvent}(주손) 하나로 본다.
 *       paper-26.3 에서 이 이벤트를 부르는 곳은 {@code handlePunch} 하나뿐이고, 클라이언트는 좌클릭(startAttack)과 서바이벌에서 블록을
 *       누르고 있는 동안(continueAttack, 틱마다)에만 punch 를 보낸다 — 버리기·우클릭·창 열기는 부르지 않는다.
 *       같은 틱(또는 바로 다음 틱)에 몹을 직접 클릭했거나 좌클릭한 블록을 다른 기능(미궁 금 간 벽·포자 주머니·퍼즐 블록·상자)이 썼으면 이미 쓴 클릭.
 *       블록을 누르고 있는 동안 오는 punch 는 새 클릭이 아니다 ({@link Press}) — 한 번 누름 = 한 발, 누르고 있어도 연사는 없다.
 *       캐기({@link #canDig}·{@link #digs}): 블록을 캘 수 있는 곳(야생의 서바이벌, 크리에이티브)에서 손 닿는 블록을 보고 눌렀고 조준선에
 *       (막는 블록 앞) 적이 없을 때만 — 마법탄 없음. 미궁은 서바이벌이지만 블록을 캘 수 없으므로 언제나 쏜다 (어드벤처 광산도).</li>
 *   <li><b>몹 직접 클릭</b> ({@link #entityClick}): 시전 무기로 손 닿는 적을 클릭하면 바닐라 공격은 막고 그 적에게 마법탄을 바로 넣는다
 *       (한 클릭 = 한 발, 같은 시계). 적이 아닌 것(동물·주민·갑옷 거치대·액자·NPC·같은 파티)은 지금처럼 바닐라에 맡긴다.</li>
 *   <li><b>바닐라 근접 피해</b> ({@link #cancelMeleeDamage}): 어떤 길로든 시전 무기의 근접 피해가 적에게 들어오면 취소만 한다 — 피해는 마법탄이 준다
 *       (두 번 맞지 않게).</li>
 *   <li><b>색</b> ({@link #trailColor}): 무기 텍스처 팔레트의 밝은 두 색(4·5번째) 가운데 더 짙은(채도 × 명도) 쪽. 그 색이 회색이면
 *       팔레트에서 밝고 짙은 색, 그것도 없으면 그 회색의 빛깔을 살려 채도를 올린다 (회색 마법탄은 연기처럼 보임).</li>
 * </ul>
 */
public final class CasterBoltRules {

    private CasterBoltRules() {}

    /** 좌클릭(팔 휘두름) 하나를 어떻게 볼지. */
    public enum Punch {
        /** 마법탄 (공격 시계가 통과시키면 나간다). */
        BOLT,
        /** 시전 무기가 아니거나 꺼짐. */
        NOT_CASTER,
        /** 이미 쓴 클릭 (몹 직접 클릭·다른 기능이 쓴 블록 좌클릭·실제로 깬 블록과 같은 틱). */
        CONSUMED,
        /** 지금은 공격할 수 없음 (관전·죽음·기절·창이 열려 있음). */
        BUSY,
        /** 블록을 누르고 있는 동안 틱마다 오는 punch (새 클릭이 아님). */
        HOLD,
        /** 블록 캐기 ({@link #digs}). */
        DIG
    }

    /**
     * @param caster   시전 무기를 들었고 마법탄이 켜져 있음 (요구 능력치 미달 무기 = 맨손이라 아님)
     * @param consumed 같은 틱에 이미 쓴 클릭 ({@link #consumed(int, int)})
     * @param busy     관전·죽음·기절·창 열림
     * @param fresh    새 클릭 ({@link Press#punch}) — false 면 블록을 누르고 있는 동안의 punch
     * @param dig      블록 캐기 ({@link #digs})
     */
    public static Punch punch(boolean caster, boolean consumed, boolean busy, boolean fresh, boolean dig) {
        if (!caster) return Punch.NOT_CASTER;
        if (consumed) return Punch.CONSUMED;
        if (busy) return Punch.BUSY;
        if (!fresh) return Punch.HOLD;
        if (dig) return Punch.DIG;
        return Punch.BOLT;
    }

    /**
     * 이 자리에서 좌클릭이 블록을 캘 수 있는가: 크리에이티브, 또는 미궁 밖의 서바이벌(야생·마을). 미궁은 서바이벌이지만 블록이 깨지지 않으므로
     * (DungeonManager 가 막음) 캐기로 보지 않는다. 어드벤처(광산)·관전은 못 캔다.
     */
    public static boolean canDig(boolean creative, boolean survival, boolean labyrinthWorld) {
        return creative || survival && !labyrinthWorld;
    }

    /**
     * 캐기 = 캘 수 있는 곳 + 조준선이 손 닿는 블록(풀·거미줄처럼 통과 가능한 것 포함 — 클라이언트가 고르는 블록)에 닿음
     * + 조준선에 맞힐 적이 없음(막는 블록 앞, 16칸까지). 적이 있으면 그 클릭은 마법탄 — 벽 앞 3~4.5칸의 몹, 작은 몹 뒤 바닥, 거미줄 너머 몹.
     */
    public static boolean digs(boolean canDig, boolean blockInReach, boolean enemyOnLine) {
        return canDig && blockInReach && !enemyOnLine;
    }

    /**
     * 한 사람의 좌클릭 punch 가 새 클릭인가 (서바이벌에서 블록을 누르고 있으면 26.3 클라이언트가 틱마다 punch 를 보낸다 — {@code continueAttack}).
     * 블록 좌클릭 시작({@code PlayerInteractEvent LEFT_CLICK_BLOCK}: 서바이벌은 START_DESTROY_BLOCK, 어드벤처는 punch 바로 앞)과 같은 틱(또는 다음 틱)의
     * punch 는 새 클릭. 서바이벌·크리에이티브면 그때부터 '누르는 중' — 놓을 때({@code BlockDamageAbortEvent}, 클라이언트는 놓으면 언제나
     * ABORT 를 보내고 paper-26.3 은 ABORT 마다 이 이벤트를 부른다)나 블록이 깨질 때({@code BlockBreakEvent})까지, 또는 punch 가
     * {@link #HOLD_GAP} 틱 넘게 끊기면 끝. 누르는 중의 punch 는 새 클릭이 아니다 (네트워크로 1~2틱 끊겨도).
     * 블록 시작 없이 온 punch(허공·클라이언트가 몹을 손 밖으로 본 클릭)는 누르는 중이 아니면 언제나 새 클릭 — 허공 연타는 그대로 시계가 거른다.
     * 어드벤처는 블록을 캐지 않아 누르고 있어도 punch 가 오지 않으므로 '누르는 중'이 되지 않는다.
     */
    public static final class Press {
        /** 누르는 중인데 punch 가 이만큼 끊기면 놓은 것으로 본다 (틱, 0.5초 — 놓았다는 알림을 놓쳤을 때만). */
        public static final int HOLD_GAP = 10;
        private int start = Integer.MIN_VALUE / 2;
        private boolean startUsed = true;
        private boolean digging;
        private boolean released;
        private int last = Integer.MIN_VALUE / 2;
        private boolean holding;

        /** 블록 좌클릭 시작. @param digging 서바이벌·크리에이티브 (클라이언트가 그 블록을 캐기 시작함) */
        public void blockStart(int tick, boolean digging) {
            start = tick;
            startUsed = false;
            this.digging = digging;
            released = false;
        }

        /** 놓음 (ABORT) · 블록이 깨짐. */
        public void release() {
            holding = false;
            released = true;
        }

        public boolean holding() { return holding; }

        /** punch 하나. @return 새 클릭이면 true, 블록을 누르고 있는 동안의 punch 면 false */
        public boolean punch(int tick) {
            boolean fresh;
            if (!startUsed && tick - start >= 0 && tick - start <= 1) {
                startUsed = true;
                holding = digging && !released;
                fresh = true;
            } else if (holding && tick - last >= 0 && tick - last <= HOLD_GAP) {
                fresh = false;
            } else {
                holding = false;
                fresh = true;
            }
            last = tick;
            return fresh;
        }
    }

    /** 몹(엔티티)을 직접 클릭했을 때. */
    public enum EntityClick {
        /** 바닐라 공격을 막고, 공격 시계가 통과시키면 그 적에게 마법탄을 바로 넣는다. */
        BOLT_STRIKE,
        /** 바닐라 그대로 (시전 무기가 아니거나 꺼짐, 또는 적이 아님). 뒤따르는 휘두름은 이미 쓴 클릭. */
        VANILLA
    }

    public static EntityClick entityClick(boolean caster, boolean livingEnemy) {
        return caster && livingEnemy ? EntityClick.BOLT_STRIKE : EntityClick.VANILLA;
    }

    /**
     * 시전 무기로 손 닿는 <b>플레이어</b>를 가리키고 눌렀는데 그 플레이어가 적이 아님 (같은 파티·PvP 꺼짐·안전지대):
     * 그 클릭은 이미 쓴 클릭으로 세지 않는다 — 뒤따르는 휘두름이 그대로 마법탄이 되어 그 플레이어를 지나 뒤의 적에게 간다
     * (바로 앞에 선 파티원이 마법사의 좌클릭을 먹어 버리지 않게). 다른 기능이 막은 클릭(빙결된 동료 풀기 등)은 그대로 이미 쓴 클릭.
     * 플레이어가 아닌 것(NPC·주민·동물·갑옷 거치대)은 지금처럼 바닐라 클릭 (NPC 좌클릭 대화 등).
     */
    public static boolean throughPlayer(boolean caster, boolean targetIsPlayer, boolean enemy, boolean cancelled) {
        return caster && targetIsPlayer && !enemy && !cancelled;
    }

    /** 시전 무기(마법탄 켜짐)의 바닐라 근접 피해가 적에게 들어왔다 → 취소만 (피해는 마법탄 한 발). */
    public static boolean cancelMeleeDamage(boolean caster, boolean enemy) { return caster && enemy; }

    /** 26.3 클라이언트가 허공 좌클릭 뒤 다음 좌클릭을 보내지 않는 시간 (Minecraft.startAttack 의 missTime = 10틱). */
    public static final long CLIENT_AIR_CLICK_GAP_MS = 500;

    /**
     * 허공 클릭(마법탄)의 기억창 (ms). 설정(combat.early_click_buffer, 기본 0.35초)과 0.5초 가운데 긴 쪽, 설정이 0 이면 끔.
     * 허공 클릭 뒤 0.5초 동안 클라이언트가 다음 클릭을 보내지 않으므로, 마구 누르는 사람의 다음 클릭은 0.5초 뒤에야 온다 —
     * 기억창이 0.35초면 간격이 0.85~1.0초인 지팡이(시작 지팡이 0.94초 포함)는 그 클릭이 '너무 이름'으로 버려져 주기가 1.0초가 된다
     * (최대 −11%). 0.5초면 그 클릭을 기억했다가 제때 쏜다.
     */
    public static long airBufferMs(double configuredSeconds) {
        if (!(configuredSeconds > 0)) return 0;
        return Math.max(Math.round(configuredSeconds * 1000.0), CLIENT_AIR_CLICK_GAP_MS);
    }

    /** 같은 틱 또는 바로 다음 틱이면 이미 쓴 클릭 (패킷이 틱 경계에 걸려 나뉘어 와도 한 번으로). */
    public static boolean consumed(int consumedTick, int nowTick) {
        int d = nowTick - consumedTick;
        return d >= 0 && d <= 1;
    }

    /** 마법탄 기본 색 (팔레트가 없을 때) — 옅은 보라. */
    public static final int DEFAULT_COLOR = 0xB98CFF;

    /**
     * 무기 팔레트 (#rrggbb 5색, 어두운 → 밝은) → 마법탄 색. 4·5번째(밝은 쪽) 가운데 채도 × 명도가 큰 쪽 — 지팡이 머리의 빛나는 색.
     * 둘 다 거의 흰색이면 그 가운데 덜 흰 쪽. 팔레트가 짧으면 있는 색 가운데 같은 기준, 없거나 못 읽으면 fallback.
     * 고른 색이 회색({@link #GREY} 미만)이면 팔레트 전체에서 밝고({@link #BRIGHT} 이상) 짙은({@link #VIVID} 이상) 색, 없으면 그 회색의 빛깔대로
     * 채도를 {@link #BOOST_SAT} 까지 올린다 (은빛 지팡이 → 옅은 하늘빛).
     */
    public static int trailColor(List<String> palette, int fallback) {
        if (palette == null || palette.isEmpty()) return fallback;
        int from = Math.max(0, palette.size() - 2);
        int best = -1;
        double bestScore = -1;
        for (int i = from; i < palette.size(); i++) {
            int rgb = parse(palette.get(i));
            if (rgb < 0) continue;
            double s = vividness(rgb);
            if (s > bestScore) {
                bestScore = s;
                best = rgb;
            }
        }
        if (best < 0) {
            for (String h : palette) {
                int rgb = parse(h);
                if (rgb >= 0 && vividness(rgb) > bestScore) {
                    bestScore = vividness(rgb);
                    best = rgb;
                }
            }
        }
        if (best < 0) return fallback;
        if (vividness(best) >= GREY) return best;
        int alt = -1;
        double altScore = -1;
        for (String h : palette) {
            int rgb = parse(h);
            if (rgb < 0 || value(rgb) < BRIGHT || vividness(rgb) < VIVID) continue;
            if (vividness(rgb) > altScore) {
                altScore = vividness(rgb);
                alt = rgb;
            }
        }
        return alt >= 0 ? alt : saturate(best, BOOST_SAT);
    }

    /** 이보다 칙칙하면(채도 × 명도) 회색으로 본다 — 은빛·잿빛 지팡이 5자루 (#c9ced6 · #c0c4d0 · #c8ccd8 · #cfc6e0). */
    static final double GREY = 0.12;
    /** 회색 대신 고를 팔레트 색의 최소 명도·짙기. */
    static final double BRIGHT = 0.5, VIVID = 0.2;
    /** 대신 고를 색이 없을 때 올릴 채도. */
    static final double BOOST_SAT = 0.32;

    static double value(int rgb) { return Math.max(rgb >> 16 & 0xFF, Math.max(rgb >> 8 & 0xFF, rgb & 0xFF)) / 255.0; }

    /** 빛깔(hue)·명도는 그대로, 채도만 sat 까지 (이미 더 짙으면 그대로). */
    static int saturate(int rgb, double sat) {
        double r = (rgb >> 16 & 0xFF) / 255.0, g = (rgb >> 8 & 0xFF) / 255.0, b = (rgb & 0xFF) / 255.0;
        double max = Math.max(r, Math.max(g, b)), span = max - Math.min(r, Math.min(g, b));
        if (max <= 0 || span < 1e-9 || span / max >= sat) return rgb; // 빛깔 없는 완전한 회색·이미 짙은 색은 그대로
        double k = max * sat / span; // 각 성분이 가장 밝은 성분에서 떨어진 거리를 같은 비율로 늘림 (빛깔·명도 그대로)
        return channel(max - (max - r) * k) << 16 | channel(max - (max - g) * k) << 8 | channel(max - (max - b) * k);
    }

    private static int channel(double v) { return (int) Math.round(Math.max(0, Math.min(1, v)) * 255); }

    /** HSV 채도 × 명도 (0~1). */
    static double vividness(int rgb) {
        double r = (rgb >> 16 & 0xFF) / 255.0, g = (rgb >> 8 & 0xFF) / 255.0, b = (rgb & 0xFF) / 255.0;
        double max = Math.max(r, Math.max(g, b)), min = Math.min(r, Math.min(g, b));
        double sat = max <= 0 ? 0 : (max - min) / max;
        return sat * max;
    }

    /** "#rrggbb" / "rrggbb" → 0xRRGGBB, 못 읽으면 -1. */
    static int parse(String hex) {
        if (hex == null) return -1;
        String h = hex.trim();
        if (h.startsWith("#")) h = h.substring(1);
        if (h.length() != 6) return -1;
        try {
            return Integer.parseInt(h, 16) & 0xFFFFFF;
        } catch (NumberFormatException e) {
            return -1;
        }
    }
}
