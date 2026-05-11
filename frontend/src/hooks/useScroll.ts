// hooks/useScroll.ts
import { useEffect, useRef, useState } from 'react';

export const useScroll = () => {
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return scrollY;
};

interface UseScrollRevealOptions {
  threshold?: number;
  rootMargin?: string;
}

export const useScrollReveal = (options: UseScrollRevealOptions = {}) => {
  const { threshold = 0.1, rootMargin = '0px' } = options;
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold, rootMargin }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  return { ref, isVisible };
};

export const useParallax = (ref: React.RefObject<HTMLElement>, speed = 0.5) => {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (ref.current) {
        const rect = ref.current.getBoundingClientRect();
        const elementOffset = window.pageYOffset + rect.top;
        const scrollOffset = window.scrollY - elementOffset;
        setOffset(scrollOffset * speed);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [ref, speed]);

  return offset;
};

interface WindowSize {
  width: number;
  height: number;
}

export const useWindowSize = (): WindowSize => {
  const [windowSize, setWindowSize] = useState<WindowSize>({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0,
  });

  useEffect(() => {
    const handleResize = () => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return windowSize;
};

export const useCountUp = (target: number, duration = 2000) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startValue = 0;
    const increment = target / (duration / 16);
    
    const counter = setInterval(() => {
      startValue += increment;
      if (startValue >= target) {
        setCount(target);
        clearInterval(counter);
      } else {
        setCount(Math.floor(startValue));
      }
    }, 16);

    return () => clearInterval(counter);
  }, [target, duration]);

  return count;
};

interface MousePosition {
  x: number;
  y: number;
}

export const useMousePosition = (): MousePosition => {
  const [position, setPosition] = useState<MousePosition>({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setPosition({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return position;
};