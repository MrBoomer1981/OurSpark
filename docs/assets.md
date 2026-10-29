# Game art: where it lives and how to replace it

«Воронье гнездо» runs on placeholder art (brief §10, §15.9). Final art replaces files and manifest entries; screens never change for it.

## Where things are

| What | Where |
|---|---|
| Pet, cosmetics, icons, the Nest background | `services/web/public/assets/` (`pet/`, `items/`, `icons/`, `scene/`) |
| Fonts | `services/web/public/fonts/` with their licenses |
| App icons (home screen, favicon) | `services/web/public/icons/`, referenced from `vite.config.ts` (PWA manifest) and `index.html` |
| Colors, frames, animations | `services/web/src/index.css` |
| The manifest: logical name → file, size, frames | `services/web/src/assets.ts` |

Code refers to art only by logical name through the manifest. To replace a placeholder, put the new file into `public/assets/` and change its manifest entry. A file replaced at the same path shows up without a rebuild: Caddy serves `/assets/*` as `no-cache`. The installed PWA gets new art with the next deploy, when its service worker precaches the new files.

## Logical names

- `pet.<stage>` — the pet at rest; `pet.<stage>.cheer` — the pet's joy: after one's own answer and on the result screen. Stage keys come from `services/api/content/pet.yaml` (`foundling`, `companion`, `keeper`). Without a `cheer` sprite the pet stays at rest.
- `item.<key>` — a cosmetic item (keys from `pet.yaml`); until it has its own art, the slot placeholder `slot.<slot>` is drawn.
- `icon.<name>` — `spark`, `seal` (the message of the day), `page` (a chronicle page), `relic`, `stage`, `habit`, `hatch`, `pet` and `chronicle` (the Nest buttons). Names describe meaning, not the drawing.
- `scene.nest` — the shelter behind the pet in the Nest, 240×104 drawn 2× (the scene is 208 px tall: the pet plus 48 px). Without the entry CSS draws the night sky, the moon and the ground (`.scene`).

## Sprites

A `Sprite` is one image with all animation frames side by side, every frame the same size.

| Field | Meaning |
|---|---|
| `width`, `height` | one frame, in art pixels |
| `frames`, `fps` | frame count and speed; 1 frame = a still image |
| `z` | layer order: the pet is 0, lower is behind it (the nest), higher is on top |
| `baseline` | pet sprites only: empty rows under the feet; the pet sinks by that much to stand on the scene's ground |

- The pet box is 160 px (80 px for try-on): the 40×40 frames are drawn 4× and 2×. A new sprite keeps a size that divides both (40 or 80) so pixels scale by a whole number and stay sharp.
- Cosmetics share the pet's canvas size, so layers line up. An animated item needs the pet's frame count and `fps` to move with it.
- Icons are 12×12 and drawn at whole multiples (24 or 36 px).
- The cheer also makes the whole pet hop in CSS (`.pet.cheering`), so worn items move with it.
- Animations run in CSS (`steps()`). With `prefers-reduced-motion` the pet stays on its first frame and the reward sparks do not fly.

## Colors, frames, fonts

- Colors are tokens in `:root` of `index.css`. `--bg` is repeated in `vite.config.ts` (`background`) and `index.html` (`theme-color`); inside Telegram the header color is read from `--bg` at startup.
- Frames are pixel borders drawn with `box-shadow` steps of `--px` (4 px), so corners stay notched. The two main places — the Nest scene and the message parchment — get the ornate gold frame (`.gilded`): `public/assets/ui/frame-gold.png` through `border-image`, sliced at 18 px and drawn 2×; its ornaments are only in the corners, so the straight sides stretch cleanly.
- The pixel font is Press Start 2P, only for headings, the stage name and the spark counter, at 16 or 24 px (it is sharp at multiples of 8). Buttons and all body text use the system font for readability (brief §10). Pixelify Sans was tried and rejected: its Cyrillic is unreadable («д» looks like «а», capital «П» is missing).
- Two font files cover Cyrillic and Latin (`unicode-range` in `index.css`). They are served from the app and precached, with no requests to Google.

## The current placeholders

- **Pet:** the CC0 crow sheet (48×48 cells): frames are cut to 40×40 at (4, 0) and get a light 1-pixel rim, without which the black crow is lost on the night background. Rest: the standing frame seven times and a blink (the eye pixel at 23,13 closed). Cheer: two wing strokes and a caw. `baseline` is 7 (the feet end on row 32).
- **Cosmetics:** drawn for this crow on the same 40×40 canvas: a crest, a pendant, a cloak, a plague-doctor mask, a nest.
- **Nest background:** the sky with the moon and the mountains of GothicVania Cemetery, recolored from magenta into the theme's night blue with a bone-white moon. The graveyard layer (skulls, red-eyed trees, the reaper) is left out on purpose: brief §10 asks for cozy gothic, not horror.
- **App icons** (`public/icons/`) are the crow's resting frame scaled 5×, 10× (maskable, inside the safe zone) and 13× on `--bg`; `favicon.svg` is the same pixels.
- The original packs are not in the repository; only the files in use are. They come from the links below.

## Sounds

There are none yet. When they come: files in `public/assets/sounds/`, logical names `sound.<name>` in the manifest, never played before the user interacts with the page.

## Authors and licenses

| What | Author | License |
|---|---|---|
| Crow (`public/assets/pet/`, app icons) | [smithygames](https://smithygames.itch.io/crow-sprite) | CC0 |
| Nest background (`public/assets/scene/`) | [Luis Zuno @ansimuz](https://opengameart.org/node/85024), GothicVania Cemetery | public domain; credit appreciated |
| Gold frame (`public/assets/ui/frame-gold.png`) | [AbyssOwl](https://abyssowl.itch.io/gothic-pixel-ui), Gothic Pixel UI (free part) | use and modify in any project; no resale, no AI training; credit required in a commercial project |
| Cosmetics and icons | drawn for this project | — |
| Press Start 2P (`public/fonts/`) | CodeMan38 | SIL Open Font License 1.1 (`public/fonts/OFL.txt`) |
