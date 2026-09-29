#!/usr/bin/env python3
"""Writes art/src/stamp_*.svg from one shared stamp frame + a per-region emblem.

The stamp SVGs in src/ are plain, self-contained files (edit them directly if you like);
this script just keeps the six frames identical. Re-run it, then `python3 art/build.py`.
"""
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

FRAME = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <!-- stamp_{name}: passport stamp for region "{region}". Region ring {base}, emblem {dark}.
       Frame is shared by all stamp_*.svg: ring + worn dashed band + cream centre + emblem. -->
  <defs>
    <mask id="ring"><circle cx="128" cy="128" r="100" fill="#fff"/></mask>
    <mask id="disc"><circle cx="128" cy="128" r="74" fill="#fff"/></mask>
    <mask id="inset">
      <circle cx="128" cy="128" r="74" fill="#fff"/>
      <circle cx="133" cy="135" r="74" fill="#000"/>
    </mask>
  </defs>
  <g transform="rotate({angle} 128 128)">
    <!-- outline + depth -->
    <circle cx="128" cy="135" r="112" fill="#1E1B2E"/>
    <circle cx="128" cy="128" r="112" fill="#1E1B2E"/>
    <!-- ring: shade, then lit face shifted up-left -->
    <circle cx="128" cy="128" r="100" fill="{shade}"/>
    <g mask="url(#ring)"><circle cx="123" cy="121" r="99" fill="{base}"/></g>
    <!-- worn perforated band -->
    <circle cx="128" cy="128" r="90.5" fill="none" stroke="{dash}" stroke-width="5" stroke-dasharray="10 7" stroke-linecap="round" opacity=".9"/>
    <g fill="{shade}" opacity=".55">
      <circle cx="58" cy="152" r="4"/><circle cx="196" cy="92" r="3"/><circle cx="170" cy="196" r="3.5"/><circle cx="96" cy="46" r="3"/>
    </g>
    <!-- centre -->
    <circle cx="128" cy="128" r="81" fill="#1E1B2E"/>
    <circle cx="128" cy="128" r="74" fill="#FFF4DC"/>
    <circle cx="128" cy="128" r="74" fill="#E9D3A6" mask="url(#inset)"/>
    <g mask="url(#disc)">
      <g transform="translate(128 132) scale(1.12) translate(-128 -128)">
{emblem}
      </g>
      <!-- uneven-ink specks: rubber-stamp texture -->
      <g fill="#FFF4DC" opacity=".75">
        <circle cx="104" cy="150" r="2.6"/><circle cx="146" cy="118" r="2.2"/><circle cx="120" cy="176" r="2"/>
        <circle cx="160" cy="160" r="2.4"/><circle cx="96" cy="112" r="1.8"/><circle cx="136" cy="96" r="1.6"/>
      </g>
    </g>
    <!-- highlight on the ring -->
    <path d="M44,108 A86,86 0 0 1 92,48" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" opacity=".75"/>
  </g>
</svg>
"""

S = {
    "home": dict(region="Home", base="#B8BFCC", shade="#8A92A6", dark="#4E566B", mid="#7D869C", dash="#FFFFFF", angle=-6),
    "europe": dict(region="Europe", base="#6E96FF", shade="#4468E0", dark="#2A44A8", mid="#5B80EE", dash="#FFF4DC", angle=7),
    "asia": dict(region="Asia", base="#FF7878", shade="#D94C4C", dark="#A83232", mid="#E86060", dash="#FFF4DC", angle=-9),
    "africa": dict(region="Africa", base="#F0BE5A", shade="#C98F2A", dark="#94601A", mid="#D9A040", dash="#FFF4DC", angle=5),
    "americas": dict(region="Americas", base="#5AD296", shade="#2FA36B", dark="#1C7048", mid="#3DB87A", dash="#FFF4DC", angle=-4),
    "legend": dict(region="Legend", base="#78FFEB", shade="#33C9B6", dark="#6A45C9", mid="#9B6BFF", dash="#FFFFFF", angle=9),
}

GROUND = '      <path d="M40,178 H216 V220 H40 Z" fill="{mid}" opacity=".45"/>\n'

EMBLEM = {
    # house with pitched roof, chimney, door + window cut-outs
    "home": GROUND + """      <rect x="146" y="92" width="16" height="30" rx="3" fill="{dark}"/>
      <polygon points="80,132 128,88 176,132" fill="{dark}" stroke="{dark}" stroke-width="12" stroke-linejoin="round"/>
      <rect x="94" y="124" width="68" height="54" rx="4" fill="{dark}"/>
      <path d="M118,178 V156 Q118,146 128,146 Q138,146 138,156 V178 Z" fill="#FFF4DC"/>
      <rect x="100" y="138" width="12" height="12" rx="2" fill="#FFF4DC"/>
      <rect x="144" y="138" width="12" height="12" rx="2" fill="#FFF4DC"/>
      <path d="M92,120 L128,96" stroke="{mid}" stroke-width="5" stroke-linecap="round"/>""",
    # fairytale castle: two cone-roof towers, crenellated wall, gate, flag
    "europe": GROUND + """      <path d="M128,110 V70" stroke="{dark}" stroke-width="5" stroke-linecap="round"/>
      <path d="M130,70 L152,78 L130,86 Z" fill="{mid}" stroke="{dark}" stroke-width="4" stroke-linejoin="round"/>
      <path d="M100,178 V118 H108 V110 H118 V118 H124 V110 H132 V118 H138 V110 H148 V118 H156 V178 Z" fill="{dark}"/>
      <rect x="76" y="100" width="30" height="78" rx="3" fill="{dark}"/>
      <rect x="150" y="100" width="30" height="78" rx="3" fill="{dark}"/>
      <polygon points="72,104 91,66 110,104" fill="{mid}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <polygon points="146,104 165,66 184,104" fill="{mid}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <path d="M116,178 V160 Q116,148 128,148 Q140,148 140,160 V178 Z" fill="#FFF4DC"/>
      <rect x="86" y="118" width="10" height="16" rx="5" fill="#FFF4DC"/>
      <rect x="160" y="118" width="10" height="16" rx="5" fill="#FFF4DC"/>""",
    # three-tier pagoda with up-turned eaves (dark roofs, lighter walls)
    "asia": GROUND + """      <path d="M128,86 V60" stroke="{dark}" stroke-width="6" stroke-linecap="round"/>
      <circle cx="128" cy="60" r="6" fill="{dark}"/>
      <rect x="108" y="100" width="40" height="24" fill="{mid}"/>
      <rect x="102" y="132" width="52" height="24" fill="{mid}"/>
      <rect x="96" y="164" width="64" height="16" fill="{mid}"/>
      <path d="M90,98 Q100,102 112,96 Q124,90 128,80 Q132,90 144,96 Q156,102 166,98 L158,110 H98 Z" fill="{dark}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <path d="M78,130 Q90,134 104,128 Q120,122 128,112 Q136,122 152,128 Q166,134 178,130 L168,142 H88 Z" fill="{dark}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <path d="M68,162 Q82,166 98,160 Q116,154 128,144 Q140,154 158,160 Q174,166 188,162 L176,174 H80 Z" fill="{dark}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <rect x="120" y="112" width="16" height="12" rx="3" fill="#FFF4DC"/>
      <rect x="112" y="144" width="12" height="12" rx="3" fill="#FFF4DC"/>
      <rect x="132" y="144" width="12" height="12" rx="3" fill="#FFF4DC"/>
      <rect x="120" y="172" width="16" height="10" rx="3" fill="#FFF4DC"/>""",
    # pyramid with a lit face and a shaded face, camel walking in front
    "africa": GROUND + """      <circle cx="170" cy="84" r="12" fill="{mid}"/>
      <polygon points="132,80 188,178 76,178" fill="{mid}" stroke="{mid}" stroke-width="6" stroke-linejoin="round"/>
      <polygon points="132,80 188,178 146,178" fill="{dark}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <path d="M104,140 H146 M92,160 H152" stroke="#FFF4DC" stroke-width="3" opacity=".6"/>
      <g fill="{dark}" stroke="#FFF4DC" stroke-width="4" stroke-linejoin="round" stroke-linecap="round">
        <path d="M60,126 Q58,118 66,116 L74,118 Q78,122 78,130 Q80,140 86,142 Q88,128 100,126 Q114,126 118,142 Q124,146 122,154 L120,176 H114 V160 H108 V176 H102 V162 H92 V176 H86 V162 Q76,158 74,146 Q72,136 70,130 L62,130 Q58,130 60,126 Z"/>
      </g>""",
    # saguaro cactus in the desert with a sun
    "americas": GROUND + """      <circle cx="86" cy="86" r="12" fill="{mid}"/>
      <g fill="none" stroke="{dark}" stroke-width="20" stroke-linecap="round" stroke-linejoin="round">
        <path d="M118,140 H102 Q94,140 94,132 V112"/>
        <path d="M138,126 H154 Q162,126 162,118 V98"/>
      </g>
      <rect x="116" y="66" width="26" height="114" rx="13" fill="{dark}"/>
      <path d="M125,80 V168 M133,80 V168" stroke="{mid}" stroke-width="3" stroke-linecap="round"/>
      <path d="M92,120 V114 M160,106 V100" stroke="{mid}" stroke-width="3" stroke-linecap="round"/>
      <path d="M64,178 Q96,168 120,178 M136,178 Q168,170 196,178" fill="none" stroke="{dark}" stroke-width="6" stroke-linecap="round"/>""",
    # floating crystal with sparkles
    "legend": """      <polygon points="128,60 160,98 152,160 128,192 104,160 96,98" fill="{mid}" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <polygon points="128,60 128,192 152,160 160,98" fill="{dark}"/>
      <polygon points="128,60 110,100 128,120 146,100" fill="#CDB5FF"/>
      <polygon points="128,120 104,158 128,192" fill="#B89BFF" opacity=".6"/>
      <polygon points="128,60 160,98 152,160 128,192 104,160 96,98" fill="none" stroke="{dark}" stroke-width="6" stroke-linejoin="round"/>
      <path d="M112,90 L104,108" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>
      <g fill="#FFC53D" stroke="#1E1B2E" stroke-width="3" stroke-linejoin="round">
        <path d="M80,76 Q82,88 92,90 Q82,92 80,104 Q78,92 68,90 Q78,88 80,76 Z"/>
        <path d="M176,138 Q178,148 186,150 Q178,152 176,162 Q174,152 166,150 Q174,148 176,138 Z"/>
        <path d="M170,72 Q171,78 176,79 Q171,80 170,86 Q169,80 164,79 Q169,78 170,72 Z"/>
      </g>""",
}

for name, c in S.items():
    em = EMBLEM[name].format(**c)
    svg = FRAME.format(name=name, emblem=em, **c)
    (SRC / f"stamp_{name}.svg").write_text(svg)
    print("wrote", name)
