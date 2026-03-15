import { useState, type FormEvent } from 'react';
import { Button, Card, CardBody, CardHeader, Input } from '@heroui/react';
import { Icon } from '@iconify/react';
import eyeBold from '@iconify/icons-solar/eye-bold';
import eyeClosedLinear from '@iconify/icons-solar/eye-closed-linear';
import lockPasswordBold from '@iconify/icons-solar/lock-password-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import { useTranslation } from 'react-i18next';
import { changePassword } from '../api/auth';
import { getSavedUsername } from '../api/client';
import { ICON_SIZES } from '../constants/iconSizes';

export default function ChangePasswordPage() {
  const { t } = useTranslation();
  const [newUsername, setNewUsername] = useState('');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess(false);

    const savedUsername = getSavedUsername()?.trim();
    if (!savedUsername) { setError(t('auth.changePw.noSavedUsername')); return; }
    if (!oldPassword.trim()) { setError(t('auth.changePw.oldRequired')); return; }
    if (!newPassword.trim()) { setError(t('setup.accountPasswordRequired')); return; }
    if (newPassword !== confirm) { setError(t('setup.accountPasswordMismatch')); return; }
    if (newPassword.length < 8) { setError(t('setup.accountPasswordTooShort')); return; }

    setLoading(true);
    try {
      await changePassword(oldPassword, newPassword, newUsername);
      setSuccess(true);
      setNewUsername('');
      setOldPassword('');
      setNewPassword('');
      setConfirm('');
    } catch (err) {
      if (err instanceof Error && err.message === 'NO_SAVED_USERNAME') {
        setError(t('auth.changePw.noSavedUsername'));
      } else {
        setError(t('auth.changePw.failed'));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg">
      <Card>
        <CardHeader>
          <span className="font-semibold">{t('auth.changePw.title')}</span>
        </CardHeader>
        <CardBody>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <Input
              label={t('auth.changePw.newUsername')}
              placeholder={t('auth.changePw.newUsernamePlaceholder')}
              variant="bordered"
              value={newUsername}
              onValueChange={setNewUsername}
              startContent={<Icon icon={userRoundedBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
              autoComplete="username"
            />
            <Input
              isRequired
              label={t('auth.changePw.oldPassword')}
              variant="bordered"
              type={showPw ? 'text' : 'password'}
              value={oldPassword}
              onValueChange={setOldPassword}
              startContent={<Icon icon={lockPasswordBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
              autoComplete="current-password"
            />
            <Input
              isRequired
              label={t('auth.changePw.newPassword')}
              variant="bordered"
              type={showPw ? 'text' : 'password'}
              value={newPassword}
              onValueChange={setNewPassword}
              startContent={<Icon icon={lockPasswordBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
              endContent={
                <button type="button" onClick={() => setShowPw(p => !p)} aria-label={t('auth.login.togglePassword')}>
                  <Icon className="text-default-400 text-xl" icon={showPw ? eyeClosedLinear : eyeBold} />
                </button>
              }
              autoComplete="new-password"
            />
            <Input
              isRequired
              label={t('setup.confirmPassword')}
              variant="bordered"
              type={showPw ? 'text' : 'password'}
              value={confirm}
              onValueChange={setConfirm}
              startContent={<Icon icon={lockPasswordBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
              autoComplete="new-password"
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            {success && <p className="text-sm text-success">{t('auth.changePw.success')}</p>}
            <Button type="submit" color="primary" className="w-full" isLoading={loading}>
              {t('auth.changePw.submit')}
            </Button>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
