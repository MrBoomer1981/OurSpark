/**
 * Манифест ассетов: код обращается к графике только по логическому имени.
 * Пути, размеры, кадры анимации и порядок слоёв живут здесь — заменить заглушку значит поменять запись,
 * а не код экранов. Файлы — в public/assets/; как заменять — docs/assets.md.
 */

/** Слой питомца. Кадры анимации лежат в одной картинке по горизонтали, все одной ширины. */
export type Sprite = {
  src: string;
  width: number; // размер одного кадра в пикселях арта
  height: number;
  frames: number; // 1 — неподвижная картинка
  fps: number; // кадров в секунду; при одном кадре не важно
  z: number; // порядок слоёв: питомец — 0, что меньше — за ним (гнездо), что больше — поверх
  baseline?: number; // у спрайта питомца: пустых рядов под лапами — на столько он опускается на землю сцены
};

/** Картинка без кадров: иконка или фон. */
export type Picture = { src: string; width: number; height: number };

/** Настроение питомца: покой или радость — после своего ответа и при раскрытии. */
export type Mood = 'idle' | 'cheer';

// Ворон-заглушка (CC0, smithygames): кадры 40×40 вырезаны из листа и обведены светлым ободком.
// Покой — стоит и моргает (голова на месте, косметика не съезжает); радость — два взмаха и «кар».
const IDLE: Sprite = { src: '/assets/pet/crow-idle.png', width: 40, height: 40, frames: 8, fps: 4, z: 0, baseline: 7 };
const CHEER: Sprite = { ...IDLE, src: '/assets/pet/crow-cheer.png', fps: 6 };
const slot = (name: string, z: number): Sprite => ({
  src: `/assets/items/${name}.svg`,
  width: 40,
  height: 40,
  frames: 1,
  fps: 0,
  z,
});
const icon = (name: string): Picture => ({ src: `/assets/icons/${name}.svg`, width: 12, height: 12 });

export const assets: Partial<Record<string, Sprite>> = {
  // Питомец по стадиям (ключи стадий — из content/pet.yaml): pet.<стадия> — покой, pet.<стадия>.cheer — радость.
  // Пока у всех стадий одна заглушка.
  'pet.foundling': IDLE,
  'pet.foundling.cheer': CHEER,
  'pet.companion': IDLE,
  'pet.companion.cheer': CHEER,
  'pet.keeper': IDLE,
  'pet.keeper.cheer': CHEER,
  // Косметика: предмет рисуется своей картинкой item.<ключ>, а пока её нет — заглушкой слота slot.<ключ>.
  'slot.nest': slot('nest', -1),
  'slot.cloak': slot('cloak', 1),
  'slot.neck': slot('neck', 2),
  'slot.mask': slot('mask', 3),
  'slot.feathers': slot('feathers', 4),
};

export const pictures: Partial<Record<string, Picture>> = {
  // Иконки по смыслу, а не по рисунку: icon.relic — сейчас ключ, но может стать чем угодно.
  'icon.spark': icon('spark'),
  'icon.seal': icon('seal'), // послание дня — письмо под восковой печатью
  'icon.page': icon('page'), // страница летописи
  'icon.relic': icon('key'),
  'icon.stage': icon('feather'),
  'icon.habit': icon('candle'),
  'icon.hatch': icon('egg'),
  'icon.pet': icon('feather'), // кнопка «Питомец»
  'icon.chronicle': icon('page'), // кнопка «Летопись»
  // Фон убежища за питомцем в Гнезде: небо и горы GothicVania (CC0, ansimuz), перекрашенные в ночную синь.
  // Высота — половина высоты сцены: рисуется ровно вдвое. Без записи сцену рисует CSS (.scene в index.css).
  'scene.nest': { src: '/assets/scene/nest.png', width: 240, height: 104 },
};

/** Спрайт стадии в нужном настроении. Неизвестная стадия рисуется первой, радости нет — покоем. */
export function petSprite(stage: string, mood: Mood): Sprite {
  const calm = assets[`pet.${stage}`] ?? IDLE;
  return mood === 'cheer' ? (assets[`pet.${stage}.cheer`] ?? calm) : calm;
}

/** Слои питомца снизу вверх: спрайт стадии и предметы. */
export function petLayers(stage: string, mood: Mood, items: { key: string; slot: string }[]): Sprite[] {
  const worn = items.map((item) => assets[`item.${item.key}`] ?? assets[`slot.${item.slot}`]);
  return [petSprite(stage, mood), ...worn.filter((sprite) => sprite !== undefined)].sort((a, b) => a.z - b.z);
}
