import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Combobox, ComboboxOption } from '@/components/ui/combobox';
import { Plus, Trash2, Edit2, Check, X, Code } from 'lucide-react';
import { ItemProperty, ItemPropertyInput, PropertyTypeOption } from '@/types/item';
import { usePropertyTypes, usePropertySubtypes, usePropertyCostValues } from '@/hooks/useItems';

interface ItemPropertyEditorProps {
  /** Original properties with resolved names for display */
  originalProperties: ItemProperty[];
  /** Current edited properties (controlled) */
  properties: ItemPropertyInput[];
  /** Called when properties change */
  onChange: (properties: ItemPropertyInput[]) => void;
}

export function ItemPropertyEditor({ originalProperties, properties, onChange }: ItemPropertyEditorProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<ItemPropertyInput | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [showRawIds, setShowRawIds] = useState(false);
  const [newProperty, setNewProperty] = useState<ItemPropertyInput>({
    property_name: 0,
    subtype: 0,
    cost_table: 0,
    cost_value: 0,
    param1: 255,
    param1_value: 0,
    chance_appear: 100,
  });

  // Fetch property types
  const { data: propertyTypesData, isLoading: typesLoading } = usePropertyTypes();
  const propertyTypes = propertyTypesData?.properties || [];

  // Convert to combobox options
  const propertyTypeOptions: ComboboxOption[] = propertyTypes.map((p) => ({
    id: p.id,
    label: p.label,
  }));

  // Find resolved names from original properties if available
  const getResolvedInfo = (propInput: ItemPropertyInput, index: number): {
    name_resolved?: string;
    subtype_resolved?: string;
    cost_value_resolved?: string;
  } => {
    // Try to find matching original property by index or property_name
    const originalProp = originalProperties[index];
    if (originalProp && originalProp.property_name === propInput.property_name) {
      return {
        name_resolved: originalProp.property_name_resolved,
        subtype_resolved: originalProp.subtype === propInput.subtype ? originalProp.subtype_resolved : undefined,
        cost_value_resolved: originalProp.cost_value === propInput.cost_value ? originalProp.cost_value_resolved : undefined,
      };
    }
    return {};
  };

  const handleDelete = (index: number) => {
    const newProps = [...properties];
    newProps.splice(index, 1);
    onChange(newProps);
  };

  const handleStartEdit = (index: number) => {
    const prop = properties[index];
    setEditingIndex(index);
    setEditForm({
      property_name: prop.property_name,
      subtype: prop.subtype ?? 0,
      cost_table: prop.cost_table ?? 0,
      cost_value: prop.cost_value ?? 0,
      param1: prop.param1 ?? 255,
      param1_value: prop.param1_value ?? 0,
      chance_appear: prop.chance_appear ?? 100,
    });
  };

  const handleSaveEdit = () => {
    if (editingIndex === null || !editForm) return;
    const newProps = [...properties];
    newProps[editingIndex] = editForm;
    onChange(newProps);
    setEditingIndex(null);
    setEditForm(null);
  };

  const handleCancelEdit = () => {
    setEditingIndex(null);
    setEditForm(null);
  };

  const handleAddProperty = () => {
    const newProps = [...properties, { ...newProperty }];
    onChange(newProps);
    setIsAdding(false);
    setNewProperty({
      property_name: 0,
      subtype: 0,
      cost_table: 0,
      cost_value: 0,
      param1: 255,
      param1_value: 0,
      chance_appear: 100,
    });
  };

  // Get property type metadata
  const getPropertyTypeMeta = (propertyId: number): PropertyTypeOption | undefined => {
    return propertyTypes.find((p) => p.id === propertyId);
  };

  // Property form with dropdowns
  const PropertyFormWithDropdowns = ({
    form,
    setForm,
    isCompact = false,
  }: {
    form: ItemPropertyInput;
    setForm: (f: ItemPropertyInput) => void;
    isCompact?: boolean;
  }) => {
    const propMeta = getPropertyTypeMeta(form.property_name);

    // Fetch subtypes and cost values based on selected property
    const { data: subtypesData, isLoading: subtypesLoading } = usePropertySubtypes(
      propMeta?.has_subtype ? form.property_name : null
    );
    const { data: costValuesData, isLoading: costValuesLoading } = usePropertyCostValues(
      propMeta?.has_cost_value ? form.property_name : null
    );

    const subtypeOptions: ComboboxOption[] = subtypesData?.subtypes || [];
    const costValueOptions: ComboboxOption[] = costValuesData?.cost_values || [];

    const handlePropertyTypeChange = (newPropertyId: number) => {
      const newMeta = getPropertyTypeMeta(newPropertyId);
      setForm({
        ...form,
        property_name: newPropertyId,
        subtype: 0,
        cost_value: 0,
        cost_table: newMeta?.cost_table ?? 0,
      });
    };

    if (showRawIds) {
      // Raw ID mode - show number inputs
      return (
        <div className={`grid ${isCompact ? 'grid-cols-4' : 'grid-cols-2'} gap-2`}>
          <div>
            <Label className="text-xs">Property ID *</Label>
            <Input
              type="number"
              min={0}
              value={form.property_name}
              onChange={(e) => setForm({ ...form, property_name: parseInt(e.target.value) || 0 })}
              className="h-8"
            />
          </div>
          <div>
            <Label className="text-xs">Subtype</Label>
            <Input
              type="number"
              min={0}
              value={form.subtype ?? 0}
              onChange={(e) => setForm({ ...form, subtype: parseInt(e.target.value) || 0 })}
              className="h-8"
            />
          </div>
          <div>
            <Label className="text-xs">Cost Table</Label>
            <Input
              type="number"
              min={0}
              value={form.cost_table ?? 0}
              onChange={(e) => setForm({ ...form, cost_table: parseInt(e.target.value) || 0 })}
              className="h-8"
            />
          </div>
          <div>
            <Label className="text-xs">Cost Value</Label>
            <Input
              type="number"
              min={0}
              value={form.cost_value ?? 0}
              onChange={(e) => setForm({ ...form, cost_value: parseInt(e.target.value) || 0 })}
              className="h-8"
            />
          </div>
          {!isCompact && (
            <>
              <div>
                <Label className="text-xs">Param1</Label>
                <Input
                  type="number"
                  min={0}
                  max={255}
                  value={form.param1 ?? 255}
                  onChange={(e) => setForm({ ...form, param1: parseInt(e.target.value) || 255 })}
                  className="h-8"
                />
              </div>
              <div>
                <Label className="text-xs">Param1 Value</Label>
                <Input
                  type="number"
                  min={0}
                  value={form.param1_value ?? 0}
                  onChange={(e) => setForm({ ...form, param1_value: parseInt(e.target.value) || 0 })}
                  className="h-8"
                />
              </div>
              <div>
                <Label className="text-xs">Chance Appear (%)</Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={form.chance_appear ?? 100}
                  onChange={(e) => setForm({ ...form, chance_appear: parseInt(e.target.value) || 100 })}
                  className="h-8"
                />
              </div>
            </>
          )}
        </div>
      );
    }

    // Dropdown mode
    return (
      <div className="space-y-2">
        {/* Property Type */}
        <div>
          <Label className="text-xs">Property Type *</Label>
          <Combobox
            options={propertyTypeOptions}
            value={form.property_name}
            onChange={handlePropertyTypeChange}
            placeholder="Select property type..."
            searchPlaceholder="Search properties..."
            loading={typesLoading}
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          {/* Subtype - only show if property has subtypes */}
          {propMeta?.has_subtype && (
            <div>
              <Label className="text-xs">Subtype</Label>
              {subtypesLoading ? (
                <div className="h-8 flex items-center text-xs text-muted-foreground">
                  Loading subtypes...
                </div>
              ) : subtypeOptions.length > 0 ? (
                <Combobox
                  options={subtypeOptions}
                  value={form.subtype ?? 0}
                  onChange={(v) => setForm({ ...form, subtype: v })}
                  placeholder="Select subtype..."
                  searchPlaceholder="Search..."
                />
              ) : (
                <Input
                  type="number"
                  min={0}
                  value={form.subtype ?? 0}
                  onChange={(e) => setForm({ ...form, subtype: parseInt(e.target.value) || 0 })}
                  className="h-8"
                />
              )}
            </div>
          )}

          {/* Cost Value - only show if property has cost values */}
          {propMeta?.has_cost_value && (
            <div>
              <Label className="text-xs">Value</Label>
              {costValuesLoading ? (
                <div className="h-8 flex items-center text-xs text-muted-foreground">
                  Loading values...
                </div>
              ) : costValueOptions.length > 0 ? (
                <Combobox
                  options={costValueOptions}
                  value={form.cost_value ?? 0}
                  onChange={(v) => setForm({ ...form, cost_value: v })}
                  placeholder="Select value..."
                  searchPlaceholder="Search..."
                />
              ) : (
                <Input
                  type="number"
                  min={0}
                  value={form.cost_value ?? 0}
                  onChange={(e) => setForm({ ...form, cost_value: parseInt(e.target.value) || 0 })}
                  className="h-8"
                />
              )}
            </div>
          )}
        </div>

        {/* Advanced options (collapsible in compact mode) */}
        {!isCompact && (
          <div className="grid grid-cols-3 gap-2 pt-2 border-t">
            <div>
              <Label className="text-xs text-muted-foreground">Param1</Label>
              <Input
                type="number"
                min={0}
                max={255}
                value={form.param1 ?? 255}
                onChange={(e) => setForm({ ...form, param1: parseInt(e.target.value) || 255 })}
                className="h-8"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Param1 Value</Label>
              <Input
                type="number"
                min={0}
                value={form.param1_value ?? 0}
                onChange={(e) => setForm({ ...form, param1_value: parseInt(e.target.value) || 0 })}
                className="h-8"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Chance (%)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={form.chance_appear ?? 100}
                onChange={(e) => setForm({ ...form, chance_appear: parseInt(e.target.value) || 100 })}
                className="h-8"
              />
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">
          Item Properties ({properties.length})
        </Label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowRawIds(!showRawIds)}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            title={showRawIds ? 'Show dropdowns' : 'Show raw IDs'}
          >
            <Code className="h-3 w-3" />
            {showRawIds ? 'Dropdowns' : 'Raw IDs'}
          </button>
          {!isAdding && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsAdding(true)}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add Property
            </Button>
          )}
        </div>
      </div>

      {/* Add New Property Form */}
      {isAdding && (
        <Card className="border-green-500/50">
          <CardContent className="pt-4 space-y-3">
            <div className="text-sm font-medium text-green-600">Add New Property</div>
            <PropertyFormWithDropdowns form={newProperty} setForm={setNewProperty} />
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsAdding(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={handleAddProperty}
              >
                <Plus className="h-4 w-4 mr-1" />
                Add
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Property List */}
      <ScrollArea className="h-[300px] border rounded-md">
        <div className="p-2 space-y-2">
          {properties.length === 0 ? (
            <div className="text-center text-muted-foreground py-8 text-sm">
              No properties. Click "Add Property" to add one.
            </div>
          ) : (
            properties.map((prop, index) => {
              const resolved = getResolvedInfo(prop, index);
              const propMeta = getPropertyTypeMeta(prop.property_name);
              return (
                <Card key={index} className={editingIndex === index ? 'border-blue-500/50' : ''}>
                  <CardContent className="pt-3 pb-3">
                    {editingIndex === index && editForm ? (
                      // Edit Mode
                      <div className="space-y-3">
                        <PropertyFormWithDropdowns form={editForm} setForm={setEditForm} />
                        <div className="flex justify-end gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={handleCancelEdit}
                          >
                            <X className="h-4 w-4 mr-1" />
                            Cancel
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            onClick={handleSaveEdit}
                          >
                            <Check className="h-4 w-4 mr-1" />
                            Save
                          </Button>
                        </div>
                      </div>
                    ) : (
                      // View Mode
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="font-medium text-sm">
                            {resolved.name_resolved || propMeta?.label || `Property ${prop.property_name}`}
                          </div>
                          <div className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-1 mt-1">
                            <span title="Property Name ID">ID: {prop.property_name}</span>
                            {(prop.subtype !== undefined && prop.subtype !== null && prop.subtype !== 0) && (
                              <span title="Subtype">
                                Subtype: {resolved.subtype_resolved || prop.subtype}
                              </span>
                            )}
                            {(prop.cost_value !== undefined && prop.cost_value !== null && prop.cost_value !== 0) && (
                              <span title="Cost Value">
                                Value: {resolved.cost_value_resolved || prop.cost_value}
                              </span>
                            )}
                            {prop.cost_table !== undefined && prop.cost_table !== null && prop.cost_table !== 0 && (
                              <span title="Cost Table">Table: {prop.cost_table}</span>
                            )}
                            {prop.chance_appear !== undefined && prop.chance_appear !== 100 && (
                              <span title="Chance to Appear">Chance: {prop.chance_appear}%</span>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleStartEdit(index)}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(index)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </ScrollArea>

      <p className="text-xs text-muted-foreground">
        Select property types from the dropdown, then choose subtypes and values as applicable.
        Click "Raw IDs" to enter numeric values directly.
      </p>
    </div>
  );
}
