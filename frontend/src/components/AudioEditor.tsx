import React, { useState, useCallback, useRef } from 'react'
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
  Chip,
} from '@mui/material'
import {
  CloudUpload,
  PlayArrow,
  Stop,
  ContentCut,
  Delete,
  Download
} from '@mui/icons-material'
import { uploadFile, clipAudio, getTask } from '../services/api'
import WaveformViewer, { WaveformViewerRef } from './WaveformViewer'

const AudioEditor: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<any>(null)
  const [audioUrl, setAudioUrl] = useState<string>('')
  const [startTime, setStartTime] = useState(0)
  const [endTime, setEndTime] = useState(0)
  const [operation, setOperation] = useState<'extract' | 'delete'>('extract')
  const [outputFormat, setOutputFormat] = useState('mp3')
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [completedFile, setCompletedFile] = useState<{ filename: string; path: string } | null>(null)

  const waveformRef = useRef<WaveformViewerRef>(null)

  const onDrop = useCallback(async (acceptedFiles: any[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        setSuccess(null)
        const uploaded = await uploadFile(file)
        setUploadedFile(uploaded)
        setAudioUrl(URL.createObjectURL(file))
        setCompletedFile(null)
        setStartTime(0)
        setEndTime(0)
      } catch (err: any) {
        setError(err.response?.data?.error || '上传失败')
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

  const handleRegionUpdate = useCallback((start: number, end: number) => {
    setStartTime(start)
    setEndTime(end)
  }, [])

  const handlePlayRegion = () => {
    if (waveformRef.current && startTime < endTime) {
      waveformRef.current.playRegion(startTime, endTime)
    }
  }

  const handleStop = () => {
    if (waveformRef.current) {
      waveformRef.current.stop()
    }
  }

  const handleProcess = async () => {
    if (!uploadedFile) {
      setError('请先上传音频文件')
      return
    }

    if (startTime >= endTime) {
      setError('请选择有效的音频片段（开始时间必须小于结束时间）')
      return
    }

    setIsProcessing(true)
    setProgress(0)
    setError(null)
    setSuccess(null)
    setCompletedFile(null)

    try {
      const result = await clipAudio(uploadedFile.id, operation, startTime, endTime, outputFormat)
      const taskId = result.task_id

      const poll = setInterval(async () => {
        try {
          const task = await getTask(taskId)
          setProgress(task.progress || 0)

          if (task.status === 'completed') {
            clearInterval(poll)
            setIsProcessing(false)
            setProgress(100)
            setSuccess(`${operation === 'extract' ? '片段提取' : '片段删除'}成功！`)
            setCompletedFile({
              filename: task.output_file?.split('/').pop() || `edited_${uploadedFile.filename}`,
              path: task.output_file || '',
            })
          } else if (task.status === 'failed') {
            clearInterval(poll)
            setIsProcessing(false)
            setError(task.error_message || '处理失败')
          }
        } catch {
          clearInterval(poll)
          setIsProcessing(false)
          setError('查询任务状态失败')
        }
      }, 1000)
    } catch (err: any) {
      setError(err.response?.data?.error || '处理失败')
      setIsProcessing(false)
    }
  }

  const handleDownload = () => {
    if (completedFile?.path) {
      const link = document.createElement('a')
      link.href = `http://localhost:5001/api/files/serve?path=${encodeURIComponent(completedFile.path)}&download=1`
      link.download = completedFile.filename
      link.click()
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    const ms = Math.floor((seconds % 1) * 100)
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          上传音频文件
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
            transition: 'all 0.3s ease',
            '&:hover': {
              borderColor: 'primary.main',
              bgcolor: 'action.hover',
            },
          }}
        >
          <input {...getInputProps()} />
          <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
          <Typography variant="body1">
            {isDragActive ? '放下文件以上传' : '拖拽音频文件到此处，或点击选择'}
          </Typography>
          <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
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

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}
      </Paper>

      {audioUrl && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            波形显示与片段选择
          </Typography>

          <Box sx={{ mb: 2 }}>
            <WaveformViewer
              ref={waveformRef}
              audioUrl={audioUrl}
              onRegionUpdate={handleRegionUpdate}
            />
          </Box>

          {startTime < endTime && (
            <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
              <Typography variant="body2" gutterBottom>
                已选择片段：
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <Chip
                  label={`${formatTime(startTime)} - ${formatTime(endTime)}`}
                  color="primary"
                  size="small"
                />
                <Chip
                  label={`时长: ${formatTime(endTime - startTime)}`}
                  color="secondary"
                  size="small"
                  variant="outlined"
                />
              </Box>
            </Paper>
          )}

          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              onClick={handlePlayRegion}
              disabled={startTime >= endTime}
              color="primary"
            >
              播放选区
            </Button>
            <Button
              variant="outlined"
              startIcon={<Stop />}
              onClick={handleStop}
            >
              停止
            </Button>
          </Box>
        </Paper>
      )}

      {uploadedFile && !isProcessing && (
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
              <MenuItem value="extract">
                <Box>
                  <Typography>提取片段</Typography>
                  <Typography variant="caption" color="textSecondary">
                    将选中的片段保存为新文件
                  </Typography>
                </Box>
              </MenuItem>
              <MenuItem value="delete">
                <Box>
                  <Typography>删除片段</Typography>
                  <Typography variant="caption" color="textSecondary">
                    删除选中的片段，保留其余部分
                  </Typography>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>导出格式</InputLabel>
            <Select
              value={outputFormat}
              label="导出格式"
              onChange={(e) => setOutputFormat(e.target.value)}
            >
              <MenuItem value="mp3">MP3 - 压缩格式，文件较小</MenuItem>
              <MenuItem value="wav">WAV - 无损格式，文件较大</MenuItem>
              <MenuItem value="flac">FLAC - 无损压缩，音质最佳</MenuItem>
            </Select>
          </FormControl>

          <Button
            variant="contained"
            startIcon={operation === 'extract' ? <ContentCut /> : <Delete />}
            onClick={handleProcess}
            disabled={isProcessing || startTime >= endTime}
            color={operation === 'delete' ? 'error' : 'primary'}
            fullWidth
            size="large"
          >
            {operation === 'extract' ? '提取片段' : '删除片段'}
          </Button>
        </Paper>
      )}

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            处理中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="textSecondary">
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
            color="primary"
            size="large"
          >
            下载结果
          </Button>
        </Paper>
      )}
    </Box>
  )
}

export default AudioEditor
