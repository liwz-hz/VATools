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
} from '@mui/material'
import { CloudUpload, Download, Edit } from '@mui/icons-material'
import { uploadFile, extractAudio, downloadFile } from '../services/api'

interface FileData {
  id: number
  filename: string
  file_path: string
  file_type: string
  file_size: number
  created_at: string
}

interface CompletedFile {
  id: number
  filename: string
}

const AudioExtractor: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<FileData | null>(null)
  const [outputFormat, setOutputFormat] = useState('mp3')
  const [bitrate, setBitrate] = useState('192k')
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
      'video/mp4': ['.mp4'],
      'video/x-msvideo': ['.avi'],
      'video/quicktime': ['.mov'],
      'video/x-matroska': ['.mkv'],
    },
    maxFiles: 1,
  })

  const handleExtract = async () => {
    if (!uploadedFile) return

    setIsProcessing(true)
    setProgress(0)
    setError(null)

    try {
      const result = await extractAudio(uploadedFile.id, outputFormat, bitrate)
      
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(interval)
            return prev
          }
          return prev + 10
        })
      }, 500)

      const checkTask = setInterval(() => {
        setProgress(100)
        clearInterval(checkTask)
        setIsProcessing(false)
        setCompletedFile({
          id: result.task_id,
          filename: `${uploadedFile.filename}.${outputFormat}`,
        })
      }, 2000)

    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string } } }
      setError(error.response?.data?.error || 'Extraction failed')
      setIsProcessing(false)
    }
  }

  const handleDownload = async () => {
    if (completedFile) {
      const blob = await downloadFile(completedFile.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = completedFile.filename
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  const handleEdit = () => {
    // Navigate to edit tab with file
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          上传视频文件
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
            {isDragActive ? '放下文件以上传' : '拖拽视频文件到此处，或点击选择'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            支持格式：MP4, AVI, MOV, MKV
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

      {uploadedFile && !isProcessing && !completedFile && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            输出设置
          </Typography>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>输出格式</InputLabel>
            <Select
              value={outputFormat}
              label="输出格式"
              onChange={(e) => setOutputFormat(e.target.value)}
            >
              <MenuItem value="mp3">MP3</MenuItem>
              <MenuItem value="wav">WAV</MenuItem>
              <MenuItem value="flac">FLAC</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>比特率</InputLabel>
            <Select
              value={bitrate}
              label="比特率"
              onChange={(e) => setBitrate(e.target.value)}
            >
              <MenuItem value="128k">128 kbps</MenuItem>
              <MenuItem value="192k">192 kbps</MenuItem>
              <MenuItem value="256k">256 kbps</MenuItem>
              <MenuItem value="320k">320 kbps</MenuItem>
            </Select>
          </FormControl>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            onClick={handleExtract}
            disabled={isProcessing}
          >
            开始提取
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
            {progress}% 完成
          </Typography>
        </Paper>
      )}

      {completedFile && (
        <Paper sx={{ p: 3 }}>
          <Alert severity="success" sx={{ mb: 2 }}>
            提取完成: {completedFile.filename}
          </Alert>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              startIcon={<Download />}
              onClick={handleDownload}
            >
              下载
            </Button>
            <Button
              variant="outlined"
              startIcon={<Edit />}
              onClick={handleEdit}
            >
              进入编辑
            </Button>
          </Box>
        </Paper>
      )}
    </Box>
  )
}

export default AudioExtractor
