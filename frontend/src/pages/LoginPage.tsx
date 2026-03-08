import { useEffect, useState } from 'react';
import { Button, Card, CardBody, CardHeader, Input } from '@heroui/react';
import { Icon } from '@iconify/react';
import lockBold from '@iconify/icons-solar/lock-bold';
import userBold from '@iconify/icons-solar/user-bold';
import arrowRightBold from '@iconify/icons-solar/arrow-right-bold';
import shieldBold from '@iconify/icons-solar/shield-bold';
import { useLocation, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { fetchSetupStatus, login } from '../api/auth';
import { clearAuthToken, getAuthToken, setAuthToken } from '../api/client';

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState<string | null>(null);

  const fromPath = (location.state as { from?: string } | undefined)?.from ?? '/';

  const setupStatus = useQuery({ queryKey: ['setup-status'], queryFn: fetchSetupStatus });

  const mutation = useMutation({
    mutationFn: () => login(form),
    onSuccess: res => {
      setAuthToken(res.token);
      navigate(fromPath, { replace: true });
    },
    onError: () => {
      setError(t('auth.invalidCredentials'));
      clearAuthToken();
    },
  });

  useEffect(() => {
    if (getAuthToken()) {
      navigate('/', { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    if (setupStatus.data?.setup_required) {
      navigate('/setup', { replace: true });
    }
  }, [navigate, setupStatus.data?.setup_required]);

  const handleSubmit = async () => {
    setError(null);
    try {
      await mutation.mutateAsync();
    } catch (err) {
      if (err instanceof Error && err.message.includes('Setup required')) {
        navigate('/setup', { replace: true });
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-950 to-black flex items-center justify-center px-4">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.05),transparent_25%),radial-gradient(circle_at_80%_0,rgba(59,130,246,0.07),transparent_30%)]" />
      <Card className="relative max-w-xl w-full border border-white/10 bg-white/10 backdrop-blur-xl shadow-2xl">
        <CardHeader className="flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-primary/10 text-primary shadow-inner">
            <Icon icon={shieldBold} fontSize={26} />
          </div>
          <div>
            <p className="text-xl font-semibold text-white">{t('auth.loginTitle')}</p>
            <p className="text-sm text-white/70">{t('auth.loginSubtitle')}</p>
          </div>
        </CardHeader>
        <CardBody className="space-y-5">
          <Input
            aria-label={t('auth.username')}
            label={t('auth.username')}
            labelPlacement="outside"
            variant="bordered"
            radius="lg"
            startContent={<Icon icon={userBold} fontSize={18} className="text-default-500" />}
            value={form.username}
            onValueChange={v => setForm(f => ({ ...f, username: v }))}
            isRequired
            autoFocus
            classNames={{
              label: 'text-default-200',
              input: 'text-white',
              inputWrapper: 'bg-white/5 border-white/15',
            }}
          />
          <Input
            aria-label={t('auth.password')}
            label={t('auth.password')}
            labelPlacement="outside"
            type="password"
            variant="bordered"
            radius="lg"
            startContent={<Icon icon={lockBold} fontSize={18} className="text-default-500" />}
            value={form.password}
            onValueChange={v => setForm(f => ({ ...f, password: v }))}
            isRequired
            classNames={{
              label: 'text-default-200',
              input: 'text-white',
              inputWrapper: 'bg-white/5 border-white/15',
            }}
          />
          {error && <p className="text-danger text-sm">{error}</p>}
          <Button
            color="primary"
            className="w-full"
            size="lg"
            radius="lg"
            endContent={<Icon icon={arrowRightBold} fontSize={18} />}
            isLoading={mutation.isPending}
            onPress={handleSubmit}
          >
            {t('auth.login')}
          </Button>
          <p className="text-xs text-default-400 text-center">{t('auth.noAccountHint')}</p>
        </CardBody>
      </Card>
    </div>
  );
}
