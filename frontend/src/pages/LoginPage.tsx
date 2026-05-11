import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Mail, Lock, ArrowRight, Loader } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { ApiError, api, tokenStore } from '../services/api';
import styles from './LoginPage.module.css';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  // ── Handle OAuth callback from URL hash ──────────────────────────
  useEffect(() => {
    // Supabase Implicit Flow puts the token in the URL hash fragment
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const supabaseAccessToken = hash.get('access_token');
    const errorDescription = hash.get('error_description');

    if (errorDescription) {
      setError(decodeURIComponent(errorDescription.replace(/\+/g, ' ')));
      window.history.replaceState(null, '', '/login'); // clean up URL
      return;
    }

    if (!supabaseAccessToken) {
      return; // Normal page visit, not an OAuth callback
    }

    const finishSupabaseLogin = async () => {
      try {
        setLoading(true);
        setError('');
        
        // Send Supabase token to Python backend to get our app JWT
        const result = await api.auth.supabaseSession(supabaseAccessToken);
        tokenStore.set(result.access_token);
        
        // Clean the URL hash so the token doesn't stay in browser history
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
    setLoading(true);

    try {
      const result = mode === 'login'
        ? await api.auth.login(email, password)
        : await api.auth.signup(email, password, fullName);

      tokenStore.set(result.access_token);
      navigate('/home');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to authenticate right now.');
    } finally {
      setLoading(false);
    }
  };

  // ── Google OAuth ──────────────────────────────────────────────────
  const handleGoogleLogin = () => {
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
    
    if (!supabaseUrl) {
      setError('VITE_SUPABASE_URL is missing in frontend/.env');
      return;
    }

    const redirectTo = `${window.location.origin}/login`;
    
    // Redirect directly to Supabase Auth (no JS SDK needed)
    const url = new URL(`${supabaseUrl.replace(/\/$/, '')}/auth/v1/authorize`);
    url.searchParams.set('provider', 'google');
    url.searchParams.set('redirect_to', redirectTo);
    
    window.location.href = url.toString();
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
              <span>🔷</span> Continue with Google
            </motion.button>
            <motion.button
              type="button"
              className={styles.socialBtn}
              variants={itemVariants}
              onClick={() => setError('Apple login is not configured yet.')}
            >
              <span>🍎</span> Continue with Apple
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