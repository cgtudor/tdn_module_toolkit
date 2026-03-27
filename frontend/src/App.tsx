import { useEffect, useState } from 'react'
import { MainLayout } from './components/layout/MainLayout'
import { ConfigDialog } from './components/config/ConfigDialog'
import { SettingsDialog } from './components/config/SettingsDialog'
import { LoadingScreen } from './components/shared/LoadingScreen'
import { useSystemStatus } from './hooks/useInstances'
import { useAppStore } from './store/appStore'
import { systemApi } from './lib/api'

function App() {
  const { data: status, isLoading, isError, refetch: refetchStatus } = useSystemStatus()
  const setSystemStatus = useAppStore((state) => state.setSystemStatus)
  const darkMode = useAppStore((state) => state.darkMode)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [showSettingsDialog, setShowSettingsDialog] = useState(false)
  const [configCancelled, setConfigCancelled] = useState(false)
  const [isReconfigure, setIsReconfigure] = useState(false)
  // Track that we just configured successfully - prevents dialog reopening during transition
  const [justConfigured, setJustConfigured] = useState(false)

  // Apply dark mode class to document
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  useEffect(() => {
    if (status) {
      setSystemStatus({
        connected: status.state === 'ready',
        mode: status.mode || 'json_directory',
        dirtyCount: status.dirty_count || 0,
        counts: status.counts,
      })

      // Reset justConfigured flag once we're ready - allows future reconfigs to work
      if (status.state === 'ready' && justConfigured) {
        setJustConfigured(false)
      }

      // Show config dialog if not configured (but not if we just completed configuration)
      if (status.state === 'needs_configuration' && !configCancelled && !justConfigured) {
        setShowConfigDialog(true)
      }
    }
  }, [status, setSystemStatus, configCancelled, justConfigured])

  const handleConfigured = async () => {
    setShowConfigDialog(false)
    setConfigCancelled(false)
    setIsReconfigure(false)
    setJustConfigured(true)  // Prevent dialog from reopening during transition

    try {
      // Trigger reinitialize to load new config
      await systemApi.reinitialize()
    } catch (err) {
      console.error('Reinitialize failed:', err);
    }

    // Refetch status to start polling the new state
    refetchStatus()
  }

  const handleConfigCancel = () => {
    setShowConfigDialog(false)
    setConfigCancelled(true)
  }

  const handleOpenSettings = () => {
    setShowSettingsDialog(true)
  }

  const handleSettingsSaved = () => {
    setShowSettingsDialog(false)
    setJustConfigured(true)  // Prevent config dialog from reopening during reinitialization
    // Status polling will pick up the reinitializing/indexing state automatically
    refetchStatus()
  }

  const handleReconfigure = () => {
    setConfigCancelled(false)
    setJustConfigured(false)  // Allow dialog to show again
    setIsReconfigure(true)
    setShowConfigDialog(true)
  }

  // Show loading screen while connecting to backend
  if (isLoading) {
    return <LoadingScreen message="Connecting to backend..." subMessage="Please wait while we establish connection" />
  }

  if (isError) {
    return (
      <LoadingScreen
        message="Unable to connect to backend"
        subMessage="Make sure the backend server is running on port 8000"
      />
    )
  }

  // Handle backend states
  const backendState = status?.state

  if (backendState === 'error') {
    return (
      <LoadingScreen
        message="An error occurred"
        subMessage={status?.error_message || 'The backend encountered an error during initialization.'}
        action={{
          label: 'Re-configure',
          onClick: handleReconfigure,
        }}
      />
    )
  }

  if (backendState === 'initializing') {
    return (
      <LoadingScreen
        message="Initializing..."
        subMessage="Setting up services and loading configuration"
      />
    )
  }

  if (backendState === 'indexing' || status?.indexing) {
    return (
      <LoadingScreen
        message="Indexing module files..."
        subMessage={status?.indexing_message || 'This may take a moment for large modules'}
        detail="Scanning templates, items, creatures, and areas"
      />
    )
  }

  if (backendState === 'needs_configuration') {
    if (configCancelled) {
      return (
        <LoadingScreen
          message="Configuration required"
          subMessage="The application needs to be configured before it can be used."
          action={{
            label: 'Open Configuration',
            onClick: handleReconfigure,
          }}
        />
      )
    }

    return (
      <ConfigDialog
        open={showConfigDialog}
        onConfigured={handleConfigured}
        onCancel={handleConfigCancel}
        isReconfigure={isReconfigure}
      />
    )
  }

  return (
    <>
      <MainLayout onOpenSettings={handleOpenSettings} />
      <ConfigDialog
        open={showConfigDialog}
        onConfigured={handleConfigured}
        onCancel={handleConfigCancel}
        isReconfigure={isReconfigure}
      />
      <SettingsDialog
        open={showSettingsDialog}
        onClose={() => setShowSettingsDialog(false)}
        onSaved={handleSettingsSaved}
      />
    </>
  )
}

export default App
