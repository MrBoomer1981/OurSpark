/**
 * Манифест ассетов: код обращается к графике только по логическому имени.
 * Пути, размеры и число кадров живут здесь — заменить заглушку значит поменять запись,
 * а не код экранов. Файлы — в public/assets/.
 */
export type Sprite = { src: string; width: number; height: number; frames: number };

export const assets = {
  'pet.hatchling': { src: '/assets/pet/placeholder.svg', width: 16, height: 16, frames: 1 },
} as const satisfies Record<string, Sprite>;

export type AssetName = keyof typeof assets;
