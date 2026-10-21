import type { Me } from '../api/client';
import { petLayers } from '../assets';
import { texts } from '../texts';

export type Pet = NonNullable<Me['pet']>;

type Props = {
  pet: Pet;
  tryOn?: string | null; // примерка: предмет поверх своего слота, без покупки
  small?: boolean;
};

/** Питомец слоями по манифесту ассетов: спрайт стадии и надетые предметы. */
export function PetView({ pet, tryOn, small }: Props) {
  const worn = new Map(pet.items.filter((item) => item.worn).map((item) => [item.slot, item]));
  const tried = pet.items.find((item) => item.key === tryOn);
  if (tried) worn.set(tried.slot, tried);
  return (
    <div className={small ? 'pet small' : 'pet'} role="img" aria-label={texts.pet.alt}>
      {petLayers(pet.stage, [...worn.values()]).map((sprite) => (
        <img key={`${sprite.z}:${sprite.src}`} src={sprite.src} alt="" />
      ))}
    </div>
  );
}
