import React, { useState, useCallback } from 'react'
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
} from '@mui/material'
import { CloudUpload, PlayArrow, Edit, Download } from '@mui/icons-material'
import { uploadFile, separateAudio } from '../services/api'

interface FileData {
  id: number
  filename: string
}

interface SeparatedFile {
  filename: string
  stem: string
}

const AudioSeparator: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<FileData | null>(null)
  const [stems, setStems] = useState({
    vocals: true,
    drums: true,
    bass: true,
    other: true,
  })
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [separatedFiles, setSeparatedFiles] = useState<SeparatedFile[]>([])

  const onDrop = useCallback(async (acceptedFiles: globalThis.File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        const uploaded = await uploadFile(file)
        setUploadedFile(uploaded)
        setSeparatedFiles([])
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
    setError(null)

    const selectedStems = Object.keys(stems).filter((key) => stems[key as keyof typeof stems])

    try {
      await separateAudio(uploadedFile.id, selectedStems)
      
      setProgress(100)
      setIsProcessing(false)
      
      setSeparatedFiles(
        selectedStems.map((stem) => ({
          filename: `${stem}.wav`,
          stem,
        }))
      )
    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string } } }
      setError(error.response?.data?.error || 'Separation failed')
      setIsProcessing(false)
    }
  }

  const handleDownload = (filename: string) => {
    alert(`Download ${filename}`)
  }

  const handleEdit = (filename: string) => {
    alert(`Edit ${filename}`)
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

      {uploadedFile && !isProcessing && separatedFiles.length === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
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
            disabled={!Object.values(stems).some((v) => v)}
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
            {progress}% 完成
          </Typography>
        </Paper>
      )}

      {separatedFiles.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            分离结果
          </Typography>

          <List>
            {separatedFiles.map((file) => (
              <ListItem
                key={file.stem}
                secondaryAction={
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <IconButton edge="end" onClick={() => alert(`Play ${file.filename}`)}>
                      <PlayArrow />
                    </IconButton>
                    <IconButton edge="end" onClick={() => handleEdit(file.filename)}>
                      <Edit />
                    </IconButton>
                    <IconButton edge="end" onClick={() => handleDownload(file.filename)}>
                      <Download />
                    </IconButton>
                  </Box>
                }
              >
                <ListItemText
                  primary={file.filename}
                  secondary={file.stem}
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
