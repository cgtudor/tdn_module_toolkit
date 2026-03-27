import { useAreaStore, useAreaCreature, useSyncStoreFromTemplate, useAddAreaStoreItemAuto, useUpdateAreaStoreItem, useRemoveAreaStoreItem, useUpdateAreaStoreSettings } from '@/hooks/useInstances';
import { useItemSearch } from '@/hooks/useItems';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { StoreItemEditDialog } from '@/components/stores/StoreItemEditDialog';
import { STORE_CATEGORY_DEFS } from '@/lib/storeCategories';
import { EQUIPMENT_SLOT_DEFS } from '@/lib/equipmentSlots';
import { StorePositionEditor } from '@/components/stores/StorePositionEditor';
import { Store, User, MapPin, RefreshCw, Package, AlertCircle, CheckCircle, Plus, Trash2, Edit2, Settings, Grid3X3, List } from 'lucide-react';
import { useState, useCallback } from 'react';

interface InstanceEditorProps {
  areaResref: string;
  instanceType: 'store' | 'creature';
  instanceIndex: number;
}

export function InstanceEditor({ areaResref, instanceType, instanceIndex }: InstanceEditorProps) {
  const { data: storeInstance, isLoading: storeLoading, error: storeError } = useAreaStore(
    instanceType === 'store' ? areaResref : null,
    instanceType === 'store' ? instanceIndex : null
  );

  const { data: creatureInstance, isLoading: creatureLoading, error: creatureError } = useAreaCreature(
    instanceType === 'creature' ? areaResref : null,
    instanceType === 'creature' ? instanceIndex : null
  );

  const syncStore = useSyncStoreFromTemplate();
  const addStoreItemAuto = useAddAreaStoreItemAuto();
  const updateStoreItem = useUpdateAreaStoreItem();
  const removeStoreItem = useRemoveAreaStoreItem();
  const updateStoreSettings = useUpdateAreaStoreSettings();

  const [syncResult, setSyncResult] = useState<{ success: boolean; message: string } | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [addNotification, setAddNotification] = useState<{ message: string; categoryId: number } | null>(null);
  const [settingsDialog, setSettingsDialog] = useState(false);
  const [editedSettings, setEditedSettings] = useState<{
    markup: number;
    markdown: number;
    store_gold: number;
    max_buy_price: number;
    identify_price: number;
    black_market: boolean;
    bm_markdown: number;
  } | null>(null);
  const [addItemDialog, setAddItemDialog] = useState<{ open: boolean }>({ open: false });
  const [editItemDialog, setEditItemDialog] = useState<{
    open: boolean;
    categoryId: number;
    item: {
      index: number;
      resref: string;
      name: string;
      infinite: boolean;
      stack_size: number;
      item_data?: Record<string, unknown>;
    };
  } | null>(null);
  const [itemSearchQuery, setItemSearchQuery] = useState('');
  const [selectedItemResref, setSelectedItemResref] = useState<string | null>(null);
  const [addAsInfinite, setAddAsInfinite] = useState(false);

  const { data: itemSearchResults } = useItemSearch(itemSearchQuery);

  const handleUpdateItemPosition = useCallback((categoryId: number, index: number, repos_x: number, repos_y: number) => {
    updateStoreItem.mutate({
      areaResref,
      storeIndex: instanceIndex,
      categoryId,
      itemIndex: index,
      repos_x,
      repos_y,
    });
  }, [areaResref, instanceIndex, updateStoreItem]);

  const isLoading = instanceType === 'store' ? storeLoading : creatureLoading;
  const error = instanceType === 'store' ? storeError : creatureError;

  if (isLoading) {
    return <div className="p-6 text-muted-foreground">Loading instance details...</div>;
  }

  if (error) {
    return (
      <div className="p-6 text-destructive">
        Failed to load {instanceType}: {error.message || 'Unknown error'}
      </div>
    );
  }

  const handleSync = () => {
    syncStore.mutate(
      { areaResref, index: instanceIndex },
      {
        onSuccess: (result) => {
          setSyncResult({ success: result.success, message: result.message });
          setTimeout(() => setSyncResult(null), 5000);
        },
        onError: (error) => {
          setSyncResult({ success: false, message: error.message });
        },
      }
    );
  };

  // Store Instance
  if (instanceType === 'store' && storeInstance) {
    const totalItems = storeInstance.categories.reduce((sum, cat) => sum + cat.items.length, 0);

    return (
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-lg bg-muted flex items-center justify-center">
            <Store className="h-8 w-8 text-muted-foreground" />
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold">{storeInstance.name || storeInstance.resref}</h2>
            <div className="flex gap-2 mt-1 flex-wrap">
              <Badge variant="outline">{storeInstance.resref}</Badge>
              {storeInstance.template_resref && (
                <Badge variant="secondary">Template: {storeInstance.template_resref}</Badge>
              )}
              <Badge>{totalItems} items</Badge>
            </div>
          </div>
          {storeInstance.template_resref && (
            <Button
              onClick={handleSync}
              disabled={syncStore.isPending}
              variant="outline"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${syncStore.isPending ? 'animate-spin' : ''}`} />
              Sync from Template
            </Button>
          )}
        </div>

        {/* Sync Result */}
        {syncResult && (
          <div className={`p-3 rounded flex items-center gap-2 ${syncResult.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {syncResult.success ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            {syncResult.message}
          </div>
        )}

        {/* Position */}
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Position: ({storeInstance.x.toFixed(2)}, {storeInstance.y.toFixed(2)}, {storeInstance.z.toFixed(2)})
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Settings */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Settings</CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setEditedSettings({
                    markup: storeInstance.settings.markup,
                    markdown: storeInstance.settings.markdown,
                    store_gold: storeInstance.settings.store_gold,
                    max_buy_price: storeInstance.settings.max_buy_price,
                    identify_price: storeInstance.settings.identify_price,
                    black_market: storeInstance.settings.black_market,
                    bm_markdown: storeInstance.settings.bm_markdown,
                  });
                  setSettingsDialog(true);
                }}
              >
                <Settings className="h-4 w-4 mr-1" />
                Edit
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Markup:</span>
                <span className="ml-2 font-medium">{storeInstance.settings.markup}%</span>
              </div>
              <div>
                <span className="text-muted-foreground">Markdown:</span>
                <span className="ml-2 font-medium">{storeInstance.settings.markdown}%</span>
              </div>
              <div>
                <span className="text-muted-foreground">Store Gold:</span>
                <span className="ml-2 font-medium">
                  {storeInstance.settings.store_gold === -1 ? 'Unlimited' : storeInstance.settings.store_gold}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Max Buy:</span>
                <span className="ml-2 font-medium">
                  {storeInstance.settings.max_buy_price === -1 ? 'No limit' : storeInstance.settings.max_buy_price}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Add Notification */}
        {addNotification && (
          <div className="flex items-center gap-2 p-2 rounded bg-green-500/10 text-green-600 text-sm">
            <CheckCircle className="h-4 w-4" />
            {addNotification.message}
          </div>
        )}

        {/* View Mode Toggle & Add Item */}
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            <Button
              variant={viewMode === 'list' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('list')}
            >
              <List className="h-4 w-4 mr-1" />
              List View
            </Button>
            <Button
              variant={viewMode === 'grid' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('grid')}
            >
              <Grid3X3 className="h-4 w-4 mr-1" />
              Position Editor
            </Button>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setAddItemDialog({ open: true });
              setItemSearchQuery('');
              setSelectedItemResref(null);
              setAddAsInfinite(false);
            }}
            disabled={addStoreItemAuto.isPending}
          >
            <Plus className="h-4 w-4 mr-1" />
            {addStoreItemAuto.isPending ? 'Adding...' : 'Add Item'}
          </Button>
        </div>

        {/* List View */}
        {viewMode === 'list' && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Inventory</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="0">
                <TabsList className="grid grid-cols-5 w-full">
                  {STORE_CATEGORY_DEFS.map((cat) => {
                    const category = storeInstance.categories.find(c => c.category_id === cat.id);
                    const count = category?.items.length || 0;
                    return (
                      <TabsTrigger key={cat.id} value={String(cat.id)}>
                        {cat.name} ({count})
                      </TabsTrigger>
                    );
                  })}
                </TabsList>

                {STORE_CATEGORY_DEFS.map((cat) => {
                  const category = storeInstance.categories.find(c => c.category_id === cat.id);
                  const items = category?.items || [];

                  return (
                    <TabsContent key={cat.id} value={String(cat.id)} className="mt-4">
                      {items.length === 0 ? (
                        <div className="text-center text-muted-foreground py-4 border rounded text-sm">
                          No items
                        </div>
                      ) : (
                        <div className="space-y-1">
                          {items.map((item, idx) => (
                            <div key={idx} className="flex items-center gap-2 p-2 rounded bg-muted/50 text-sm group">
                              <Package className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                              <span className="flex-1 truncate">{item.name || item.resref}</span>
                              {item.infinite && <Badge variant="outline" className="text-xs">Infinite</Badge>}
                              {item.stack_size > 1 && <span className="text-muted-foreground">x{item.stack_size}</span>}
                              <div className="opacity-0 group-hover:opacity-100 flex gap-1 transition-opacity">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 w-6 p-0"
                                  onClick={() => setEditItemDialog({
                                    open: true,
                                    categoryId: cat.id,
                                    item: {
                                      index: idx,
                                      resref: item.resref,
                                      name: item.name,
                                      infinite: item.infinite,
                                      stack_size: item.stack_size,
                                      item_data: item.item_data as Record<string, unknown> | undefined,
                                    },
                                  })}
                                >
                                  <Edit2 className="h-3 w-3" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                                  onClick={() => {
                                    if (confirm(`Remove ${item.name || item.resref} from this store?`)) {
                                      removeStoreItem.mutate({
                                        areaResref,
                                        storeIndex: instanceIndex,
                                        categoryId: cat.id,
                                        itemIndex: idx,
                                      });
                                    }
                                  }}
                                >
                                  <Trash2 className="h-3 w-3" />
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
        )}

        {/* Position Editor (Grid View) */}
        {viewMode === 'grid' && (
          <StorePositionEditor
            storeResref={storeInstance.resref}
            categories={storeInstance.categories}
            onUpdateItem={handleUpdateItemPosition}
            isUpdating={updateStoreItem.isPending}
          />
        )}

        {/* Add Item Dialog */}
        <Dialog open={addItemDialog.open} onOpenChange={(open) => setAddItemDialog({ open })}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Add Item to Store</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Items are automatically placed in the correct category based on their type.
            </p>
            <div className="space-y-4">
              <div>
                <Label>Search Items</Label>
                <Input
                  placeholder="Type to search items..."
                  value={itemSearchQuery}
                  onChange={(e) => setItemSearchQuery(e.target.value)}
                />
              </div>
              {itemSearchResults?.items && itemSearchResults.items.length > 0 && (
                <ScrollArea className="h-48 border rounded">
                  <div className="divide-y">
                    {itemSearchResults.items.map((item: any) => (
                      <button
                        key={item.resref}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-accent ${selectedItemResref === item.resref ? 'bg-accent' : ''}`}
                        onClick={() => setSelectedItemResref(item.resref)}
                      >
                        <div className="font-medium truncate">{item.name || item.resref}</div>
                        <div className="text-xs text-muted-foreground">{item.resref}</div>
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              )}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="infinite"
                  checked={addAsInfinite}
                  onCheckedChange={(checked) => setAddAsInfinite(checked === true)}
                />
                <Label htmlFor="infinite">Infinite stock</Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddItemDialog({ open: false })}>
                Cancel
              </Button>
              <Button
                disabled={!selectedItemResref || addStoreItemAuto.isPending}
                onClick={() => {
                  if (selectedItemResref) {
                    addStoreItemAuto.mutate(
                      {
                        areaResref,
                        storeIndex: instanceIndex,
                        itemResref: selectedItemResref,
                        infinite: addAsInfinite,
                      },
                      {
                        onSuccess: (result) => {
                          setAddItemDialog({ open: false });
                          setSelectedItemResref(null);
                          setItemSearchQuery('');
                          // Show notification about category
                          setAddNotification({
                            message: `Added "${selectedItemResref}" to ${result.category_name}`,
                            categoryId: result.category_id,
                          });
                          setTimeout(() => setAddNotification(null), 3000);
                        },
                      }
                    );
                  }
                }}
              >
                {addStoreItemAuto.isPending ? 'Adding...' : 'Add Item'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Item Dialog */}
        <StoreItemEditDialog
          open={!!editItemDialog?.open}
          onOpenChange={(open) => !open && setEditItemDialog(null)}
          item={editItemDialog?.item ?? null}
          categoryId={editItemDialog?.categoryId ?? 0}
          isAreaInstance={true}
          isSaving={updateStoreItem.isPending}
          onSave={(updates) => {
            if (editItemDialog) {
              updateStoreItem.mutate(
                {
                  areaResref,
                  storeIndex: instanceIndex,
                  categoryId: editItemDialog.categoryId,
                  itemIndex: editItemDialog.item.index,
                  ...updates,
                },
                {
                  onSuccess: () => setEditItemDialog(null),
                }
              );
            }
          }}
        />

        {/* Edit Settings Dialog */}
        <Dialog open={settingsDialog} onOpenChange={(open) => !open && setSettingsDialog(false)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Edit Store Settings</DialogTitle>
            </DialogHeader>
            {editedSettings && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Markup (%)</Label>
                    <Input
                      type="number"
                      value={editedSettings.markup}
                      onChange={(e) => setEditedSettings({ ...editedSettings, markup: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label>Markdown (%)</Label>
                    <Input
                      type="number"
                      value={editedSettings.markdown}
                      onChange={(e) => setEditedSettings({ ...editedSettings, markdown: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Store Gold (-1 = unlimited)</Label>
                    <Input
                      type="number"
                      value={editedSettings.store_gold}
                      onChange={(e) => setEditedSettings({ ...editedSettings, store_gold: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label>Max Buy Price (-1 = no limit)</Label>
                    <Input
                      type="number"
                      value={editedSettings.max_buy_price}
                      onChange={(e) => setEditedSettings({ ...editedSettings, max_buy_price: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Identify Price</Label>
                    <Input
                      type="number"
                      value={editedSettings.identify_price}
                      onChange={(e) => setEditedSettings({ ...editedSettings, identify_price: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <Label>BM Markdown (%)</Label>
                    <Input
                      type="number"
                      value={editedSettings.bm_markdown}
                      onChange={(e) => setEditedSettings({ ...editedSettings, bm_markdown: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="black_market"
                    checked={editedSettings.black_market}
                    onCheckedChange={(checked) => setEditedSettings({ ...editedSettings, black_market: checked === true })}
                  />
                  <Label htmlFor="black_market">Black Market</Label>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setSettingsDialog(false)}>
                Cancel
              </Button>
              <Button
                disabled={updateStoreSettings.isPending}
                onClick={() => {
                  if (editedSettings) {
                    updateStoreSettings.mutate(
                      {
                        areaResref,
                        storeIndex: instanceIndex,
                        settings: editedSettings,
                      },
                      {
                        onSuccess: () => {
                          setSettingsDialog(false);
                          setEditedSettings(null);
                        },
                      }
                    );
                  }
                }}
              >
                {updateStoreSettings.isPending ? 'Saving...' : 'Save Settings'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // Creature Instance
  if (instanceType === 'creature' && creatureInstance) {
    const displayName = `${creatureInstance.first_name} ${creatureInstance.last_name}`.trim() || creatureInstance.resref;

    return (
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
            <User className="h-8 w-8 text-muted-foreground" />
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold">{displayName}</h2>
            <div className="flex gap-2 mt-1 flex-wrap">
              <Badge variant="outline">{creatureInstance.resref}</Badge>
              {creatureInstance.template_resref && (
                <Badge variant="secondary">Template: {creatureInstance.template_resref}</Badge>
              )}
              {creatureInstance.tag && <Badge>{creatureInstance.tag}</Badge>}
            </div>
          </div>
        </div>

        {/* Position */}
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Position: ({creatureInstance.x.toFixed(2)}, {creatureInstance.y.toFixed(2)}, {creatureInstance.z.toFixed(2)})
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Equipment */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Equipment (Read-only)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2">
              {EQUIPMENT_SLOT_DEFS.map((slotDef) => {
                const equipped = creatureInstance.equipment.find(e => e.slot_id === slotDef.id);
                return (
                  <div
                    key={slotDef.id}
                    className={`p-2 rounded border text-sm ${equipped?.item_resref ? 'bg-accent' : 'bg-muted/50'}`}
                  >
                    <div className="text-xs text-muted-foreground">{slotDef.shortName}</div>
                    {equipped?.item_resref ? (
                      <div className="truncate font-medium">{equipped.item_name || equipped.item_resref}</div>
                    ) : (
                      <div className="text-muted-foreground">Empty</div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Inventory */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Inventory ({creatureInstance.inventory.length} items, Read-only)</CardTitle>
          </CardHeader>
          <CardContent>
            {creatureInstance.inventory.length === 0 ? (
              <div className="text-center text-muted-foreground py-4">No items</div>
            ) : (
              <div className="space-y-1">
                {creatureInstance.inventory.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2 p-2 rounded bg-muted/50 text-sm">
                    <Package className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="flex-1 truncate">{item.name || item.resref}</span>
                    {item.stack_size > 1 && <span className="text-muted-foreground">x{item.stack_size}</span>}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return <div className="p-6 text-destructive">Instance not found</div>;
}
