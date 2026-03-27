import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Package, Coins, Layers, Eye, Infinity } from 'lucide-react';

interface StoreItemData {
  index: number;
  resref: string;
  name: string;
  infinite: boolean;
  stack_size: number;
  item_data?: Record<string, unknown>;
}

interface StoreItemEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: StoreItemData | null;
  categoryId: number;
  onSave: (updates: {
    infinite?: boolean;
    stack_size?: number;
    cost?: number;
    identified?: boolean;
  }) => void;
  isSaving?: boolean;
  isAreaInstance?: boolean;
}

export function StoreItemEditDialog({
  open,
  onOpenChange,
  item,
  categoryId: _categoryId,
  onSave,
  isSaving = false,
  isAreaInstance = false,
}: StoreItemEditDialogProps) {
  void _categoryId; // Reserved for future use
  const [infinite, setInfinite] = useState(false);
  const [stackSize, setStackSize] = useState(1);
  const [cost, setCost] = useState(0);
  const [identified, setIdentified] = useState(true);
  const [showRawData, setShowRawData] = useState(false);

  // Extract values from item_data when dialog opens
  useEffect(() => {
    if (item) {
      setInfinite(item.infinite);
      setStackSize(item.stack_size);

      // Extract cost and identified from item_data
      if (item.item_data) {
        const itemData = item.item_data;
        // Handle GFF format where values may be nested
        const costValue = extractGffValue(itemData, 'Cost', 0);
        const identValue = extractGffValue(itemData, 'Identified', 1);
        setCost(costValue);
        setIdentified(identValue === 1);
      } else {
        setCost(0);
        setIdentified(true);
      }
    }
  }, [item]);

  // Helper to extract GFF values (handles both {type, value} and direct values)
  const extractGffValue = (data: Record<string, unknown>, key: string, defaultVal: number): number => {
    if (!(key in data)) return defaultVal;
    const val = data[key];
    if (typeof val === 'object' && val !== null && 'value' in val) {
      return (val as { value: number }).value;
    }
    if (typeof val === 'number') return val;
    return defaultVal;
  };

  const handleSave = () => {
    const updates: {
      infinite?: boolean;
      stack_size?: number;
      cost?: number;
      identified?: boolean;
    } = {};

    // Always include infinite and stack_size
    updates.infinite = infinite;
    updates.stack_size = stackSize;

    // For area instances, include cost and identified
    if (isAreaInstance) {
      updates.cost = cost;
      updates.identified = identified;
    }

    onSave(updates);
  };

  if (!item) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            Edit Store Item
          </DialogTitle>
          <DialogDescription>
            Modify properties of this item in the store inventory.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Item Info */}
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded bg-muted flex items-center justify-center">
                  <Package className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <div className="font-medium">{item.name || item.resref}</div>
                  <Badge variant="outline" className="text-xs">{item.resref}</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Stock Settings */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="infinite"
                checked={infinite}
                onCheckedChange={(checked) => setInfinite(checked === true)}
              />
              <Label htmlFor="infinite" className="flex items-center gap-2">
                <Infinity className="h-4 w-4" />
                Infinite Stock
              </Label>
            </div>

            <div className="space-y-2">
              <Label htmlFor="stack-size" className="flex items-center gap-2">
                <Layers className="h-4 w-4" />
                Stack Size
              </Label>
              <Input
                id="stack-size"
                type="number"
                min={1}
                value={stackSize}
                onChange={(e) => setStackSize(parseInt(e.target.value) || 1)}
              />
            </div>
          </div>

          {/* Area Instance Specific Fields */}
          {isAreaInstance && (
            <div className="space-y-3 border-t pt-4">
              <div className="text-sm font-medium text-muted-foreground">
                Instance-specific properties
              </div>

              <div className="space-y-2">
                <Label htmlFor="cost" className="flex items-center gap-2">
                  <Coins className="h-4 w-4" />
                  Cost (Gold)
                </Label>
                <Input
                  id="cost"
                  type="number"
                  min={0}
                  value={cost}
                  onChange={(e) => setCost(parseInt(e.target.value) || 0)}
                />
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="identified"
                  checked={identified}
                  onCheckedChange={(checked) => setIdentified(checked === true)}
                />
                <Label htmlFor="identified" className="flex items-center gap-2">
                  <Eye className="h-4 w-4" />
                  Identified
                </Label>
              </div>
            </div>
          )}

          {/* Raw Data Toggle */}
          {item.item_data && (
            <div className="border-t pt-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRawData(!showRawData)}
                className="text-xs"
              >
                {showRawData ? 'Hide' : 'Show'} Raw Data
              </Button>

              {showRawData && (
                <ScrollArea className="h-40 mt-2 border rounded">
                  <pre className="text-xs p-2">
                    {JSON.stringify(item.item_data, null, 2)}
                  </pre>
                </ScrollArea>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
