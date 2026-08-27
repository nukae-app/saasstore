'use client';

import { useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Link } from '../../../i18n/navigation';
import { useRouter } from '../../../i18n/navigation';
import { Loader2, Mail, Lock, UserPlus, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../../components/store/AuthProvider';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';
import { useTenantConfig } from '../../../components/store/useTenantConfig';

const TAB = { password: 'password', magic: 'magic', register: 'register' };

export default function LoginClient() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('login');
  const tenantConfig = useTenantConfig();
  const { user, login } = useAuth();
  const [tab, setTab] = useState(TAB.password);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [nombre, setNombre] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [unverifiedEmail, setUnverifiedEmail] = useState('');
  const [resendState, setResendState] = useState('idle'); // idle | sending | sent

  if (user) {
    router.replace('/compte');
    return null;
  }

  async function handlePasswordLogin(e) {
    e.preventDefault();
    setLoading(true); setError(''); setUnverifiedEmail(''); setResendState('idle');
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    setLoading(false);
    if (res.ok) {
      const { access_token } = await res.json();
      login(access_token);
      router.replace('/compte');
    } else {
      const d = await res.json().catch(() => ({}));
      setError(d.detail || t('invalidCredentials'));
      if (res.status === 403 && d.detail?.includes('Confirma el teu email')) setUnverifiedEmail(email);
    }
  }

  async function handleResend() {
    setResendState('sending');
    await fetch('/api/auth/resend-verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: unverifiedEmail }),
    });
    setResendState('sent');
  }

  async function handleRegister(e) {
    e.preventDefault();
    if (password.length < 8) { setError(t('passwordMinLength')); return; }
    setLoading(true); setError('');
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name: nombre || undefined, language: locale }),
    });
    setLoading(false);
    if (res.ok) {
      setSent(true);
    } else {
      const d = await res.json().catch(() => ({}));
      setError(d.detail || t('registerFailed'));
    }
  }

  async function handleMagicLink(e) {
    e.preventDefault();
    setLoading(true); setError('');
    const res = await fetch('/api/auth/magic-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, language: locale }),
    });
    setLoading(false);
    if (res.ok) setSent(true);
    else setError(t('sendEmailFailed'));
  }

  const tabs = [
    { id: TAB.password, label: t('tabPassword'), icon: Lock },
    { id: TAB.magic,    label: t('tabMagicLink'),  icon: Mail },
    { id: TAB.register, label: t('tabRegister'), icon: UserPlus },
  ];

  return (
    <>
      <StorefrontNav />
      <main className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <h1 className="font-serif italic text-3xl mb-2">
              {tab === TAB.register ? t('createAccount') : t('login')}
            </h1>
            <p className="text-zinc-500 text-sm">
              {tab === TAB.password && t('loginWithEmailPassword')}
              {tab === TAB.magic && t('magicLinkSubtitle')}
              {tab === TAB.register && t('createAccountSubtitle', { shopName: tenantConfig.nombre })}
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] shadow-sm overflow-hidden">
            {/* Tabs */}
            <div className="flex border-b border-zinc-100">
              {tabs.map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => { setTab(id); setError(''); setSent(false); setUnverifiedEmail(''); }}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-medium transition-colors ${tab === id ? 'border-b-2 border-zinc-900 text-zinc-900' : 'text-zinc-500 hover:text-zinc-600'}`}>
                  <Icon size={13} />{label}
                </button>
              ))}
            </div>

            <div className="p-8">
              {/* Password login */}
              {tab === TAB.password && (
                <form onSubmit={handlePasswordLogin} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">Email</label>
                    <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                      placeholder={t('emailPlaceholder')}
                      className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('password')}</label>
                    <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                  {error && <p className="text-sm text-red-500">{error}</p>}
                  {unverifiedEmail && (
                    <p className="text-xs text-zinc-500">
                      {resendState === 'sent'
                        ? t('resentConfirmation')
                        : (
                          <>
                            {t('didntReceiveIt')}{' '}
                            <button type="button" onClick={handleResend} disabled={resendState === 'sending'}
                              className="text-zinc-900 hover:text-zinc-700 underline disabled:opacity-60">
                              {resendState === 'sending' ? t('sending') : t('resend')}
                            </button>
                          </>
                        )}
                    </p>
                  )}
                  <button type="submit" disabled={loading}
                    className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-zinc-800 text-white py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-60">
                    {loading ? <Loader2 size={15} className="animate-spin" /> : <Lock size={15} />}
                    {loading ? t('loggingIn') : t('login')}
                  </button>
                  <button type="button" onClick={() => { setTab(TAB.magic); setError(''); }}
                    className="w-full text-center text-xs text-zinc-500 hover:text-zinc-600 transition-colors">
                    {t('forgotPassword')}
                  </button>
                </form>
              )}

              {/* Magic link */}
              {tab === TAB.magic && !sent && (
                <form onSubmit={handleMagicLink} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">Email</label>
                    <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                      placeholder={t('emailPlaceholder')}
                      className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                  {error && <p className="text-sm text-red-500">{error}</p>}
                  <button type="submit" disabled={loading}
                    className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-zinc-800 text-white py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-60">
                    {loading ? <Loader2 size={15} className="animate-spin" /> : <Mail size={15} />}
                    {loading ? t('sending') : t('sendMeTheLink')}
                  </button>
                </form>
              )}

              {tab === TAB.magic && sent && (
                <div className="text-center">
                  <div className="w-14 h-14 bg-zinc-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Mail size={24} className="text-zinc-900" />
                  </div>
                  <h2 className="font-serif italic text-xl mb-2">{t('checkYourEmail')}</h2>
                  <p className="text-zinc-500 text-sm mb-1">{t('accessLinkSentTo')}</p>
                  <p className="font-medium text-zinc-800 text-sm mb-4">{email}</p>
                  <p className="text-zinc-500 text-xs mb-6">{t('linkExpires15min')}</p>
                  <button onClick={() => { setSent(false); setEmail(''); }}
                    className="text-sm text-zinc-500 hover:text-zinc-700 flex items-center gap-1 mx-auto transition-colors">
                    <ArrowLeft size={13} /> {t('changeEmail')}
                  </button>
                </div>
              )}

              {/* Registre */}
              {tab === TAB.register && sent && (
                <div className="text-center">
                  <div className="w-14 h-14 bg-zinc-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Mail size={24} className="text-zinc-900" />
                  </div>
                  <h2 className="font-serif italic text-xl mb-2">{t('checkYourEmail')}</h2>
                  <p className="text-zinc-500 text-sm mb-1">{t('confirmationLinkSentTo')}</p>
                  <p className="font-medium text-zinc-800 text-sm mb-4">{email}</p>
                  <p className="text-zinc-500 text-xs mb-6">{t('clickToActivate')}</p>
                  <button onClick={() => { setSent(false); setEmail(''); setPassword(''); setNombre(''); }}
                    className="text-sm text-zinc-500 hover:text-zinc-700 flex items-center gap-1 mx-auto transition-colors">
                    <ArrowLeft size={13} /> {t('changeEmail')}
                  </button>
                </div>
              )}
              {tab === TAB.register && !sent && (
                <form onSubmit={handleRegister} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('nameOptional')}</label>
                    <input type="text" value={nombre} onChange={e => setNombre(e.target.value)}
                      placeholder={t('yourName')}
                      className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">Email</label>
                    <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                      placeholder={t('emailPlaceholder')}
                      className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('password')}</label>
                    <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                      placeholder={t('min8Chars')}
                      className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                  {error && <p className="text-sm text-red-500">{error}</p>}
                  <button type="submit" disabled={loading}
                    className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-zinc-800 text-white py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-60">
                    {loading ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />}
                    {loading ? t('creatingAccount') : t('createAccount')}
                  </button>
                </form>
              )}

              {/* Google (no al tab de registre: ja inclòs implícitament) */}
              {tab !== TAB.register && (
                <>
                  <div className="relative my-5">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-zinc-100" />
                    </div>
                    <div className="relative flex justify-center text-xs text-zinc-500">
                      <span className="bg-white px-3">{t('orContinueWith')}</span>
                    </div>
                  </div>
                  <a href={`/api/auth/google/login?locale=${locale}`}
                    className="w-full flex items-center justify-center gap-3 border border-zinc-200 hover:bg-zinc-50 py-2.5 rounded-lg text-sm font-medium text-zinc-700 transition-colors">
                    <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden>
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    {t('continueWithGoogle')}
                  </a>
                </>
              )}

              <p className="text-center text-xs text-zinc-500 mt-6">
                {t('byLoggingInYouAccept')}{' '}
                <Link href="/termes" className="underline hover:text-zinc-700">{t('termsOfUse')}</Link>
                {' '}{t('and')}{' '}
                <Link href="/privacitat" className="underline hover:text-zinc-700">{t('privacyPolicy')}</Link>.
              </p>
            </div>
          </div>

          <p className="text-center text-xs text-zinc-500 mt-6">
            <Link href="/" className="hover:text-zinc-700 transition-colors">{t('backToShop')}</Link>
          </p>
        </div>
      </main>
      <StorefrontFooter />
    </>
  );
}
