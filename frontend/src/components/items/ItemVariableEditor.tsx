import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Variable } from 'lucide-react';
import { ScriptVariable, ScriptVariableInput } from '@/types/item';

interface ItemVariableEditorProps {
  originalVariables: ScriptVariable[];
  variables: ScriptVariableInput[];
  onChange: (variables: ScriptVariableInput[]) => void;
}

const VAR_TYPES = [
  { id: 1, name: 'int', label: 'Integer' },
  { id: 2, name: 'float', label: 'Float' },
  { id: 3, name: 'string', label: 'String' },
];

export function ItemVariableEditor({
  originalVariables,
  variables,
  onChange,
}: ItemVariableEditorProps) {
  const [newVarName, setNewVarName] = useState('');
  const [newVarType, setNewVarType] = useState(1);
  const [newVarValue, setNewVarValue] = useState<string>('');

  const handleAddVariable = () => {
    if (!newVarName.trim()) return;

    // Check for duplicate names
    if (variables.some(v => v.name === newVarName.trim())) {
      return;
    }

    // Parse value based on type
    let parsedValue: number | string;
    if (newVarType === 1) {
      parsedValue = parseInt(newVarValue) || 0;
    } else if (newVarType === 2) {
      parsedValue = parseFloat(newVarValue) || 0.0;
    } else {
      parsedValue = newVarValue;
    }

    onChange([
      ...variables,
      {
        name: newVarName.trim(),
        var_type: newVarType,
        value: parsedValue,
      },
    ]);

    // Reset form
    setNewVarName('');
    setNewVarValue('');
  };

  const handleRemoveVariable = (index: number) => {
    onChange(variables.filter((_, i) => i !== index));
  };

  const handleUpdateVariable = (index: number, field: keyof ScriptVariableInput, value: string | number) => {
    const updated = [...variables];
    const variable = { ...updated[index] };

    if (field === 'var_type') {
      variable.var_type = value as number;
      // Convert value to new type
      if (variable.var_type === 1) {
        variable.value = parseInt(String(variable.value)) || 0;
      } else if (variable.var_type === 2) {
        variable.value = parseFloat(String(variable.value)) || 0.0;
      } else {
        variable.value = String(variable.value);
      }
    } else if (field === 'value') {
      if (variable.var_type === 1) {
        variable.value = parseInt(String(value)) || 0;
      } else if (variable.var_type === 2) {
        variable.value = parseFloat(String(value)) || 0.0;
      } else {
        variable.value = String(value);
      }
    } else if (field === 'name') {
      variable.name = String(value);
    }

    updated[index] = variable;
    onChange(updated);
  };

  const getTypeName = (typeId: number): string => {
    return VAR_TYPES.find(t => t.id === typeId)?.name || 'unknown';
  };

  const getTypeBadgeColor = (typeId: number): string => {
    switch (typeId) {
      case 1: return 'bg-blue-100 text-blue-800';
      case 2: return 'bg-green-100 text-green-800';
      case 3: return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const isModified = (variable: ScriptVariableInput): boolean => {
    const original = originalVariables.find(v => v.name === variable.name);
    if (!original) return true; // New variable
    return original.var_type !== variable.var_type || original.value !== variable.value;
  };

  const isRemoved = (originalVar: ScriptVariable): boolean => {
    return !variables.some(v => v.name === originalVar.name);
  };

  // Count changes
  const addedCount = variables.filter(v => !originalVariables.some(ov => ov.name === v.name)).length;
  const removedCount = originalVariables.filter(ov => isRemoved(ov)).length;
  const modifiedCount = variables.filter(v => {
    const original = originalVariables.find(ov => ov.name === v.name);
    return original && (original.var_type !== v.var_type || original.value !== v.value);
  }).length;

  return (
    <div className="space-y-4">
      {/* Summary of changes */}
      {(addedCount > 0 || removedCount > 0 || modifiedCount > 0) && (
        <div className="flex gap-2 text-sm">
          {addedCount > 0 && (
            <Badge variant="outline" className="bg-green-50 text-green-700">
              +{addedCount} added
            </Badge>
          )}
          {modifiedCount > 0 && (
            <Badge variant="outline" className="bg-amber-50 text-amber-700">
              {modifiedCount} modified
            </Badge>
          )}
          {removedCount > 0 && (
            <Badge variant="outline" className="bg-red-50 text-red-700">
              -{removedCount} removed
            </Badge>
          )}
        </div>
      )}

      {/* Add new variable form */}
      <Card>
        <CardContent className="pt-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Variable className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Add Variable</span>
            </div>

            <div className="grid grid-cols-12 gap-2">
              <div className="col-span-4">
                <Input
                  placeholder="Variable name"
                  value={newVarName}
                  onChange={(e) => setNewVarName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddVariable();
                    }
                  }}
                />
              </div>
              <div className="col-span-2">
                <select
                  className="w-full h-10 px-3 py-2 text-sm rounded-md border border-input bg-background"
                  value={newVarType}
                  onChange={(e) => setNewVarType(parseInt(e.target.value))}
                >
                  {VAR_TYPES.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-4">
                <Input
                  placeholder={newVarType === 3 ? 'String value' : 'Numeric value'}
                  type={newVarType === 3 ? 'text' : 'number'}
                  step={newVarType === 2 ? '0.01' : '1'}
                  value={newVarValue}
                  onChange={(e) => setNewVarValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddVariable();
                    }
                  }}
                />
              </div>
              <div className="col-span-2">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleAddVariable}
                  disabled={!newVarName.trim() || variables.some(v => v.name === newVarName.trim())}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
            {newVarName.trim() && variables.some(v => v.name === newVarName.trim()) && (
              <p className="text-sm text-red-500">A variable with this name already exists</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Existing variables */}
      {variables.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <Variable className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>No script variables defined</p>
          <p className="text-sm">Add variables to store custom data on this item</p>
        </div>
      ) : (
        <div className="space-y-2">
          <Label className="text-sm text-muted-foreground">
            Variables ({variables.length})
          </Label>
          {variables.map((variable, index) => (
            <Card
              key={index}
              className={isModified(variable) ? 'border-amber-300 bg-amber-50/30' : ''}
            >
              <CardContent className="py-3">
                <div className="grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-4">
                    <Input
                      value={variable.name}
                      onChange={(e) => handleUpdateVariable(index, 'name', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="col-span-2">
                    <select
                      className="w-full h-10 px-3 py-2 text-sm rounded-md border border-input bg-background"
                      value={variable.var_type}
                      onChange={(e) => handleUpdateVariable(index, 'var_type', parseInt(e.target.value))}
                    >
                      {VAR_TYPES.map((type) => (
                        <option key={type.id} value={type.id}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-4">
                    <Input
                      type={variable.var_type === 3 ? 'text' : 'number'}
                      step={variable.var_type === 2 ? '0.01' : '1'}
                      value={variable.value}
                      onChange={(e) => handleUpdateVariable(index, 'value', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="col-span-2 flex justify-end gap-1">
                    <Badge className={`text-xs ${getTypeBadgeColor(variable.var_type)}`}>
                      {getTypeName(variable.var_type)}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                      onClick={() => handleRemoveVariable(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
