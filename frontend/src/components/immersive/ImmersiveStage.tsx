import { ImmersiveBackground } from './ImmersiveBackground';

type ImmersiveStageProps = {
  variant?: 'hero' | 'ambient';
  className?: string;
};

export function ImmersiveStage(props: ImmersiveStageProps) {
  return <ImmersiveBackground {...props} />;
}
