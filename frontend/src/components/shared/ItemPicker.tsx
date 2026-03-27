import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAppStore } from '@/store/appStore';
import { useItemSearch, useItemList } from '@/hooks/useItems';
import { getBaseItemName } from '@/lib/baseItems';
import { Search, Package } from 'lucide-react';

export function ItemPicker() {
  const { itemPickerOpen, closeItemPicker, itemPickerCallback } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');

  const { data: searchResults, isLoading: searchLoading } = useItemSearch(searchQuery, searchQuery.length > 0);
  const { data: listResults, isLoading: listLoading } = useItemList({ limit: 50 });

  const items = searchQuery ? searchResults?.items : listResults?.items;
  const isLoading = searchQuery ? searchLoading : listLoading;

  const handleSelect = (resref: string) => {
    if (itemPickerCallback) {
      itemPickerCallback(resref);
    }
    closeItemPicker();
    setSearchQuery('');
  };

  return (
    <Dialog open={itemPickerOpen} onOpenChange={(open) => !open && closeItemPicker()}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Select Item</DialogTitle>
        </DialogHeader>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search items..."
            className="pl-9"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
          />
        </div>

        <ScrollArea className="flex-1 min-h-0 max-h-96 border rounded-md">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground">Loading...</div>
          ) : !items?.length ? (
            <div className="p-4 text-center text-muted-foreground">
              {searchQuery ? 'No items found' : 'No items available'}
            </div>
          ) : (
            <div className="divide-y">
              {items.map((item) => (
                <button
                  key={item.resref}
                  className="w-full px-4 py-3 text-left hover:bg-accent flex items-center gap-3 transition-colors"
                  onClick={() => handleSelect(item.resref)}
                >
                  <div className="w-8 h-8 rounded bg-muted flex items-center justify-center">
                    <Package className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">
                      {item.name || item.resref}
                    </div>
                    <div className="text-xs text-muted-foreground flex gap-2">
                      <span>{item.resref}</span>
                      <span>|</span>
                      <span>{getBaseItemName(item.base_item)}</span>
                      {item.cost > 0 && (
                        <>
                          <span>|</span>
                          <span>{item.cost.toLocaleString()} gp</span>
                        </>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        <div className="flex justify-end">
          <Button variant="outline" onClick={closeItemPicker}>
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
