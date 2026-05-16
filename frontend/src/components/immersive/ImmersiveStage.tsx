import { Suspense, lazy } from 'react';

type ImmersiveStageProps = {
  variant?: 'hero' | 'ambient';
  className?: string;
};

const ImmersiveBackground = lazy(() =>
  import('./ImmersiveBackground').then((module) => ({
    default: module.ImmersiveBackground,
  })),
);

export function ImmersiveStage(props: ImmersiveStageProps) {
  return (
    <Suspense fallback={null}>
      <ImmersiveBackground {...props} />
    </Suspense>
  );
}
