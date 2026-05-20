import React, { useEffect, useState } from 'react';
import { Eye, EyeOff, Mail, Lock, ArrowRight, Loader } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import { motion } from '../components/ui/staticMotion';
import { ApiError, api, tokenStore } from '../services/api';
import styles from './LoginPage.module.css';

const oauthErrorMessages: Record<string, string> = {
  oauth_failed: 'Google sign-in could not be completed. Please try again.',
  missing_code: 'Google did not return a login code. Please try again.',
  auth_failed: 'Google sign-in succeeded, but the app could not create your session.',
  access_denied: 'Google sign-in was cancelled.',
};

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const backendAccessToken = query.get('access_token');
    const supabaseAccessToken = hash.get('access_token');
    const rawError = query.get('error') || hash.get('error_description');

    if (rawError) {
      const decodedError = decodeURIComponent(rawError.replace(/\+/g, ' '));
      setError(oauthErrorMessages[decodedError] || decodedError);
      window.history.replaceState(null, '', '/login');
      return;
    }

    if (backendAccessToken) {
      tokenStore.set(backendAccessToken);
      window.history.replaceState(null, '', '/login');
      navigate('/home');
      return;
    }

    if (!supabaseAccessToken) {
      return; // Normal page visit, not an OAuth callback
    }

    const finishSupabaseLogin = async () => {
      try {
        setLoading(true);
        setError('');
        
        const result = await api.auth.supabaseSession(supabaseAccessToken);
        tokenStore.set(result.access_token);

        window.history.replaceState(null, '', '/login');
        navigate('/home');
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Google login failed.');
        window.history.replaceState(null, '', '/login');
      } finally {
        setLoading(false);
      }
    };

    finishSupabaseLogin();
  }, [navigate]);

  // ── Email / Password submit ───────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError('Enter your email and password.');
      return;
    }

    if (mode === 'signup' && !fullName.trim()) {
      setError('Enter your full name to create an account.');
      return;
    }

    setLoading(true);

    try {
      const result = mode === 'login'
        ? await api.auth.login(trimmedEmail, password)
        : await api.auth.signup(trimmedEmail, password, fullName.trim());

      tokenStore.set(result.access_token);
      navigate('/home');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to authenticate right now.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');

    try {
      const result = await api.auth.google();
      window.location.href = result.url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Google login is not available right now.');
      setLoading(false);
    }
  };

  // ── Animation variants ────────────────────────────────────────────
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: 'easeOut' },
    },
  };

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className={styles.loginPage}>
      <ImmersiveStage variant="ambient" />
      {/* Left Side - Branding */}
      <motion.div
        className={styles.leftPanel}
        initial={{ opacity: 0, x: -50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.8 }}
      >
        <div className={styles.brandContent}>
          <motion.div
            className={styles.logo}
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 4, repeat: Infinity }}
          >
            <div className={styles.logoIcon}>⚡</div>
            <span>intervue.ai</span>
          </motion.div>

          <motion.h1 variants={itemVariants}>Welcome Back</motion.h1>

          <motion.p variants={itemVariants}>
            Continue your interview preparation journey and crush your next interview.
          </motion.p>

          <motion.div
            className={styles.featureBullets}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {['AI-Powered Practice', 'Real-time Feedback', 'Progress Tracking'].map((feature, i) => (
              <motion.div key={i} className={styles.bullet} variants={itemVariants}>
                <span className={styles.checkmark}>✓</span>
                {feature}
              </motion.div>
            ))}
          </motion.div>

          <motion.div
            className={styles.illustration}
            variants={itemVariants}
            animate={{ y: [0, 20, 0] }}
            transition={{ duration: 5, repeat: Infinity }}
          >
            <div className={styles.shape}></div>
          </motion.div>
        </div>
      </motion.div>

      {/* Right Side - Form */}
      <motion.div
        className={styles.rightPanel}
        initial={{ opacity: 0, x: 50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.8 }}
      >
        <motion.div
          className={styles.formContainer}
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <motion.div variants={itemVariants}>
            <h2>{mode === 'login' ? 'Login to Your Account' : 'Create Your Account'}</h2>
            <p>{mode === 'login' ? 'Sign in with your email and password' : 'Start with your name, email, and password'}</p>
          </motion.div>

          <form onSubmit={handleSubmit} className={styles.form}>
            {mode === 'signup' && (
              <motion.div className={styles.formGroup} variants={itemVariants}>
                <label htmlFor="fullName">Full Name</label>
                <div className={styles.inputWrapper}>
                  <Mail size={20} className={styles.inputIcon} />
                  <input
                    type="text"
                    id="fullName"
                    placeholder="Adarsh Kumar"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className={styles.input}
                    required={mode === 'signup'}
                  />
                </div>
              </motion.div>
            )}

            <motion.div className={styles.formGroup} variants={itemVariants}>
              <label htmlFor="email">Email Address</label>
              <div className={styles.inputWrapper}>
                <Mail size={20} className={styles.inputIcon} />
                <input
                  type="email"
                  id="email"
                  placeholder="you@gmail.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={styles.input}
                  required
                />
              </div>
            </motion.div>

            <motion.div className={styles.formGroup} variants={itemVariants}>
              <label htmlFor="password">Password</label>
              <div className={styles.inputWrapper}>
                <Lock size={20} className={styles.inputIcon} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={styles.input}
                  required
                />
                <button
                  type="button"
                  className={styles.togglePassword}
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </motion.div>

            <motion.div className={styles.checkboxGroup} variants={itemVariants}>
              <label>
                <input type="checkbox" />
                <span>Remember me</span>
              </label>
              <a href="#forgot">Forgot password?</a>
            </motion.div>

            <motion.button
              type="submit"
              className={styles.submitBtn}
              variants={itemVariants}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader size={20} className={styles.spinner} />
                  {mode === 'login' ? 'Signing in...' : 'Creating account...'}
                </>
              ) : (
                <>
                  {mode === 'login' ? 'Sign In' : 'Create Account'}
                  <ArrowRight size={18} />
                </>
              )}
            </motion.button>
            {error && <p className={styles.errorMessage}>{error}</p>}
          </form>

          <motion.div className={styles.divider} variants={itemVariants}>
            <span>OR</span>
          </motion.div>

          <motion.div
            className={styles.socialLogin}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <motion.button type="button" className={styles.socialBtn} variants={itemVariants} onClick={handleGoogleLogin}>
              <span>G</span> Continue with Google
            </motion.button>
          </motion.div>

          <motion.p className={styles.signupLink} variants={itemVariants}>
            {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <button type="button" onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
              {mode === 'login' ? 'Sign up for free' : 'Sign in'}
            </button>
          </motion.p>
        </motion.div>
      </motion.div>

      {/* Animated Background Elements */}
      <div className={styles.bgElements}>
        <motion.div
          className={styles.bgElement1}
          animate={{ rotate: 360, x: [0, 20, 0], y: [0, 30, 0] }}
          transition={{
            rotate: { duration: 20, repeat: Infinity, ease: 'linear' },
            x: { duration: 6, repeat: Infinity, ease: 'easeInOut' },
            y: { duration: 8, repeat: Infinity, ease: 'easeInOut' },
          }}
        />
        <motion.div
          className={styles.bgElement2}
          animate={{ rotate: -360, x: [0, -30, 0], y: [0, -20, 0] }}
          transition={{
            rotate: { duration: 25, repeat: Infinity, ease: 'linear' },
            x: { duration: 7, repeat: Infinity, ease: 'easeInOut' },
            y: { duration: 9, repeat: Infinity, ease: 'easeInOut' },
          }}
        />
      </div>
    </div>
  );
};

export default LoginPage;
