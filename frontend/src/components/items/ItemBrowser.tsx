import { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { useItemList, useItemSearch } from '@/hooks/useItems';
import { SearchInput } from '@/components/shared/SearchInput';
import { ItemCard } from './ItemCard';
import { ItemDetail } from './ItemDetail';
import { ItemFilters } from './ItemFilters';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export function ItemBrowser() {
  const { selectedItemResref, setSelectedItemResref } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [baseItemFilter, setBaseItemFilter] = useState<number | undefined>();
  const pageSize = 50;

  const { data: searchResults, isLoading: searchLoading } = useItemSearch(searchQuery, searchQuery.length > 0);
  const { data: listResults, isLoading: listLoading } = useItemList({
    offset: page * pageSize,
    limit: pageSize,
    base_item: baseItemFilter,
  });

  const items = searchQuery ? searchResults?.items : listResults?.items;
  const total = searchQuery ? searchResults?.total : listResults?.total;
  const isLoading = searchQuery ? searchLoading : listLoading;

  const totalPages = total ? Math.ceil(total / pageSize) : 0;

  return (
    <div className="h-full flex">
      {/* List Panel */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b space-y-3">
          <SearchInput
            value={searchQuery}
            onChange={(v) => {
              setSearchQuery(v);
              setPage(0);
            }}
            placeholder="Search items..."
          />
          <ItemFilters
            baseItem={baseItemFilter}
            onBaseItemChange={(v) => {
              setBaseItemFilter(v);
              setPage(0);
            }}
          />
        </div>

        <ScrollArea className="flex-1">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground">Loading...</div>
          ) : !items?.length ? (
            <div className="p-4 text-center text-muted-foreground">No items found</div>
          ) : (
            <div className="divide-y">
              {items.map((item) => (
                <ItemCard
                  key={item.resref}
                  item={item}
                  selected={item.resref === selectedItemResref}
                  onClick={() => setSelectedItemResref(item.resref)}
                />
              ))}
            </div>
          )}
        </ScrollArea>

        {!searchQuery && totalPages > 1 && (
          <div className="p-3 border-t flex items-center justify-between text-sm">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Detail Panel */}
      <div className="flex-1 overflow-auto">
        {selectedItemResref ? (
          <ItemDetail resref={selectedItemResref} />
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            Select an item to view details
          </div>
        )}
      </div>
    </div>
  );
}
