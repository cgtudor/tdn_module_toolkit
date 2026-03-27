import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle, CheckCircle, Loader2, FolderOpen, Settings } from 'lucide-react';
import { PathBrowser } from './PathBrowser';

interface ValidationResult {
  valid: boolean;
  message: string;
  found_files?: string[];
}

interface ValidationResults {
  module_path: ValidationResult;
  mod_file_path: ValidationResult;
  custom_tlk_path: ValidationResult;
  base_tlk_path: ValidationResult;
  tda_folder_path: ValidationResult;
}

interface ConfigDialogProps {
  open: boolean;
  onConfigured: () => void;
  onCancel?: () => void;
  isReconfigure?: boolean;
}

export function ConfigDialog({ open, onConfigured, onCancel, isReconfigure }: ConfigDialogProps) {
  const [sourceMode, setSourceMode] = useState<'json_directory' | 'mod_file'>('json_directory');
  const [modulePath, setModulePath] = useState('');
  const [modFilePath, setModFilePath] = useState('');
  const [customTlkPath, setCustomTlkPath] = useState('');
  const [baseTlkPath, setBaseTlkPath] = useState('');
  const [tdaFolderPath, setTdaFolderPath] = useState('');
  const [hakSourcePath, setHakSourcePath] = useState('');
  const [nwnRootPath, setNwnRootPath] = useState('');

  const [validation, setValidation] = useState<ValidationResults | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load defaults or current config on mount
  useEffect(() => {
    if (open) {
      loadConfig();
    }
  }, [open]);

  const loadConfig = async () => {
    try {
      const endpoint = isReconfigure ? '/api/config' : '/api/config/defaults';
      const response = await fetch(endpoint);
      const config = await response.json();
      setSourceMode(config.source_mode || 'json_directory');
      setModulePath(config.module_path || '');
      setModFilePath(config.mod_file_path || '');
      setCustomTlkPath(config.custom_tlk_path || '');
      setBaseTlkPath(config.base_tlk_path || '');
      setTdaFolderPath(config.tda_folder_path || '');
      setHakSourcePath(config.hak_source_path || '');
      setNwnRootPath(config.nwn_root_path || '');
    } catch (err) {
      console.error('Failed to load config:', err);
    }
  };

  const handleSaveAndContinue = async () => {
    setIsSaving(true);
    setError(null);
    setValidation(null);

    try {
      // Step 1: Validate
      const validateResponse = await fetch('/api/config/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_mode: sourceMode,
          module_path: modulePath,
          mod_file_path: modFilePath,
          custom_tlk_path: customTlkPath,
          base_tlk_path: baseTlkPath,
          tda_folder_path: tdaFolderPath,
          hak_source_path: hakSourcePath,
          nwn_root_path: nwnRootPath,
        }),
      });

      const validateResult = await validateResponse.json();
      setValidation(validateResult.validation);

      const v = validateResult.validation as ValidationResults;
      const sourcePathValid = sourceMode === 'mod_file' ? v.mod_file_path.valid : v.module_path.valid;
      if (!sourcePathValid || !v.tda_folder_path.valid || !v.custom_tlk_path.valid) {
        setIsSaving(false);
        setError('Please fix the validation errors above before saving.');
        return;
      }

      // Step 2: Save
      const saveResponse = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_mode: sourceMode,
          module_path: modulePath,
          mod_file_path: modFilePath,
          custom_tlk_path: customTlkPath,
          base_tlk_path: baseTlkPath,
          tda_folder_path: tdaFolderPath,
          hak_source_path: hakSourcePath,
          nwn_root_path: nwnRootPath,
        }),
      });

      if (!saveResponse.ok) {
        const errorData = await saveResponse.json();
        throw new Error(errorData.detail || 'Failed to save configuration');
      }

      setIsSaving(false);
      onConfigured();
    } catch (err) {
      setIsSaving(false);
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    }
  };

  const ValidationIcon = ({ result }: { result: ValidationResult | undefined }) => {
    if (!result) return null;
    return result.valid ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <AlertCircle className="h-4 w-4 text-red-500" />
    );
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleCancel(); }}>
      <DialogContent className="max-w-2xl" onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Initial Configuration
          </DialogTitle>
          <DialogDescription>
            Configure paths to your TDN module files. These settings are required for the tool to work properly.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Source Mode Selector */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Source Mode</Label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="source-mode"
                  value="json_directory"
                  checked={sourceMode === 'json_directory'}
                  onChange={() => { setSourceMode('json_directory'); setValidation(null); }}
                  className="accent-primary"
                />
                <span className="text-sm">JSON Directory</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="source-mode"
                  value="mod_file"
                  checked={sourceMode === 'mod_file'}
                  onChange={() => { setSourceMode('mod_file'); setValidation(null); }}
                  className="accent-primary"
                />
                <span className="text-sm">MOD File</span>
              </label>
            </div>
          </div>

          {/* Module Path (JSON Directory mode) */}
          {sourceMode === 'json_directory' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="module-path" className="flex items-center gap-2">
                  <FolderOpen className="h-4 w-4" />
                  Module Path *
                </Label>
                {validation && <ValidationIcon result={validation.module_path} />}
              </div>
              <PathBrowser
                id="module-path"
                value={modulePath}
                onChange={setModulePath}
                placeholder="D:\tdn\workspace\tdn_gff\module"
                mode="folder"
              />
              {validation?.module_path && (
                <p className={`text-xs ${validation.module_path.valid ? 'text-green-600' : 'text-red-600'}`}>
                  {validation.module_path.message}
                </p>
              )}
            </div>
          )}

          {/* MOD File Path (MOD File mode) */}
          {sourceMode === 'mod_file' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="mod-file-path" className="flex items-center gap-2">
                  <FolderOpen className="h-4 w-4" />
                  MOD File Path *
                </Label>
                {validation && <ValidationIcon result={validation.mod_file_path} />}
              </div>
              <PathBrowser
                id="mod-file-path"
                value={modFilePath}
                onChange={setModFilePath}
                placeholder="D:\tdn\workspace\tdn_gff\tdn_build.mod"
                mode="file"
                fileFilter={['.mod']}
              />
              {validation?.mod_file_path && (
                <p className={`text-xs ${validation.mod_file_path.valid ? 'text-green-600' : 'text-red-600'}`}>
                  {validation.mod_file_path.message}
                </p>
              )}
            </div>
          )}

          {/* 2DA Folder Path */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="tda-folder-path" className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4" />
                2DA Folder *
              </Label>
              {validation && <ValidationIcon result={validation.tda_folder_path} />}
            </div>
            <PathBrowser
              id="tda-folder-path"
              value={tdaFolderPath}
              onChange={setTdaFolderPath}
              placeholder="D:\tdn\workspace\TDN_Haks\tdn_2da"
              mode="folder"
            />
            {validation?.tda_folder_path && (
              <p className={`text-xs ${validation.tda_folder_path.valid ? 'text-green-600' : 'text-red-600'}`}>
                {validation.tda_folder_path.message}
                {validation.tda_folder_path.found_files && validation.tda_folder_path.found_files.length > 0 && (
                  <span className="block mt-1">
                    Found: {validation.tda_folder_path.found_files.join(', ')}
                  </span>
                )}
              </p>
            )}
          </div>

          {/* Custom TLK Path */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="custom-tlk-path" className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4" />
                Custom TLK (dragonsneck.tlk.json)
              </Label>
              {validation && <ValidationIcon result={validation.custom_tlk_path} />}
            </div>
            <PathBrowser
              id="custom-tlk-path"
              value={customTlkPath}
              onChange={setCustomTlkPath}
              placeholder="D:\tdn\workspace\TDN_Haks\tlk\dragonsneck.tlk.json"
              mode="file"
              fileFilter={['.tlk', '.json']}
            />
            {validation?.custom_tlk_path && (
              <p className={`text-xs ${validation.custom_tlk_path.valid ? 'text-green-600' : 'text-red-600'}`}>
                {validation.custom_tlk_path.message}
              </p>
            )}
          </div>

          {/* Base TLK Path */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="base-tlk-path" className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4" />
                Base TLK (dialog.tlk.json)
              </Label>
              {validation && <ValidationIcon result={validation.base_tlk_path} />}
            </div>
            <PathBrowser
              id="base-tlk-path"
              value={baseTlkPath}
              onChange={setBaseTlkPath}
              placeholder="D:\tdn\workspace\TDN_Haks\tlk\dialog.tlk.json"
              mode="file"
              fileFilter={['.tlk', '.json']}
            />
            {validation?.base_tlk_path && (
              <p className={`text-xs ${validation.base_tlk_path.valid ? 'text-green-600' : 'text-red-600'}`}>
                {validation.base_tlk_path.message}
              </p>
            )}
          </div>

          {/* Hak Source Path */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="hak-source-path" className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4" />
                Hak Source Path (TDN_Haks)
              </Label>
            </div>
            <PathBrowser
              id="hak-source-path"
              value={hakSourcePath}
              onChange={setHakSourcePath}
              placeholder="D:\tdn\workspace\TDN_Haks"
              mode="folder"
            />
            <p className="text-xs text-muted-foreground">
              Path to TDN_Haks directory containing custom item icons and textures.
            </p>
          </div>

          {/* NWN Root Path */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="nwn-root-path" className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4" />
                NWN:EE Install Path
              </Label>
            </div>
            <PathBrowser
              id="nwn-root-path"
              value={nwnRootPath}
              onChange={setNwnRootPath}
              placeholder="C:\Games\Steam\steamapps\common\Neverwinter Nights"
              mode="folder"
            />
            <p className="text-xs text-muted-foreground">
              Path to NWN:EE installation for base game icons (KEY/BIF files).
            </p>
          </div>

          {/* Info Card */}
          <Card className="bg-muted/50">
            <CardContent className="pt-4 text-sm text-muted-foreground">
              <p>
                <strong>2DA Folder</strong> should contain baseitems.2da, itemprops.2da, racialtypes.2da, and appearance.2da files.
                These are used for item categorization and creature appearance data.
              </p>
              <p className="mt-2">
                <strong>TLK files</strong> are used to resolve item names and descriptions.
                The custom TLK contains TDN-specific strings, while the base TLK contains standard NWN strings.
              </p>
            </CardContent>
          </Card>

          {/* Error Display */}
          {error && (
            <div className="p-3 rounded bg-red-100 text-red-800 text-sm flex items-center gap-2 dark:bg-red-900/30 dark:text-red-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>

        <DialogFooter className="flex gap-2">
          {onCancel && (
            <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
              Cancel
            </Button>
          )}
          <Button
            onClick={handleSaveAndContinue}
            disabled={isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save & Continue'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
