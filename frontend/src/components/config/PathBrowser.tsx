import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { FolderOpen, Folder, File, HardDrive, ArrowUp, Loader2 } from 'lucide-react';
import { isElectron, showFolderDialog, showFileDialog } from '@/lib/electron';

interface BrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
  is_file: boolean;
}

interface BrowseResult {
  current_path: string;
  parent_path: string | null;
  entries: BrowseEntry[];
  drives: string[];
}

interface PathBrowserProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  mode: 'folder' | 'file';
  fileFilter?: string[];  // e.g., ['.tlk', '.json']
  id?: string;
}

export function PathBrowser({ value, onChange, placeholder, mode, fileFilter, id }: PathBrowserProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [browseData, setBrowseData] = useState<BrowseResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const browse = async (path?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/config/browse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path || value || null }),
      });
      if (!response.ok) {
        throw new Error('Failed to browse directory');
      }
      const data = await response.json();
      setBrowseData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to browse');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenBrowser = async () => {
    // Use native Electron dialogs if available
    if (isElectron()) {
      try {
        if (mode === 'folder') {
          const result = await showFolderDialog({
            title: 'Select Folder',
            defaultPath: value || undefined
          });
          if (result) {
            onChange(result);
            return;
          }
        } else {
          // File mode
          const filters = fileFilter?.map(ext => ({
            name: ext.replace('.', '').toUpperCase() + ' Files',
            extensions: [ext.replace('.', '')]
          }));
          const result = await showFileDialog({
            title: 'Select File',
            defaultPath: value || undefined,
            filters
          });
          if (result?.[0]) {
            onChange(result[0]);
            return;
          }
        }
        // User cancelled - don't open browser fallback
        return;
      } catch (err) {
        console.error('Native dialog error:', err);
        // Fall through to browser-based dialog
      }
    }

    // Browser-based fallback
    setIsOpen(true);
    browse();
  };

  const handleNavigate = (path: string) => {
    browse(path);
  };

  const handleSelect = (entry: BrowseEntry) => {
    if (entry.is_dir) {
      if (mode === 'folder') {
        // In folder mode, clicking a folder navigates into it
        browse(entry.path);
      } else {
        // In file mode, navigate into folders
        browse(entry.path);
      }
    } else if (entry.is_file && mode === 'file') {
      // In file mode, clicking a file selects it
      if (fileFilter && fileFilter.length > 0) {
        const matches = fileFilter.some(ext => entry.name.toLowerCase().endsWith(ext.toLowerCase()));
        if (!matches) return;
      }
      onChange(entry.path);
      setIsOpen(false);
    }
  };

  const handleSelectCurrentFolder = () => {
    if (browseData && mode === 'folder') {
      onChange(browseData.current_path);
      setIsOpen(false);
    }
  };

  const filteredEntries = browseData?.entries.filter(entry => {
    if (mode === 'folder') {
      return entry.is_dir;
    }
    if (entry.is_dir) return true;
    if (!fileFilter || fileFilter.length === 0) return true;
    return fileFilter.some(ext => entry.name.toLowerCase().endsWith(ext.toLowerCase()));
  }) || [];

  return (
    <>
      <div className="flex gap-2">
        <Input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1"
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={handleOpenBrowser}
          title={mode === 'folder' ? 'Browse for folder' : 'Browse for file'}
        >
          <FolderOpen className="h-4 w-4" />
        </Button>
      </div>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>
              {mode === 'folder' ? 'Select Folder' : 'Select File'}
            </DialogTitle>
          </DialogHeader>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-red-500 py-4">{error}</div>
          ) : browseData ? (
            <div className="space-y-4">
              {/* Current path display */}
              <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted p-2 rounded">
                <Folder className="h-4 w-4" />
                <span className="truncate flex-1">{browseData.current_path}</span>
              </div>

              {/* Drive selector (Windows) */}
              {browseData.drives && browseData.drives.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {browseData.drives.map(drive => (
                    <Button
                      key={drive}
                      variant="outline"
                      size="sm"
                      onClick={() => handleNavigate(drive)}
                      className="h-7 px-2"
                    >
                      <HardDrive className="h-3 w-3 mr-1" />
                      {drive}
                    </Button>
                  ))}
                </div>
              )}

              {/* Navigation buttons */}
              <div className="flex gap-2">
                {browseData.parent_path && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleNavigate(browseData.parent_path!)}
                  >
                    <ArrowUp className="h-4 w-4 mr-1" />
                    Up
                  </Button>
                )}
                {mode === 'folder' && (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={handleSelectCurrentFolder}
                    className="ml-auto"
                  >
                    Select This Folder
                  </Button>
                )}
              </div>

              {/* File/folder list */}
              <ScrollArea className="h-[300px] border rounded">
                <div className="p-2 space-y-1">
                  {filteredEntries.length === 0 ? (
                    <div className="text-center text-muted-foreground py-4">
                      {mode === 'folder' ? 'No subfolders' : 'No matching files'}
                    </div>
                  ) : (
                    filteredEntries.map(entry => (
                      <button
                        key={entry.path}
                        onClick={() => handleSelect(entry)}
                        onDoubleClick={() => {
                          if (entry.is_dir && mode === 'folder') {
                            onChange(entry.path);
                            setIsOpen(false);
                          }
                        }}
                        className={`w-full flex items-center gap-2 p-2 rounded text-left hover:bg-accent transition-colors ${
                          entry.is_dir ? 'text-foreground' : 'text-muted-foreground'
                        }`}
                      >
                        {entry.is_dir ? (
                          <Folder className="h-4 w-4 text-yellow-500" />
                        ) : (
                          <File className="h-4 w-4" />
                        )}
                        <span className="truncate">{entry.name}</span>
                      </button>
                    ))
                  )}
                </div>
              </ScrollArea>

              {/* Help text */}
              <p className="text-xs text-muted-foreground">
                {mode === 'folder'
                  ? 'Click a folder to navigate into it. Double-click or use "Select This Folder" to select.'
                  : 'Click a file to select it, or click a folder to navigate into it.'}
              </p>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
