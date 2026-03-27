import { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { useAreaList, useAreaStores, useAreaCreatures, useAreaSearch } from '@/hooks/useInstances';
import { SearchInput } from '@/components/shared/SearchInput';
import { InstanceEditor } from './InstanceEditor';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ChevronLeft, ChevronRight, Map, Store, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

export function AreaBrowser() {
  const { selectedAreaResref, setSelectedAreaResref } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedInstance, setSelectedInstance] = useState<{ type: 'store' | 'creature'; index: number } | null>(null);
  const pageSize = 50;

  const { data: listResults, isLoading: listLoading } = useAreaList({
    offset: page * pageSize,
    limit: pageSize,
  });

  const { data: searchResults, isLoading: searchLoading } = useAreaSearch(searchQuery);

  const { data: storesData } = useAreaStores(selectedAreaResref);
  const { data: creaturesData } = useAreaCreatures(selectedAreaResref);

  // Use search results when searching, otherwise use paginated list
  const isLoading = searchQuery ? searchLoading : listLoading;
  const displayAreas = searchQuery ? searchResults?.areas : listResults?.areas;
  const totalPages = Math.ceil((listResults?.total || 0) / pageSize);

  return (
    <div className="h-full flex">
      {/* Areas List Panel */}
      <div className="w-72 border-r flex flex-col">
        <div className="p-4 border-b">
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search areas..."
          />
        </div>

        <ScrollArea className="flex-1">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground">Loading...</div>
          ) : !displayAreas?.length ? (
            <div className="p-4 text-center text-muted-foreground">No areas found</div>
          ) : (
            <div className="divide-y">
              {displayAreas.map((area) => (
                <button
                  key={area.resref}
                  className={cn(
                    "w-full px-4 py-3 text-left hover:bg-accent transition-colors flex items-center gap-3",
                    area.resref === selectedAreaResref && "bg-accent"
                  )}
                  onClick={() => {
                    setSelectedAreaResref(area.resref);
                    setSelectedInstance(null);
                  }}
                >
                  <div className="w-8 h-8 rounded bg-muted flex items-center justify-center flex-shrink-0">
                    <Map className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate text-sm">
                      {area.name || area.resref}
                    </div>
                    <div className="text-xs text-muted-foreground flex gap-2">
                      <span className="truncate">{area.resref}</span>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground flex-shrink-0">
                    <div>{area.store_count} stores</div>
                    <div>{area.creature_count} creatures</div>
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

      {/* Instances Panel */}
      <div className="w-80 border-r flex flex-col">
        {selectedAreaResref ? (
          <>
            <div className="p-4 border-b">
              <h3 className="font-semibold">{selectedAreaResref}</h3>
              <p className="text-xs text-muted-foreground">Instances in this area</p>
            </div>

            <Tabs defaultValue="stores" className="flex-1 flex flex-col">
              <TabsList className="mx-4 mt-2 grid grid-cols-2">
                <TabsTrigger value="stores" className="gap-1">
                  <Store className="h-4 w-4" />
                  Stores ({storesData?.stores?.length || 0})
                </TabsTrigger>
                <TabsTrigger value="creatures" className="gap-1">
                  <Users className="h-4 w-4" />
                  Creatures ({creaturesData?.creatures?.length || 0})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="stores" className="flex-1 overflow-auto m-0">
                <ScrollArea className="h-full">
                  {!storesData?.stores?.length ? (
                    <div className="p-4 text-center text-muted-foreground text-sm">
                      No store instances in this area
                    </div>
                  ) : (
                    <div className="divide-y">
                      {storesData.stores.map((store: any) => (
                        <button
                          key={store.index}
                          className={cn(
                            "w-full px-4 py-2 text-left hover:bg-accent transition-colors text-sm",
                            selectedInstance?.type === 'store' && selectedInstance?.index === store.index && "bg-accent"
                          )}
                          onClick={() => setSelectedInstance({ type: 'store', index: store.index })}
                        >
                          <div className="font-medium truncate">{store.name || store.resref}</div>
                          <div className="text-xs text-muted-foreground">
                            {store.resref} @ ({store.x.toFixed(1)}, {store.y.toFixed(1)})
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="creatures" className="flex-1 overflow-auto m-0">
                <ScrollArea className="h-full">
                  {!creaturesData?.creatures?.length ? (
                    <div className="p-4 text-center text-muted-foreground text-sm">
                      No creature instances in this area
                    </div>
                  ) : (
                    <div className="divide-y">
                      {creaturesData.creatures.map((creature: any) => (
                        <button
                          key={creature.index}
                          className={cn(
                            "w-full px-4 py-2 text-left hover:bg-accent transition-colors text-sm",
                            selectedInstance?.type === 'creature' && selectedInstance?.index === creature.index && "bg-accent"
                          )}
                          onClick={() => setSelectedInstance({ type: 'creature', index: creature.index })}
                        >
                          <div className="font-medium truncate">{creature.display_name || creature.resref}</div>
                          <div className="text-xs text-muted-foreground">
                            {creature.resref} @ ({creature.x.toFixed(1)}, {creature.y.toFixed(1)})
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            Select an area to view instances
          </div>
        )}
      </div>

      {/* Instance Detail Panel */}
      <div className="flex-1 overflow-auto">
        {selectedAreaResref && selectedInstance ? (
          <InstanceEditor
            areaResref={selectedAreaResref}
            instanceType={selectedInstance.type}
            instanceIndex={selectedInstance.index}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            {selectedAreaResref
              ? 'Select an instance to view details'
              : 'Select an area and instance to view details'}
          </div>
        )}
      </div>
    </div>
  );
}
