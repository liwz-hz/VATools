import { useState } from 'react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import { CssBaseline, AppBar, Toolbar, Typography, Container, Tabs, Tab, Box } from '@mui/material'
import AudioExtractor from './components/AudioExtractor'
import AudioEditor from './components/AudioEditor'
import AudioSeparator from './components/AudioSeparator'
import AudioSubtitle from './components/AudioSubtitle'
import AudioTTS from './components/AudioTTS'
import Settings from './components/Settings'

const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
})

function App() {
  const [currentTab, setCurrentTab] = useState(0)

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue)
  }

  return (
    <ThemeProvider theme={lightTheme}>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            VATools - 音视频处理工具
          </Typography>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
          <Tabs value={currentTab} onChange={handleTabChange}>
            <Tab label="音频提取" />
            <Tab label="音频编辑" />
            <Tab label="音源分离" />
            <Tab label="自动字幕" />
            <Tab label="语音合成" />
            <Tab label="设置" />
          </Tabs>
        </Box>
        <Box sx={{ mt: 2 }}>
          {currentTab === 0 && <AudioExtractor />}
          {currentTab === 1 && <AudioEditor />}
          {currentTab === 2 && <AudioSeparator />}
          {currentTab === 3 && <AudioSubtitle />}
          {currentTab === 4 && <AudioTTS />}
          {currentTab === 5 && <Settings />}
        </Box>
      </Container>
    </ThemeProvider>
  )
}

export default App
