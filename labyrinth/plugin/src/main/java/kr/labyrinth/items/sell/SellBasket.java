package kr.labyrinth.items.sell;

import java.util.ArrayList;
import java.util.List;

/**
 * 판매 대기 칸 (순수 — 아이템 묶음 타입 T 와 무관해서 서버 없이 테스트한다. 실제로는 T = ItemStack).
 * <p>
 * 규칙: 올린 묶음은 이 바구니만 들고 있다(가방에서는 이미 빠짐). 나가는 길은 셋 뿐이고 셋 다 바구니를 비운다 —
 * {@link #remove}(한 칸 돌려받기), {@link #takeAll}(닫기·접속 종료·죽음·서버 종료 때 전부 돌려받기),
 * {@link #sell}(판매 — 합계를 한 번만 돌려준다). {@link #close} 뒤로는 아무것도 받지 않는다 → 닫힌 창에 늦게 온 클릭이
 * 물건을 삼키거나 골드를 두 번 주는 일이 없다.
 * <p>
 * 영웅 이상·강화 장비(risky)가 섞여 있으면 [판매] 를 {@link #press} 로 두 번 눌러야 하고, 칸이 바뀌면 다시 처음부터.
 */
public final class SellBasket<T> {

    /** 묶음 다루기 (ItemStack 이면 getAmount · asQuantity · isSimilar · getMaxStackSize). */
    public interface Stacks<T> {
        int amount(T stack);

        /** 같은 물건 amount 개짜리 새 묶음 (원본은 건드리지 않음). */
        T withAmount(T stack, int amount);

        boolean similar(T a, T b);

        int maxStack(T stack);
    }

    /** 한 칸: 묶음 + 한 개 값 + 확인이 필요한 물건인가. */
    public record Entry<T>(T stack, int unitPrice, boolean risky) {}

    /** 판매 결과 — 골드는 total 만큼 한 번만 준다. */
    public record Sale<T>(long total, int count, List<Entry<T>> entries) {}

    public enum Press { EMPTY, ARMED, SELL }

    private final Stacks<T> stacks;
    private final int capacity;
    private final long confirmWindowMs;
    private final List<Entry<T>> entries = new ArrayList<>();
    private boolean closed;
    private long armedAt = -1;

    public SellBasket(Stacks<T> stacks, int capacity, long confirmWindowMs) {
        this.stacks = stacks;
        this.capacity = Math.max(1, capacity);
        this.confirmWindowMs = Math.max(0, confirmWindowMs);
    }

    public int capacity() { return capacity; }
    public int size() { return entries.size(); }
    public boolean isEmpty() { return entries.isEmpty(); }
    public boolean closed() { return closed; }
    public List<Entry<T>> entries() { return List.copyOf(entries); }

    /** 이 물건을 몇 개까지 더 올릴 수 있나 (같은 물건 칸의 남은 자리 + 빈 칸 × 묶음 최대). 닫혔으면 0. */
    public int room(T stack, int unitPrice) {
        if (closed || stack == null) return 0;
        int max = Math.max(1, stacks.maxStack(stack));
        long room = 0;
        for (Entry<T> e : entries) {
            if (e.unitPrice() == unitPrice && stacks.similar(e.stack(), stack)) room += Math.max(0, max - stacks.amount(e.stack()));
        }
        room += (long) (capacity - entries.size()) * max;
        return (int) Math.min(Integer.MAX_VALUE, Math.max(0, room));
    }

    /**
     * 올린다 (같은 물건 칸부터 채우고 남으면 새 칸). 호출하는 쪽은 {@link #room} 만큼만 가방에서 빼서 넘길 것.
     * @return 실제로 받은 개수 (닫혔거나 자리가 없으면 0 — 그때는 가방에서 빼면 안 된다)
     */
    public int add(T stack, int unitPrice, boolean risky) {
        if (closed || stack == null) return 0;
        int left = stacks.amount(stack);
        if (left <= 0 || room(stack, unitPrice) < left) return 0; // 다 못 받으면 하나도 받지 않는다 (반쪽 이동 없음)
        int max = Math.max(1, stacks.maxStack(stack));
        for (int i = 0; i < entries.size() && left > 0; i++) {
            Entry<T> e = entries.get(i);
            if (e.unitPrice() != unitPrice || !stacks.similar(e.stack(), stack)) continue;
            int have = stacks.amount(e.stack());
            int put = Math.min(left, max - have);
            if (put <= 0) continue;
            entries.set(i, new Entry<>(stacks.withAmount(e.stack(), have + put), unitPrice, e.risky() || risky));
            left -= put;
        }
        while (left > 0) {
            int put = Math.min(left, max);
            entries.add(new Entry<>(stacks.withAmount(stack, put), unitPrice, risky));
            left -= put;
        }
        disarm();
        return stacks.amount(stack);
    }

    /** 한 칸을 꺼낸다 (돌려받기). 없는 칸이면 null. */
    public T remove(int index) {
        if (index < 0 || index >= entries.size()) return null;
        disarm();
        return entries.remove(index).stack();
    }

    /** 전부 꺼낸다 (돌려받기). 바구니는 빈다. */
    public List<T> takeAll() {
        List<T> out = new ArrayList<>(entries.size());
        for (Entry<T> e : entries) out.add(e.stack());
        entries.clear();
        disarm();
        return out;
    }

    /** 창이 닫혔다: 전부 꺼내고 앞으로는 받지 않는다. 두 번 불러도 두 번째는 빈 목록. */
    public List<T> close() {
        closed = true;
        return takeAll();
    }

    /** 대기 중인 물건 합계 (골드). */
    public long total() {
        long t = 0;
        for (Entry<T> e : entries) t += (long) e.unitPrice() * stacks.amount(e.stack());
        return t;
    }

    public int count() {
        int n = 0;
        for (Entry<T> e : entries) n += stacks.amount(e.stack());
        return n;
    }

    public boolean needsConfirm() {
        for (Entry<T> e : entries) if (e.risky()) return true;
        return false;
    }

    /** 확인 대기 중인가 (첫 [판매] 뒤 confirmWindowMs 안). */
    public boolean armed(long now) { return armedAt >= 0 && now - armedAt <= confirmWindowMs; }

    /**
     * [판매] 누름. 비었으면 EMPTY, 확인이 필요한데 아직이면 ARMED(다음 누름부터 판매), 아니면 SELL — SELL 이면 바로 {@link #sell} 할 것.
     */
    public Press press(long now) {
        if (closed || entries.isEmpty()) return Press.EMPTY;
        if (needsConfirm() && !armed(now)) {
            armedAt = now;
            return Press.ARMED;
        }
        return Press.SELL;
    }

    /** 판다: 전부 비우고 결과를 한 번만 돌려준다 (비었거나 닫혔으면 null). 골드는 호출하는 쪽이 total 만큼 한 번 준다. */
    public Sale<T> sell() {
        if (closed || entries.isEmpty()) return null;
        Sale<T> s = new Sale<>(total(), count(), List.copyOf(entries));
        entries.clear();
        disarm();
        return s;
    }

    private void disarm() { armedAt = -1; }
}
