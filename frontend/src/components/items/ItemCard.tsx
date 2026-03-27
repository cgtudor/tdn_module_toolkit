import { getBaseItemName } from '@/lib/baseItems';
import { cn } from '@/lib/utils';
import { ItemSummary } from '@/types/item';
import { ItemIcon } from './ItemIcon';

interface ItemCardProps {
  item: ItemSummary;
  selected: boolean;
  onClick: () => void;
}

export function ItemCard({ item, selected, onClick }: ItemCardProps) {
  return (
    <button
      className={cn(
        "w-full px-4 py-3 text-left hover:bg-accent transition-colors flex items-center gap-3",
        selected && "bg-accent"
      )}
      onClick={onClick}
    >
      <ItemIcon resref={item.resref} baseItem={item.base_item} size="sm" />
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">
          {item.name || item.resref}
        </div>
        <div className="text-xs text-muted-foreground flex gap-2">
          <span className="truncate">{item.resref}</span>
          <span>|</span>
          <span className="truncate">{getBaseItemName(item.base_item)}</span>
        </div>
      </div>
      {item.cost > 0 && (
        <div className="text-sm text-muted-foreground flex-shrink-0">
          {item.cost.toLocaleString()}g
        </div>
      )}
    </button>
  );
}
