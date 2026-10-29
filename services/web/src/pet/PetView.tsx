import { useEffect, useState, type CSSProperties } from 'react';

import type { Me } from '../api/client';
import { petLayers, petSprite, type Mood, type Sprite } from '../assets';
import { texts } from '../texts';

export type Pet = NonNullable<Me['pet']>;

type Props = {
  pet: Pet;
  tryOn?: string | null; // примерка: предмет поверх своего слота, без покупки
  small?: boolean;
  cheer?: boolean; // питомец радуется: несколько взмахов при появлении экрана, потом покой
};

const CHEER_MS = 2400;

/** Питомец слоями по манифесту ассетов: спрайт стадии и надетые предметы. Кадры анимации — из манифеста. */
export function PetView({ pet, tryOn, small, cheer }: Props) {
  const [mood, setMood] = useState<Mood>(cheer ? 'cheer' : 'idle');

  useEffect(() => {
    if (!cheer) return;
    setMood('cheer');
    const timer = setTimeout(() => setMood('idle'), CHEER_MS);
    return () => clearTimeout(timer);
  }, [cheer]);

  const worn = new Map(pet.items.filter((item) => item.worn).map((item) => [item.slot, item]));
  const tried = pet.items.find((item) => item.key === tryOn);
  if (tried) worn.set(tried.slot, tried);
  const base = petSprite(pet.stage, mood);
  // Доля пустых рядов под лапами: на сцене Гнезда питомец опускается на столько, чтобы стоять на земле.
  const baseline = { '--baseline': (base.baseline ?? 0) / base.height } as CSSProperties;
  return (
    <div
      className={['pet', small && 'small', mood === 'cheer' && 'cheering'].filter(Boolean).join(' ')}
      role="img"
      aria-label={texts.pet.alt}
      style={baseline}
    >
      {petLayers(pet.stage, mood, [...worn.values()]).map((sprite) => (
        <span
          key={`${sprite.z}:${sprite.src}`}
          className={sprite.frames > 1 ? 'sprite animated' : 'sprite'}
          style={spriteStyle(sprite)}
        />
      ))}
    </div>
  );
}

/** Картинка слоя растянута на все кадры; анимация в index.css сдвигает её покадрово. */
function spriteStyle(sprite: Sprite): CSSProperties {
  return {
    backgroundImage: `url(${sprite.src})`,
    backgroundSize: `${sprite.frames * 100}% 100%`,
    '--frames': sprite.frames,
    '--duration': `${sprite.frames / Math.max(sprite.fps, 1)}s`,
  } as CSSProperties;
}
