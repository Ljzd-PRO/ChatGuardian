import { useState, useEffect, type FormEvent } from 'react';
import { Button, Input, Card, CardBody, Spinner } from '@heroui/react';
import { Icon } from '@iconify/react';
import eyeBold from '@iconify/icons-solar/eye-bold';
import eyeClosedLinear from '@iconify/icons-solar/eye-closed-linear';
import lockPasswordBold from '@iconify/icons-solar/lock-password-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Navigate, useNavigate } from 'react-router-dom';
import { ICON_SIZES } from '../constants/iconSizes';

export default function LoginPage() {
  const { t } = useTranslation();
  const { login, loading: authLoading, setupRequired, authenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = `${t('auth.login.title')} - ${t('common.appName')}`;
  }, [t]);
  const [loading, setLoading] = useState(false);

  // Redirect to setup if credentials not yet configured
  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-default-50">
        <Spinner size="lg" />
      </div>
    );
  }
  if (setupRequired) return <Navigate to="/setup" replace />;
  if (authenticated) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError(t('auth.login.required'));
      return;
    }
    setLoading(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch {
      setError(t('auth.login.failed'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-default-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardBody className="px-8 pt-8 pb-10">
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-bold text-primary">{t('common.appName')}</h1>
            <p className="mt-2 text-default-500">{t('auth.login.subtitle')}</p>
          </div>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <Input
              isRequired
              label={t('auth.login.username')}
              labelPlacement="outside"
              placeholder={t('auth.login.usernamePlaceholder')}
              variant="bordered"
              value={username}
              onValueChange={setUsername}
              startContent={
                <Icon icon={userRoundedBold} fontSize={ICON_SIZES.input} className="text-default-400" />
              }
              autoComplete="username"
            />
            <Input
              isRequired
              label={t('auth.login.password')}
              labelPlacement="outside"
              placeholder={t('auth.login.passwordPlaceholder')}
              variant="bordered"
              classNames={{ input: 'login-password-native-toggle-hidden' }}
              type={showPw ? 'text' : 'password'}
              value={password}
              onValueChange={setPassword}
              startContent={
                <Icon icon={lockPasswordBold} fontSize={ICON_SIZES.input} className="text-default-400" />
              }
              endContent={
                <button type="button" onClick={() => setShowPw(p => !p)} aria-label={t('auth.login.togglePassword')}>
                  <Icon
                    className="text-default-400 pointer-events-none text-xl"
                    icon={showPw ? eyeClosedLinear : eyeBold}
                  />
                </button>
              }
              autoComplete="current-password"
            />
            {error && (
              <p className="text-sm text-danger">{error}</p>
            )}
            <Button
              type="submit"
              color="primary"
              className="mt-2 w-full"
              isLoading={loading}
            >
              {t('auth.login.submit')}
            </Button>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
