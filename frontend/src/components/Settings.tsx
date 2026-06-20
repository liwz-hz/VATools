import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Grid,
} from '@mui/material'
import { Save, Restore } from '@mui/icons-material'
import { getConfig, updateConfig, resetConfig } from '../services/api'

const Settings: React.FC = () => {
  const [config, setConfig] = useState<Record<string, string>>({})
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await getConfig()
      setConfig(data)
    } catch {
      setError('Failed to load config')
    }
  }

  const handleChange = (key: string, value: string) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  const handleSave = async () => {
    try {
      await updateConfig(config)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('Failed to save config')
    }
  }

  const handleReset = async () => {
    try {
      const data = await resetConfig()
      setConfig(data)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('Failed to reset config')
    }
  }

  return (
    <Box>
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          配置已保存
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          工作目录设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="上传目录"
              value={config.upload_dir || ''}
              onChange={(e) => handleChange('upload_dir', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="输出目录"
              value={config.workspace_dir || ''}
              onChange={(e) => handleChange('workspace_dir', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="最大文件大小 (MB)"
              value={parseInt(config.max_file_size || '0') / (1024 * 1024)}
              onChange={(e) => handleChange('max_file_size', String(parseInt(e.target.value) * 1024 * 1024))}
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          日志设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="日志目录"
              value={config.log_dir || ''}
              onChange={(e) => handleChange('log_dir', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>日志级别</InputLabel>
              <Select
                value={config.log_level || 'INFO'}
                label="日志级别"
                onChange={(e) => handleChange('log_level', e.target.value)}
              >
                <MenuItem value="DEBUG">DEBUG</MenuItem>
                <MenuItem value="INFO">INFO</MenuItem>
                <MenuItem value="WARNING">WARNING</MenuItem>
                <MenuItem value="ERROR">ERROR</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="日志大小 (MB)"
              value={parseInt(config.log_max_size || '0') / (1024 * 1024)}
              onChange={(e) => handleChange('log_max_size', String(parseInt(e.target.value) * 1024 * 1024))}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="保留天数"
              value={config.log_retention_days || '30'}
              onChange={(e) => handleChange('log_retention_days', e.target.value)}
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          音频设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>默认格式</InputLabel>
              <Select
                value={config.default_audio_format || 'mp3'}
                label="默认格式"
                onChange={(e) => handleChange('default_audio_format', e.target.value)}
              >
                <MenuItem value="mp3">MP3</MenuItem>
                <MenuItem value="wav">WAV</MenuItem>
                <MenuItem value="flac">FLAC</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>默认比特率</InputLabel>
              <Select
                value={config.default_bitrate || '192k'}
                label="默认比特率"
                onChange={(e) => handleChange('default_bitrate', e.target.value)}
              >
                <MenuItem value="128k">128 kbps</MenuItem>
                <MenuItem value="192k">192 kbps</MenuItem>
                <MenuItem value="256k">256 kbps</MenuItem>
                <MenuItem value="320k">320 kbps</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="采样率 (Hz)"
              value={config.default_sample_rate || '44100'}
              onChange={(e) => handleChange('default_sample_rate', e.target.value)}
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          音源分离设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>分离模型</InputLabel>
              <Select
                value={config.separation_model || 'spleeter'}
                label="分离模型"
                onChange={(e) => handleChange('separation_model', e.target.value)}
              >
                <MenuItem value="spleeter">Spleeter</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>加速方式</InputLabel>
              <Select
                value={config.acceleration_type || 'auto'}
                label="加速方式"
                onChange={(e) => handleChange('acceleration_type', e.target.value)}
              >
                <MenuItem value="auto">自动检测</MenuItem>
                <MenuItem value="mps">MPS (Metal Performance Shaders)</MenuItem>
                <MenuItem value="mlx">MLX (Apple MLX)</MenuItem>
                <MenuItem value="cpu">CPU</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>输出格式</InputLabel>
              <Select
                value={config.separation_output_format || 'wav'}
                label="输出格式"
                onChange={(e) => handleChange('separation_output_format', e.target.value)}
              >
                <MenuItem value="wav">WAV</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          variant="contained"
          startIcon={<Save />}
          onClick={handleSave}
        >
          保存配置
        </Button>
        <Button
          variant="outlined"
          startIcon={<Restore />}
          onClick={handleReset}
        >
          恢复默认
        </Button>
      </Box>
    </Box>
  )
}

export default Settings
