import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { useAppStore } from '@/store/appStore';
import { useAddStoreItemAuto, useUpdateStoreItem, useRemoveStoreItem } from '@/hooks/useStores';
import { StoreCategory } from '@/types/store';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { STORE_CATEGORY_DEFS } from '@/lib/storeCategories';
import { Package, Plus, Trash2, Infinity, CheckCircle2 } from 'lucide-react';

interface StoreCategoryTabsProps {
  storeResref: string;
  categories: StoreCategory[];
}

export function StoreCategoryTabs({ storeResref, categories }: StoreCategoryTabsProps) {
  const { openItemPicker } = useAppStore();
  const addItemAuto = useAddStoreItemAuto();
  const updateItem = useUpdateStoreItem();
  const removeItem = useRemoveStoreItem();

  const [itemToRemove, setItemToRemove] = useState<{ categoryId: number; index: number; name: string } | null>(null);
  const [activeTab, setActiveTab] = useState('0');
  const [notification, setNotification] = useState<{ message: string; categoryId: number } | null>(null);

  const handleAddItem = () => {
    openItemPicker((itemResref) => {
      addItemAuto.mutate(
        { resref: storeResref, itemResref },
        {
          onSuccess: (result) => {
            // Show notification about which category the item was added to
            setNotification({
              message: `Added "${itemResref}" to ${result.category_name}`,
              categoryId: result.category_id,
            });
            // Switch to the category where item was added
            setActiveTab(String(result.category_id));
            // Clear notification after 3 seconds
            setTimeout(() => setNotification(null), 3000);
          },
        }
      );
    });
  };

  const handleToggleInfinite = (categoryId: number, index: number, currentValue: boolean) => {
    updateItem.mutate({
      resref: storeResref,
      categoryId,
      index,
      updates: { infinite: !currentValue },
    });
  };

  const handleRemoveItem = (categoryId: number, index: number, name: string) => {
    setItemToRemove({ categoryId, index, name });
  };

  const confirmRemove = () => {
    if (itemToRemove) {
      removeItem.mutate({
        resref: storeResref,
        categoryId: itemToRemove.categoryId,
        index: itemToRemove.index,
      });
      setItemToRemove(null);
    }
  };

  const categoryMap = new Map(categories.map(c => [c.category_id, c]));

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Inventory</CardTitle>
            <Button size="sm" onClick={handleAddItem} disabled={addItemAuto.isPending}>
              <Plus className="h-4 w-4 mr-1" />
              {addItemAuto.isPending ? 'Adding...' : 'Add Item'}
            </Button>
          </div>
          {notification && (
            <div className="flex items-center gap-2 mt-2 p-2 rounded bg-green-500/10 text-green-600 text-sm">
              <CheckCircle2 className="h-4 w-4" />
              {notification.message}
            </div>
          )}
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid grid-cols-5 w-full">
              {STORE_CATEGORY_DEFS.map((cat) => {
                const category = categoryMap.get(cat.id);
                const count = category?.items.length || 0;
                return (
                  <TabsTrigger key={cat.id} value={String(cat.id)}>
                    {cat.name} ({count})
                  </TabsTrigger>
                );
              })}
            </TabsList>

            {STORE_CATEGORY_DEFS.map((cat) => {
              const category = categoryMap.get(cat.id);
              const items = category?.items || [];

              return (
                <TabsContent key={cat.id} value={String(cat.id)} className="mt-4">
                  {items.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8 border rounded">
                      No items in this category
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {items.map((item, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-3 p-3 rounded border bg-muted/50 hover:bg-accent transition-colors"
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

                          <div className="flex items-center gap-2">
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={item.infinite}
                                onCheckedChange={() => handleToggleInfinite(cat.id, idx, item.infinite)}
                              />
                              <Infinity className={`h-4 w-4 ${item.infinite ? 'text-primary' : 'text-muted-foreground'}`} />
                            </div>

                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              onClick={() => handleRemoveItem(cat.id, idx, item.name || item.resref)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>
              );
            })}
          </Tabs>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={itemToRemove !== null}
        onOpenChange={(open) => !open && setItemToRemove(null)}
        title="Remove Item"
        description={`Are you sure you want to remove "${itemToRemove?.name}" from this store?`}
        confirmLabel="Remove"
        onConfirm={confirmRemove}
        variant="destructive"
      />
    </>
  );
}
