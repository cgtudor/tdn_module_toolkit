import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Package, AlertTriangle, Loader2 } from 'lucide-react';
import { ItemDetail, ItemTemplateUpdate, ItemPropertyInput, ScriptVariableInput, PaletteCategory } from '@/types/item';
import { ItemPropertyEditor } from './ItemPropertyEditor';
import { ItemVariableEditor } from './ItemVariableEditor';
import { usePaletteCategories } from '@/hooks/useItems';

interface ItemEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: ItemDetail;
  onSave: (data: ItemTemplateUpdate) => Promise<void>;
  isSaving?: boolean;
}

export function ItemEditDialog({
  open,
  onOpenChange,
  item,
  onSave,
  isSaving = false,
}: ItemEditDialogProps) {
  // Basic fields
  const [name, setName] = useState('');
  const [tag, setTag] = useState('');
  const [cost, setCost] = useState(0);
  const [additionalCost, setAdditionalCost] = useState(0);
  const [stackSize, setStackSize] = useState(1);
  const [charges, setCharges] = useState(0);

  // Flags
  const [identified, setIdentified] = useState(true);
  const [plot, setPlot] = useState(false);
  const [cursed, setCursed] = useState(false);
  const [stolen, setStolen] = useState(false);

  // Description
  const [description, setDescription] = useState('');
  const [descIdentified, setDescIdentified] = useState('');

  // Properties
  const [properties, setProperties] = useState<ItemPropertyInput[]>([]);

  // Variables
  const [variables, setVariables] = useState<ScriptVariableInput[]>([]);

  // Advanced
  const [newResref, setNewResref] = useState('');
  const [paletteCategory, setPaletteCategory] = useState<number | undefined>(undefined);

  // Validation
  const [resrefError, setResrefError] = useState<string | null>(null);

  // Load palette categories
  const { data: paletteCategoriesData } = usePaletteCategories();
  const paletteCategories = paletteCategoriesData?.categories || [];
  const paletteAvailable = paletteCategoriesData?.available || false;

  // Initialize form when dialog opens
  useEffect(() => {
    if (open && item) {
      setName(item.name || '');
      setTag(item.tag || '');
      setCost(item.cost || 0);
      setAdditionalCost(item.additional_cost || 0);
      setStackSize(item.stack_size || 1);
      setCharges(item.charges || 0);

      setIdentified(item.identified);
      setPlot(item.plot);
      setCursed(item.cursed);
      setStolen(item.stolen);

      setDescription(item.description || '');
      // Extract DescIdentified from raw_data if available
      const descIdent = extractDescIdentified(item.raw_data);
      setDescIdentified(descIdent);

      // Convert properties to input format
      setProperties(item.properties.map(p => ({
        property_name: p.property_name,
        subtype: p.subtype ?? 0,
        cost_table: p.cost_table ?? 0,
        cost_value: p.cost_value ?? 0,
        param1: p.param1 ?? 255,
        param1_value: p.param1_value ?? 0,
        chance_appear: p.chance_appear ?? 100,
      })));

      // Convert variables to input format
      setVariables((item.variables || []).map(v => ({
        name: v.name,
        var_type: v.var_type,
        value: v.value,
      })));

      setNewResref(item.resref);
      setPaletteCategory(item.palette_id ?? undefined);
      setResrefError(null);
    }
  }, [open, item]);

  // Extract DescIdentified from raw GFF data
  const extractDescIdentified = (rawData?: Record<string, unknown>): string => {
    if (!rawData || !rawData.DescIdentified) return '';
    const descIdent = rawData.DescIdentified as { value?: { '0'?: string } };
    if (descIdent.value && typeof descIdent.value === 'object' && '0' in descIdent.value) {
      return descIdent.value['0'] || '';
    }
    return '';
  };

  // Validate resref
  const validateResref = (value: string): string | null => {
    if (!value) return 'Resref is required';
    if (value.length > 16) return 'Resref cannot exceed 16 characters';
    if (!/^[a-zA-Z0-9_]+$/.test(value)) return 'Resref can only contain letters, numbers, and underscores';
    return null;
  };

  const handleResrefChange = (value: string) => {
    setNewResref(value.toLowerCase());
    setResrefError(validateResref(value.toLowerCase()));
  };

  const handleSave = async () => {
    // Validate resref
    const resrefValidation = validateResref(newResref);
    if (resrefValidation) {
      setResrefError(resrefValidation);
      return;
    }

    // Build update object - only include changed fields
    const update: ItemTemplateUpdate = {};

    // Basic fields
    if (name !== item.name) {
      update.name = { text: name };
    }
    if (tag !== item.tag) {
      update.tag = tag;
    }
    if (cost !== item.cost) {
      update.cost = cost;
    }
    if (additionalCost !== item.additional_cost) {
      update.additional_cost = additionalCost;
    }
    if (stackSize !== item.stack_size) {
      update.stack_size = stackSize;
    }
    if (charges !== item.charges) {
      update.charges = charges;
    }

    // Flags
    if (identified !== item.identified) {
      update.identified = identified;
    }
    if (plot !== item.plot) {
      update.plot = plot;
    }
    if (cursed !== item.cursed) {
      update.cursed = cursed;
    }
    if (stolen !== item.stolen) {
      update.stolen = stolen;
    }

    // Description
    if (description !== (item.description || '')) {
      update.description = { text: description };
    }
    const originalDescIdent = extractDescIdentified(item.raw_data);
    if (descIdentified !== originalDescIdent) {
      update.desc_identified = { text: descIdentified };
    }

    // Properties - always send full list if any property changed
    const propsChanged = JSON.stringify(properties) !== JSON.stringify(
      item.properties.map(p => ({
        property_name: p.property_name,
        subtype: p.subtype ?? 0,
        cost_table: p.cost_table ?? 0,
        cost_value: p.cost_value ?? 0,
        param1: p.param1 ?? 255,
        param1_value: p.param1_value ?? 0,
        chance_appear: p.chance_appear ?? 100,
      }))
    );
    if (propsChanged) {
      update.properties = properties;
    }

    // Variables - always send full list if any variable changed
    const varsChanged = JSON.stringify(variables) !== JSON.stringify(
      (item.variables || []).map(v => ({
        name: v.name,
        var_type: v.var_type,
        value: v.value,
      }))
    );
    if (varsChanged) {
      update.variables = variables;
    }

    // Advanced
    if (newResref !== item.resref) {
      update.new_resref = newResref;
    }
    if (paletteCategory !== item.palette_id && paletteCategory !== undefined) {
      update.palette_category = paletteCategory;
    }

    await onSave(update);
  };

  const hasChanges = (): boolean => {
    if (name !== item.name) return true;
    if (tag !== item.tag) return true;
    if (cost !== item.cost) return true;
    if (additionalCost !== item.additional_cost) return true;
    if (stackSize !== item.stack_size) return true;
    if (charges !== item.charges) return true;
    if (identified !== item.identified) return true;
    if (plot !== item.plot) return true;
    if (cursed !== item.cursed) return true;
    if (stolen !== item.stolen) return true;
    if (description !== (item.description || '')) return true;
    if (descIdentified !== extractDescIdentified(item.raw_data)) return true;
    if (newResref !== item.resref) return true;
    if (paletteCategory !== item.palette_id && paletteCategory !== undefined) return true;
    // Check properties
    const propsChanged = JSON.stringify(properties) !== JSON.stringify(
      item.properties.map(p => ({
        property_name: p.property_name,
        subtype: p.subtype ?? 0,
        cost_table: p.cost_table ?? 0,
        cost_value: p.cost_value ?? 0,
        param1: p.param1 ?? 255,
        param1_value: p.param1_value ?? 0,
        chance_appear: p.chance_appear ?? 100,
      }))
    );
    if (propsChanged) return true;
    // Check variables
    const varsChanged = JSON.stringify(variables) !== JSON.stringify(
      (item.variables || []).map(v => ({
        name: v.name,
        var_type: v.var_type,
        value: v.value,
      }))
    );
    if (varsChanged) return true;
    return false;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            Edit Item Template
          </DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            <Badge variant="outline">{item.resref}</Badge>
            <span>Editing item template properties</span>
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="basic" className="w-full">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="basic">Basic</TabsTrigger>
            <TabsTrigger value="flags">Flags</TabsTrigger>
            <TabsTrigger value="description">Desc</TabsTrigger>
            <TabsTrigger value="properties">Properties</TabsTrigger>
            <TabsTrigger value="variables">Variables</TabsTrigger>
            <TabsTrigger value="advanced">Advanced</TabsTrigger>
          </TabsList>

          <ScrollArea className="h-[400px] mt-4">
            {/* Basic Tab */}
            <TabsContent value="basic" className="space-y-4 pr-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Item name"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="tag">Tag</Label>
                <Input
                  id="tag"
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                  placeholder="Item tag"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cost">Base Cost (gp)</Label>
                  <Input
                    id="cost"
                    type="number"
                    min={0}
                    value={cost}
                    onChange={(e) => setCost(parseInt(e.target.value) || 0)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="additional-cost">Additional Cost (gp)</Label>
                  <Input
                    id="additional-cost"
                    type="number"
                    min={0}
                    value={additionalCost}
                    onChange={(e) => setAdditionalCost(parseInt(e.target.value) || 0)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="stack-size">Stack Size</Label>
                  <Input
                    id="stack-size"
                    type="number"
                    min={1}
                    value={stackSize}
                    onChange={(e) => setStackSize(parseInt(e.target.value) || 1)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="charges">Charges</Label>
                  <Input
                    id="charges"
                    type="number"
                    min={0}
                    value={charges}
                    onChange={(e) => setCharges(parseInt(e.target.value) || 0)}
                  />
                </div>
              </div>
            </TabsContent>

            {/* Flags Tab */}
            <TabsContent value="flags" className="space-y-4 pr-4">
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="identified"
                    checked={identified}
                    onCheckedChange={(checked) => setIdentified(checked === true)}
                  />
                  <Label htmlFor="identified" className="cursor-pointer">
                    Identified
                    <span className="text-muted-foreground ml-2 text-sm">
                      Item properties are visible to players
                    </span>
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="plot"
                    checked={plot}
                    onCheckedChange={(checked) => setPlot(checked === true)}
                  />
                  <Label htmlFor="plot" className="cursor-pointer">
                    Plot Item
                    <span className="text-muted-foreground ml-2 text-sm">
                      Cannot be dropped or sold
                    </span>
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="cursed"
                    checked={cursed}
                    onCheckedChange={(checked) => setCursed(checked === true)}
                  />
                  <Label htmlFor="cursed" className="cursor-pointer">
                    Cursed
                    <span className="text-muted-foreground ml-2 text-sm">
                      Cannot be unequipped normally
                    </span>
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="stolen"
                    checked={stolen}
                    onCheckedChange={(checked) => setStolen(checked === true)}
                  />
                  <Label htmlFor="stolen" className="cursor-pointer">
                    Stolen
                    <span className="text-muted-foreground ml-2 text-sm">
                      Marked as stolen property
                    </span>
                  </Label>
                </div>
              </div>
            </TabsContent>

            {/* Description Tab */}
            <TabsContent value="description" className="space-y-4 pr-4">
              <div className="space-y-2">
                <Label htmlFor="description">Description (Unidentified)</Label>
                <textarea
                  id="description"
                  className="w-full h-32 px-3 py-2 text-sm rounded-md border border-input bg-background resize-none"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Description shown when item is not identified..."
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="desc-identified">Description (Identified)</Label>
                <textarea
                  id="desc-identified"
                  className="w-full h-32 px-3 py-2 text-sm rounded-md border border-input bg-background resize-none"
                  value={descIdentified}
                  onChange={(e) => setDescIdentified(e.target.value)}
                  placeholder="Description shown when item is identified..."
                />
              </div>
            </TabsContent>

            {/* Properties Tab */}
            <TabsContent value="properties" className="pr-4">
              <ItemPropertyEditor
                originalProperties={item.properties}
                properties={properties}
                onChange={setProperties}
              />
            </TabsContent>

            {/* Variables Tab */}
            <TabsContent value="variables" className="pr-4">
              <ItemVariableEditor
                originalVariables={item.variables || []}
                variables={variables}
                onChange={setVariables}
              />
            </TabsContent>

            {/* Advanced Tab */}
            <TabsContent value="advanced" className="space-y-4 pr-4">
              <Card className="border-amber-500/50 bg-amber-50/50">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-2 text-amber-800">
                    <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <p className="font-medium">Caution: Advanced Settings</p>
                      <p className="mt-1">
                        Changing the resref will rename the item file. This may break references
                        in scripts, creatures, and stores that use the old resref.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="space-y-2">
                <Label htmlFor="resref">
                  Resref (File Name)
                  <span className="text-muted-foreground ml-2 text-sm">Max 16 characters</span>
                </Label>
                <Input
                  id="resref"
                  value={newResref}
                  onChange={(e) => handleResrefChange(e.target.value)}
                  placeholder="item_resref"
                  maxLength={16}
                  className={resrefError ? 'border-red-500' : ''}
                />
                {resrefError && (
                  <p className="text-sm text-red-500">{resrefError}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  Current: {item.resref}
                  {newResref !== item.resref && (
                    <span className="text-amber-600 ml-2">
                      Will be renamed to: {newResref}
                    </span>
                  )}
                </p>
              </div>

              {paletteAvailable && paletteCategories.length > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="palette-category">Palette Category</Label>
                  <select
                    id="palette-category"
                    className="w-full h-10 px-3 py-2 text-sm rounded-md border border-input bg-background"
                    value={paletteCategory ?? ''}
                    onChange={(e) => setPaletteCategory(e.target.value ? parseInt(e.target.value) : undefined)}
                  >
                    <option value="">-- No Change --</option>
                    {paletteCategories.map((cat: PaletteCategory) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name} (ID: {cat.id})
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Move this item to a different category in the toolset palette.
                  </p>
                </div>
              )}
            </TabsContent>
          </ScrollArea>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || !hasChanges() || !!resrefError}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
