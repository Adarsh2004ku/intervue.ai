import React from 'react';

type StaticStyleValue = string | number | undefined;

type MotionOnlyProps = {
  animate?: Record<string, unknown> | string;
  exit?: unknown;
  initial?: unknown;
  layout?: unknown;
  layoutId?: unknown;
  transition?: unknown;
  variants?: unknown;
  viewport?: unknown;
  whileHover?: unknown;
  whileInView?: Record<string, unknown> | string;
  whileTap?: unknown;
};

type StaticMotionProps =
  & React.HTMLAttributes<HTMLElement>
  & React.ButtonHTMLAttributes<HTMLButtonElement>
  & React.FormHTMLAttributes<HTMLFormElement>
  & MotionOnlyProps
  & {
    style?: React.CSSProperties;
  };

const motionPropNames = new Set([
  'animate',
  'exit',
  'initial',
  'layout',
  'layoutId',
  'transition',
  'variants',
  'viewport',
  'whileHover',
  'whileInView',
  'whileTap',
]);

const scalarStyleKeys = new Set([
  'height',
  'maxHeight',
  'maxWidth',
  'minHeight',
  'minWidth',
  'opacity',
  'width',
]);

function resolveStyleValue(value: unknown): StaticStyleValue {
  if (Array.isArray(value)) {
    return resolveStyleValue(value[value.length - 1]);
  }

  if (typeof value === 'string' || typeof value === 'number') {
    return value;
  }

  return undefined;
}

function mergeStaticStyle(baseStyle: React.CSSProperties | undefined, motionStyle: unknown) {
  const style = { ...baseStyle };

  if (!motionStyle || typeof motionStyle !== 'object' || Array.isArray(motionStyle)) {
    return style;
  }

  Object.entries(motionStyle as Record<string, unknown>).forEach(([key, value]) => {
    if (!scalarStyleKeys.has(key)) {
      return;
    }

    const resolvedValue = resolveStyleValue(value);
    if (resolvedValue !== undefined) {
      (style as Record<string, StaticStyleValue>)[key] = resolvedValue;
    }
  });

  return style;
}

function createStaticMotionElement(tagName: keyof JSX.IntrinsicElements) {
  return React.forwardRef<HTMLElement, StaticMotionProps>((props, ref) => {
    const { style, whileInView, ...rest } = props;
    const domProps: Record<string, unknown> = {};

    Object.entries(rest).forEach(([key, value]) => {
      if (!motionPropNames.has(key)) {
        domProps[key] = value;
      }
    });

    domProps.ref = ref;
    domProps.style = mergeStaticStyle(style, whileInView);

    return React.createElement(tagName, domProps);
  });
}

export const motion = {
  aside: createStaticMotionElement('aside'),
  button: createStaticMotionElement('button'),
  div: createStaticMotionElement('div'),
  form: createStaticMotionElement('form'),
  h1: createStaticMotionElement('h1'),
  h2: createStaticMotionElement('h2'),
  header: createStaticMotionElement('header'),
  nav: createStaticMotionElement('nav'),
  p: createStaticMotionElement('p'),
  section: createStaticMotionElement('section'),
  span: createStaticMotionElement('span'),
};
