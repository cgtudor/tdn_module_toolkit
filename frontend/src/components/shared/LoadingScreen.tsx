import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface LoadingScreenProps {
  message?: string;
  subMessage?: string;
  detail?: string;
  progress?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function LoadingScreen({
  message = 'Loading...',
  subMessage,
  detail,
  progress,
  action,
}: LoadingScreenProps) {
  return (
    <div className="fixed inset-0 bg-background flex items-center justify-center z-50">
      <div className="text-center space-y-4 max-w-md px-6">
        <div className="flex justify-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">{message}</h2>
          {subMessage && (
            <p className="text-sm text-muted-foreground">{subMessage}</p>
          )}
          {detail && (
            <p className="text-xs text-muted-foreground">{detail}</p>
          )}
        </div>
        {progress !== undefined && (
          <div className="w-full">
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {Math.round(progress)}%
            </p>
          </div>
        )}
        {action && (
          <Button onClick={action.onClick} variant="outline" className="mt-4">
            {action.label}
          </Button>
        )}
      </div>
    </div>
  );
}
