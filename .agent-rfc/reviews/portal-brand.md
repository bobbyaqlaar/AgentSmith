# Review — portal-brand

Design: `.agent-rfc/designs/portal-brand.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **The AgentSmith "PNG" is a JPEG, with no transparency.** `file` reports
   `assets/Logo_AgentSmith.png` as JPEG, 1280×1280, three components. Used as it
   is, the dark theme would show a pale textured square. The portal's copy is
   derived instead: luminance becomes alpha, so the off-white ground goes and the
   edges stay smooth, and the white detail lines inside the figure stay the
   background's colour on both themes. Checked rendered on light and dark before
   it went near a page. The original in `assets/` is untouched.

2. **`next/image`'s optimizer needs `sharp` in standalone mode, and the portal does
   not install it.** Next 14.2.35, no `sharp` in `node_modules` or `package.json`.
   Under `next dev` the marks would have worked; in the Docker image the optimizer
   route would have failed. Both marks are `unoptimized` and derived at about four
   times their displayed size — 128 px for the 28 px header mark, 96 px for the
   20 px footer mark — which also took them from 226 KB to 22 KB together. The
   design was amended to say so first; `test/brand.test.ts` fails if either loses
   `unoptimized`.

## Pass 2 — findings: 0

Checked on the BUILT STANDALONE server — `node .next/standalone/server.js` with
`.next/static` copied beside it, which is exactly what `portal/Dockerfile` ships:

- both marks were served from `/_next/static/media/` (`agentsmith-mark.6b309cb9.png`,
  `aqlaar.f81423e0.png`), decoded at 128×128 and 96×86 and shown at 28×28 and
  20×18; the favicon from `/icon.png`;
- dark theme: the AgentSmith mark inverted to white (`filter: invert(1)`), the Aqlaar
  mark unfiltered; light theme: the mark black; both read in the header and footer;
- both carry `alt=""` beside their own names, so a screen reader says each once;
- at 375 px the header and footer fit, and nothing overflows.

`test/brand.test.ts` was mutated three ways, each caught: a `public/` folder appearing,
a root-relative `src` in a component, and a mark rendered without `unoptimized`.

The derivation, run from the repository root with Pillow, so a changed original is
re-derived rather than hand-edited (P14):

```python
from PIL import Image, ImageDraw

LO, HI = 60, 200  # luminance at or below LO is fully opaque; at or above HI fully transparent

src = Image.open("assets/Logo_AgentSmith.png").convert("L")
alpha = src.point(lambda v: 0 if v >= HI else 255 if v <= LO else round((HI - v) * 255 / (HI - LO)))
mark = Image.new("RGBA", src.size, (0, 0, 0, 0))
mark.putalpha(alpha)
box = alpha.point(lambda a: 255 if a > 16 else 0).getbbox()
mark = mark.crop(box)
side = round(max(mark.size) * 1.04)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
square.resize((128, 128), Image.LANCZOS).save("portal/assets/brand/agentsmith-mark.png", optimize=True)

icon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
ImageDraw.Draw(icon).rounded_rectangle((0, 0, 63, 63), radius=14, fill=(255, 255, 255, 255))
inner = square.resize((52, 52), Image.LANCZOS)
icon.alpha_composite(inner, (6, 6))
icon.save("portal/app/icon.png", optimize=True)

aq = Image.open("assets/LogoAqlaar-Transparent.png").convert("RGBA")
aq.resize((96, round(96 * aq.height / aq.width)), Image.LANCZOS).save("portal/assets/brand/aqlaar.png", optimize=True)
print("derived")
```

## Sign-off

Group 1 · DRY & shared code — [x] checked — the marks are rendered once, in `portal/app/layout.tsx`, the shell every page shares; the footer reuses the header's border and the pages' muted text.
Group 2 · Quality / safety — [x] checked — `test/brand.test.ts` (4 tests) pins the deployment trap and the files' shape; three mutations caught; checked on the standalone server.
Group 3 · Architecture / hygiene — [x] checked — derived assets beside the code that imports them, originals untouched, the derivation recorded.
Group 4 · Process — [x] checked — the design was amended for `unoptimized` before the layout used it.
Group 5 · Intuitive UI — [x] checked — light and dark themes, phone width, decorative `alt`, fixed dimensions so the header does not shift.
Group 6 · Signal integrity — [x] n/a — nothing here reports a status or a result.
Group 7 · Auth & session integrity — [x] n/a — no auth, session or permission is touched; the favicon route is served like any page asset.

Tests added: `portal/test/brand.test.ts` (4), registered in `portal/package.json`.
Mutation-checked: by hand — a `public/` folder, a root-relative `src`, a mark without `unoptimized`, each caught.
Fixtures re-pinned: none.
Gates run: `npx tsc --noEmit`, `npm test` (16 files), `npm run build`, the standalone server in both themes and at 375 px, and `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `matches-the-existing-component-language`, `works-at-real-viewport-sizes`, `keyboard-and-screen-reader-operable`, `environment-parity`, `guards-must-be-able-to-fail`, `every-line-earns-its-place`.

KG query: kg:4db5efdf7e02
