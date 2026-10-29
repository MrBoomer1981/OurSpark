import type { CSSProperties } from 'react';

import { pictures } from '../assets';

type Props = {
  name: string; // логическое имя без префикса: spark → icon.spark в манифесте
  scale?: number; // во сколько раз увеличить: только целое, чтобы пиксели не расплывались
  className?: string;
  style?: CSSProperties;
};

/** Пиксельная иконка из манифеста. Украшение: смысл всегда есть и в тексте рядом. */
export function Icon({ name, scale = 2, className, style }: Props) {
  const picture = pictures[`icon.${name}`];
  if (!picture) return null;
  return (
    <img
      className={className ? `icon ${className}` : 'icon'}
      src={picture.src}
      width={picture.width * scale}
      height={picture.height * scale}
      style={style}
      alt=""
      aria-hidden="true"
    />
  );
}
