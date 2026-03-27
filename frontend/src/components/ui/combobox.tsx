import * as React from 'react';
import { ChevronDown, Search, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ComboboxOption {
  id: number;
  label: string;
}

interface ComboboxProps {
  options: ComboboxOption[];
  value: number | null;
  onChange: (value: number) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  /** Format for displaying options, use {id} and {label} as placeholders */
  displayFormat?: string;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = 'Select...',
  searchPlaceholder = 'Search...',
  disabled = false,
  loading = false,
  className,
  displayFormat = '{label}',
}: ComboboxProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [search, setSearch] = React.useState('');
  const containerRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const formatDisplay = (option: ComboboxOption): string => {
    return displayFormat
      .replace('{id}', String(option.id))
      .replace('{label}', option.label);
  };

  const filteredOptions = React.useMemo(() => {
    if (!search) return options;
    const searchLower = search.toLowerCase();
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(searchLower) ||
        String(opt.id).includes(searchLower)
    );
  }, [options, search]);

  const selectedOption = React.useMemo(
    () => options.find((opt) => opt.id === value),
    [options, value]
  );

  // Close on click outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus input when opened
  React.useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSelect = (option: ComboboxOption) => {
    onChange(option.id);
    setIsOpen(false);
    setSearch('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      setSearch('');
    } else if (e.key === 'Enter' && filteredOptions.length === 1) {
      handleSelect(filteredOptions[0]);
    }
  };

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => !disabled && !loading && setIsOpen(!isOpen)}
        disabled={disabled || loading}
        className={cn(
          'flex h-8 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm',
          'focus:outline-none focus:ring-1 focus:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          isOpen && 'ring-1 ring-ring'
        )}
      >
        <span className={cn('truncate', !selectedOption && 'text-muted-foreground')}>
          {loading ? (
            <span className="flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading...
            </span>
          ) : selectedOption ? (
            formatDisplay(selectedOption)
          ) : (
            placeholder
          )}
        </span>
        <ChevronDown className={cn('h-4 w-4 opacity-50 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-zinc-700 bg-zinc-900 shadow-lg">
          {/* Search input */}
          <div className="flex items-center border-b px-2 py-1.5">
            <Search className="h-4 w-4 text-muted-foreground mr-2" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={searchPlaceholder}
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>

          {/* Options list */}
          <div className="max-h-[200px] overflow-auto p-1">
            {filteredOptions.length === 0 ? (
              <div className="py-4 text-center text-sm text-muted-foreground">
                No options found
              </div>
            ) : (
              filteredOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => handleSelect(option)}
                  className={cn(
                    'flex w-full items-center rounded-sm px-2 py-1.5 text-sm outline-none',
                    'hover:bg-accent hover:text-accent-foreground',
                    'focus:bg-accent focus:text-accent-foreground',
                    option.id === value && 'bg-accent'
                  )}
                >
                  <span className="text-muted-foreground text-xs mr-2 w-8 text-right">
                    {option.id}:
                  </span>
                  <span className="truncate">{option.label}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
