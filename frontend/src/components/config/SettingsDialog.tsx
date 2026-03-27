import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle, CheckCircle, Loader2, FolderOpen, Settings } from 'lucide-react';
import { PathBrowser } from './PathBrowser';
import { systemApi } from '@/lib/api';

interface ValidationResult {
  valid: boolean;
  message: string;
  found_files?: string[];
}

interface ValidationResults {
  module_path: ValidationResult;
  custom_tlk_path: ValidationResult;
  base_tlk_path: ValidationResult;
  tda_folder_path: ValidationResult;
}

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function SettingsDialog({ open, onClose, onSaved }: SettingsDialogProps) {
  const [modulePath, setModulePath] = useState('');
  const [customTlkPath, setCustomTlkPath] = useState('');
  const [baseTlkPath, setBaseTlkPath] = useState('');
  const [tdaFolderPath, setTdaFolderPath] = useState('');

  const [validation, setValidation] = useState<ValidationResults | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load current config when dialog opens
  useEffect(() => {
    if (open) {
      loadCurrentConfig();
    }
  }, [open]);

  const loadCurrentConfig = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/config');
      if (!response.ok) {
        throw new Error('Failed to load configuration');
      }
      const config = await response.json();
      setModulePath(config.module_path || '');
      setCustomTlkPath(config.custom_tlk_path || '');
      setBaseTlkPath(config.base_tlk_path || '');
      setTdaFolderPath(config.tda_folder_path || '');
      setValidation(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveAndRestart = async () => {
    setIsSaving(true);
    setError(null);
    setValidation(null);

    try {
      // Step 1: Validate
      const validateResponse = await fetch('/api/config/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          module_path: modulePath,
          custom_tlk_path: customTlkPath,
          base_tlk_path: baseTlkPath,
          tda_folder_path: tdaFolderPath,
        }),
      });

      const validateResult = await validateResponse.json();
      setValidation(validateResult.validation);

      const v = validateResult.validation as ValidationResults;
      if (!v.module_path.valid || !v.tda_folder_path.valid || !v.custom_tlk_path.valid) {
        setIsSaving(false);
        setError('Please fix the validation errors above before saving.');
        return;
      }

      // Step 2: Save
      const saveResponse = await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          module_path: modulePath,
          custom_tlk_path: customTlkPath,
          base_tlk_path: baseTlkPath,
          tda_folder_path: tdaFolderPath,
        }),
      });

      if (!saveResponse.ok) {
        const errorData = await saveResponse.json();
        throw new Error(errorData.detail || 'Failed to save configuration');
      }

      // Step 3: Reinitialize instead of reload
      await systemApi.reinitialize();

      setIsSaving(false);
      onSaved();
    } catch (err) {
      setIsSaving(false);
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
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
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Settings
          </DialogTitle>
          <DialogDescription>
            Configure paths to your TDN module files. Changes will reinitialize the application.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="py-8 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {/* Module Path */}
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

            {/* Info Card */}
            <Card className="bg-muted/50">
              <CardContent className="pt-4 text-sm text-muted-foreground">
                <p>
                  <strong>Note:</strong> After saving changes, the application will reinitialize
                  to apply the new configuration.
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
        )}

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveAndRestart}
            disabled={isSaving || isLoading}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save & Restart'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
