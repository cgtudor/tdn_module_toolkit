import { useState, useCallback } from 'react';
import { useStore, useUpdateStoreItem } from '@/hooks/useStores';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StoreSettings } from './StoreSettings';
import { StoreCategoryTabs } from './StoreCategoryTabs';
import { StorePositionEditor } from './StorePositionEditor';
import { Store, TrendingUp, TrendingDown, Coins, CreditCard, Grid3X3, List } from 'lucide-react';

interface StoreDetailProps {
  resref: string;
}

export function StoreDetail({ resref }: StoreDetailProps) {
  const { data: store, isLoading, error } = useStore(resref);
  const updateItem = useUpdateStoreItem();
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  const handleUpdateItemPosition = useCallback((categoryId: number, index: number, repos_x: number, repos_y: number) => {
    updateItem.mutate({
      resref,
      categoryId,
      index,
      updates: { repos_x, repos_y },
    });
  }, [resref, updateItem]);

  if (isLoading) {
    return (
      <div className="p-6 text-muted-foreground">Loading store details...</div>
    );
  }

  if (error || !store) {
    return (
      <div className="p-6 text-destructive">Failed to load store: {resref}</div>
    );
  }

  const totalItems = store.categories.reduce((sum, cat) => sum + cat.items.length, 0);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="w-16 h-16 rounded-lg bg-muted flex items-center justify-center">
          <Store className="h-8 w-8 text-muted-foreground" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold">{store.name || store.resref}</h2>
          <div className="flex gap-2 mt-1 flex-wrap">
            <Badge variant="outline">{store.resref}</Badge>
            {store.tag && <Badge variant="secondary">{store.tag}</Badge>}
            <Badge>{totalItems} items</Badge>
          </div>
        </div>
      </div>

      {/* Quick Info */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <TrendingUp className="h-4 w-4" />
              <span>Markup</span>
            </div>
            <div className="text-xl font-bold mt-1">{store.settings.markup}%</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <TrendingDown className="h-4 w-4" />
              <span>Markdown</span>
            </div>
            <div className="text-xl font-bold mt-1">{store.settings.markdown}%</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Coins className="h-4 w-4" />
              <span>Store Gold</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {store.settings.store_gold === -1 ? 'Unlimited' : store.settings.store_gold.toLocaleString()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <CreditCard className="h-4 w-4" />
              <span>Max Buy</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {store.settings.max_buy_price === -1 ? 'No limit' : store.settings.max_buy_price.toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Settings Panel */}
      <StoreSettings storeResref={resref} settings={store.settings} />

      {/* View Mode Toggle */}
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

      {/* Category Tabs with Items (List View) */}
      {viewMode === 'list' && (
        <StoreCategoryTabs storeResref={resref} categories={store.categories} />
      )}

      {/* Position Editor (Grid View) */}
      {viewMode === 'grid' && (
        <StorePositionEditor
          storeResref={resref}
          categories={store.categories}
          onUpdateItem={handleUpdateItemPosition}
          isUpdating={updateItem.isPending}
        />
      )}

      {/* Raw Data */}
      {store.raw_data && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Raw Data</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-64">
              {JSON.stringify(store.raw_data, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
