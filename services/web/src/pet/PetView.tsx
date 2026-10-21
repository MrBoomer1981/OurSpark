import { assets, type AssetName } from '../assets';
import { texts } from '../texts';

/** Питомец по манифесту ассетов. Пока один кадр-заглушка; стадии и косметика — этап 3. */
export function PetView({ sprite }: { sprite: AssetName }) {
  const { src, width, height } = assets[sprite];
  return <img className="pet" src={src} width={width} height={height} alt={texts.pet.alt} />;
}
