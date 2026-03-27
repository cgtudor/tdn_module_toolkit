import { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { useStoreList, useStoreSearch } from '@/hooks/useStores';
import { SearchInput } from '@/components/shared/SearchInput';
import { StoreDetail } from './StoreDetail';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, Store } from 'lucide-react';
import { cn } from '@/lib/utils';

export function StoreBrowser() {
  const { selectedStoreResref, setSelectedStoreResref } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const { data: searchResults, isLoading: searchLoading } = useStoreSearch(searchQuery, searchQuery.length > 0);
  const { data: listResults, isLoading: listLoading } = useStoreList({
    offset: page * pageSize,
    limit: pageSize,
  });

  const stores = (searchQuery ? searchResults?.stores : listResults?.stores) as import('@/types/store').StoreSummary[] | undefined;
  const total = searchQuery ? searchResults?.total : listResults?.total;
  const isLoading = searchQuery ? searchLoading : listLoading;

  const totalPages = total ? Math.ceil(total / pageSize) : 0;

  return (
    <div className="h-full flex">
      {/* List Panel */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <SearchInput
            value={searchQuery}
            onChange={(v) => {
              setSearchQuery(v);
              setPage(0);
            }}
            placeholder="Search stores..."
          />
        </div>

        <ScrollArea className="flex-1">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground">Loading...</div>
          ) : !stores?.length ? (
            <div className="p-4 text-center text-muted-foreground">No stores found</div>
          ) : (
            <div className="divide-y">
              {stores.map((store) => (
                <button
                  key={store.resref}
                  className={cn(
                    "w-full px-4 py-3 text-left hover:bg-accent transition-colors flex items-center gap-3",
                    store.resref === selectedStoreResref && "bg-accent"
                  )}
                  onClick={() => setSelectedStoreResref(store.resref)}
                >
                  <div className="w-8 h-8 rounded bg-muted flex items-center justify-center flex-shrink-0">
                    <Store className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">
                      {store.name || store.resref}
                    </div>
                    <div className="text-xs text-muted-foreground flex gap-2">
                      <span className="truncate">{store.resref}</span>
                      <span>|</span>
                      <span>{store.item_count} items</span>
                    </div>
                  </div>
                </button>
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
        {selectedStoreResref ? (
          <StoreDetail resref={selectedStoreResref} />
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            Select a store to view details
          </div>
        )}
      </div>
    </div>
  );
}
