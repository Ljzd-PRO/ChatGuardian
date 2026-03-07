import { Button, Select, SelectItem, Switch } from '@heroui/react';
import { Icon } from '@iconify/react';
import hamburgerMenuBold from '@iconify/icons-solar/hamburger-menu-bold';
import moonBold from '@iconify/icons-solar/moon-bold';
import sun2Bold from '@iconify/icons-solar/sun-2-bold';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../hooks/useTheme';
import { supportedLanguages } from '../../i18n';

interface TopNavbarProps {
  onMenuClick: () => void;
  title: string;
}

export default function TopNavbar({ onMenuClick, title }: TopNavbarProps) {
  const { t, i18n } = useTranslation();
  const { isDark, toggle } = useTheme();
  const resolved = i18n.resolvedLanguage ?? i18n.language;
  const currentLang = supportedLanguages.some(l => l.code === resolved) ? resolved : 'en';

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-6 py-4 bg-background/80 backdrop-blur border-b border-divider">
      <div className="flex items-center gap-4">
        <Button isIconOnly size="md" variant="light" className="md:hidden" onPress={onMenuClick}>
          <Icon icon={hamburgerMenuBold} fontSize={22} />
        </Button>
        <h1 className="text-lg md:text-xl font-semibold text-default-900">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        <Icon icon={sun2Bold} fontSize={18} className="text-default-500" />
        <Switch
          size="md"
          isSelected={isDark}
          onValueChange={toggle}
          aria-label={t('common.toggleDark')}
        />
        <Icon icon={moonBold} fontSize={18} className="text-default-500" />
        <Select
          size="md"
          aria-label={t('common.language')}
          selectedKeys={[currentLang]}
          className="w-[170px]"
          onSelectionChange={keys => {
            const lng = Array.from(keys)[0] as string | undefined;
            if (lng) i18n.changeLanguage(lng);
          }}
        >
          {supportedLanguages.map(lang => (
            <SelectItem key={lang.code}>{lang.label}</SelectItem>
          ))}
        </Select>
      </div>
    </header>
  );
}
