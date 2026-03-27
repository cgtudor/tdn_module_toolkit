import { useState } from 'react';
import { Package } from 'lucide-react';
import { cn } from '@/lib/utils';

const SIZE_MAP = {
  sm: 'w-8 h-8',
  md: 'w-12 h-12',
  lg: 'w-16 h-16',
} as const;

const PX_MAP = {
  sm: 32,
  md: 48,
  lg: 64,
} as const;

interface ItemIconProps {
  resref?: string;
  baseItem?: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function ItemIcon({ resref, baseItem, size = 'md', className }: ItemIconProps) {
  const [error, setError] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const sizeClass = SIZE_MAP[size];
  const px = PX_MAP[size];

  // Build the image URL
  let src: string | null = null;
  if (resref && !error) {
    src = `/api/icons/item/${resref}`;
  } else if (baseItem !== undefined && !error) {
    src = `/api/icons/base-item/${baseItem}/default`;
  }

  if (!src || error) {
    return (
      <div className={cn(sizeClass, 'rounded bg-muted flex items-center justify-center flex-shrink-0', className)}>
        <Package className="h-1/2 w-1/2 text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className={cn(sizeClass, 'rounded bg-muted flex items-center justify-center flex-shrink-0 overflow-hidden', className)}>
      {!loaded && (
        <Package className="h-1/2 w-1/2 text-muted-foreground animate-pulse" />
      )}
      <img
        src={src}
        alt=""
        width={px}
        height={px}
        className={cn('object-contain pixelated', !loaded && 'hidden')}
        style={{ imageRendering: 'pixelated' }}
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
      />
    </div>
  );
}
