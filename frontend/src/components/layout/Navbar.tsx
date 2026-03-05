import { Button, Switch } from '@heroui/react';
import { Menu, Moon, Sun } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

interface TopNavbarProps {
  onMenuClick: () => void;
  title: string;
}

export default function TopNavbar({ onMenuClick, title }: TopNavbarProps) {
  const { isDark, toggle } = useTheme();

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
          aria-label="Toggle dark mode"
        />
        <Moon size={14} className="text-default-500" />
      </div>
    </header>
  );
}
