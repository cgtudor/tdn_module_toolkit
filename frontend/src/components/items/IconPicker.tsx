import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AvailablePartsSimple {
  model_type: 0 | 1;
  parts: number[];
}

interface AvailablePartsComposite {
  model_type: 2;
  bottom_parts: number[];
  middle_parts: number[];
  top_parts: number[];
}

interface AvailablePartsArmor {
  model_type: 3;
  default_icon?: string;
}

type AvailableParts = AvailablePartsSimple | AvailablePartsComposite | AvailablePartsArmor;

interface IconPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  baseItem: number;
  currentPart1: number;
  currentPart2: number;
  currentPart3: number;
  onSelect: (part1: number, part2: number, part3: number) => void;
}

function PartGrid({
  parts,
  selectedPart,
  onSelect,
  baseItem,
  partPrefix,
}: {
  parts: number[];
  selectedPart: number;
  onSelect: (part: number) => void;
  baseItem: number;
  partPrefix?: string;
}) {
  return (
    <div className="grid grid-cols-5 gap-1.5">
      {parts.map((part) => {
        const previewParams = partPrefix
          ? `base_item=${baseItem}&p1=${partPrefix === 'b' ? part : 1}&p2=${partPrefix === 'm' ? part : 1}&p3=${partPrefix === 't' ? part : 1}`
          : `base_item=${baseItem}&p1=${part}&p2=1&p3=1`;

        return (
          <button
            key={part}
            className={cn(
              'w-14 h-14 rounded border-2 bg-muted flex flex-col items-center justify-center overflow-hidden transition-colors',
              selectedPart === part
                ? 'border-primary bg-primary/10'
                : 'border-transparent hover:border-muted-foreground/30'
            )}
            onClick={() => onSelect(part)}
            title={`Part ${part}`}
          >
            <img
              src={`/api/icons/preview?${previewParams}`}
              alt={`Part ${part}`}
              className="w-10 h-10 object-contain"
              style={{ imageRendering: 'pixelated' }}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
            <span className="text-[10px] text-muted-foreground leading-none">{part}</span>
          </button>
        );
      })}
    </div>
  );
}

export function IconPicker({
  open,
  onOpenChange,
  baseItem,
  currentPart1,
  currentPart2,
  currentPart3,
  onSelect,
}: IconPickerProps) {
  const [availableParts, setAvailableParts] = useState<AvailableParts | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [part1, setPart1] = useState(currentPart1);
  const [part2, setPart2] = useState(currentPart2);
  const [part3, setPart3] = useState(currentPart3);

  useEffect(() => {
    if (open) {
      setPart1(currentPart1);
      setPart2(currentPart2);
      setPart3(currentPart3);
      fetchAvailableParts();
    }
  }, [open, baseItem]);

  const fetchAvailableParts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/icons/base-item/${baseItem}/available`);
      if (!response.ok) {
        throw new Error('Failed to load available icons');
      }
      const data = await response.json();
      setAvailableParts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    onSelect(part1, part2, part3);
    onOpenChange(false);
  };

  const hasChanges = part1 !== currentPart1 || part2 !== currentPart2 || part3 !== currentPart3;
  const isComposite = availableParts?.model_type === 2;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Change Item Icon</DialogTitle>
          <DialogDescription>
            Select model parts to change the item's appearance.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-6 min-h-[450px]">
          {/* Left: Large preview */}
          <div className="flex flex-col items-center gap-3 flex-shrink-0">
            <div className="w-32 h-32 rounded-lg bg-muted border flex items-center justify-center overflow-hidden">
              <img
                src={`/api/icons/preview?base_item=${baseItem}&p1=${part1}&p2=${part2}&p3=${part3}`}
                alt="Preview"
                className="w-32 h-32 object-contain"
                style={{ imageRendering: 'pixelated' }}
              />
            </div>
            <div className="text-xs text-muted-foreground text-center space-y-0.5">
              {isComposite ? (
                <>
                  <div>Bottom: {part1}</div>
                  <div>Middle: {part2}</div>
                  <div>Top: {part3}</div>
                </>
              ) : (
                <div>Part: {part1}</div>
              )}
            </div>
          </div>

          {/* Right: Part selector */}
          <div className="flex-1 min-w-0">
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading available icons...</span>
              </div>
            )}

            {error && (
              <div className="text-destructive text-center py-8">{error}</div>
            )}

            {availableParts && !loading && availableParts.model_type === 3 && (
              <p className="text-muted-foreground text-sm py-8">
                Armor icons are generated from body part models and cannot be changed through the icon picker.
              </p>
            )}

            {availableParts && !loading && (availableParts.model_type === 0 || availableParts.model_type === 1) && (
              <div className="space-y-2">
                <Label>Model Part ({(availableParts as AvailablePartsSimple).parts.length} available)</Label>
                <ScrollArea className="h-[400px]">
                  <PartGrid
                    parts={(availableParts as AvailablePartsSimple).parts}
                    selectedPart={part1}
                    onSelect={setPart1}
                    baseItem={baseItem}
                  />
                </ScrollArea>
              </div>
            )}

            {availableParts && !loading && availableParts.model_type === 2 && (
              <Tabs defaultValue="bottom" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="bottom">
                    Bottom ({(availableParts as AvailablePartsComposite).bottom_parts.length})
                  </TabsTrigger>
                  <TabsTrigger value="middle">
                    Middle ({(availableParts as AvailablePartsComposite).middle_parts.length})
                  </TabsTrigger>
                  <TabsTrigger value="top">
                    Top ({(availableParts as AvailablePartsComposite).top_parts.length})
                  </TabsTrigger>
                </TabsList>

                <ScrollArea className="h-[390px] mt-2">
                  <TabsContent value="bottom" className="mt-0">
                    <PartGrid
                      parts={(availableParts as AvailablePartsComposite).bottom_parts}
                      selectedPart={part1}
                      onSelect={setPart1}
                      baseItem={baseItem}
                      partPrefix="b"
                    />
                  </TabsContent>

                  <TabsContent value="middle" className="mt-0">
                    <PartGrid
                      parts={(availableParts as AvailablePartsComposite).middle_parts}
                      selectedPart={part2}
                      onSelect={setPart2}
                      baseItem={baseItem}
                      partPrefix="m"
                    />
                  </TabsContent>

                  <TabsContent value="top" className="mt-0">
                    <PartGrid
                      parts={(availableParts as AvailablePartsComposite).top_parts}
                      selectedPart={part3}
                      onSelect={setPart3}
                      baseItem={baseItem}
                      partPrefix="t"
                    />
                  </TabsContent>
                </ScrollArea>
              </Tabs>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleApply} disabled={!hasChanges}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
