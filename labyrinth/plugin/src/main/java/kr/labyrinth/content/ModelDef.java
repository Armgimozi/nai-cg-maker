package kr.labyrinth.content;

import java.util.List;

/** 몹/보스 3D 모델 리그 정의 (mobs.yml/bosses.yml model). pivot 은 블록 단위, size 는 px(16=1블록). */
public record ModelDef(int textureWidth, int textureHeight, List<Part> parts, Params style) {

    public static final ModelDef EMPTY = new ModelDef(64, 64, List.of(), Params.EMPTY);

    public record Part(String name, String form, double sizeX, double sizeY, double sizeZ,
                       double pivotX, double pivotY, double pivotZ, String anim) {}
}
