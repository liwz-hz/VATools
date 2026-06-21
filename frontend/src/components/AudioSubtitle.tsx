import React, { useState, useCallback, useEffect, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
  LinearProgress,
  Alert,
  TextField,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import { CloudUpload, Download, Delete, Add } from '@mui/icons-material'
import {
  uploadFile,
  startSubtitle,
  getSubtitleStatus,
  getSubtitleResult,
  exportSubtitle,
  getTask,
} from '../services/api'

interface FileData {
  id: number
  filename: string
}

interface Segment {
  id: number
  start: number
  end: number
  text: string
}

interface AsrModel {
  path: string
}

const AudioSubtitle: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<FileData | null>(null)
  const [models, setModels] = useState<Record<string, AsrModel>>({})
  const [selectedModel, setSelectedModel] = useState('')
  const [language, setLanguage] = useState('auto')
  const [mlxAvailable, setMlxAvailable] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [segments, setSegments] = useState<Segment[]>([])
  const [taskId, setTaskId] = useState<number | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadStatus()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const loadStatus = async () => {
    try {
      const status = await getSubtitleStatus()
      setModels(status.models || {})
      setMlxAvailable(status.mlx_audio_available || false)
      if (status.default_model && status.models?.[status.default_model]) {
        setSelectedModel(status.default_model)
      } else {
        const modelNames = Object.keys(status.models || {})
        if (modelNames.length > 0) setSelectedModel(modelNames[0])
      }
    } catch (err) {
      console.error('Failed to load ASR status:', err)
    }
  }

  const onDrop = useCallback(async (acceptedFiles: globalThis.File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        setSegments([])
        const uploaded = await uploadFile(file)
        setUploadedFile(uploaded)
      } catch (err: unknown) {
        const e = err as { response?: { data?: { error?: string } } }
        setError(e.response?.data?.error || '上传失败')
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

  const handleStart = async () => {
    if (!uploadedFile) return

    setIsProcessing(true)
    setProgress(0)
    setStatusText('开始处理...')
    setError(null)
    setSegments([])

    try {
      const result = await startSubtitle(uploadedFile.id, selectedModel || undefined, language)
      const id = result.task_id
      setTaskId(id)

      pollRef.current = setInterval(async () => {
        try {
          const task = await getTask(id)
          setProgress(task.progress || 0)
          setStatusText(task.status === 'processing' ? '处理中...' : task.status)

          if (task.status === 'completed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setIsProcessing(false)
            setProgress(100)
            setStatusText('完成')
            await loadResult(id)
          } else if (task.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setIsProcessing(false)
            setError(task.error_message || '处理失败')
          }
        } catch (err) {
          console.error('Failed to poll task:', err)
        }
      }, 2000)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } }
      setError(e.response?.data?.error || '识别失败')
      setIsProcessing(false)
    }
  }

  const loadResult = async (id: number) => {
    try {
      const result = await getSubtitleResult(id)
      setSegments(result.segments || [])
    } catch (err) {
      console.error('Failed to load result:', err)
      setError('加载结果失败')
    }
  }

  const handleSegmentChange = (index: number, field: keyof Segment, value: string | number) => {
    setSegments((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      return updated
    })
  }

  const handleDeleteSegment = (index: number) => {
    setSegments((prev) => prev.filter((_, i) => i !== index))
  }

  const handleAddSegment = () => {
    setSegments((prev) => [
      ...prev,
      {
        id: prev.length + 1,
        start: prev.length > 0 ? prev[prev.length - 1].end : 0,
        end: prev.length > 0 ? prev[prev.length - 1].end + 2 : 2,
        text: '',
      },
    ])
  }

  const handleExport = async (format: string) => {
    if (!taskId) return
    try {
      const response = await exportSubtitle(taskId, format, segments)
      const blob = new Blob([response.data])
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `subtitle.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
      setError('导出失败')
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
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </Paper>

      {uploadedFile && !isProcessing && segments.length === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            识别设置
          </Typography>

          {!mlxAvailable && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              mlx-audio 未安装，请运行: pip install mlx-audio==0.4.4
            </Alert>
          )}

          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 250 }}>
              <InputLabel>ASR 模型</InputLabel>
              <Select
                value={selectedModel}
                label="ASR 模型"
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {Object.keys(models).map((name) => (
                  <MenuItem key={name} value={name}>
                    {name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl sx={{ minWidth: 150 }}>
              <InputLabel>语言</InputLabel>
              <Select
                value={language}
                label="语言"
                onChange={(e) => setLanguage(e.target.value)}
              >
                <MenuItem value="auto">自动检测</MenuItem>
                <MenuItem value="zh">中文</MenuItem>
                <MenuItem value="en">英文</MenuItem>
                <MenuItem value="ja">日文</MenuItem>
                <MenuItem value="ko">韩文</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            onClick={handleStart}
            disabled={!mlxAvailable || Object.keys(models).length === 0}
          >
            开始识别
          </Button>
        </Paper>
      )}

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            识别中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {progress}% - {statusText}
          </Typography>
        </Paper>
      )}

      {segments.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              字幕结果 ({segments.length} 条)
            </Typography>
            <Button startIcon={<Add />} onClick={handleAddSegment} size="small">
              添加字幕
            </Button>
          </Box>

          <TableContainer sx={{ maxHeight: 500 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 50 }}>#</TableCell>
                  <TableCell sx={{ width: 120 }}>开始时间(s)</TableCell>
                  <TableCell sx={{ width: 120 }}>结束时间(s)</TableCell>
                  <TableCell>字幕文本</TableCell>
                  <TableCell sx={{ width: 60 }}>操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {segments.map((seg, index) => (
                  <TableRow key={index}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell>
                      <TextField
                        type="number"
                        size="small"
                        value={seg.start}
                        onChange={(e) => handleSegmentChange(index, 'start', parseFloat(e.target.value) || 0)}
                        inputProps={{ step: 0.1, min: 0 }}
                        sx={{ width: 100 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        type="number"
                        size="small"
                        value={seg.end}
                        onChange={(e) => handleSegmentChange(index, 'end', parseFloat(e.target.value) || 0)}
                        inputProps={{ step: 0.1, min: 0 }}
                        sx={{ width: 100 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        fullWidth
                        size="small"
                        value={seg.text}
                        onChange={(e) => handleSegmentChange(index, 'text', e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton size="small" onClick={() => handleDeleteSegment(index)} color="error">
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
            <Button variant="contained" startIcon={<Download />} onClick={() => handleExport('srt')}>
              导出 SRT
            </Button>
            <Button variant="outlined" startIcon={<Download />} onClick={() => handleExport('vtt')}>
              导出 VTT
            </Button>
            <Button variant="outlined" startIcon={<Download />} onClick={() => handleExport('json')}>
              导出 JSON
            </Button>
          </Box>
        </Paper>
      )}
    </Box>
  )
}

export default AudioSubtitle
