import { useEffect, useState } from 'react';

import { install, installOffer, onInstallChange, type InstallOffer as Offer } from '../platform/install';
import { texts } from '../texts';

/** Предложение поставить гнездо на экран: ярлык Telegram, установка PWA или подсказка для iOS. */
export function InstallOffer() {
  const [offer, setOffer] = useState<Offer>(null);

  useEffect(() => {
    const update = () => void installOffer().then(setOffer);
    update();
    return onInstallChange(update);
  }, []);

  if (offer === null) return null;
  if (offer === 'ios') return <p className="muted small">{texts.install.ios}</p>;
  return (
    <button
      className="link"
      onClick={() => {
        void install(offer);
        setOffer(null);
      }}
    >
      {offer === 'telegram' ? texts.install.telegram : texts.install.prompt}
    </button>
  );
}
