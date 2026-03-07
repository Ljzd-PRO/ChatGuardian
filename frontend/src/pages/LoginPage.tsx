import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, CardBody, Input } from '@heroui/react';
import { Icon } from '@iconify/react';
import eyeBold from '@iconify/icons-solar/eye-bold';
import eyeClosedBold from '@iconify/icons-solar/eye-closed-bold';
import lockBold from '@iconify/icons-solar/lock-bold';
import shieldCheckBold from '@iconify/icons-solar/shield-check-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) return;
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch {
      setError(t('auth.login.error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-default-50 via-default-100 to-default-200 dark:from-[#0d0d1a] dark:via-[#13131f] dark:to-[#1a1a2e] px-4">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-4">
            <Icon icon={shieldCheckBold} className="text-primary" fontSize={32} />
          </div>
          <h1 className="text-3xl font-bold text-default-900">{t('common.appName')}</h1>
          <p className="text-default-500 mt-1">{t('auth.login.subtitle')}</p>
        </div>

        {/* Login card */}
        <Card className="shadow-xl border border-default-200/60 dark:border-default-100/10 bg-background/80 backdrop-blur-sm">
          <CardBody className="p-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              <Input
                label={t('auth.login.username')}
                placeholder={t('auth.login.usernamePlaceholder')}
                value={username}
                onValueChange={setUsername}
                startContent={<Icon icon={userRoundedBold} className="text-default-400" fontSize={18} />}
                variant="bordered"
                autoFocus
                isRequired
              />
              <Input
                label={t('auth.login.password')}
                placeholder={t('auth.login.passwordPlaceholder')}
                value={password}
                onValueChange={setPassword}
                type={showPassword ? 'text' : 'password'}
                startContent={<Icon icon={lockBold} className="text-default-400" fontSize={18} />}
                endContent={
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="text-default-400 hover:text-default-600 transition-colors"
                  >
                    <Icon icon={showPassword ? eyeClosedBold : eyeBold} fontSize={18} />
                  </button>
                }
                variant="bordered"
                isRequired
              />

              {error && (
                <div className="text-danger text-sm bg-danger-50 dark:bg-danger/10 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                color="primary"
                className="w-full font-semibold"
                size="lg"
                isLoading={loading}
                isDisabled={!username || !password || loading}
              >
                {loading ? t('auth.login.loading') : t('auth.login.loginButton')}
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
