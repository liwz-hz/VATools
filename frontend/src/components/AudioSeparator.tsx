import React, { useState, useCallback, useEffect, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
  FormControlLabel,
  Checkbox,
  LinearProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
} from '@mui/material'
import { CloudUpload, PlayArrow, Edit, Download, Stop } from '@mui/icons-material'
import { io, Socket } from 'socket.io-client'
import { uploadFile, separateAudio, getSeparationStatus, getTask } from '../services/api'

interface FileData {
  id: number
  filename: string
}

interface SeparatedFile {
  filename: string
  stem: string
  path: string
  id?: number
}

interface EngineStatus {
  name: string
  available: boolean
  error: string | null
  models: Record<string, {
    available: boolean
    description: string
    stems: string[]
  }>
}

const AudioSeparator: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<FileData | null>(null)
  const [stems, setStems] = useState({
    vocals: true,
    drums: true,
    bass: true,
    other: true,
  })
  const [engine, setEngine] = useState<string>('demucs')
  const [model, setModel] = useState<string>('htdemucs_ft')
  const [engineStatus, setEngineStatus] = useState<Record<string, EngineStatus>>({})
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [separatedFiles, setSeparatedFiles] = useState<SeparatedFile[]>([])
  const [playingFile, setPlayingFile] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const socketRef = useRef<Socket | null>(null)

  useEffect(() => {
    socketRef.current = io('http://localhost:5001')

    socketRef.current.on('connect', () => {
      console.log('Socket connected')
    })

    socketRef.current.on('task_progress', (data) => {
      setProgress(data.progress)
      setStatusText(data.status || '处理中...')
    })

    socketRef.current.on('task_completed', (data) => {
      console.log('Task completed:', data)
      setIsProcessing(false)
      setProgress(100)
      setStatusText('完成')
      
      if (data.output_files && Array.isArray(data.output_files)) {
        const files: SeparatedFile[] = data.output_files.map((filePath: string) => {
          const filename = filePath.split('/').pop() || filePath
          const stem = filename.replace('.wav', '').split('_').pop() || 'unknown'
          return {
            filename,
            stem,
            path: filePath,
          }
        })
        setSeparatedFiles(files)
      }
    })

    socketRef.current.on('task_failed', (data) => {
      console.error('Task failed:', data)
      setError(data.error || '处理失败')
      setIsProcessing(false)
    })

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
    }
  }, [])

  useEffect(() => {
    loadEngineStatus()
  }, [])

  const loadEngineStatus = async () => {
    try {
      const status = await getSeparationStatus()
      setEngineStatus(status.engines || {})
      
      // 自动选择可用的引擎
      if (status.engines?.demucs?.available) {
        setEngine('demucs')
      } else if (status.engines?.spleeter?.available) {
        setEngine('spleeter')
      }
    } catch (err) {
      console.error('Failed to load engine status:', err)
    }
  }

  const onDrop = useCallback(async (acceptedFiles: globalThis.File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        setSeparatedFiles([])
        const uploaded = await uploadFile(file)
        setUploadedFile(uploaded)
      } catch (err: unknown) {
        const error = err as { response?: { data?: { error?: string } } }
        setError(error.response?.data?.error || '上传失败')
      }
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/mpeg': ['.mp3'],
      'audio/wav': ['.wav'],
      'audio/flac': ['.flac'],
    },
    maxFiles: 1,
  })

  const handleStemChange = (stem: string) => {
    setStems((prev) => ({
      ...prev,
      [stem]: !prev[stem as keyof typeof prev],
    }))
  }

  const handleSeparate = async () => {
    if (!uploadedFile) return

    setIsProcessing(true)
    setProgress(0)
    setStatusText('开始处理...')
    setError(null)
    setSeparatedFiles([])

    const selectedStems = Object.keys(stems).filter((key) => stems[key as keyof typeof stems])

    try {
      const result = await separateAudio(uploadedFile.id, selectedStems, engine, model)
      const taskId = result.task_id
      
      // 开始轮询任务状态
      const pollInterval = setInterval(async () => {
        try {
          const task = await getTask(taskId)
          setProgress(task.progress || 0)
          setStatusText(task.status === 'processing' ? '处理中...' : task.status)
          
          if (task.status === 'completed') {
            clearInterval(pollInterval)
            setIsProcessing(false)
            setProgress(100)
            setStatusText('完成')
            
            // 解析输出文件
            if (task.output_file) {
              const filePaths = task.output_file.split(',')
              const files: SeparatedFile[] = filePaths.map((filePath: string) => {
                const filename = filePath.split('/').pop() || filePath
                const stem = filename.replace('.wav', '').split('_').pop() || 'unknown'
                return { filename, stem, path: filePath }
              })
              setSeparatedFiles(files)
            }
          } else if (task.status === 'failed') {
            clearInterval(pollInterval)
            setIsProcessing(false)
            setError(task.error_message || '处理失败')
          }
        } catch (err) {
          console.error('Failed to poll task status:', err)
        }
      }, 2000) // 每2秒轮询一次
      
    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string } } }
      setError(error.response?.data?.error || '分离失败')
      setIsProcessing(false)
    }
  }

  const handlePlay = (file: SeparatedFile) => {
    if (playingFile === file.path) {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      setPlayingFile(null)
    } else {
      if (audioRef.current) {
        audioRef.current.pause()
      }
      
      const audio = new Audio(`http://localhost:5001/api/files/serve?path=${encodeURIComponent(file.path)}`)
      audio.play().catch(err => {
        console.error('播放失败:', err)
        setError('音频播放失败，请检查文件是否存在')
      })
      audioRef.current = audio
      setPlayingFile(file.path)
      
      audio.onended = () => {
        setPlayingFile(null)
        audioRef.current = null
      }
    }
  }

  const handleDownload = (file: SeparatedFile) => {
    const link = document.createElement('a')
    link.href = `http://localhost:5001/api/files/serve?path=${encodeURIComponent(file.path)}&download=1`
    link.download = file.filename
    link.click()
  }

  const handleEdit = (file: SeparatedFile) => {
    alert(`编辑功能开发中\n文件路径: ${file.path}`)
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          选择音频文件
        </Typography>
        
        <Box
          {...getRootProps()}
          sx={{
            border: '2px dashed #ccc',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            cursor: 'pointer',
            bgcolor: isDragActive ? 'action.hover' : 'background.paper',
            mb: 2,
          }}
        >
          <input {...getInputProps()} />
          <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
          <Typography>
            {isDragActive ? '放下文件以上传' : '拖拽音频文件到此处，或点击选择'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            支持格式：MP3, WAV, FLAC
          </Typography>
        </Box>

        {uploadedFile && (
          <Alert severity="success" sx={{ mb: 2 }}>
            已上传: {uploadedFile.filename}
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </Paper>

      {uploadedFile && !isProcessing && separatedFiles.length === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            引擎设置
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 150 }}>
              <InputLabel>分离引擎</InputLabel>
              <Select
                value={engine}
                label="分离引擎"
                onChange={(e) => setEngine(e.target.value)}
              >
                {Object.entries(engineStatus).map(([id, status]) => (
                  <MenuItem key={id} value={id} disabled={!status.available}>
                    {status.name} {!status.available && '(不可用)'}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <FormControl sx={{ minWidth: 200 }}>
              <InputLabel>模型</InputLabel>
              <Select
                value={model}
                label="模型"
                onChange={(e) => setModel(e.target.value)}
                disabled={!engineStatus[engine]?.available}
              >
                {engineStatus[engine]?.available && Object.entries(engineStatus[engine].models).map(([id, info]) => (
                  <MenuItem key={id} value={id}>
                    {info.description || id}
                    {info.available ? '' : ' (不可用)'}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
          
          {engineStatus[engine]?.error && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {engineStatus[engine].error}
            </Alert>
          )}
          
          <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
            分离类型
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={stems.vocals}
                  onChange={() => handleStemChange('vocals')}
                />
              }
              label="人声 (Vocals)"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={stems.drums}
                  onChange={() => handleStemChange('drums')}
                />
              }
              label="鼓点 (Drums)"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={stems.bass}
                  onChange={() => handleStemChange('bass')}
                />
              }
              label="贝斯 (Bass)"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={stems.other}
                  onChange={() => handleStemChange('other')}
                />
              }
              label="其他伴奏 (Other)"
            />
          </Box>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            sx={{ mt: 2 }}
            onClick={handleSeparate}
            disabled={!Object.values(stems).some((v) => v) || !engineStatus[engine]?.available}
          >
            开始分离
          </Button>
        </Paper>
      )}

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            处理中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {progress}% - {statusText}
          </Typography>
        </Paper>
      )}

      {separatedFiles.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            分离结果 ({separatedFiles.length} 个文件)
          </Typography>

          <List>
            {separatedFiles.map((file, index) => (
              <ListItem
                key={index}
                secondaryAction={
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <IconButton 
                      edge="end" 
                      onClick={() => handlePlay(file)}
                      color={playingFile === file.path ? 'primary' : 'default'}
                    >
                      {playingFile === file.path ? <Stop /> : <PlayArrow />}
                    </IconButton>
                    <IconButton edge="end" onClick={() => handleEdit(file)}>
                      <Edit />
                    </IconButton>
                    <IconButton edge="end" onClick={() => handleDownload(file)}>
                      <Download />
                    </IconButton>
                  </Box>
                }
              >
                <ListItemText
                  primary={file.filename}
                  secondary={
                    <Box>
                      <Typography variant="body2" component="div" color="text.secondary">
                        {file.stem}
                      </Typography>
                      <Typography variant="caption" component="div" color="text.disabled" sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
                        {file.path}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </Paper>
      )}
    </Box>
  )
}

export default AudioSeparator
