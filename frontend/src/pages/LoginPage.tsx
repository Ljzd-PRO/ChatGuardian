import { useEffect, useState } from 'react';
import { Button, Card, CardBody, CardHeader, Input } from '@heroui/react';
import { Icon } from '@iconify/react';
import lockBold from '@iconify/icons-solar/lock-bold';
import userBold from '@iconify/icons-solar/user-bold';
import arrowRightBold from '@iconify/icons-solar/arrow-right-bold';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthActions, useAuthStatus } from '../hooks/useAuth';

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { data } = useAuthStatus();
  const { login } = useAuthActions();
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data?.setup_required) {
      navigate('/setup', { replace: true });
    } else if (data?.authenticated) {
      navigate('/', { replace: true });
    }
  }, [data, navigate]);

  const fromPath = (location.state as { from?: string } | undefined)?.from ?? '/';

  async function handleLogin() {
    setError(null);
    login.mutate(
      { username: form.username.trim(), password: form.password },
      {
        onSuccess: () => navigate(fromPath, { replace: true }),
        onError: err => setError((err as Error).message),
      },
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-950 to-black flex items-center justify-center px-4">
      <Card className="max-w-xl w-full border border-white/10 bg-white/5 backdrop-blur-lg shadow-2xl">
        <CardHeader className="flex items-center gap-3">
          <div className="p-2 rounded-full bg-primary/10 text-primary">
            <Icon icon={lockBold} fontSize={22} />
          </div>
          <div>
            <p className="text-xl font-semibold text-default-900">{t('auth.loginTitle')}</p>
            <p className="text-sm text-default-500">{t('auth.loginSubtitle')}</p>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <Input
            aria-label={t('auth.username')}
            label={t('auth.username')}
            startContent={<Icon icon={userBold} fontSize={18} className="text-default-400" />}
            value={form.username}
            onValueChange={v => setForm(f => ({ ...f, username: v }))}
            isRequired
          />
          <Input
            aria-label={t('auth.password')}
            label={t('auth.password')}
            type="password"
            startContent={<Icon icon={lockBold} fontSize={18} className="text-default-400" />}
            value={form.password}
            onValueChange={v => setForm(f => ({ ...f, password: v }))}
            isRequired
          />
          {error && <p className="text-danger text-sm">{error}</p>}
          <Button
            color="primary"
            className="w-full"
            endContent={<Icon icon={arrowRightBold} fontSize={18} />}
            isLoading={login.isPending}
            onPress={handleLogin}
          >
            {t('auth.login')}
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}
