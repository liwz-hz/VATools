import React, { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  LinearProgress,
  Alert,
  TextField,
} from '@mui/material'
import { CloudUpload, PlayArrow, ContentCut, Download } from '@mui/icons-material'
import { uploadFile, clipAudio } from '../services/api'
import WaveformViewer from './WaveformViewer'

interface FileData {
  id: number
  filename: string
}

interface CompletedFile {
  filename: string
}

const AudioEditor: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<FileData | null>(null)
  const [audioUrl, setAudioUrl] = useState<string>('')
  const [startTime, setStartTime] = useState(0)
  const [endTime, setEndTime] = useState(0)
  const [operation, setOperation] = useState<'extract' | 'delete'>('extract')
  const [outputFormat, setOutputFormat] = useState('mp3')
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [completedFile, setCompletedFile] = useState<CompletedFile | null>(null)

  const onDrop = useCallback(async (acceptedFiles: globalThis.File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        const uploaded = await uploadFile(file)
        setUploadedFile(uploaded)
        setAudioUrl(URL.createObjectURL(file))
        setCompletedFile(null)
      } catch (err: unknown) {
        const error = err as { response?: { data?: { error?: string } } }
        setError(error.response?.data?.error || 'Upload failed')
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

  const handleRegionUpdate = (start: number, end: number) => {
    setStartTime(start)
    setEndTime(end)
  }

  const handleProcess = async () => {
    if (!uploadedFile) return

    setIsProcessing(true)
    setProgress(0)
    setError(null)

    try {
      await clipAudio(uploadedFile.id, operation, startTime, endTime, outputFormat)
      
      setProgress(100)
      setIsProcessing(false)
      setCompletedFile({
        filename: `edited_${uploadedFile.filename}`,
      })
    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string } } }
      setError(error.response?.data?.error || 'Processing failed')
      setIsProcessing(false)
    }
  }

  const handleDownload = async () => {
    if (completedFile) {
      alert('Download functionality will be implemented with actual file tracking')
    }
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
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
      </Paper>

      {audioUrl && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            波形显示与片段选择
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <WaveformViewer audioUrl={audioUrl} onRegionUpdate={handleRegionUpdate} />
          </Box>

          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <TextField
              label="开始时间 (秒)"
              type="number"
              value={startTime.toFixed(1)}
              onChange={(e) => setStartTime(parseFloat(e.target.value))}
              size="small"
            />
            <TextField
              label="结束时间 (秒)"
              type="number"
              value={endTime.toFixed(1)}
              onChange={(e) => setEndTime(parseFloat(e.target.value))}
              size="small"
            />
          </Box>

          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <Button
              variant="outlined"
              startIcon={<PlayArrow />}
              onClick={() => alert('Play selected region')}
            >
              试听选区
            </Button>
          </Box>
        </Paper>
      )}

      {uploadedFile && !isProcessing && !completedFile && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            操作设置
          </Typography>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>操作类型</InputLabel>
            <Select
              value={operation}
              label="操作类型"
              onChange={(e) => setOperation(e.target.value as 'extract' | 'delete')}
            >
              <MenuItem value="extract">提取片段</MenuItem>
              <MenuItem value="delete">删除片段</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>导出格式</InputLabel>
            <Select
              value={outputFormat}
              label="导出格式"
              onChange={(e) => setOutputFormat(e.target.value)}
            >
              <MenuItem value="mp3">MP3</MenuItem>
              <MenuItem value="wav">WAV</MenuItem>
              <MenuItem value="flac">FLAC</MenuItem>
            </Select>
          </FormControl>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              startIcon={<ContentCut />}
              onClick={handleProcess}
              disabled={isProcessing || startTime >= endTime}
            >
              {operation === 'extract' ? '提取片段' : '删除片段'}
            </Button>
          </Box>
        </Paper>
      )}

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            处理中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {progress}% 完成
          </Typography>
        </Paper>
      )}

      {completedFile && (
        <Paper sx={{ p: 3 }}>
          <Alert severity="success" sx={{ mb: 2 }}>
            处理完成: {completedFile.filename}
          </Alert>

          <Button
            variant="contained"
            startIcon={<Download />}
            onClick={handleDownload}
          >
            下载结果
          </Button>
        </Paper>
      )}
    </Box>
  )
}

export default AudioEditor
