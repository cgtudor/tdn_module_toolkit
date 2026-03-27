import { Search, Settings, Sun, Moon, Save } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/appStore';
import { useGlobalSearch } from '@/hooks/useInstances';
import { systemApi } from '@/lib/api';
import { useState, useRef, useEffect } from 'react';

interface HeaderProps {
  onOpenSettings?: () => void;
}

export function Header({ onOpenSettings }: HeaderProps) {
  const { globalSearchQuery, setGlobalSearchQuery, setCurrentView, setSelectedItemResref, setSelectedCreatureResref, setSelectedStoreResref, darkMode, toggleDarkMode, systemStatus } = useAppStore();
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { data: results } = useGlobalSearch(globalSearchQuery, globalSearchQuery.length > 0);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (type: 'item' | 'creature' | 'store', resref: string) => {
    if (type === 'item') {
      setCurrentView('items');
      setSelectedItemResref(resref);
    } else if (type === 'creature') {
      setCurrentView('creatures');
      setSelectedCreatureResref(resref);
    } else {
      setCurrentView('stores');
      setSelectedStoreResref(resref);
    }
    setIsOpen(false);
    setGlobalSearchQuery('');
  };

  return (
    <header className="h-14 border-b bg-card flex items-center px-4 gap-4">
      <div className="relative flex-1 max-w-md" ref={dropdownRef}>
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          placeholder="Search items, creatures, stores..."
          className="pl-9"
          value={globalSearchQuery}
          onChange={(e) => {
            setGlobalSearchQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
        />

        {isOpen && globalSearchQuery && results && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-card border rounded-md shadow-lg z-50 max-h-96 overflow-auto">
            {results.items.length === 0 && results.creatures.length === 0 && results.stores.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                No results found
              </div>
            ) : (
              <>
                {results.items.length > 0 && (
                  <div>
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground bg-muted">
                      Items ({results.items.length})
                    </div>
                    {results.items.slice(0, 5).map((item) => (
                      <button
                        key={item.resref}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex justify-between"
                        onClick={() => handleSelect('item', item.resref)}
                      >
                        <span>{item.name || item.resref}</span>
                        <span className="text-muted-foreground">{item.resref}</span>
                      </button>
                    ))}
                  </div>
                )}

                {results.creatures.length > 0 && (
                  <div>
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground bg-muted">
                      Creatures ({results.creatures.length})
                    </div>
                    {results.creatures.slice(0, 5).map((creature) => (
                      <button
                        key={creature.resref}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex justify-between"
                        onClick={() => handleSelect('creature', creature.resref)}
                      >
                        <span>{creature.display_name || creature.resref}</span>
                        <span className="text-muted-foreground">{creature.resref}</span>
                      </button>
                    ))}
                  </div>
                )}

                {results.stores.length > 0 && (
                  <div>
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground bg-muted">
                      Stores ({results.stores.length})
                    </div>
                    {results.stores.slice(0, 5).map((store) => (
                      <button
                        key={store.resref}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex justify-between"
                        onClick={() => handleSelect('store', store.resref)}
                      >
                        <span>{store.name || store.resref}</span>
                        <span className="text-muted-foreground">{store.resref}</span>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Mode badge */}
      <span className={`text-xs font-medium px-2 py-1 rounded ${
        systemStatus.mode === 'mod_file'
          ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
          : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
      }`}>
        {systemStatus.mode === 'mod_file' ? 'MOD' : 'JSON'}
      </span>

      {/* Save button (MOD mode only) */}
      {systemStatus.mode === 'mod_file' && systemStatus.dirtyCount > 0 && (
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          disabled={isSaving}
          onClick={async () => {
            setIsSaving(true);
            try {
              await systemApi.save();
            } catch (err) {
              console.error('Save failed:', err);
            } finally {
              setIsSaving(false);
            }
          }}
          title={`Save ${systemStatus.dirtyCount} pending change${systemStatus.dirtyCount === 1 ? '' : 's'} to .mod file`}
        >
          <Save className="h-4 w-4" />
          Save ({systemStatus.dirtyCount})
        </Button>
      )}

      {/* Dark mode toggle */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleDarkMode}
        title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
      </Button>

      {/* Settings button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={onOpenSettings}
        title="Settings"
      >
        <Settings className="h-5 w-5" />
      </Button>
    </header>
  );
}
