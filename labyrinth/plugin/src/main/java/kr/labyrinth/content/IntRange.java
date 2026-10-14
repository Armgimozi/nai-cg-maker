package kr.labyrinth.content;

import java.util.random.RandomGenerator;

/** 정수 닫힌 구간 [min, max]. */
public record IntRange(int min, int max) {
    public static final IntRange ZERO = new IntRange(0, 0);
    public static final IntRange ONE = new IntRange(1, 1);

    public int roll(RandomGenerator rng) {
        return max <= min ? min : min + rng.nextInt(max - min + 1);
    }

    public boolean contains(int v) { return v >= min && v <= max; }
}
