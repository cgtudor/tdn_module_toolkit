import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useAppStore } from '@/store/appStore';
import { ItemBrowser } from '@/components/items/ItemBrowser';
import { CreatureBrowser } from '@/components/creatures/CreatureBrowser';
import { StoreBrowser } from '@/components/stores/StoreBrowser';
import { AreaBrowser } from '@/components/instances/AreaBrowser';
import { ItemPicker } from '@/components/shared/ItemPicker';

interface MainLayoutProps {
  onOpenSettings?: () => void;
}

export function MainLayout({ onOpenSettings }: MainLayoutProps) {
  const { currentView } = useAppStore();

  return (
    <div className="h-screen flex">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onOpenSettings={onOpenSettings} />
        <main className="flex-1 overflow-hidden">
          {currentView === 'items' && <ItemBrowser />}
          {currentView === 'creatures' && <CreatureBrowser />}
          {currentView === 'stores' && <StoreBrowser />}
          {currentView === 'areas' && <AreaBrowser />}
        </main>
      </div>
      <ItemPicker />
    </div>
  );
}
