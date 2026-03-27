import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/appStore';
import { useAddInventory, useRemoveInventory } from '@/hooks/useCreatures';
import { InventoryItem } from '@/types/creature';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { Package, Plus, Trash2, Backpack } from 'lucide-react';

interface InventoryGridProps {
  creatureResref: string;
  inventory: InventoryItem[];
}

export function InventoryGrid({ creatureResref, inventory }: InventoryGridProps) {
  const { openItemPicker } = useAppStore();
  const addInventory = useAddInventory();
  const removeInventory = useRemoveInventory();
  const [itemToRemove, setItemToRemove] = useState<number | null>(null);

  const handleAddItem = () => {
    openItemPicker((itemResref) => {
      addInventory.mutate({ resref: creatureResref, itemResref });
    });
  };

  const handleRemoveItem = (index: number) => {
    setItemToRemove(index);
  };

  const confirmRemove = () => {
    if (itemToRemove !== null) {
      removeInventory.mutate({ resref: creatureResref, index: itemToRemove });
      setItemToRemove(null);
    }
  };

  const itemToRemoveData = itemToRemove !== null ? inventory[itemToRemove] : null;

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Backpack className="h-5 w-5" />
              Inventory ({inventory.length})
            </CardTitle>
            <Button size="sm" onClick={handleAddItem}>
              <Plus className="h-4 w-4 mr-1" />
              Add Item
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {inventory.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              No items in inventory
            </div>
          ) : (
            <div className="space-y-2">
              {inventory.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-3 p-2 rounded border bg-muted/50 hover:bg-accent transition-colors"
                >
                  <div className="w-8 h-8 rounded bg-background flex items-center justify-center flex-shrink-0">
                    <Package className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {item.name || item.resref}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {item.resref}
                      {item.stack_size > 1 && ` x${item.stack_size}`}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={() => handleRemoveItem(idx)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={itemToRemove !== null}
        onOpenChange={(open) => !open && setItemToRemove(null)}
        title="Remove Item"
        description={`Are you sure you want to remove "${itemToRemoveData?.name || itemToRemoveData?.resref}" from the inventory?`}
        confirmLabel="Remove"
        onConfirm={confirmRemove}
        variant="destructive"
      />
    </>
  );
}
