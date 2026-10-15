package kr.labyrinth.content;

import java.util.List;

/** 몹/보스 3D 모델 리그 정의 (mobs.yml/bosses.yml model). pivot 은 블록 단위, size 는 px(16=1블록). */
public record ModelDef(int textureWidth, int textureHeight, List<Part> parts, Params style) {

    public static final ModelDef EMPTY = new ModelDef(64, 64, List.of(), Params.EMPTY);

    /**
     * 파트 하나 (GDD §14.6).
     * <ul>
     *   <li>{@code pivot} = 모델 원점(8,8,8)이 놓이는 곳(블록, 몹 로컬: +X 몹의 왼쪽 · +Y 위 · +Z 앞).</li>
     *   <li>{@code joint} = 회전 중심(엉덩이·어깨·목·턱 경첩). 없으면 pivot — 예전과 똑같이 돈다.</li>
     *   <li>{@code set} = 한 설계를 나눠 만든 파트 묶음의 원래 이름(다리 세트 {@code legs} → leg_l·leg_r …). 리소스팩만 쓴다.</li>
     *   <li>{@code foot} = 다리: joint 에서 발바닥 가운데까지(블록)와 발바닥 앞뒤 반길이. 땅 높이 보정·보폭 계산.</li>
     * </ul>
     */
    public record Part(String name, String form, double sizeX, double sizeY, double sizeZ,
                       double pivotX, double pivotY, double pivotZ, String anim,
                       String set, double jointX, double jointY, double jointZ, Foot foot) {

        /** joint 없음(= pivot)·set 없음·foot 없음 (예전 9인자 — 테스트·코드 호환). */
        public Part(String name, String form, double sizeX, double sizeY, double sizeZ,
                    double pivotX, double pivotY, double pivotZ, String anim) {
            this(name, form, sizeX, sizeY, sizeZ, pivotX, pivotY, pivotZ, anim, null, pivotX, pivotY, pivotZ, null);
        }

        /** 같은 파트에 회전 중심·발만 바꾼 사본. */
        public Part withJoint(double x, double y, double z, Foot f) {
            return new Part(name, form, sizeX, sizeY, sizeZ, pivotX, pivotY, pivotZ, anim, set, x, y, z, f);
        }
    }

    /** 발: joint → 발바닥 가운데 (dx, dy, dz) 블록, half = 발바닥 앞뒤 반길이. */
    public record Foot(double dx, double dy, double dz, double half) {}
}
