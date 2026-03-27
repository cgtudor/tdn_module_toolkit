import { useBaseItemCounts } from '@/hooks/useItems';

interface ItemFiltersProps {
  baseItem: number | undefined;
  onBaseItemChange: (value: number | undefined) => void;
}

export function ItemFilters({ baseItem, onBaseItemChange }: ItemFiltersProps) {
  const { data } = useBaseItemCounts();

  return (
    <div>
      <select
        className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
        value={baseItem ?? ''}
        onChange={(e) => onBaseItemChange(e.target.value ? Number(e.target.value) : undefined)}
      >
        <option value="">All item types</option>
        {data?.base_items.slice(0, 30).map(({ base_item, name, count }) => (
          <option key={base_item} value={base_item}>
            {name} ({count})
          </option>
        ))}
      </select>
    </div>
  );
}
