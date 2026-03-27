import { Package, Users, Store, Map, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppStore, ViewType } from '@/store/appStore';
import { useSystemStatus, useReindex } from '@/hooks/useInstances';
import { cn } from '@/lib/utils';

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  view: ViewType;
  count?: number;
}

function NavItem({ icon, label, view, count }: NavItemProps) {
  const { currentView, setCurrentView } = useAppStore();
  const isActive = currentView === view;

  return (
    <button
      onClick={() => setCurrentView(view)}
      className={cn(
        "w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
        isActive
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
    >
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {count !== undefined && (
        <span className={cn(
          "text-xs px-2 py-0.5 rounded-full",
          isActive ? "bg-primary-foreground/20" : "bg-muted"
        )}>
          {count.toLocaleString()}
        </span>
      )}
    </button>
  );
}

export function Sidebar() {
  const { data: status } = useSystemStatus();
  const reindex = useReindex();

  const counts = status?.counts || { items: 0, creatures: 0, stores: 0, areas: 0 };

  return (
    <div className="w-64 border-r bg-card flex flex-col h-full">
      <div className="p-4 border-b">
        <h1 className="text-xl font-bold">Module Toolkit</h1>
        <p className="text-xs text-muted-foreground mt-1">TDN Module Tools</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        <NavItem
          icon={<Package className="h-4 w-4" />}
          label="Items"
          view="items"
          count={counts.items}
        />
        <NavItem
          icon={<Users className="h-4 w-4" />}
          label="Creatures"
          view="creatures"
          count={counts.creatures}
        />
        <NavItem
          icon={<Store className="h-4 w-4" />}
          label="Stores"
          view="stores"
          count={counts.stores}
        />
        <NavItem
          icon={<Map className="h-4 w-4" />}
          label="Areas"
          view="areas"
          count={counts.areas}
        />
      </nav>

      <div className="p-3 border-t">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => reindex.mutate()}
          disabled={reindex.isPending}
        >
          <RefreshCw className={cn("h-4 w-4 mr-2", reindex.isPending && "animate-spin")} />
          {reindex.isPending ? "Reindexing..." : "Reindex Files"}
        </Button>

        <div className="mt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-2 h-2 rounded-full",
              status?.file_watcher ? "bg-green-500" : "bg-red-500"
            )} />
            <span>File watcher {status?.file_watcher ? "active" : "inactive"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
