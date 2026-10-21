/**
 * Манифест ассетов: код обращается к графике только по логическому имени.
 * Пути, размеры, число кадров и порядок слоёв живут здесь — заменить заглушку значит поменять запись,
 * а не код экранов. Файлы — в public/assets/.
 */
export type Sprite = { src: string; width: number; height: number; frames: number; z: number };

const PET: Sprite = { src: '/assets/pet/placeholder.svg', width: 16, height: 16, frames: 1, z: 0 };
const slot = (name: string, z: number): Sprite => ({ src: `/assets/items/${name}.svg`, width: 16, height: 16, frames: 1, z });

export const assets: Partial<Record<string, Sprite>> = {
  // Питомец по стадиям (ключи стадий — из content/pet.yaml). Пока у всех стадий одна заглушка.
  'pet.foundling': PET,
  'pet.companion': PET,
  'pet.keeper': PET,
  // Косметика: предмет рисуется своей картинкой item.<ключ>, а пока её нет — заглушкой слота slot.<ключ>.
  // z — порядок слоёв: питомец — 0, что меньше — за ним (гнездо), что больше — поверх.
  'slot.nest': slot('nest', -1),
  'slot.cloak': slot('cloak', 1),
  'slot.neck': slot('neck', 2),
  'slot.mask': slot('mask', 3),
  'slot.feathers': slot('feathers', 4),
};

/** Слои питомца снизу вверх: спрайт стадии и предметы. Неизвестная стадия рисуется первой. */
export function petLayers(stage: string, items: { key: string; slot: string }[]): Sprite[] {
  const base = assets[`pet.${stage}`] ?? PET;
  const worn = items.map((item) => assets[`item.${item.key}`] ?? assets[`slot.${item.slot}`]);
  return [base, ...worn.filter((sprite) => sprite !== undefined)].sort((a, b) => a.z - b.z);
}
