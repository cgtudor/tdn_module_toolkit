import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { useUpdateStoreSettings } from '@/hooks/useStores';
import { StoreSettings as StoreSettingsType } from '@/types/store';
import { Settings, Save } from 'lucide-react';

interface StoreSettingsProps {
  storeResref: string;
  settings: StoreSettingsType;
}

export function StoreSettings({ storeResref, settings }: StoreSettingsProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedSettings, setEditedSettings] = useState(settings);
  const updateSettings = useUpdateStoreSettings();

  const handleSave = () => {
    updateSettings.mutate(
      { resref: storeResref, settings: editedSettings as unknown as Record<string, unknown> },
      {
        onSuccess: () => setIsEditing(false),
      }
    );
  };

  const handleCancel = () => {
    setEditedSettings(settings);
    setIsEditing(false);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Store Settings
          </CardTitle>
          {!isEditing ? (
            <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
              Edit
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleCancel}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} disabled={updateSettings.isPending}>
                <Save className="h-4 w-4 mr-1" />
                Save
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-medium">Markup (%)</label>
            <Input
              type="number"
              value={editedSettings.markup}
              onChange={(e) => setEditedSettings({ ...editedSettings, markup: parseInt(e.target.value) || 0 })}
              disabled={!isEditing}
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Markdown (%)</label>
            <Input
              type="number"
              value={editedSettings.markdown}
              onChange={(e) => setEditedSettings({ ...editedSettings, markdown: parseInt(e.target.value) || 0 })}
              disabled={!isEditing}
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Store Gold (-1 = unlimited)</label>
            <Input
              type="number"
              value={editedSettings.store_gold}
              onChange={(e) => setEditedSettings({ ...editedSettings, store_gold: parseInt(e.target.value) || 0 })}
              disabled={!isEditing}
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Max Buy Price (-1 = no limit)</label>
            <Input
              type="number"
              value={editedSettings.max_buy_price}
              onChange={(e) => setEditedSettings({ ...editedSettings, max_buy_price: parseInt(e.target.value) || 0 })}
              disabled={!isEditing}
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Identify Price</label>
            <Input
              type="number"
              value={editedSettings.identify_price}
              onChange={(e) => setEditedSettings({ ...editedSettings, identify_price: parseInt(e.target.value) || 0 })}
              disabled={!isEditing}
              className="mt-1"
            />
          </div>

          <div className="flex items-center gap-3 pt-6">
            <Switch
              checked={editedSettings.black_market}
              onCheckedChange={(checked) => setEditedSettings({ ...editedSettings, black_market: checked })}
              disabled={!isEditing}
            />
            <label className="text-sm font-medium">Black Market</label>
          </div>

          {editedSettings.black_market && (
            <div>
              <label className="text-sm font-medium">BM Markdown (%)</label>
              <Input
                type="number"
                value={editedSettings.bm_markdown}
                onChange={(e) => setEditedSettings({ ...editedSettings, bm_markdown: parseInt(e.target.value) || 0 })}
                disabled={!isEditing}
                className="mt-1"
              />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
