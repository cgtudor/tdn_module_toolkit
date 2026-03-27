import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/appStore';
import { useSetEquipment, useRemoveEquipment } from '@/hooks/useCreatures';
import { EquipmentSlot } from '@/types/creature';
import { EQUIPMENT_SLOT_DEFS, getSlotById } from '@/lib/equipmentSlots';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { Package, Plus, X, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EquipmentPanelProps {
  creatureResref: string;
  equipment: EquipmentSlot[];
}

export function EquipmentPanel({ creatureResref, equipment }: EquipmentPanelProps) {
  const { openItemPicker } = useAppStore();
  const setEquipment = useSetEquipment();
  const removeEquipment = useRemoveEquipment();
  const [slotToRemove, setSlotToRemove] = useState<number | null>(null);

  const equippedMap = new Map(equipment.map(e => [e.slot_id, e]));

  const handleAddItem = (slotId: number) => {
    openItemPicker((itemResref) => {
      setEquipment.mutate({ resref: creatureResref, slotId, itemResref });
    });
  };

  const handleRemoveItem = (slotId: number) => {
    setSlotToRemove(slotId);
  };

  const confirmRemove = () => {
    if (slotToRemove !== null) {
      removeEquipment.mutate({ resref: creatureResref, slotId: slotToRemove });
      setSlotToRemove(null);
    }
  };

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Equipment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-2">
            {EQUIPMENT_SLOT_DEFS.map((slotDef) => {
              const equipped = equippedMap.get(slotDef.id);

              return (
                <div
                  key={slotDef.id}
                  className={cn(
                    "relative p-2 rounded border bg-muted/50 min-h-[80px] flex flex-col",
                    equipped && "bg-accent"
                  )}
                >
                  <div className="text-xs text-muted-foreground mb-1">{slotDef.shortName}</div>

                  {equipped?.item_resref ? (
                    <div className="flex-1 flex flex-col">
                      <div className="flex items-center gap-1">
                        <Package className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        <span className="text-xs font-medium truncate" title={equipped.item_name || equipped.item_resref}>
                          {equipped.item_name || equipped.item_resref}
                        </span>
                      </div>
                      <div className="mt-auto flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => handleAddItem(slotDef.id)}
                          title="Replace item"
                        >
                          <Plus className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-destructive"
                          onClick={() => handleRemoveItem(slotDef.id)}
                          title="Remove item"
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8"
                        onClick={() => handleAddItem(slotDef.id)}
                      >
                        <Plus className="h-4 w-4 mr-1" />
                        Add
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={slotToRemove !== null}
        onOpenChange={(open) => !open && setSlotToRemove(null)}
        title="Remove Equipment"
        description={`Are you sure you want to remove the item from ${getSlotById(slotToRemove ?? 0)?.name ?? 'this slot'}?`}
        confirmLabel="Remove"
        onConfirm={confirmRemove}
        variant="destructive"
      />
    </>
  );
}
