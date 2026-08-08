import { type ComponentProps, Fragment, useMemo, useState } from 'react';
import { type VariantProps, cva } from 'class-variance-authority';
import { Track } from 'livekit-client';
import {
  LoaderIcon,
  MicIcon,
  MicOffIcon,
  MonitorOffIcon,
  MonitorUpIcon,
  VideoIcon,
  VideoOffIcon,
} from 'lucide-react';
import { Toggle } from '@/components/ui/toggle';
import { cn } from '@/lib/shadcn/utils';

export const agentTrackToggleVariants = cva(['size-9'], {
  variants: {
    size: {
      default: 'h-9 px-2 min-w-9',
      sm: 'h-8 px-1.5 min-w-8',
      lg: 'h-10 px-2.5 min-w-10',
    },
    variant: {
      default: [
        'data-[state=off]:bg-rose-500/30 data-[state=off]:text-rose-100 data-[state=off]:border data-[state=off]:border-rose-400/50',
        'data-[state=off]:hover:bg-rose-500/45 data-[state=off]:hover:text-white',
        'data-[state=off]:focus-visible:ring-rose-400/40',
        'data-[state=on]:bg-white/20 data-[state=on]:text-white data-[state=on]:border data-[state=on]:border-white/25',
        'data-[state=on]:hover:bg-white/30',
      ],
      outline: [
        'data-[state=off]:bg-rose-500/30 data-[state=off]:text-rose-100 data-[state=off]:border data-[state=off]:border-rose-400/50',
        'data-[state=off]:hover:bg-rose-500/45 data-[state=off]:hover:text-white',
        'data-[state=off]:focus-visible:ring-rose-400/40',
        'data-[state=on]:bg-white/20 data-[state=on]:text-white data-[state=on]:border data-[state=on]:border-white/25',
        'data-[state=on]:hover:bg-white/30',
      ],
    },
  },
  defaultVariants: {
    variant: 'default',
  },
});

function getSourceIcon(source: Track.Source, enabled: boolean, pending = false) {
  if (pending) {
    return LoaderIcon;
  }

  switch (source) {
    case Track.Source.Microphone:
      return enabled ? MicIcon : MicOffIcon;
    case Track.Source.Camera:
      return enabled ? VideoIcon : VideoOffIcon;
    case Track.Source.ScreenShare:
      return enabled ? MonitorUpIcon : MonitorOffIcon;
    default:
      return Fragment;
  }
}

/**
 * Props for the AgentTrackToggle component.
 */
export type AgentTrackToggleProps = VariantProps<typeof agentTrackToggleVariants> &
  ComponentProps<'button'> & {
    /**
     * The size of the toggle.
     */
    size?: 'sm' | 'default' | 'lg';
    /**
     * The variant of the toggle.
     * @defaultValue 'default'
     */
    variant?: 'default' | 'outline';
    /**
     * The track source to toggle (Microphone, Camera, or ScreenShare).
     */
    source: 'camera' | 'microphone' | 'screen_share';
    /**
     * Whether the toggle is in a pending/loading state.
     * When true, displays a loading spinner icon.
     * @defaultValue false
     */
    pending?: boolean;
    /**
     * Whether the toggle is currently pressed/enabled.
     * @defaultValue false
     */
    pressed?: boolean;
    /**
     * The default pressed state when uncontrolled.
     * @defaultValue false
     */
    defaultPressed?: boolean;
    /**
     * Callback fired when the pressed state changes.
     */
    onPressedChange?: (pressed: boolean) => void;
  };

/**
 * A toggle button for controlling track publishing state.
 * Displays appropriate icons based on the track source and state.
 *
 * @extends ComponentProps<'button'>
 *
 * @example
 * ```tsx
 * <AgentTrackToggle
 *   source={Track.Source.Microphone}
 *   pressed={isMicEnabled}
 *   onPressedChange={(pressed) => setMicEnabled(pressed)}
 * />
 * ```
 */
export function AgentTrackToggle({
  size = 'default',
  variant = 'default',
  source,
  pending = false,
  pressed,
  defaultPressed = false,
  className,
  onPressedChange,
  ...props
}: AgentTrackToggleProps) {
  const [uncontrolledPressed, setUncontrolledPressed] = useState(defaultPressed ?? false);
  const isControlled = pressed !== undefined;
  const resolvedPressed = useMemo(
    () => (isControlled ? pressed : uncontrolledPressed) ?? false,
    [isControlled, pressed, uncontrolledPressed]
  );
  const IconComponent = getSourceIcon(source as Track.Source, resolvedPressed, pending);
  const handlePressedChange = (nextPressed: boolean) => {
    if (!isControlled) {
      setUncontrolledPressed(nextPressed);
    }
    onPressedChange?.(nextPressed);
  };

  return (
    <Toggle
      size={size}
      variant={variant}
      pressed={isControlled ? pressed : undefined}
      defaultPressed={isControlled ? undefined : defaultPressed}
      aria-label={`Toggle ${source}`}
      onPressedChange={handlePressedChange}
      className={cn(
        agentTrackToggleVariants({
          size,
          variant: variant ?? 'default',
          className,
        })
      )}
      {...props}
    >
      <IconComponent className={cn(pending && 'animate-spin')} />
      {props.children}
    </Toggle>
  );
}
