package kr.labyrinth.content;

import java.util.List;

/** npcs.yml. role = entrance | blacksmith | class_master | title_keeper | merchant | lore. */
public record NpcDef(String id, String name, String nameplate, String skin, String role, String placement, int floor,
                     List<String> dialogue, List<ShopEntry> shop, Params skinStyle, Params raw) {

    public record ShopEntry(String item, int price, int levelReq) {}
}
