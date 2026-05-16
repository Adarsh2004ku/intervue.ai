import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, MeshDistortMaterial, Sparkles, Stars } from '@react-three/drei';
import { gsap } from 'gsap';
import * as THREE from 'three';
import styles from './ImmersiveBackground.module.css';

type ImmersiveBackgroundProps = {
  variant?: 'hero' | 'ambient';
  className?: string;
};

type OrbConfig = {
  position: [number, number, number];
  scale: number;
  color: string;
  speed: number;
};

const heroOrbs: OrbConfig[] = [
  { position: [-2.2, 0.6, -1.2], scale: 1.1, color: '#7C3AED', speed: 0.45 },
  { position: [1.8, -0.2, -1.8], scale: 0.72, color: '#8B5CF6', speed: 0.38 },
  { position: [0.25, 1.05, -2.2], scale: 0.48, color: '#C4B5FD', speed: 0.52 },
];

const ambientOrbs: OrbConfig[] = [
  { position: [-2.4, 0.35, -2.4], scale: 0.72, color: '#7C3AED', speed: 0.28 },
  { position: [2.2, 0.8, -2.8], scale: 0.42, color: '#8B5CF6', speed: 0.24 },
];

function Orb({ position, scale, color, speed }: OrbConfig) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (!meshRef.current) {
      return;
    }

    meshRef.current.rotation.x += delta * speed * 0.28;
    meshRef.current.rotation.y += delta * speed * 0.42;
    meshRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * speed) * 0.08;
  });

  return (
    <Float speed={1.1 + speed} rotationIntensity={0.16} floatIntensity={0.36}>
      <mesh ref={meshRef} position={position} scale={scale}>
        <sphereGeometry args={[1, 48, 48]} />
        <MeshDistortMaterial
          color={color}
          distort={0.34}
          speed={1.2}
          roughness={0.22}
          metalness={0.42}
          transparent
          opacity={0.82}
        />
      </mesh>
    </Float>
  );
}

function HolographicRings({ variant }: { variant: 'hero' | 'ambient' }) {
  const groupRef = useRef<THREE.Group>(null);
  const rings = useMemo(() => {
    const count = variant === 'hero' ? 4 : 2;
    return Array.from({ length: count }, (_, index) => ({
      radius: 1.15 + index * 0.38,
      color: index % 2 === 0 ? '#7C3AED' : '#8B5CF6',
      opacity: 0.2 - index * 0.028,
    }));
  }, [variant]);

  useFrame((_, delta) => {
    if (!groupRef.current) {
      return;
    }

    groupRef.current.rotation.z += delta * 0.05;
    groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, -0.42, 0.02);
  });

  return (
    <group ref={groupRef} position={[0.25, -0.2, -2.6]} rotation={[-0.4, 0, 0.2]}>
      {rings.map((ring) => (
        <mesh key={ring.radius} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[ring.radius, 0.006, 12, 128]} />
          <meshBasicMaterial color={ring.color} transparent opacity={ring.opacity} />
        </mesh>
      ))}
    </group>
  );
}

function Scene({ variant }: { variant: 'hero' | 'ambient' }) {
  const orbs = variant === 'hero' ? heroOrbs : ambientOrbs;

  return (
    <>
      <ambientLight intensity={variant === 'hero' ? 0.74 : 0.48} />
      <pointLight position={[-3, 3.4, 2.5]} intensity={variant === 'hero' ? 1.7 : 0.9} color="#7C3AED" />
      <pointLight position={[3.2, -1.6, 1.8]} intensity={variant === 'hero' ? 1.25 : 0.65} color="#8B5CF6" />
      <Stars radius={48} depth={18} count={variant === 'hero' ? 720 : 320} factor={2.4} saturation={0} fade speed={0.18} />
      <Sparkles
        count={variant === 'hero' ? 58 : 24}
        speed={0.22}
        size={variant === 'hero' ? 2.8 : 1.7}
        opacity={0.42}
        scale={variant === 'hero' ? [6.5, 3.1, 4.2] : [5.2, 2, 3]}
        color="#8B5CF6"
      />
      {orbs.map((orb) => (
        <Orb key={`${orb.color}-${orb.position.join('-')}`} {...orb} />
      ))}
      <HolographicRings variant={variant} />
    </>
  );
}

export function ImmersiveBackground({ variant = 'hero', className = '' }: ImmersiveBackgroundProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!rootRef.current) {
      return undefined;
    }

    const context = gsap.context(() => {
      gsap.to(`.${styles.grid}`, {
        backgroundPosition: '84px 84px',
        duration: 18,
        repeat: -1,
        ease: 'none',
      });
    }, rootRef);

    return () => context.revert();
  }, []);

  return (
    <div ref={rootRef} className={`${styles.backdrop} ${styles[variant]} ${className}`} aria-hidden="true">
      <div className={styles.lightSweep} />
      <Canvas
        className={styles.canvas}
        camera={{ position: [0, 0, 5.2], fov: 52 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      >
        <Suspense fallback={null}>
          <Scene variant={variant} />
        </Suspense>
      </Canvas>
      <div className={styles.grid} />
      <div className={styles.vignette} />
    </div>
  );
}
