import { useItem, useItemReferences, useUpdateItemInstances, useUpdateItem } from '@/hooks/useItems';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getBaseItemName } from '@/lib/baseItems';
import { Tag, Coins, Layers, Zap, Shield, Info, RefreshCw, Users, Store, Map, AlertCircle, CheckCircle, Edit } from 'lucide-react';
import { useState } from 'react';
import { ItemEditDialog } from './ItemEditDialog';
import { ItemIcon } from './ItemIcon';
import { ItemTemplateUpdate } from '@/types/item';

interface ItemDetailProps {
  resref: string;
}

export function ItemDetail({ resref }: ItemDetailProps) {
  const { data: item, isLoading, error, refetch } = useItem(resref);
  const { data: references, isLoading: refsLoading } = useItemReferences(resref);
  const updateInstances = useUpdateItemInstances();
  const updateItem = useUpdateItem();
  const [updateResult, setUpdateResult] = useState<{ success: boolean; message: string } | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="p-6 text-muted-foreground">Loading item details...</div>
    );
  }

  if (error || !item) {
    return (
      <div className="p-6 text-destructive">Failed to load item: {resref}</div>
    );
  }

  const handleUpdateInstances = () => {
    updateInstances.mutate(resref, {
      onSuccess: (result) => {
        setUpdateResult({ success: true, message: result.message });
        setTimeout(() => setUpdateResult(null), 5000);
      },
      onError: (error) => {
        setUpdateResult({ success: false, message: error.message });
      },
    });
  };

  const handleSaveItem = async (data: ItemTemplateUpdate) => {
    return new Promise<void>((resolve, reject) => {
      updateItem.mutate(
        { resref, data },
        {
          onSuccess: () => {
            setEditDialogOpen(false);
            setUpdateResult({ success: true, message: 'Item updated successfully' });
            setTimeout(() => setUpdateResult(null), 5000);
            refetch();
            resolve();
          },
          onError: (error) => {
            setUpdateResult({ success: false, message: error.message });
            reject(error);
          },
        }
      );
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <ItemIcon resref={resref} baseItem={item.base_item} size="lg" className="rounded-lg" />
        <div className="flex-1">
          <h2 className="text-2xl font-bold">{item.name || item.resref}</h2>
          <div className="flex gap-2 mt-1">
            <Badge variant="outline">{item.resref}</Badge>
            <Badge variant="secondary">{getBaseItemName(item.base_item)}</Badge>
          </div>
        </div>
        <Button onClick={() => setEditDialogOpen(true)} variant="outline">
          <Edit className="h-4 w-4 mr-2" />
          Edit Item
        </Button>
      </div>

      {/* Quick Info */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Coins className="h-4 w-4" />
              <span>Cost</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {item.cost.toLocaleString()} gp
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Layers className="h-4 w-4" />
              <span>Stack Size</span>
            </div>
            <div className="text-xl font-bold mt-1">{item.stack_size}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Zap className="h-4 w-4" />
              <span>Charges</span>
            </div>
            <div className="text-xl font-bold mt-1">{item.charges}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Tag className="h-4 w-4" />
              <span>Tag</span>
            </div>
            <div className="text-xl font-bold mt-1 truncate" title={item.tag}>
              {item.tag || '-'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Flags */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Flags
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {item.identified && <Badge>Identified</Badge>}
            {item.plot && <Badge variant="secondary">Plot Item</Badge>}
            {item.cursed && <Badge variant="destructive">Cursed</Badge>}
            {item.stolen && <Badge variant="outline">Stolen</Badge>}
            {!item.identified && !item.plot && !item.cursed && !item.stolen && (
              <span className="text-muted-foreground text-sm">No special flags</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* References */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              References
            </CardTitle>
            {references && references.total_count > 0 && (
              <Button
                size="sm"
                onClick={handleUpdateInstances}
                disabled={updateInstances.isPending}
              >
                {updateInstances.isPending ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Updating...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Update All Instances
                  </>
                )}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {updateResult && (
            <div className={`mb-4 p-3 rounded flex items-center gap-2 ${updateResult.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
              {updateResult.success ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              {updateResult.message}
            </div>
          )}

          {refsLoading ? (
            <div className="text-muted-foreground text-sm">Loading references...</div>
          ) : references ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-2 p-2 bg-muted rounded">
                <Users className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-sm text-muted-foreground">Creature Inventory</div>
                  <div className="font-bold">{references.creature_inventory.length}</div>
                </div>
              </div>

              <div className="flex items-center gap-2 p-2 bg-muted rounded">
                <Users className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-sm text-muted-foreground">Creature Equipment</div>
                  <div className="font-bold">{references.creature_equipment.length}</div>
                </div>
              </div>

              <div className="flex items-center gap-2 p-2 bg-muted rounded">
                <Store className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-sm text-muted-foreground">Store Templates</div>
                  <div className="font-bold">{references.store_templates.length}</div>
                </div>
              </div>

              <div className="flex items-center gap-2 p-2 bg-muted rounded">
                <Map className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-sm text-muted-foreground">Area Stores</div>
                  <div className="font-bold">{references.area_stores.length}</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground text-sm">No references found</div>
          )}

          {references && references.total_count > 0 && (
            <div className="mt-3 text-sm text-muted-foreground">
              Total: {references.total_count} instance{references.total_count !== 1 ? 's' : ''} across the module.
              Click "Update All Instances" to sync changes from this template.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Description */}
      {item.description && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Info className="h-5 w-5" />
              Description
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{item.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Properties */}
      {item.properties.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Item Properties ({item.properties.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {item.properties.map((prop, idx) => {
                // Only show subtype if we have a resolved name OR if subtype is non-zero
                const showSubtype = prop.subtype_resolved || (prop.subtype !== undefined && prop.subtype !== null && prop.subtype !== 0);
                // Only show value if we have a resolved name OR if value is non-zero
                const showValue = prop.cost_value_resolved || (prop.cost_value !== undefined && prop.cost_value !== null && prop.cost_value !== 0);

                return (
                  <div key={idx} className="text-sm p-2 bg-muted rounded">
                    <span className="font-medium" title={`ID: ${prop.property_name}`}>
                      {prop.property_name_resolved || `Property ${prop.property_name}`}
                    </span>
                    {showSubtype && (
                      <span className="text-muted-foreground ml-2" title={`Subtype ID: ${prop.subtype}`}>
                        {prop.subtype_resolved || `Subtype: ${prop.subtype}`}
                      </span>
                    )}
                    {showValue && (
                      <span className="text-muted-foreground ml-2" title={`Value ID: ${prop.cost_value}`}>
                        {prop.cost_value_resolved || `Value: ${prop.cost_value}`}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Raw Data Debug */}
      {item.raw_data && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Raw Data</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-64">
              {JSON.stringify(item.raw_data, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Edit Dialog */}
      <ItemEditDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        item={item}
        onSave={handleSaveItem}
        isSaving={updateItem.isPending}
      />
    </div>
  );
}
