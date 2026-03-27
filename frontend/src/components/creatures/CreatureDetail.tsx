import { useCreature } from '@/hooks/useCreatures';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EquipmentPanel } from './EquipmentPanel';
import { InventoryGrid } from './InventoryGrid';
import { User, Tag, Users, Palette } from 'lucide-react';

interface CreatureDetailProps {
  resref: string;
}

export function CreatureDetail({ resref }: CreatureDetailProps) {
  const { data: creature, isLoading, error } = useCreature(resref);

  if (isLoading) {
    return (
      <div className="p-6 text-muted-foreground">Loading creature details...</div>
    );
  }

  if (error || !creature) {
    return (
      <div className="p-6 text-destructive">Failed to load creature: {resref}</div>
    );
  }

  const displayName = `${creature.first_name} ${creature.last_name}`.trim() || resref;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
          <User className="h-8 w-8 text-muted-foreground" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold">{displayName}</h2>
          <div className="flex gap-2 mt-1 flex-wrap">
            <Badge variant="outline">{creature.resref}</Badge>
            {creature.tag && <Badge variant="secondary">{creature.tag}</Badge>}
          </div>
        </div>
      </div>

      {/* Quick Info */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Users className="h-4 w-4" />
              <span>Race</span>
            </div>
            <div className="text-xl font-bold mt-1" title={`ID: ${creature.race}`}>
              {creature.race_name || creature.race}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Palette className="h-4 w-4" />
              <span>Appearance</span>
            </div>
            <div className="text-xl font-bold mt-1 truncate" title={creature.appearance_name || `ID: ${creature.appearance}`}>
              {creature.appearance_name || creature.appearance}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <User className="h-4 w-4" />
              <span>Gender</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {creature.gender === 0 ? 'Male' : creature.gender === 1 ? 'Female' : 'Other'}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Tag className="h-4 w-4" />
              <span>Faction</span>
            </div>
            <div className="text-xl font-bold mt-1" title={`ID: ${creature.faction_id}`}>
              {creature.faction_name || creature.faction_id}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Equipment and Inventory */}
      <div className="grid lg:grid-cols-2 gap-6">
        <EquipmentPanel
          creatureResref={resref}
          equipment={creature.equipment}
        />
        <InventoryGrid
          creatureResref={resref}
          inventory={creature.inventory}
        />
      </div>

      {/* Raw Data */}
      {creature.raw_data && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Raw Data</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-64">
              {JSON.stringify(creature.raw_data, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
