import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, BarChart3, Zap, Brain, TrendingUp } from 'lucide-react';
import { ImmersiveStage } from '../components/immersive/ImmersiveStage';
import { api } from '../services/api';
import styles from './LandingPage.module.css';

const LandingPage: React.FC = () => {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api.health()
      .then(setApiOnline)
      .catch(() => setApiOnline(false));
  }, []);

  const goToLogin = () => {
    window.location.href = '/login';
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2,
        delayChildren: 0.3,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.8, ease: 'easeOut' },
    },
  };

  const floatVariants = {
    initial: { y: 0 },
    animate: {
      y: [0, -20, 0],
      transition: { duration: 4, repeat: Infinity, ease: 'easeInOut' },
    },
  };

  const features = [
    {
      icon: <Brain className={styles.featureIcon} />,
      title: 'AI-Powered Interviews',
      description: 'Realistic questions tailored to your role and experience',
    },
    {
      icon: <Zap className={styles.featureIcon} />,
      title: 'Real-time Feedback',
      description: 'Instant AI analysis on your answers, time, and clarity',
    },
    {
      icon: <BarChart3 className={styles.featureIcon} />,
      title: 'Behavior Analysis',
      description: 'AI analyzes your expressions, confidence, and engagement',
    },
    {
      icon: <TrendingUp className={styles.featureIcon} />,
      title: 'Detailed Reports',
      description: 'Comprehensive insights with actionable improvements',
    },
  ];

  const companies = [
    { name: 'Google', opacity: 0.6 },
    { name: 'Microsoft', opacity: 0.6 },
    { name: 'Amazon', opacity: 0.6 },
    { name: 'Meta', opacity: 0.6 },
    { name: 'Adobe', opacity: 0.6 },
    { name: 'Netflix', opacity: 0.6 },
  ];

  return (
    <div className={styles.landingPage}>
      <ImmersiveStage variant="hero" />
      {/* Navigation */}
      <motion.nav 
        className={styles.navbar}
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.8 }}
      >
        <div className={styles.navContent}>
          <div className={styles.logo}>
            <div className={styles.logoIcon}>⚡</div>
            <span>intervue.ai</span>
          </div>
          <div className={styles.navLinks}>
            <a href="#features">Features</a>
            <a href="#how">How it Works</a>
            <a href="#pricing">Pricing</a>
            <a href="#resources">Resources</a>
            <a href="#about">About</a>
            <button className={styles.loginBtn} onClick={goToLogin}>Log in</button>
            <button className={styles.ctaBtn} onClick={goToLogin}>Get Started</button>
          </div>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <motion.div
            className={styles.heroText}
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <motion.div className={styles.badge} variants={itemVariants}>
              <span>AI</span>{' '}
              {apiOnline === false ? 'API Offline, UI Ready' : 'AI Powered, Human Perfected'}
            </motion.div>

            <motion.h1 variants={itemVariants}>
              Crush Every Interview.
              <br />
              <span className={styles.gradient}>Land Your Dream Role.</span>
            </motion.h1>

            <motion.p variants={itemVariants}>
              Intervue.ai simulates real interviews, provides real-time feedback, and delivers actionable insights to help you go from prepared to unstoppable.
            </motion.p>

            <motion.div className={styles.ctaGroup} variants={itemVariants}>
              <button className={styles.primaryBtn} onClick={goToLogin}>
                Start Free Interview
                <ArrowRight size={18} />
              </button>
              <button className={styles.secondaryBtn} onClick={goToLogin}>
                See workflow
              </button>
            </motion.div>

            <motion.div className={styles.socialProof} variants={itemVariants}>
              <div className={styles.avatars}>
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className={styles.avatar}>
                    C{i}
                  </div>
                ))}
              </div>
              <span>Joined by 30,000+ successful candidates</span>
            </motion.div>
          </motion.div>

          <motion.div
            className={styles.heroVisual}
            variants={floatVariants}
            initial="initial"
            animate="animate"
          >
            <div className={styles.animatedShape}>
              <div className={styles.gradient1}></div>
              <div className={styles.gradient2}></div>
              <div className={styles.gradient3}></div>
            </div>
            <div className={styles.chartMockup}>
              <div className={styles.bar} style={{ height: '40%' }}></div>
              <div className={styles.bar} style={{ height: '60%' }}></div>
              <div className={styles.bar} style={{ height: '35%' }}></div>
              <div className={styles.bar} style={{ height: '75%' }}></div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className={styles.features}>
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true }}
        >
          Your Personal AI Interview Copilot
        </motion.h2>

        <motion.div
          className={styles.featureGrid}
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1, delayChildren: 0.2 }}
          viewport={{ once: true }}
        >
          {features.map((feature, index) => (
            <motion.div
              key={index}
              className={styles.featureCard}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ y: -10 }}
              transition={{ duration: 0.6 }}
              viewport={{ once: true }}
            >
              <div className={styles.featureIconWrapper}>
                {feature.icon}
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Trusted By Section */}
      <section className={styles.trustedBy}>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true }}
        >
          TRUSTED BY TOP TALENT
        </motion.p>

        <motion.div
          className={styles.companies}
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1, delayChildren: 0.2 }}
          viewport={{ once: true }}
        >
          {companies.map((company, index) => (
            <motion.div
              key={index}
              className={styles.company}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              whileHover={{ scale: 1.1 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
              style={{ opacity: company.opacity }}
            >
              <span>{company.name}</span>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Testimonial Section */}
      <section className={styles.testimonial}>
        <motion.div
          className={styles.testimonialContent}
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true }}
        >
          <p className={styles.quote}>
            "The more you practice, the luckier you get."
          </p>
          <p className={styles.author}>— intervue.ai</p>
        </motion.div>
      </section>

      {/* CTA Footer */}
      <motion.section
        className={styles.ctaFooter}
        initial={{ opacity: 0, y: 50 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        viewport={{ once: true }}
      >
        <h2>Ready to Crush Your Next Interview?</h2>
        <button className={styles.primaryBtn} onClick={goToLogin}>
          Start Your Free Interview
          <ArrowRight size={18} />
        </button>
      </motion.section>
    </div>
  );
};

export default LandingPage;
