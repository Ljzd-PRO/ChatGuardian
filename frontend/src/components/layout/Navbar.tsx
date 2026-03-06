import { Button, Select, SelectItem, Switch } from '@heroui/react';
import { Menu, Moon, Sun } from 'lucide-react';
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
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 py-3 bg-background/80 backdrop-blur border-b border-divider">
      <div className="flex items-center gap-3">
        <Button isIconOnly size="sm" variant="light" className="md:hidden" onPress={onMenuClick}>
          <Menu size={18} />
        </Button>
        <h1 className="text-base font-semibold text-default-900">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <Sun size={14} className="text-default-500" />
        <Switch
          size="sm"
          isSelected={isDark}
          onValueChange={toggle}
          aria-label={t('common.toggleDark')}
        />
        <Moon size={14} className="text-default-500" />
        <Select
          size="sm"
          aria-label={t('common.language')}
          selectedKeys={[currentLang]}
          className="w-[140px]"
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
