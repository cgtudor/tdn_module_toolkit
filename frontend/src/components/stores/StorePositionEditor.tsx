import { useState, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { StoreCategory, StoreItem } from '@/types/store';
import { STORE_CATEGORY_DEFS } from '@/lib/storeCategories';
import { GripVertical, Save, ChevronLeft, ChevronRight } from 'lucide-react';

// NWN store panel grid dimensions
const GRID_COLS = 10;
const GRID_ROWS = 10; // Per page
const CELL_SIZE = 32; // pixels

interface StorePositionEditorProps {
  storeResref: string;
  categories: StoreCategory[];
  onUpdateItem: (categoryId: number, index: number, repos_x: number, repos_y: number) => void;
  isUpdating?: boolean;
}

interface DragState {
  item: StoreItem;
  categoryId: number;
  offsetX: number;
  offsetY: number;
}

export function StorePositionEditor({ storeResref: _storeResref, categories, onUpdateItem, isUpdating }: StorePositionEditorProps) {
  void _storeResref; // Reserved for future use
  const [activeTab, setActiveTab] = useState('0');
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [pendingChanges, setPendingChanges] = useState<Map<string, { categoryId: number; index: number; repos_x: number; repos_y: number }>>(new Map());
  const [currentPage, setCurrentPage] = useState<Record<number, number>>({});

  const categoryMap = new Map(categories.map(c => [c.category_id, c]));

  // Calculate max page for each category
  const maxPages = useMemo(() => {
    const pages: Record<number, number> = {};
    categories.forEach(cat => {
      let maxY = 0;
      cat.items.forEach(item => {
        const key = `${cat.category_id}-${item.index}`;
        const pending = pendingChanges.get(key);
        const y = pending ? pending.repos_y : item.repos_y;
        const itemHeight = item.inv_slot_height || 1;
        maxY = Math.max(maxY, y + itemHeight);
      });
      pages[cat.category_id] = Math.max(1, Math.ceil(maxY / GRID_ROWS));
    });
    return pages;
  }, [categories, pendingChanges]);

  const getPage = (categoryId: number) => currentPage[categoryId] || 0;

  const handleDragStart = useCallback((e: React.DragEvent, item: StoreItem, categoryId: number) => {
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const offsetX = e.clientX - rect.left;
    const offsetY = e.clientY - rect.top;

    setDragState({ item, categoryId, offsetX, offsetY });
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', item.resref);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, categoryId: number) => {
    e.preventDefault();
    if (!dragState || dragState.categoryId !== categoryId) return;

    const gridRect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const dropX = e.clientX - gridRect.left - dragState.offsetX;
    // Y is from bottom in NWN, but we display from top, so flip it
    const dropY = gridRect.height - (e.clientY - gridRect.top) - (dragState.item.inv_slot_height || 1) * CELL_SIZE + dragState.offsetY;

    // Snap to grid
    const page = getPage(categoryId);
    const pageOffset = page * GRID_ROWS;
    const newX = Math.max(0, Math.min(GRID_COLS - (dragState.item.inv_slot_width || 1), Math.round(dropX / CELL_SIZE)));
    const newY = Math.max(0, Math.round(dropY / CELL_SIZE)) + pageOffset;

    // Store pending change
    const key = `${categoryId}-${dragState.item.index}`;
    setPendingChanges(prev => new Map(prev).set(key, {
      categoryId,
      index: dragState.item.index,
      repos_x: newX,
      repos_y: newY,
    }));

    setDragState(null);
  }, [dragState, currentPage]);

  const handleDragEnd = useCallback(() => {
    setDragState(null);
  }, []);

  const saveAllChanges = useCallback(() => {
    pendingChanges.forEach((change) => {
      onUpdateItem(change.categoryId, change.index, change.repos_x, change.repos_y);
    });
    setPendingChanges(new Map());
  }, [pendingChanges, onUpdateItem]);

  const getItemPosition = (item: StoreItem, categoryId: number) => {
    const key = `${categoryId}-${item.index}`;
    const pending = pendingChanges.get(key);
    if (pending) {
      return { x: pending.repos_x, y: pending.repos_y };
    }
    return { x: item.repos_x, y: item.repos_y };
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Position Editor</CardTitle>
          {pendingChanges.size > 0 && (
            <Button size="sm" onClick={saveAllChanges} disabled={isUpdating}>
              <Save className="h-4 w-4 mr-1" />
              Save Positions ({pendingChanges.size})
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Drag items to reposition. Y=0 is at bottom (NWN convention). Grid is 10x10 per page.
        </p>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid grid-cols-5 w-full mb-4">
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
            const page = getPage(cat.id);
            const totalPages = maxPages[cat.id] || 1;
            const pageOffset = page * GRID_ROWS;

            // Filter items for current page
            const pageItems = items.filter(item => {
              const pos = getItemPosition(item, cat.id);
              const itemHeight = item.inv_slot_height || 1;
              const itemTop = pos.y;
              const itemBottom = pos.y + itemHeight;
              const pageTop = pageOffset;
              const pageBottom = pageOffset + GRID_ROWS;
              return itemBottom > pageTop && itemTop < pageBottom;
            });

            return (
              <TabsContent key={cat.id} value={String(cat.id)} className="mt-0">
                {/* Page navigation */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page === 0}
                      onClick={() => setCurrentPage(prev => ({ ...prev, [cat.id]: page - 1 }))}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm">Page {page + 1} of {totalPages}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages - 1}
                      onClick={() => setCurrentPage(prev => ({ ...prev, [cat.id]: page + 1 }))}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                )}

                <div
                  className="relative border rounded bg-muted/20 overflow-hidden mx-auto"
                  style={{
                    width: GRID_COLS * CELL_SIZE,
                    height: GRID_ROWS * CELL_SIZE,
                  }}
                  onDragOver={handleDragOver}
                  onDrop={(e) => handleDrop(e, cat.id)}
                >
                  {/* Grid lines */}
                  <div
                    className="absolute inset-0 pointer-events-none"
                    style={{
                      backgroundImage: `
                        linear-gradient(to right, hsl(var(--border)) 1px, transparent 1px),
                        linear-gradient(to bottom, hsl(var(--border)) 1px, transparent 1px)
                      `,
                      backgroundSize: `${CELL_SIZE}px ${CELL_SIZE}px`,
                    }}
                  />

                  {/* Y-axis label (bottom = 0) */}
                  <div className="absolute -left-6 bottom-0 text-[10px] text-muted-foreground">
                    Y={pageOffset}
                  </div>
                  <div className="absolute -left-6 top-0 text-[10px] text-muted-foreground">
                    Y={pageOffset + GRID_ROWS}
                  </div>

                  {/* Items - Y is flipped (0 at bottom) */}
                  {pageItems.map((item) => {
                    const pos = getItemPosition(item, cat.id);
                    const width = (item.inv_slot_width || 1) * CELL_SIZE;
                    const height = (item.inv_slot_height || 1) * CELL_SIZE;
                    const isPending = pendingChanges.has(`${cat.id}-${item.index}`);

                    // Convert Y: in NWN, Y=0 is bottom. In our display, we flip it.
                    const displayY = GRID_ROWS * CELL_SIZE - (pos.y - pageOffset + (item.inv_slot_height || 1)) * CELL_SIZE;

                    return (
                      <div
                        key={item.index}
                        draggable
                        onDragStart={(e) => handleDragStart(e, item, cat.id)}
                        onDragEnd={handleDragEnd}
                        className={`absolute cursor-move rounded border-2 flex flex-col items-center justify-center text-xs overflow-hidden transition-all ${
                          isPending
                            ? 'border-yellow-500 bg-yellow-500/20'
                            : 'border-primary/50 bg-primary/10 hover:border-primary hover:bg-primary/20'
                        }`}
                        style={{
                          left: pos.x * CELL_SIZE,
                          top: displayY,
                          width: width - 2,
                          height: height - 2,
                        }}
                        title={`${item.name || item.resref}\nPosition: (${pos.x}, ${pos.y})\nSize: ${item.inv_slot_width || 1}x${item.inv_slot_height || 1}`}
                      >
                        <GripVertical className="h-3 w-3 text-muted-foreground mb-0.5" />
                        <span className="truncate max-w-full px-1 text-center leading-tight">
                          {item.name || item.resref}
                        </span>
                        {item.infinite && (
                          <span className="text-[10px] text-muted-foreground">∞</span>
                        )}
                      </div>
                    );
                  })}

                  {/* Empty state */}
                  {items.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                      No items in this category
                    </div>
                  )}
                </div>
              </TabsContent>
            );
          })}
        </Tabs>
      </CardContent>
    </Card>
  );
}
