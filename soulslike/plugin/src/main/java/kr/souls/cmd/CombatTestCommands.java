package kr.souls.cmd;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import kr.souls.Souls;
import kr.souls.cmd.test.ContractTestCommands;
import kr.souls.cmd.test.FoeTestCommands;
import kr.souls.cmd.test.ProbeTestCommands;

/**
 * M1 전투 시험 명령의 한 곳 (M1_PLAN 3절, R32). /soulstest 밑의 가지를 묶음마다 cmd/test/&lt;이름&gt;TestCommands 하나에 두고, 여기서는
 * 그 가지를 붙이기만 한다. 묶음은 자기 표시 줄 밑에 한 줄 ({@code root.then(XxxTestCommands.node(plugin));}) 만 더한다.
 * 같은 낱말의 가지를 두 묶음이 붙이면 brigadier 가 합친다 (foe: P1b 의 dummy·dojo 와 P5a 의 foe spawn 은 같은 파일 FoeTestCommands).
 * 시험 모드 (debug.test-mode) 와 권한은 /soulstest 뿌리가 본다. 줄은 모두 ASCII 기계 글 ([T] ..., 봇이 읽는다).
 * <pre>
 *   probe …                PS   cmd/test/ProbeTestCommands
 *   contract …             P1-0 cmd/test/ContractTestCommands (계약 점검: 적 몸·옮기기·한 대·거두기·느려짐·서버 휘두르기·틱 차례)
 *   move … | moves | state P1a  cmd/test/MoveTestCommands
 *   dojo … | dummy …       P1b  cmd/test/FoeTestCommands
 *   queue … | guard dump   P2a  cmd/test/QueueTestCommands
 *   post …                 P2b  cmd/test/PostTestCommands
 *   stun | crit | telemetry P3  cmd/test/CritTestCommands
 *   posture | poise | knockdown P4 cmd/test/PoiseTestCommands
 *   foe …                  P5a  cmd/test/FoeTestCommands
 *   wave … | lever         P5b  cmd/test/WaveTestCommands
 *   bow dump               P7   cmd/test/BowTestCommands
 *   lock dump              P8   cmd/test/LockTestCommands
 * </pre>
 */
public final class CombatTestCommands {
    private CombatTestCommands() {}

    /** /soulstest 뿌리 (root) 에 M1 가지를 붙인다. */
    public static void attach(Souls plugin, LiteralArgumentBuilder<CommandSourceStack> root) {
        // ── M1 PS ──
        root.then(ProbeTestCommands.node(plugin));
        // ── M1 P1-0 ──
        root.then(ContractTestCommands.node(plugin));
        // ── M1 P1a ──
        root.then(kr.souls.cmd.test.MoveTestCommands.move(plugin));
        root.then(kr.souls.cmd.test.MoveTestCommands.moves(plugin));
        root.then(kr.souls.cmd.test.MoveTestCommands.state(plugin));
        // ── M1 P1b ──
        root.then(FoeTestCommands.dummy(plugin));
        root.then(FoeTestCommands.dojo(plugin));
        // ── M1 P1c ──
        // ── M1 P2a ──
        // ── M1 P2b ──
        // ── M1 P3 ──
        // ── M1 P4 ──
        // ── M1 P5a ──
        // ── M1 P5b ──
        // ── M1 P6 ──
        // ── M1 P7 ──
        // ── M1 P8 ──
        // ── M1 끝 ──
    }
}
