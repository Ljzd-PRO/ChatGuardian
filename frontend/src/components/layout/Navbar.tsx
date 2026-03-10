import { Button, Select, SelectItem } from '@heroui/react';
import { Icon } from '@iconify/react';
import hamburgerMenuBold from '@iconify/icons-solar/hamburger-menu-bold';
import moonBold from '@iconify/icons-solar/moon-bold';
import sun2Bold from '@iconify/icons-solar/sun-2-bold';
import earthBold from '@iconify/icons-solar/earth-bold';
import exitBold from '@iconify/icons-solar/exit-bold';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../hooks/useTheme';
import { supportedLanguages } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

interface TopNavbarProps {
  onMenuClick: () => void;
  title: string;
}

export default function TopNavbar({ onMenuClick, title }: TopNavbarProps) {
  const { t, i18n } = useTranslation();
  const { isDark, toggle } = useTheme();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const resolved = i18n.resolvedLanguage ?? i18n.language;
  const currentLang = supportedLanguages.some(l => l.code === resolved) ? resolved : 'en';

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-6 py-4 bg-background/80 backdrop-blur border-b border-divider">
      <div className="flex items-center gap-4">
        <Button isIconOnly size="md" variant="light" className="md:hidden" onPress={onMenuClick}>
          <Icon icon={hamburgerMenuBold} fontSize={22} />
        </Button>
        <h1 className="hidden md:block text-lg md:text-xl font-semibold text-default-900">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        <Icon icon={earthBold} fontSize={18} className="text-default-500" />
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
        <Button
          isIconOnly
          size="md"
          variant="flat"
          color={isDark ? 'secondary' : 'warning'}
          onPress={toggle}
          aria-label={t('common.toggleDark')}
        >
          <Icon icon={isDark ? moonBold : sun2Bold} fontSize={20} />
        </Button>
        <Button
          isIconOnly
          size="md"
          variant="flat"
          color="danger"
          onPress={handleLogout}
          aria-label={t('auth.logout')}
        >
          <Icon icon={exitBold} fontSize={20} />
        </Button>
      </div>
    </header>
  );
}
